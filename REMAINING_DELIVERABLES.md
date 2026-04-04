# Remaining Deliverables & Work Items
**Generated:** 2026-04-04
**Project:** Attack Path Analyzer (Hackathon)

---

## Overview

You have completed **Deliverables 1 & 2 (49/55 marks)**. This document outlines what remains to achieve full marks (100) and optional bonus marks (up to 115 total).

---

## Deliverable 3: Algorithm Correctness [20 marks] ❌ NEEDS IMPLEMENTATION

The implementation needs **unit tests** that verify algorithm correctness against hidden test cases and the mock dataset.

### 3.1 BFS Blast Radius Tests [7 marks]

**Required Test Cases:**

| Test ID | Input | Expected Output | Status |
|---------|-------|-----------------|--------|
| BFS-1 | Source: pod-webfront, hops: 3 | **Hop 1:** {sa-webapp, sa-default, internal-api-svc, sidecar-proxy}<br>**Hop 2:** {secret-reader, tls-cert, api-key, cluster-admin, api-server}<br>**Hop 3:** {db-credentials, secret-admin-token, sa-worker, db-url-config} | ❌ MISSING |
| BFS-2 | Source: cicd-bot, hops: 2 | **Hop 1:** {sa-cicd}<br>**Hop 2:** {deployer, cicd-deploy-token} | ❌ MISSING |
| BFS-3 | Source: isolated-node, hops: 3 | Empty result (0 reachable nodes), no crash | ❌ MISSING |

**What to implement:**
- ✅ BFS algorithm exists (bfs.py) - **needs unit test**
- Create test file: `test_algorithm_correctness_bfs.py`
- Verify layer/hop assignments are correct
- Ensure no node double-counting across layers
- Test edge case: isolated nodes with no outbound edges

**Scoring rubric:**
- **Full marks (7/7):** BFS-1 and BFS-2 exact match, BFS-3 handled correctly, correct layer assignments
- **Strong (5/7):** BFS-1 correct, BFS-2 off by one node, BFS-3 not tested
- **Good (4/7):** Hop layers merged into flat list (no layering), node set correct
- **Partial (2/7):** BFS visits nodes in wrong order or revisits nodes, incorrect counts
- **None (0/7):** Not implemented

---

### 3.2 Dijkstra's Shortest Path Tests [7 marks]

**Required Test Cases:**

| Test ID | Input | Expected Output | Status |
|---------|-------|-----------------|--------|
| DIJK-1 | Source: user-dev1, Target: db-production | **Path:** user-dev1 → pod-webfront → sa-webapp → role-secret-reader → secret-db-creds → db-production<br>**Cost:** 24.1 | ❌ MISSING |
| DIJK-2 | Source: internet, Target: ns-kube-system | **Path:** internet → lb-service → pod-api → sa-default → clusterrole-admin → secret-admin-token → ns-kube-system<br>**Cost:** 32.0 | ❌ MISSING |
| DIJK-3 | Source: no-path-src, Target: no-path-dst | **Result:** Clear "No path found" message, no exception, exit 0 | ❌ MISSING |

**What to implement:**
- ✅ Dijkstra algorithm exists (dijkstra.py) - **needs unit test**
- Create test file: `test_algorithm_correctness_dijkstra.py`
- Verify edge weights are used (not hop count)
- Test path correctness and cost calculation
- Handle no-path cases gracefully

**Scoring rubric:**
- **Full marks (7/7):** DIJK-1 and DIJK-2 return correct path and cost (±0.05), DIJK-3 handles gracefully
- **Strong (5/7):** DIJK-1 correct, DIJK-2 finds valid path but not shortest, DIJK-3 no crash
- **Good (3/7):** Uses unweighted BFS instead of Dijkstra, results differ from expected
- **Partial (1/7):** Path returned but incorrect, cost not calculated or 0
- **None (0/7):** Not implemented

---

### 3.3 Cycle Detection Tests [6 marks]

**Required Test Cases:**

