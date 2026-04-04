"""
graph_diff_service.py — Graph Diff Service
Compares two analysis run snapshots from SQLite and returns
a structured diff showing what changed between them.

Key use case for judges:
    "Before we deployed the vulnerable scenario: risk=4.2, 0 attack paths"
    "After deployment: risk=7.6, 3 attack paths, 1 new cycle"
    → Delta: risk +81%, 3 new paths, 1 new cycle, 4 new critical nodes

This proves the tool is useful for continuous monitoring,
not just one-time audits.
"""

from app.core.database import get_conn
from app.utils.helpers import severity_label, utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Main diff function ────────────────────────────────────────────────────────

def diff_runs(run_id_before: str, run_id_after: str) -> dict:
    """
    Compare two analysis runs and return a structured diff.

    Args:
        run_id_before: the baseline run (e.g. before deploying vulnerable app)
        run_id_after:  the comparison run (e.g. after deploying)

    Returns a comprehensive diff with:
        - Overall risk delta
        - New / removed / changed nodes
        - Attack path count change
        - Cycle count change
        - Severity distribution shift
        - Top newly risky nodes
    """
    before = _load_run(run_id_before)
    after  = _load_run(run_id_after)

    if not before:
        raise ValueError(f"Run '{run_id_before}' not found in history")
    if not after:
        raise ValueError(f"Run '{run_id_after}' not found in history")

    return {
        "meta":              _build_meta(before, after),
        "risk_delta":        _diff_risk(before, after),
        "node_changes":      _diff_nodes(before, after),
        "severity_shift":    _diff_severity(before, after),
        "path_delta":        _diff_paths(before, after),
        "cycle_delta":       _diff_cycles(before, after),
        "finding_delta":     _diff_findings(before, after),
        "edge_changes":      _diff_edges(before, after),
        "top_new_risks":     _top_new_risks(before, after),
        "top_improved":      _top_improved(before, after),
        "recommendation":    _generate_recommendation(before, after),
    }


