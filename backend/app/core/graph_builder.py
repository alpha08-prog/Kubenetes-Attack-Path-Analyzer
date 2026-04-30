"""
graph_builder.py — NetworkX DiGraph Construction
Takes the cleaned node/edge list from parser.py and builds
a NetworkX DiGraph that all algorithms operate on.

Also exposes helpers to query the graph used across services.
"""

import networkx as nx

from app.utils.logger import get_logger, log_graph_event
from app.utils.helpers import timed, utc_now

logger = get_logger(__name__)

# Module-level graph instance — rebuilt on each ingestion call
_graph: nx.DiGraph = nx.DiGraph()
_metadata: dict = {}


def create_graph(parsed_data: dict) -> nx.DiGraph:
    """
    Build a NetworkX DiGraph without touching the module-level singleton.
    Use from CLI/tests; use build_graph() when wiring the running API server.
    """
    G = nx.DiGraph()

    nodes = parsed_data.get("nodes", [])
    edges = parsed_data.get("edges", [])

    for node in nodes:
        node_id = node["id"]
        attrs: dict = {
            "label": node.get("label", node_id),
            "type": node.get("type", "unknown"),
            "risk": float(node.get("risk", 0.0)),
            "namespace": node.get("namespace", "default"),
            "metadata": dict(node.get("metadata") or {}),
        }
        if "is_source" in node:
            attrs["is_source"] = bool(node["is_source"])
        if "is_sink" in node:
            attrs["is_sink"] = bool(node["is_sink"])
        if "cves" in node:
            attrs["cves"] = list(node["cves"] or [])
        if "risk_score" in node:
            attrs["risk_score"] = float(node["risk_score"])
        G.add_node(node_id, **attrs)

    skipped = 0
    for edge in edges:
        src = edge["source"]
        dst = edge["target"]

        if src not in G.nodes or dst not in G.nodes:
            logger.debug("Skipping edge %s → %s (node not in graph)", src, dst)
            skipped += 1
            continue

        rel = edge.get("relation") or edge.get("relationship") or "accesses"
        # weight == exploitability cost (Dijkstra optimizes this); risk is a display value (defaults to weight)
        eattrs: dict = {
            "relation": rel,
            "relationship": edge.get("relationship", rel),
            "risk": float(edge.get("risk", edge.get("weight", 5.0))),
            "weight": float(edge.get("weight", 5.0)),
        }
        if "cve" in edge:
            eattrs["cve"] = edge["cve"]
        if "cvss" in edge:
            eattrs["cvss"] = edge["cvss"]
        G.add_edge(src, dst, **eattrs)

    if skipped:
        logger.warning("Skipped %d edges with missing nodes", skipped)

    return G


def add_shared_service_account_lateral_edges(G: nx.DiGraph) -> int:
    """
    Add bidirectional Pod<->Pod edges for workloads that share the same ServiceAccount
    (same namespace). Models lateral movement co-tenancy; required for rubric BFS-1
    (e.g. web-frontend reaches sidecar-proxy in hop 1 when both use sa-webapp).
    """
    from collections import defaultdict

    sa_pods: dict[str, list[str]] = defaultdict(list)
    for u, v, data in G.edges(data=True):
        if data.get("relation") != "uses":
            continue
        if G.nodes[v].get("type") != "service_account":
            continue
        if G.nodes[u].get("type") != "pod":
            continue
        sa_pods[v].append(u)

    added = 0
    rel = "shares-service-account"
    w = 1.0
    for _sa, pods in sa_pods.items():
        seen_p = list(dict.fromkeys(pods))
        if len(seen_p) < 2:
            continue
        for i, p1 in enumerate(seen_p):
            ns1 = G.nodes[p1].get("namespace", "default")
            for p2 in seen_p[i + 1 :]:
                if G.nodes[p2].get("namespace", "default") != ns1:
                    continue
                for a, b in ((p1, p2), (p2, p1)):
                    if not G.has_edge(a, b):
                        G.add_edge(
                            a,
                            b,
                            relation=rel,
                            relationship=rel,
                            weight=w,
                            risk=w,
                        )
                        added += 1
    if added:
        logger.debug("Added %d shared-ServiceAccount lateral pod edges", added)
    return added


