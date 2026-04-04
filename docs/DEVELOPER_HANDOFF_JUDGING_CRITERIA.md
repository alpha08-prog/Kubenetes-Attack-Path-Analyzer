# Developer handoff: judging criteria vs current codebase

This document is for **implementers**. It splits the hackathon rubric into **already in the project** (what judges can partially credit today) and **must be added or changed** to aim for full marks.

**Companion doc (full rubric mapping):** [RUBRIC_STATUS.md](RUBRIC_STATUS.md)  
**Organizer inputs:** [mock-cluster-graph.json](mock-cluster-graph.json), [sample-output.txt](sample-output.txt), scoring rubric PDF (official copy from organizers).

---

## 1. What judges expect (five mandatory deliverables)

| # | Deliverable | Weight |
|---|-------------|--------|
| 1 | Working **CLI** + graph **ingestion** + **E2E** on mock data | 30% |
| 2 | **Kill chain report** (accuracy, structure, remediation) | 25% |
| 3 | **Unit tests** for BFS, Dijkstra, DFS (mock + hidden graphs) | 20% |
| 4 | **Critical node** via node removal + **all simple paths** (not shortest-path-only proxy) | 15% |
| 5 | **Code quality** + **schema** README + setup | 10% |

Bonuses (viz, NVD CVE, temporal diff) are **extra**; they do not replace the above.

---

## 2. Already in the project (reusable for judging)

These satisfy **parts** of the criteria but may be exposed as **REST/UI** instead of CLI, or use **different** data than `docs/mock-cluster-graph.json`.

### Deliverable 1 (CLI + ingestion)

- **Directed weighted graph in memory (NetworkX):** `build_graph()` loads `{nodes, edges}` and stores `relation`, `risk`, `weight` on edges — **when** the parsed dict already uses internal field names.
- **Kubectl → graph pipeline:** `parser.parse_cluster_data` + ingestion in `ingestion_service.py` for live cluster JSON.
- **Mock scenario loading:** `MOCK_MODE` loads a JSON file from `MOCK_SCENARIO` path (today: Nokia-style graph, not the organizer mock file).

### Deliverable 2 (Kill chain report)

- **Dijkstra shortest path** (weighted): `algorithm/dijkstra.py` → `shortest_attack_path`, `all_attack_paths`.
- **Path enrichment:** `attack_service.py` adds severity labels; `remediation_service.py` produces actionable suggestions for a path payload.
- **Human-readable / export paths:** narrator + prompts, PDF report helper (`report_export_service.py`), dashboard UI — **not** the same as the plain-text report in `sample-output.txt`.

### Deliverable 3 (algorithm correctness)

- **BFS blast radius** with hop layers: `algorithm/bfs.py` → `blast_radius`.
- **Cycle detection:** `algorithm/dfs_cycles.py` → `detect_cycles` (NetworkX `simple_cycles`).
- **Logic exists** to run the right *families* of algorithms; **automated rubric test cases are not in the repo yet.**

### Deliverable 4 (critical node)

- **Per–source/target “what-if” removal** with `all_simple_paths` before/after: `centrality.simulate_node_removal` (graph copy, no in-place mutation of the original graph in that function).
- **Ranking UI/API:** `find_critical_nodes` uses **betweenness centrality** — useful product feature but **not** the rubric’s primary critical-node definition.

### Deliverable 5 (docs / quality)

- **README, algorithms.md, START_GUIDE, demo_script** — good for the **web product** and technical depth.
- **Modular backend** (FastAPI routes, services, separate algorithm modules).

### Bonuses (optional alignment)

- **B1:** Cytoscape graph in the frontend.
- **B2:** CVE / NVD-style integration in `cve_service.py`.
- **B3:** Graph diff / history in `graph_diff_service.py` and related APIs.

---

## 3. Must be added or fixed (implementation backlog)

Give this section to the developer as the **task list**. Order is suggested; adjust with the team.

### A. Hackathon JSON normalization (blocks E2E and many tests)

**Problem:** Organizer `mock-cluster-graph.json` uses `name`, `risk_score`, `relationship`, `is_source` / `is_sink`, `cves`, and edge `cve` / `cvss`. The builder expects `label`, `risk`, `relation` and does not persist CVE flags on nodes/edges.

**Implement:**

1. `normalize_hackathon_graph(raw: dict) -> dict` (or equivalent) that outputs the shape `build_graph` expects **and** preserves extra fields (e.g. in `metadata` or explicit graph attrs) for reporting.
2. Normalize **node `type`** to whatever `find_entry_points` / `find_sensitive_targets` expect, **or** update those helpers to use `is_source` / `is_sink` from JSON when present (rubric CNA uses explicit source/sink flags).

**Acceptance:** Loading `docs/mock-cluster-graph.json` yields correct node/edge counts, correct labels for display, non-zero node risks where `risk_score` is set, correct edge relationship strings, CVE/CVSS available for kill-chain text.

---

### B. CLI entrypoint (Deliverable 1.2)

**Problem:** Rubric requires flags such as `--blast-radius`, `--source` / `--target`, `--cycles`, `--critical-node`, `--full-report`, working `--help`, sensible exit codes.

