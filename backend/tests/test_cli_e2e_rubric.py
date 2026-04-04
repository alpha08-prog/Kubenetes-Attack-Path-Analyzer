"""
E2E checks aligned with rubric Deliverable 1.3 (mock-cluster-graph.json).

Six pre-planted path chains exist as contiguous edges in the graph.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.cluster_graph_loader import load_cluster_graph_file

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = BACKEND_ROOT / "main.py"
MOCK = REPO_ROOT / "docs" / "mock-cluster-graph.json"

# Rubric "six pre-planted" chains (node ids, per mock JSON comments)
PRE_PLANTED_CHAINS: list[list[str]] = [
    [
        "user-dev1",
        "pod-webfront",
        "sa-webapp",
        "role-secret-reader",
        "secret-db-creds",
        "db-production",
    ],
    [
        "internet",
        "lb-service",
        "pod-api",
        "sa-worker",
        "role-pod-exec",
        "node-worker-1",
    ],
    [
        "user-cicd",
        "sa-cicd",
        "clusterrole-deploy",
        "secret-cicd-token",
        "db-production",
    ],
    [
        "internet",
        "lb-service",
        "pod-webfront",
        "sa-default",
        "clusterrole-admin",
        "secret-admin-token",
        "ns-kube-system",
    ],
    [
        "user-dev2",
        "pod-logger",
        "sa-logger",
        "role-node-reader",
        "node-worker-1",
        "pvc-data",
    ],
    [
        "internet",
        "lb-service",
        "pod-api",
        "configmap-dburl",
        "db-analytics",
    ],
]


def _chain_exists(G, nodes: list[str]) -> bool:
    for i in range(len(nodes) - 1):
        if not G.has_edge(nodes[i], nodes[i + 1]):
            return False
    return True


@pytest.fixture
def mock_path():
    if not MOCK.is_file():
        pytest.skip("mock-cluster-graph.json missing")
    return MOCK


def test_six_pre_planted_chains_present(mock_path: Path) -> None:
    built = load_cluster_graph_file(mock_path)
    G = built.graph
    for chain in PRE_PLANTED_CHAINS:
        assert _chain_exists(G, chain), f"missing chain: {chain}"


def test_main_py_help_exits_zero() -> None:
    if not MAIN_PY.is_file():
        pytest.skip("main.py missing")
    r = subprocess.run(
        [sys.executable, str(MAIN_PY), "--help"],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0
    assert "--blast-radius" in r.stdout
    assert "--full-report" in r.stdout


def test_main_py_cycles_json(mock_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(MAIN_PY),
            "--input",
            str(mock_path),
            "--cycles",
        ],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["cycle_count"] >= 1
    raw_cycles = [frozenset(c["nodes"]) for c in data["cycles"]]
    assert frozenset({"svc-service-a", "svc-service-b"}) in raw_cycles


def test_main_py_full_report_no_crash(mock_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(MAIN_PY),
            "--input",
            str(mock_path),
            "--full-report",
        ],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "SECTION 1" in r.stdout
    assert "web-frontend" in r.stdout


def test_main_py_blast_radius_rubric_flags(mock_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(MAIN_PY),
            "--input",
            str(mock_path),
            "--blast-radius",
            "--source",
            "pod-webfront",
            "--hops",
            "3",
        ],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["source"] == "pod-webfront"
    assert data["max_hops"] == 3
    hop1 = {n["label"] for n in data["zones"].get("1", [])}
    assert "sidecar-proxy" in hop1


def test_unknown_node_blast_exits_nonzero(mock_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(MAIN_PY),
            "--input",
            str(mock_path),
            "--blast-radius",
            "--source",
            "no-such-node-xyz",
            "--hops",
            "2",
        ],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode != 0
