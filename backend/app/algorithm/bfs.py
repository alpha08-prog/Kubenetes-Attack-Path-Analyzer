"""
bfs.py — Blast Radius Analysis
Uses Breadth-First Search to find all reachable nodes within N hops
from a compromised node, grouped by hop distance.
"""

from collections import deque
import networkx as nx


def blast_radius(G: nx.DiGraph, source: str, max_hops: int = 3) -> dict:
    """
    BFS from a compromised node up to max_hops.

    Returns:
        {
            "source": "pod-api",
            "max_hops": 3,
            "total_reachable": 5,
            "zones": {
                1: [{"id": "sa-backend", "type": "service_account", "risk": 6.5}],
                2: [{"id": "secret-db-creds", "type": "secret", "risk": 8.2}],
                3: [{"id": "db-production", "type": "database", "risk": 9.0}]
            },
            "all_reachable": ["sa-backend", "secret-db-creds", "db-production", ...]
        }
    """
    if source not in G:
        raise ValueError(f"Node '{source}' not found in graph")

    visited = {source: 0}   # node -> hop distance
    queue = deque([source])

    while queue:
        node = queue.popleft()
        current_hop = visited[node]

        if current_hop >= max_hops:
            continue

        for neighbor in G.successors(node):
            if neighbor not in visited:
                visited[neighbor] = current_hop + 1
                queue.append(neighbor)

    # Remove source itself from results
    visited.pop(source)

    # Group by hop distance into zones
    zones = {}
    for node_id, hop in visited.items():
        if hop not in zones:
            zones[hop] = []
        node_data = G.nodes[node_id]
        zones[hop].append({
            "id": node_id,
            "label": node_data.get("label", node_id),
            "type": node_data.get("type", "unknown"),
            "risk": node_data.get("risk", 0.0),
            "namespace": node_data.get("namespace", "default"),
        })

    # Sort each zone by risk descending
    for hop in zones:
        zones[hop].sort(key=lambda x: x["risk"], reverse=True)

    return {
        "source": source,
        "source_label": G.nodes[source].get("label", source),
        "max_hops": max_hops,
        "total_reachable": len(visited),
        "zones": zones,
        "all_reachable": list(visited.keys()),
    }


def blast_radius_summary(G: nx.DiGraph, source: str, max_hops: int = 3) -> str:
    """
    Human-readable summary of blast radius result.
    Used by narrator_service to feed into Claude prompt.
    """
    result = blast_radius(G, source, max_hops)

    lines = [
        f"Blast radius from '{result['source_label']}':",
        f"  Total reachable nodes: {result['total_reachable']} within {max_hops} hops",
    ]
    for hop, nodes in sorted(result["zones"].items()):
        node_names = [n["label"] for n in nodes]
        lines.append(f"  Hop {hop}: {', '.join(node_names)}")

    return "\n".join(lines)


def highest_risk_in_blast_radius(G: nx.DiGraph, source: str, max_hops: int = 3) -> dict | None:
    """
    Returns the single highest-risk node reachable from source.
    Useful for highlighting the most critical exposure.
    """
    result = blast_radius(G, source, max_hops)
    all_nodes = [n for zone in result["zones"].values() for n in zone]

    if not all_nodes:
        return None

    return max(all_nodes, key=lambda x: x["risk"])