@timed
def build_graph(parsed_data: dict, *, add_sa_lateral: bool = False) -> nx.DiGraph:
    """
    Build a NetworkX DiGraph from the output of parser.parse_cluster_data()
    (or normalized hackathon JSON) and register it as the live API graph.

    When add_sa_lateral is True (cluster-graph.json style), link pods that share a SA.
    """
    global _graph, _metadata

    G = create_graph(parsed_data)
    if add_sa_lateral:
        add_shared_service_account_lateral_edges(G)
    _graph = G
    _metadata = {
        "built_at": utc_now(),
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "is_dag": nx.is_directed_acyclic_graph(G),
    }

    log_graph_event("build_graph", G.number_of_nodes(), G.number_of_edges(), source="parser")
    return G


def get_graph() -> nx.DiGraph:
    """
    Return the currently loaded graph.
    Called by all route handlers and services.
    Raises if no graph has been built yet.
    """
    if _graph.number_of_nodes() == 0:
        raise RuntimeError(
            "Graph is empty. Run ingestion first: POST /api/graph/reload "
            "or set MOCK_MODE=true to auto-load the Nokia scenario."
        )
    return _graph


def get_metadata() -> dict:
    """Return metadata about the currently loaded graph."""
    return _metadata


def graph_to_cytoscape(G: nx.DiGraph) -> dict:
    """
    Convert the NetworkX DiGraph to Cytoscape.js element format.
    """
    cy_nodes = []
    for node_id, attrs in G.nodes(data=True):
        cy_nodes.append({
            "data": {
                "id": node_id,
                "label": attrs.get("label", node_id),
                "type": attrs.get("type", "unknown"),
                "risk": attrs.get("risk", 0.0),
                "namespace": attrs.get("namespace", "default"),
                "metadata": attrs.get("metadata", {}),
            }
        })

    cy_edges = []
    for i, (src, dst, attrs) in enumerate(G.edges(data=True)):
        cy_edges.append({
            "data": {
                "id": f"e{i}",
                "source": src,
                "target": dst,
                "relation": attrs.get("relation", "accesses"),
                "risk": attrs.get("risk", 5.0),
                "weight": attrs.get("weight", 5.0),
            }
        })

    return {"nodes": cy_nodes, "edges": cy_edges}


def get_nodes_by_type(G: nx.DiGraph, node_type: str) -> list:
    """Return all node IDs of a given type."""
    return [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("type") == node_type
    ]


def get_high_risk_nodes(G: nx.DiGraph, threshold: float = 7.0) -> list:
    """Return all nodes with risk score >= threshold, sorted by risk descending."""
    results = [
        {
            "id": n,
            "label": attrs.get("label", n),
            "type": attrs.get("type", "unknown"),
            "risk": attrs.get("risk", 0.0),
        }
        for n, attrs in G.nodes(data=True)
        if attrs.get("risk", 0.0) >= threshold
    ]
    return sorted(results, key=lambda x: x["risk"], reverse=True)


