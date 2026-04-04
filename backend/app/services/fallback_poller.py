"""
fallback_poller.py — Periodic polling fallback for the Watch API.

Activated automatically by watch_service when the K8s Watch API is
unavailable or has failed too many consecutive times.

Every FALLBACK_POLL_INTERVAL_SEC seconds (default 300 / 5 minutes):
    1. Call ingest_and_build() to rebuild the attack graph
    2. Hash the graph summary
    3. If the summary changed → call analyze_changes([]) to trigger
       the full diff / alert pipeline
    4. Sleep and repeat

The poller stops itself when watch_service manages to reconnect (it sets
_poller.running = False from the watch loop).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Dict, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackPoller:
    """Periodic-polling monitor, used when the Watch API is unavailable."""

    def __init__(self, interval_sec: int = None) -> None:
        self.interval_sec: int = interval_sec or settings.FALLBACK_POLL_INTERVAL_SEC
        self.running: bool = False
        self._last_hash: Optional[str] = None
        self._poll_count: int = 0
        self._poll_task: asyncio.Task | None = None

    # ── Public API ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the polling loop in the background."""
        if self.running:
            return
        self.running = True
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="fallback-poller"
        )
        logger.info(
            "FallbackPoller started (interval=%ds)", self.interval_sec
        )

    async def stop(self) -> None:
        """Stop the polling loop."""
        self.running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await asyncio.wait_for(self._poll_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        logger.info("FallbackPoller stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "running":       self.running,
            "interval_sec":  self.interval_sec,
            "polls_done":    self._poll_count,
        }

    # ── Internal loop ───────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self.running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.error("FallbackPoller error: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self.interval_sec)
            except asyncio.CancelledError:
                break

    async def _poll_once(self) -> None:
        """
        Rebuild the graph from the current cluster state and check if
        anything changed since the last poll.
        """
        from app.services.ingestion_service import ingest_and_build

        loop = asyncio.get_running_loop()
        summary: Dict[str, Any] = await loop.run_in_executor(None, ingest_and_build)
        self._poll_count += 1

        current_hash = _hash_summary(summary)

        if current_hash != self._last_hash:
            logger.info(
                "FallbackPoller: cluster state changed (poll #%d), triggering analysis",
                self._poll_count,
            )
            self._last_hash = current_hash
            from app.services.watch_decision_engine import analyze_changes
            await analyze_changes([])  # empty events list — diff handles it
        else:
            logger.debug(
                "FallbackPoller: no change detected (poll #%d)", self._poll_count
            )


# ── Module-level singleton ─────────────────────────────────────────────────────

_poller: Optional[FallbackPoller] = None


def get_poller() -> FallbackPoller:
    global _poller
    if _poller is None:
        _poller = FallbackPoller()
    return _poller


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash_summary(summary: Dict[str, Any]) -> str:
    """Stable hash of graph summary for change detection."""
    key = json.dumps(
        {
            "node_count": summary.get("node_count", 0),
            "edge_count": summary.get("edge_count", 0),
            "source":     summary.get("source", ""),
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]
