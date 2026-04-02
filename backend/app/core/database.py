"""
database.py — SQLite Database Setup
Single SQLite file for storing analysis history.
No external database needed — file lives at data/history.db

Tables:
    analysis_runs   — each time /api/report or any analysis is triggered
    risk_snapshots  — node-level risk scores per run
    findings_log    — individual findings per run (from AI narrator)
"""

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

        """)

    logger.info("SQLite database initialised at %s", DB_PATH)


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