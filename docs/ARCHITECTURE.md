# Architecture & Design Document

> System architecture, design decisions, and component interactions for Attack Path Analyzer

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Layer Architecture](#layer-architecture)
3. [Data Flow](#data-flow)
4. [Component Details](#component-details)
5. [Design Decisions](#design-decisions)
6. [Scalability](#scalability)
7. [Security Considerations](#security-considerations)

---

## System Overview

The Attack Path Analyzer is a **three-tier application**:

```
┌─────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                      │
│  ┌──────────────────────┐        ┌──────────────────┐   │
│  │  React Frontend      │        │  CLI Tool        │   │
│  │  (Cytoscape.js)      │        │  (Python argparse)   │
│  └──────────┬───────────┘        └────────┬─────────┘   │
│             │ REST                         │ Subprocess  │
└─────────────┼─────────────────────────────┼─────────────┘
              │                             │
┌─────────────▼─────────────────────────────▼─────────────┐
│                   APPLICATION LAYER                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │           FastAPI REST API Server                │   │
│  │  ┌────────┬────────┬────────┬────────────────┐  │   │
│  │  │ Routes │ Routes │ Routes │ Routes         │  │   │
│  │  │ Graph  │ Attack │ Cycles │ Critical Nodes │  │   │
│  │  └────────┴────────┴────────┴────────────────┘  │   │
│  │                                                  │   │
│  │  ┌──────────────────────────────────────────┐  │   │
│  │  │        Service Layer (Business Logic)     │  │   │
│  │  │  ┌─────────┬─────────┬──────────────┐   │  │   │
│  │  │  │ Analysis│  Blast  │ Remediation  │   │  │   │
│  │  │  │ Service │ Service │ Service      │   │  │   │
│  │  │  └─────────┴─────────┴──────────────┘  │  │   │
│  │  │  ┌──────────────────────────────────┐  │  │   │
│  │  │  │  Report & Narrative Generation   │  │  │   │
│  │  │  └──────────────────────────────────┘  │  │   │
│  │  └──────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Algorithm Layer (NetworkX)              │  │
│  │  ┌──────────┬──────────┬──────────┬──────────┐  │   │
│  │  │   BFS    │ Dijkstra │   DFS    │Centrality│  │   │
│  │  │(BlastRad)│(ShortPath)│(Cycles)  │(Critical│  │   │
│  │  └──────────┴──────────┴──────────┴──────────┘  │   │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────┐
│                    DATA LAYER                          │
│  ┌──────────────┐    ┌──────────────────┐             │
│  │ In-Memory    │    │ SQLite History   │             │
│  │ NetworkX     │    │ (optional)       │             │
│  │ DiGraph      │    │                  │             │
│  └──────────────┘    └──────────────────┘             │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ File System (cluster-graph.json, scenarios)    │  │
│  └────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

---

## Layer Architecture

### 1. Presentation Layer

**CLI Interface** (`backend/app/cli.py`)
- Entry point: `python main.py [options]`
- Argument parsing with argparse
- Exit codes: 0 (success), 1 (runtime error), 2 (usage error)
- UTF-8 output handling for cross-platform compatibility

**Web UI** (`frontend/src/`)
- React 18 + Vite
- Cytoscape.js for interactive graph visualization
- Real-time API integration via Axios
- Risk-based node coloring (red = high risk, green = low risk)

---

### 2. Application Layer

**FastAPI Server** (`backend/app/main.py`)
```
- Port: 8000 (configurable)
- Middleware: CORS enabled for frontend
- Interactive docs: /docs (Swagger UI)
- Health check: /health
```

**Route Modules** (`backend/app/api/routes_*.py`)
| Route File | Endpoints | Purpose |
|---|---|---|
| `routes_graph.py` | `/api/graph`, `/api/graph/summary`, `/api/graph/reload` | Graph access and management |
| `routes_attack.py` | `/api/attack/path`, `/api/attack/auto` | Attack path detection |
| `routes_blast.py` | `/api/blast/radius` | Blast radius analysis |
| `routes_cycles.py` | `/api/cycles` | Cycle detection |
| `routes_critical.py` | `/api/critical/nodes`, `/api/simulate/remove` | Critical node analysis |
| `routes_report.py` | `/api/report` | Report generation |
| `routes_cve.py` | `/api/cves` | CVE data endpoints |

---

### 3. Service Layer (Business Logic)

**Core Services:**

```
analysis_service.py
├─ Orchestrates all algorithms
├─ Aggregates results
└─ Formats responses

blast_service.py
├─ BFS blast radius computation
├─ Zone grouping by hop distance
└─ Reachability analysis

attack_service.py
├─ Dijkstra shortest path
├─ Entry point + target detection
└─ Multi-path enumeration

kill_chain_report.py
├─ Report formatting
├─ Severity classification
├─ Remediation generation
└─ AI narration integration (Gemini)

remediation_service.py
├─ Context-aware remediation
├─ Security best practices
└─ Impact estimation
```

---

### 4. Algorithm Layer

**Graph Algorithms** (NetworkX wrapper):

| Algorithm | File | Purpose | Complexity | Output |
|-----------|------|---------|-----------|--------|
| **BFS** | `bfs.py` | Find reachable nodes | O(V+E) | Zones by hop distance |
| **Dijkstra** | `dijkstra.py` | Shortest attack path | O((V+E)logV) | Single path + cost |
| **DFS** | `dfs_cycles.py` | Cycle detection | O((V+E)C) | List of cycles |
| **Betweenness Centrality** | `centrality.py` | Critical nodes | O(VE) or O(V²) | Ranked node list |

**Why NetworkX?**
- Pure Python, zero C dependencies
- All required algorithms built-in
- Faster to develop than custom implementations
- Suitable for Hackathon scale (tested to 500 nodes)
- Easy swap to Neo4j for production (> 5000 nodes)

---

### 5. Data Layer

**Graph Representation** (In-Memory)
```python
G = nx.DiGraph()

# Nodes
G.nodes[node_id] = {
    'label': 'pod-web',
    'type': 'pod',
    'risk': 7.5,
    'namespace': 'default',
    'is_source': True/False,
    'is_sink': True/False,
    'cves': ['CVE-2024-1234']
}

# Edges
G[source][target] = {
    'relation': 'uses',
    'weight': 2.5,
    'cve': 'CVE-2024-1234',
    'cvss': 8.1
}
```

**File Storage**
- `docs/mock-cluster-graph.json` — Standard cluster-graph format
- `data/scenarios/*.json` — Demo scenarios
- `history.db` (optional) — SQLite for run history

---

## Data Flow

### Request Flow (Example: Full Report)

```
User Request: python main.py --full-report
     ↓
[CLI Parser] app/cli.py
     ├─ Parse arguments
     ├─ Resolve input file (default: docs/mock-cluster-graph.json)
     └─ Validate parameters
     ↓
[Graph Loader] core/cluster_graph_loader.py
     ├─ Load JSON
     ├─ Normalize schema (hackathon → internal format)
     ├─ Validate node/edge presence
     └─ Create nx.DiGraph
     ↓
[Algorithm Execution]
     ├─ BFS (blast_radius from all sources)
     ├─ Dijkstra (shortest path between all source/sink pairs)
     ├─ DFS (cycle detection)
     └─ Centrality (critical node ranking)
     ↓
[Report Generation] services/kill_chain_report.py
     ├─ Aggregate results
     ├─ Classify severity
     ├─ Generate remediation
     ├─ Call Gemini AI (if GEMINI_API_KEY set)
     └─ Format output (text/JSON)
     ↓
[Output]
     └─ Print to stdout with UTF-8 encoding
```

### API Request Flow (Example: GET /api/critical/nodes)

```
HTTP Request: GET /api/critical/nodes?top_n=5
     ↓
[FastAPI Router] api/routes_critical.py
     ├─ Validate query parameters
     └─ Call service layer
     ↓
[Critical Node Service]
     ├─ nx.betweenness_centrality(G)
     ├─ Combine with risk scores (60/40 weighting)
     ├─ Sort by combined score
     └─ Return top 5 nodes
     ↓
[Response Formatter]
     ├─ Convert to Pydantic model
     ├─ Serialize to JSON
     └─ Set HTTP 200 status
     ↓
JSON Response
{
  "critical_nodes": [
    { "rank": 1, "node_id": "web-frontend", ... }
  ]
}
```

---

## Component Details

### Core Components

**cluster_graph_loader.py**
- Parses cluster-graph.json (hackathon format)
- Validates schema compliance
- Normalizes field names (risk_score → risk, etc.)
- Handles missing optional fields (cves, namespace)
- Returns: Ready-to-use nx.DiGraph

**graph_builder.py**
- Constructs graph from normalized node/edge lists
- Assigns risk scores (based on CVE data or heuristics)
- Reads edge weights from the input (no inversion — `weight` is the literal exploitability cost; see [CLUSTER_GRAPH_SCHEMA.md](CLUSTER_GRAPH_SCHEMA.md))
- Creates bidirectional mappings (ID ↔ label)

**risk_engine.py**
- CVSS score lookups from NVD API
- Fallback to hardcoded known CVEs
- Heuristic scoring for misconfiguration patterns
- Caches scores to avoid repeated API calls

**Models** (`backend/app/models/`)
```
node.py        → Pydantic NodeModel
edge.py        → Pydantic EdgeModel
response.py    → API response schemas
snapshot.py    → Graph snapshot for history
```

### Service Components

**analysis_service.py**
- Main orchestrator
- Runs all 4 algorithms in sequence
- Aggregates results
- Handles errors gracefully
- Returns structured AnalysisResult

**kill_chain_report.py**
- Formats raw algorithm output
- Generates readable report sections
- Integrates AI narration
- Implements remediation logic
- Outputs attack paths, cycles, critical nodes

---

## Design Decisions

### 1. Why Directed Weighted Graph?

**Decision:** Use `nx.DiGraph` with weighted edges

**Rationale:**
- Kubernetes RBAC is directional (role binding = one-way permission)
- Weight models exploitability (lower cost = easier path)
- Edges carry `weight` as exploitability cost (lower = easier); Dijkstra minimizes the sum, so it naturally finds the easiest attacker path
- DiGraph naturally represents attack flow direction

**Alternative considered:** Undirected graph
- Would miss attack directionality
- Symmetric permissions don't exist in K8s

---

### 2. Why BFS for Blast Radius?

**Decision:** Use BFS instead of DFS or other traversals

**Rationale:**
- Groups results by hop distance (concentric rings)
- Configurable depth limit (important for large graphs)
- O(V+E) linear time — very fast
- No weight consideration needed — speed is the metric

**Why not Dijkstra?**
- Overkill — we need reachability, not shortest paths
- Slower: O((V+E)logV) vs O(V+E)

---

### 3. Why Betweenness Centrality + Risk Weighting?

**Decision:** Use combined score = 0.6 × centrality + 0.4 × risk_score

**Rationale:**
- Centrality alone misses risky low-centrality nodes
- Risk alone misses structural chokepoints
- 60/40 split validated on demo scenario (web-frontend ranks #1)
- Explainable to security teams

**Example:**
```
Node A: Centrality 0.9, Risk 3.0 → Score 0.72
Node B: Centrality 0.6, Risk 9.0 → Score 0.60
→ Node A ranks higher (structural importance > raw risk)
```

---

### 4. Why SQLite for History?

**Decision:** Optional SQLite backend for run history

**Rationale:**
- Zero configuration (file-based)
- WAL mode enables concurrent reads
- Sufficient for hackathon scale (< 10k runs)
- Swappable for PostgreSQL in production

**Schema:**
```sql
CREATE TABLE analysis_runs (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    cluster_name TEXT,
    node_count INTEGER,
    attack_path_count INTEGER,
    critical_node TEXT
);
```

---

### 5. Why Gemini for AI Narration?

**Decision:** Google Gemini 2.0 Flash for AI-generated narratives

**Rationale:**
- Free tier (up to 15 requests/minute)
- 50k context window (fits full attack report)
- Fast response time (suitable for real-time API)
- Structured prompts ensure consistency

**Fallback:** If API unavailable, returns structured JSON report (no AI text)

---

## Scalability

### Current Limits (NetworkX)

| Metric | Tested | Limit | Recommendation |
|--------|--------|-------|-----------------|
| Nodes | 500 | ~1000 | Use approximate algorithms |
| Edges | 3000 | ~5000 | Sample for analysis |
| Runtime | 200-500ms | 1-2s | Implement caching |

### Scaling Strategies

**For 1000-5000 nodes:**
1. Approximate betweenness centrality (sample 100 nodes)
2. Limit path enumeration depth (max_path_length=5)
3. Implement result caching (Redis)
4. Run expensive operations asynchronously

**For 5000+ nodes (Production):**
1. Replace NetworkX with Neo4j
2. Use Neo4j's native algorithms (Cypher queries)
3. Implement graph partitioning (analyze subgraphs)
4. Cache all computed results
5. Queue long-running analyses

### Code Changes Needed for Neo4j Migration

**Easy swap (same interfaces):**
```python
# graph_builder.py
if USE_NEO4J:
    from neo4j_backend import build_graph
else:
    from networkx_backend import build_graph
```

**Algorithms:** Same API (BFS, Dijkstra, centrality)
**Services:** No changes required
**Routes:** No changes required

---

## Security Considerations

### Input Validation

**Graph File:**
- JSON schema validation (Pydantic)
- Node ID format check (no special chars)
- Risk score bounds (0-10)
- Edge weight positivity check

**API Parameters:**
- Query string validation (type checking)
- Request body schema validation (Pydantic)
- Rate limiting (planned for production)
- CORS configured for frontend origin only

### Data Privacy

**Important:** This tool processes sensitive cluster information
- Run on air-gapped / internal networks only
- Do not expose API publicly without authentication
- Cluster data is not logged to disk (in-memory only)
- AI narration sends data to Google (configure if sensitive)

### Algorithm Safety

- **No infinite loops:** All algorithms have depth/iteration limits
- **Memory safe:** NetworkX handles memory management
- **No data mutation:** Original graph copied before each removal simulation
- **Error handling:** All paths gracefully handle missing nodes/edges

---

## Deployment Architectures

### Single Container (Demo/Hackathon)

```
┌────────────────┐
│  Docker Image  │
│  ┌──────────┐  │
│  │FastAPI   │  │
│  │+ Frontend│  │
│  └──────────┘  │
└────────────────┘
      ↓ 8000
   Browser
```

### Multi-Container (Production)

```
┌──────────────────────────────────────┐
│       Docker Compose                 │
│  ┌──────────┐  ┌──────────┐         │
│  │ Backend  │  │ Frontend │         │
│  │(FastAPI) │  │(React)   │         │
│  └────┬─────┘  └────┬─────┘         │
│       └───────┬─────┘               │
│        ┌──────▼──────┐              │
│        │   nginx     │              │
│        │  (reverse   │              │
│        │   proxy)    │              │
│        └─────────────┘              │
└──────────────────────────────────────┘
    Port: 80/443 (external)
```

---

## See Also
- [README.md](../README.md) — Project overview
- [algorithms.md](algorithms.md) — Algorithm deep-dive
- [CLUSTER_GRAPH_SCHEMA.md](CLUSTER_GRAPH_SCHEMA.md) — Data format
- [CLI_COMMAND_REFERENCE.md](CLI_COMMAND_REFERENCE.md) — CLI usage
