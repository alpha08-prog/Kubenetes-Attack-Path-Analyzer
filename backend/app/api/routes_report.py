"""
routes_report.py - AI report endpoint.
GET /api/report -> run all algorithms and generate Groq AI findings.
"""

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services.narrator_service import generate_report
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
    Run all four algorithms on the current graph, send results to Groq,
    and return a structured list of findings with kill chains and remediation.
    """
    name = cluster_name or settings.CLUSTER_NAME
    try:
        return generate_report(cluster_name=name)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
