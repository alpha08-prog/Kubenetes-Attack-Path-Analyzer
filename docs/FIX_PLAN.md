# Bug & Issue Fix Plan — Kubernetes Attack Path Analyzer

> Hand-off document for the developer agent. Each item below is independently
> actionable: it has a precise file:line reference, a description of the
> current (broken) behaviour, the expected behaviour, and a concrete fix.
>
> **Order of work:** finish all `[CRITICAL]` items first, then `[HIGH]`,
> then `[MEDIUM]`, then `[LOW]`. Within a phase, items can be tackled in any
> order unless a dependency is noted.
>
> All paths are relative to the repo root: `C:/Users/agraw/Attack_path_analyzer/`.

---

## Resolved 2026-04-30

All items below are complete. Test suite: **20/20 passing.** CLI rubric commands and live API smoke tests verified. The historical plan is preserved as-is for context.

| ID | Outcome |
|----|---------|
| **C-1** | `bfs.py:72` returns `max(0, len(visited) - 1)`. Updated docstring + `blast_service.py:44` comment. Bonus: `get_multi_blast_radius` now also subtracts sources from the union. |
| **C-2** | `cli.py:191-201` — replaced unconditional `unlink` with lazy-write-on-first-call (`nonlocal _first_write`). Verified: pre-existing output file is preserved when CLI errors. |
| **C-3** | Code: `dijkstra.py:47` now sums `weight` (not `risk`) so `total_cost` matches what Dijkstra optimized. Docstring + inline comments in `graph_builder.py:61` and `cluster_graph_loader.py:106`. Docs: README "Why Weight Inversion?" → "Edge Weight Semantics"; `algorithms.md` and `ARCHITECTURE.md` cleaned. New `docs/CLUSTER_GRAPH_SCHEMA.md` (202 lines) is the canonical reference. `generate_mock_data.py:250` and `edge.py:27` strings updated. |
| **H-1** | `routes_attack.py:33`, `routes_simulate.py:41` — `ValueError` → 400. Bonus: dict-pattern node-not-found in `routes_blast.py:28` and `routes_simulate.py:38` also flipped to 400. Live verified. |
| **H-2** | `centrality.py:49` — `min(risk, 10.0) / 10.0`; combined ≤ 1.0 provable. |
| **H-3** | Wrapped 5 Slack call sites: `attack_service.py`, `narrator_service.py`, three in `watch_decision_engine.py`. `temporal_alert_service` refactored to delegate via new `slack_service.send_temporal_alert()` (eliminated direct `httpx` path). Lazy imports hoisted. `routes_slack.py` left intentional (user-initiated). |
| **H-4** | `config.py:27,32` — removed `GROK_API_KEY/Grok_API_KEY` and `GROK_MODEL/Grok_MODEL` aliases. Repo-wide `GROK` grep now clean. |
| **H-5** | `git mv` — `docker/{backend,frontend}.DockerFile` → `.Dockerfile`. `docker-compose.yml` lines 15, 68 updated. |
| **H-6** | Backend: 8 routes (`cycles`, `history`, `analysis`, `cve`, `graph`, `report`, `snapshot` GET+POST) — `@router.get("/")` → `@router.get("")`. Frontend: 9 axios URL trailing slashes dropped across `graphApi.ts`, `snapshotApi.ts`, `cveApi.ts`, `TemporalAnalysisPage.tsx`. Live verified — all 7 endpoints return 200 directly, no 307. |
| **M-1** | Docs: `docs/API_DOCUMENTATION.md` documents `total_reachable` as canonical, asymmetry between single/multi blast-radius. Frontend: dropped `total_affected` fallback in 4 places (`DemoMode.tsx:46,275`, `useAnalysis.ts:59`, `BlastRadiusPanel.tsx:58`). |
| **M-2** | `cli.py` — added `_positive_int` validator (range 1..50), applied to `--hops`. |
| **M-3** | `main.py:119,125` — startup baseline `except: pass` blocks → `logger.warning(...)`. |
| **M-4** | Removed `Play` from `BlastRadiusPanel.tsx:2` and `ArrowRight` from `SimulationPanel.tsx:2`. The plan's claim about `Pause`/`Play`/`RotateCcw` in `DemoMode.tsx`/`Dashboard.tsx` was stale — they're actually used. |
| **M-5** | All 3 BFS tests pass (`test_bfs_isolated_empty`, `test_bfs_pod_webfront_levels`, `test_bfs_cicd_two_hops`). No other tests required expected-value updates. |
| **M-6** | `docs/CLUSTER_GRAPH_SCHEMA.md` created. README links to `DOCUMENTATION_SUMMARY.md` / `DOCUMENTATION_CHECKLIST.md` did not actually exist (FIX_PLAN historical reference only). |
| **M-7** | `docker-compose.yml:23-30` and `.env.example:9-19` — added `GROQ_API_KEY`, `SLACK_WEBHOOK_URL`, `NVD_API_KEY` forwarding. |
| **L-1** | `narrator_service.py` confirmed clean (no GROK references). |
| **L-2** | Verified — no `@router.<verb>("/")` remains in `app/api/`. |
| **L-3** | `logger.py` — `FileHandler` → `RotatingFileHandler(maxBytes=10_485_760, backupCount=5, encoding="utf-8")`. |
| **L-4** | 9 README edits softened "rubric" / "Hack2Future" / "100/100 marks" / "What Makes This Special" framing. Bonus: `docs/INDEX.md` "Rubric Requirements (Deliverable 5)" → "Core Reference"; `slack_service.py` Slack alert footers no longer say "Nokia Hackathon 2024". |
| **L-5** | `git mv algorithms.md docs/algorithms.md`. Updated 6 docs files (`ARCHITECTURE.md`, `CONTRIBUTING.md`, `TESTING.md`, `QUICK_START.md`, `INDEX.md`) that linked to the old root path. README links already pointed at `docs/algorithms.md`. |

