"""
routes_report.py — AI Report Endpoint
GET /api/report → run all algorithms + generate Gemini AI findings
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.narrator_service import generate_report
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def get_report(
    cluster_name: str = Query(
        default=None,
        description="Override cluster display name in the report",
    )
):
    """
    Run all four algorithms on the current graph, send results to
    Gemini, and return a structured list of security findings with
    kill chains and remediation recommendations.

    This is the flagship endpoint — it powers NarratorPanel.jsx.
    Expect 3-8 seconds response time (Gemini API call).
    """
    name = cluster_name or settings.CLUSTER_NAME
    try:
        report = generate_report(cluster_name=name)
        return report
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}"
        )