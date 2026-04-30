"""
routes_report.py - AI report endpoints.
GET /api/report -> run all algorithms and generate Groq AI findings.
GET /api/report/pdf -> generate a downloadable PDF version of the report.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import settings
from app.services.narrator_service import generate_report
from app.services.report_export_service import build_report_pdf
from app.utils.helpers import timestamp_filename
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("")
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


@router.get("/pdf")
def get_report_pdf(
    cluster_name: str = Query(
        default=None,
        description="Override cluster display name in the report",
    )
):
    """
    Run report generation and return it as a downloadable PDF.
    """
    name = cluster_name or settings.CLUSTER_NAME
    try:
        report = generate_report(cluster_name=name)
        pdf_bytes = build_report_pdf(report)
        filename = timestamp_filename("attack_path_report", ext="pdf")

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ModuleNotFoundError as e:
        if e.name == "reportlab":
            raise HTTPException(
                status_code=503,
                detail="PDF export dependency missing: install 'reportlab' in the backend environment.",
            )
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("PDF report generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF report generation failed: {str(e)}")
