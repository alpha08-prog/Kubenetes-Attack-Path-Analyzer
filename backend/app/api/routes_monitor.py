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
    broadcast_graph_update,
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


# ── Test / dev helper ─────────────────────────────────────────────────────────

@router.post("/test-event")
async def fire_test_event():
    """
    Broadcast a synthetic GRAPH_UPDATE event to all connected SSE clients.

    Useful for:
    • Verifying the SSE pipeline works end-to-end without touching K8s
    • Testing the frontend Monitor tab locally with only minikube installed
    • Demoing the real-time alert UI

    Returns the number of SSE clients that received the message.
    """
    import uuid
    from datetime import datetime, timezone

    fake_run_id = uuid.uuid4().hex[:8]

    fake_diff = {
        "meta": {
            "run_id_before":  "test-baseline",
            "run_id_after":   fake_run_id,
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "cluster":        settings.CLUSTER_NAME,
        },
        "risk_delta": {
            "before":          5.2,
            "after":           6.8,
            "delta":           1.6,
            "delta_pct":       30.8,
            "direction":       "increase",
            "severity_before": "medium",
            "severity_after":  "high",
        },
        "path_delta": {
            "before":    2,
            "after":     3,
            "delta":     1,
            "direction": "increase",
            "label":     "1 new attack path introduced",
        },
        "cycle_delta": {
            "before":    0,
            "after":     1,
            "delta":     1,
            "direction": "increase",
            "label":     "1 new privilege escalation cycle detected",
        },
        "node_changes": {
            "added":   ["pod:default:test-nginx"],
            "removed": [],
            "changed": [],
        },
        "severity_shift": {
            "critical": {"before": 1, "after": 2, "delta": 1},
            "high":     {"before": 3, "after": 3, "delta": 0},
            "medium":   {"before": 5, "after": 4, "delta": -1},
            "low":      {"before": 2, "after": 2, "delta": 0},
        },
        "top_new_risks": [
            {"node_id": "pod:default:test-nginx", "label": "test-nginx", "risk_score": 7.4, "node_type": "pod"},
        ],
        "top_improved": [],
        "recommendation": (
            "A new high-risk pod was detected. "
            "Review the service account bound to test-nginx and check for "
            "overly permissive role bindings. Consider applying network policies."
        ),
    }

    clients_before = connected_client_count()
    await broadcast_graph_update(fake_diff, fake_run_id)

    return {
        "status":          "broadcast_sent",
        "run_id":          fake_run_id,
        "sse_clients":     clients_before,
        "message":         f"Test GRAPH_UPDATE sent to {clients_before} client(s). "
                           "Check the Monitor tab → Session Events in your browser.",
    }


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
