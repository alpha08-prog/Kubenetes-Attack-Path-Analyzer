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

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# Minimum seconds between full graph rebuilds triggered by the Watch API.
# Prevents the initial K8s event flood (all resources dumped as ADDED on each
# watch reconnect) from causing back-to-back rebuilds when nothing changed.
_MIN_REBUILD_INTERVAL_SEC = 30
_last_rebuild_time: float = 0.0

from app.config import settings
from app.core.database import record_monitoring_event
from app.services.broadcast_service import broadcast_graph_update, broadcast_raw
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
            logger.warning("No prior analysis run — recording baseline and broadcasting")
            run_id = _rebuild_and_record()
            # Broadcast so the frontend refreshes the graph even on first run
            if run_id:
                await broadcast_raw(json.dumps({
                    "type":      "GRAPH_UPDATE",
                    "run_id":    run_id,
                    "diff":      {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            return

        previous_run_id: str = history[0]["run_id"]

        # ── 2 + 3. Rebuild graph & record ────────────────────────────────────
        new_run_id = _rebuild_and_record()
        if new_run_id is None:
            return

        # Guard: don't diff a run against itself (dedup case — graph unchanged)
        # Still broadcast so the frontend knows the analysis completed and can
        # refresh the canvas.
        if new_run_id == previous_run_id:
            logger.info("Graph unchanged (run=%s) — broadcasting no-change update", new_run_id)
            await broadcast_raw(json.dumps({
                "type":      "GRAPH_UPDATE",
                "run_id":    new_run_id,
                "diff":      {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
            return

        # ── 4. Diff ──────────────────────────────────────────────────────────
        try:
            diff_result = diff_runs(previous_run_id, new_run_id)
        except ValueError as exc:
            logger.warning("Diff skipped: %s", exc)
            return

        # ── 5 + 6. Threshold checks & alerts ────────────────────────────────
        triggered_alerts = _check_and_fire_alerts(diff_result, new_run_id)

        # Always broadcast to frontend SSE clients so Session Events and the
        # Dashboard alert banner are updated even when no threshold was exceeded.
        # (Previously this was gated on triggered_alerts, which meant the
        # frontend never saw sub-threshold analysis results.)
        await broadcast_graph_update(diff_result, new_run_id)
        logger.info(
            "Watch cycle complete — run=%s alerts=%s",
            new_run_id,
            triggered_alerts or "none",
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("analyze_changes failed: %s", exc, exc_info=True)


# ── Private helpers ───────────────────────────────────────────────────────────

def _rebuild_and_record() -> str | None:
    """
    Rebuild attack graph, run cycle detection + attack path analysis,
    and persist a new history run with REAL values.

    Previously this always stored attack_paths=0 and cycles=0 (the defaults),
    which made path_delta and cycle_delta always 0 — so no alert ever fired.
    Now the actual algorithms run before recording so the DB reflects reality.
    """
    global _last_rebuild_time
    try:
        now = time.monotonic()
        elapsed = now - _last_rebuild_time
        if elapsed < _MIN_REBUILD_INTERVAL_SEC and _last_rebuild_time > 0:
            # Return the most recent run ID so the caller can still diff/broadcast.
            history = get_run_history(limit=1, cluster_name=settings.CLUSTER_NAME)
            if history:
                logger.debug(
                    "Skipping rebuild — last rebuild was %.1fs ago (min=%ds)",
                    elapsed, _MIN_REBUILD_INTERVAL_SEC,
                )
                return history[0]["run_id"]
        _last_rebuild_time = now
        summary = ingest_and_build()

        # ── Run real analysis algorithms ──────────────────────────────────────
        attack_paths = 0
        cycle_count  = 0

        try:
            from app.services.attack_service import get_auto_attack_path
            path_result  = get_auto_attack_path()
            attack_paths = 1 if path_result.get("found") else 0
        except Exception as exc:  # noqa: BLE001
            logger.debug("Attack path detection skipped during rebuild: %s", exc)

        try:
            from app.services.analysis_service import get_cycles
            cycles_result = get_cycles()
            cycle_count   = cycles_result.get("cycle_count", 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Cycle detection skipped during rebuild: %s", exc)

        # ── Persist run with real values ──────────────────────────────────────
        run_id = record_analysis_run(
            cluster_name=settings.CLUSTER_NAME,
            source=summary.get("source", "watch_api"),
            triggered_by="watch_event",
            attack_paths=attack_paths,
            cycles=cycle_count,
        )
        logger.info(
            "Rebuilt graph — %d nodes, %d edges, %d path(s), %d cycle(s) (run=%s)",
            summary["node_count"],
            summary["edge_count"],
            attack_paths,
            cycle_count,
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

    # ── Alert 4: New nodes added to cluster ───────────────────────────────────
    # Fires when kubectl reports new pods / serviceaccounts / roles / secrets
    # even if the overall average risk barely moves (diluted by many existing nodes).
    # This catches the scenario-deploy case reliably.
    new_nodes_val = (diff.get("node_changes") or {}).get("new_count", 0)
    if new_nodes_val > 0 and not triggered:
        # Only fire this if no stronger alert already fired — avoids double noise.
        new_node_labels = [
            n.get("label", n.get("node_id", ""))
            for n in (diff.get("node_changes", {}).get("new_nodes") or [])[:5]
        ]
        summary_txt = (
            f"{new_nodes_val} new K8s resource(s) detected: "
            f"{', '.join(new_node_labels)}"
        )
        logger.warning("ALERT NEW_RESOURCES: %s", summary_txt)

        record_monitoring_event(
            run_id=new_run_id,
            event_type="NEW_RESOURCES",
            severity="medium",
            summary=summary_txt,
            details=diff.get("node_changes"),
            triggered_alerts=["websocket", "history"],
        )
        triggered.append("NEW_RESOURCES")

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
    try:
        send_critical_alert(findings, settings.CLUSTER_NAME)
    except Exception as exc:
        logger.warning("Slack risk-increase alert failed (non-critical): %s", exc)


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
    try:
        send_attack_path_alert(path_result, settings.CLUSTER_NAME)
    except Exception as exc:
        logger.warning("Slack new-attack-path alert failed (non-critical): %s", exc)


def _send_cycle_slack_from_diff(diff: Dict[str, Any]) -> None:
    """Synthesise a cycles_result dict for send_cycle_alert."""
    cd = diff.get("cycle_delta", {})
    cycles_result = {
        "cycle_count": cd.get("after", 0),
        "cycles": [],
    }
    try:
        send_cycle_alert(cycles_result, settings.CLUSTER_NAME)
    except Exception as exc:
        logger.warning("Slack new-cycle alert failed (non-critical): %s", exc)