| Test ID | Input | Expected Output | Status |
|---------|-------|-----------------|--------|
| DFS-1 | Full mock dataset | **Result:** Exactly 1 cycle: [svc-service-a, svc-service-b], no false positives | ❌ MISSING |
| DFS-2 (Hidden) | Graph with 3 planted cycles | **Result:** All 3 cycles returned, no duplicates | ❌ MISSING |

**What to implement:**
- ✅ DFS cycle detection exists (dfs_cycles.py) - **needs unit test**
- Create test file: `test_algorithm_correctness_dfs.py`
- Verify exactly 1 cycle detected in mock data (svc-service-a ↔ svc-service-b)
- Ensure no duplicate cycle reporting (e.g., A→B→A and B→A→B counted separately)
- Return cycle as ordered node list

**Scoring rubric:**
- **Full marks (6/6):** DFS-1 correct (1 cycle, correct nodes), DFS-2 finds all 3, no duplicates
- **Strong (4/4):** DFS-1 correct, DFS-2 finds 2 of 3 cycles
- **Good (3/3):** Detects cycles but reports duplicates
- **Partial (1/1):** Returns True/False only (cycle exists), not the cycle nodes
- **None (0/0):** Not implemented

---

## Deliverable 4: Critical Node Analysis [15 marks] ❌ NEEDS VERIFICATION

### 4.1 Critical Node Identification [8 marks]

**Expected Result (from sample-output):**
```
Critical node: web-frontend (Pod)
Paths eliminated: 32 of 46 baseline paths
Top-5 ranking:
  1. web-frontend (Pod)           -32 paths
  2. api-server (Pod)             -24 paths
  3. internal-api-svc (Service)   -16 paths
  4. sa-worker (ServiceAccount)   -14 paths
  5. pod-exec (Role)              -14 paths
```

**Implementation Status:**
- ✅ Critical node analysis exists (critical_elimination.py) - **needs verification against expected**
- ⚠️ Output may differ due to data mismatch (58 edges vs 48 expected)

**What to fix:**
- Verify correct critical node is identified (web-frontend)
- Verify elimination count matches (32 of 46)
- Verify top-5 ranking is correct
- Exclude source and sink nodes from candidates
- Output matches format: "Critical node: {name} ({type}) | Paths eliminated: {count}"

**Scoring rubric:**
- **Full marks (8/8):** Correct node identified (web-frontend), correct count (32), ranking matches, sources/sinks excluded
- **Strong (6/6):** Correct node, count off by ±2, ranking mostly correct
- **Good (4/4):** Second-ranked node returned, methodology correct
- **Partial (2/2):** Node returned but wrong (e.g., source node), no ranking
- **None (0/0):** Not implemented

---

### 4.2 Methodology Correctness [7 marks]

**Requirements to verify:**
1. Graph is **copied** before each node removal (not mutated in-place)
2. **All simple paths** are counted (not just shortest paths)
3. **Baseline path count** is reported before removals
4. **Cutoff depth** is applied consistently for large graphs
5. **Graph restored** to original state after analysis

**Implementation Status:**
- ✅ Exists in critical_elimination.py - **needs code review**

**Scoring rubric:**
- **Full marks (7/7):** Graph copied, all simple paths counted, cutoff applied, baseline reported, restored after
- **Strong (5/5):** Correct methodology, minor issue (cutoff not applied or baseline not reported)
- **Good (3/3):** Graph mutated in-place (corrupts after analysis), results numerically correct on mock data
- **Partial (2/2):** Only shortest paths counted, or betweenness centrality proxy used
- **None (0/0):** No methodology

---

## Deliverable 5: Code Quality & Documentation [10 marks] ❌ NEEDS COMPLETION

### 5.1 Code Readability [4 marks]

**Current Status:** ⚠️ PARTIAL

**Checklist:**
- [ ] Functions have docstrings (check all algorithm functions)
- [ ] Variables clearly named (review cryptic variable names)
- [ ] Algorithms in distinct functions (separate concerns)
- [ ] No magic numbers (document weights, thresholds)
- [ ] PEP-8 compliant (run `black` and `pylint`)
- [ ] No dead code (remove unused imports/functions)

