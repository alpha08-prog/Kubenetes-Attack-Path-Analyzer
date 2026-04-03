"""
attack_service.py â€” Shortest Attack Path Service
Orchestrates the Dijkstra algorithm and enriches the result
with severity labels and frontend-ready formatting.
"""

from app.config import settings
from app.algorithm.dijkstra import shortest_attack_path, all_attack_paths
from app.core.graph_builder import get_graph, find_entry_points, find_sensitive_targets
from app.utils.helpers import severity_label, timed
from app.utils.logger import get_logger, log_algorithm_run
from app.services.remediation_service import analyze_attack_path_for_remediation

logger = get_logger(__name__)


@timed
def get_attack_path(source: str, target: str) -> dict:
    """
    Find the shortest (easiest) attack path from source to target.
    Called by routes_attack.py.
    """
    G = get_graph()
    result = shortest_attack_path(G, source, target)

    log_algorithm_run(
        "dijkstra",
        {"source": source, "target": target},
        f"found={result.get('found')} hops={result.get('hop_count')}",
    )

    if not result.get("found"):
        return result

    # Enrich each hop with severity label
    for hop in result.get("hops", []):
        hop["severity"] = severity_label(hop["edge_risk"])

    # Overall path severity = worst single hop
    max_risk = max((h["edge_risk"] for h in result.get("hops", [])), default=0.0)
    result["severity"] = severity_label(max_risk)

    # NEW: Add remediation suggestions
    remediations = analyze_attack_path_for_remediation(result)
    result["remediations"] = [r.to_dict() for r in remediations]

    if result.get("found"):
        from app.services.slack_service import send_attack_path_alert
        send_attack_path_alert(result, cluster_name=settings.CLUSTER_NAME)

    return result


@timed
def get_all_attack_paths(source: str, target: str, max_paths: int = 5) -> dict:
    """
    Return up to max_paths routes from source to target.
    Shows judges that attackers have multiple options.
    """
    G = get_graph()
    paths = all_attack_paths(G, source, target, max_paths=max_paths)

    log_algorithm_run(
        "dijkstra_all_paths",
        {"source": source, "target": target},
        f"found {len(paths)} paths",
    )

    return {
        "source":    source,
        "target":    target,
        "paths":     paths,
        "count":     len(paths),
    }


def get_auto_attack_path() -> dict:
    """
    Auto-detect the most dangerous source â†’ target pair and run Dijkstra.
    Used by DemoMode.jsx â€” one click, no manual node selection needed.
    """
    G = get_graph()
    entries  = find_entry_points(G)
    targets  = find_sensitive_targets(G)

    if not entries or not targets:
        return {
            "found":   False,
            "message": "Could not auto-detect entry points or sensitive targets.",
        }

    # Try pairs until we find a path, starting from highest-risk entry
    entries_sorted = sorted(entries, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)
    targets_sorted = sorted(targets, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)

    for source in entries_sorted:
        for target in targets_sorted:
            if source == target:
                continue
            result = shortest_attack_path(G, source, target)
            if result.get("found") and result.get("hop_count", 0) > 0:
                result["auto_detected"] = True
                logger.info("Auto-detected path: %s â†’ %s", source, target)
                return result

    return {
        "found":   False,
        "message": "No attack path found between any entry point and sensitive target.",
    }
