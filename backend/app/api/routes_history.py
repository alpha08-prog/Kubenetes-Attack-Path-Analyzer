"""
routes_history.py — Risk Score History Endpoints
GET  /api/history/              → recent analysis runs list
GET  /api/history/trend         → risk score time series for chart
GET  /api/history/stats         → all-time summary stats
GET  /api/history/{run_id}      → full detail for one run
GET  /api/history/hotspots      → persistently high-risk nodes
POST /api/history/record        → manually trigger a snapshot
DELETE /api/history/{run_id}    → delete a run
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.history_service import (
    record_analysis_run,
    get_run_history,
    get_risk_trend,
    get_run_detail,
    get_riskiest_nodes_over_time,
    get_stats_summary,
    delete_run,
)
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def list_runs(
    limit:        int = Query(default=20, ge=1, le=100),
    cluster_name: str = Query(default=None),
):
    """
    Returns the N most recent analysis runs newest first.
    Used by the history table in the dashboard.
    """
    runs = get_run_history(limit=limit, cluster_name=cluster_name)
    return {"runs": runs, "count": len(runs)}


@router.get("/trend")
def risk_trend(
    limit:        int = Query(default=10, ge=2, le=50,
                              description="Number of runs to include in trend"),
    cluster_name: str = Query(default=None),
):
    """
    Returns risk score time series for the trend chart.

    Key field: delta_pct — percentage change vs previous run.
    Frontend renders this as a line chart with a "▲ +23%" badge.

    Example response:
    {
        "trend": [
            {"run_id": "a3f9b2c1", "overall_risk": 6.2, "created_at": "..."},
            {"run_id": "b8e1d4f2", "overall_risk": 7.6, "created_at": "..."}
        ],
        "latest_risk":     7.6,
        "delta":           1.4,
        "delta_pct":       22.6,
        "trend_direction": "increasing"
    }
    """
    return get_risk_trend(limit=limit, cluster_name=cluster_name)


@router.get("/stats")
def stats_summary():
    """
    All-time aggregate stats across every recorded run.
    Used by the history dashboard header cards.
    """
    return get_stats_summary()


@router.get("/hotspots")
def risk_hotspots(
    node_type: str = Query(default=None,
                           description="Filter by type: pod|service_account|role|secret|database"),
    limit:     int = Query(default=10, ge=1, le=50),
):
    """
    Returns nodes that have been consistently high-risk across multiple runs.
    These are your persistent security debt items.
    A node that scores 9.0 in every single run is more dangerous
    than one that spiked once.
    """
    return {
        "hotspots": get_riskiest_nodes_over_time(node_type=node_type, limit=limit)
    }


@router.get("/{run_id}")
def run_detail(run_id: str):
    """
    Full detail for a single run: summary + all node snapshots + all findings.
    Used when a judge clicks a row in the history table.
    """
    detail = get_run_detail(run_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return detail


@router.post("/record")
def trigger_snapshot(triggered_by: str = "manual"):
    """
    Manually record a risk snapshot of the current graph state.
    Useful for "before hardening" and "after hardening" comparisons.
    Call this before and after removing a critical node to show delta.
    """
    try:
        run_id = record_analysis_run(
            cluster_name = settings.CLUSTER_NAME,
            source       = "mock" if settings.MOCK_MODE else "kubectl",
            triggered_by = triggered_by,
        )
        return {
            "status": "recorded",
            "run_id": run_id,
            "message": f"Snapshot saved. View at GET /api/history/{run_id}",
        }
    except Exception as e:
        logger.error("Manual snapshot failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{run_id}")
def remove_run(run_id: str):
    """Delete a specific run and its node snapshots."""
    deleted = delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return {"status": "deleted", "run_id": run_id}