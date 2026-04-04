from __future__ import annotations

import json

import networkx as nx
import pytest

from app.algorithm.bfs import blast_radius
from app.algorithm.critical_elimination import critical_node_by_path_elimination
from app.algorithm.dfs_cycles import detect_cycles
from app.algorithm.dijkstra import shortest_attack_path
from app.core.cluster_graph_loader import load_cluster_graph_file


@pytest.fixture
def mock_g(mock_graph_path):
    return load_cluster_graph_file(mock_graph_path).graph


def _zone_labels(result: dict, hop: int) -> set[str]:
    return {n["label"] for n in result["zones"].get(hop, [])}


def test_bfs_pod_webfront_levels(mock_g) -> None:
    br = blast_radius(mock_g, "pod-webfront", max_hops=3)
    assert _zone_labels(br, 1) == {
        "sa-webapp",
        "default",
        "internal-api-svc",
        "sidecar-proxy",
    }
    assert _zone_labels(br, 2) == {
        "secret-reader",
        "tls-cert",
        "api-key",
        "cluster-admin",
        "api-server",
        "db-credentials",
    }
    assert _zone_labels(br, 3) == {
        "admin-token",
        "analytics-db",
        "db-url-config",
        "default",
        "production-db",
        "sa-worker",
        "background-worker",
    }


def test_bfs_cicd_two_hops(mock_g) -> None:
    br = blast_radius(mock_g, "user-cicd", max_hops=2)
    assert _zone_labels(br, 1) == {"sa-cicd"}
    assert _zone_labels(br, 2) == {"deployer", "cicd-deploy-token"}


def test_bfs_isolated_empty() -> None:
    G = nx.DiGraph()
    G.add_node("solo", label="solo", type="pod", risk=5.0, is_source=True)
    br = blast_radius(G, "solo", max_hops=3)
    assert br["total_reachable"] == 0


def test_dijkstra_dev1_to_db_production(mock_g) -> None:
    res = shortest_attack_path(mock_g, "user-dev1", "db-production")
    assert res.get("found") is True
    assert res["hop_count"] == 5
    assert res["total_cost"] == 24.1
    assert res["path"] == [
        "user-dev1",
        "pod-webfront",
        "sa-webapp",
        "role-secret-reader",
        "secret-db-creds",
        "db-production",
    ]
    assert res["hops"][0].get("cve") == "CVE-2024-1234"


def test_dijkstra_internet_to_kube_system(mock_g) -> None:
    res = shortest_attack_path(mock_g, "internet", "ns-kube-system")
    assert res.get("found") is True
    assert res["total_cost"] == 32.0
    assert res["hop_count"] == 5


def test_dijkstra_no_path_message() -> None:
    G = nx.DiGraph()
    for nid, label in [("a", "a"), ("b", "b")]:
        G.add_node(nid, label=label, type="pod", risk=5.0)
    res = shortest_attack_path(G, "a", "b")
    assert res.get("found") is False
    assert "message" in res


def test_dfs_mutual_admin_cycle(mock_g) -> None:
    cres = detect_cycles(mock_g)
    two_node = [
        c for c in cres["cycles"]
        if len(c["nodes"]) == 2
        and set(c["nodes"]) == {"svc-service-a", "svc-service-b"}
    ]
    assert len(two_node) >= 1


def test_critical_node_path_elimination(mock_g) -> None:
    out = critical_node_by_path_elimination(mock_g, path_cutoff=None, top_n=5)
    assert out["baseline_path_count"] == 70
    assert out["critical_node_id"] == "pod-webfront"
    assert out["paths_eliminated"] == 48
    assert out["ranking"][0]["label"] == "web-frontend"
