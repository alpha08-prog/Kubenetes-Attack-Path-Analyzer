"""
node.py — Node Data Models
Pydantic schemas for all Kubernetes resource nodes in the graph.
Used for validation in API requests and internal data passing.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ─── Node Type Enum ────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    POD             = "pod"
    SERVICE_ACCOUNT = "service_account"
    ROLE            = "role"
    SECRET          = "secret"
    DATABASE        = "database"
    USER            = "user"
    NAMESPACE       = "namespace"


# ─── Core Node Model ───────────────────────────────────────────────────────────

class NodeModel(BaseModel):
    """
    Represents a single node in the attack graph.
    All graph nodes — pods, secrets, roles, etc. — use this schema.
    """
    id:        str       = Field(..., description="Unique node ID: type:namespace:name")
    label:     str       = Field(..., description="Human-readable display name")
    type:      NodeType  = Field(..., description="Kubernetes resource type")
    risk:      float     = Field(..., ge=0.0, le=10.0, description="Risk score 0–10 (CVSS-aligned)")
    namespace: str       = Field(default="default", description="Kubernetes namespace")
    metadata:  dict[str, Any] = Field(default_factory=dict, description="Type-specific extra data")

    class Config:
        use_enum_values = True

    @property
    def severity(self) -> str:
        if self.risk >= 9.0: return "critical"
        if self.risk >= 7.0: return "high"
        if self.risk >= 4.0: return "medium"
        if self.risk > 0.0:  return "low"
        return "none"

    @property
    def color(self) -> str:
        """Frontend color for this node type. Matches nodeColors.js."""
        return {
            NodeType.POD:             "#378ADD",
            NodeType.SERVICE_ACCOUNT: "#1D9E75",
            NodeType.ROLE:            "#7F77DD",
            NodeType.SECRET:          "#BA7517",
            NodeType.DATABASE:        "#E24B4A",
            NodeType.USER:            "#D85A30",
            NodeType.NAMESPACE:       "#888780",
        }.get(self.type, "#888780")


# ─── Cytoscape Node (for frontend) ────────────────────────────────────────────

class CytoscapeNode(BaseModel):
    """Cytoscape.js element format for a single node."""
    data: dict[str, Any]

    @classmethod
    def from_node(cls, node: NodeModel) -> "CytoscapeNode":
        return cls(data={
            "id":        node.id,
            "label":     node.label,
            "type":      node.type,
            "risk":      node.risk,
            "severity":  node.severity,
            "color":     node.color,
            "namespace": node.namespace,
            "metadata":  node.metadata,
        })


# ─── Request Models ────────────────────────────────────────────────────────────

class NodeIdRequest(BaseModel):
    """Used by blast radius and simulation endpoints."""
    node_id:  str = Field(..., description="ID of the node to analyze")
    max_hops: int = Field(default=3, ge=1, le=10, description="Max BFS hops")


class AttackPathRequest(BaseModel):
    """Used by the Dijkstra attack path endpoint."""
    source: str = Field(..., description="Source node ID (attacker entry point)")
    target: str = Field(..., description="Target node ID (sensitive asset)")


class SimulateRequest(BaseModel):
    """Used by the what-if node removal simulation endpoint."""
    node_id: str = Field(..., description="Node to remove from the graph")
    source:  str = Field(..., description="Attack path source node")
    target:  str = Field(..., description="Attack path target node")