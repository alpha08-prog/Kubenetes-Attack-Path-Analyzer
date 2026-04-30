# Cluster Graph JSON Schema

This document describes the input JSON contract for the attack-path analyzer.
It is the authoritative reference for anyone authoring a new scenario file
(`data/scenarios/*.json`) or producing output from an external collector.

The contract is reverse-engineered from the live ingestion code:

- `backend/app/core/graph_builder.py` (`create_graph`)
- `backend/app/core/cluster_graph_loader.py` (`parse_cluster_graph_document`)

Where this document and older prose docs disagree, **this document wins** —
it reflects what the code actually does.

---

## Top-level structure

```json
{
  "metadata": { ... optional, free-form ... },
  "meta":     { ... optional alias for metadata used by Nokia scenarios ... },
  "nodes":    [ { ... node ... }, ... ],
  "edges":    [ { ... edge ... }, ... ]
}
```

Only `nodes` is strictly required. `edges` defaults to an empty list. The
top-level object may carry an optional `metadata` (or `meta`) block; the loader
uses `metadata.node_count` / `metadata.edge_count` only as a sanity check
(`graph_counts_match_file_metadata`) and otherwise ignores it.

> *Note:* the loader accepts both `metadata` and `meta` as the top-level
> metadata key (historical — different scenario sets use different spellings).
> Either is valid; do not mix both in one file.

Two flavors of node shape are accepted:

1. **Internal / Nokia shape** — node has `label` + `risk` and no `name` / `risk_score`.
   Passed through unchanged. Used by `data/scenarios/*.json`.
2. **Rubric / cluster-graph shape** — node has `name` and/or `risk_score`.
   Normalized: `name` -> `label`, `risk_score` -> `risk`, `type` lowercased
   and aliased (e.g. `ServiceAccount` -> `service_account`,
   `ExternalActor` -> `external_actor`). Used by `docs/mock-cluster-graph.json`.

The loader detects the flavor per-node, so a single file can mix both if needed.

---

## Node object

| Field        | Type             | Required | Meaning |
|--------------|------------------|----------|---------|
| `id`         | string           | yes      | Unique identifier. Used as the NetworkX node key and as the value of `source` / `target` on edges. |
| `type`       | string           | no       | Resource kind. Free-form; canonical values are `pod`, `user`, `service_account`, `role`, `cluster_role`, `secret`, `database`, `configmap`, `node`, `service`, `namespace`, `external_actor`, `persistent_volume`. Rubric capitalizations (`ServiceAccount`, `ExternalActor`) are auto-normalized. Default: `"unknown"`. |
| `label`      | string           | no       | Human-readable name shown in the UI. Falls back to `name`, then `id`. |
| `name`       | string           | no       | Rubric alias for `label`. Used only when `label` is absent. |
| `risk`       | number (0–10)    | no       | Canonical numeric risk on the graph. Default: `0.0`. If absent, falls back to `risk_score`. |
| `risk_score` | number (0–10)    | no       | Rubric alias for `risk`. Both fields are preserved on the in-memory node so heuristics can read either. |
| `namespace`  | string           | no       | Kubernetes namespace. Default: `"default"`. |
| `metadata`   | object           | no       | Free-form bag of details (image, phase, has_wildcard, etc.). Passed through verbatim. |
| `is_source`  | boolean          | no       | Marks this node as an explicit attacker entry point. Used by `find_graph_sources`. When any node has `is_source: true`, the heuristic fallback is skipped entirely. |
| `is_sink`    | boolean          | no       | Marks this node as an explicit attack target. Used by `find_graph_sinks`. Same precedence rule as `is_source`. |
| `cves`       | array of strings | no       | CVE IDs associated with the node (e.g. `["CVE-2024-1234"]`). Currently informational — surfaced in the UI and used by enrichment, not by Dijkstra. |

A minimum viable node is just `{"id": "..."}`. Everything else has a default.

---

## Edge object

| Field          | Type             | Required | Meaning |
|----------------|------------------|----------|---------|
| `source`       | string           | yes      | `id` of the source node. Edge is **silently skipped** if the node is missing. |
| `target`       | string           | yes      | `id` of the target node. Edge is silently skipped if missing. |
| `relation`     | string           | no       | Relationship label (e.g. `uses`, `bound-to`, `can-read`). Default: `"accesses"`. |
| `relationship` | string           | no       | Rubric alias for `relation`. If both are present, `relation` wins; otherwise either is accepted and both fields are preserved on the in-memory edge. |
| `weight`       | number (0–10)    | no       | **Exploitability cost.** This is the value Dijkstra minimizes. **Lower = easier to exploit.** Default: `5.0`. See "Edge weight semantics" below. |
| `risk`         | number (0–10)    | no       | Display value used for the cost reported in `total_cost` (sum of `risk` along the path). Defaults to whatever `weight` is, so authors can omit it for symmetric edges. |
| `cve`          | string \| null   | no       | A single CVE ID this edge represents (e.g. `"CVE-2024-1234"`). Surfaced in path hops. |
| `cvss`         | number \| null   | no       | CVSS base score for the CVE. Surfaced in path hops alongside `cve`. |

