"""
routes_snapshot.py — Graph Snapshot Endpoints (B3 Temporal Analysis)

GET  /api/snapshots/              → list snapshots (paginated)
POST /api/snapshots/              → create a manual snapshot
GET  /api/snapshots/timeline      → risk timeline for the last N days
GET  /api/snapshots/alerts        → list temporal alerts
GET  /api/snapshots/{id}          → full snapshot with nodes/edges
GET  /api/snapshots/{id1}/diff/{id2} → compare two snapshots
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.snapshot import (
    CreateSnapshotRequest, SnapshotListResponse, TimelineResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def list_snapshots(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
):
    """
    List graph snapshots ordered by timestamp descending.
    Returns lightweight summaries (no nodes/edges JSON).
    """
    try:
        from app.services.snapshot_service import list_snapshots as svc_list
        snapshots, total = svc_list(limit=limit, offset=offset)
        return SnapshotListResponse(
            snapshots=snapshots,
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.error("list_snapshots failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/")
def create_snapshot(body: CreateSnapshotRequest = None):
    """
    Manually create a graph snapshot of the current in-memory graph.
    Returns the lightweight snapshot object.
    """
    if body is None:
        body = CreateSnapshotRequest()
    try:
        from app.core.graph_builder import get_graph
        from app.services.snapshot_service import create_snapshot as svc_create, diff_snapshots, get_latest_snapshot_id

        G = get_graph()
        prev_id = get_latest_snapshot_id()

        snapshot = svc_create(
            G,
            trigger_source=body.trigger_source,
            trigger_desc=body.description,
        )

        # Auto-diff against previous snapshot if one exists
        diff = None
        if prev_id and prev_id != snapshot.snapshot_id:
            try:
                diff = diff_snapshots(prev_id, snapshot.snapshot_id)
            except Exception as exc:
                logger.warning("Auto-diff failed after snapshot creation: %s", exc)

        result = snapshot.model_dump()
        if diff:
            result["diff"] = {
                "severity": diff.severity,
                "alert_triggered": diff.alert_triggered,
                "alert_reasons": diff.alert_reasons,
                "new_attack_paths_count": diff.new_attack_paths_count,
                "new_cycles_count": diff.new_cycles_count,
                "overall_risk_delta": diff.overall_risk_delta,
            }
        return result

    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.error("create_snapshot failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/timeline")
def snapshot_timeline(days: int = Query(default=7, ge=1, le=90)):
    """
    Return risk timeline data points for the last N days.
    Used by the SnapshotTimeline chart on the frontend.
    """
    try:
        from app.services.snapshot_service import get_snapshot_timeline
        points = get_snapshot_timeline(days=days)
        return TimelineResponse(timeline=points, days=days)
    except Exception as exc:
        logger.error("snapshot_timeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/alerts")
def list_alerts(
    limit:    int = Query(default=20, ge=1, le=100),
    severity: str = Query(default=None, description="Filter by severity: critical|high|medium|low"),
):
    """
    List recent temporal alerts, newest first.
    Optionally filter by severity.
    """
    try:
        from app.core.database import list_temporal_alerts
        alerts = list_temporal_alerts(limit=limit, severity=severity)
        return {"alerts": alerts, "total": len(alerts)}
    except Exception as exc:
        logger.error("list_alerts failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{snapshot_id}/diff/{snapshot_id_2}")
def diff_snapshots(snapshot_id: str, snapshot_id_2: str):
    """
    Compare two snapshots and return a detailed SnapshotDiff.
    Detects new attack paths, new cycles, risk changes, node/edge changes.
    """
    try:
        from app.services.snapshot_service import diff_snapshots as svc_diff
        diff = svc_diff(snapshot_id, snapshot_id_2)
        return diff.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("diff_snapshots failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    """
    Retrieve a full snapshot (with all nodes and edges) by ID.
    """
    try:
        from app.services.snapshot_service import get_snapshot_full
        snap = get_snapshot_full(snapshot_id)
        if snap is None:
            raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
        return snap.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_snapshot failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
