# Cluster graph JSON schema (hackathon / organizer format)

This describes the JSON shape loaded by [`backend/app/core/cluster_graph_loader.py`](../backend/app/core/cluster_graph_loader.py) (`load_cluster_graph_file`, `parse_cluster_graph_document`). The CLI (`python main.py` from `backend/`) uses that loader. The module `hackathon_normalize.normalize_hackathon_graph` is a thin alias of `parse_cluster_graph_document`.

Reference file: [mock-cluster-graph.json](mock-cluster-graph.json).

## Top-level object

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | object | Optional. May include `cluster`, `generated`, `node_count`, `edge_count`, etc. |
| `nodes` | array | Required. Each element is a **node object**. |
| `edges` | array | Required. Each element is an **edge object** or (ignored) a comment-only object. |

Comment-only edge rows (e.g. `{"comment": "..."}`) are skipped during normalization.

## Node object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Stable graph identifier (used as NetworkX node key). |
| `type` | string | Yes | Resource type (e.g. `Pod`, `User`, `Database`). Normalized internally to lowercase snake_case where applicable (`ServiceAccount` → `service_account`). |
| `name` | string | No* | Display name; mapped to internal `label` when `label` is absent. |
| `label` | string | No* | If present with `risk` and without hackathon fields, node is treated as already internal-shaped. |
| `namespace` | string | No | Defaults to `"default"`. |
| `risk_score` | number | No* | 0–10; mapped to internal `risk`. Use `risk` instead for internal format. |
| `risk` | number | No* | Internal format risk score. |
| `is_source` | boolean | No | If true, node is treated as an attack **source** for path enumeration and blast-radius sources. |
| `is_sink` | boolean | No | If true, node is treated as an attack **sink** for path enumeration and critical-node analysis. |
| `cves` | array of string | No | CVE IDs affecting the node (stored on the graph for reporting). |

\*Either (`name` + `risk_score`) hackathon style or (`label` + `risk`) internal scenario style.

## Edge object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Tail node `id`. |
| `target` | string | Yes | Head node `id`. |
| `relationship` | string | No* | Organizer field; mapped to internal `relation`. |
| `relation` | string | No* | Internal relation name. |
| `weight` | number | No | Edge weight for Dijkstra / path risk sums (default `5.0`). |
| `risk` | number | No | Optional separate risk display; defaults to `weight` if omitted. |
| `cve` | string or null | No | CVE ID for this edge (shown in kill-chain text). |
| `cvss` | number or null | No | CVSS score when `cve` is set. |

## Example node and edge

```json
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
```

```json
{
  "source": "user-dev1",
  "target": "pod-webfront",
  "relationship": "can-exec",
  "weight": 5.0,
  "cve": "CVE-2024-1234",
  "cvss": 8.1
}
```

## Internal graph (after normalization)

- Nodes carry: `label`, `type`, `risk`, `namespace`, `metadata`, and when present `is_source`, `is_sink`, `cves`.
- Edges carry: `relation`, `weight`, `risk`, and when present `cve`, `cvss`.

The application never writes back to the input JSON file; ingestion is read-only.
