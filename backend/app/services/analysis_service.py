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
from app.services.cve_service import get_cve_score_for_image

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


def enrich_nodes_with_cves(G=None) -> int:
    """
    Post-process the graph to add CVE scores to Pod nodes.
    Stores per-image CVSS scores, container images list, and aggregate score.
    Returns the number of pods enriched.
    """
    if G is None:
        G = get_graph()

    count = 0
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("type") != "pod":
            continue

        images = attrs.get("metadata", {}).get("image", [])
        if not images:
            continue

        # Get per-image CVSS scores
        cvss_scores: dict = {}
        max_cve_score = 0.0
        for img in images:
            score = get_cve_score_for_image(img)
            cvss_scores[img] = score
            if score > max_cve_score:
                max_cve_score = score

        if max_cve_score > 0:
            old_risk = attrs.get("risk", 0.0)
            new_risk = min(10.0, old_risk + (max_cve_score * 0.2))

            G.nodes[node_id]["risk"] = round(new_risk, 1)
            G.nodes[node_id]["metadata"]["cve_score"] = max_cve_score
            G.nodes[node_id]["metadata"]["cvss_scores"] = cvss_scores
            G.nodes[node_id]["metadata"]["container_images"] = list(images)
            count += 1

    if count:
        logger.info("Enriched %d Pod nodes with live CVE scores", count)
    return count


def get_pod_image_cvss_data(pod_id: str) -> dict | None:
    """
    Return detailed CVE/CVSS data for a specific Pod node.
    Used by the /api/cves/images/{pod_id} endpoint.
    """
    G = get_graph()
    if pod_id not in G.nodes:
        return None

    attrs = G.nodes[pod_id]
    if attrs.get("type") != "pod":
        return None

    images = attrs.get("metadata", {}).get("image", [])
    if not images:
        images = []

    cvss_scores = attrs.get("metadata", {}).get("cvss_scores", {})
    image_data = []
    for img in images:
        score = cvss_scores.get(img)
        if score is None:
            score = get_cve_score_for_image(img)
            cvss_scores[img] = score
            G.nodes[pod_id]["metadata"]["cvss_scores"] = cvss_scores

        image_data.append({
            "image": img,
            "cvss_score": score,
            "severity": _score_to_severity(score),
            "source": "nist_nvd" if score > 0 else "not_found",
        })

    aggregate_risk = max((d["cvss_score"] for d in image_data), default=0.0)
    from app.utils.helpers import utc_now
    return {
        "pod_id": pod_id,
        "pod_label": attrs.get("label", pod_id),
        "images": image_data,
        "aggregate_risk": aggregate_risk,
        "aggregate_severity": _score_to_severity(aggregate_risk),
        "timestamp": utc_now(),
    }


def refresh_all_pod_cvss(G=None) -> dict:
    """
    Force-refresh CVSS scores for all Pod nodes by clearing cache and re-enriching.
    Returns a summary of what was updated.
    """
    if G is None:
        G = get_graph()

    # Clear existing CVE metadata so scores are re-fetched
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("type") == "pod":
            md = attrs.get("metadata", {})
            md.pop("cve_score", None)
            md.pop("cvss_scores", None)

    pods_updated = enrich_nodes_with_cves(G)
    from app.utils.helpers import utc_now
    return {
        "status": "completed",
        "pods_updated": pods_updated,
        "timestamp": utc_now(),
    }


def _score_to_severity(score: float) -> str:
    if score >= 9.0:
        return "critical"
    elif score >= 7.0:
        return "high"
    elif score >= 4.0:
        return "medium"
    elif score > 0.0:
        return "low"
    return "none"


def get_full_analysis() -> dict:
    """
    Run all four algorithms in one call and return a combined report dict.
    This is what narrator_service.py consumes to build the AI prompt.
    Called internally — not directly exposed as a route.
    """
    G = get_graph()
    enrich_nodes_with_cves(G)

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
