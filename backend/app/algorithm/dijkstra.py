"""
dijkstra.py — Shortest Attack Path
Uses Dijkstra's algorithm to find the lowest-cost (easiest) attack path
between two nodes, where edge weight = exploitability (lower = easier).
"""

import networkx as nx


def shortest_attack_path(G: nx.DiGraph, source: str, target: str) -> dict | None:
    """
    Find the lowest-cost attack path from source to target.

    Edge weights represent exploitability cost (lower = easier to exploit).
    This is computed as: weight = 10 - risk_score
    So a highly risky edge (risk=9) gets weight=1 → Dijkstra prefers it.

    Returns:
        {
            "source": "pod-web",
            "target": "db-production",
            "found": True,
            "hop_count": 3,
            "total_cost": 4.5,
            "path": ["pod-web", "sa-backend", "secret-db-creds", "db-production"],
            "hops": [
                {
                    "from": "pod-web",
                    "from_label": "web-server",
                    "relation": "uses",
                    "to": "sa-backend",
                    "to_label": "backend-sa",
                    "edge_risk": 7.0,
                    "edge_weight": 3.0
                },
                ...
            ]
        }
    """
    if source not in G:
        raise ValueError(f"Source node '{source}' not found in graph")
    if target not in G:
        raise ValueError(f"Target node '{target}' not found in graph")

    try:
        path = nx.dijkstra_path(G, source, target, weight="weight")
        cost = nx.dijkstra_path_length(G, source, target, weight="weight")
    except nx.NetworkXNoPath:
        return {
            "source": source,
            "target": target,
            "found": False,
            "message": f"No path exists from '{source}' to '{target}'",
        }
    except nx.NodeNotFound as e:
        raise ValueError(str(e))

    # Build detailed hop-by-hop breakdown
    hops = []
    for i in range(len(path) - 1):
        frm = path[i]
        to = path[i + 1]
        edge_data = G[frm][to]

        hops.append({
            "step": i + 1,
            "from": frm,
            "from_label": G.nodes[frm].get("label", frm),
            "from_type": G.nodes[frm].get("type", "unknown"),
            "relation": edge_data.get("relation", "accesses"),
            "to": to,
            "to_label": G.nodes[to].get("label", to),
            "to_type": G.nodes[to].get("type", "unknown"),
            "edge_risk": edge_data.get("risk", 0.0),
            "edge_weight": edge_data.get("weight", 0.0),
        })

    return {
        "source": source,
        "source_label": G.nodes[source].get("label", source),
        "target": target,
        "target_label": G.nodes[target].get("label", target),
        "found": True,
        "hop_count": len(path) - 1,
        "total_cost": round(cost, 2),
        "path": path,
        "hops": hops,
    }


def all_attack_paths(G: nx.DiGraph, source: str, target: str, max_paths: int = 5) -> list:
    """
    Find up to max_paths simple paths from source to target,
    sorted by total risk cost (ascending = easiest first).
    Useful for showing attackers have multiple routes.
    """
    if source not in G or target not in G:
        return []

    try:
        raw_paths = list(nx.all_simple_paths(G, source, target))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []

    results = []
    for path in raw_paths:
        total_cost = sum(
            G[path[i]][path[i + 1]].get("weight", 1.0)
            for i in range(len(path) - 1)
        )
        results.append({
            "path": path,
            "hop_count": len(path) - 1,
            "total_cost": round(total_cost, 2),
        })

    results.sort(key=lambda x: x["total_cost"])
    return results[:max_paths]


def attack_path_summary(result: dict) -> str:
    """
    Human-readable summary of shortest attack path.
    Used by narrator_service to feed into Claude prompt.
    """
    if not result.get("found"):
        return f"No attack path found from '{result['source']}' to '{result['target']}'."

    hop_labels = [result["source_label"]]
    for hop in result["hops"]:
        hop_labels.append(f"--[{hop['relation']}]--> {hop['to_label']}")

    chain = " ".join(hop_labels)
    return (
        f"Attack path: {chain}\n"
        f"  Total hops: {result['hop_count']}\n"
        f"  Exploitability cost: {result['total_cost']} (lower = easier)\n"
    )