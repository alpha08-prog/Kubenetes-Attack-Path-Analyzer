from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.graph_builder import create_graph
from app.core.hackathon_normalize import normalize_hackathon_graph


def test_normalize_mock_cluster_counts(mock_graph_path: Path) -> None:
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    parsed = normalize_hackathon_graph(raw)
    assert len(parsed["nodes"]) == 41
    assert len(parsed["edges"]) == 48
    G = create_graph(parsed)
    assert G.number_of_nodes() == 41
    assert G.number_of_edges() == 48


def test_normalize_preserves_cve_on_edge(mock_graph_path: Path) -> None:
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    parsed = normalize_hackathon_graph(raw)
    G = create_graph(parsed)
    cve = G["user-dev1"]["pod-webfront"].get("cve")
    assert cve == "CVE-2024-1234"
    assert G["user-dev1"]["pod-webfront"].get("cvss") == 8.1


def test_normalize_flags_on_nodes(mock_graph_path: Path) -> None:
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    parsed = normalize_hackathon_graph(raw)
    G = create_graph(parsed)
    assert G.nodes["internet"].get("is_source") is True
    assert G.nodes["db-production"].get("is_sink") is True
    assert G.nodes["pod-webfront"].get("cves") == ["CVE-2024-1234"]
