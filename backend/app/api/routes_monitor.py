"""
routes_monitor.py — Real-time monitoring control endpoints + SSE stream.

Endpoints:
    POST /api/monitor/start           → Start K8s Watch API listener
    POST /api/monitor/stop            → Stop watcher gracefully
    GET  /api/monitor/status          → Current monitoring status
    GET  /api/monitor/events/stream   → SSE stream of GRAPH_UPDATE events
    GET  /api/monitor/events          → Recent events from DB (REST)
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.database import get_recent_monitoring_events
from app.services.broadcast_service import (
    connected_client_count,
    register_client,
    unregister_client,
)
from app.services.fallback_poller import get_poller
from app.services.watch_service import get_watch_status, start_watching, stop_watching
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Control endpoints ──────────────────────────────────────────────────────────

@router.post("/start")
async def start_monitor():
    """
    Start real-time K8s Watch API monitoring.

    Connects to the current kubectl context and begins streaming events for:
    pods, serviceaccounts, secrets, roles, clusterroles,
    rolebindings, clusterrolebindings.

    Requires MOCK_MODE=false in .env.
    """
    if settings.MOCK_MODE:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot start monitoring in MOCK_MODE. "
                "Set MOCK_MODE=false in .env and restart the server."
            ),
        )

    try:
        result = await start_watching()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("start_monitor failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
async def stop_monitor():
    """Stop real-time monitoring. Also stops fallback poller if active."""
    result = await stop_watching()

    # Also stop fallback poller if it's running
    poller = get_poller()
    if poller.running:
        await poller.stop()

    return result


@router.get("/status")
async def monitor_status():
    """
    Get current monitoring status.

    Returns:
        watching            — Is watch API active?
        fallback_active     — Is fallback polling active instead?
        uptime_seconds      — Seconds since watch started
        events_processed    — Total K8s events received
        pending_events      — Events waiting in debounce queue
        sse_clients         — Connected SSE frontend clients
        resources_watched   — Number of resource types watched
    """
    status = get_watch_status()
    status["sse_clients"] = connected_client_count()
    status["fallback_status"] = get_poller().get_status()
    return status


# ── SSE stream endpoint ────────────────────────────────────────────────────────

@router.get("/events/stream")
async def events_stream():
    """
    Server-Sent Events (SSE) stream of real-time graph updates.

    Connect from the frontend with::

        const es = new EventSource('/api/monitor/events/stream');
        es.onmessage = (e) => {
            const update = JSON.parse(e.data);
            // update.type === "GRAPH_UPDATE"
            // update.diff  === full DiffResult
            // update.run_id, update.timestamp
        };

    A ``: heartbeat`` comment is sent every 25 seconds to keep the
    connection alive through proxies / load balancers.
    """

    async def generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        register_client(queue)

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxy connections alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass  # Client disconnected
        except GeneratorExit:
            pass
        finally:
            unregister_client(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
        },
    )


# ── Recent events (REST) ───────────────────────────────────────────────────────

@router.get("/events")
def recent_events(limit: int = 20):
    """
    Return the most recent monitoring events from the database.

    Useful for building an audit log / events timeline in the UI.
    """
    events = get_recent_monitoring_events(
        cluster_name=settings.CLUSTER_NAME, limit=limit
    )
    return {"events": events, "count": len(events)}
