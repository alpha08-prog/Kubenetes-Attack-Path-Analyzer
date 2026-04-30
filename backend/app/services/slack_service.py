"""
slack_service.py — Slack Alert Integration  ★ DEMO WOW FACTOR ★
Sends rich formatted alerts to a Slack channel when critical
findings are detected during analysis.

Setup (2 minutes):
    1. Go to https://api.slack.com/apps → Create New App → From Scratch
    2. Add "Incoming Webhooks" feature → Activate → Add to Workspace
    3. Copy the Webhook URL → paste in .env as SLACK_WEBHOOK_URL
    4. Done. Free, no bot token needed.

What judges see:
    Run analysis → Slack message appears on screen in real time.
    Nobody else will have this.
"""

import httpx
from datetime import datetime
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SLACK_TIMEOUT = 10


# ── Severity colors (Slack attachment colors) ─────────────────────────────────
SEVERITY_COLORS = {
    "critical": "#E24B4A",   # red
    "high":     "#EF9F27",   # orange
    "medium":   "#378ADD",   # blue
    "low":      "#1D9E75",   # green
}

SEVERITY_EMOJI = {
    "critical": ":red_circle:",
    "high":     ":large_orange_circle:",
    "medium":   ":large_blue_circle:",
    "low":      ":large_green_circle:",
}


# ── Main alert functions ───────────────────────────────────────────────────────

def send_critical_alert(findings: list, cluster_name: str = None) -> dict:
    """
    Send a Slack alert for critical and high findings.
    Called automatically by narrator_service after generating a report.

    Args:
        findings:     list of Finding dicts from narrator_service
        cluster_name: display name of the cluster

    Returns:
        {"sent": True/False, "alerts_sent": N, "reason": "..."}
    """
    if not settings.SLACK_WEBHOOK_URL:
        logger.info("Slack alerts disabled — SLACK_WEBHOOK_URL not set in .env")
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not configured"}

    cluster = cluster_name or settings.CLUSTER_NAME

    # Filter to critical and high only
    urgent = [
        f for f in findings
        if f.get("severity") in ("critical", "high")
    ]

    if not urgent:
        logger.info("No critical/high findings — Slack alert skipped")
        return {"sent": False, "reason": "No critical or high findings to alert"}

    # Send one summary message + individual cards for critical findings
    alerts_sent = 0

    # 1 — Summary header block
    _send_summary_block(urgent, cluster)
    alerts_sent += 1

    # 2 — Individual detailed cards for critical findings only
    critical_only = [f for f in urgent if f.get("severity") == "critical"]
    for finding in critical_only[:3]:          # cap at 3 to avoid spam
        _send_finding_card(finding, cluster)
        alerts_sent += 1

    logger.info("Slack: sent %d alerts for cluster '%s'", alerts_sent, cluster)
    return {
        "sent":        True,
        "alerts_sent": alerts_sent,
        "urgent_count": len(urgent),
        "critical_count": len(critical_only),
    }


def send_attack_path_alert(path_result: dict, cluster_name: str = None) -> dict:
    """
    Send an immediate Slack alert when an attack path is found.
    Called by attack_service when Dijkstra finds a path.
    More urgent than the full report — fires instantly.
    """
    if not settings.SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not configured"}

    if not path_result.get("found"):
        return {"sent": False, "reason": "No attack path found"}

    cluster  = cluster_name or settings.CLUSTER_NAME
    hops     = path_result.get("hop_count", 0)
    path     = path_result.get("path", [])
    cost     = path_result.get("total_cost", 0)
    source   = path_result.get("source_label", path_result.get("source", "unknown"))
    target   = path_result.get("target_label", path_result.get("target", "unknown"))

    # Build readable chain from hops
    hop_chain = " → ".join(
        f"{h.get('from_label')} `[{h.get('relation')}]`"
        for h in path_result.get("hops", [])
    )
    if path:
        hop_chain += f" → {path_result.get('target_label', target)}"

    payload = {
        "text": f":warning: *Attack Path Detected* — {cluster}",
        "attachments": [
            {
                "color": "#E24B4A",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f":skull_and_crossbones: *Attack path found in `{cluster}`*\n"
                                f"*From:* `{source}`\n"
                                f"*To:* `{target}`\n"
                                f"*Hops:* {hops}   *Cost:* {cost} (lower = easier)\n"
                            ),
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Kill chain:*\n```{hop_chain}```",
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": (
                                    f":clock1: {_now()}  |  "
                                    f"Attack Path Analyzer"
                                ),
                            }
                        ],
                    },
                ],
            }
        ],
    }

    success = _post_to_slack(payload)
    return {"sent": success, "path": f"{source} → {target}", "hops": hops}


def send_cycle_alert(cycles_result: dict, cluster_name: str = None) -> dict:
    """
    Send a Slack alert when privilege escalation cycles are detected.
    Called by analysis_service after cycle detection.
    """
    if not settings.SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not configured"}

    cycle_count = cycles_result.get("cycle_count", 0)
    if cycle_count == 0:
        return {"sent": False, "reason": "No cycles found"}

    cluster = cluster_name or settings.CLUSTER_NAME
    cycles  = cycles_result.get("cycles", [])

    cycle_text = "\n".join(
        f"• `{c.get('chain', 'unknown')}` — *{c.get('severity', '').upper()}*"
        for c in cycles[:5]
    )

    payload = {
        "text": f":arrows_counterclockwise: *Privilege Escalation Loop* — {cluster}",
        "attachments": [
            {
                "color": "#7F77DD",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f":repeat: *{cycle_count} privilege escalation "
                                f"loop{'s' if cycle_count > 1 else ''} detected "
                                f"in `{cluster}`*\n\n"
                                f"{cycle_text}"
                            ),
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f":clock1: {_now()}"}
                        ],
                    },
                ],
            }
        ],
    }

    success = _post_to_slack(payload)
    return {"sent": success, "cycle_count": cycle_count}


