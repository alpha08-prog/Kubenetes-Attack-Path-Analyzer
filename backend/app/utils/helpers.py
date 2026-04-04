"""
helpers.py — Shared Utility Functions
Small, reusable helpers used across core, algorithms, and services.
No business logic here — pure utility functions only.
"""

import json
import time
from pathlib import Path
from functools import wraps
from datetime import datetime, timezone

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── File I/O ────────────────────────────────────────────────────────────────

def load_json(filepath: str | Path) -> dict | list:
    """
    Load a JSON file safely with clear error messages.

    Usage:
        data = load_json("data/scenarios/nokia_telecom.json")
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path.resolve()}")
    if path.stat().st_size == 0:
        raise ValueError(f"JSON file is empty: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")


def save_json(data: dict | list, filepath: str | Path, indent: int = 2) -> None:
    """
    Save data to a JSON file, creating parent directories if needed.

    Usage:
        save_json(graph_data, "data/processed/graph_data.json")
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, default=str)

    logger.debug("Saved JSON to %s (%d bytes)", path, path.stat().st_size)


# ─── Risk Scoring ─────────────────────────────────────────────────────────────

def risk_to_weight(risk_score: float) -> float:
    """
    Convert a risk score (0–10) to a Dijkstra edge weight.
    Higher risk = lower weight = Dijkstra prefers this edge (easier to exploit).

    risk=9.0  →  weight=1.0  (very easy, attacker loves this)
    risk=5.0  →  weight=5.0  (moderate)
    risk=1.0  →  weight=9.0  (hard to exploit)
    """
    risk_score = max(0.0, min(10.0, float(risk_score)))
    return round(10.0 - risk_score, 2)


def weight_to_risk(weight: float) -> float:
    """Inverse of risk_to_weight."""
    return round(10.0 - max(0.0, min(10.0, float(weight))), 2)


def severity_label(score: float) -> str:
    """
    Convert a numeric risk score to a severity label.
    Based on CVSS v3 severity ranges.

        9.0–10.0  →  Critical
        7.0–8.9   →  High
        4.0–6.9   →  Medium
        0.1–3.9   →  Low
        0.0       →  None
    """
    if score >= 9.0:
        return "critical"
    elif score >= 7.0:
        return "high"
    elif score >= 4.0:
        return "medium"
    elif score > 0.0:
        return "low"
    return "none"


def severity_color(severity: str) -> str:
    """
    Map severity label to a hex color for frontend use.
    Matches the nodeColors.js color scheme.
    """
    return {
        "critical": "#E24B4A",
        "high":     "#EF9F27",
        "medium":   "#378ADD",
        "low":      "#1D9E75",
        "none":     "#888780",
    }.get(severity.lower(), "#888780")


# ─── Graph Helpers ────────────────────────────────────────────────────────────

def node_type_color(node_type: str) -> str:
    """
    Map a node type string to the frontend color.
    Matches nodeColors.js exactly so backend + frontend are consistent.
    """
    return {
        "pod":             "#378ADD",   # blue
        "service_account": "#1D9E75",   # teal
        "role":            "#7F77DD",   # purple
        "secret":          "#BA7517",   # amber
        "database":        "#E24B4A",   # red
        "user":            "#D85A30",   # coral
        "namespace":       "#888780",   # gray
    }.get(node_type.lower(), "#888780")


def sanitize_k8s_name(name: str) -> str:
    """
    Strip Kubernetes namespace prefixes and clean up resource names
    for use as graph node IDs.

    "default/my-pod-6f4d8" → "my-pod"
    """
    if "/" in name:
        name = name.split("/")[-1]
    # Remove random suffixes like -6f4d8b9c7-xkzqp (deployment pods)
    parts = name.split("-")
    if len(parts) > 2 and len(parts[-1]) in (5, 10):
        name = "-".join(parts[:-1])
    return name.lower().strip()


def truncate(text: str, max_len: int = 40) -> str:
    """Truncate long strings for display in logs and labels."""
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


# ─── Timing Decorator ─────────────────────────────────────────────────────────

def timed(func):
    """
    Decorator that logs how long a function takes to run.
    Wrap any algorithm or service function with this.

    Usage:
        @timed
        def blast_radius(G, source, max_hops):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("%-30s completed in %.2fms", func.__qualname__, elapsed_ms)
        return result
    return wrapper


# ─── Timestamp ────────────────────────────────────────────────────────────────

def utc_now() -> str:
    """Return current UTC time as ISO 8601 string (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_filename(prefix: str, ext: str = "json") -> str:
    """
    Generate a timestamped filename for exports and reports.

    timestamp_filename("report") → "report_2024-03-15_14-32-07.json"
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{ts}.{ext}"