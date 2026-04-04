"""
hackathon_normalize.py — Back-compat alias for cluster-graph parsing.

Prefer: app.core.cluster_graph_loader.parse_cluster_graph_document
"""

from __future__ import annotations

from typing import Any

from app.core.cluster_graph_loader import parse_cluster_graph_document


def normalize_hackathon_graph(raw: dict[str, Any]) -> dict[str, Any]:
    """Delegate to cluster_graph_loader.parse_cluster_graph_document."""
    return parse_cluster_graph_document(raw)
