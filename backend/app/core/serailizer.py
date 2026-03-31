"""
serializer.py — Graph Serializer
Converts a NetworkX DiGraph into Cytoscape.js element format
consumed by GraphCanvas.jsx on the frontend.

Also provides node/edge filtering helpers used by the
blast radius and attack path overlays.
"""

import networkx as nx
from app.utils.helpers import severity_label, node_type_color
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Main serializer ──────────────────────────────────────────────────────────

def to_cytoscape(G: nx.DiGraph) -> dict:
    """
    Convert full graph to Cytoscape.js elements format.

    Returns:
        {
            "nodes": [ {"data": {...}}, ... ],
            "edges": [ {"data": {...}}, ... ]
        }
    """
    cy_nodes = _serialize_nodes(G)
    cy_edges = _serialize_edges(G)

    logger.debug("Serialized %d nodes and %d edges to Cytoscape format",
                 len(cy_nodes), len(cy_edges))

    return {"nodes": cy_nodes, "edges": cy_edges}


def to_cytoscape_subgraph(G: nx.DiGraph, node_ids: list[str]) -> dict:
    """
    Serialize only a subset of nodes and their connecting edges.
    Used by blast radius and attack path overlays to send
    only the relevant portion of the graph to the frontend.

    Args:
        node_ids: list of node IDs to include
    """
    subgraph = G.subgraph(node_ids)
    return to_cytoscape(subgraph)


def path_to_cytoscape(G: nx.DiGraph, path: list[str]) -> dict:
    """
    Serialize a specific attack path (ordered node list) into
    Cytoscape elements with highlighted edge styling data.
    Used by AttackPathPanel.jsx to render the kill chain overlay.
    """
    cy_nodes = []
    for node_id in path:
        if node_id not in G:
            continue
        attrs = G.nodes[node_id]
        cy_nodes.append({
            "data": {
                **_node_data(node_id, attrs),
                "in_path": True,
            }
        })

    cy_edges = []
    for i in range(len(path) - 1):
        src, dst = path[i], path[i + 1]
        if not G.has_edge(src, dst):
            continue
        edge_attrs = G[src][dst]
        cy_edges.append({
            "data": {
                **_edge_data(f"path-e{i}", src, dst, edge_attrs),
                "in_path":   True,
                "path_step": i + 1,
            }
        })

    return {"nodes": cy_nodes, "edges": cy_edges}


def blast_to_cytoscape(
    G: nx.DiGraph,
    source: str,
    zones: dict,
) -> dict:
    """
    Serialize blast radius result with hop-zone metadata attached
    to each node. Frontend uses `hop` to color concentric rings.

    zones: { hop_int: [ {id, label, type, risk, ...}, ... ] }
    """
    # Build a flat id → hop lookup
    hop_map = {source: 0}
    for hop, nodes in zones.items():
        for n in nodes:
            hop_map[n["id"]] = hop

    cy_nodes = []
    all_ids = list(hop_map.keys())
    for node_id in all_ids:
        if node_id not in G:
            continue
        attrs = G.nodes[node_id]
        cy_nodes.append({
            "data": {
                **_node_data(node_id, attrs),
                "hop":        hop_map[node_id],
                "is_source":  node_id == source,
            }
        })

    # Include edges only between nodes in the blast zone
    cy_edges = []
    id_set = set(all_ids)
    for i, (src, dst, edge_attrs) in enumerate(G.edges(data=True)):
        if src in id_set and dst in id_set:
            cy_edges.append({
                "data": _edge_data(f"b-e{i}", src, dst, edge_attrs)
            })

    return {"nodes": cy_nodes, "edges": cy_edges}


# ─── Node serialization ───────────────────────────────────────────────────────

def _serialize_nodes(G: nx.DiGraph) -> list:
    return [
        {"data": _node_data(node_id, attrs)}
        for node_id, attrs in G.nodes(data=True)
    ]


def _node_data(node_id: str, attrs: dict) -> dict:
    risk = attrs.get("risk", 0.0)
    ntype = attrs.get("type", "unknown")
    return {
        "id":        node_id,
        "label":     attrs.get("label", node_id),
        "type":      ntype,
        "risk":      risk,
        "severity":  severity_label(risk),
        "color":     node_type_color(ntype),
        "namespace": attrs.get("namespace", "default"),
        "metadata":  attrs.get("metadata", {}),
    }


# ─── Edge serialization ───────────────────────────────────────────────────────

def _serialize_edges(G: nx.DiGraph) -> list:
    return [
        {"data": _edge_data(f"e{i}", src, dst, attrs)}
        for i, (src, dst, attrs) in enumerate(G.edges(data=True))
    ]


def _edge_data(edge_id: str, src: str, dst: str, attrs: dict) -> dict:
    risk = attrs.get("risk", 5.0)
    return {
        "id":       edge_id,
        "source":   src,
        "target":   dst,
        "relation": attrs.get("relation", "accesses"),
        "risk":     risk,
        "weight":   attrs.get("weight", 5.0),
        "severity": severity_label(risk),
    }