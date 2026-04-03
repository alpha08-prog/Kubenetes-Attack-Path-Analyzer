"""
analysis_service.py — Combined Analysis Service
Orchestrates cycle detection and critical node identification.
Also produces the combined summary fed into the AI narrator.
"""

from app.algorithm.dfs_cycles import detect_cycles, nodes_in_any_cycle
from app.algorithm.centrality import find_critical_nodes
from app.core.graph_builder import get_graph
from app.utils.helpers import timed
from app.utils.logger import get_logger, log_algorithm_run
from app.services.threat_score_service import calculate_threat_score
from app.services.remediation_service import analyze_attack_path_for_remediation, analyze_cycles_for_remediation

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
    This is what narrator_service.py consumes to build the AI prompt.
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
                if source == target:
                    continue
                ap = shortest_attack_path(G, source, target)
                if ap.get("found") and ap.get("hop_count", 0) > 0:
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
    from app.services.history_service import record_analysis_run
    from app.config import settings
 
    record_analysis_run(
    cluster_name  = settings.CLUSTER_NAME,
    source        = "mock" if settings.MOCK_MODE else "kubectl",
    attack_paths  = 1 if (attack_path and attack_path.get("found")) else 0,
    cycles        = cycles.get("cycle_count", 0),
    has_ai_report = False,
    triggered_by  = "analysis",
)

    # NEW: Add remediations to attack path
    if attack_path and attack_path.get("found"):
        path_rems = analyze_attack_path_for_remediation(attack_path)
        cycle_rems = analyze_cycles_for_remediation(cycles)
        all_rems = path_rems + cycle_rems
        # Deduplicate and sort
        seen_titles = set()
        unique_rems = []
        for r in sorted(all_rems, key=lambda x: (-x.impact_count, x.difficulty != "low")):
            if r.title not in seen_titles:
                seen_titles.add(r.title)
                unique_rems.append(r)
        attack_path["remediations"] = [r.to_dict() for r in unique_rems[:5]]

    # NEW: Calculate threat score
    analysis_result = {
        "attack_path":    attack_path,
        "blast_radius":   blast,
        "cycles":         cycles,
        "critical_nodes": critical,
    }

    threat_score_result = calculate_threat_score(analysis_result)
    analysis_result["threat_score"] = threat_score_result

    return analysis_result
