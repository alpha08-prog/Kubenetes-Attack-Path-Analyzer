"""
edge.py — Edge Data Models
Pydantic schemas for edges (access relationships) in the attack graph,
plus all API response shapes used across every route.
"""

from typing import Any
from pydantic import BaseModel, Field


# ─── Edge Model ────────────────────────────────────────────────────────────────

class EdgeModel(BaseModel):
    """
    Represents a directed access relationship between two nodes.

    relation examples:
        "uses"      — pod uses a service account
        "bound-to"  — service account is bound to a role
        "can-read"  — role can read a secret
        "accesses"  — generic access
    """
    source:   str   = Field(..., description="Source node ID")
    target:   str   = Field(..., description="Target node ID")
    relation: str   = Field(..., description="Type of access relationship")
    risk:     float = Field(..., ge=0.0, le=10.0, description="Risk score of this edge")
    weight:   float = Field(..., description="Exploitability cost on a 0-10 scale; lower = easier to exploit. Dijkstra minimizes sum of weights along a path.")

    class Config:
        json_schema_extra = {
            "example": {
                "source":   "pod:default:web-server",
                "target":   "service_account:default:backend-sa",
                "relation": "uses",
                "risk":     7.5,
                "weight":   2.5,
            }
        }


class CytoscapeEdge(BaseModel):
    """Cytoscape.js element format for a single edge."""
    data: dict[str, Any]

    @classmethod
    def from_edge(cls, edge: EdgeModel, edge_id: str) -> "CytoscapeEdge":
        return cls(data={
            "id":       edge_id,
            "source":   edge.source,
            "target":   edge.target,
            "relation": edge.relation,
            "risk":     edge.risk,
            "weight":   edge.weight,
        })


# ─── Hop Model (for Dijkstra results) ─────────────────────────────────────────

class HopDetail(BaseModel):
    """One step in an attack path."""
    step:       int   = Field(..., description="Step number (1-indexed)")
    from_id:    str
    from_label: str
    from_type:  str
    relation:   str
    to_id:      str
    to_label:   str
    to_type:    str
    edge_risk:  float
    edge_weight: float


# ─── API Response Models ───────────────────────────────────────────────────────

class GraphResponse(BaseModel):
    """Response for GET /api/graph"""
    nodes:    list[dict]
    edges:    list[dict]
    summary:  dict[str, Any]


class AttackPathResponse(BaseModel):
    """Response for POST /api/attack-path"""
    source:       str
    source_label: str
    target:       str
    target_label: str
    found:        bool
    hop_count:    int | None       = None
    total_cost:   float | None     = None
    path:         list[str] | None = None
    hops:         list[HopDetail] | None = None
    message:      str | None       = None


class BlastZoneNode(BaseModel):
    id:        str
    label:     str
    type:      str
    risk:      float
    namespace: str


class BlastRadiusResponse(BaseModel):
    """Response for POST /api/blast-radius"""
    source:          str
    source_label:    str
    max_hops:        int
    total_reachable: int
    zones:           dict[int, list[BlastZoneNode]]
    all_reachable:   list[str]


class CycleNode(BaseModel):
    id:        str
    label:     str
    type:      str
    risk:      float
    namespace: str


class CycleDetail(BaseModel):
    id:           int
    length:       int
    nodes:        list[str]
    node_details: list[CycleNode]
    severity:     str
    max_risk:     float
    chain:        str
    description:  str


class CyclesResponse(BaseModel):
    """Response for GET /api/cycles"""
    cycle_count: int
    cycles:      list[CycleDetail]
    message:     str | None = None


class CriticalNodeDetail(BaseModel):
    rank:              int
    id:                str
    label:             str
    type:              str
    namespace:         str
    centrality_score:  float
    risk:              float
    combined_score:    float
    recommendation:    str


class CriticalNodesResponse(BaseModel):
    """Response for GET /api/critical-nodes"""
    total_nodes: int
    top_n:       int
    nodes:       list[CriticalNodeDetail]


class Finding(BaseModel):
    """One finding from the AI narrator."""
    id:             str
    severity:       str
    category:       str
    title:          str
    description:    str
    kill_chain:     str | None
    affected_nodes: list[str]
    recommendation: str
    effort:         str


class ReportResponse(BaseModel):
    """Response for GET /api/report"""
    report_title:   str
    cluster:        str
    generated_at:   str
    tool:           str
    total_findings: int
    model_used:     str
    findings:       list[Finding]


class SimulationResponse(BaseModel):
    """Response for POST /api/simulate"""
    node_removed:        str
    node_label:          str
    source:              str
    target:              str
    paths_before:        int
    paths_after:         int
    paths_broken:        int
    cost_before:         float | None
    cost_after:          float | None
    shortest_path_before: list[str] | None
    shortest_path_after:  list[str] | None
    impact:              str
    recommendation:      str
    narrative:           str | None = None


class ErrorResponse(BaseModel):
    """Standard error shape for all 4xx/5xx responses."""
    error:   str
    detail:  str | None = None
    path:    str | None = None