**Example improvements needed:**
```python
# ❌ BAD - Magic numbers, no docstring
def dijkstra(graph, src, dst):
    dist = {n: 9999 for n in graph.nodes()}

# ✅ GOOD - Clear names, documented
def dijkstra_shortest_path(graph, source, target):
    """
    Find shortest attack path using Dijkstra's algorithm.
    Edge weights = 10 - risk_score (higher risk = lower weight).

    Args:
        graph: NetworkX DiGraph
        source: Source node ID
        target: Target node ID
    Returns:
        (path_list, cost)
    """
```

**Scoring rubric:**
- **Full marks (4/4):** Docstrings, clear names, separated algorithms, no magic numbers, PEP-8
- **Good (3/3):** Mostly readable, few long functions, minor style issues
- **Partial (1/1):** One long main() block, hardcoded values
- **None (0/0):** Unreadable/obfuscated

---

### 5.2 Schema Documentation [3 marks]

**Status:** ❌ NOT DONE

**What to create:**
- Create file: `SCHEMA.md` in root directory OR section in `README.md`
- Document all node types with examples
- Document all edge relationship types
- Explain weight semantics
- Explain is_source/is_sink flags
- Document CVE field format

**Template:**

```markdown
# Cluster Graph Schema

## Node Types

### Pod
- **id:** Unique identifier (e.g., "pod-webfront")
- **name:** Display name (e.g., "web-frontend")
- **namespace:** Kubernetes namespace
- **risk_score:** 0-10 (0=safe, 10=critical)
- **cves:** List of CVE IDs (e.g., ["CVE-2024-1234"])
- **is_source:** true if external entry point (can initiate attacks)
- **is_sink:** true if sensitive target (databases, secrets)

### ServiceAccount, Role, Secret, Database, etc.
[similar documentation for each type]

## Edge Relationships

### can-exec
- **meaning:** User/Pod can execute commands on target
- **weight:** Typically 4.0-5.0
- **example:** user-dev1 --[can-exec]--> web-frontend

### uses
- **meaning:** Pod/Process uses ServiceAccount's identity
- **weight:** Typically 2.0-3.0
- **example:** web-frontend --[uses]--> sa-webapp

### bound-to
- **meaning:** ServiceAccount/Role binding grants permissions
- **weight:** Typically 3.5-5.0
- **example:** sa-webapp --[bound-to]--> secret-reader

[document all other relationship types...]

## Weight Semantics
- Weights represent exploitation difficulty
- Edge weight = 10 - risk_score
- Lower weight = easier to exploit
- Used by Dijkstra to find highest-risk paths

## Example Node
{
  "id": "pod-webfront",
  "type": "Pod",
  "name": "web-frontend",
  "namespace": "default",
  "risk_score": 7.5,
  "is_source": false,
  "is_sink": false,
  "cves": ["CVE-2024-1234"]
}

## Example Edge
{
  "source": "user-dev1",
  "target": "pod-webfront",
  "relationship": "can-exec",
  "weight": 5.0,
  "cve": "CVE-2024-1234",
  "cvss": 8.1
}
```

**Scoring rubric:**
- **Full marks (3/3):** All node types, edge relationships, weights, flags documented with examples
- **Good (2/2):** Schema documented but missing 1-2 field explanations
- **Partial (1/1):** Schema mentioned but not documented, reader must infer from JSON
- **None (0/0):** No documentation

---

### 5.3 README & Setup Instructions [3 marks]

**Status:** ⚠️ PARTIAL (exists but needs enhancement)

**Current README gaps:**
- [ ] Installation steps (`pip install -r requirements.txt`)
- [ ] CLI usage examples with expected output snippets
- [ ] Description of all 4 algorithms (BFS, Dijkstra, DFS, Critical Node)
- [ ] Project structure overview (directories and files)
- [ ] Estimated setup time: "New user can run the tool within 5 minutes"

**Template sections needed:**

