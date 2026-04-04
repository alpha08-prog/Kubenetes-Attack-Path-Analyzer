"""
watch_service.py — Real-time Kubernetes cluster monitoring via Watch API.

Maintains a long-lived stream connection to the K8s API server and forwards
change events (ADDED / MODIFIED / DELETED) for seven security-relevant
resource types to the EventDebouncer, which batches them before handing
off to the decision engine.

Resilience strategy
-------------------
* Connection failure  → exponential back-off (5 s, 10 s, 20 s … max 60 s)
* 3 consecutive total failures → gracefully switch to FallbackPoller
* GracefulStop (POST /monitor/stop or app shutdown) → clean task cancellation

Resource types watched
-----------------------
    pods, serviceaccounts, secrets
    roles, clusterroles, rolebindings, clusterrolebindings
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.database import upsert_monitoring_config
from app.services.event_debouncer import EventDebouncer
from app.services.watch_decision_engine import analyze_changes
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Resource definitions: (api_group, resource_name, is_cluster_scoped)
_WATCHED_RESOURCES: List[tuple[str, str, bool]] = [
    ("v1",                               "pods",                  False),
    ("v1",                               "serviceaccounts",       False),
    ("v1",                               "secrets",               False),
    ("rbac.authorization.k8s.io/v1",     "roles",                 False),
    ("rbac.authorization.k8s.io/v1",     "clusterroles",          True),
    ("rbac.authorization.k8s.io/v1",     "rolebindings",          False),
    ("rbac.authorization.k8s.io/v1",     "clusterrolebindings",   True),
]

_MAX_RECONNECT_DELAY = 60     # seconds
_MAX_FAILURES_BEFORE_FALLBACK = 3


class KubernetesWatcher:
    """
    Watches a Kubernetes cluster for resource changes using the K8s Watch API
    and drives the analysis/alert pipeline on significant changes.
    """

    def __init__(self) -> None:
        self.watching: bool = False
        self._debouncer: EventDebouncer = EventDebouncer(
            debounce_ms=settings.WATCH_DEBOUNCE_MS,
            on_flush=analyze_changes,
        )
        self._watch_task: asyncio.Task | None = None
        self._consecutive_failures: int = 0
        self._events_processed: int = 0
        self._alerts_triggered: int = 0
        self._started_at: Optional[datetime] = None
        self._last_event_at: Optional[datetime] = None
        self._fallback_active: bool = False

    # ── Public control ──────────────────────────────────────────────────────────

    async def start(self) -> Dict[str, Any]:
        """
        Start the background Watch API loop.

        Tries to load K8s credentials from kubeconfig (local dev) or
        in-cluster service account (production pod).

        Returns status dict.
        Raises ValueError if K8s config cannot be loaded.
        """
        if self.watching:
            return {
                "status": "already_watching",
                "message": "Watch is already running",
                "resources": len(_WATCHED_RESOURCES),
            }

        # Validate K8s connectivity before starting
        _load_k8s_config()

        self.watching = True
        self._started_at = datetime.now(timezone.utc)
        self._consecutive_failures = 0
        self._fallback_active = False

        upsert_monitoring_config(
            settings.CLUSTER_NAME,
            watching=1,
            watch_started_at=self._started_at.isoformat(),
            watch_stopped_at=None,
            alert_threshold_risk_delta=settings.ALERT_RISK_DELTA_THRESHOLD,
            alert_on_new_paths=int(settings.ALERT_ON_NEW_PATHS),
            alert_on_new_cycles=int(settings.ALERT_ON_NEW_CYCLES),
        )

        self._watch_task = asyncio.create_task(
            self._watch_loop(), name="k8s-watch-loop"
        )

        logger.info(
            "K8s Watch started — cluster=%s, resources=%d, debounce=%dms",
            settings.CLUSTER_NAME,
            len(_WATCHED_RESOURCES),
            settings.WATCH_DEBOUNCE_MS,
        )

        return {
            "status": "watching",
            "resources": len(_WATCHED_RESOURCES),
            "message": f"Watching {len(_WATCHED_RESOURCES)} resource type(s)",
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop the watcher gracefully."""
        self.watching = False

        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await asyncio.wait_for(self._watch_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._watch_task = None

        upsert_monitoring_config(
            settings.CLUSTER_NAME,
            watching=0,
            watch_stopped_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("K8s Watch stopped")
        return {"status": "stopped", "message": "Watch stopped"}

    def get_status(self) -> Dict[str, Any]:
        """Return a status summary dict."""
        uptime_sec: Optional[int] = None
        if self._started_at and self.watching:
            uptime_sec = int(
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
            )

        return {
            "watching":            self.watching,
            "fallback_active":     self._fallback_active,
            "started_at":          self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds":      uptime_sec,
            "cluster":             settings.CLUSTER_NAME,
            "debounce_ms":         settings.WATCH_DEBOUNCE_MS,
            "alert_threshold":     settings.ALERT_RISK_DELTA_THRESHOLD,
            "resources_watched":   len(_WATCHED_RESOURCES),
            "events_processed":    self._events_processed,
            "pending_events":      self._debouncer.get_queue_size(),
            "last_event_at":       self._last_event_at.isoformat() if self._last_event_at else None,
        }

    # ── Watch loop ──────────────────────────────────────────────────────────────

    async def _watch_loop(self) -> None:
        """
        Outer resilience loop.  Each iteration attempts to watch all resources;
        on failure it waits with back-off before retrying.
        Falls back to polling after _MAX_FAILURES_BEFORE_FALLBACK consecutive errors.
        """
        delay = settings.WATCH_RECONNECT_DELAY_SEC

        while self.watching:
            try:
                await self._watch_all_resources()
                # Reached here means clean exit (self.watching set to False)
            except asyncio.CancelledError:
                logger.info("Watch loop cancelled")
                break
            except Exception as exc:  # noqa: BLE001
                if not self.watching:
                    break

                self._consecutive_failures += 1
                logger.error(
                    "Watch loop error (attempt %d): %s",
                    self._consecutive_failures,
                    exc,
                    exc_info=True,
                )

                if self._consecutive_failures >= _MAX_FAILURES_BEFORE_FALLBACK:
                    logger.warning(
                        "Switching to fallback polling after %d failures",
                        self._consecutive_failures,
                    )
                    await self._activate_fallback()
                    break

                # Exponential back-off
                actual_delay = min(delay * (2 ** (self._consecutive_failures - 1)), _MAX_RECONNECT_DELAY)
                logger.info("Reconnecting in %ds…", actual_delay)
                await asyncio.sleep(actual_delay)

    async def _watch_all_resources(self) -> None:
        """
        Stream events from every watched resource type.
        Uses the kubernetes Python client's Watch() iterator.
        """
        try:
            from kubernetes import client as k8s_client, config as k8s_config, watch
        except ImportError:
            raise RuntimeError(
                "kubernetes package not installed. "
                "Run: pip install kubernetes>=30.1.0"
            )

        _load_k8s_config()

        core_v1   = k8s_client.CoreV1Api()
        rbac_v1   = k8s_client.RbacAuthorizationV1Api()

        # Map resource → (api_instance, list_method_namespaced, list_method_cluster)
        resource_map = {
            "pods":                  (core_v1,  core_v1.list_namespaced_pod,                  core_v1.list_pod_for_all_namespaces),
            "serviceaccounts":       (core_v1,  core_v1.list_namespaced_service_account,       core_v1.list_service_account_for_all_namespaces),
            "secrets":               (core_v1,  core_v1.list_namespaced_secret,                core_v1.list_secret_for_all_namespaces),
            "roles":                 (rbac_v1,  rbac_v1.list_namespaced_role,                  rbac_v1.list_role_for_all_namespaces),
            "clusterroles":          (rbac_v1,  None,                                           rbac_v1.list_cluster_role),
            "rolebindings":          (rbac_v1,  rbac_v1.list_namespaced_role_binding,           rbac_v1.list_role_binding_for_all_namespaces),
            "clusterrolebindings":   (rbac_v1,  None,                                           rbac_v1.list_cluster_role_binding),
        }

        tasks = []
        for _, resource_name, is_cluster_scoped in _WATCHED_RESOURCES:
            if resource_name not in resource_map:
                continue
            _, namespaced_fn, all_ns_fn = resource_map[resource_name]
            # Always use the all-namespaces / cluster-scoped list fn so we
            # receive events from every namespace in a single stream.
            # cluster-scoped resources (clusterroles, clusterrolebindings) use
            # their dedicated list_cluster_* method; namespaced resources use
            # list_*_for_all_namespaces — both are stored in all_ns_fn.
            list_fn = all_ns_fn
            tasks.append(
                asyncio.create_task(
                    self._stream_resource(resource_name, list_fn, watch),
                    name=f"watch-{resource_name}",
                )
            )

        # Run all resource watchers concurrently; stop all if any fail
        try:
            await asyncio.gather(*tasks)
        except Exception:
            for t in tasks:
                t.cancel()
            raise
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()

    async def _stream_resource(
        self,
        resource_type: str,
        list_fn,
        watch_module,
    ) -> None:
        """Stream events for one resource type and queue them to the debouncer."""
        w = watch_module.Watch()
        logger.debug("Streaming %s…", resource_type)

        try:
            # watch.stream is a blocking generator — run it in a thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._sync_stream(resource_type, list_fn, w),
            )
        except Exception:
            w.stop()
            raise

    def _sync_stream(self, resource_type: str, list_fn, w) -> None:
        """
        Blocking: iterate K8s watch stream and schedule debouncer.queue_event
        on the asyncio event loop.
        This runs in a thread-pool executor so it doesn't block the loop.
        """
        loop = asyncio.get_event_loop()

        for raw_event in w.stream(list_fn, timeout_seconds=30):
            if not self.watching:
                w.stop()
                return

            event = {
                "k8s_event_type": raw_event.get("type"),        # ADDED|MODIFIED|DELETED
                "resource_type":  resource_type,
                "object":         raw_event.get("object"),
            }

            self._events_processed += 1
            self._last_event_at = datetime.now(timezone.utc)
            self._consecutive_failures = 0  # Reset on successful event

            # Schedule async queue_event on the event loop from this thread
            asyncio.run_coroutine_threadsafe(
                self._debouncer.queue_event(event), loop
            )

    # ── Fallback ────────────────────────────────────────────────────────────────

    async def _activate_fallback(self) -> None:
        """Switch to the periodic polling fallback."""
        self._fallback_active = True
        from app.services.fallback_poller import get_poller
        poller = get_poller()
        await poller.start()


# ── Module-level singleton ─────────────────────────────────────────────────────

_watcher: Optional[KubernetesWatcher] = None


def get_watcher() -> KubernetesWatcher:
    global _watcher
    if _watcher is None:
        _watcher = KubernetesWatcher()
    return _watcher


async def start_watching() -> Dict[str, Any]:
    return await get_watcher().start()


async def stop_watching() -> Dict[str, Any]:
    return await get_watcher().stop()


def get_watch_status() -> Dict[str, Any]:
    return get_watcher().get_status()


# ── K8s config loader (shared) ─────────────────────────────────────────────────

def _load_k8s_config() -> None:
    """
    Try in-cluster config first (running as a K8s pod), fall back to kubeconfig.
    Raises ValueError with a helpful message if neither works.
    """
    try:
        from kubernetes import config as k8s_config
    except ImportError:
        raise RuntimeError(
            "kubernetes package not installed. Run: pip install kubernetes>=30.1.0"
        )

    try:
        k8s_config.load_incluster_config()
        return
    except Exception:
        pass  # Not in-cluster — try kubeconfig

    try:
        k8s_config.load_kube_config()
        return
    except Exception as exc:
        raise ValueError(
            f"Cannot connect to Kubernetes: {exc}. "
            "Make sure minikube / kubectl is running and kubeconfig is accessible."
        ) from exc
