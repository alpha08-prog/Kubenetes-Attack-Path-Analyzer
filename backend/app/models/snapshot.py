"""
snapshot.py — Graph Snapshot & Diff Data Models
Used by snapshot_service.py and routes_snapshot.py.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class SnapshotMeta(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    entry_points: list[str] = Field(default_factory=list)
    sensitive_targets: list[str] = Field(default_factory=list)
    cycles_detected: int = 0
    aggregate_risk: float = 0.0


class SnapshotTrigger(BaseModel):
    source: str = "manual"   # manual | watch_api | api_call
    description: str = ""


class GraphSnapshot(BaseModel):
    """Immutable record of the graph state at a point in time."""
    snapshot_id: str
    cluster_name: str
    timestamp: str
    trigger: SnapshotTrigger = Field(default_factory=SnapshotTrigger)
    metadata: SnapshotMeta = Field(default_factory=SnapshotMeta)
    # nodes / edges NOT included here — fetched on demand to keep list payloads small


class GraphSnapshotFull(GraphSnapshot):
    """Full snapshot with node and edge data (returned by GET /snapshots/{id})."""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class SnapshotDiff(BaseModel):
    """Result of comparing two graph snapshots."""
    diff_id: str
    snapshot_id_before: str
    snapshot_id_after: str
    timestamp_before: str
    timestamp_after: str

    # Node changes
    nodes_added: list[str] = Field(default_factory=list)
    nodes_removed: list[str] = Field(default_factory=list)
    nodes_risk_increased: list[dict[str, Any]] = Field(default_factory=list)
    nodes_risk_decreased: list[dict[str, Any]] = Field(default_factory=list)

    # Edge changes
    edges_added: list[dict[str, Any]] = Field(default_factory=list)
    edges_removed: list[dict[str, Any]] = Field(default_factory=list)

    # Path analysis
    new_attack_paths: list[dict[str, Any]] = Field(default_factory=list)
    disappeared_paths: list[dict[str, Any]] = Field(default_factory=list)

    # Cycle analysis
    new_cycles: list[dict[str, Any]] = Field(default_factory=list)
    disappeared_cycles: list[dict[str, Any]] = Field(default_factory=list)

    # Risk metrics
    overall_risk_delta: float = 0.0
    high_risk_nodes_delta: int = 0

    # Summary counts (convenience)
    nodes_added_count: int = 0
    nodes_removed_count: int = 0
    edges_added_count: int = 0
    edges_removed_count: int = 0
    new_attack_paths_count: int = 0
    disappeared_paths_count: int = 0
    new_cycles_count: int = 0
    disappeared_cycles_count: int = 0

    # Alert result
    severity: str = "low"
    alert_triggered: bool = False
    alert_reasons: list[str] = Field(default_factory=list)

    computed_at: str = ""


class SnapshotListResponse(BaseModel):
    snapshots: list[GraphSnapshot]
    total: int
    limit: int
    offset: int


class CreateSnapshotRequest(BaseModel):
    trigger_source: str = Field(default="manual", description="manual | watch_api | api_call")
    description: str = Field(default="Manual snapshot", description="Human-readable trigger description")


class TimelinePoint(BaseModel):
    snapshot_id: str
    timestamp: str
    aggregate_risk: float
    node_count: int
    edge_count: int
    cycles_detected: int


class TimelineResponse(BaseModel):
    timeline: list[TimelinePoint]
    days: int
