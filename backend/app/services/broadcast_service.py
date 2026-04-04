"""
broadcast_service.py — Server-Sent Events (SSE) broadcaster.

Keeps a registry of connected frontend clients and pushes graph-update
messages to all of them whenever the Watch API detects a significant change.

Why SSE instead of WebSocket?
    SSE is unidirectional (server → client), automatically reconnects, and
    needs zero extra client-side library.  For our use case — the server
    pushing updates to the dashboard — SSE is the right tool.

Usage (backend):
    await broadcast_graph_update(diff_result, new_run_id)

Usage (frontend):
    const es = new EventSource('/api/monitor/events/stream');
    es.onmessage = (e) => { const update = JSON.parse(e.data); ... };
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Global client registry ────────────────────────────────────────────────────
# Each connected SSE client gets its own asyncio.Queue.
# When a graph update arrives we push a JSON string to every queue.
_clients: List[asyncio.Queue] = []


# ── Public helpers ─────────────────────────────────────────────────────────────

def register_client(queue: asyncio.Queue) -> None:
    """Called by the SSE endpoint when a new frontend client connects."""
    _clients.append(queue)
    logger.info("SSE client connected  — total clients: %d", len(_clients))


def unregister_client(queue: asyncio.Queue) -> None:
    """Called when a client disconnects or times out."""
    if queue in _clients:
        _clients.remove(queue)
    logger.info("SSE client disconnected — total clients: %d", len(_clients))


def connected_client_count() -> int:
    return len(_clients)


async def broadcast_graph_update(
    diff_result: Dict[str, Any],
    new_run_id: str,
) -> None:
    """
    Push a GRAPH_UPDATE event to every connected SSE client.

    Message shape::

        {
            "type":    "GRAPH_UPDATE",
            "run_id":  "a3f9b2c1",
            "diff":    { ...full diff_result... },
            "timestamp": "2026-04-04T14:30:12Z"
        }
    """
    if not _clients:
        logger.debug("No SSE clients connected — skipping broadcast")
        return

    message = json.dumps(
        {
            "type":      "GRAPH_UPDATE",
            "run_id":    new_run_id,
            "diff":      diff_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    dead: List[asyncio.Queue] = []
    for q in list(_clients):  # iterate over a snapshot
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("SSE client queue full — marking for removal")
            dead.append(q)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error pushing to SSE client: %s", exc)
            dead.append(q)

    for q in dead:
        unregister_client(q)

    logger.info(
        "Broadcast GRAPH_UPDATE run=%s to %d client(s) (%d dead removed)",
        new_run_id,
        len(_clients),
        len(dead),
    )


async def broadcast_raw(message: str) -> None:
    """
    Broadcast an arbitrary pre-serialised JSON string.
    Useful for heartbeats or custom event types.
    """
    if not _clients:
        return
    dead: List[asyncio.Queue] = []
    for q in list(_clients):
        try:
            q.put_nowait(message)
        except Exception:  # noqa: BLE001
            dead.append(q)
    for q in dead:
        unregister_client(q)
