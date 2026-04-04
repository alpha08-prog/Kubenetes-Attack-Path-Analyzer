"""
event_debouncer.py — Batches rapid K8s events for efficient processing.

Problem it solves:
    When a Kubernetes rolling-deploy lands, 20–100 events arrive in <200 ms.
    Rebuilding the attack graph after each individual event wastes CPU and
    produces a stream of near-identical Slack alerts.

Solution:
    Accumulate events in a 2-second sliding window, deduplicate by resource
    UID, then hand off a single batched list to the decision engine.
"""

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)


class EventDebouncer:
    """
    Collects incoming K8s watch events and flushes them as a single batch
    after ``debounce_ms`` milliseconds of *silence*.

    The flush callback is an async function that receives the deduplicated
    event list::

        async def on_flush(events: list[dict]) -> None:
            await analyze_changes(events)

        debouncer = EventDebouncer(debounce_ms=2000, on_flush=on_flush)
        await debouncer.queue_event(event_dict)
    """

    def __init__(
        self,
        debounce_ms: int = 2000,
        on_flush: Callable[[List[Dict[str, Any]]], Coroutine] = None,
    ) -> None:
        self.debounce_ms = debounce_ms
        self.on_flush = on_flush
        self._queue: List[Dict[str, Any]] = []
        self._flush_task: asyncio.Task | None = None
        # uid → latest event for deduplication
        self._seen: Dict[str, Dict[str, Any]] = {}

    # ── Public API ──────────────────────────────────────────────────────────────

    async def queue_event(self, event: Dict[str, Any]) -> None:
        """
        Enqueue a K8s watch event.

        Calling this method resets the debounce timer so that a *burst* of
        events will be collected into one flush rather than many.
        """
        uid = self._uid_for(event)
        self._seen[uid] = event           # keep only the *latest* state
        self._queue.append(event)

        # Cancel any pending flush and start a fresh timer
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

        self._flush_task = asyncio.create_task(self._delayed_flush())

    def get_queue_size(self) -> int:
        """Current number of queued (un-flushed) events."""
        return len(self._queue)

    async def flush_now(self) -> None:
        """Immediately flush whatever is in the queue (used for testing)."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        await self._do_flush()

    # ── Internals ───────────────────────────────────────────────────────────────

    async def _delayed_flush(self) -> None:
        """Wait for the debounce window, then flush."""
        try:
            await asyncio.sleep(self.debounce_ms / 1000.0)
            await self._do_flush()
        except asyncio.CancelledError:
            pass  # Another event arrived, timer was reset

    async def _do_flush(self) -> None:
        if not self._seen:
            return

        # Snapshot and reset before calling on_flush to avoid re-entrancy issues
        deduplicated = list(self._seen.values())
        self._queue.clear()
        self._seen.clear()
        self._flush_task = None

        logger.info(
            "Debouncer flushing %d unique resource change(s)", len(deduplicated)
        )

        if self.on_flush:
            try:
                await self.on_flush(deduplicated)
            except Exception as exc:  # noqa: BLE001
                logger.error("Debouncer on_flush callback raised: %s", exc, exc_info=True)

    @staticmethod
    def _uid_for(event: Dict[str, Any]) -> str:
        """Build a stable deduplication key from the event."""
        obj = event.get("object") or {}
        meta = {}
        if hasattr(obj, "metadata") and obj.metadata:
            # kubernetes Python client object
            meta = {"uid": getattr(obj.metadata, "uid", ""), "name": getattr(obj.metadata, "name", "")}
        elif isinstance(obj, dict):
            meta = obj.get("metadata", {})

        uid = meta.get("uid") or meta.get("name") or ""
        resource_type = event.get("resource_type", "")
        return f"{resource_type}:{uid}" if uid else f"{resource_type}:{id(event)}"