### Out-of-plan side fixes landed
- `test_kill_chain_report.py:21-27` — fixed pre-existing failures (em-dash vs hyphen; stale `"JSON metadata node_count/edge_count"` assertion). Suite is now fully green.

### Filed for follow-up (not in this plan)
- `BlastRadiusResponse` Pydantic model in `backend/app/models/edge.py:104-111` is missing `source_label`, `stats`, `highest_risk_node`. No model exists for the multi-radius response. Real contract gap, separate concern.
- `main.py:177-178,182-183` — silent `except: pass` blocks around `stop_watching()` / `get_poller().stop()` in shutdown handler. Out of M-3 strict scope.
- `docs/TESTING.md:281,298` — "Deliverable 3 (20 marks)" / "Deliverable 1.3 (10 marks)" headings still use rubric language. Out of L-4 strict scope.
- `test_rubric_algorithms.py` filename — could be renamed for consistency with L-4 wording cleanup.

---

## Quick Index

| ID | Severity | Area | Title |
|---|---|---|---|
| C-1 | CRITICAL | Algorithm | BFS `total_reachable` includes source — breaks isolated-node test and inflates blast counts |
| C-2 | CRITICAL | CLI | `--output` file is unlinked before any work runs — data loss on failure |
| C-3 | CRITICAL | Algorithm / Docs | Edge weight semantics undocumented and inconsistent with code comments |
| H-1 | HIGH | API | `ValueError` mapped to HTTP 404 in `routes_attack.py` (should be 400) |
| H-2 | HIGH | Algorithm | Centrality combined-score uses un-clamped risk after CVE enrichment can push past 10 |
| H-3 | HIGH | Service | Slack webhook failure crashes the attack-path API response |
| H-4 | HIGH | Config | `GROK_API_KEY` alias exists alongside `GROQ_API_KEY` — invites wrong env var |
| H-5 | HIGH | Config | Dockerfile filenames use mixed-case (`backend.DockerFile`) — case-sensitive on Linux/CI |
| H-6 | HIGH | API | Frontend `getCycles()` and `getRunHistory()` rely on trailing slashes that may 307-redirect |
| M-1 | MEDIUM | API | `BlastRadius` response has both `total_reachable` and `stats.total` — frontend has defensive `total_affected` fallback |
| M-2 | MEDIUM | CLI | `--hops` accepts `0` and negatives; silently returns empty result |
| M-3 | MEDIUM | Service | `record_analysis_run` startup baseline can throw and is silently swallowed |
| M-4 | MEDIUM | Frontend | DemoMode imports unused lucide icons — bundle bloat |
| M-5 | MEDIUM | Test | `test_bfs_isolated_empty` is wired against the broken `total_reachable` semantics — fix together with C-1 |
| M-6 | MEDIUM | Docs | README links to `DOCUMENTATION_SUMMARY.md`, `DOCUMENTATION_CHECKLIST.md`, `CLUSTER_GRAPH_SCHEMA.md` that are not in the repo |
| M-7 | MEDIUM | Config | `docker-compose.yml` only forwards `GEMINI_API_KEY` but the narrator uses Groq — Groq key never reaches the container |
| L-1 | LOW | Code Quality | `narrator_service` has a copy of `GROK_API_KEY` aliasing — drop |
| L-2 | LOW | API | `/api/cycles/` includes a trailing slash in the registered prefix that fights FastAPI's redirect default |
| L-3 | LOW | Logging | No log rotation configured |
| L-4 | LOW | Docs | README still claims "Total: 100/100 marks" — leftover from hackathon submission |
| L-5 | LOW | Docs | `algorithms.md` is referenced both at root and under `docs/` — only one copy exists |

