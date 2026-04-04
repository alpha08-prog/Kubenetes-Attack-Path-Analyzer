from __future__ import annotations

import json
from pathlib import Path

from app.core.cluster_graph_loader import (
    graph_counts_match_file_metadata,
    load_cluster_graph_file,
    parse_cluster_graph_document,
)


def test_loader_preserves_rubric_fields(mock_graph_path: Path) -> None:
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    built = load_cluster_graph_file(mock_graph_path)
    G = built.graph
    assert G.nodes["internet"].get("risk_score") == 10.0
    assert G.nodes["pod-webfront"].get("cves") == ["CVE-2024-1234"]
    e = G["user-dev1"]["pod-webfront"]
    assert e.get("relationship") == "can-exec"
    assert e.get("relation") == "can-exec"
    assert e.get("cve") == "CVE-2024-1234"
    assert e.get("cvss") == 8.1


def test_parse_roundtrip_metadata(mock_graph_path: Path) -> None:
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    parsed = parse_cluster_graph_document(raw)
    assert "metadata" in parsed
    assert parsed["metadata"].get("cluster") == "mock-prod-cluster"


def test_counts_reported(mock_graph_path: Path) -> None:
    built = load_cluster_graph_file(mock_graph_path)
    assert built.parsed_nodes == built.node_count == 41
    assert built.parsed_edges == 48
    assert built.edge_count == 52  # +4 bidirectional pod<->pod shared-SA laterals
    # File metadata still says 40/58 — mismatch is documented
    assert not graph_counts_match_file_metadata(built)
