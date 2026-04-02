"""
graph_builder.py â€” NetworkX DiGraph Construction
Takes the cleaned node/edge list from parser.py and builds
a NetworkX DiGraph that all algorithms operate on.

Also exposes helpers to query the graph used across services.
"""

import networkx as nx

from app.utils.logger import get_logger, log_graph_event
from app.utils.helpers import timed, utc_now

logger = get_logger(__name__)

# Module-level graph instance â€” rebuilt on each ingestion call
_graph: nx.DiGraph = nx.DiGraph()
_metadata: dict = {}


# â”€â”€â”€ Build â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@timed
def build_graph(parsed_data: dict) -> nx.DiGraph:
    """
    Build a NetworkX DiGraph from the output of parser.parse_cluster_data().

    Each node carries its full metadata as node attributes.
    Each edge carries relation, risk, and weight attributes.

    Args:
        parsed_data: {"nodes": [...], "edges": [...]}

    Returns:
        nx.DiGraph ready for all algorithm modules.
    """
    global _graph, _metadata

    G = nx.DiGraph()

    nodes = parsed_data.get("nodes", [])
    edges = parsed_data.get("edges", [])

    # Add nodes with all attributes
    for node in nodes:
        node_id = node["id"]
        G.add_node(
            node_id,
            label=node.get("label", node_id),
            type=node.get("type", "unknown"),
            risk=node.get("risk", 0.0),
            namespace=node.get("namespace", "default"),
            metadata=node.get("metadata", {}),
        )

    # Add edges with all attributes
    skipped = 0
    for edge in edges:
        src = edge["source"]
        dst = edge["target"]

        # Only add edge if both nodes exist
        if src not in G.nodes or dst not in G.nodes:
            logger.debug("Skipping edge %s â†’ %s (node not in graph)", src, dst)
            skipped += 1
            continue

        G.add_edge(
            src,
            dst,
            relation=edge.get("relation", "accesses"),
            risk=edge.get("risk", 5.0),
            weight=edge.get("weight", 5.0),
        )

    if skipped:
        logger.warning("Skipped %d edges with missing nodes", skipped)

    _graph = G
    _metadata = {
        "built_at":   utc_now(),
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "is_dag":     nx.is_directed_acyclic_graph(G),
    }

    log_graph_event("build_graph", G.number_of_nodes(), G.number_of_edges(), source="parser")
    return G


# â”€â”€â”€ Get current graph â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_graph() -> nx.DiGraph:
    """
    Return the currently loaded graph.
    Called by all route handlers and services.
    Raises if no graph has been built yet.
    """
    if _graph.number_of_nodes() == 0:
        raise RuntimeError(
            "Graph is empty. Run ingestion first: POST /api/graph/reload "
            "or set MOCK_MODE=true to auto-load the Nokia scenario."
        )
    return _graph


def get_metadata() -> dict:
    """Return metadata about the currently loaded graph."""
    return _metadata


# â”€â”€â”€ Serialization for frontend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def graph_to_cytoscape(G: nx.DiGraph) -> dict:
    """
    Convert the NetworkX DiGraph to Cytoscape.js element format.

    Returns:
        {
            "nodes": [ {"data": {"id", "label", "type", "risk", ...}} ],
            "edges": [ {"data": {"id", "source", "target", "relation", "risk"}} ]
        }
    """
    cy_nodes = []
    for node_id, attrs in G.nodes(data=True):
        cy_nodes.append({
            "data": {
                "id":        node_id,
                "label":     attrs.get("label", node_id),
                "type":      attrs.get("type", "unknown"),
                "risk":      attrs.get("risk", 0.0),
                "namespace": attrs.get("namespace", "default"),
                "metadata":  attrs.get("metadata", {}),
            }
        })

    cy_edges = []
    for i, (src, dst, attrs) in enumerate(G.edges(data=True)):
        cy_edges.append({
            "data": {
                "id":       f"e{i}",
                "source":   src,
                "target":   dst,
                "relation": attrs.get("relation", "accesses"),
                "risk":     attrs.get("risk", 5.0),
                "weight":   attrs.get("weight", 5.0),
            }
        })

    return {"nodes": cy_nodes, "edges": cy_edges}


# â”€â”€â”€ Graph Query Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_nodes_by_type(G: nx.DiGraph, node_type: str) -> list:
    """
    Return all node IDs of a given type.

    Usage:
        databases = get_nodes_by_type(G, "database")
        pods = get_nodes_by_type(G, "pod")
    """
    return [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("type") == node_type
    ]


def get_high_risk_nodes(G: nx.DiGraph, threshold: float = 7.0) -> list:
    """
    Return all nodes with risk score >= threshold, sorted by risk descending.
    Used to auto-select source/target nodes for demo mode.
    """
    results = [
        {
            "id":    n,
            "label": attrs.get("label", n),
            "type":  attrs.get("type", "unknown"),
            "risk":  attrs.get("risk", 0.0),
        }
        for n, attrs in G.nodes(data=True)
        if attrs.get("risk", 0.0) >= threshold
    ]
    return sorted(results, key=lambda x: x["risk"], reverse=True)


def find_entry_points(G: nx.DiGraph) -> list:
    """
    Find likely attacker entry points.
    Restrict to attacker-controllable identities/workloads so we don't
    pick isolated sensitive assets as both source and target.
    These are natural Dijkstra source nodes.
    """
    entry_types = {"pod", "user", "service_account"}
    return [
        n for n in G.nodes
        if G.in_degree(n) == 0
        and G.nodes[n].get("type") in entry_types
        and G.nodes[n].get("risk", 0) >= 3.0
    ]

def find_sensitive_targets(G: nx.DiGraph) -> list:
    """
    Find likely target nodes â€” databases and high-risk secrets
    with no outgoing edges (sinks in the graph).
    These are natural Dijkstra target nodes.
    """
    return [
        n for n in G.nodes
        if G.out_degree(n) == 0
        and G.nodes[n].get("type") in ("database", "secret")
        and G.nodes[n].get("risk", 0) >= 7.0
    ]


def graph_summary(G: nx.DiGraph) -> dict:
    """
    Return a quick summary of graph stats for the dashboard header.
    """
    type_counts = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total_nodes":  G.number_of_nodes(),
        "total_edges":  G.number_of_edges(),
        "is_dag":       nx.is_directed_acyclic_graph(G),
        "node_types":   type_counts,
        "entry_points": find_entry_points(G),
        "targets":      find_sensitive_targets(G),
        "built_at":     _metadata.get("built_at"),
    }