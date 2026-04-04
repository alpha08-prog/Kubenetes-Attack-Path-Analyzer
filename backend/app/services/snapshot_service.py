"""
snapshot_service.py — Graph Snapshot Service (B3 Temporal Analysis)

Creates and stores immutable point-in-time snapshots of the attack graph.
Computes diffs between consecutive snapshots to detect new attack paths,
new cycles, and risk score changes. Triggers alerts when thresholds are exceeded.
"""

import uuid
import networkx as nx

from app.utils.helpers import utc_now, severity_label
from app.utils.logger import get_logger
from app.config import settings
from app.core import database as db
from app.models.snapshot import (
    GraphSnapshot, GraphSnapshotFull, SnapshotMeta, SnapshotTrigger,
    SnapshotDiff, TimelinePoint,
)

logger = get_logger(__name__)


# ── Snapshot creation ─────────────────────────────────────────────────────────

def create_snapshot(
    G: nx.DiGraph,
    trigger_source: str = "manual",
    trigger_desc: str = "Manual snapshot",
) -> GraphSnapshot:
    """
    Capture the current graph state as an immutable snapshot.
    Persists to SQLite and returns a lightweight GraphSnapshot object.
    """
    from app.core.graph_builder import (
        find_graph_sources, find_graph_sinks, graph_summary,
    )
    from app.algorithm.dfs_cycles import detect_cycles

    snapshot_id = str(uuid.uuid4())
    now = utc_now()

    # Serialise nodes
    nodes = [
        {
            "id": n,
            "label": attrs.get("label", n),
            "type": attrs.get("type", "unknown"),
            "risk": attrs.get("risk", 0.0),
            "namespace": attrs.get("namespace", "default"),
        }
        for n, attrs in G.nodes(data=True)
    ]

    # Serialise edges
    edges = [
        {
            "source": src,
            "target": dst,
            "relation": attrs.get("relation", "accesses"),
            "risk": attrs.get("risk", 0.0),
        }
        for src, dst, attrs in G.edges(data=True)
    ]

    risks = [n["risk"] for n in nodes]
    aggregate_risk = round(sum(risks) / len(risks), 2) if risks else 0.0

    try:
        cycles_result = detect_cycles(G)
        cycles_detected = cycles_result.get("cycle_count", 0)
    except Exception:
        cycles_detected = 0

    entry_points = find_graph_sources(G)
    sensitive_targets = find_graph_sinks(G)

    row = {
        "snapshot_id": snapshot_id,
        "cluster_name": settings.CLUSTER_NAME,
        "timestamp": now,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "entry_points": entry_points,
        "sensitive_targets": sensitive_targets,
        "cycles_detected": cycles_detected,
        "aggregate_risk": aggregate_risk,
        "trigger_source": trigger_source,
        "trigger_desc": trigger_desc,
    }

    db.save_snapshot(row)
    logger.info(
        "Snapshot created: %s  nodes=%d  edges=%d  risk=%.2f",
        snapshot_id, len(nodes), len(edges), aggregate_risk,
    )

    return GraphSnapshot(
        snapshot_id=snapshot_id,
        cluster_name=settings.CLUSTER_NAME,
        timestamp=now,
        trigger=SnapshotTrigger(source=trigger_source, description=trigger_desc),
        metadata=SnapshotMeta(
            node_count=len(nodes),
            edge_count=len(edges),
            entry_points=entry_points,
            sensitive_targets=sensitive_targets,
            cycles_detected=cycles_detected,
            aggregate_risk=aggregate_risk,
        ),
    )


# ── Snapshot retrieval ────────────────────────────────────────────────────────

def get_snapshot_full(snapshot_id: str) -> GraphSnapshotFull | None:
    """Retrieve full snapshot (with nodes+edges) by ID."""
    row = db.get_snapshot(snapshot_id)
    if not row:
        return None
    return _row_to_full(row)


def list_snapshots(limit: int = 20, offset: int = 0) -> tuple[list[GraphSnapshot], int]:
    """Return a page of snapshots (lightweight) and total count."""
    rows = db.list_snapshots(limit=limit, offset=offset)
    total = db.count_snapshots()
    snapshots = [_row_to_snapshot(r) for r in rows]
    return snapshots, total


