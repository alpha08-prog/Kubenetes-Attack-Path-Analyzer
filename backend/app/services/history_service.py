"""
history_service.py — Risk Score History Service
Records every analysis run to SQLite and queries trends over time.

Key insight for judges:
    "Your risk score increased 23% after the last deployment —
     admin-role was added 2 hours ago and created 3 new attack paths."
"""

import uuid
from app.core.database import get_conn
from app.core.graph_builder import get_graph
from app.utils.helpers import severity_label, utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Record a new analysis run ─────────────────────────────────────────────────

def record_analysis_run(
    cluster_name:   str,
    source:         str = "mock",
    attack_paths:   int = 0,
    cycles:         int = 0,
    has_ai_report:  bool = False,
    triggered_by:   str = "manual",
    findings:       list = None,
) -> str:
    """
    Save a full analysis run snapshot to SQLite.
    Returns the run_id for reference.

    Called by:
        - routes_report.py after generating AI report
        - routes_attack.py after finding an attack path
        - analysis_service.get_full_analysis()
    """
    run_id = str(uuid.uuid4())[:8]     # short readable ID e.g. "a3f9b2c1"
    now    = utc_now()

    try:
        G = get_graph()
    except RuntimeError:
        logger.warning("Cannot record run — graph not loaded")
        return run_id

    # Compute overall risk stats from current graph
    all_risks      = [G.nodes[n].get("risk", 0.0) for n in G.nodes]
    overall_risk   = round(sum(all_risks) / len(all_risks), 2) if all_risks else 0.0
    critical_count = sum(1 for r in all_risks if r >= 9.0)
    high_count     = sum(1 for r in all_risks if 7.0 <= r < 9.0)

    # Skip recording if the graph state is identical to the most recent run.
    # Return the EXISTING run_id so watch_decision_engine detects the skip via
    # its `new_run_id == previous_run_id` guard and exits cleanly.
    with get_conn() as conn:
        prev = conn.execute(
            """
            SELECT run_id, overall_risk, node_count, edge_count, attack_paths, cycles
            FROM analysis_runs
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()

    if prev and (
        abs(prev["overall_risk"] - overall_risk) < 0.01
        and prev["node_count"] == G.number_of_nodes()
        and prev["edge_count"] == G.number_of_edges()
        and prev["attack_paths"] == attack_paths
        and prev["cycles"] == cycles
    ):
        logger.info(
            "Analysis run skipped — identical to previous (risk=%.1f paths=%d cycles=%d)",
            overall_risk, attack_paths, cycles,
        )
        return prev["run_id"]  # existing ID, not in doubt — caller will skip diff

    with get_conn() as conn:

        # Insert the run summary
        conn.execute("""
            INSERT INTO analysis_runs
                (run_id, cluster_name, source, node_count, edge_count,
                 overall_risk, critical_nodes, high_nodes,
                 attack_paths, cycles, has_ai_report, triggered_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_id, cluster_name, source,
            G.number_of_nodes(), G.number_of_edges(),
            overall_risk, critical_count, high_count,
            attack_paths, cycles,
            1 if has_ai_report else 0,
            triggered_by, now,
        ))

        # Insert node-level risk snapshot
        for node_id, attrs in G.nodes(data=True):
            risk = attrs.get("risk", 0.0)
            conn.execute("""
                INSERT INTO risk_snapshots
                    (run_id, node_id, node_label, node_type,
                     namespace, risk_score, severity, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                run_id,
                node_id,
                attrs.get("label", node_id),
                attrs.get("type", "unknown"),
                attrs.get("namespace", "default"),
                risk,
                severity_label(risk),
                now,
            ))

        # Insert edge-level snapshot
        for u, v, attrs in G.edges(data=True):
            conn.execute("""
                INSERT INTO edge_snapshots
                    (run_id, source_id, target_id, relation, risk_score, created_at)
                VALUES (?,?,?,?,?,?)
            """, (
                run_id,
                u,
                v,
                attrs.get("relation", "accesses"),
                attrs.get("risk", 5.0),
                now,
            ))

        # Insert individual findings if provided
        if findings:
            for f in findings:
                conn.execute("""
                    INSERT INTO findings_log
                        (run_id, finding_id, severity, category,
                         title, kill_chain, recommendation, effort, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    run_id,
                    f.get("id", ""),
                    f.get("severity", ""),
                    f.get("category", ""),
                    f.get("title", ""),
                    f.get("kill_chain"),
                    f.get("recommendation", ""),
                    f.get("effort", ""),
                    now,
                ))

    logger.info(
        "Recorded run %s — risk=%.1f critical=%d high=%d paths=%d cycles=%d",
        run_id, overall_risk, critical_count, high_count, attack_paths, cycles,
    )
    return run_id


# ── Query functions ───────────────────────────────────────────────────────────

