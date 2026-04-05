"""
blast_service.py — Blast Radius Service
Orchestrates BFS and enriches zones with severity labels
and risk summaries for the frontend overlay.
"""

from app.algorithm.bfs import blast_radius, highest_risk_in_blast_radius
from app.core.graph_builder import get_graph
from app.utils.helpers import severity_label, timed
from app.utils.logger import get_logger, log_algorithm_run

logger = get_logger(__name__)


@timed
def get_blast_radius(node_id: str, max_hops: int = 3) -> dict:
    """
    Run BFS from a compromised node and return enriched zone data.
    Called by routes_blast.py.
    """
    G = get_graph()

    if node_id not in G:
        return {
            "error":   True,
            "message": f"Node '{node_id}' not found in graph.",
        }

    result = blast_radius(G, node_id, max_hops)

    # Enrich each node in every zone (including zone 0 = source) with severity label
    for hop, nodes in result["zones"].items():
        for node in nodes:
            node["severity"] = severity_label(node["risk"])

    # Summary stats — collect from all zones (zone 0 is the source node itself)
    all_nodes = [n for zone in result["zones"].values() for n in zone]
    critical_count = sum(1 for n in all_nodes if n["risk"] >= 9.0)
    high_count     = sum(1 for n in all_nodes if 7.0 <= n["risk"] < 9.0)

    result["stats"] = {
        "critical": critical_count,
        "high":     high_count,
        "total":    result["total_reachable"],  # includes source node
    }

    # Highest risk node in blast zone (for alert banner)
    result["highest_risk_node"] = highest_risk_in_blast_radius(G, node_id, max_hops)

    log_algorithm_run(
        "bfs_blast_radius",
        {"source": node_id, "max_hops": max_hops},
        f"reachable={result['total_reachable']} critical={critical_count}",
    )

    return result


@timed
def get_multi_blast_radius(node_ids: list[str], max_hops: int = 3) -> dict:
    """
    Run BFS from multiple compromised nodes simultaneously.
    Shows combined blast zone if an attacker controls several entry points.
    """
    G = get_graph()
    combined_reachable = set()
    per_node = {}

    for node_id in node_ids:
        if node_id not in G:
            continue
        result = blast_radius(G, node_id, max_hops)
        combined_reachable.update(result["all_reachable"])
        per_node[node_id] = result

    return {
        "sources":            node_ids,
        "combined_reachable": list(combined_reachable),
        "total_reachable":    len(combined_reachable),
        "per_node":           per_node,
    }
