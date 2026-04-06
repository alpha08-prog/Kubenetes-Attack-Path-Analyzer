# CLI Command Reference Guide

> Complete guide to all command-line interface options for the Attack Path Analyzer

## Quick Reference

```bash
# Run from backend/ directory after: pip install -r requirements.txt

python main.py --help                    # Show help
python main.py --full-report             # Complete security analysis
python main.py --blast-radius --source pod-webfront --hops 3
python main.py --source user-dev1 --target db-production
python main.py --cycles                  # Detect privilege escalation loops
python main.py --critical-node           # Find critical chokepoints
python main.py --input <path> [options]  # Specify custom graph file
```

---

## Commands in Detail

### 1. Full Security Report

**Command:**
```bash
python main.py --full-report
```

**What it does:**
- Runs all algorithms (BFS, Dijkstra, DFS, centrality analysis)
- Generates a complete kill chain report with remediation advice
- Outputs attack paths, blast radius, cycles, and critical nodes
- Exit code: 0 on success, 1 on error

**Expected output (excerpt):**
```
==================================================================
  KILL CHAIN REPORT  -  2026-04-04 12:48:15
  Cluster : mock-prod-cluster
  Nodes   : 41  |  Edges: 48
==================================================================

[ SECTION 1 - ATTACK PATH DETECTION ]
  46 attack path(s) detected

  Path #1  |  3 hops  |  Risk Score: 9.5  [CRITICAL]
  dev-1 → web-frontend [CVE-2024-1234, CVSS 8.1]
       → sa-webapp → secret-reader → db-credentials → production-db

[ SECTION 2 - BLAST RADIUS ]
  From: web-frontend | Hops: 3
  Hop 1 (1 node):  sa-webapp, internal-api-svc
  Hop 2 (3 nodes): secret-reader, tls-cert, api-key
  Hop 3 (2 nodes): db-credentials, secret-admin-token

[ SECTION 3 - PRIVILEGE ESCALATION CYCLES ]
  ✓ 1 cycle detected

  Cycle #1 [HIGH RISK]
  svc-service-a → svc-service-b → svc-service-a
  (mutual admin grant allows privilege compounding)

[ SECTION 4 - CRITICAL NODE ANALYSIS ]
  web-frontend (Pod)
  Betweenness Centrality: 0.847
  Paths Eliminated if Removed: 32 of 46 (69.6%)
  Recommendation: Isolate with network policies; patch CVE-2024-1234

[ SECTION 5 - REMEDIATION SUMMARY ]
  • Remove RoleBinding secret-reader from sa-webapp
  • Patch CVE-2024-1234 on web-frontend
  • Break cycle: Revoke admin-grant from service-b to service-a
  • Network isolation: Move web-frontend to restricted namespace
```

**Options:**
- `--input <file>` — Use custom graph file (default: `docs/mock-cluster-graph.json`)
- `--path-cutoff <N>` — Limit path enumeration depth (for large graphs)

---

### 2. Blast Radius Analysis (BFS)

**Command:**
```bash
python main.py --blast-radius --source <node-id> --hops <N>
```

**What it does:**
- Maps all resources reachable from a compromised node within N hops
- Groups results by hop distance (concentric rings)
- Shows the "blast radius" of a compromise

**Example:**
```bash
python main.py --blast-radius --source pod-webfront --hops 3
```

**Expected output:**
```
BLAST RADIUS ANALYSIS
====================
Source Node: pod-webfront (Pod) | Max Hops: 3

Hop 0 (Compromised):
  • pod-webfront (Pod, risk: 7.5)

Hop 1 (Direct access):
  • sa-webapp (ServiceAccount, risk: 6.8)
  • internal-api-svc (Service, risk: 5.2)
  • sidecar-proxy (Container, risk: 4.0)

Hop 2 (2 edges from source):
  • secret-reader (Role, risk: 7.5)
  • tls-cert (Secret, risk: 6.0)
  • api-key (Secret, risk: 7.0)
  • cluster-admin (Role, risk: 9.5)
  • api-server (Pod, risk: 8.2)

Hop 3 (3 edges from source):
  • db-credentials (Secret, risk: 9.0)
  • secret-admin-token (Secret, risk: 8.5)
  • sa-worker (ServiceAccount, risk: 5.5)
  • db-url-config (ConfigMap, risk: 4.5)

Total Reachable: 13 nodes (including source)
Time Complexity: O(V + E) | Execution: 2ms
```

**Parameters:**
- `--source NODE` — Starting node ID or label (required)
- `--hops N` — Maximum hop distance (default: 3)
- `--input FILE` — Custom graph file

---