---

## CRITICAL — Fix First

### C-1 — BFS `total_reachable` includes the source node

**Files:**
- `backend/app/algorithm/bfs.py:72` (`total_reachable = len(visited)`)
- `backend/tests/test_rubric_algorithms.py:57-61` (test expects `0` for an isolated node)

**Symptom:** `test_bfs_isolated_empty` asserts `br["total_reachable"] == 0` for a node with no outgoing edges, but the code returns `1` because `visited` is seeded with the source. The test currently fails. Worse, every blast-radius API response over-counts by 1, and the `stats.total` and dashboard number are inflated for every cluster.

**Why it matters:** `blast_service.get_blast_radius()` exposes `stats.total` to the UI; the report's "N nodes at risk" line is wrong by 1; comparisons across snapshots are off by 1. The docstring on lines 47–50 even acknowledges the inconsistency ("includes the source so the report counts match") — but the design is wrong and the test is the source of truth.

**Fix:**
```python
# bfs.py:68-75
return {
    "source": source,
    "source_label": G.nodes[source].get("label", source),
    "max_hops": max_hops,
    "total_reachable": max(0, len(visited) - 1),  # exclude source
    "zones": zones,
    "all_reachable": list(visited.keys()),
}
```
Then update `bfs.py:78-94` (`blast_radius_summary`) to drop the "(including source)" annotation, and audit `kill_chain_report.py` for any code that subtracts 1 to compensate (remove the compensation if found).

**Acceptance:**
- `pytest backend/tests/test_rubric_algorithms.py::test_bfs_isolated_empty` passes.
- Existing `test_bfs_pod_webfront_levels` still passes (it checks zone *contents*, not the count).
- The "Total reachable" line in `python main.py --full-report` is unchanged for the demo graph or decreases by exactly 1 — verify against `docs/sample-output.txt`.

---

### C-2 — CLI deletes `--output` file before any analysis runs

**File:** `backend/app/cli.py:191-200`

