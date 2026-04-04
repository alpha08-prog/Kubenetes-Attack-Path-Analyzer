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