### 3. Shortest Attack Path (Dijkstra)

**Command:**
```bash
python main.py --source <source-node> --target <target-node>
```

**What it does:**
- Finds the easiest attack path from source to target
- Uses weighted edges (risk-based costs)
- Shows the "most dangerous" route an attacker would take

**Example:**
```bash
python main.py --source user-dev1 --target db-production
```

**Expected output:**
```
SHORTEST ATTACK PATH (DIJKSTRA)
===============================
Source: user-dev1 (User)  →  Target: db-production (Database)

Optimal Attack Path:
  user-dev1 (User, risk: 5.0)
    ↓ [can-ssh-to, weight: 2.0]
  pod-webfront (Pod, risk: 7.5)
    ↓ [uses, weight: 3.2, CVE-2024-1234 CVSS:8.1]
  sa-webapp (ServiceAccount, risk: 6.8)
    ↓ [bound-to, weight: 0.5]
  role-secret-reader (Role, risk: 7.5)
    ↓ [can-read, weight: 1.0]
  secret-db-creds (Secret, risk: 9.0)
    ↓ [unlocks, weight: 0.5]
  db-production (Database, risk: 9.5)

Path Length: 5 hops
Total Cost: 24.1 (out of max 50.0)
Risk Level: [CRITICAL]

How to interpret cost:
  • Low cost (< 15): Very exploitable, high-priority remediation
  • Medium cost (15-30): Moderate risk, standard monitoring
  • High cost (> 30): Less likely, but still concerning

Remediation Actions (in priority order):
  1. Patch CVE-2024-1234 on pod-webfront (immediately)
  2. Remove RoleBinding: role-secret-reader from sa-webapp
  3. Revoke read access: role-secret-reader on secret-db-creds
  4. Rotate database credentials in secret-db-creds
```

**Parameters:**
- `--source NODE` — Source node ID or label (required)
- `--target NODE` — Target node ID or label (required)
- `--input FILE` — Custom graph file

---

### 4. Cycle Detection (DFS)

**Command:**
```bash
python main.py --cycles
```

**What it does:**
- Detects privilege escalation loops in the graph
- Identifies circular permission relationships
- Classifies severity (Critical/High/Medium/Low)

**Expected output:**
```
PRIVILEGE ESCALATION CYCLES (DFS)
==================================
Total Cycles Found: 1

Cycle #1 [HIGH RISK]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  svc-service-a (Role, risk: 8.0)
    ↓ [can-impersonate]
  svc-service-b (Role, risk: 8.5)
    ↓ [admin-grant]
  svc-service-a (Role, risk: 8.0)

Cycle Length: 2 nodes
Max Node Risk: 8.5
Severity: HIGH

Why This Matters:
  This creates a privilege escalation loop where an attacker can:
  1. Compromise svc-service-a
  2. Use impersonation to gain svc-service-b's elevated permissions
  3. Use admin-grant to escalate back to svc-service-a with MORE permissions
  4. Repeat indefinitely (no permission ceiling)

Immediate Actions:
  • Break the cycle: Revoke admin-grant from svc-service-b to svc-service-a
  • OR: Remove can-impersonate permission from svc-service-a
  • Verify: Re-run --cycles to confirm no path back exists
```

**Parameters:**
- `--input FILE` — Custom graph file

---

### 5. Critical Node Analysis

**Command:**
```bash
python main.py --critical-node
```

**What it does:**
- Identifies nodes whose removal would break the most attack paths
- Uses betweenness centrality (graph algorithm)
- Shows "chokepoints" in the cluster architecture

