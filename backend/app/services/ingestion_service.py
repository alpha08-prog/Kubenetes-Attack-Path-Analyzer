"""
ingestion_service.py - Data ingestion
Fetches cluster data via kubectl or falls back to mock scenario data.
Controlled by MOCK_MODE in config.py.
"""

import json
import subprocess
from pathlib import Path

from app.config import settings
from app.core.graph_builder import build_graph
from app.core.parser import parse_cluster_data
from app.utils.logger import get_logger, log_graph_event

logger = get_logger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
MOCK_SCENARIO_PATH = (REPO_ROOT / settings.MOCK_SCENARIO).resolve()
RAW_DATA_DIR = (BACKEND_DIR / "data" / "raw").resolve()


def ingest_and_build() -> dict:
    """
    Top-level call used by main.py on startup and by reload endpoint.
    Returns graph summary after building.
    """
    if settings.MOCK_MODE:
        logger.warning("MOCK_MODE=true - loading Nokia telecom scenario")
        parsed = _load_mock()
    else:
        logger.info("Fetching live cluster data via kubectl")
        raw = _fetch_kubectl()
        parsed = parse_cluster_data(raw)

    graph = build_graph(parsed)

    log_graph_event(
        "ingest_complete",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        source="mock" if settings.MOCK_MODE else "kubectl",
    )

    return {
        "source": "mock" if settings.MOCK_MODE else "kubectl",
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "status": "ok",
    }


def _fetch_kubectl() -> dict:
    """
    Run kubectl commands and return raw JSON blobs.
    Falls back to saved raw files in backend/data/raw if kubectl fails.
    """
    resources = {
        "pods": ["kubectl", "get", "pods", "-A", "-o", "json"],
        "serviceaccounts": ["kubectl", "get", "serviceaccounts", "-A", "-o", "json"],
        "roles": ["kubectl", "get", "roles", "-A", "-o", "json"],
        "clusterroles": ["kubectl", "get", "clusterroles", "-o", "json"],
        "rolebindings": ["kubectl", "get", "rolebindings", "-A", "-o", "json"],
        "clusterrolebindings": ["kubectl", "get", "clusterrolebindings", "-o", "json"],
        "secrets": ["kubectl", "get", "secrets", "-A", "-o", "json"],
    }

    raw = {}
    for key, cmd in resources.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                raw[key] = json.loads(result.stdout)
                logger.info("Fetched %s: %d items", key, len(raw[key].get("items", [])))
            else:
                logger.warning("kubectl failed for %s: %s", key, result.stderr.strip())
                raw[key] = _load_raw_file(key)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error("Error fetching %s: %s - using saved raw file", key, exc)
            raw[key] = _load_raw_file(key)

    return raw


def _load_raw_file(resource: str) -> dict:
    """Load a previously saved kubectl output from backend/data/raw."""
    path = RAW_DATA_DIR / f"{resource}.json"
    if path.exists():
        with open(path, encoding="utf-8") as file_handle:
            return json.load(file_handle)
    logger.warning("No raw file found for %s - returning empty", resource)
    return {"items": []}


def _load_mock() -> dict:
    """
    Load the Nokia telecom demo scenario.
    The mock scenario is already in parsed {nodes, edges} format.
    """
    if not MOCK_SCENARIO_PATH.exists():
        logger.error("Mock scenario not found at %s", MOCK_SCENARIO_PATH)
        raise FileNotFoundError(
            f"Mock scenario missing: {MOCK_SCENARIO_PATH}\n"
            "Run from repo root: python scripts/generate_mock_data.py"
        )

    with open(MOCK_SCENARIO_PATH, encoding="utf-8") as file_handle:
        scenario = json.load(file_handle)

    logger.info(
        "Loaded mock scenario: %d nodes, %d edges",
        len(scenario.get("nodes", [])),
        len(scenario.get("edges", [])),
    )
    return scenario


def is_mock_mode() -> bool:
    return settings.MOCK_MODE