**Symptom:**
```python
out_file = args.output
def _write_output(content: str) -> None:
    if out_file:
        with out_file.open("a", encoding="utf-8") as f:
            f.write(content + "\n")
    ...
if out_file and out_file.exists():
    out_file.unlink()           # <— happens unconditionally, before any work
```
If the graph load (line 183) or any subsequent step throws, the user-supplied output file is already gone and there is no replacement. Also, the unlink is silent — there is no `--force` confirmation.

**Fix:** open the file once in write mode (truncating) inside `_write_output` *only when first invoked successfully*, then append. Simplest implementation:
```python
out_file = args.output
_first_write = True
def _write_output(content: str) -> None:
    nonlocal _first_write
    if out_file:
        mode = "w" if _first_write else "a"
        with out_file.open(mode, encoding="utf-8") as f:
            f.write(content + "\n")
        _first_write = False
    else:
        _print_utf8(content)
# delete the unconditional unlink block
```
(Use a `[True]` list or a small class if `nonlocal` doesn't work given the function nesting.)

**Acceptance:**
- Running `python main.py --output existing.txt --source missing-node --target other` (which fails inside the algorithm) leaves `existing.txt` untouched.
- Running `python main.py --output out.txt --full-report --cycles` writes both sections to `out.txt`, with `--full-report` not erased by `--cycles`.

---

### C-3 — Edge weight semantics: docstring says one thing, code does another

**Files:**
- `backend/app/algorithm/dijkstra.py:14-16` (docstring claims `weight = 10 - risk`)
- `backend/app/core/graph_builder.py:60-66` (no inversion happens)
- `backend/app/core/cluster_graph_loader.py:106-107` (treats `weight` and `risk` as interchangeable)
- `docs/mock-cluster-graph.json` and `data/scenarios/*` (input files store `weight` directly, no `risk` field)
- `README.md:493-498` ("Why Weight Inversion?" section claims inversion happens)

**Symptom:** The README and Dijkstra docstring describe a model where the input file contains a `risk` score and the loader inverts it to a low-cost weight. In reality, the input files just have `"weight": 5.0` already representing exploitability cost, and the code treats the input weight as the cost directly. `total_cost` in `dijkstra.py:47` sums `risk` (which defaults to `weight` when absent) — i.e. it sums the weights, not `10 - risk`. The tests pass only because the data was hand-authored against the actual (undocumented) convention.

**Why it matters:** Anyone authoring a new scenario file or migrating a real cluster will follow the README/docstring, set `risk` instead of `weight`, and get either inverted Dijkstra results or all-equal weights of 5.0 (the default). This is the single largest landmine for the next person extending the tool.

**Fix (recommended):** *Make the documentation match the code*, not the other way around — the data files and tests are the de-facto contract.
1. Update `dijkstra.py:14-16` docstring to:
   ```python
   """
   Edge weights represent exploitability cost (lower = easier to exploit).
   Input files specify `weight` directly. If only `risk` is provided, it is
   used as the weight (assumes risk is already an "exploitability cost"
   metric, not a 0-10 severity score).
   """
   ```
2. Update `README.md:493-498` "Why Weight Inversion?" — either delete it or rewrite to: "Edge `weight` is exploitability cost on a 0–10 scale; lower means easier. Authors should pre-compute this from CVSS/risk."
3. In `graph_builder.py:60-66` and `cluster_graph_loader.py:106-107`, leave the code as-is, but add a one-line comment: `# weight == exploitability cost; risk is a display value (may equal weight)`.
4. Update `algorithms.md` Dijkstra section to remove any "weight = 10 - risk" formula.

**Alternative (if you want to keep the inversion model):** add `weight = max(0.1, 10.0 - float(edge.get("risk", 5.0)))` in `graph_builder.create_graph()` *and* migrate every scenario file in `data/scenarios/` and `docs/mock-cluster-graph.json` to use `risk` instead of `weight`. This is the larger, breaking change — only do it if the team agrees the inversion model is the right one.

**Acceptance:**
- The README, `algorithms.md`, and `dijkstra.py` docstring all describe the same semantics.
- A new contributor reading `CLUSTER_GRAPH_SCHEMA.md` (or its replacement, see M-6) can author a scenario file that produces correct Dijkstra results on the first try.

---

## HIGH — Fix Before Release

### H-1 — `ValueError` mapped to HTTP 404 in attack routes

**File:** `backend/app/api/routes_attack.py:32-33`

**Symptom:** A request like `POST /api/attack/path {"source":"missing","target":"db"}` returns `404 Not Found` because `_resolve_node` (or the algorithm) raises `ValueError("Node 'missing' not found in graph")`. 404 means *the URL has no resource*, but here the URL is fine — the body is invalid. Standard mapping is 400 (or 422).

**Fix:**
```python
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```
Audit other route files for the same pattern: `routes_blast.py`, `routes_simulate.py`, `routes_critical.py`. Apply consistently.

**Acceptance:** Frontend error states distinguish "graph not loaded" (503) from "bad input" (400) from "no path exists" (still 200 with `found: false`).

---

### H-2 — Centrality combined score not clamped after CVE enrichment

**Files:**
- `backend/app/algorithm/centrality.py:49` (`combined = (score * 0.6) + ((risk / 10.0) * 0.4)`)
- `backend/app/main.py:66` (`risk = round(min(10.0, old_risk + (max_cve_score * 0.2)), 1)`)

**Symptom:** The CVE-enrichment background thread is *already* clamped to 10 (line 66), so this looks safe today. But the clamp is the only thing standing between a typo elsewhere and a centrality score `> 1.0`. Make centrality defensive so future risk bumps can't break the formula.

**Fix:**
```python
combined = round((score * 0.6) + ((min(risk, 10.0) / 10.0) * 0.4), 4)
```
Same change in `centrality.py` everywhere `risk / 10.0` appears.

**Acceptance:** Manually set a node's `risk` to `15.0` in a test fixture and verify combined score ≤ 1.0.

---

### H-3 — Slack alert can crash the attack-path response

**File:** `backend/app/services/attack_service.py:55-56` (also pattern likely in other services that call `slack_service`)

**Symptom:** `send_attack_path_alert` is invoked synchronously inside `get_attack_path`. If the webhook is misconfigured, off-network, or 5xx-ing, the exception bubbles up and the API returns 500 — the user gets no path even though the analysis succeeded.

**Fix:** wrap the call:
```python
if result.get("found"):
    try:
        from app.services.slack_service import send_attack_path_alert
        send_attack_path_alert(result, cluster_name=settings.CLUSTER_NAME)
    except Exception as exc:
        logger.warning("Slack alert failed (non-critical): %s", exc)
```
Audit every call site of `slack_service.*` (`temporal_alert_service`, `watch_decision_engine`, etc.) and apply the same pattern.

**Acceptance:** Set `SLACK_WEBHOOK_URL=https://invalid.example.com/webhook` and run `POST /api/attack/path` — response is still 200 with the path, log contains a single warning.

---

### H-4 — `GROK_API_KEY` env-var alias

**File:** `backend/app/config.py:27-28`

**Symptom:**
```python
validation_alias=AliasChoices(
    "GROQ_API_KEY", "Groq_API_KEY",
    "GROK_API_KEY", "Grok_API_KEY",   # <— "Grok" is X.AI's product, not Groq
)
```
Accepting the wrong spelling silently means a developer who sets `GROK_API_KEY=...` will think the integration works but be hitting Groq with whatever fallback model the code defaults to — confusing both ways.

**Fix:** delete the `GROK_*` aliases. Keep only `GROQ_API_KEY` and `Groq_API_KEY`.

**Acceptance:** Setting only `GROK_API_KEY` produces a startup log line "Groq API key not configured — narrator falls back to deterministic findings" instead of pretending to work.

---

### H-5 — Dockerfile filenames use mixed-case

**Files:**
- `docker/backend.DockerFile`
- `docker/frontend.DockerFile`
- `docker-compose.yml:15` and `docker-compose.yml:59` reference these.

**Symptom:** Windows is case-insensitive so this works locally, but on a Linux CI runner or in a remote build environment the file lookup will fail with "Dockerfile not found." Convention is `Dockerfile` (capital D, lowercase rest) or all-lowercase suffix.

**Fix:**
1. `git mv docker/backend.DockerFile docker/backend.Dockerfile`
2. `git mv docker/frontend.DockerFile docker/frontend.Dockerfile`
3. Update `docker-compose.yml` lines 15 and 59 to match.

**Acceptance:** `docker-compose build` succeeds in a clean checkout on Linux (verify in WSL or via CI).

---

### H-6 — Trailing-slash inconsistency in cycles & history endpoints

**Files:**
- `backend/app/main.py:262` (`prefix="/api/cycles"`) and `routes_cycles.py` route `@router.get("/")` → final URL is `/api/cycles/`
- `frontend/src/api/graphApi.ts:14` calls `/api/cycles/` (with trailing slash)
- Same pattern at `/api/history/`, `/api/diff/latest` (no slash)

**Symptom:** FastAPI's default redirect from `/api/cycles` → `/api/cycles/` is a 307. axios follows redirects but the preflight-CORS round-trip plus the redirect cost a request. More importantly, calling `/api/cycles` (no slash) from a tool that doesn't follow redirects will fail.

**Fix:** Either standardise on no-trailing-slash everywhere (preferred) or set `redirect_slashes=False` on the FastAPI app and pin the routes. Concrete:
- In each route file (e.g. `routes_cycles.py`), change `@router.get("/")` to `@router.get("")`.
- Update `graphApi.ts` calls to drop trailing slashes: `/api/cycles`, `/api/graph`, `/api/history`, `/api/report`.

**Acceptance:** `curl -v http://localhost:8000/api/cycles` returns 200 directly (no `307`).

---

## MEDIUM

### M-1 — Blast radius response shape

**Files:**
- `backend/app/services/blast_service.py:41-45`
- `frontend/src/pages/DemoMode.tsx` (uses `total_reachable ?? total_affected ?? 0`)

The frontend has a defensive fallback to `total_affected`, which suggests an earlier version of the API used that name. Pick one (`total_reachable`) and remove the fallback in `DemoMode.tsx`. Document the contract in `API_DOCUMENTATION.md`.

---

### M-2 — `--hops` accepts non-positive values

**File:** `backend/app/cli.py:106-112`

**Fix:** add `argparse` validation:
```python
def _positive_int(s: str) -> int:
    n = int(s)
    if n < 1 or n > 50:
        raise argparse.ArgumentTypeError("--hops must be 1..50")
    return n
parser.add_argument("--hops", type=_positive_int, default=3, ...)
```

---

### M-3 — Startup baseline-recording silent failures

**File:** `backend/app/main.py:115-126`

The `try: ... except Exception: pass` blocks around `get_auto_attack_path()` and `get_cycles()` mean a bug in those services is invisible at startup. At minimum, log at `WARNING`:
```python
except Exception as exc:
    logger.warning("Startup baseline (attack path) failed: %s", exc)
```

---

### M-4 — Unused frontend imports

**File:** `frontend/src/pages/DemoMode.tsx` (and likely `Dashboard.tsx`)

Run `npx eslint --rule "no-unused-vars: error" --rule "@typescript-eslint/no-unused-vars: error" src/` and remove every flagged import. Specifically `Pause`, `Play`, `RotateCcw` from lucide-react if not used in JSX.

---

### M-5 — Companion to C-1

After applying C-1, re-run `pytest -k bfs` and verify:
- `test_bfs_pod_webfront_levels` still passes
- `test_bfs_isolated_empty` now passes
- `test_bfs_cicd_two_hops` still passes

If any other test referenced `total_reachable` against a non-isolated graph, decrement the expected value by 1.

---

### M-6 — Broken README links

**File:** `README.md`

The following links 404:
- `[docs/DOCUMENTATION_SUMMARY.md]` — file does not exist
- `[DOCUMENTATION_CHECKLIST.md]` — file does not exist (referenced from `README.md:480`)
- `[docs/CLUSTER_GRAPH_SCHEMA.md]` — file does not exist (referenced multiple times)

**Fix:** either create stubs or remove the references. If keeping references, create at minimum a `docs/CLUSTER_GRAPH_SCHEMA.md` documenting the input JSON format (nodes, edges, `weight`, `risk`, `is_source`, `is_sink`, `cves`, `cvss`, `cve` fields). This is also what C-3 needs to land cleanly.

---

### M-7 — `docker-compose.yml` does not forward Groq key

**File:** `docker-compose.yml:19-26`

```yaml
environment:
  GEMINI_API_KEY: ${GEMINI_API_KEY:-}
```
Only Gemini is forwarded, but `narrator_service.py` actually uses Groq (and `routes_ai`/`routes_report` depend on it). The container will always fall back to deterministic findings.

**Fix:** add `GROQ_API_KEY: ${GROQ_API_KEY:-}` and update `.env.example` to list both. Also forward `SLACK_WEBHOOK_URL`, `NVD_API_KEY` if those are referenced in `config.py`.

---

## LOW — Polish

### L-1 — `narrator_service` Grok aliasing

Same root cause as H-4. Verify `narrator_service.py:51` doesn't independently `os.environ.get("GROK_API_KEY")` and remove if it does.

### L-2 — `routes_cycles` empty-string vs `/` route

Subset of H-6. After H-6 lands this should be a one-liner.

### L-3 — Log rotation

`backend/app/utils/logger.py` uses a plain `FileHandler` (or stdout). For long-running pods, switch to `logging.handlers.RotatingFileHandler(maxBytes=10_485_760, backupCount=5)` when a file path is configured.

### L-4 — Hackathon language in README

`README.md:478` claims "Total: 100/100 marks" and the project is "Hack2Future 2.0 ready". Now that the project is moving past the hackathon, soften or remove these lines so they don't appear in production docs.

### L-5 — Duplicate `algorithms.md`

Root has `algorithms.md` (19 KB). README links to both `algorithms.md` and `docs/algorithms.md`. Only one exists. Either move the file under `docs/` and update root link, or delete the `docs/algorithms.md` reference.

---

## Cross-cutting checks (do these once everything above is done)

1. **Run the full test suite:** `cd backend && pytest -v` — every test must pass.
2. **Run the CLI smoke test:** all five rubric commands from `README.md:319-348` must produce non-empty, valid JSON or report output.
3. **Smoke-test Docker:** `docker-compose up --build` then `curl http://localhost:8000/health`, `curl http://localhost:3000`. Both must return 200.
4. **Smoke-test the dashboard:** open the frontend, run the demo mode, confirm Attack Path / Blast Radius / Cycles / Critical Nodes panels all render data without console errors.
5. **Re-grep for `TODO`, `FIXME`, `XXX`, `HACK`** across `backend/` and `frontend/src/` — file an issue for each remaining one.
6. **Re-read this document** and remove any items that have been resolved.

---

## Out-of-scope (intentionally not in this plan)

These were considered and skipped — record here so a future audit doesn't re-discover them:

- **Snapshot route prefix mismatch.** Verified consistent (`/api/snapshots` plural, all internal routes use root-relative paths).
- **`add_shared_service_account_lateral_edges` lateral-edge weight of 1.0.** Intentional — these are not real RBAC edges, they model co-tenancy and should be the cheapest path possible. Document in `algorithms.md` rather than change.
- **`graph_to_cytoscape` re-numbers edges as `e0, e1, ...`.** Stable enough for the UI; only matters if we add edge-level diff/snapshot UIs.

---

*Plan generated from a verified audit on 2026-04-30. File and line numbers are accurate as of commit `2e0093c`. Re-verify if substantial changes have landed since.*