def get_run_history(limit: int = 20, cluster_name: str = None) -> list:
    """
    Return the N most recent analysis runs, newest first.
    Used by the risk trend chart on the frontend.
    """
    with get_conn() as conn:
        if cluster_name:
            rows = conn.execute("""
                SELECT * FROM analysis_runs
                WHERE cluster_name = ?
                ORDER BY created_at DESC LIMIT ?
            """, (cluster_name, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM analysis_runs
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_risk_trend(limit: int = 10, cluster_name: str = None) -> dict:
    """
    Returns the overall_risk time series for the trend chart.
    Also computes delta vs the previous run so you can say
    "risk increased 23% since last deployment."
    """
    runs = get_run_history(limit=limit, cluster_name=cluster_name)

    if not runs:
        return {
            "trend":          [],
            "latest_risk":    None,
            "delta":          None,
            "delta_pct":      None,
            "trend_direction": "stable",
        }

    # Reverse so chart goes oldest → newest
    trend = [
        {
            "run_id":       r["run_id"],
            "overall_risk": r["overall_risk"],
            "critical":     r["critical_nodes"],
            "high":         r["high_nodes"],
            "attack_paths": r["attack_paths"],
            "cycles":       r["cycles"],
            "created_at":   r["created_at"],
        }
        for r in reversed(runs)
    ]

    latest_risk = trend[-1]["overall_risk"]
    prev_risk   = trend[-2]["overall_risk"] if len(trend) >= 2 else None

    delta     = round(latest_risk - prev_risk, 2) if prev_risk is not None else None
    delta_pct = round((delta / prev_risk) * 100, 1) if (prev_risk and prev_risk > 0) else None

    if delta is None:
        direction = "stable"
    elif delta > 0.5:
        direction = "increasing"
    elif delta < -0.5:
        direction = "decreasing"
    else:
        direction = "stable"

    return {
        "trend":           trend,
        "latest_risk":     latest_risk,
        "prev_risk":       prev_risk,
        "delta":           delta,
        "delta_pct":       delta_pct,
        "trend_direction": direction,
        "run_count":       len(trend),
    }


def get_run_detail(run_id: str) -> dict | None:
    """Full detail for a single run including node snapshots and findings."""
    with get_conn() as conn:
        run = conn.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)
        ).fetchone()

        if not run:
            return None

        snapshots = conn.execute("""
            SELECT * FROM risk_snapshots
            WHERE run_id = ?
            ORDER BY risk_score DESC
        """, (run_id,)).fetchall()

        findings = conn.execute("""
            SELECT * FROM findings_log
            WHERE run_id = ?
            ORDER BY CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                ELSE 4 END
        """, (run_id,)).fetchall()

    return {
        "run":       dict(run),
        "snapshots": [dict(s) for s in snapshots],
        "findings":  [dict(f) for f in findings],
    }


def get_riskiest_nodes_over_time(node_type: str = None, limit: int = 10) -> list:
    """
    Returns nodes that have been consistently high-risk across runs.
    Useful for "persistent risk hotspot" analysis.
    """
    with get_conn() as conn:
        if node_type:
            rows = conn.execute("""
                SELECT
                    node_id, node_label, node_type,
                    COUNT(*)        AS appearance_count,
                    AVG(risk_score) AS avg_risk,
                    MAX(risk_score) AS max_risk,
                    MIN(risk_score) AS min_risk
                FROM risk_snapshots
                WHERE node_type = ?
                GROUP BY node_id
                HAVING AVG(risk_score) >= 7.0
                ORDER BY avg_risk DESC
                LIMIT ?
            """, (node_type, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    node_id, node_label, node_type,
                    COUNT(*)        AS appearance_count,
                    AVG(risk_score) AS avg_risk,
                    MAX(risk_score) AS max_risk,
                    MIN(risk_score) AS min_risk
                FROM risk_snapshots
                GROUP BY node_id
                HAVING AVG(risk_score) >= 7.0
                ORDER BY avg_risk DESC
                LIMIT ?
            """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_stats_summary() -> dict:
    """
    High-level stats across all runs.
    Used by the history dashboard header.
    """
    with get_conn() as conn:
        totals = conn.execute("""
            SELECT
                COUNT(*)        AS total_runs,
                AVG(overall_risk) AS avg_risk_all_time,
                MAX(overall_risk) AS peak_risk,
                MIN(overall_risk) AS lowest_risk,
                SUM(attack_paths) AS total_paths_found,
                SUM(cycles)       AS total_cycles_found
            FROM analysis_runs
        """).fetchone()

        most_common_finding = conn.execute("""
            SELECT title, COUNT(*) AS cnt
            FROM findings_log
            GROUP BY title
            ORDER BY cnt DESC
            LIMIT 1
        """).fetchone()

    return {
        "total_runs":          totals["total_runs"] or 0,
        "avg_risk_all_time":   round(totals["avg_risk_all_time"] or 0, 2),
        "peak_risk":           totals["peak_risk"] or 0,
        "lowest_risk":         totals["lowest_risk"] or 0,
        "total_paths_found":   totals["total_paths_found"] or 0,
        "total_cycles_found":  totals["total_cycles_found"] or 0,
        "most_common_finding": dict(most_common_finding) if most_common_finding else None,
    }


def delete_run(run_id: str) -> bool:
    """Delete a specific run and its associated data."""
    with get_conn() as conn:
        conn.execute("DELETE FROM risk_snapshots WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM findings_log   WHERE run_id = ?", (run_id,))
        result = conn.execute(
            "DELETE FROM analysis_runs WHERE run_id = ?", (run_id,)
        )
    return result.rowcount > 0