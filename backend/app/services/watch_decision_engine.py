"""
watch_decision_engine.py — Alert decision logic for Watch API events.

Receives a deduplicated batch of K8s resource changes, rebuilds the attack
graph, compares it against the previous run, and decides which (if any)
alerts to send.

Alert types (configured via settings):
    RISK_INCREASE   — overall risk delta > ALERT_RISK_DELTA_THRESHOLD
    NEW_ATTACK_PATHS — new attack paths discovered
    NEW_CYCLES       — new privilege escalation cycles detected

On alert:
    1. Send Slack alert via slack_service
    2. Broadcast SSE update to frontend via broadcast_service
    3. Record monitoring_event row in SQLite
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.config import settings
from app.core.database import record_monitoring_event
from app.services.broadcast_service import broadcast_graph_update
from app.services.graph_diff_service import diff_runs
from app.services.history_service import get_run_history, record_analysis_run
from app.services.ingestion_service import ingest_and_build
from app.services.slack_service import send_attack_path_alert, send_critical_alert, send_cycle_alert
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Main entry point ──────────────────────────────────────────────────────────

async def analyze_changes(events: List[Dict[str, Any]]) -> None:
    """
    Called by EventDebouncer after the debounce window expires.

    Steps:
        1. Fetch previous run from history
        2. Rebuild graph from current cluster state (kubectl or mock)
        3. Record the new run in history
        4. Diff the two runs
        5. Check alert thresholds
        6. Fire alerts (Slack + SSE + DB) if thresholds exceeded
    """
    logger.info("watch_decision_engine: analysing %d event(s)", len(events))

    try:
        # ── 1. Previous run ──────────────────────────────────────────────────
        history = get_run_history(limit=1, cluster_name=settings.CLUSTER_NAME)
        if not history:
            logger.warning("No prior analysis run — skipping diff (first run?)")
            # Still record the current state as baseline
            _rebuild_and_record()
            return

        previous_run_id: str = history[0]["run_id"]

        # ── 2 + 3. Rebuild graph & record ────────────────────────────────────
        new_run_id = _rebuild_and_record()
        if new_run_id is None:
            return

        # Guard: don't diff a run against itself (can happen if record_analysis_run
        # returns the same ID due to a UUID collision in tests)
        if new_run_id == previous_run_id:
            logger.warning("new_run_id == previous_run_id (%s) — skipping diff", new_run_id)
            return

        # ── 4. Diff ──────────────────────────────────────────────────────────
        try:
            diff_result = diff_runs(previous_run_id, new_run_id)
        except ValueError as exc:
            logger.warning("Diff skipped: %s", exc)
            return

        # ── 5 + 6. Threshold checks & alerts ────────────────────────────────
        triggered_alerts = _check_and_fire_alerts(diff_result, new_run_id)

        if triggered_alerts:
            # Broadcast to frontend SSE clients
            await broadcast_graph_update(diff_result, new_run_id)
            logger.info(
                "Watch cycle complete — run=%s, alerts=%s",
                new_run_id,
                triggered_alerts,
            )
        else:
            logger.info(
                "Watch cycle complete — run=%s, no alert thresholds exceeded",
                new_run_id,
            )

    except Exception as exc:  # noqa: BLE001
        logger.error("analyze_changes failed: %s", exc, exc_info=True)


# ── Private helpers ───────────────────────────────────────────────────────────

def _rebuild_and_record() -> str | None:
    """Rebuild attack graph and persist a new history run. Returns run_id."""
    try:
        summary = ingest_and_build()
        run_id = record_analysis_run(
            cluster_name=settings.CLUSTER_NAME,
            source=summary.get("source", "watch_api"),
            triggered_by="watch_event",
        )
        logger.info(
            "Rebuilt graph — %d nodes, %d edges (run=%s)",
            summary["node_count"],
            summary["edge_count"],
            run_id,
        )
        return run_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph rebuild failed: %s", exc, exc_info=True)
        return None


def _check_and_fire_alerts(
    diff: Dict[str, Any],
    new_run_id: str,
) -> List[str]:
    """
    Evaluate diff against configured thresholds.
    Returns list of alert type strings that were triggered.
    """
    triggered: List[str] = []

    # ── Alert 1: Risk increase ────────────────────────────────────────────────
    risk_delta_val = (diff.get("risk_delta") or {}).get("delta", 0.0)
    if risk_delta_val > settings.ALERT_RISK_DELTA_THRESHOLD:
        severity = "critical" if risk_delta_val > 2.0 else "high"
        summary_txt = (
            f"Risk increased from {diff['risk_delta']['before']:.1f} "
            f"to {diff['risk_delta']['after']:.1f} "
            f"(+{risk_delta_val:.1f}, {diff['risk_delta'].get('delta_pct', 0):.0f}%)"
        )
        logger.warning("ALERT RISK_INCREASE: %s", summary_txt)

        # Slack — build a minimal findings list
        _send_risk_slack(diff, severity)

        record_monitoring_event(
            run_id=new_run_id,
            event_type="RISK_INCREASE",
            severity=severity,
            summary=summary_txt,
            details=diff.get("risk_delta"),
            triggered_alerts=["slack", "websocket", "history"],
        )
        triggered.append("RISK_INCREASE")

    # ── Alert 2: New attack paths ─────────────────────────────────────────────
    path_delta_val = (diff.get("path_delta") or {}).get("delta", 0)
    if settings.ALERT_ON_NEW_PATHS and path_delta_val > 0:
        summary_txt = (
            f"{path_delta_val} new attack path(s) introduced "
            f"(total: {diff['path_delta']['after']})"
        )
        logger.warning("ALERT NEW_ATTACK_PATHS: %s", summary_txt)

        _send_path_slack(diff)

        record_monitoring_event(
            run_id=new_run_id,
            event_type="NEW_ATTACK_PATHS",
            severity="critical",
            summary=summary_txt,
            details=diff.get("path_delta"),
            triggered_alerts=["slack", "websocket", "history"],
        )
        triggered.append("NEW_ATTACK_PATHS")

    # ── Alert 3: New cycles ───────────────────────────────────────────────────
    cycle_delta_val = (diff.get("cycle_delta") or {}).get("delta", 0)
    if settings.ALERT_ON_NEW_CYCLES and cycle_delta_val > 0:
        summary_txt = (
            f"{cycle_delta_val} new privilege escalation loop(s) detected "
            f"(total: {diff['cycle_delta']['after']})"
        )
        logger.warning("ALERT NEW_CYCLES: %s", summary_txt)

        _send_cycle_slack_from_diff(diff)

        record_monitoring_event(
            run_id=new_run_id,
            event_type="NEW_CYCLES",
            severity="high",
            summary=summary_txt,
            details=diff.get("cycle_delta"),
            triggered_alerts=["slack", "websocket", "history"],
        )
        triggered.append("NEW_CYCLES")

    return triggered


# ── Slack helpers (bridge existing slack_service signatures) ──────────────────

def _send_risk_slack(diff: Dict[str, Any], severity: str) -> None:
    """Package risk-increase diff as a findings list for send_critical_alert."""
    rd = diff.get("risk_delta", {})
    findings = [
        {
            "severity": severity,
            "title": (
                f"Risk increased {rd.get('before', 0):.1f} → {rd.get('after', 0):.1f} "
                f"(+{rd.get('delta', 0):.1f})"
            ),
            "category": "risk_increase",
            "description": diff.get("recommendation", ""),
            "recommendation": diff.get("recommendation", "Review new roles and bindings"),
            "affected_nodes": [
                n.get("label", n.get("node_id", ""))
                for n in (diff.get("top_new_risks") or [])[:3]
            ],
            "effort": "medium",
        }
    ]
    send_critical_alert(findings, settings.CLUSTER_NAME)


def _send_path_slack(diff: Dict[str, Any]) -> None:
    """Synthesise a path_result dict that send_attack_path_alert expects."""
    pd = diff.get("path_delta", {})
    path_result = {
        "found": True,
        "hop_count": 0,
        "path": [],
        "hops": [],
        "total_cost": 0,
        "source_label": "cluster",
        "target_label": "critical-asset",
    }
    # Enrich if top_new_risks available
    top = diff.get("top_new_risks") or []
    if top:
        path_result["source_label"] = top[0].get("label", "attacker")
    send_attack_path_alert(path_result, settings.CLUSTER_NAME)


def _send_cycle_slack_from_diff(diff: Dict[str, Any]) -> None:
    """Synthesise a cycles_result dict for send_cycle_alert."""
    cd = diff.get("cycle_delta", {})
    cycles_result = {
        "cycle_count": cd.get("after", 0),
        "cycles": [],
    }
    send_cycle_alert(cycles_result, settings.CLUSTER_NAME)
