"""
seed_graph.py — Load cluster data into the backend graph
Reads data/raw/ JSON files, parses them, builds the graph,
and saves the processed result to data/processed/

Run from the backend/app directory:
    python scripts/seed_graph.py                  # load from data/raw/
    python scripts/seed_graph.py --mock           # load nokia_telecom.json
    python scripts/seed_graph.py --verify         # load + print summary
"""

import sys
import json
import argparse
from pathlib import Path

# ── Allow imports from app/ ────────────────────────────────────────────────────
SCRIPT_PATH = Path(__file__).resolve()
BACKEND_DIR = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[3]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.parser import parse_cluster_data
from app.core.graph_builder import build_graph, graph_summary
from app.core.risk_engine import enrich_graph_risks
from app.utils.helpers import save_json, utc_now
from app.utils.logger import get_logger

logger = get_logger("seed_graph")

RAW_DIR       = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MOCK_PATH     = REPO_ROOT / "data" / "scenarios" / "nokia_telecom.json"


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Seed the attack graph from kubectl raw data or mock scenario"
    )
    parser.add_argument("--mock",   action="store_true", help="Load nokia_telecom.json instead of data/raw/")
    parser.add_argument("--verify", action="store_true", help="Print graph summary after loading")
    parser.add_argument("--save",   action="store_true", default=True, help="Save processed graph to data/processed/")
    return parser.parse_args()


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_raw_kubectl() -> dict:
    """Load all kubectl JSON files from data/raw/"""
    if not RAW_DIR.exists():
        print(f"\n  ✗ data/raw/ directory not found.")
        print("  Run: bash scripts/fetch_k8s_data.sh\n")
        sys.exit(1)

    resources = [
        "pods", "serviceaccounts", "secrets",
        "roles", "clusterroles", "rolebindings", "clusterrolebindings"
    ]

    raw = {}
    print("\n  Loading raw kubectl data...")
    for resource in resources:
        path = RAW_DIR / f"{resource}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            count = len(data.get("items", []))
            print(f"    ✓ {resource:<30} {count} items")
            raw[resource] = data
        else:
            print(f"    ⚠ {resource:<30} not found — skipping")
            raw[resource] = {"items": []}

    return raw


def load_mock() -> dict:
    """Load the pre-built Nokia telecom scenario"""
    if not MOCK_PATH.exists():
        print(f"\n  ✗ Mock scenario not found at {MOCK_PATH}")
        print("  Run: python scripts/generate_mock_data.py\n")
        sys.exit(1)

    with open(MOCK_PATH) as f:
        scenario = json.load(f)

    print(f"\n  ✓ Loaded mock scenario: {MOCK_PATH}")
    print(f"    Nodes: {len(scenario.get('nodes', []))}")
    print(f"    Edges: {len(scenario.get('edges', []))}")
    return scenario


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     Attack Path Analyzer — Seed Graph   ║")
    print("  ╚══════════════════════════════════════════╝")

    # ── Load data ─────────────────────────────────────────────────────────────
    if args.mock:
        print("\n  Mode: Mock scenario (nokia_telecom.json)")
        scenario = load_mock()
        # Mock data is already parsed — go straight to build
        nodes = scenario.get("nodes", [])
        edges = scenario.get("edges", [])
        source = "mock"
    else:
        print("\n  Mode: Live kubectl data (data/raw/)")
        raw = load_raw_kubectl()
        print("\n  Parsing cluster data...")
        parsed = parse_cluster_data(raw)
        nodes = parsed["nodes"]
        edges = parsed["edges"]
        source = "kubectl"

    # ── Enrich with CVE risk scores ───────────────────────────────────────────
    print(f"\n  Enriching risk scores...")
    nodes, edges = enrich_graph_risks(nodes, edges)
    print(f"    ✓ Risk enrichment complete")

    # ── Build graph ───────────────────────────────────────────────────────────
    print(f"\n  Building graph...")
    G = build_graph({"nodes": nodes, "edges": edges})
    print(f"    ✓ Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # ── Save processed data ───────────────────────────────────────────────────
    if args.save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        graph_data = {
            "meta": {
                "source":     source,
                "generated":  utc_now(),
                "node_count": G.number_of_nodes(),
                "edge_count": G.number_of_edges(),
            },
            "nodes": nodes,
            "edges": edges,
        }

        save_json(graph_data, PROCESSED_DIR / "graph_data.json")

        relations = [
            {"source": e["source"], "target": e["target"], "relation": e["relation"]}
            for e in edges
        ]
        save_json(relations, PROCESSED_DIR / "relations.json")

        print(f"    ✓ Saved to data/processed/graph_data.json")
        print(f"    ✓ Saved to data/processed/relations.json")

    # ── Verify ────────────────────────────────────────────────────────────────
    if args.verify:
        print("\n  Graph Summary:")
        summary = graph_summary(G)
        print(f"    Total nodes  : {summary['total_nodes']}")
        print(f"    Total edges  : {summary['total_edges']}")
        print(f"    Is DAG       : {summary['is_dag']}")
        print(f"    Node types   : {summary['node_types']}")
        print(f"    Entry points : {summary['entry_points']}")
        print(f"    Targets      : {summary['targets']}")

        # Quick algorithm check
        print("\n  Quick algorithm check...")
        from app.algorithm.bfs import blast_radius
        from app.algorithm.dfs_cycles import detect_cycles
        from app.algorithm.centrality import find_critical_nodes

        if summary["entry_points"]:
            ep = summary["entry_points"][0]
            br = blast_radius(G, ep, max_hops=3)
            print(f"    BFS from {ep}: {br['total_reachable']} nodes reachable")

        cycles = detect_cycles(G)
        print(f"    DFS cycles: {cycles['cycle_count']} found")

        critical = find_critical_nodes(G, top_n=3)
        if critical["nodes"]:
            top = critical["nodes"][0]
            print(f"    Top critical node: {top['label']} (score={top['combined_score']})")

    # ── Done ──────────────────────────────────────────────────────────────────
    print()
    print("  ✓ Done. Graph is ready.")
    print()
    print("  Next steps:")
    print("    • Restart the backend to pick up processed data")
    print("    • Or call POST /api/graph/reload to hot-reload without restart")
    print()


if __name__ == "__main__":
    main()
