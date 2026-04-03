"""
routes_analysis.py — Combined Analysis Endpoint
GET /api/analysis/ → full analysis including threat score
"""

from fastapi import APIRouter
from app.services.analysis_service import get_full_analysis
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def full_analysis():
    """
    Run all algorithms in one call and return combined analysis with threat score.
    Includes: attack paths, blast radius, cycles, critical nodes, and threat score.
    """
    try:
        result = get_full_analysis()
        return result
    except RuntimeError as e:
        logger.error("Full analysis failed: %s", e)
        return {
            "attack_path": None,
            "blast_radius": None,
            "cycles": None,
            "critical_nodes": None,
            "threat_score": None,
            "error": str(e),
        }
