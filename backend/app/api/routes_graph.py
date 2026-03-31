"""
routes_graph.py — Graph Endpoints
GET  /api/graph         → full graph for Cytoscape.js frontend
GET  /api/graph/summary → quick stats for dashboard header
POST /api/graph/reload  → re-ingest cluster data and rebuild graph
"""

from fastapi import APIRouter, HTTPException
from app.core.graph_builder import get_graph, graph_to_cytoscape, graph_summary, get_metadata
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def get_full_graph():
    """
    Returns the full graph in Cytoscape.js format.
    Called once on dashboard load — frontend stores this locally.
    """
    try:
        G = get_graph()
        return graph_to_cytoscape(G)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/summary")
def get_graph_summary():
    """
    Returns node/edge counts, type breakdown, entry points, targets.
    Used by the dashboard header stat cards.
    """
    try:
        G = get_graph()
        return graph_summary(G)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/metadata")
def get_graph_metadata():
    """Returns when the graph was last built and basic counts."""
    return get_metadata()


@router.post("/reload")
def reload_graph():
    """
    Re-ingest cluster data and rebuild the graph.
    Call this after running fetch_k8s_data.sh to pick up new data.
    """
    try:
        from app.services.ingestion_service import ingest_and_build
        summary = ingest_and_build()
        logger.info("Graph reloaded via API: %s", summary)
        return {"status": "reloaded", **summary}
    except Exception as e:
        logger.error("Graph reload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))