**Implement:** e.g. `python -m app.cli` under `backend/app/`, delegating to existing algorithms after building a graph from a `--input` JSON file (normalized).

**Acceptance:** Judges can run one command against the mock file without starting the web stack; unknown nodes fail clearly; exit `0` on success, non-zero on failure.

---

### C. Full kill-chain text report (Deliverables 2.1–2.3)

**Problem:** Rubric + `sample-output.txt` expect a **structured text report** (sections: attack paths, blast radius, cycles, critical node, summary), correct hop counts and **cumulative edge-weight scores** (±0.1), CVE annotations on edges, paths sorted as specified, and **per-path / per-cycle remediation**.

**Implement:**

1. A formatter that prints sections matching `sample-output.txt` (or rubric wording).
2. Wire **per-path** remediation (extend `remediation_service` or report layer).
3. **Resolve product ambiguity:** Rubric example “Path #1” is **shortest-path Dijkstra** for one pair; `sample-output.txt` lists **all** source→sink simple paths (18 on mock). Confirm with organizers or support **both** via a flag (e.g. `--report-mode dijkstra-pair|all-paths`).

**Acceptance:** Output can be diffed or manually compared to `docs/sample-output.txt` for the mock graph (within agreed tolerance); CVE lines appear where data provides them.

---

### D. Pytest suite for Section 6 (Deliverable 3)

**Problem:** No `backend/tests/` asserting BFS-1, BFS-2, DIJK-1, DIJK-2, DFS-1, CNA-1 (and graceful behavior for hidden-style cases).

**Implement:**

- `pytest` + fixture graph built from **normalized** `docs/mock-cluster-graph.json`.
- Tests for exact expected hop sets (BFS), paths and costs (Dijkstra), cycle set (DFS), critical node id and 32/46 style counts (CNA).
- DIJK-3 / BFS-3 style: no path / empty blast radius, no exception.

**Acceptance:** `pytest` passes locally; CI runs the same tests on Python 3.10+.

---

### E. Critical node by path elimination (Deliverables 4.1–4.2)

**Problem:** Rubric wants the node (excluding sources/sinks) whose removal removes the **most** source→sink **simple** paths, with baseline count (e.g. 46) and elimination count (e.g. 32). Current leaderboard uses **betweenness centrality**.

**Implement:**

- New function e.g. `critical_node_by_path_elimination(G, source_ids, sink_ids, exclude_types_or_flags)` using a **copy** of `G` per candidate removal, `nx.all_simple_paths` over all source×sink pairs (with sane cutoff or cutoff documented for large graphs).
- Expose via CLI `--critical-node` and full report Section 4.

**Acceptance:** On normalized mock data, top node matches rubric expectation (`web-frontend` / `pod-webfront` per graph ids) and counts match **32 / 46** (or document id↔name mapping).

---

### F. E2E on organizer mock (Deliverable 1.3)

**Problem:** Default mock is not `docs/mock-cluster-graph.json`.

**Implement:** Config or CLI `--input` so the judge mock is the default for hackathon submission; verify runtime &lt; 60s, no crash, cycle + critical node + path counts per rubric.

---

### G. README and schema doc (Deliverable 5.2–5.3)

**Problem:** README is Docker/web-centric; rubric wants pip install, **CLI** examples with **output snippets**, all four algorithms described, project structure, and a **schema** doc for `cluster-graph.json` (node types, relationships, weights, `is_source`/`is_sink`, CVE fields, examples).

**Implement:**

- Add `docs/CLUSTER_GRAPH_SCHEMA.md` (or extend README) aligned to **organizer** JSON.
- Add a “Hackathon / CLI” section to README after CLI exists.

---

## 4. Penalties to avoid (from rubric PDF)

- No unhandled exceptions on mock run.
- **Do not** write back to or corrupt the input JSON file.
- **Do not** hardcode expected path lists to match the mock.
- Stay within stated runtime limits on the 40-node mock.
- Target **Python 3.10+** as specified.

---

## 5. Key files the developer will touch most

| Area | Path |
|------|------|
| Graph build | `backend/app/core/graph_builder.py` |
| Ingestion / mock path | `backend/app/services/ingestion_service.py`, `backend/app/config.py` |
| Algorithms | `backend/app/algorithm/bfs.py`, `dijkstra.py`, `dfs_cycles.py`, `centrality.py` (extend or add sibling module for CNA) |
| API (optional parity) | `backend/app/api/routes_*.py` |
| Remediation | `backend/app/services/remediation_service.py` |
| Tests | new `backend/tests/test_rubric_*.py` (suggested) |
| CLI | new `backend/app/cli.py` or `backend/app/main_cli.py` (suggested) |
| Docs | `README.md`, new `docs/CLUSTER_GRAPH_SCHEMA.md` |

---

## 6. One open question for organizers / PM

**Attack path enumeration:** Shortest path only (rubric §2.1 example / DIJK-1) vs **all** simple paths sorted by total weight (`sample-output.txt`). Implementation and tests depend on the answer; see [RUBRIC_STATUS.md](RUBRIC_STATUS.md) §“Rubric Path #1 vs sample-output.txt”.

---

*End of handoff. For criterion-by-criterion tables, see [RUBRIC_STATUS.md](RUBRIC_STATUS.md).*