```markdown
# Attack Path Analyzer

## Installation (Estimated: 2 minutes)

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd Attack_path_analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Verify installation:
   ```bash
   python backend/main.py --help
   ```

## Quick Start (Estimated: 3 minutes)

### Generate Full Report
```bash
python backend/main.py --input docs/mock-cluster-graph.json --full-report
```

Expected output:
```
KILL CHAIN REPORT  -  2026-04-04 15:14:22
Cluster: mock-prod-cluster
Nodes: 41 | Edges: 48

[ SECTION 1 - ATTACK PATH DETECTION (Dijkstra) ]
⚠ 18 attack path(s) detected

Path #1 | 3 hops | Risk Score: 9.5 [MEDIUM]
...
```

### Find Shortest Attack Path
```bash
python backend/main.py --source user-dev1 --target db-production
```

### Detect Permission Cycles
```bash
python backend/main.py --cycles
```

### Find Critical Infrastructure Node
```bash
python backend/main.py --critical-node
```

### Map Blast Radius
```bash
python backend/main.py --blast-radius --source internet --hops 3
```

## Algorithms Explained

### 1. Dijkstra's Shortest Path (--source/--target)
Finds the lowest-risk attack path from source to target.
- **Weight formula:** 10 - risk_score
- **Output:** Hop-by-hop path, total cost, CVE annotations

### 2. Blast Radius (--blast-radius)
Breadth-First Search (BFS) to find all reachable nodes within N hops.
- **Input:** Source node, max hops
- **Output:** Nodes grouped by hop distance

### 3. Cycle Detection (--cycles)
Depth-First Search (DFS) to find privilege escalation loops.
- **Output:** List of cycles (mutual admin grants, etc.)

### 4. Critical Node Analysis (--critical-node)
Removes each node and recounts attack paths to find most impactful node.
- **Output:** Critical node, number of paths eliminated, top-5 ranking

## Project Structure

```
backend/
  ├── main.py                 # CLI entry point
  ├── requirements.txt        # Python dependencies
  ├── app/
  │   ├── cli.py             # CLI interface
  │   ├── algorithm/
  │   │   ├── dijkstra.py    # Shortest path
  │   │   ├── bfs.py         # Blast radius
  │   │   ├── dfs_cycles.py  # Cycle detection
  │   │   └── critical_elimination.py  # Critical node
  │   ├── core/
  │   │   ├── graph_builder.py       # Graph construction
  │   │   └── cluster_graph_loader.py # Data ingestion
  │   └── services/
  │       └── kill_chain_report.py   # Report generation
  └── data/
      └── mock-cluster-graph.json    # Test data

frontend/
  └── src/
      └── pages/Dashboard.tsx        # Web UI (optional)

tests/
  ├── test_algorithm_correctness_bfs.py
  ├── test_algorithm_correctness_dijkstra.py
  └── test_algorithm_correctness_dfs.py
```

## Troubleshooting

**Q: "No module named 'networkx'"**
A: Run `pip install networkx`

**Q: "Graph is empty"**
A: Verify path to mock-cluster-graph.json is correct

**Q: "No path found"**
A: Source and target may not be connected in the graph
```

**Scoring rubric:**
- **Full marks (3/3):** Installation steps, CLI examples with output, all 4 algorithms described, structure shown, <5 min setup
- **Good (2/2):** Install + basic usage present, missing algo descriptions or structure
- **Partial (1/1):** Stub with title only or just file names listed
- **None (0/0):** No README

---

## Summary Table

| Deliverable | Component | Status | Marks | Action Required |
|-------------|-----------|--------|-------|-----------------|
| **D3** | BFS Tests | ❌ | 0/7 | Write unit tests for BFS-1, BFS-2, BFS-3 |
| **D3** | Dijkstra Tests | ❌ | 0/7 | Write unit tests for DIJK-1, DIJK-2, DIJK-3 |
| **D3** | DFS Tests | ❌ | 0/6 | Write unit tests for DFS-1, DFS-2 |
| **D3 Total** | | ❌ | 0/20 | **Write 3 test files** |
| **D4** | Critical Node | ⚠️ | 0/8 | Verify against expected output |
| **D4** | Methodology | ⚠️ | 0/7 | Code review for graph copying & path counting |
| **D4 Total** | | ⚠️ | 0/15 | **Verify & test** |
| **D5** | Code Readability | ⚠️ | 0/4 | Add docstrings, fix style |
| **D5** | Schema Docs | ❌ | 0/3 | Create SCHEMA.md or README section |
| **D5** | README & Setup | ⚠️ | 0/3 | Expand with CLI examples & algo descriptions |
| **D5 Total** | | ⚠️ | 0/10 | **Documentation work** |
| | | | | |
| **CURRENT TOTAL** | D1-D2 | ✅ | 49/55 | **Complete D3, D4, D5 for 100** |
| **WITH D3-D5** | All Core | ❌ | 49/100 | **Work needed** |