def send_temporal_alert(
    severity: str,
    reasons: list,
    nodes_added: int,
    nodes_removed: int,
    new_attack_paths_count: int,
    overall_risk_delta: float,
    timestamp_after: str,
    cluster_name: str = None,
) -> dict:
    """
    Send a Slack alert for a temporal graph-change event.
    Called by temporal_alert_service when a SnapshotDiff exceeds thresholds.
    """
    if not settings.SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not configured"}

    cluster       = cluster_name or settings.CLUSTER_NAME
    emoji         = SEVERITY_EMOJI.get(severity, ":white_circle:")
    color         = SEVERITY_COLORS.get(severity, "#888780")
    reasons_text  = "\n".join(f"• {r}" for r in reasons)

    payload = {
        "text": f"{emoji} *Temporal Security Alert* — {cluster}",
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"{emoji} *Graph Change Detected* in `{cluster}`\n"
                                f"*Severity:* {severity.upper()}\n"
                                f"*Changes:*\n{reasons_text}"
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Nodes Added*\n{nodes_added}"},
                            {"type": "mrkdwn", "text": f"*Nodes Removed*\n{nodes_removed}"},
                            {"type": "mrkdwn", "text": f"*New Attack Paths*\n{new_attack_paths_count}"},
                            {"type": "mrkdwn", "text": f"*Risk Δ*\n{overall_risk_delta:+.1f}"},
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": (
                                    f":clock1: {timestamp_after}  |  "
                                    "Attack Path Analyzer — Temporal Analysis"
                                ),
                            }
                        ],
                    },
                ],
            }
        ],
    }

    success = _post_to_slack(payload)
    if success:
        logger.info("Temporal alert sent to Slack [%s]", severity)
    return {"sent": success, "severity": severity}


def send_test_alert(cluster_name: str = None) -> dict:
    """
    Send a test message to verify the Slack webhook is working.
    Called by GET /api/slack/test
    """
    if not settings.SLACK_WEBHOOK_URL:
        return {"sent": False, "reason": "SLACK_WEBHOOK_URL not set in .env"}

    cluster = cluster_name or settings.CLUSTER_NAME

    payload = {
        "text": f":white_check_mark: Slack alerts connected — *{cluster}*",
        "attachments": [
            {
                "color": "#1D9E75",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                ":shield: *Attack Path Analyzer* is connected "
                                "and ready to send security alerts.\n\n"
                                f"Cluster: `{cluster}`\n"
                                f"Time: {_now()}"
                            ),
                        }
                    }
                ],
            }
        ],
    }

    success = _post_to_slack(payload)
    return {
        "sent":    success,
        "message": "Test alert sent successfully" if success else "Failed to send",
        "webhook": settings.SLACK_WEBHOOK_URL[:40] + "...",
    }


# ── Rich block builders ────────────────────────────────────────────────────────

def _send_summary_block(findings: list, cluster: str) -> None:
    """Send a summary header message listing all urgent findings."""
    critical = [f for f in findings if f.get("severity") == "critical"]
    high     = [f for f in findings if f.get("severity") == "high"]

    lines = []
    for f in findings[:6]:                    # max 6 in summary
        sev   = f.get("severity", "")
        emoji = SEVERITY_EMOJI.get(sev, ":white_circle:")
        lines.append(f"{emoji} *[{sev.upper()}]* {f.get('title', 'Untitled')}")

    summary_text = "\n".join(lines)

    payload = {
        "text": f":rotating_light: *Security Alert — {cluster}*",
        "attachments": [
            {
                "color": "#E24B4A",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🛡️ Attack Path Analyzer — {cluster}",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Critical Findings*\n{len(critical)}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*High Findings*\n{len(high)}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Findings detected:*\n{summary_text}",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": (
                                    f":clock1: {_now()}  |  "
                                    "Attack Path Analyzer"
                                ),
                            }
                        ],
                    },
                ],
            }
        ],
    }

    _post_to_slack(payload)


def _send_finding_card(finding: dict, cluster: str) -> None:
    """Send a detailed card for a single critical finding."""
    sev        = finding.get("severity", "critical")
    color      = SEVERITY_COLORS.get(sev, "#888780")
    emoji      = SEVERITY_EMOJI.get(sev, ":white_circle:")
    kill_chain = finding.get("kill_chain")
    rec        = finding.get("recommendation", "")
    nodes      = finding.get("affected_nodes", [])

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *{finding.get('title', 'Security Finding')}*\n"
                    f"{finding.get('description', '')}"
                ),
            },
        },
    ]

    if kill_chain:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Kill chain:*\n```{kill_chain}```",
            },
        })

    if nodes:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Affected nodes:* {', '.join(f'`{n}`' for n in nodes[:5])}",
            },
        })

    if rec:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":wrench: *Fix:* {rec}",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"Effort: *{finding.get('effort', 'unknown')}*  |  "
                    f"Category: *{finding.get('category', 'unknown')}*  |  "
                    f":clock1: {_now()}"
                ),
            }
        ],
    })

    payload = {
        "attachments": [{"color": color, "blocks": blocks}]
    }
    _post_to_slack(payload)


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _post_to_slack(payload: dict) -> bool:
    """POST payload to Slack webhook. Returns True on success."""
    try:
        with httpx.Client(timeout=SLACK_TIMEOUT) as client:
            resp = client.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if resp.status_code == 200 and resp.text == "ok":
            return True
        else:
            logger.warning(
                "Slack webhook returned %d: %s", resp.status_code, resp.text
            )
            return False
    except Exception as e:
        logger.error("Slack alert failed: %s", e)
        return False


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")