def get_latest_snapshot_id() -> str | None:
    return db.get_latest_snapshot_id()


def get_snapshot_timeline(days: int = 7) -> list[TimelinePoint]:
    """Return timeline data points for the last N days."""
    rows = db.list_snapshots(limit=200)
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    points = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if ts < cutoff:
                continue
        except Exception:
            continue
        points.append(TimelinePoint(
            snapshot_id=row["snapshot_id"],
            timestamp=row["timestamp"],
            aggregate_risk=row.get("aggregate_risk", 0.0),
            node_count=row.get("node_count", 0),
            edge_count=row.get("edge_count", 0),
            cycles_detected=row.get("cycles_detected", 0),
        ))
    return sorted(points, key=lambda p: p.timestamp)


# ── Snapshot diffing ──────────────────────────────────────────────────────────

def diff_snapshots(snapshot_id_before: str, snapshot_id_after: str) -> SnapshotDiff:
    """
    Compare two snapshots and return a detailed SnapshotDiff.
    Results are cached in the database for subsequent calls.
    """
    before = db.get_snapshot(snapshot_id_before)
    after = db.get_snapshot(snapshot_id_after)

    if not before:
        raise ValueError(f"Snapshot not found: {snapshot_id_before}")
    if not after:
        raise ValueError(f"Snapshot not found: {snapshot_id_after}")

    diff_id = f"{snapshot_id_before[:8]}_{snapshot_id_after[:8]}"
    now = utc_now()

    before_nodes = {n["id"]: n for n in before.get("nodes", [])}
    after_nodes  = {n["id"]: n for n in after.get("nodes", [])}

    before_edges = {(e["source"], e["target"]) for e in before.get("edges", [])}
    after_edges  = {(e["source"], e["target"]) for e in after.get("edges", [])}

    nodes_added   = [nid for nid in after_nodes if nid not in before_nodes]
    nodes_removed = [nid for nid in before_nodes if nid not in after_nodes]

    risk_increased = []
    risk_decreased = []
    for nid in set(before_nodes) & set(after_nodes):
        old_r = before_nodes[nid].get("risk", 0.0)
        new_r = after_nodes[nid].get("risk", 0.0)
        delta = round(new_r - old_r, 2)
        if delta >= 0.5:
            risk_increased.append({"id": nid, "label": after_nodes[nid].get("label", nid),
                                   "old_risk": old_r, "new_risk": new_r, "delta": delta})
        elif delta <= -0.5:
            risk_decreased.append({"id": nid, "label": after_nodes[nid].get("label", nid),
                                   "old_risk": old_r, "new_risk": new_r, "delta": delta})

    edges_added = [
        {"source": s, "target": t}
        for s, t in after_edges - before_edges
    ]
    edges_removed = [
        {"source": s, "target": t}
        for s, t in before_edges - after_edges
    ]

    # Run attack-path analysis on both graphs to find new/disappeared paths
    new_attack_paths, disappeared_paths = _diff_attack_paths(before, after)

    # Diff cycles
    new_cycles, disappeared_cycles = _diff_cycles(before, after)

    # Risk delta
    old_avg = before.get("aggregate_risk", 0.0)
    new_avg = after.get("aggregate_risk", 0.0)
    overall_risk_delta = round(new_avg - old_avg, 2)

    old_high = sum(1 for n in before.get("nodes", []) if n.get("risk", 0) >= 7.0)
    new_high = sum(1 for n in after.get("nodes", []) if n.get("risk", 0) >= 7.0)

    diff = SnapshotDiff(
        diff_id=diff_id,
        snapshot_id_before=snapshot_id_before,
        snapshot_id_after=snapshot_id_after,
        timestamp_before=before.get("timestamp", ""),
        timestamp_after=after.get("timestamp", ""),
        nodes_added=nodes_added,
        nodes_removed=nodes_removed,
        nodes_risk_increased=risk_increased,
        nodes_risk_decreased=risk_decreased,
        edges_added=edges_added,
        edges_removed=edges_removed,
        new_attack_paths=new_attack_paths,
        disappeared_paths=disappeared_paths,
        new_cycles=new_cycles,
        disappeared_cycles=disappeared_cycles,
        overall_risk_delta=overall_risk_delta,
        high_risk_nodes_delta=new_high - old_high,
        nodes_added_count=len(nodes_added),
        nodes_removed_count=len(nodes_removed),
        edges_added_count=len(edges_added),
        edges_removed_count=len(edges_removed),
        new_attack_paths_count=len(new_attack_paths),
        disappeared_paths_count=len(disappeared_paths),
        new_cycles_count=len(new_cycles),
        disappeared_cycles_count=len(disappeared_cycles),
        computed_at=now,
    )

    # Compute alert severity + persist
    from app.services.temporal_alert_service import evaluate_diff
    diff = evaluate_diff(diff)
    db.save_snapshot_diff(diff.model_dump())

    logger.info(
        "Diff %s->%s: +%d/-%d nodes, +%d/-%d paths, severity=%s",
        snapshot_id_before[:8], snapshot_id_after[:8],
        len(nodes_added), len(nodes_removed),
        len(new_attack_paths), len(disappeared_paths),
        diff.severity,
    )
    return diff


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_nx(snapshot_row: dict) -> nx.DiGraph:
    """Reconstruct a NetworkX DiGraph from a snapshot row."""
    G = nx.DiGraph()
    for n in snapshot_row.get("nodes", []):
        G.add_node(n["id"], **n)
    for e in snapshot_row.get("edges", []):
        G.add_edge(e["source"], e["target"], **e)
    return G


