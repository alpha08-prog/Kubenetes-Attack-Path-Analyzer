"""
ingestion_service.py - Data ingestion
Fetches cluster data via kubectl or falls back to mock scenario data.
Controlled by MOCK_MODE in config.py.
"""

import json
import shutil
import subprocess
from pathlib import Path

from app.config import settings
from app.core.graph_builder import build_graph
from app.core.parser import parse_cluster_data
from app.utils.logger import get_logger, log_graph_event

logger = get_logger(__name__)

SERVICE_FILE = Path(__file__).resolve()
BACKEND_DIR = SERVICE_FILE.parents[2]


def _discover_repo_root() -> Path:
    """
    Discover the project root in both local and container layouts.
    Prefer a parent that contains data/scenarios.
    """
    for parent in SERVICE_FILE.parents:
        if (parent / "data" / "scenarios").exists():
            return parent
    if (BACKEND_DIR / "data").exists():
        return BACKEND_DIR
    return BACKEND_DIR.parent


REPO_ROOT = _discover_repo_root()
MOCK_SCENARIO_PATH = (REPO_ROOT / settings.MOCK_SCENARIO).resolve()
RAW_DATA_DIRS = [
    (REPO_ROOT / "data" / "raw").resolve(),
    (BACKEND_DIR / "data" / "raw").resolve(),  # Legacy fallback location.
]
PROCESSED_DATA_DIR = (REPO_ROOT / "data" / "processed").resolve()
PROCESSED_GRAPH_PATH = (PROCESSED_DATA_DIR / "graph_data.json").resolve()
PROCESSED_RELATIONS_PATH = (PROCESSED_DATA_DIR / "relations.json").resolve()


def ingest_and_build() -> dict:
    """
    Top-level call used by main.py on startup and by reload endpoint.
    Returns graph summary after building.
    """
    if settings.MOCK_MODE:
        logger.warning("MOCK_MODE=true - loading Nokia telecom scenario")
        parsed = _load_mock()
        processed_source = "mock"
    else:
        logger.info("Fetching live cluster data via kubectl")
        raw, fetch_meta = _fetch_kubectl()
        parsed = parse_cluster_data(raw)
        processed_source = fetch_meta["source"]

    _save_processed(parsed, source=processed_source)
    nodes = parsed.get("nodes") or []
    hackathon_cluster_graph = bool(
        nodes and isinstance(nodes[0], dict) and "risk_score" in nodes[0],
    )
    graph = build_graph(parsed, add_sa_lateral=hackathon_cluster_graph)

    log_graph_event(
        "ingest_complete",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        source=processed_source,
    )

    summary = {
        "source": processed_source,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "status": "ok",
    }

    # NOTE: CVE enrichment (B2) is intentionally NOT called here.
    # It makes sequential NVD API calls that take 2-5s each and would block
    # startup. Instead, main.py kicks it off as a non-blocking background
    # thread via _start_background_cve_enrichment().

    if not settings.MOCK_MODE:
        summary["fallback_count"] = fetch_meta["fallback_count"]
        summary["live_resource_count"] = fetch_meta["live_resource_count"]
    return summary


def _fetch_kubectl() -> tuple[dict, dict]:
    """
    Run kubectl commands and return raw JSON blobs.
    Falls back to saved raw files in data/raw if kubectl fails.
    """
    kubectl_bin = shutil.which("kubectl.exe") or shutil.which("kubectl")
    minikube_bin = shutil.which("minikube.exe") or shutil.which("minikube")

    resources = {
        "pods": ["get", "pods", "-A", "-o", "json"],
        "serviceaccounts": ["get", "serviceaccounts", "-A", "-o", "json"],
        "roles": ["get", "roles", "-A", "-o", "json"],
        "clusterroles": ["get", "clusterroles", "-o", "json"],
        "rolebindings": ["get", "rolebindings", "-A", "-o", "json"],
        "clusterrolebindings": ["get", "clusterrolebindings", "-o", "json"],
        "secrets": ["get", "secrets", "-A", "-o", "json"],
    }

    def _run_json(cmd: list[str]) -> tuple[dict | None, str]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.KUBECTL_TIMEOUT)
            if result.returncode != 0:
                return None, result.stderr.strip() or f"exit={result.returncode}"
            return json.loads(result.stdout), ""
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
            return None, str(exc)

    raw = {}
    fallback_count = 0
    live_resource_count = 0
    live_sources: set[str] = set()

    for key, args in resources.items():
        payload = None
        error = ""

        if kubectl_bin:
            payload, error = _run_json([kubectl_bin, *args])
            if payload is not None:
                raw[key] = payload
                live_resource_count += 1
                live_sources.add("kubectl")
                logger.info("Fetched %s via %s: %d items", key, kubectl_bin, len(payload.get("items", [])))
                continue
            logger.warning("kubectl failed for %s: %s", key, error)

        if minikube_bin:
            payload, error = _run_json([minikube_bin, "kubectl", "--", *args])
            if payload is not None:
                raw[key] = payload
                live_resource_count += 1
                live_sources.add("minikube")
                logger.info(
                    "Fetched %s via minikube kubectl: %d items",
                    key,
                    len(payload.get("items", [])),
                )
                continue
            logger.warning("minikube kubectl failed for %s: %s", key, error)

        fallback_count += 1
        logger.warning("Falling back to saved raw file for %s", key)
        raw[key] = _load_raw_file(key)

    total_resources = len(resources)
    if fallback_count == total_resources:
        source = "saved_raw"
    elif fallback_count > 0 or len(live_sources) > 1:
        source = "mixed"
    elif "minikube" in live_sources:
        source = "minikube"
    else:
        source = "kubectl"

    if fallback_count:
        logger.warning(
            "Cluster data loaded in fallback mode: %d/%d resources came from saved raw files",
            fallback_count,
            total_resources,
        )

    return raw, {
        "source": source,
        "fallback_count": fallback_count,
        "live_resource_count": live_resource_count,
    }


