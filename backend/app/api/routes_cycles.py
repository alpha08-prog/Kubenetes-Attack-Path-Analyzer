"""
routes_cycles.py — Cycle Detection Endpoints
GET /api/cycles             → all privilege escalation loops
GET /api/cycles/node/{id}   → cycles involving a specific node
"""

from fastapi import APIRouter, HTTPException
from app.services.analysis_service import get_cycles
from app.algorithm.dfs_cycles import cycles_involving_node
from app.core.graph_builder import get_graph
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("")
def get_all_cycles():
    """
    Detect all privilege escalation loops in the graph using DFS.
    Returns cycles sorted by severity descending.
    Also returns cycle_node_ids — used by frontend to
    highlight looped nodes in red on the graph canvas.
    """
    try:
        result = get_cycles()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/node/{node_id:path}")
def cycles_for_node(node_id: str):
    """
    Returns all cycles that pass through a specific node.
    Called when a user clicks a node in the graph canvas
    and the sidebar checks if it's part of a privilege loop.

    node_id uses :path to handle colons in IDs like
    'service_account:default:backend-sa'
    """
    try:
        G = get_graph()
        cycles = cycles_involving_node(G, node_id)
        return {
            "node_id":     node_id,
            "cycle_count": len(cycles),
            "cycles":      cycles,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))