"""
cluster_graph_loader.py — Official cluster-graph.json format (judge / rubric).

Loads the organizer JSON schema directly (not kubectl). Maps fields for
NetworkX while preserving rubric attributes: risk_score, relationship, cve, cvss,
is_source, is_sink, cves.

See docs/CLUSTER_GRAPH_SCHEMA.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from app.core.graph_builder import create_graph, add_shared_service_account_lateral_edges
from app.utils.helpers import load_json

_TYPE_ALIASES: dict[str, str] = {
    "pod": "pod",
    "user": "user",
    "serviceaccount": "service_account",
    "role": "role",
    "clusterrole": "cluster_role",
    "secret": "secret",
    "database": "database",
    "configmap": "configmap",
    "node": "node",
    "service": "service",
    "namespace": "namespace",
    "externalactor": "external_actor",
    "persistentvolume": "persistent_volume",
}


def _normalize_type(raw_type: str | None) -> str:
    if not raw_type:
        return "unknown"
    key = raw_type.replace("_", "").replace(" ", "").lower()
    return _TYPE_ALIASES.get(key, raw_type.lower().replace(" ", "_"))


def parse_cluster_graph_document(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a cluster-graph JSON object into internal {nodes, edges, metadata?}.

    - name -> label (when label absent)
    - risk_score -> risk (canonical numeric on graph)
    - relationship -> relation (algorithms); relationship also kept on edge for rubric
    - Preserves: is_source, is_sink, cves, cve, cvss

    Internal / Nokia scenarios: nodes with label+risk and without name/risk_score
    are passed through unchanged.
    """
    if not isinstance(raw, dict) or "nodes" not in raw:
        raise ValueError("Invalid cluster-graph JSON: expected object with 'nodes' array")

    nodes_out: list[dict[str, Any]] = []
    for node in raw.get("nodes", []):
        if not isinstance(node, dict) or "id" not in node:
            continue

        if (
            "label" in node
            and "risk" in node
            and "name" not in node
            and "risk_score" not in node
        ):
            nodes_out.append(dict(node))
            continue

        label = node.get("label") or node.get("name") or node["id"]
        risk_score_val = float(node.get("risk_score", node.get("risk", 0.0)))
        risk = float(node.get("risk", risk_score_val))

        meta: dict[str, Any] = dict(node.get("metadata") or {})

        out_node: dict[str, Any] = {
            "id": node["id"],
            "label": label,
            "type": _normalize_type(node.get("type")),
            "risk": risk,
            "risk_score": risk_score_val,
            "namespace": node.get("namespace", "default"),
            "metadata": meta,
        }
        if "is_source" in node:
            out_node["is_source"] = bool(node["is_source"])
        if "is_sink" in node:
            out_node["is_sink"] = bool(node["is_sink"])
        if "cves" in node:
            out_node["cves"] = list(node["cves"] or [])
        nodes_out.append(out_node)

    edges_out: list[dict[str, Any]] = []
    for edge in raw.get("edges", []):
        if not isinstance(edge, dict):
            continue
        if "source" not in edge or "target" not in edge:
            continue

        relationship = edge.get("relationship") or edge.get("relation") or "accesses"
        weight = float(edge.get("weight", 5.0))
        risk = float(edge.get("risk", weight))

        out_edge: dict[str, Any] = {
            "source": edge["source"],
            "target": edge["target"],
            "relation": relationship,
            "relationship": relationship,
            "weight": weight,
            "risk": risk,
        }
        if "cve" in edge:
            out_edge["cve"] = edge["cve"]
        if "cvss" in edge:
            out_edge["cvss"] = edge["cvss"]
        edges_out.append(out_edge)

    result: dict[str, Any] = {"nodes": nodes_out, "edges": edges_out}
    if "metadata" in raw:
        result["metadata"] = raw["metadata"]
    return result


@dataclass(frozen=True)
class ClusterGraphBuildResult:
    """Outcome of loading cluster-graph.json into NetworkX."""

    graph: nx.DiGraph
    file_metadata: dict[str, Any]
    node_count: int
    edge_count: int
    parsed_nodes: int
    parsed_edges: int


def load_cluster_graph_file(path: str | Path) -> ClusterGraphBuildResult:
    """
    Read cluster-graph.json from disk and build a directed graph.

    Read-only: does not modify the file.
    """
    p = Path(path)
    raw = load_json(p)
    if not isinstance(raw, dict):
        raise ValueError("cluster-graph file must contain a JSON object")
    parsed = parse_cluster_graph_document(raw)
    nodes = parsed.get("nodes", [])
    edges = parsed.get("edges", [])
    G = create_graph({"nodes": nodes, "edges": edges})
    add_shared_service_account_lateral_edges(G)
    meta = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    return ClusterGraphBuildResult(
        graph=G,
        file_metadata=meta,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        parsed_nodes=len(nodes),
        parsed_edges=len(edges),
    )


def graph_counts_match_file_metadata(result: ClusterGraphBuildResult) -> bool:
    """True if built counts match top-level metadata.node_count / edge_count when present."""
    m = result.file_metadata
    nc = m.get("node_count")
    ec = m.get("edge_count")
    if nc is not None and int(nc) != result.node_count:
        return False
    if ec is not None and int(ec) != result.edge_count:
        return False
    return True