def _load_raw_file(resource: str) -> dict:
    """Load a previously saved kubectl output from data/raw (repo root)."""
    for raw_dir in RAW_DATA_DIRS:
        path = raw_dir / f"{resource}.json"
        if path.exists():
            with open(path, encoding="utf-8") as file_handle:
                return json.load(file_handle)
    logger.warning(
        "No raw file found for %s in: %s - returning empty",
        resource,
        ", ".join(str(p) for p in RAW_DATA_DIRS),
    )
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

    nodes = scenario.get("nodes") or []
    if nodes and isinstance(nodes[0], dict) and "risk_score" in nodes[0]:
        from app.core.cluster_graph_loader import parse_cluster_graph_document

        scenario = parse_cluster_graph_document(scenario)

    logger.info(
        "Loaded mock scenario: %d nodes, %d edges",
        len(scenario.get("nodes", [])),
        len(scenario.get("edges", [])),
    )
    return scenario


def _save_processed(parsed: dict, source: str) -> None:
    """
    Persist processed graph artifacts for clean data layering:
      - data/processed/graph_data.json
      - data/processed/relations.json
    """
    try:
        nodes = parsed.get("nodes", [])
        edges = parsed.get("edges", [])
        node_index = {node.get("id"): node for node in nodes if node.get("id")}

        type_counts: dict[str, int] = {}
        namespaces: set[str] = set()
        for node in nodes:
            node_type = str(node.get("type", "unknown"))
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
            namespaces.add(str(node.get("namespace", "default")))

        graph_payload = {
            "meta": {
                "source": source,
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
            "summary": {
                "node_types": type_counts,
                "namespaces": sorted(namespaces),
            },
            "nodes": nodes,
            "edges": edges,
        }

        relations = []
        for edge in edges:
            src_id = edge.get("source")
            dst_id = edge.get("target")
            src_node = node_index.get(src_id, {})
            dst_node = node_index.get(dst_id, {})
            relations.append(
                {
                    "source": src_id,
                    "source_label": src_node.get("label", src_id),
                    "source_type": src_node.get("type", "unknown"),
                    "target": dst_id,
                    "target_label": dst_node.get("label", dst_id),
                    "target_type": dst_node.get("type", "unknown"),
                    "relation": edge.get("relation", "accesses"),
                    "risk": edge.get("risk", 5.0),
                    "weight": edge.get("weight", 5.0),
                }
            )

        relations_payload = {
            "meta": {
                "source": source,
                "count": len(relations),
            },
            "relations": relations,
        }

        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROCESSED_GRAPH_PATH, "w", encoding="utf-8") as graph_file:
            json.dump(graph_payload, graph_file, indent=2)
        with open(PROCESSED_RELATIONS_PATH, "w", encoding="utf-8") as rel_file:
            json.dump(relations_payload, rel_file, indent=2)
        logger.info(
            "Saved processed artifacts: %s and %s",
            PROCESSED_GRAPH_PATH,
            PROCESSED_RELATIONS_PATH,
        )
    except Exception as exc:
        logger.warning("Failed to save processed artifacts: %s", exc)


def is_mock_mode() -> bool:
    return settings.MOCK_MODE
