# API Documentation

> Complete REST API reference for Attack Path Analyzer backend

**Base URL:** `http://localhost:8000`
**API Prefix:** `/api`
**Response Format:** JSON
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

## Table of Contents

1. [Graph Operations](#graph-operations)
2. [Attack Path Analysis](#attack-path-analysis)
3. [Blast Radius Analysis](#blast-radius-analysis)
4. [Cycle Detection](#cycle-detection)
5. [Critical Node Analysis](#critical-node-analysis)
6. [Reporting](#reporting)
7. [Error Handling](#error-handling)

---

## Graph Operations

### GET /api/graph

**Description:** Retrieve the full graph in Cytoscape.js format (for visualization)

**Response (200 OK):**
```json
{
  "nodes": [
    {
      "data": {
        "id": "pod-webfront",
        "label": "web-frontend",
        "type": "pod",
        "risk": 7.5,
        "namespace": "default"
      }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "pod-webfront->sa-webapp",
        "source": "pod-webfront",
        "target": "sa-webapp",
        "relation": "uses",
        "weight": 2.5,
        "cve": "CVE-2024-1234"
      }
    }
  ]
}
```

---

### GET /api/graph/summary

**Description:** Get high-level graph statistics without full node/edge details

**Response (200 OK):**
```json
{
  "node_count": 41,
  "edge_count": 48,
  "is_dag": false,
  "sources": ["user-dev1", "internet"],
  "sinks": ["db-production", "billing-database"],
  "avg_risk": 6.8,
  "max_risk": 10.0,
  "cycle_count": 1
}
```

---

### POST /api/graph/reload

**Description:** Re-ingest cluster data from kubectl or reload from file

**Request:**
```json
{
  "source": "mock",  // or "kubectl"
  "scenario": "nokia_telecom"  // optional
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Graph reloaded from mock data",
  "nodes_loaded": 41,
  "edges_loaded": 48
}
```

---

## Attack Path Analysis

### POST /api/attack/path

**Description:** Find shortest attack path between two nodes using Dijkstra's algorithm

**Request:**
```bash
POST /api/attack/path
Content-Type: application/json

{
  "source": "user-dev1",
  "target": "db-production",
  "include_details": true
}
```

**Response (200 OK):**
```json
{
  "source": "user-dev1",
  "target": "db-production",
  "path": ["user-dev1", "pod-webfront", "sa-webapp", "secret-db-creds", "db-production"],
  "cost": 24.1,
  "hops": [
    {
      "from": "user-dev1",
      "to": "pod-webfront",
      "relation": "can-ssh",
      "weight": 2.5,
      "cve": null
    },
    {
      "from": "pod-webfront",
      "to": "sa-webapp",
      "relation": "uses",
      "weight": 3.2,
      "cve": "CVE-2024-1234",
      "cvss": 8.1
    },
    {
      "from": "sa-webapp",
      "to": "secret-db-creds",
      "relation": "bound-to-role-read",
      "weight": 1.0,
      "cve": null
    },
    {
      "from": "secret-db-creds",
      "to": "db-production",
      "relation": "unlocks",
      "weight": 17.4,
      "cve": null
    }
  ],
  "severity": "CRITICAL"
}
```

**Error Response (404):**
```json
{
  "error": "No path found",
  "source": "unknown-node",
  "target": "db-production",
  "detail": "Source node 'unknown-node' not found in graph"
}
```

**Parameters:**
- `source` (string, required) — Source node ID or label
- `target` (string, required) — Target node ID or label
- `include_details` (boolean, optional) — Include hop-by-hop details (default: true)

---

### GET /api/attack/auto

**Description:** Automatically detect the most dangerous attack path in the cluster

**Response (200 OK):**
```json
{
  "detected": true,
  "most_dangerous_path": {
    "source": "internet",
    "target": "billing-database",
    "path": ["internet", "web-frontend", "backend-sa", "admin-role", "db-credentials", "billing-database"],
    "cost": 3.2,
    "severity": "CRITICAL"
  },
  "explanation": "Public internet can reach billing database via web server privilege escalation"
}
```

---

## Blast Radius Analysis

### POST /api/blast/radius

**Description:** Find all nodes reachable from a source within N hops (BFS)

**Request:**
```json
{
  "source": "pod-webfront",
  "max_hops": 3
}
```

**Response (200 OK):**
```json
{
  "source": "pod-webfront",
  "max_hops": 3,
  "total_reachable": 13,
  "zones": {
    "0": [
      {
        "id": "pod-webfront",
        "label": "web-frontend",
        "type": "pod",
        "risk": 7.5
      }
    ],
    "1": [
      {
        "id": "sa-webapp",
        "label": "backend-sa",
        "type": "service_account",
        "risk": 6.8
      }
    ],
    "2": [
      {
        "id": "secret-db-creds",
        "label": "db-credentials",
        "type": "secret",
        "risk": 9.0
      }
    ],
    "3": [
      {
        "id": "db-production",
        "label": "production-db",
        "type": "database",
        "risk": 9.5
      }
    ]
  },
  "all_reachable": ["pod-webfront", "sa-webapp", "secret-db-creds", "db-production", ...]
}
```

**Parameters:**
- `source` (string, required) — Starting node ID or label
- `max_hops` (integer, optional) — Maximum hop distance (default: 3, min: 1, max: 10)

---

## Cycle Detection

### GET /api/cycles

**Description:** Detect all privilege escalation cycles in the graph (DFS)

**Response (200 OK):**
```json
{
  "cycle_count": 1,
  "cycles": [
    {
      "nodes": ["svc-service-a", "svc-service-b"],
      "length": 2,
      "severity": "HIGH",
      "chain": "svc-service-a → svc-service-b → svc-service-a"
    }
  ]
}
```

**Cycle Severity Levels:**
- **CRITICAL**: Cycle length ≤ 2 OR max node risk ≥ 8.0
- **HIGH**: Cycle length ≤ 4 OR max node risk ≥ 6.0
- **MEDIUM**: Max node risk ≥ 4.0
- **LOW**: All other cycles

---

## Critical Node Analysis

### GET /api/critical/nodes

**Description:** Identify critical nodes (bottlenecks) using betweenness centrality

**Query Parameters:**
- `top_n` (integer, optional) — Return top N nodes (default: 5, max: 20)

**Response (200 OK):**
```json
{
  "critical_nodes": [
    {
      "rank": 1,
      "node_id": "web-frontend",
      "node_type": "pod",
      "centrality_score": 0.847,
      "risk_score": 7.5,
      "combined_score": 0.809,
      "paths_eliminated": 32,
      "total_paths": 46,
      "elimination_percentage": 69.6,
      "impact_level": "CRITICAL"
    },
    {
      "rank": 2,
      "node_id": "api-server",
      "node_type": "pod",
      "centrality_score": 0.765,
      "risk_score": 8.2,
      "combined_score": 0.768,
      "paths_eliminated": 24,
      "total_paths": 46,
      "elimination_percentage": 52.2,
      "impact_level": "CRITICAL"
    }
  ]
}
```

---

### POST /api/simulate/remove

**Description:** Simulate the impact of removing a node from the graph

**Request:**
```json
{
  "node_id": "web-frontend",
  "source": "user-dev1",
  "target": "db-production"
}
```

**Response (200 OK):**
```json
{
  "node_removed": "web-frontend",
  "paths_before": 46,
  "paths_after": 14,
  "paths_broken": 32,
  "impact_percentage": 69.6,
  "impact_level": "CRITICAL",
  "new_shortest_path": {
    "path": ["user-dev1", "internal-api", "..."],
    "cost": 35.2
  }
}
```

---

## Reporting

### GET /api/report

**Description:** Generate complete security analysis report with AI narration

**Query Parameters:**
- `format` (string, optional) — "json" or "text" (default: "json")
- `include_remediation` (boolean, optional) — Include remediation advice (default: true)

**Response (200 OK):**
```json
{
  "report_id": "report-2026-04-04-124815",
  "generated_at": "2026-04-04T12:48:15Z",
  "cluster_name": "mock-prod-cluster",
  "summary": {
    "total_nodes": 41,
    "total_edges": 48,
    "total_attack_paths": 46,
    "total_cycles": 1,
    "overall_risk": "CRITICAL"
  },
  "attack_paths": [
    {
      "path_id": 1,
      "source": "user-dev1",
      "target": "db-production",
      "path": ["user-dev1", "pod-webfront", "sa-webapp", "secret-db-creds", "db-production"],
      "cost": 24.1,
      "severity": "CRITICAL"
    }
  ],
  "critical_nodes": [
    {
      "node_id": "web-frontend",
      "impact": "Removing this node breaks 32 of 46 attack paths (69.6%)"
    }
  ],
  "cycles": [
    {
      "nodes": ["svc-service-a", "svc-service-b"],
      "severity": "HIGH"
    }
  ],
  "remediation": [
    "Patch CVE-2024-1234 on web-frontend immediately",
    "Remove RoleBinding secret-reader from sa-webapp",
    "Break cycle: Revoke admin-grant from svc-service-b"
  ],
  "ai_narrative": "The cluster contains a critical privilege escalation path..."
}
```

---

## Health & Status

### GET /health

**Description:** Health check endpoint

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T12:48:15Z",
  "graph_loaded": true,
  "nodes": 41,
  "edges": 48
}
```

---

## Error Handling

### Error Response Format

All errors return JSON with HTTP status codes:

```json
{
  "error": "Error type",
  "detail": "Detailed error message",
  "status_code": 400
}
```

### Common Error Codes

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| 400 | Bad Request | Invalid input parameters | Check request body/query params |
| 404 | Not Found | Node not found in graph | Verify node ID exists |
| 409 | Graph Error | Algorithm failed on graph | Try --full-report to diagnose |
| 500 | Internal Server Error | Unexpected server error | Check backend logs |

### Example Error

**Request:** `POST /api/attack/path` with unknown source node

**Response (404):**
```json
{
  "error": "Node not found",
  "detail": "Source node 'unknown-node' does not exist in graph. Available sources: ['user-dev1', 'internet', ...]",
  "status_code": 404
}
```

---

## Authentication

Currently, the API has **no authentication** (suitable for hackathon/demo).

For production:
- Add JWT bearer tokens
- Implement RBAC for sensitive operations
- Use TLS for all endpoints

---

## Rate Limiting

No rate limiting in place for hackathon scale.

For production (large clusters):
- Implement rate limiting (100 requests/min per IP)
- Cache expensive computations (critical node analysis)
- Queue long-running analyses

---

## Performance Tips

### For Large Graphs (> 500 nodes)

1. **Limit path enumeration:**
   ```
   POST /api/attack/path
   {
     "source": "...",
     "target": "...",
     "max_path_length": 5
   }
   ```

2. **Use sampling for centrality:**
   ```
   GET /api/critical/nodes?sampling=true&sample_size=100
   ```

3. **Paginate cycle results:**
   ```
   GET /api/cycles?limit=10&offset=0
   ```

---

## Integration Examples

### Python (using requests)

```python
import requests

# Get blast radius
response = requests.post(
    "http://localhost:8000/api/blast/radius",
    json={"source": "pod-webfront", "max_hops": 3}
)
print(response.json())

# Get critical nodes
response = requests.get(
    "http://localhost:8000/api/critical/nodes?top_n=5"
)
print(response.json())
```

### cURL

```bash
# Full report
curl http://localhost:8000/api/report

# Blast radius
curl -X POST http://localhost:8000/api/blast/radius \
  -H "Content-Type: application/json" \
  -d '{"source": "pod-webfront", "max_hops": 3}'
```

### JavaScript (using fetch)

```javascript
// Attack path
const response = await fetch('http://localhost:8000/api/attack/path', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    source: 'user-dev1',
    target: 'db-production'
  })
});

const data = await response.json();
console.log(data);
```

---

## See Also
- [CLI_COMMAND_REFERENCE.md](CLI_COMMAND_REFERENCE.md) — Command-line interface
- [README.md](../README.md) — Project overview
- Interactive Docs: `http://localhost:8000/docs`
