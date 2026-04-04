"""
critical_elimination.py — Critical node by source→sink simple path elimination.

Rubric methodology: remove each non-source/non-sink candidate, recount all simple
paths from any source to any sink; pick the removal that eliminates the most paths.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable

import networkx as nx

from app.core.graph_builder import find_graph_sources, find_graph_sinks


def iter_simple_paths_sources_to_sinks(
    G: nx.DiGraph,
    sources: Iterable[str],
    sinks: Iterable[str],
    cutoff: int | None,
) -> Iterable[list[str]]:
    """Yield every simple path from any source to any distinct sink."""
    sources = list(sources)
    sinks = list(sinks)
    sink_set = set(sinks)
    for s in sources:
        for t in sinks:
            if s == t:
                continue
            try:
                gen = nx.all_simple_paths(G, s, t, cutoff=cutoff)
            except nx.NodeNotFound:
                continue
            for path in gen:
                if path[-1] in sink_set:
                    yield path


def count_source_sink_paths(
    G: nx.DiGraph,
    sources: list[str],
    sinks: list[str],
    cutoff: int | None = None,
) -> int:
    return sum(1 for _ in iter_simple_paths_sources_to_sinks(G, sources, sinks, cutoff))


def critical_node_by_path_elimination(
    G: nx.DiGraph,
    sources: list[str] | None = None,
    sinks: list[str] | None = None,
    *,
    path_cutoff: int | None = None,
    top_n: int = 5,
) -> dict:
    """
    Find the non-source, non-sink node whose removal eliminates the most
    source→sink simple paths.

    Args:
        G: Directed graph (never mutated).
        sources/sinks: If None, derived via find_graph_sources / find_graph_sinks.
        path_cutoff: Passed to nx.all_simple_paths (None = unlimited; use e.g. 25 for safety).
        top_n: How many runners-up to include in ranking.

    Returns:
        baseline_path_count, critical_node_id, paths_eliminated, ranking, sources, sinks
    """
    if sources is None:
        sources = find_graph_sources(G)
    if sinks is None:
        sinks = find_graph_sinks(G)

    source_set = set(sources)
    sink_set = set(sinks)
    excluded = source_set | sink_set

    baseline = count_source_sink_paths(G, sources, sinks, path_cutoff)

    candidates = [n for n in G.nodes() if n not in excluded]
    results: list[tuple[str, int]] = []

    for node_id in candidates:
        H = deepcopy(G)
        if node_id not in H:
            continue
        H.remove_node(node_id)
        after = count_source_sink_paths(H, sources, sinks, path_cutoff)
        eliminated = baseline - after
        results.append((node_id, eliminated))

    results.sort(key=lambda x: (-x[1], x[0]))
    best_id, best_elim = results[0] if results else ("", 0)

    ranking = []
    for rank, (nid, elim) in enumerate(results[:top_n], start=1):
        ranking.append({
            "rank": rank,
            "id": nid,
            "label": G.nodes[nid].get("label", nid),
            "type": G.nodes[nid].get("type", "unknown"),
            "paths_eliminated": elim,
        })

    return {
        "baseline_path_count": baseline,
        "critical_node_id": best_id,
        "critical_node_label": G.nodes[best_id].get("label", best_id) if best_id else "",
        "paths_eliminated": best_elim,
        "sources": list(sources),
        "sinks": list(sinks),
        "ranking": ranking,
    }
