"""
centrality.py — Critical Node Identification
Uses Betweenness Centrality to find nodes whose removal would
break the maximum number of attack paths.
Also supports "what-if" simulation: remove a node and recompute.
"""

import networkx as nx
from copy import deepcopy


def find_critical_nodes(G: nx.DiGraph, top_n: int = 10) -> dict:
    """
    Rank nodes by betweenness centrality — how many shortest paths
    pass through each node. High centrality = removing this node
    breaks the most attack routes.

    Returns:
        {
            "total_nodes": 18,
            "top_n": 5,
            "nodes": [
                {
                    "rank": 1,
                    "id": "sa-cluster-admin",
                    "label": "cluster-admin-sa",
                    "type": "service_account",
                    "centrality_score": 0.847,
                    "risk": 9.2,
                    "combined_score": 8.93,
                    "recommendation": "Remove cluster-admin binding from sa-cluster-admin"
                },
                ...
            ]
        }
    """
    if len(G.nodes) == 0:
        return {"total_nodes": 0, "top_n": top_n, "nodes": []}

    # Betweenness centrality — fraction of all shortest paths passing through each node
    centrality = nx.betweenness_centrality(G, weight="weight", normalized=True)

    ranked = []
    for node_id, score in centrality.items():
        node_data = G.nodes[node_id]
        risk = node_data.get("risk", 0.0)

        # Combined score weights centrality (structural importance) + risk (exploitability)
        combined = round((score * 0.6) + ((risk / 10.0) * 0.4), 4)

        ranked.append({
            "id": node_id,
            "label": node_data.get("label", node_id),
            "type": node_data.get("type", "unknown"),
            "namespace": node_data.get("namespace", "default"),
            "centrality_score": round(score, 4),
            "risk": risk,
            "combined_score": combined,
            "recommendation": _generate_recommendation(node_id, node_data, score),
        })

    ranked.sort(key=lambda x: x["combined_score"], reverse=True)

    # Add rank
    for i, node in enumerate(ranked):
        node["rank"] = i + 1

    return {
        "total_nodes": len(G.nodes),
        "top_n": top_n,
        "nodes": ranked[:top_n],
    }


def simulate_node_removal(
    G: nx.DiGraph,
    node_to_remove: str,
    source: str,
    target: str,
) -> dict:
    """
    Simulate removing a node and show the impact on attack paths.
    Used by simulator_service for the "what-if" feature.

    Returns before/after comparison:
        {
            "node_removed": "sa-cluster-admin",
            "paths_before": 3,
            "paths_after": 0,
            "paths_broken": 3,
            "shortest_path_before": {...},
            "shortest_path_after": None,
            "impact": "critical"
        }
    """
    if node_to_remove not in G:
        raise ValueError(f"Node '{node_to_remove}' not found in graph")

    # Count paths before removal
    try:
        paths_before = list(nx.all_simple_paths(G, source, target))
        shortest_before = nx.dijkstra_path(G, source, target, weight="weight")
        cost_before = nx.dijkstra_path_length(G, source, target, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        paths_before = []
        shortest_before = None
        cost_before = None

    # Remove node and recompute
    G_reduced = deepcopy(G)
    G_reduced.remove_node(node_to_remove)

    try:
        paths_after = list(nx.all_simple_paths(G_reduced, source, target))
        shortest_after = nx.dijkstra_path(G_reduced, source, target, weight="weight")
        cost_after = nx.dijkstra_path_length(G_reduced, source, target, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        paths_after = []
        shortest_after = None
        cost_after = None

    paths_broken = len(paths_before) - len(paths_after)
    impact = _classify_removal_impact(paths_broken, len(paths_before))

    return {
        "node_removed": node_to_remove,
        "node_label": G.nodes[node_to_remove].get("label", node_to_remove),
        "source": source,
        "target": target,
        "paths_before": len(paths_before),
        "paths_after": len(paths_after),
        "paths_broken": paths_broken,
        "cost_before": round(cost_before, 2) if cost_before is not None else None,
        "cost_after": round(cost_after, 2) if cost_after is not None else None,
        "shortest_path_before": shortest_before,
        "shortest_path_after": shortest_after,
        "impact": impact,
        "recommendation": _generate_recommendation(
            node_to_remove, G.nodes[node_to_remove], 1.0
        ),
    }


def _classify_removal_impact(paths_broken: int, total_paths: int) -> str:
    if total_paths == 0:
        return "none"
    ratio = paths_broken / total_paths
    if ratio == 1.0:
        return "critical"   # removes ALL paths
    elif ratio >= 0.5:
        return "high"
    elif ratio > 0:
        return "medium"
    else:
        return "low"


def _generate_recommendation(node_id: str, node_data: dict, centrality: float) -> str:
    """
    Generate a specific hardening recommendation based on node type.
    """
    node_type = node_data.get("type", "unknown")
    label = node_data.get("label", node_id)

    recommendations = {
        "service_account": (
            f"Restrict permissions on ServiceAccount '{label}'. "
            "Apply least-privilege RBAC — remove any cluster-admin or wildcard bindings."
        ),
        "role": (
            f"Audit Role '{label}' — remove wildcard verbs (*) and "
            "limit resource access to only what is necessary."
        ),
        "secret": (
            f"Rotate Secret '{label}' immediately. "
            "Consider using a secrets manager (Vault, AWS Secrets Manager) "
            "instead of Kubernetes Secrets."
        ),
        "pod": (
            f"Harden Pod '{label}' — disable privilege escalation, "
            "run as non-root, and drop all Linux capabilities."
        ),
        "database": (
            f"Add network policy to restrict access to '{label}'. "
            "Only explicitly whitelisted pods should reach this database."
        ),
    }

    return recommendations.get(
        node_type,
        f"Review and restrict access to '{label}' (centrality={round(centrality, 3)}).",
    )


def critical_nodes_summary(result: dict) -> str:
    """
    Human-readable summary of critical nodes.
    Used by narrator_service to feed into Claude prompt.
    """
    if not result["nodes"]:
        return "No critical nodes identified."

    lines = [f"Top {result['top_n']} critical nodes by combined centrality + risk score:"]
    for node in result["nodes"]:
        lines.append(
            f"  #{node['rank']} {node['label']} ({node['type']}) — "
            f"centrality={node['centrality_score']}, risk={node['risk']}, "
            f"combined={node['combined_score']}"
        )
        lines.append(f"       Fix: {node['recommendation']}")
    return "\n".join(lines)