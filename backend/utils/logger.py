"""
logger.py — Centralized Logging
Structured logging for the entire backend.
All modules import from here — never use print() in production code.
"""

import logging
import sys
from datetime import datetime


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger. Usage in any module:

        from app.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Graph built with 18 nodes")
        logger.warning("MOCK_MODE is enabled")
        logger.error("kubectl fetch failed: %s", err)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    # Console handler — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(console)

    # File handler — DEBUG and above (full trace for debugging)
    try:
        file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(file_handler)
    except FileNotFoundError:
        pass  # logs/ dir may not exist in test environments

    logger.propagate = False
    return logger


def log_graph_event(action: str, node_count: int, edge_count: int, source: str = "unknown"):
    """
    Structured log for graph construction events.
    Keeps graph-related logs consistent and searchable.
    """
    logger = get_logger("graph.events")
    logger.info(
        "ACTION=%-20s | nodes=%-4d | edges=%-4d | source=%s",
        action, node_count, edge_count, source
    )


def log_algorithm_run(algorithm: str, params: dict, result_summary: str):
    """
    Structured log for every algorithm execution.
    Useful for debugging and showing judges the system is active.
    """
    logger = get_logger("algorithm.events")
    param_str = " | ".join(f"{k}={v}" for k, v in params.items())
    logger.info("ALGO=%-20s | %s | result=%s", algorithm, param_str, result_summary)


def log_api_request(method: str, path: str, status: int, duration_ms: float):
    """
    Structured log for API requests.
    """
    logger = get_logger("api.requests")
    level = logging.INFO if status < 400 else logging.WARNING
    logger.log(level, "%-6s %-35s | %d | %.1fms", method, path, status, duration_ms)