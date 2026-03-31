"""
routes_critical.py — Critical Node Endpoints
GET /api/critical/nodes          → ranked list by centrality + risk
GET /api/critical/candidates     → top removal candidates for a path
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.analysis_service import get_critical_nodes
from app.services.simulator_service import get_top_removal_candidates
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/nodes")
def critical_nodes(top_n: int = Query(default=10, ge=1, le=50)):
    """
    Rank all nodes by combined betweenness centrality + risk score.
    Higher score = removing this node breaks the most attack paths.
    Used by CriticalNodeTable.jsx to populate the ranked leaderboard.
    """
    try:
        result = get_critical_nodes(top_n=top_n)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/candidates")
def removal_candidates(
    source: str = Query(..., description="Attack path source node ID"),
    target: str = Query(..., description="Attack path target node ID"),
    top_n:  int = Query(default=5, ge=1, le=20),
):
    """
    Find the top N nodes whose removal breaks the most paths
    between source and target.
    Used by the 'Simulate' button in CriticalNodeTable.jsx to
    pre-rank which nodes are worth simulating.
    """
    try:
        candidates = get_top_removal_candidates(source, target, top_n=top_n)
        return {
            "source":     source,
            "target":     target,
            "candidates": candidates,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))