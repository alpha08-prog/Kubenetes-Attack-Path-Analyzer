"""
routes_diff.py — Graph Diff Endpoints
GET  /api/diff/latest          → auto-diff the two most recent runs
POST /api/diff/compare         → diff any two specific run IDs
GET  /api/diff/vs-current/{id} → compare a historical run vs live graph
"""

from fastapi import APIRouter, HTTPException, Body
from app.services.graph_diff_service import (
    diff_runs,
    diff_latest_two,
    diff_snapshot_vs_current,
)
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/latest")
def diff_latest(cluster_name: str = None):
    """
    Auto-diff the two most recent analysis runs.
    No parameters needed — just call it.

    Perfect for the demo:
        1. Record a baseline: POST /api/history/record
        2. Deploy vulnerable scenario
        3. Record again: POST /api/history/record
        4. Call this endpoint — see full diff

    Returns complete before/after comparison including
    risk delta, new nodes, severity shift, and recommendations.
    """
    try:
        return diff_latest_two(
            cluster_name=cluster_name or settings.CLUSTER_NAME
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Diff latest failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
def compare_runs(
    run_id_before: str = Body(..., embed=True),
    run_id_after:  str = Body(..., embed=True),
):
    """
    Diff any two specific runs by their run IDs.
    Get run IDs from GET /api/history/

    Body:
    {
        "run_id_before": "a3f9b2c1",
        "run_id_after":  "b8e1d4f2"
    }
    """
    try:
        return diff_runs(run_id_before, run_id_after)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Diff compare failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vs-current/{run_id}")
def diff_vs_current(run_id: str):
    """
    Compare a specific historical run against the current live graph.

    Use case — live demo sequence:
        1. Record baseline: POST /api/history/record  → get run_id
        2. Deploy vulnerable resources to minikube
        3. Reload graph: POST /api/graph/reload
        4. Call this endpoint with the baseline run_id
        5. See exactly what changed

    This endpoint creates a temporary snapshot of the current graph,
    runs the diff, and returns the result without polluting history.
    """
    try:
        return diff_snapshot_vs_current(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Diff vs current failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))