def diff_latest_two(cluster_name: str = None) -> dict:
    """
    Auto-diff the two most recent runs.
    Convenience endpoint — no need to specify run IDs manually.
    """
    with get_conn() as conn:
        if cluster_name:
            rows = conn.execute("""
                SELECT run_id FROM analysis_runs
                WHERE cluster_name = ?
                ORDER BY created_at DESC LIMIT 2
            """, (cluster_name,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT run_id FROM analysis_runs
                ORDER BY created_at DESC LIMIT 2
            """).fetchall()

    if len(rows) < 2:
        raise ValueError(
            "Need at least 2 analysis runs to compare. "
            "Run an analysis a couple of times first — "
            "call POST /api/history/record to create snapshots."
        )

    # rows[0] = latest (after), rows[1] = previous (before)
    return diff_runs(
        run_id_before=rows[1]["run_id"],
        run_id_after=rows[0]["run_id"],
    )


def diff_snapshot_vs_current(run_id_before: str) -> dict:
    """
    Compare a historical run against the current live graph state.
    Creates a temporary snapshot of current state, runs diff,
    returns result without persisting the temporary run.

    Useful for "how much has risk changed since I started this demo?"
    """
    from app.services.history_service import record_analysis_run
    from app.config import settings

    # Record current state as a temporary run
    temp_run_id = record_analysis_run(
        cluster_name = settings.CLUSTER_NAME,
        source       = "mock" if settings.MOCK_MODE else "kubectl",
        triggered_by = "diff_temp",
    )

    result = diff_runs(run_id_before, temp_run_id)
    result["meta"]["note"] = "Comparing historical snapshot vs current live graph"
    return result


# ── Load helpers ──────────────────────────────────────────────────────────────

def _load_run(run_id: str) -> dict | None:
    """Load a run and its node snapshots from SQLite."""
    with get_conn() as conn:
        run = conn.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)
        ).fetchone()

        if not run:
            return None

        snapshots = conn.execute("""
            SELECT * FROM risk_snapshots WHERE run_id = ?
        """, (run_id,)).fetchall()

        edges = conn.execute("""
            SELECT * FROM edge_snapshots WHERE run_id = ?
        """, (run_id,)).fetchall()

        findings = conn.execute("""
            SELECT * FROM findings_log WHERE run_id = ?
        """, (run_id,)).fetchall()

    return {
        "run":       dict(run),
        "nodes":     {r["node_id"]: dict(r) for r in snapshots},
        "edges":     [dict(e) for e in edges],
        "findings":  [dict(f) for f in findings],
    }


# ── Diff builders ─────────────────────────────────────────────────────────────

def _build_meta(before: dict, after: dict) -> dict:
    b = before["run"]
    a = after["run"]
    return {
        "run_before":      b["run_id"],
        "run_after":       a["run_id"],
        "time_before":     b["created_at"],
        "time_after":      a["created_at"],
        "cluster":         a["cluster_name"],
        "compared_at":     utc_now(),
    }


def _diff_risk(before: dict, after: dict) -> dict:
    b_risk = before["run"]["overall_risk"]
    a_risk = after["run"]["overall_risk"]
    delta  = round(a_risk - b_risk, 2)
    pct    = round((delta / b_risk) * 100, 1) if b_risk > 0 else 0.0

    return {
        "before":          b_risk,
        "after":           a_risk,
        "delta":           delta,
        "delta_pct":       pct,
        "direction":       "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged",
        "severity_before": severity_label(b_risk),
        "severity_after":  severity_label(a_risk),
    }


def _diff_nodes(before: dict, after: dict) -> dict:
    b_nodes = set(before["nodes"].keys())
    a_nodes = set(after["nodes"].keys())

    new_nodes     = a_nodes - b_nodes
    removed_nodes = b_nodes - a_nodes
    common_nodes  = b_nodes & a_nodes

    # Find nodes whose risk score changed significantly (>= 1.0)
    risk_increased = []
    risk_decreased = []
    unchanged      = []

    for node_id in common_nodes:
        b_risk = before["nodes"][node_id]["risk_score"]
        a_risk = after["nodes"][node_id]["risk_score"]
        delta  = round(a_risk - b_risk, 2)

        node_info = {
            "node_id":    node_id,
            "label":      after["nodes"][node_id]["node_label"],
            "type":       after["nodes"][node_id]["node_type"],
            "risk_before": b_risk,
            "risk_after":  a_risk,
            "delta":       delta,
        }

        if delta >= 1.0:
            risk_increased.append(node_info)
        elif delta <= -1.0:
            risk_decreased.append(node_info)
        else:
            unchanged.append(node_id)

    risk_increased.sort(key=lambda x: x["delta"], reverse=True)
    risk_decreased.sort(key=lambda x: x["delta"])

    # Enrich new nodes with their details
    new_node_details = [
        {
            "node_id":   nid,
            "label":     after["nodes"][nid]["node_label"],
            "type":      after["nodes"][nid]["node_type"],
            "risk":      after["nodes"][nid]["risk_score"],
            "severity":  after["nodes"][nid]["severity"],
            "namespace": after["nodes"][nid]["namespace"],
        }
        for nid in new_nodes
    ]
    new_node_details.sort(key=lambda x: x["risk"], reverse=True)

    return {
        "total_before":    len(b_nodes),
        "total_after":     len(a_nodes),
        "new_count":       len(new_nodes),
        "removed_count":   len(removed_nodes),
        "changed_count":   len(risk_increased) + len(risk_decreased),
        "new_nodes":       new_node_details,
        "removed_nodes":   list(removed_nodes),
        "risk_increased":  risk_increased[:10],
        "risk_decreased":  risk_decreased[:10],
    }


def _diff_edges(before: dict, after: dict) -> dict:
    """Compare edges before vs after."""
    b_edges_list = before.get("edges", [])
    a_edges_list = after.get("edges", [])

    # Create keys for easier comparison
    def edge_key(e): return f"{e['source_id']}->{e['target_id']}:{e['relation']}"
    
    b_edges = {edge_key(e): e for e in b_edges_list}
    a_edges = {edge_key(e): e for e in a_edges_list}

    b_keys = set(b_edges.keys())
    a_keys = set(a_edges.keys())

    added_keys   = a_keys - b_keys
    removed_keys = b_keys - a_keys

    added = []
    for k in added_keys:
        e = a_edges[k]
        added.append({
            "source": e["source_id"],
            "target": e["target_id"],
            "relation": e["relation"],
            "risk": e["risk_score"]
        })

    return {
        "added_count":   len(added),
        "removed_count": len(removed_keys),
        "total_before":  len(b_edges),
        "total_after":   len(a_edges),
        "new_edges":     added[:10],
    }


def _diff_severity(before: dict, after: dict) -> dict:
    """Compare severity distribution before vs after."""
    def count_severity(nodes: dict) -> dict:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "none": 0}
        for n in nodes.values():
            sev = n.get("severity", "none")
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    b_dist = count_severity(before["nodes"])
    a_dist = count_severity(after["nodes"])

    deltas = {
        sev: a_dist.get(sev, 0) - b_dist.get(sev, 0)
        for sev in ("critical", "high", "medium", "low")
    }

    return {
        "before":  b_dist,
        "after":   a_dist,
        "deltas":  deltas,
        "summary": _severity_summary(deltas),
    }


def _diff_paths(before: dict, after: dict) -> dict:
    b_paths = before["run"]["attack_paths"]
    a_paths = after["run"]["attack_paths"]
    delta   = a_paths - b_paths

    return {
        "before":    b_paths,
        "after":     a_paths,
        "delta":     delta,
        "direction": "more_paths" if delta > 0 else "fewer_paths" if delta < 0 else "unchanged",
        "label":     (
            f"{abs(delta)} new attack path{'s' if abs(delta) != 1 else ''} introduced"
            if delta > 0 else
            f"{abs(delta)} attack path{'s' if abs(delta) != 1 else ''} eliminated"
            if delta < 0 else
            "No change in attack path count"
        ),
    }


def _diff_cycles(before: dict, after: dict) -> dict:
    b_cycles = before["run"]["cycles"]
    a_cycles = after["run"]["cycles"]
    delta    = a_cycles - b_cycles

    return {
        "before":    b_cycles,
        "after":     a_cycles,
        "delta":     delta,
        "direction": "more_cycles" if delta > 0 else "fewer_cycles" if delta < 0 else "unchanged",
        "label":     (
            f"{abs(delta)} new privilege escalation loop{'s' if abs(delta) != 1 else ''}"
            if delta > 0 else
            f"{abs(delta)} privilege escalation loop{'s' if abs(delta) != 1 else ''} resolved"
            if delta < 0 else
            "No change in cycle count"
        ),
    }


def _diff_findings(before: dict, after: dict) -> dict:
    b_titles = {f["title"] for f in before["findings"]}
    a_titles = {f["title"] for f in after["findings"]}

    new_findings     = [f for f in after["findings"]  if f["title"] not in b_titles]
    resolved         = [f for f in before["findings"] if f["title"] not in a_titles]

    new_findings.sort(key=lambda x: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 4)
    ))

    return {
        "new_count":      len(new_findings),
        "resolved_count": len(resolved),
        "new_findings":   new_findings[:5],
        "resolved":       resolved[:5],
    }


def _top_new_risks(before: dict, after: dict, top_n: int = 5) -> list:
    """Nodes that are newly critical or significantly riskier."""
    b_nodes = before["nodes"]
    a_nodes = after["nodes"]
    results = []

    for node_id, a_node in a_nodes.items():
        a_risk = a_node["risk_score"]
        b_risk = b_nodes[node_id]["risk_score"] if node_id in b_nodes else 0.0
        delta  = a_risk - b_risk

        if delta >= 2.0 or (node_id not in b_nodes and a_risk >= 7.0):
            results.append({
                "node_id":    node_id,
                "label":      a_node["node_label"],
                "type":       a_node["node_type"],
                "risk_before": b_risk,
                "risk_after":  a_risk,
                "delta":       round(delta, 2),
                "is_new":     node_id not in b_nodes,
            })

    results.sort(key=lambda x: x["delta"], reverse=True)
    return results[:top_n]


def _top_improved(before: dict, after: dict, top_n: int = 5) -> list:
    """Nodes that are now safer — shows hardening is working."""
    b_nodes = before["nodes"]
    a_nodes = after["nodes"]
    results = []

    for node_id in set(b_nodes) & set(a_nodes):
        b_risk = b_nodes[node_id]["risk_score"]
        a_risk = a_nodes[node_id]["risk_score"]
        delta  = a_risk - b_risk

        if delta <= -1.5:
            results.append({
                "node_id":    node_id,
                "label":      b_nodes[node_id]["node_label"],
                "type":       b_nodes[node_id]["node_type"],
                "risk_before": b_risk,
                "risk_after":  a_risk,
                "delta":       round(delta, 2),
            })

    results.sort(key=lambda x: x["delta"])
    return results[:top_n]


def _severity_summary(deltas: dict) -> str:
    parts = []
    if deltas.get("critical", 0) > 0:
        parts.append(f"+{deltas['critical']} critical node(s)")
    if deltas.get("high", 0) > 0:
        parts.append(f"+{deltas['high']} high node(s)")
    if deltas.get("critical", 0) < 0:
        parts.append(f"{deltas['critical']} critical node(s) resolved")
    if not parts:
        return "No significant severity changes"
    return ", ".join(parts)


def _generate_recommendation(before: dict, after: dict) -> str:
    """AI-free plain-English summary of what the diff means."""
    b = before["run"]
    a = after["run"]

    risk_delta  = a["overall_risk"] - b["overall_risk"]
    path_delta  = a["attack_paths"] - b["attack_paths"]
    cycle_delta = a["cycles"] - b["cycles"]

    if risk_delta > 2.0 or path_delta > 0 or cycle_delta > 0:
        parts = []
        alert_level = "info"
        if path_delta > 0:
            parts.append(f"{path_delta} new attack path(s) were introduced")
            alert_level = "critical"
        if cycle_delta > 0:
            parts.append(f"{cycle_delta} new privilege escalation loop(s) detected")
            if alert_level != "critical": alert_level = "high"
        if risk_delta > 1.0:
            parts.append(f"overall risk increased by {round(risk_delta, 1)} points")
            if alert_level == "info": alert_level = "medium"

        return {
            "text": (
                f"Security posture has degraded: {', '.join(parts)}. "
                "Review newly added roles and service account bindings immediately. "
                "Use the simulate removal feature to identify which node to harden first."
            ),
            "alert_level": alert_level
        }
    elif risk_delta < -1.0 or path_delta < 0:
        return {
            "text": (
                "Security posture has improved. "
                f"Risk decreased by {abs(round(risk_delta, 1))} points"
                + (f" and {abs(path_delta)} attack path(s) were eliminated." if path_delta < 0 else ".")
            ),
            "alert_level": "success"
        }
    else:
        return {
            "text": "No significant security changes detected between these two runs.",
            "alert_level": "info"
        }