def _diff_attack_paths(before: dict, after: dict) -> tuple[list, list]:
    """Find new/disappeared attack paths by running Dijkstra on both snapshots."""
    try:
        from app.algorithm.dijkstra import shortest_attack_path
        from app.core.graph_builder import find_graph_sources, find_graph_sinks

        G_before = _build_nx(before)
        G_after  = _build_nx(after)

        def collect_paths(G):
            paths = set()
            entries  = find_graph_sources(G)
            targets  = find_graph_sinks(G)
            for src in entries:
                for tgt in targets:
                    if src == tgt:
                        continue
                    result = shortest_attack_path(G, src, tgt)
                    if result.get("found"):
                        paths.add((src, tgt))
            return paths

        paths_before = collect_paths(G_before)
        paths_after  = collect_paths(G_after)

        new_paths = [
            {"source": s, "target": t}
            for s, t in paths_after - paths_before
        ]
        gone_paths = [
            {"source": s, "target": t}
            for s, t in paths_before - paths_after
        ]
        return new_paths, gone_paths

    except Exception as exc:
        logger.warning("Attack path diff failed: %s", exc)
        return [], []


def _diff_cycles(before: dict, after: dict) -> tuple[list, list]:
    """Find new/disappeared privilege escalation cycles."""
    try:
        from app.algorithm.dfs_cycles import detect_cycles

        G_before = _build_nx(before)
        G_after  = _build_nx(after)

        def cycle_set(G):
            result = detect_cycles(G)
            return {frozenset(c.get("nodes", [])) for c in result.get("cycles", [])}

        cycles_before = cycle_set(G_before)
        cycles_after  = cycle_set(G_after)

        new = [{"nodes": list(c)} for c in cycles_after - cycles_before]
        gone = [{"nodes": list(c)} for c in cycles_before - cycles_after]
        return new, gone

    except Exception as exc:
        logger.warning("Cycle diff failed: %s", exc)
        return [], []


def _row_to_snapshot(row: dict) -> GraphSnapshot:
    return GraphSnapshot(
        snapshot_id=row["snapshot_id"],
        cluster_name=row.get("cluster_name", ""),
        timestamp=row.get("timestamp", ""),
        trigger=SnapshotTrigger(
            source=row.get("trigger_source", "manual"),
            description=row.get("trigger_desc", ""),
        ),
        metadata=SnapshotMeta(
            node_count=row.get("node_count", 0),
            edge_count=row.get("edge_count", 0),
            cycles_detected=row.get("cycles_detected", 0),
            aggregate_risk=row.get("aggregate_risk", 0.0),
        ),
    )


def _row_to_full(row: dict) -> GraphSnapshotFull:
    base = _row_to_snapshot(row)
    return GraphSnapshotFull(
        **base.model_dump(),
        nodes=row.get("nodes", []),
        edges=row.get("edges", []),
    )
