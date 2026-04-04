"""
cli.py - Rubric CLI (no FastAPI).

Rubric-style invocations (from backend/):

    python main.py --blast-radius --source pod-webfront --hops 3
    python main.py --source user-dev1 --target db-production
    python main.py --cycles
    python main.py --critical-node
    python main.py --full-report
    python main.py --help

Or: python -m app.cli  (same flags)

Exit codes: 0 success, 1 runtime/algorithm error, 2 usage/validation error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.algorithm.bfs import blast_radius
from app.algorithm.critical_elimination import critical_node_by_path_elimination
from app.algorithm.dfs_cycles import detect_cycles
from app.algorithm.dijkstra import shortest_attack_path
from app.core.cluster_graph_loader import load_cluster_graph_file
from app.services.kill_chain_report import KillChainReportOptions, generate_full_report


def _resolve_node(G, name: str) -> str:
    """Return the graph node ID for *name*, which may be an ID or a label."""
    if name in G:
        return name
    # Try label match (case-insensitive)
    for nid, data in G.nodes(data=True):
        if data.get("label", "").lower() == name.lower():
            return nid
    raise ValueError(f"Node '{name}' not found in graph (checked IDs and labels)")


def _default_input_path() -> Path | None:
    """../docs/mock-cluster-graph.json relative to repository root."""
    # app/cli.py -> parents[2] == repo root
    repo = Path(__file__).resolve().parents[2]
    candidate = repo / "docs" / "mock-cluster-graph.json"
    return candidate if candidate.is_file() else None


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _print_utf8(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


class _Utf8HelpArgumentParser(argparse.ArgumentParser):
    """Avoid UnicodeEncodeError when printing --help on Windows (cp1252)."""

    def print_help(self, file=None) -> None:
        text = self.format_help()
        if file is None or file is sys.stdout:
            sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
        else:
            file.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = _Utf8HelpArgumentParser(
        prog="main.py",
        description=(
            "Attack path analyzer CLI - loads cluster-graph.json (rubric format). "
            "Use --blast-radius with --source/--hops, or --source/--target for Dijkstra."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        metavar="FILE",
        default=None,
        help="Path to cluster-graph.json (default: docs/mock-cluster-graph.json under repo root)",
    )
    parser.add_argument(
        "--blast-radius",
        action="store_true",
        help="Run BFS blast radius from the node given by --source (use --hops for depth)",
    )
    parser.add_argument(
        "--source",
        metavar="NODE",
        default=None,
        help="Blast-radius start node (with --blast-radius) or Dijkstra source (with --target)",
    )
    parser.add_argument(
        "--target",
        metavar="NODE",
        default=None,
        help="Dijkstra target node (do not combine with --blast-radius)",
    )
    parser.add_argument(
        "--hops",
        type=int,
        default=3,
        metavar="N",
        help="Blast-radius max depth (default: 3). Also used for blast section in --full-report.",
    )
    parser.add_argument("--cycles", action="store_true", help="Detect and print privilege cycles (JSON)")
    parser.add_argument(
        "--critical-node",
        action="store_true",
        help="Critical node via source-to-sink simple path elimination (JSON)",
    )
    parser.add_argument("--full-report", action="store_true", help="Print full kill-chain text report")
    parser.add_argument(
        "--report-mode",
        choices=["dijkstra", "all_paths"],
        default="dijkstra",
        help="Path enumeration mode for --full-report (default: dijkstra)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="FILE",
        default=None,
        help="Optional file path to write output instead of stdout",
    )
    parser.add_argument(
        "--path-cutoff",
        type=int,
        default=None,
        help="Optional max length for all_simple_paths (large graphs)",
    )
    args = parser.parse_args(argv)

    inp = args.input
    if inp is None:
        inp = _default_input_path()
    if inp is None:
        _die("error: specify --input path to cluster-graph.json", 2)

    if not inp.is_file():
        _die(f"error: file not found: {inp.resolve()}", 2)

    if args.blast_radius and args.target is not None:
        _die(
            "error: do not use --target with --blast-radius "
            "(use --source and --hops for blast radius, or omit --blast-radius for Dijkstra)",
            2,
        )

    if args.blast_radius and args.source is None:
        _die("error: --blast-radius requires --source <node id>", 2)

    dijkstra_ok = args.source is not None and args.target is not None and not args.blast_radius
    if (args.source is None) ^ (args.target is None) and not args.blast_radius:
        _die("error: Dijkstra requires both --source and --target (or use --blast-radius --source ...)", 2)

    has_action = bool(
        args.full_report
        or args.cycles
        or args.critical_node
        or args.blast_radius
        or dijkstra_ok,
    )

    if not has_action:
        parser.print_help()
        print(
            "\nerror: specify at least one of "
            "--full-report, --cycles, --critical-node, "
            "--blast-radius --source NODE [--hops N], or --source NODE --target NODE",
            file=sys.stderr,
        )
        return 2

    try:
        built = load_cluster_graph_file(inp)
    except (OSError, ValueError, KeyError) as exc:
        _die(f"error: failed to load cluster graph: {exc}", 1)

    G = built.graph
    meta = built.file_metadata
    exit_code = 0

    out_file = args.output
    def _write_output(content: str) -> None:
        if out_file:
            with out_file.open("a", encoding="utf-8") as f:
                f.write(content + "\n")
        else:
            _print_utf8(content)

    if out_file and out_file.exists():
        out_file.unlink()

    if args.blast_radius:
        assert args.source is not None
        try:
            source_id = _resolve_node(G, args.source)
            br = blast_radius(G, source_id, max_hops=args.hops)
        except ValueError as exc:
            _die(str(exc), 1)
        _write_output(json.dumps(br, indent=2, default=str))

    if dijkstra_ok:
        assert args.source is not None and args.target is not None
        try:
            source_id = _resolve_node(G, args.source)
            target_id = _resolve_node(G, args.target)
            res = shortest_attack_path(G, source_id, target_id)
            _write_output(json.dumps(res, indent=2, default=str))
            if not res.get("found"):
                print(res.get("message", "No path found"), file=sys.stderr)
        except ValueError as exc:
            _die(f"error: {exc}", 1)

    if args.cycles:
        _write_output(json.dumps(detect_cycles(G), indent=2, default=str))

    if args.critical_node:
        _write_output(
            json.dumps(
                critical_node_by_path_elimination(G, path_cutoff=args.path_cutoff),
                indent=2,
                default=str,
            )
        )

    if args.full_report:
        cluster = str(meta.get("cluster", "cluster"))
        text = generate_full_report(
            G,
            KillChainReportOptions(
                report_mode=args.report_mode,
                blast_radius_hops=args.hops,
                path_cutoff=args.path_cutoff,
                critical_path_cutoff=args.path_cutoff,
                cluster_name=cluster,
                metadata=meta,
            ),
        )
        _write_output(text)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
