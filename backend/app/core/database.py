"""
database.py — SQLite Database Setup
Single SQLite file for storing analysis history.
No external database needed — file lives at data/history.db

Tables:
    analysis_runs      — each time /api/report or any analysis is triggered
    risk_snapshots     — node-level risk scores per run
    findings_log       — individual findings per run (from AI narrator)
    monitoring_events  — events emitted by real-time K8s Watch monitoring
    monitoring_config  — per-cluster monitoring configuration
"""

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from app.utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = Path("data/history.db")


def init_db() -> None:
    """
    Create tables if they don't exist.
    Called once on app startup from main.py lifespan.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_conn() as conn:
        conn.executescript("""

        CREATE TABLE IF NOT EXISTS analysis_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT    NOT NULL UNIQUE,
            cluster_name    TEXT    NOT NULL,
            source          TEXT    NOT NULL,          -- mock | kubectl
            node_count      INTEGER NOT NULL,
            edge_count      INTEGER NOT NULL,
            overall_risk    REAL    NOT NULL,          -- avg risk across all nodes
            critical_nodes  INTEGER NOT NULL DEFAULT 0,
            high_nodes      INTEGER NOT NULL DEFAULT 0,
            attack_paths    INTEGER NOT NULL DEFAULT 0, -- number of paths found
            cycles          INTEGER NOT NULL DEFAULT 0,
            has_ai_report   INTEGER NOT NULL DEFAULT 0, -- 0|1
            triggered_by    TEXT    DEFAULT 'manual',   -- manual | auto | api
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS risk_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT    NOT NULL,
            node_id     TEXT    NOT NULL,
            node_label  TEXT    NOT NULL,
            node_type   TEXT    NOT NULL,
            namespace   TEXT    NOT NULL,
            risk_score  REAL    NOT NULL,
            severity    TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS edge_snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT    NOT NULL,
            source_id    TEXT    NOT NULL,
            target_id    TEXT    NOT NULL,
            relation     TEXT    NOT NULL,
            risk_score   REAL    NOT NULL,
            created_at   TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS findings_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         TEXT    NOT NULL,
            finding_id     TEXT    NOT NULL,
            severity       TEXT    NOT NULL,
            category       TEXT    NOT NULL,
            title          TEXT    NOT NULL,
            kill_chain     TEXT,
            recommendation TEXT,
            effort         TEXT,
            created_at     TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_runs_created    ON analysis_runs(created_at);
        CREATE INDEX IF NOT EXISTS idx_runs_cluster    ON analysis_runs(cluster_name);
        CREATE INDEX IF NOT EXISTS idx_snapshots_runid ON risk_snapshots(run_id);
        CREATE INDEX IF NOT EXISTS idx_findings_runid  ON findings_log(run_id);
        CREATE INDEX IF NOT EXISTS idx_findings_sev    ON findings_log(severity);

        -- ── Real-time monitoring tables ──────────────────────────────────────

        CREATE TABLE IF NOT EXISTS monitoring_events (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           TEXT    NOT NULL,
            event_type       TEXT    NOT NULL,   -- RESOURCE_ADDED|RISK_INCREASED|NEW_PATH|NEW_CYCLE
            resource_type    TEXT,               -- pod|role|rolebinding|secret
            resource_id      TEXT,
            severity         TEXT,               -- critical|high|medium|low
            summary          TEXT,
            details          TEXT,               -- JSON blob
            triggered_alerts TEXT,               -- comma-sep: "slack,websocket,history"
            created_at       TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS monitoring_config (
            cluster_name              TEXT    PRIMARY KEY,
            watching                  INTEGER NOT NULL DEFAULT 0,   -- 0|1
            watch_started_at          TEXT,
            watch_stopped_at          TEXT,
            alert_threshold_risk_delta REAL   NOT NULL DEFAULT 1.0,
            alert_on_new_paths        INTEGER NOT NULL DEFAULT 1,
            alert_on_new_cycles       INTEGER NOT NULL DEFAULT 1,
            created_at                TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_mon_events_run_id   ON monitoring_events(run_id);
        CREATE INDEX IF NOT EXISTS idx_mon_events_severity ON monitoring_events(severity);
        CREATE INDEX IF NOT EXISTS idx_mon_events_created  ON monitoring_events(created_at);

        -- ── B2: CVE image score cache ────────────────────────────────────────

        CREATE TABLE IF NOT EXISTS cve_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            image        TEXT    NOT NULL UNIQUE,
            cvss_score   REAL    NOT NULL DEFAULT 0.0,
            source       TEXT    NOT NULL DEFAULT 'nist_nvd',
            fetched_at   TEXT    NOT NULL,
            expires_at   TEXT    NOT NULL,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_cve_cache_image   ON cve_cache(image);
        CREATE INDEX IF NOT EXISTS idx_cve_cache_expires ON cve_cache(expires_at);

        -- ── B3: Temporal graph snapshots ─────────────────────────────────────

        CREATE TABLE IF NOT EXISTS graph_snapshots (
            snapshot_id      TEXT    PRIMARY KEY,
            cluster_name     TEXT    NOT NULL,
            timestamp        TEXT    NOT NULL,
            nodes_json       TEXT    NOT NULL,
            edges_json       TEXT    NOT NULL,
            node_count       INTEGER NOT NULL DEFAULT 0,
            edge_count       INTEGER NOT NULL DEFAULT 0,
            entry_points_json TEXT,
            sensitive_targets_json TEXT,
            cycles_detected  INTEGER NOT NULL DEFAULT 0,
            aggregate_risk   REAL    NOT NULL DEFAULT 0.0,
            trigger_source   TEXT    NOT NULL DEFAULT 'manual',
            trigger_desc     TEXT,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
            expires_at       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON graph_snapshots(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshots_cluster   ON graph_snapshots(cluster_name);

        -- ── B3: Snapshot diffs (cached comparisons) ──────────────────────────

        CREATE TABLE IF NOT EXISTS snapshot_diffs (
            diff_id              TEXT PRIMARY KEY,
            snapshot_id_before   TEXT NOT NULL,
            snapshot_id_after    TEXT NOT NULL,
            nodes_added          INTEGER NOT NULL DEFAULT 0,
            nodes_removed        INTEGER NOT NULL DEFAULT 0,
            edges_added          INTEGER NOT NULL DEFAULT 0,
            edges_removed        INTEGER NOT NULL DEFAULT 0,
            risk_delta           REAL    NOT NULL DEFAULT 0.0,
            new_attack_paths_count   INTEGER NOT NULL DEFAULT 0,
            new_paths_json       TEXT,
            disappeared_paths_count  INTEGER NOT NULL DEFAULT 0,
            new_cycles_count     INTEGER NOT NULL DEFAULT 0,
            disappeared_cycles_count INTEGER NOT NULL DEFAULT 0,
            severity             TEXT    NOT NULL DEFAULT 'low',
            alert_triggered      INTEGER NOT NULL DEFAULT 0,
            alert_reasons_json   TEXT,
            computed_at          TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (snapshot_id_before) REFERENCES graph_snapshots(snapshot_id),
            FOREIGN KEY (snapshot_id_after)  REFERENCES graph_snapshots(snapshot_id)
        );

        CREATE INDEX IF NOT EXISTS idx_diffs_after ON snapshot_diffs(snapshot_id_after);

        -- ── B3: Temporal alerts ───────────────────────────────────────────────

        CREATE TABLE IF NOT EXISTS temporal_alerts (
            alert_id         TEXT PRIMARY KEY,
            diff_id          TEXT,
            severity         TEXT NOT NULL DEFAULT 'low',
            title            TEXT NOT NULL,
            description      TEXT,
            new_paths_json   TEXT,
            new_cycles_json  TEXT,
            risk_delta       REAL NOT NULL DEFAULT 0.0,
            triggered_at     TEXT NOT NULL DEFAULT (datetime('now')),
            acknowledged_at  TEXT,
            FOREIGN KEY (diff_id) REFERENCES snapshot_diffs(diff_id)
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_severity  ON temporal_alerts(severity);
        CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON temporal_alerts(triggered_at DESC);

        """)

    logger.info("SQLite database initialised at %s", DB_PATH)


# ── Monitoring helper functions ───────────────────────────────────────────────

def record_monitoring_event(
    run_id: str,
    event_type: str,
    resource_type: str = None,
    resource_id: str = None,
    severity: str = None,
    summary: str = None,
    details: dict = None,
    triggered_alerts: list = None,
) -> None:
    """Record a monitoring event to the database."""
    from app.utils.helpers import utc_now
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO monitoring_events
                (run_id, event_type, resource_type, resource_id,
                 severity, summary, details, triggered_alerts, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_type,
                resource_type,
                resource_id,
                severity,
                summary,
                json.dumps(details) if details else None,
                ",".join(triggered_alerts) if triggered_alerts else None,
                utc_now(),
            ),
        )


def get_monitoring_config(cluster_name: str) -> dict | None:
    """Get monitoring configuration for a cluster. Returns None if not found."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM monitoring_config WHERE cluster_name = ?",
            (cluster_name,),
        ).fetchone()
    return dict(row) if row else None


def upsert_monitoring_config(cluster_name: str, **kwargs) -> None:
    """
    Insert or update monitoring configuration for a cluster.
    Creates the row on first call, updates fields on subsequent calls.
    """
    from app.utils.helpers import utc_now
    existing = get_monitoring_config(cluster_name)
    if existing is None:
        # Build insert with defaults
        fields = {"cluster_name": cluster_name, "created_at": utc_now(), **kwargs}
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields.keys())
        with get_conn() as conn:
            conn.execute(
                f"INSERT INTO monitoring_config ({columns}) VALUES ({placeholders})",
                list(fields.values()),
            )
    else:
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE monitoring_config SET {set_clause} WHERE cluster_name = ?",
                [*kwargs.values(), cluster_name],
            )


def get_recent_monitoring_events(cluster_name: str = None, limit: int = 20) -> list:
    """Get recent monitoring events, optionally filtered by cluster."""
    with get_conn() as conn:
        if cluster_name:
            rows = conn.execute(
                """
                SELECT me.* FROM monitoring_events me
                JOIN analysis_runs ar ON me.run_id = ar.run_id
                WHERE ar.cluster_name = ?
                ORDER BY me.created_at DESC LIMIT ?
                """,
                (cluster_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM monitoring_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def save_snapshot(snapshot: dict) -> None:
    """Persist a graph snapshot to the database."""
    from app.utils.helpers import utc_now
    import json
    from datetime import datetime, timezone, timedelta

    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO graph_snapshots
                (snapshot_id, cluster_name, timestamp, nodes_json, edges_json,
                 node_count, edge_count, entry_points_json, sensitive_targets_json,
                 cycles_detected, aggregate_risk, trigger_source, trigger_desc,
                 created_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot["snapshot_id"],
                snapshot.get("cluster_name", "unknown"),
                snapshot["timestamp"],
                json.dumps(snapshot.get("nodes", [])),
                json.dumps(snapshot.get("edges", [])),
                snapshot.get("node_count", 0),
                snapshot.get("edge_count", 0),
                json.dumps(snapshot.get("entry_points", [])),
                json.dumps(snapshot.get("sensitive_targets", [])),
                snapshot.get("cycles_detected", 0),
                snapshot.get("aggregate_risk", 0.0),
                snapshot.get("trigger_source", "manual"),
                snapshot.get("trigger_desc", ""),
                utc_now(),
                expires,
            ),
        )


def get_snapshot(snapshot_id: str) -> dict | None:
    """Retrieve a snapshot by ID."""
    import json
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM graph_snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["nodes"] = json.loads(d.pop("nodes_json", "[]"))
    d["edges"] = json.loads(d.pop("edges_json", "[]"))
    d["entry_points"] = json.loads(d.pop("entry_points_json", "[]") or "[]")
    d["sensitive_targets"] = json.loads(d.pop("sensitive_targets_json", "[]") or "[]")
    return d


def list_snapshots(limit: int = 20, offset: int = 0) -> list:
    """List snapshots ordered by timestamp desc (lightweight, no nodes/edges JSON)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_id, cluster_name, timestamp, node_count, edge_count,
                   aggregate_risk, cycles_detected, trigger_source, trigger_desc, created_at
            FROM graph_snapshots
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_snapshots() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM graph_snapshots").fetchone()[0]


def get_latest_snapshot_id() -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT snapshot_id FROM graph_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def save_snapshot_diff(diff: dict) -> None:
    """Persist a computed SnapshotDiff to the database."""
    import json
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO snapshot_diffs
                (diff_id, snapshot_id_before, snapshot_id_after,
                 nodes_added, nodes_removed, edges_added, edges_removed,
                 risk_delta, new_attack_paths_count, new_paths_json,
                 disappeared_paths_count, new_cycles_count, disappeared_cycles_count,
                 severity, alert_triggered, alert_reasons_json, computed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                diff["diff_id"],
                diff["snapshot_id_before"],
                diff["snapshot_id_after"],
                diff.get("nodes_added_count", 0),
                diff.get("nodes_removed_count", 0),
                diff.get("edges_added_count", 0),
                diff.get("edges_removed_count", 0),
                diff.get("overall_risk_delta", 0.0),
                diff.get("new_attack_paths_count", 0),
                json.dumps(diff.get("new_attack_paths", [])),
                diff.get("disappeared_paths_count", 0),
                diff.get("new_cycles_count", 0),
                diff.get("disappeared_cycles_count", 0),
                diff.get("severity", "low"),
                1 if diff.get("alert_triggered") else 0,
                json.dumps(diff.get("alert_reasons", [])),
                diff.get("computed_at", ""),
            ),
        )


def save_temporal_alert(alert: dict) -> None:
    """Persist a temporal alert to the database."""
    import json
    from app.utils.helpers import utc_now
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO temporal_alerts
                (alert_id, diff_id, severity, title, description,
                 new_paths_json, new_cycles_json, risk_delta, triggered_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                alert["alert_id"],
                alert.get("diff_id"),
                alert.get("severity", "low"),
                alert.get("title", ""),
                alert.get("description", ""),
                json.dumps(alert.get("new_paths", [])),
                json.dumps(alert.get("new_cycles", [])),
                alert.get("risk_delta", 0.0),
                utc_now(),
            ),
        )


def list_temporal_alerts(limit: int = 20, severity: str = None) -> list:
    """List recent temporal alerts."""
    import json
    with get_conn() as conn:
        if severity:
            rows = conn.execute(
                "SELECT * FROM temporal_alerts WHERE severity = ? ORDER BY triggered_at DESC LIMIT ?",
                (severity, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM temporal_alerts ORDER BY triggered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["new_paths"] = json.loads(d.pop("new_paths_json", "[]") or "[]")
        d["new_cycles"] = json.loads(d.pop("new_cycles_json", "[]") or "[]")
        result.append(d)
    return result


def purge_old_snapshots(days: int = 7) -> int:
    """Delete snapshots older than N days. Returns count deleted."""
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM graph_snapshots WHERE timestamp < ?", (cutoff,)
        )
    return cur.rowcount


@contextmanager
def get_conn():
    """
    Context manager for SQLite connections.
    Auto-commits on success, rolls back on exception.

    Usage:
        with get_conn() as conn:
            conn.execute("SELECT ...")
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safe for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()