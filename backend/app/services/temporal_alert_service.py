"""
temporal_alert_service.py — Temporal Alert Evaluation (B3)

Evaluates SnapshotDiff objects against configured thresholds and
emits alerts via Slack when thresholds are exceeded.
"""

import uuid

from app.config import settings
from app.models.snapshot import SnapshotDiff
from app.utils.logger import get_logger
from app.core import database as db

logger = get_logger(__name__)

# ── Alert thresholds (can be driven from settings if added to config.py) ───────
ALERT_ON_NEW_PATHS: bool = True
ALERT_NEW_PATHS_THRESHOLD: int = 1      # Alert if >=N new attack paths
ALERT_RISK_DELTA_THRESHOLD: float = 1.0  # Alert if risk increased by >=X
ALERT_ON_NEW_CYCLES: bool = True
ALERT_SEVERITY_MINIMUM: str = "medium"  # Only send Slack for >= this severity


def evaluate_diff(diff: SnapshotDiff) -> SnapshotDiff:
    """
    Evaluate a SnapshotDiff against alert thresholds.
    Updates diff.severity, diff.alert_triggered, diff.alert_reasons in place.
    Persists alert to DB and sends Slack notification if triggered.

    Returns the updated diff.
    """
    reasons: list[str] = []

    if ALERT_ON_NEW_PATHS and diff.new_attack_paths_count >= ALERT_NEW_PATHS_THRESHOLD:
        reasons.append(
            f"{diff.new_attack_paths_count} new attack path(s) detected"
        )

    if diff.overall_risk_delta >= ALERT_RISK_DELTA_THRESHOLD:
        reasons.append(
            f"Aggregate risk increased by {diff.overall_risk_delta:.1f}"
        )

    if ALERT_ON_NEW_CYCLES and diff.new_cycles_count > 0:
        reasons.append(
            f"{diff.new_cycles_count} new privilege escalation cycle(s) detected"
        )

    if diff.nodes_added_count > 0:
        reasons.append(f"{diff.nodes_added_count} new node(s) appeared in graph")

    severity = _compute_severity(diff)
    alert_triggered = len(reasons) > 0

    diff.severity = severity
    diff.alert_triggered = alert_triggered
    diff.alert_reasons = reasons

    if alert_triggered:
        logger.warning(
            "Temporal alert triggered [%s]: %s",
            severity.upper(),
            "; ".join(reasons),
        )
        _persist_alert(diff)
        _send_slack_alert(diff)

    return diff


def _compute_severity(diff: SnapshotDiff) -> str:
    """
    Assign alert severity based on what changed.
    critical > high > medium > low
    """
    # Critical: new direct attack paths to sensitive targets
    if diff.new_attack_paths_count > 0 and diff.overall_risk_delta >= 2.0:
        return "critical"
    if diff.new_attack_paths_count > 0:
        return "high"
    if diff.new_cycles_count > 0:
        return "high"
    if diff.overall_risk_delta >= ALERT_RISK_DELTA_THRESHOLD:
        return "medium"
    if diff.nodes_added_count > 0 or diff.edges_added_count > 0:
        return "low"
    return "low"


def _persist_alert(diff: SnapshotDiff) -> None:
    alert = {
        "alert_id": str(uuid.uuid4()),
        "diff_id": diff.diff_id,
        "severity": diff.severity,
        "title": _alert_title(diff),
        "description": "; ".join(diff.alert_reasons),
        "new_paths": diff.new_attack_paths,
        "new_cycles": diff.new_cycles,
        "risk_delta": diff.overall_risk_delta,
    }
    try:
        db.save_temporal_alert(alert)
    except Exception as exc:
        logger.error("Failed to persist temporal alert: %s", exc)


def _send_slack_alert(diff: SnapshotDiff) -> None:
    """Send a Slack notification for the temporal alert (if Slack is configured)."""
    if not settings.SLACK_WEBHOOK_URL:
        return

    # Only send for alerts at or above the minimum severity
    sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if sev_order.get(diff.severity, 0) < sev_order.get(ALERT_SEVERITY_MINIMUM, 0):
        return

    severity_emoji = {
        "critical": ":red_circle:",
        "high": ":large_orange_circle:",
        "medium": ":large_blue_circle:",
        "low": ":large_green_circle:",
    }
    emoji = severity_emoji.get(diff.severity, ":white_circle:")
    reasons_text = "\n".join(f"• {r}" for r in diff.alert_reasons)

    payload = {
        "text": f"{emoji} *Temporal Security Alert* — {settings.CLUSTER_NAME}",
        "attachments": [
            {
                "color": {"critical": "#E24B4A", "high": "#EF9F27",
                          "medium": "#378ADD", "low": "#1D9E75"}.get(diff.severity, "#888780"),
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"{emoji} *Graph Change Detected* in `{settings.CLUSTER_NAME}`\n"
                                f"*Severity:* {diff.severity.upper()}\n"
                                f"*Changes:*\n{reasons_text}"
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Nodes Added*\n{diff.nodes_added_count}"},
                            {"type": "mrkdwn", "text": f"*Nodes Removed*\n{diff.nodes_removed_count}"},
                            {"type": "mrkdwn", "text": f"*New Attack Paths*\n{diff.new_attack_paths_count}"},
                            {"type": "mrkdwn", "text": f"*Risk Δ*\n{diff.overall_risk_delta:+.1f}"},
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": (
                                    f":clock1: {diff.timestamp_after}  |  "
                                    "Attack Path Analyzer — Temporal Analysis"
                                ),
                            }
                        ],
                    },
                ],
            }
        ],
    }

    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if resp.status_code == 200:
            logger.info("Temporal alert sent to Slack [%s]", diff.severity)
        else:
            logger.warning("Slack temporal alert returned %d", resp.status_code)
    except Exception as exc:
        logger.error("Slack temporal alert failed: %s", exc)


def _alert_title(diff: SnapshotDiff) -> str:
    if diff.new_attack_paths_count > 0:
        return f"{diff.new_attack_paths_count} New Attack Path(s) Detected"
    if diff.new_cycles_count > 0:
        return f"{diff.new_cycles_count} New Privilege Escalation Cycle(s)"
    if diff.overall_risk_delta >= ALERT_RISK_DELTA_THRESHOLD:
        return f"Cluster Risk Increased by {diff.overall_risk_delta:.1f}"
    return "Graph Change Detected"
