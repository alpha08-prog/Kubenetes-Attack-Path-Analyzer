"""
analysis_service.py — Combined Analysis Service
Orchestrates cycle detection and critical node identification.
Also produces the combined summary fed into the Claude narrator.
"""

from app.algorithm.dfs_cycles import detect_cycles, nodes_in_any_cycle
from app.algorithm.centrality import find_critical_nodes
from app.core.graph_builder import get_graph
from app.utils.helpers import timed
from app.utils.logger import get_logger, log_algorithm_run

logger = get_logger(__name__)


@timed
def get_cycles() -> dict:
    """
    Detect all privilege escalation cycles in the graph.
    Called by routes_cycles.py.
    """
    G = get_graph()
    result = detect_cycles(G)

    log_algorithm_run(
        "dfs_cycle_detection",
        {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
        f"cycles_found={result['cycle_count']}",
    )

    # Add set of all involved node IDs for frontend highlighting
    result["cycle_node_ids"] = list(nodes_in_any_cycle(G))

    return result


@timed
def get_critical_nodes(top_n: int = 10) -> dict:
    """
    Rank nodes by betweenness centrality + risk score.
    Called by routes_critical.py.
    """
    G = get_graph()
    result = find_critical_nodes(G, top_n=top_n)

    log_algorithm_run(
        "betweenness_centrality",
        {"top_n": top_n},
        f"top_node={result['nodes'][0]['label'] if result['nodes'] else 'none'}",
    )

    return result


def get_full_analysis() -> dict:
    """
    Run all four algorithms in one call and return a combined report dict.
    This is what narrator_service.py consumes to build the Claude prompt.
    Called internally — not directly exposed as a route.
    """
    G = get_graph()

    from app.algorithm.dijkstra import shortest_attack_path
    from app.algorithm.bfs import blast_radius
    from app.core.graph_builder import find_entry_points, find_sensitive_targets

    # Auto-detect best source/target pair
    entries = find_entry_points(G)
    targets = find_sensitive_targets(G)

    attack_path = None
    blast = None

    if entries and targets:
        entries_sorted = sorted(entries, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)
        targets_sorted = sorted(targets, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)

        for source in entries_sorted:
            for target in targets_sorted:
                ap = shortest_attack_path(G, source, target)
                if ap.get("found"):
                    attack_path = ap
                    blast = blast_radius(G, source, max_hops=3)
                    break
            if attack_path:
                break

    cycles        = detect_cycles(G)
    critical      = find_critical_nodes(G, top_n=5)

    logger.info(
        "Full analysis: path_found=%s, cycles=%d, critical_nodes=%d",
        bool(attack_path and attack_path.get("found")),
        cycles["cycle_count"],
        len(critical["nodes"]),
    )

    return {
        "attack_path":    attack_path,
        "blast_radius":   blast,
        "cycles":         cycles,
        "critical_nodes": critical,
    }
