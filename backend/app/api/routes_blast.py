"""
routes_blast.py — Blast Radius Endpoints
POST /api/blast/radius       → BFS from a single compromised node
POST /api/blast/multi-radius → BFS from multiple compromised nodes
"""

from fastapi import APIRouter, HTTPException
from app.models.node import NodeIdRequest
from app.services.blast_service import get_blast_radius, get_multi_blast_radius
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/radius")
def blast_radius(body: NodeIdRequest):
    """
    Run BFS from a compromised node up to max_hops.
    Returns nodes grouped by hop distance (zones) for
    the concentric ring visualization in BlastRadiusOverlay.jsx.

    Body: { "node_id": "pod:default:web-server", "max_hops": 3 }
    """
    try:
        result = get_blast_radius(body.node_id, body.max_hops)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/multi-radius")
def multi_blast_radius(node_ids: list[str], max_hops: int = 3):
    """
    Run BFS from multiple compromised nodes simultaneously.
    Returns combined blast zone — useful when an attacker
    already controls several pods at once.

    Body: ["pod:default:web-server", "pod:default:api-server"]
    """
    try:
        result = get_multi_blast_radius(node_ids, max_hops=max_hops)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))