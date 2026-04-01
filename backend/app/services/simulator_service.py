"""
simulator_service.py — Node Removal What-If Simulation  ★ WOW FACTOR ★
Removes a node from the graph, reruns all algorithms,
and returns a before/after delta with AI narration.
"""

from app.algorithm.centrality import simulate_node_removal
from app.algorithm.dfs_cycles import detect_cycles
from app.core.graph_builder import get_graph
from app.utils.helpers import timed
from app.utils.logger import get_logger, log_algorithm_run

logger = get_logger(__name__)


@timed
def simulate_removal(node_id: str, source: str, target: str) -> dict:
    """
    Remove node_id from the graph and measure impact on attack paths.
    Called by routes_simulate.py.

    Returns a full before/after comparison with AI narration.
    """
    G = get_graph()

    if node_id not in G:
        return {
            "error":   True,
            "message": f"Node '{node_id}' not found in graph.",
        }

    result = simulate_node_removal(G, node_id, source, target)

    # Also check cycle impact
    from copy import deepcopy
    G_reduced = deepcopy(G)
    G_reduced.remove_node(node_id)

    cycles_before = detect_cycles(G)
    cycles_after  = detect_cycles(G_reduced)

    result["cycles_before"] = cycles_before["cycle_count"]
    result["cycles_after"]  = cycles_after["cycle_count"]
    result["cycles_broken"] = cycles_before["cycle_count"] - cycles_after["cycle_count"]

    log_algorithm_run(
        "simulate_removal",
        {"node": node_id, "source": source, "target": target},
        f"paths_broken={result['paths_broken']} impact={result['impact']}",
    )

    # Attach AI narration
    try:
        from app.services.narrator_service import narrate_simulation
        result["narrative"] = narrate_simulation(result)
    except Exception as e:
        logger.warning("Could not generate simulation narrative: %s", e)
        result["narrative"] = None

    return result


def get_top_removal_candidates(source: str, target: str, top_n: int = 5) -> list:
    """
    Find the top N nodes whose removal breaks the most attack paths.
    Helps the analyst decide which node to harden first.
    Used by CriticalNodeTable.jsx 'Simulate' button to pre-rank candidates.
    """
    G = get_graph()
    results = []

    for node_id in list(G.nodes):
        node_type = G.nodes[node_id].get("type", "")
        # Only simulate removal of intermediate nodes, not source/target
        if node_id in (source, target):
            continue
        # Focus on high-value node types
        if node_type not in ("service_account", "role", "secret"):
            continue

        try:
            sim = simulate_node_removal(G, node_id, source, target)
            if sim.get("paths_broken", 0) > 0:
                results.append({
                    "node_id":      node_id,
                    "node_label":   G.nodes[node_id].get("label", node_id),
                    "node_type":    node_type,
                    "paths_broken": sim["paths_broken"],
                    "impact":       sim["impact"],
                    "recommendation": sim.get("recommendation", ""),
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["paths_broken"], reverse=True)
    return results[:top_n]
