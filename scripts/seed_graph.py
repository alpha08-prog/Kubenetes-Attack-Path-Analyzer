#!/usr/bin/env python3
"""
seed_graph.py

Prepare processed graph artifacts from a scenario file and optionally
ask a running backend instance to reload.

Outputs:
  - data/processed/graph_data.json
  - data/processed/relations.json

Usage examples:
  python scripts/seed_graph.py
  python scripts/seed_graph.py --scenario vulnerable_cluster
  python scripts/seed_graph.py --scenario data/scenarios/fixed_cluster.json --reload-backend
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_SCENARIO = SCENARIOS_DIR / "nokia_telecom.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _resolve_scenario_path(scenario_arg: str) -> Path:
    candidate = Path(scenario_arg)
    if candidate.suffix == "":
        candidate = SCENARIOS_DIR / f"{scenario_arg}.json"
    elif not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _validate_scenario(scenario: dict[str, Any], scenario_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = scenario.get("nodes")
    edges = scenario.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError(f"{scenario_path} must contain list fields: 'nodes' and 'edges'")

    node_ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    if len(node_ids) != len(nodes) or any(not nid for nid in node_ids):
        raise ValueError(f"{scenario_path} has node entries missing 'id'")
    if len(set(node_ids)) != len(node_ids):
        raise ValueError(f"{scenario_path} contains duplicate node ids")

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"{scenario_path} edge[{idx}] is not an object")
        for required in ("source", "target", "relation"):
            if required not in edge:
                raise ValueError(f"{scenario_path} edge[{idx}] missing '{required}'")

    return nodes, edges


def _build_processed_payloads(
    scenario: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scenario_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    node_index = {node["id"]: node for node in nodes}
    type_counts = Counter(str(node.get("type", "unknown")) for node in nodes)
    namespaces = sorted({str(node.get("namespace", "default")) for node in nodes})

    graph_data = {
        "meta": {
            "seeded_at": _utc_now(),
            "source": "scenario",
            "scenario_name": scenario.get("meta", {}).get("name", scenario_path.stem),
            "scenario_path": _display_path(scenario_path),
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
        "summary": {
            "node_types": dict(type_counts),
            "namespaces": namespaces,
        },
        "nodes": nodes,
        "edges": edges,
    }

    relations = []
    for edge in edges:
        source = node_index.get(edge["source"], {})
        target = node_index.get(edge["target"], {})
        relations.append(
            {
                "source": edge["source"],
                "source_label": source.get("label", edge["source"]),
                "source_type": source.get("type", "unknown"),
                "target": edge["target"],
                "target_label": target.get("label", edge["target"]),
                "target_type": target.get("type", "unknown"),
                "relation": edge.get("relation", "accesses"),
                "risk": edge.get("risk", 5.0),
                "weight": edge.get("weight", 5.0),
            }
        )

    relations_data = {
        "meta": {
            "seeded_at": _utc_now(),
            "scenario_path": _display_path(scenario_path),
            "count": len(relations),
        },
        "relations": relations,
    }
    return graph_data, relations_data


def _reload_backend(backend_url: str, timeout: float) -> dict[str, Any]:
    url = f"{backend_url.rstrip('/')}/api/graph/reload"
    request = Request(url=url, method="POST")
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed graph artifacts from a scenario.")
    parser.add_argument(
        "--scenario",
        default=str(DEFAULT_SCENARIO),
        help=(
            "Scenario file path or scenario name under data/scenarios "
            "(default: data/scenarios/nokia_telecom.json)"
        ),
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend base URL for reload (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--reload-backend",
        action="store_true",
        help="POST /api/graph/reload after writing processed files.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=6.0,
        help="HTTP timeout in seconds for backend reload (default: 6.0)",
    )
    args = parser.parse_args()

    scenario_path = _resolve_scenario_path(args.scenario)
    scenario = _load_json(scenario_path)
    nodes, edges = _validate_scenario(scenario, scenario_path)
    graph_data, relations_data = _build_processed_payloads(scenario, nodes, edges, scenario_path)

    graph_path = PROCESSED_DIR / "graph_data.json"
    relations_path = PROCESSED_DIR / "relations.json"
    _save_json(graph_path, graph_data)
    _save_json(relations_path, relations_data)

    print(f"Seeded scenario: {_display_path(scenario_path)}")
    print(f"Wrote: {_display_path(graph_path)} ({len(nodes)} nodes, {len(edges)} edges)")
    print(f"Wrote: {_display_path(relations_path)} ({len(relations_data['relations'])} relations)")

    if args.reload_backend:
        try:
            result = _reload_backend(args.backend_url, args.timeout)
            print(f"Backend reloaded: {json.dumps(result)}")
        except HTTPError as exc:
            print(f"Backend reload failed (HTTP {exc.code}): {exc.reason}")
            return 2
        except URLError as exc:
            print(f"Backend reload failed: {exc.reason}")
            return 2
        except Exception as exc:
            print(f"Backend reload failed: {exc}")
            return 2
    else:
        print("Tip: add --reload-backend if backend is already running.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
