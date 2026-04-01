"""
dfs_cycles.py — Privilege Escalation Loop Detection
Uses Depth-First Search to detect cycles in the access graph.
A cycle means an attacker can escalate privileges in a loop —
gaining more permissions each time around.
"""

import networkx as nx


def detect_cycles(G: nx.DiGraph) -> dict:
    """
    Detect all privilege escalation cycles in the graph using DFS.

    A cycle like:
        RoleA → ServiceAccount-X → RoleB → ServiceAccount-X
    means ServiceAccount-X can continuously escalate its own permissions.

    Returns:
        {
            "cycle_count": 2,
            "cycles": [
                {
                    "id": 0,
                    "length": 3,
                    "nodes": ["sa-backend", "role-admin", "secret-master"],
                    "node_details": [...],
                    "severity": "critical",
                    "description": "Privilege escalation loop of length 3"
                },
                ...
            ]
        }
    """
    raw_cycles = list(nx.simple_cycles(G))

    if not raw_cycles:
        return {
            "cycle_count": 0,
            "cycles": [],
            "message": "No privilege escalation loops detected.",
        }

    cycles = []
    for idx, cycle in enumerate(raw_cycles):
        node_details = []
        for node_id in cycle:
            node_data = G.nodes[node_id]
            node_details.append({
                "id": node_id,
                "label": node_data.get("label", node_id),
                "type": node_data.get("type", "unknown"),
                "risk": node_data.get("risk", 0.0),
                "namespace": node_data.get("namespace", "default"),
            })

        # Severity based on cycle length and max node risk
        max_risk = max(n["risk"] for n in node_details)
        severity = _classify_severity(len(cycle), max_risk)

        # Build readable chain e.g. "sa-backend → role-admin → secret-master → sa-backend"
        labels = [G.nodes[n].get("label", n) for n in cycle]
        chain = " → ".join(labels) + f" → {labels[0]}"

        cycles.append({
            "id": idx,
            "length": len(cycle),
            "nodes": cycle,
            "node_details": node_details,
            "severity": severity,
            "max_risk": max_risk,
            "chain": chain,
            "description": f"Privilege escalation loop of length {len(cycle)}",
        })

    # Sort by severity then by max_risk
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    cycles.sort(key=lambda x: (severity_order[x["severity"]], -x["max_risk"]))

    return {
        "cycle_count": len(cycles),
        "cycles": cycles,
    }


def _classify_severity(cycle_length: int, max_risk: float) -> str:
    """
    Classify a cycle's severity based on its length and the
    highest risk score among its nodes.
    Short cycles with high-risk nodes are the most dangerous.
    """
    if max_risk >= 8.0 or cycle_length <= 2:
        return "critical"
    elif max_risk >= 6.0 or cycle_length <= 4:
        return "high"
    elif max_risk >= 4.0:
        return "medium"
    else:
        return "low"


def nodes_in_any_cycle(G: nx.DiGraph) -> set:
    """
    Returns the set of all node IDs that participate in at least one cycle.
    Used by the frontend to highlight these nodes in the graph.
    """
    result = detect_cycles(G)
    involved = set()
    for cycle in result["cycles"]:
        involved.update(cycle["nodes"])
    return involved


def cycles_involving_node(G: nx.DiGraph, node_id: str) -> list:
    """
    Returns all cycles that pass through a specific node.
    Used when a judge/user clicks a node and asks "is this in a loop?"
    """
    result = detect_cycles(G)
    return [c for c in result["cycles"] if node_id in c["nodes"]]


def cycles_summary(result: dict) -> str:
    """
    Human-readable summary of cycle detection.
    Used by narrator_service to feed into AI prompt.
    """
    if result["cycle_count"] == 0:
        return "No privilege escalation loops detected."

    lines = [f"Detected {result['cycle_count']} privilege escalation loop(s):"]
    for cycle in result["cycles"]:
        lines.append(
            f"  [{cycle['severity'].upper()}] {cycle['chain']}  "
            f"(length={cycle['length']}, max_risk={cycle['max_risk']})"
        )
    return "\n".join(lines)
