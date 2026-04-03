"""
threat_score_service.py — Overall Cluster Threat Model Scoring
Aggregates findings from all algorithms into a 1-10 business-friendly risk score.
"""

from app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_threat_score(analysis_result: dict) -> dict:
    """
    Calculate a 1-10 overall threat/risk score for the cluster.
    Factors:
    - Number and length of attack paths (longer = lower risk)
    - Presence of privilege escalation cycles (high weight)
    - Number of critical nodes (junction points)
    - CVE counts
    """

    attack_path = analysis_result.get("attack_path") or {}
    cycles = analysis_result.get("cycles") or {}
    critical_nodes = analysis_result.get("critical_nodes") or {}
    blast_radius = analysis_result.get("blast_radius") or {}

    score = 5.0  # Baseline: neutral risk

    # Factor 1: Attack paths (short = high risk)
    if attack_path.get("found"):
        hop_count = attack_path.get("hop_count", 999)
        # 1-hop = +3 risk, 2-hop = +2, 3-hop = +1, 4+ = +0.5
        if hop_count == 1:
            score += 3.0
        elif hop_count == 2:
            score += 2.0
        elif hop_count == 3:
            score += 1.0
        elif hop_count > 3:
            score += 0.5
    else:
        score -= 1.0  # Good: no obvious attack path

    # Factor 2: Privilege escalation cycles (very dangerous)
    cycle_count = cycles.get("cycle_count", 0)
    if cycle_count > 0:
        # Each cycle adds 1.5 to score
        cycle_contribution = min(cycle_count * 1.5, 3.0)  # Cap at +3
        score += cycle_contribution

    # Factor 3: Critical nodes (many junctions = higher attack density)
    critical_node_count = len(critical_nodes.get("nodes", []))
    if critical_node_count > 5:
        score += 1.5
    elif critical_node_count > 2:
        score += 0.8

    # Factor 4: Blast radius (many reachable = worse)
    total_reachable = blast_radius.get("total_reachable", 0)
    if total_reachable > 50:
        score += 1.5
    elif total_reachable > 20:
        score += 1.0
    elif total_reachable > 10:
        score += 0.5

    # Clamp to 1-10 range
    score = max(1.0, min(10.0, score))

    # Risk level labels
    if score >= 9:
        risk_level = "critical"
        description = "IMMEDIATE ACTION REQUIRED: Multiple attack paths and privilege escalation found"
    elif score >= 7:
        risk_level = "high"
        description = "High risk: Significant attack paths present; urgent remediation needed"
    elif score >= 5:
        risk_level = "medium"
        description = "Medium risk: Some attack paths exist; address within 2 weeks"
    elif score >= 3:
        risk_level = "low"
        description = "Low risk: Limited direct attack paths; standard hardening recommended"
    else:
        risk_level = "minimal"
        description = "Minimal risk: Well-segmented cluster; maintain current posture"

    return {
        "threat_score": round(score * 2) / 2,  # Round to nearest 0.5
        "risk_level": risk_level,
        "description": description,
        "factors": {
            "attack_paths": attack_path.get("found", False),
            "shortest_path_hops": attack_path.get("hop_count"),
            "privilege_escalation_cycles": cycle_count,
            "critical_node_junctions": critical_node_count,
            "blast_radius_size": total_reachable,
        },
        "benchmarks": {
            "example_safe_cluster": 1.2,
            "example_typical_cluster": 5.0,
            "example_vulnerable_cluster": 8.5,
        },
    }


def score_trend_from_history(history_runs: list) -> dict:
    """
    If there are multiple analysis runs in history, calculate trend.
    """
    if len(history_runs) < 2:
        return {"trend": "insufficient_data", "score_delta": None}

    latest = history_runs[-1]
    previous = history_runs[-2]

    latest_score = latest.get("threat_score", 5.0)
    previous_score = previous.get("threat_score", 5.0)
    delta = latest_score - previous_score

    if delta < -1:
        trend = "improving"
    elif delta > 1:
        trend = "worsening"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "score_delta": round(delta * 2) / 2,
        "previous_score": previous_score,
        "latest_score": latest_score,
    }
