"""
routes_slack.py — Slack Alert Endpoints
GET  /api/slack/test     → send a test message to verify connection
GET  /api/slack/status   → check if webhook is configured
POST /api/slack/alert    → manually trigger an alert from current analysis
"""

from fastapi import APIRouter, HTTPException
from app.services.slack_service import (
    send_test_alert,
    send_critical_alert,
    send_attack_path_alert,
    send_cycle_alert,
)
from app.services.analysis_service import get_full_analysis
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/status")
def slack_status():
    """
    Check whether Slack alerts are configured.
    Used by the status indicator in the dashboard header.
    """
    configured = bool(settings.SLACK_WEBHOOK_URL)
    return {
        "configured": configured,
        "status":     "active" if configured else "disabled",
        "message":    (
            "Slack alerts active" if configured
            else "Set SLACK_WEBHOOK_URL in .env to enable alerts"
        ),
        "webhook_preview": (
            settings.SLACK_WEBHOOK_URL[:40] + "..."
            if configured else None
        ),
    }


@router.get("/test")
def test_alert():
    """
    Send a test message to verify the Slack webhook is working.
    Run this first after setting SLACK_WEBHOOK_URL.
    You should see a green message appear in your Slack channel.
    """
    result = send_test_alert()
    if not result["sent"]:
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Failed to send test alert"),
        )
    return result


@router.post("/alert")
def trigger_alert():
    """
    Run a full analysis and send Slack alerts for any critical/high findings.
    This is the endpoint DemoMode.jsx calls to trigger the live Slack demo.

    Sequence:
        1. Run all algorithms
        2. If attack path found → send attack path alert immediately
        3. If cycles found → send cycle alert
        4. Run AI narration → send findings summary
    """
    if not settings.SLACK_WEBHOOK_URL:
        raise HTTPException(
            status_code=503,
            detail="SLACK_WEBHOOK_URL not set in .env — Slack alerts disabled",
        )

    results = {}

    try:
        # Step 1 — run full analysis
        analysis = get_full_analysis()

        # Step 2 — attack path alert (fires immediately, most urgent)
        if analysis.get("attack_path") and analysis["attack_path"].get("found"):
            results["attack_path"] = send_attack_path_alert(
                analysis["attack_path"],
                cluster_name=settings.CLUSTER_NAME,
            )

        # Step 3 — cycle alert
        if analysis.get("cycles") and analysis["cycles"].get("cycle_count", 0) > 0:
            results["cycles"] = send_cycle_alert(
                analysis["cycles"],
                cluster_name=settings.CLUSTER_NAME,
            )

        # Step 4 — AI narration + findings alert
        try:
            from app.services.narrator_service import generate_report
            report   = generate_report(cluster_name=settings.CLUSTER_NAME)
            findings = report.get("findings", [])
            results["findings"] = send_critical_alert(
                findings,
                cluster_name=settings.CLUSTER_NAME,
            )
        except Exception as e:
            logger.warning("AI narration skipped during Slack alert: %s", e)
            results["findings"] = {"sent": False, "reason": str(e)}

        total_sent = sum(1 for r in results.values() if r.get("sent"))

        return {
            "status":      "completed",
            "alerts_sent": total_sent,
            "details":     results,
        }

    except Exception as e:
        logger.error("Slack alert trigger failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))