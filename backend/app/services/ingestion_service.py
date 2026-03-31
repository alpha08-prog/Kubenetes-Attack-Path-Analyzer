"""
ingestion_service.py — Data Ingestion
Fetches cluster data via kubectl or falls back to mock scenario.
Controlled by MOCK_MODE in config.py.
All other services get their graph through here.
"""

import json
import subprocess
from pathlib import Path

from app.config import settings
from app.core.parser import parse_cluster_data
from app.core.graph_builder import build_graph, get_graph
from app.utils.logger import get_logger, log_graph_event

logger = get_logger(__name__)

MOCK_SCENARIO_PATH = Path("data/scenarios/nokia_telecom.json")
RAW_DATA_DIR       = Path("data/raw")


# ─── Main entry point ─────────────────────────────────────────────────────────

def ingest_and_build() -> dict:
    """
    Top-level call used by main.py on startup and by reload endpoint.
    Returns graph summary after building.
    """
    if settings.MOCK_MODE:
        logger.warning("MOCK_MODE=true — loading Nokia telecom scenario")
        raw = _load_mock()
    else:
        logger.info("Fetching live cluster data via kubectl")
        raw = _fetch_kubectl()

    parsed = parse_cluster_data(raw)
    G = build_graph(parsed)

    log_graph_event(
        "ingest_complete",
        G.number_of_nodes(),
        G.number_of_edges(),
        source="mock" if settings.MOCK_MODE else "kubectl",
    )

    return {
        "source":      "mock" if settings.MOCK_MODE else "kubectl",
        "node_count":  G.number_of_nodes(),
        "edge_count":  G.number_of_edges(),
        "status":      "ok",
    }


# ─── kubectl fetch ─────────────────────────────────────────────────────────────

def _fetch_kubectl() -> dict:
    """
    Run kubectl commands and return raw JSON blobs.
    Falls back to saved raw files in data/raw/ if kubectl fails.
    """
    resources = {
        "pods":                ["kubectl", "get", "pods",                "-A", "-o", "json"],
        "serviceaccounts":     ["kubectl", "get", "serviceaccounts",     "-A", "-o", "json"],
        "roles":               ["kubectl", "get", "roles",               "-A", "-o", "json"],
        "clusterroles":        ["kubectl", "get", "clusterroles",              "-o", "json"],
        "rolebindings":        ["kubectl", "get", "rolebindings",        "-A", "-o", "json"],
        "clusterrolebindings": ["kubectl", "get", "clusterrolebindings",       "-o", "json"],
        "secrets":             ["kubectl", "get", "secrets",             "-A", "-o", "json"],
    }

    raw = {}
    for key, cmd in resources.items():
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                raw[key] = json.loads(result.stdout)
                logger.info("Fetched %s: %d items", key, len(raw[key].get("items", [])))
            else:
                logger.warning("kubectl failed for %s: %s", key, result.stderr.strip())
                raw[key] = _load_raw_file(key)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("Error fetching %s: %s — using saved raw file", key, e)
            raw[key] = _load_raw_file(key)

    return raw


def _load_raw_file(resource: str) -> dict:
    """Load a previously saved kubectl output from data/raw/."""
    path = RAW_DATA_DIR / f"{resource}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    logger.warning("No raw file found for %s — returning empty", resource)
    return {"items": []}


# ─── Mock scenario ─────────────────────────────────────────────────────────────

def _load_mock() -> dict:
    """
    Load the Nokia telecom demo scenario.
    This is pre-built data with a guaranteed 3-hop attack path
    and at least one privilege escalation cycle.
    """
    if not MOCK_SCENARIO_PATH.exists():
        logger.error("Mock scenario not found at %s", MOCK_SCENARIO_PATH)
        raise FileNotFoundError(
            f"Mock scenario missing: {MOCK_SCENARIO_PATH}\n"
            "Run: python scripts/generate_mock_data.py"
        )

    with open(MOCK_SCENARIO_PATH) as f:
        scenario = json.load(f)

    # Mock scenario is already parsed (nodes + edges format)
    # so we skip parse_cluster_data and go straight to build_graph
    logger.info(
        "Loaded mock scenario: %d nodes, %d edges",
        len(scenario.get("nodes", [])),
        len(scenario.get("edges", [])),
    )
    return scenario


def is_mock_mode() -> bool:
    return settings.MOCK_MODE