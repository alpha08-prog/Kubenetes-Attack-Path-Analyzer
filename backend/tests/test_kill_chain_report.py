from __future__ import annotations

import json

from app.core.cluster_graph_loader import load_cluster_graph_file
from app.services.kill_chain_report import KillChainReportOptions, generate_full_report


def test_full_report_sections(mock_graph_path) -> None:
    G = load_cluster_graph_file(mock_graph_path).graph
    raw = json.loads(mock_graph_path.read_text(encoding="utf-8"))
    meta = raw.get("metadata") or {}
    text = generate_full_report(
        G,
        KillChainReportOptions(
            cluster_name="mock-prod-cluster",
            report_mode="all_paths",
            metadata=meta,
        ),
    )
    assert "[ SECTION 1 — ATTACK PATH DETECTION" in text
    assert "[ SECTION 2 — BLAST RADIUS" in text
    assert "[ SECTION 3 — CIRCULAR PERMISSION" in text
    assert "[ SECTION 4 — CRITICAL NODE" in text
    assert "SUMMARY" in text
    assert "web-frontend" in text
    assert "Nodes" in text and "Edges" in text  # node/edge counts surfaced in header
    assert "Patch CVE-2024-1234" in text or "Remove RoleBinding" in text
