"""Pytest fixtures — paths relative to repository root."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_GRAPH_PATH = REPO_ROOT / "docs" / "mock-cluster-graph.json"


@pytest.fixture
def mock_graph_path() -> Path:
    if not MOCK_GRAPH_PATH.is_file():
        pytest.skip(f"Mock graph not found: {MOCK_GRAPH_PATH}")
    return MOCK_GRAPH_PATH
