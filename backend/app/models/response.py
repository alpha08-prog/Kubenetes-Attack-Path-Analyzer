"""
response.py — API Response Models
All Pydantic response shapes used across every route.
Import these in route files as return type annotations.
"""

from typing import Any
from pydantic import BaseModel, Field


# ─── Graph ────────────────────────────────────────────────────────────────────

class GraphSummaryResponse(BaseModel):
    total_nodes:  int
    total_edges:  int
    is_dag:       bool
    node_types:   dict[str, int]
    entry_points: list[str]
    targets:      list[str]
    built_at:     str | None = None


class GraphResponse(BaseModel):
    nodes:   list[dict[str, Any]]
    edges:   list[dict[str, Any]]
    summary: GraphSummaryResponse | None = None


class GraphMetadataResponse(BaseModel):
    built_at:    str | None = None
    node_count:  int
    edge_count:  int
    is_dag:      bool


class GraphReloadResponse(BaseModel):
    status:     str
    source:     str
    node_count: int
    edge_count: int


# ─── Attack Path ──────────────────────────────────────────────────────────────

class HopDetail(BaseModel):
    step:        int
    from_id:     str
    from_label:  str
    from_type:   str
    relation:    str
    to_id:       str
    to_label:    str
    to_type:     str
    edge_risk:   float
    edge_weight: float
    severity:    str | None = None


class RemediationStep(BaseModel):
    title: str
    description: str
    action_type: str  # "rbac", "network_policy", "pod_hardening", "secret_isolation"
    target_resource: str
    target_resource_type: str
    change: str
    yaml_snippet: str
    impact_count: int
    difficulty: str  # "low", "medium", "high"


class AttackPathResponse(BaseModel):
    source:        str
    source_label:  str
    target:        str
    target_label:  str
    found:         bool
    hop_count:     int   | None = None
    total_cost:    float | None = None
    severity:      str   | None = None
    path:          list[str]    | None = None
    hops:          list[HopDetail] | None = None
    message:       str   | None = None
    auto_detected: bool  | None = None
    remediations:  list[RemediationStep] | None = None  # NEW: suggested fixes


class AllPathsEntry(BaseModel):
    path:       list[str]
    hop_count:  int
    total_cost: float


class AllAttackPathsResponse(BaseModel):
    source: str
    target: str
    count:  int
    paths:  list[AllPathsEntry]


# ─── Blast Radius ─────────────────────────────────────────────────────────────

class BlastZoneNode(BaseModel):
    id:        str
    label:     str
    type:      str
    risk:      float
    namespace: str
    severity:  str | None = None


class BlastStats(BaseModel):
    critical: int
    high:     int
    total:    int


class BlastRadiusResponse(BaseModel):
    source:            str
    source_label:      str
    max_hops:          int
    total_reachable:   int
    zones:             dict[int, list[BlastZoneNode]]
    all_reachable:     list[str]
    stats:             BlastStats      | None = None
    highest_risk_node: BlastZoneNode   | None = None


class MultiBlastRadiusResponse(BaseModel):
    sources:            list[str]
    combined_reachable: list[str]
    total_reachable:    int
    per_node:           dict[str, Any]


# ─── Cycles ───────────────────────────────────────────────────────────────────

class CycleNodeDetail(BaseModel):
    id:        str
    label:     str
    type:      str
    risk:      float
    namespace: str


class CycleDetail(BaseModel):
    id:           int
    length:       int
    nodes:        list[str]
    node_details: list[CycleNodeDetail]
    severity:     str
    max_risk:     float
    chain:        str
    description:  str


class CyclesResponse(BaseModel):
    cycle_count:    int
    cycles:         list[CycleDetail]
    cycle_node_ids: list[str] | None = None
    message:        str       | None = None


class NodeCyclesResponse(BaseModel):
    node_id:     str
    cycle_count: int
    cycles:      list[CycleDetail]


# ─── Critical Nodes ───────────────────────────────────────────────────────────

class CriticalNodeDetail(BaseModel):
    rank:             int
    id:               str
    label:            str
    type:             str
    namespace:        str
    centrality_score: float
    risk:             float
    combined_score:   float
    recommendation:   str


class CriticalNodesResponse(BaseModel):
    total_nodes: int
    top_n:       int
    nodes:       list[CriticalNodeDetail]


class RemovalCandidate(BaseModel):
    node_id:        str
    node_label:     str
    node_type:      str
    paths_broken:   int
    impact:         str
    recommendation: str


class RemovalCandidatesResponse(BaseModel):
    source:     str
    target:     str
    candidates: list[RemovalCandidate]


# ─── AI Report ────────────────────────────────────────────────────────────────

class Finding(BaseModel):
    id:             str
    severity:       str
    category:       str
    title:          str
    description:    str
    kill_chain:     str  | None = None
    affected_nodes: list[str]
    recommendation: str
    effort:         str


class ReportResponse(BaseModel):
    report_title:   str
    cluster:        str
    generated_at:   str
    tool:           str
    total_findings: int
    model_used:     str
    findings:       list[Finding]


# ─── Simulation ───────────────────────────────────────────────────────────────

class SimulationResponse(BaseModel):
    node_removed:         str
    node_label:           str
    source:               str
    target:               str
    paths_before:         int
    paths_after:          int
    paths_broken:         int
    cycles_before:        int   | None = None
    cycles_after:         int   | None = None
    cycles_broken:        int   | None = None
    cost_before:          float | None = None
    cost_after:           float | None = None
    shortest_path_before: list[str] | None = None
    shortest_path_after:  list[str] | None = None
    impact:               str
    recommendation:       str
    narrative:            str  | None = None
    auto_detected:        bool | None = None


# ─── Shared / Error ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error:  str
    detail: str  | None = None
    path:   str  | None = None


class StatusResponse(BaseModel):
    status:  str
    message: str | None = None


# ─── Threat Score ─────────────────────────────────────────────────────────────

class ThreatScoreFactors(BaseModel):
    attack_paths: bool
    shortest_path_hops: int | None
    privilege_escalation_cycles: int
    critical_node_junctions: int
    blast_radius_size: int


class ThreatScoreBenchmarks(BaseModel):
    example_safe_cluster: float
    example_typical_cluster: float
    example_vulnerable_cluster: float


class ThreatScoreResponse(BaseModel):
    threat_score: float  # 1.0-10.0
    risk_level: str  # "critical", "high", "medium", "low", "minimal"
    description: str
    factors: ThreatScoreFactors
    benchmarks: ThreatScoreBenchmarks


class ThreatScoreTrend(BaseModel):
    trend: str  # "improving", "worsening", "stable", "insufficient_data"
    score_delta: float | None
    previous_score: float | None
    latest_score: float | None