**Expected output:**
```
CRITICAL NODE ANALYSIS
======================
Algorithm: Betweenness Centrality + Risk Weighting (60% centrality, 40% risk)

Top 5 Critical Nodes (by impact on attack paths):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rank 1: web-frontend (Pod)
  Centrality Score: 0.847
  Risk Score: 7.5 / 10
  Combined Score: 0.809
  Paths Eliminated if Removed: 32 of 46 (69.6%)
  Impact Level: CRITICAL

  Recommendation:
    • Isolate with network policies (restrict inbound/outbound)
    • Patch CVE-2024-1234 immediately
    • Implement intrusion detection on this pod
    • Monitor for privilege escalation attempts

Rank 2: api-server (Pod)
  Centrality Score: 0.765
  Risk Score: 8.2 / 10
  Combined Score: 0.768
  Paths Eliminated if Removed: 24 of 46 (52.2%)
  Impact Level: CRITICAL

  Recommendation:
    • Run behind TLS with mutual authentication
    • Enable audit logging
    • Restrict access to cluster-admin identities only

Rank 3: role-secret-reader (Role)
  Centrality Score: 0.623
  Risk Score: 7.5 / 10
  Combined Score: 0.617
  Paths Eliminated if Removed: 18 of 46 (39.1%)
  Impact Level: HIGH

  Recommendation:
    • Review and minimize permissions (principle of least privilege)
    • Audit all bindings to this role
    • Consider splitting into more granular roles

Rank 4: secret-db-creds (Secret)
  Centrality Score: 0.512
  Risk Score: 9.0 / 10
  Combined Score: 0.535
  Paths Eliminated if Removed: 12 of 46 (26.1%)
  Impact Level: HIGH

  Recommendation:
    • Move credentials to secret management system (Vault, Sealed Secrets)
    • Rotate credentials immediately
    • Implement automatic rotation policy (weekly)

Rank 5: cluster-admin (Role)
  Centrality Score: 0.401
  Risk Score: 10.0 / 10
  Combined Score: 0.480
  Paths Eliminated if Removed: 9 of 46 (19.6%)
  Impact Level: MEDIUM

  Recommendation:
    • Audit all cluster-admin bindings
    • Create least-privilege roles for common operations
    • Require explicit approval for cluster-admin usage

Baseline (before any removal): 46 total attack paths
After removing #1: 14 paths remain (32 broken - 69.6% reduction)
After removing #1 and #2: 6 paths remain (40 broken - 86.9% reduction)
After removing #1, #2, #3: 2 paths remain (44 broken - 95.7% reduction)
```

**Parameters:**
- `--input FILE` — Custom graph file
- (Optional: `--top N` to show top N nodes instead of top 5)

---

### 6. Explicit Input File

**Command:**
```bash
python main.py --input /path/to/cluster-graph.json --full-report
```

**What it does:**
- Loads custom graph file instead of default location
- Useful for testing multiple scenarios

**Example:**
```bash
python main.py --input docs/mock-cluster-graph.json --full-report
python main.py --input vulnerable-cluster.json --critical-node
python main.py --input fixed-cluster.json --blast-radius --source web-frontend --hops 2
```

---

## Error Handling

### Exit Codes
- **0** — Success
- **1** — Runtime error (invalid node, graph error, algorithm failure)
- **2** — Usage error (invalid arguments, missing required flags)

### Common Error Messages

**"Node 'X' not found in graph"**
```bash
# Solution: Check the node ID or label in your graph
python main.py --blast-radius --source pod-webfront --hops 3
# If you don't know the exact ID, use the full report first:
python main.py --full-report | grep "Hop 0"
```

**"Cannot find default input file"**
```bash
# Solution: Specify the input file explicitly
python main.py --input /path/to/mock-cluster-graph.json --full-report
```

**"Source and target are the same node"**
```bash
# Solution: For Dijkstra, source and target must be different
python main.py --source pod-webfront --target db-credentials
```

---

## Performance Characteristics

| Operation | Time Complexity | Space Complexity | On 40-node graph | On 500-node graph |
|-----------|-----------------|------------------|------------------|-------------------|
| Full Report | O(V² + E) | O(V + E) | 50-100ms | 200-500ms |
| Blast Radius (3 hops) | O(V + E) | O(V) | 2-5ms | 10-20ms |
| Shortest Path | O((V+E) log V) | O(V) | 1-3ms | 5-15ms |
| Cycle Detection | O((V+E)C) | O(V + E) | 5-10ms | 20-50ms |
| Critical Node | O(VE) | O(V + E) | 10-20ms | 100-200ms |

**Tip:** For very large graphs (> 1000 nodes), use `--path-cutoff 5` to limit path enumeration:
```bash
python main.py --full-report --path-cutoff 5
```

---

## Testing Commands

Run these to verify the CLI is working correctly:

```bash
# 1. Check help works
python main.py --help

# 2. Run full report on mock data
python main.py --full-report

# 3. Test blast radius
python main.py --blast-radius --source pod-webfront --hops 3

# 4. Test shortest path
python main.py --source user-dev1 --target db-production

# 5. Test cycle detection
python main.py --cycles

# 6. Test critical node
python main.py --critical-node

# Expected: All 6 commands succeed (exit code 0) and produce formatted output
```

---

## Integration with CI/CD

```bash
# Exit code can be used in pipelines:
python main.py --full-report
if [ $? -eq 0 ]; then
  echo "✓ Security analysis passed"
else
  echo "✗ Security analysis failed"
  exit 1
fi
```

---

## See Also
- [README.md](../README.md) — Project overview and setup
- [CLUSTER_GRAPH_SCHEMA.md](CLUSTER_GRAPH_SCHEMA.md) — Input file format
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — REST API endpoints