---

## Bonus Challenges [+15 marks, non-substitutable]

These can add up to 15 bonus points but don't substitute for core deliverables.

### B1: Interactive Graph Visualization [+5 marks]

**What to implement:**
- Render attack graph in browser (D3.js or Cytoscape.js)
- Highlight critical attack path in red
- Mark safe nodes in green
- Support zoom/pan
- Node tooltips showing: name, type, risk score

**Where to start:**
- Frontend already exists in `/frontend/src/pages/Dashboard.tsx`
- Uses Cytoscape.js for visualization
- May already be partially implemented ✅

**Evaluation criteria:**
- Graph renders without error
- Attack path nodes visually distinct
- Zoom/pan functional
- Tooltips show all required info

---

### B2: Live CVE Scoring [+5 marks]

**What to implement:**
- Integration with NIST NVD API (or similar)
- Fetch CVSS scores for CVEs automatically
- Apply scores to Pod nodes based on container images
- Fallback to mock data if API unavailable
- Handle rate limiting

**Where to start:**
- Check if `/backend/app/services/cve_service.py` exists
- May need to implement NVD API integration

**Evaluation criteria:**
- API called successfully
- CVSS score fetched for at least one real CVE
- Fallback to mock data works
- Rate limiting handled

---

### B3: Temporal Analysis [+5 marks]

**What to implement:**
- Store graph snapshots over time (before/after hardening)
- Detect new attack paths between snapshots
- Alert when new paths appear
- Show risk delta (what changed)

**Where to start:**
- Check if `/backend/app/services/graph_diff_service.py` exists
- Implement snapshot comparison logic

**Evaluation criteria:**
- Two snapshots loadable
- Diff identifies: new nodes, new edges, new paths
- Alert output clearly describes changes & risk delta

---

## Priority Order

### Immediate (High Priority)
1. **Resolve data mismatch** - Use correct mock-cluster-graph.json from judges
2. **Write D3 Tests** - Algorithm correctness (20 marks)
3. **Fix D5 Docs** - README + Schema (10 marks)

### Important (Medium Priority)
4. **Verify D4** - Critical node analysis
5. **Code cleanup** - Readability improvements

### Optional (Low Priority)
6. **Bonus challenges** - B1, B2, B3 (only for >100 points)

---

## Estimated Effort

| Task | Effort | Impact |
|------|--------|--------|
| Write 3 test files (D3) | 3-4 hours | +20 marks |
| Verify D4 & fix data | 1-2 hours | +15 marks |
| Complete README & SCHEMA | 1-2 hours | +10 marks |
| **Total to reach 100** | **5-8 hours** | **+55 marks** |
| Bonus: Graph viz (B1) | 2-3 hours | +5 marks |
| Bonus: CVE API (B2) | 2-3 hours | +5 marks |
| Bonus: Temporal (B3) | 2-3 hours | +5 marks |
| **Total for 115** | **13-20 hours** | **+15 bonus marks** |

---

## Next Steps

1. ✅ **Confirm test data:** Which mock-cluster-graph.json is official?
2. ✅ **Write D3 tests:** Use pytest format from existing tests
3. ✅ **Verify D4 output:** Check critical node against expected
4. ✅ **Complete D5 docs:** Update README and create SCHEMA.md
5. ⚠️ **Test all deliverables:** Run against judge's test cases
6. 🎯 **Submit:** Ensure all 5 core deliverables complete before bonuses
