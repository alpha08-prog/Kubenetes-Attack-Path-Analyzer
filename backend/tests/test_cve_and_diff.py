import pytest
from app.services.cve_service import get_cve_score_for_image
from app.services.graph_diff_service import diff_runs
from app.services.history_service import record_analysis_run
from app.core.graph_builder import build_graph

from app.core.database import init_db

def test_cve_score_for_image():
    # Test with a known vulnerable image (should fetch or fallback)
    score = get_cve_score_for_image("nginx:1.14.2")
    # Even if API fails, it should return 0.0 or a valid score
    assert isinstance(score, float)
    assert score >= 0.0

def test_graph_diff_with_edges():
    init_db()
    # 1. Build initial graph
    data1 = {
        "nodes": [
            {"id": "pod:1", "label": "pod1", "type": "pod", "risk": 5.0},
            {"id": "sa:1", "label": "sa1", "type": "service_account", "risk": 3.0}
        ],
        "edges": [
            {"source": "pod:1", "target": "sa:1", "relation": "uses", "risk": 5.0}
        ]
    }
    build_graph(data1)
    run1 = record_analysis_run("test-cluster", source="test")
    
    # 2. Build modified graph with a new edge
    data2 = {
        "nodes": [
            {"id": "pod:1", "label": "pod1", "type": "pod", "risk": 5.0},
            {"id": "sa:1", "label": "sa1", "type": "service_account", "risk": 3.0},
            {"id": "role:1", "label": "role1", "type": "role", "risk": 8.0}
        ],
        "edges": [
            {"source": "pod:1", "target": "sa:1", "relation": "uses", "risk": 5.0},
            {"source": "sa:1", "target": "role:1", "relation": "bound-to", "risk": 8.0}
        ]
    }
    build_graph(data2)
    run2 = record_analysis_run("test-cluster", source="test")
    
    # 3. Diff
    diff = diff_runs(run1, run2)
    
    assert diff["node_changes"]["new_count"] == 1
    assert diff["edge_changes"]["added_count"] == 1
    assert diff["edge_changes"]["new_edges"][0]["source"] == "sa:1"
    assert diff["edge_changes"]["new_edges"][0]["target"] == "role:1"
    assert "recommendation" in diff
    assert "alert_level" in diff["recommendation"]