def find_graph_sources(G: nx.DiGraph) -> list:
    """
    Nodes marked is_source=True, sorted by id.
    If no node has is_source set, fall back to heuristic entry points.

    Resolution order:
      1. is_source=True flag  (mock + hackathon data)
      2. In-degree-0 attacker-facing nodes (case-insensitive type match)
      3. Any attacker-facing node with high risk (if nothing has in_degree 0)
    """
    flagged = [n for n, d in G.nodes(data=True) if d.get("is_source") is True]
    if flagged:
        return sorted(flagged)

    # Normalise type strings for comparison (handles "ExternalActor", "Pod", etc.)
    entry_types = {"pod", "user", "service_account", "externalactor", "external_actor", "service"}

    def _matches_entry_type(n: str) -> bool:
        raw = G.nodes[n].get("type", "")
        return raw.lower().replace("-", "_") in entry_types or raw.lower() in entry_types

    def _risk(n: str) -> float:
        return G.nodes[n].get("risk", G.nodes[n].get("risk_score", 0))

    # Prefer true in-degree-0 nodes
    zero_in = sorted(
        (n for n in G.nodes if G.in_degree(n) == 0 and _matches_entry_type(n) and _risk(n) >= 3.0)
    )
    if zero_in:
        return zero_in

    # Fallback: any attacker-facing node with meaningful risk (ignores in-degree)
    any_entry = sorted(n for n in G.nodes if _matches_entry_type(n) and _risk(n) >= 3.0)
    if any_entry:
        return any_entry

    # Last resort: highest-risk node in entire graph
    return [max(G.nodes, key=_risk, default=None)] if G.nodes else []


def find_graph_sinks(G: nx.DiGraph) -> list:
    """
    Nodes marked is_sink=True. If none flagged, use find_sensitive_targets().
    """
    flagged = [n for n, d in G.nodes(data=True) if d.get("is_sink") is True]
    if flagged:
        return sorted(flagged)
    return sorted(find_sensitive_targets(G))


def find_entry_points(G: nx.DiGraph) -> list:
    """
    Find likely attacker entry points for Dijkstra / demos.
    Prefer explicit is_source when present; else legacy heuristic.
    """
    return find_graph_sources(G)


def find_sensitive_targets(G: nx.DiGraph) -> list:
    """
    Find likely target nodes — databases and high-risk secrets.

    Resolution order (stops at the first non-empty result):
      1. Nodes explicitly flagged is_sink=True  (works for mock + hackathon data)
      2. Out-degree-0 nodes whose type is database/secret (case-insensitive)
      3. Highest-risk nodes overall (last-resort fallback so demo always works)
    """
    # 1. Explicit sink flag — covers both capitalized mock types and real types
    flagged = sorted(
        [n for n, d in G.nodes(data=True) if d.get("is_sink") is True],
        key=lambda n: G.nodes[n].get("risk", G.nodes[n].get("risk_score", 0)),
        reverse=True,
    )
    if flagged:
        return flagged

    # 2. Type-based heuristic (case-insensitive) — covers live kubectl data
    sensitive_types = {"database", "secret"}
    type_based = [
        n for n in G.nodes
        if G.out_degree(n) == 0
        and G.nodes[n].get("type", "").lower() in sensitive_types
        and G.nodes[n].get("risk", G.nodes[n].get("risk_score", 0)) >= 7.0
    ]
    if type_based:
        return type_based

    # 3. Broadest fallback — top-5 highest-risk leaf nodes regardless of type
    leaves = sorted(
        (n for n in G.nodes if G.out_degree(n) == 0),
        key=lambda n: G.nodes[n].get("risk", G.nodes[n].get("risk_score", 0)),
        reverse=True,
    )
    if leaves:
        return leaves[:5]

    # 4. Any database/secret node regardless of out-degree (live clusters may have outgoing edges)
    def _risk_t(n: str) -> float:
        return G.nodes[n].get("risk", G.nodes[n].get("risk_score", 0))

    any_sensitive = sorted(
        (n for n in G.nodes if G.nodes[n].get("type", "").lower() in {"database", "secret"}),
        key=_risk_t,
        reverse=True,
    )
    if any_sensitive:
        return any_sensitive[:5]

    # 5. Last resort: top-5 highest-risk nodes of any type
    return sorted(G.nodes, key=_risk_t, reverse=True)[:5]


def graph_summary(G: nx.DiGraph) -> dict:
    """Return a quick summary of graph stats for the dashboard header."""
    type_counts: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "is_dag": nx.is_directed_acyclic_graph(G),
        "node_types": type_counts,
        "entry_points": find_entry_points(G),
        "targets": find_graph_sinks(G),
        "built_at": _metadata.get("built_at"),
    }