A minimum viable edge is `{"source": "a", "target": "b"}`; it gets
`relation = "accesses"`, `weight = 5.0`, `risk = 5.0`.

---

## Edge weight semantics (read this carefully — C-3)

`weight` is **exploitability cost on a 0–10 scale where lower means easier to
exploit**. Dijkstra calls `nx.dijkstra_path(G, source, target, weight="weight")`
and minimizes the sum, so:

- A trivially exploitable edge (default creds, public RCE) should be `weight: 1.0`.
- A merely possible edge (requires auth, internal-only) should be `weight: 7.0`–`9.0`.
- The default when `weight` is omitted is `5.0`.

**There is no `weight = 10 - risk` inversion in the code.** Older prose in
`README.md` and `dijkstra.py`'s docstring describes such a formula; that
formula is not implemented. The ingestion code in
`graph_builder.py` (lines 60–66) and `cluster_graph_loader.py` (lines 106–107)
treats `weight` as the literal exploitability cost. Authors must pre-compute
this themselves (e.g. from CVSS exploitability sub-score) — the loader does
not derive it.

Fallback rules used by the loader:

1. If `weight` is present, use it directly.
2. If `weight` is absent, default to `5.0`.
3. If `risk` is absent, it defaults to whatever `weight` ended up as.
4. If only `risk` is provided (no `weight`), `risk` is used as-is for the cost
   total, but `weight` will still be the default `5.0` for Dijkstra. To make
   Dijkstra prefer a risky edge you **must** set `weight` low — setting only
   `risk` high will not change pathfinding.

This means `risk` and `weight` are independent dimensions:

- `weight` drives **which path Dijkstra picks**.
- `risk` drives **the displayed total cost** of that path.

Authoring tip: for most scenarios you can set them equal. Only diverge them
when you want the displayed cost to reflect impact while pathfinding reflects
exploit difficulty.

---

## CVE fields

CVE data lives in two places and is purely informational at the moment:

- **Node-level `cves`** — array of CVE IDs attached to the resource itself
  (e.g. a pod running a vulnerable image). Surfaced in the node panel.
- **Edge-level `cve` + `cvss`** — a single CVE that explains *why* this edge
  exists (e.g. an RCE that lets the attacker pivot from `source` to `target`),
  plus its CVSS base score. Surfaced per-hop in the Dijkstra output (`hops[i].cve`,
  `hops[i].cvss`) and in narration prompts.

Both `cve` and `cvss` accept JSON `null`. Neither field affects Dijkstra cost
today — to penalize a vulnerable edge, set its `weight` low.

---

## Minimal valid example

```json
{
  "nodes": [
    {"id": "pod-web", "type": "pod", "risk": 7.0, "is_source": true},
    {"id": "db-prod", "type": "database", "risk": 9.5, "is_sink": true}
  ],
  "edges": [
    {"source": "pod-web", "target": "db-prod", "relation": "connects", "weight": 2.0}
  ]
}
```

This produces a 2-node graph with one direct attack path of cost `2.0`
(Dijkstra) and `2.0` (displayed total, since `risk` defaulted to `weight`).

---

## Fuller example with CVEs

```json
{
  "metadata": {"cluster": "demo", "node_count": 4, "edge_count": 3},
  "nodes": [
    {"id": "internet",   "type": "ExternalActor",  "name": "internet",        "risk_score": 10.0, "is_source": true},
    {"id": "pod-web",    "type": "Pod",            "name": "web-frontend",    "risk_score": 7.5,  "cves": ["CVE-2024-1234"]},
    {"id": "sa-webapp",  "type": "ServiceAccount", "name": "sa-webapp",       "risk_score": 5.5},
    {"id": "db-prod",    "type": "Database",       "name": "production-db",   "risk_score": 10.0, "is_sink": true}
  ],
  "edges": [
    {"source": "internet",  "target": "pod-web",   "relationship": "reaches",         "weight": 2.0, "cve": "CVE-2024-1234", "cvss": 8.1},
    {"source": "pod-web",   "target": "sa-webapp", "relationship": "uses",            "weight": 3.0},
    {"source": "sa-webapp", "target": "db-prod",   "relationship": "grants-access-to","weight": 4.0, "risk": 9.0}
  ]
}
```

Notes on this example:

- Uses the rubric flavor (`name`, `risk_score`, capitalized `type`,
  `relationship`). All are normalized at load time.
- Edge 3 separates `weight` (4.0, used by Dijkstra) from `risk` (9.0, used in
  the displayed total cost). Dijkstra picks this path because the weight is
  low; the UI shows a high impact because the risk is high.
- Edge `cve` / `cvss` are reported per-hop but do not influence routing.

---

## Quick reference: defaults applied by the loader

| Field          | Default if omitted |
|----------------|--------------------|
| node `type`    | `"unknown"`        |
| node `label`   | `name` -> `id`     |
| node `risk`    | `risk_score` -> `0.0` |
| node `namespace` | `"default"`      |
| node `metadata`  | `{}`             |
| edge `relation`  | `"accesses"`     |
| edge `weight`    | `5.0`            |
| edge `risk`      | value of `weight` |

Edges referencing nodes that are not in `nodes[]` are silently dropped; the
loader logs a debug message and a warning with the skipped count.
