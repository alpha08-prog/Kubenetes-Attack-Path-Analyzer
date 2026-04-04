# Real-Time Kubernetes Monitoring Architecture

## System Overview

The Attack Path Analyzer now supports **real-time monitoring** of Kubernetes clusters using the K8s Watch API. This enables:

- **0-5 second latency** on cluster changes (vs 5-30 minute manual refresh cycle)
- **Automatic alerts** when attack paths appear or risk increases
- **Live frontend updates** showing what changed (via Server-Sent Events)
- **Fallback to polling** if Watch API becomes unavailable
- **Complete audit trail** in SQLite history

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     KUBERNETES CLUSTER                              │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │         K8s Watch API (streaming events)                    │  │
│  │  Events: ADDED, MODIFIED, DELETED                          │  │
│  │  Resources: pods, roles, rolebindings, secrets, etc        │  │
│  └────────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────────┼─────────────────────────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │ BACKEND (Attack Path Server)  │
                    └─────────────┬────────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
        ┌───────▼────────┐  ┌─────▼──────┐  ┌────▼──────────┐
        │  Watch API     │  │  Debouncer │  │  Event Queue  │
        │  Listener      │  │  (2s)      │  │  (SQLite)     │
        │                │  │            │  │               │
        │ • Connects to  │  │ • Batches  │  │ • Stores      │
        │   K8s API      │  │   rapid    │  │   pending     │
        │ • Receives     │  │   changes  │  │   events      │
        │   event stream │  │ • Dedupl.  │  │ • Allows      │
        │ • Decodes JSON │  │   events   │  │   retry       │
        └───────┬────────┘  └──────┬─────┘  └────┬──────────┘
                │                  │              │
                └──────────────────┼──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Delta Analysis             │
                    │  (watch_decision_engine.py) │
                    │                            │
                    │ 1. Get previous run_id     │
                    │ 2. Rebuild graph           │
                    │ 3. Record new run_id       │
                    │ 4. diff_runs()             │
                    │ 5. Check thresholds        │
                    └──────────────┬─────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
        ┌───────▼────────┐  ┌──────▼────────┐  ┌────▼──────────┐
        │  Alert Engine  │  │  Slack Alert  │  │  SSE Broadcast│
        │                │  │               │  │               │
        │ • Risk +1.0?   │  │ • Format msg  │  │ • Queue event │
        │   → ALERT      │  │ • Post hook   │  │ • Send to all │
        │ • New paths?   │  │ • Log result  │  │   connected   │
        │   → CRITICAL   │  │               │  │   clients     │
        │ • New cycles?  │  │               │  │               │
        │   → HIGH       │  │               │  │               │
        └────────────────┘  └────────────────┘  └────┬──────────┘
                                                     │
                                ┌────────────────────┼────────────────┐
                                │                    │                │
                        ┌───────▼────────┐  ┌───────▼─────────┐  ┌──▼─────────────┐
                        │  SQLite        │  │  Slack Channel  │  │  Frontend SSE  │
                        │  History DB    │  │                 │  │  (WebSocket)   │
                        │                │  │  #alerts-infra  │  │                │
                        │ • monitoring_  │  │                 │  │ EventSource    │
                        │   events table │  │ ┌─────────────┐ │  │ /monitor/      │
                        │ • Tracks all   │  │ │ Risk: +1.3  │ │  │ events/stream  │
                        │   changes      │  │ │ Run: a3f9b2 │ │  │                │
                        │ • Run linkage  │  │ │ 14:30 UTC   │ │  │ Auto-refresh   │
                        │                │  │ └─────────────┘ │  │ Show diff      │
                        └────────────────┘  └─────────────────┘  │ Highlight      │
                                                                 │ changes        │
                                                                 └────────────────┘
                                                                       │
                                                                       │ HTTP
                                                                       ▼
                                                           ┌─────────────────────┐
                                                           │  Frontend Dashboard │
                                                           │                     │
                                                           │ • React app         │
                                                           │ • Cytoscape graph   │
                                                           │ • Diff panel        │
                                                           │ • Live indicator    │
                                                           └─────────────────────┘
```

---

## Component Details

### 1. Watch API Listener (`watch_service.py`)

**Purpose:** Connects to Kubernetes cluster and receives live event stream

**Responsibilities:**
- Load K8s configuration (kubeconfig or in-cluster)
- Connect to K8s Watch API for 7 resource types
- Stream events continuously until shutdown
- Handle connection failures gracefully

**Key Methods:**
```python
async def start() → Dict
  Starts watching K8s cluster
  Returns: {"status": "watching", "resources": 7}

async def stop() → Dict
  Stops watching gracefully
  Returns: {"status": "stopped"}

async def get_status() → Dict
  Current watch status
  Returns: {"watching": true, "cluster": "..."}
```

**Event Types Watched:**
- `pods` - Any pod created, modified, or deleted
- `serviceaccounts` - Service account changes
- `secrets` - Secret access/changes
- `roles` - Role definition changes
- `clusterroles` - Cluster-wide role changes
- `rolebindings` - Namespace role assignments
- `clusterrolebindings` - Cluster role assignments

---

### 2. Event Debouncer (`event_debouncer.py`)

**Purpose:** Prevents analysis thrashing when cluster is under load

**Problem It Solves:**
- When rolling out a new deployment, 20+ events arrive in 100ms
- Analyzing after each event = wasteful
- Debouncing = batch them, analyze once

**Algorithm:**
1. Event arrives → add to queue
2. Start 2-second timer
3. More events arrive → add to queue (timer running)
4. Timer expires → process all queued events at once
5. Deduplicate: if resource changed twice, keep only latest state

**Key Method:**
```python
async def queue_event(event: Dict)
  Queues event for debounced processing
  Starts timer if not already running
```

---

### 3. Alert Decision Engine (`watch_decision_engine.py`)

**Purpose:** Decides if cluster changes warrant sending alerts

**Decision Logic:**

**A. Risk Increase Alert**
```
if new_risk - previous_risk > ALERT_RISK_DELTA_THRESHOLD (default 1.0):
    severity = "critical" if delta > 2.0 else "high"
    → SEND ALERT
```

Example:
```
Before: overall_risk = 6.2
After:  overall_risk = 7.5
Delta:  +1.3

1.3 > 1.0 → ALERT with severity="high"
```

**B. New Attack Paths Alert**
```
if new_run.attack_paths > previous_run.attack_paths:
    → SEND ALERT with severity="critical"

Example: 0 paths → 2 paths = critical threat
```

**C. New Privilege Escalation Cycles Alert**
```
if new_run.cycles > previous_run.cycles:
    → SEND ALERT with severity="high"

Example: detected a loop that enables privilege escalation
```

**Workflow:**
```
1. Get previous_run_id from history
2. Rebuild current graph from K8s
3. Record new_run_id to SQLite
4. diff_runs(previous_run_id, new_run_id)
5. Check all 3 thresholds
6. If any triggered:
   a. Send Slack alert
   b. Send SSE to frontend
   c. Record to monitoring_events table
```

---

### 4. Broadcast Service (`broadcast_service.py`)

**Purpose:** Sends real-time updates to connected frontend clients

**Transport:** Server-Sent Events (SSE)

**Why SSE not WebSocket?**
- SSE: unidirectional (server → client), simpler, auto-reconnect
- WebSocket: bidirectional, more overhead
- For our use case (server pushing updates), SSE is perfect

**Message Format:**
```json
{
  "type": "GRAPH_UPDATE",
  "run_id": "a3f9b2c1",
  "diff": {
    "risk_delta": {"before": 6.2, "after": 7.5, "delta": 1.3},
    "path_delta": {"before": 0, "after": 2, "delta": 2},
    "cycle_delta": {"before": 0, "after": 1, "delta": 1},
    "top_new_risks": [...],
    "recommendation": "..."
  },
  "timestamp": "2026-04-04T14:30:12Z"
}
```

**Frontend Connection:**
```javascript
const eventSource = new EventSource('/api/monitor/events/stream');
eventSource.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // Refresh graph, show diff, send toast notification
};
```

---

### 5. Fallback Poller (`fallback_poller.py`)

**Purpose:** Provides resilience if Watch API connection fails

**Scenario:**
- Watch API connection drops (network issue, K8s API server restart)
- Instead of going silent, fall back to polling
- Every 5 minutes: run `ingest_and_build()`, check for changes
- Resume Watch API when connection recovers

**Retry Logic:**
```
Attempt 1: Watch API        (0-2s latency)
         ↓ (fails)
Attempt 2: Watch API retry  (after 5s)
         ↓ (fails 3x)
Fallback:  Polling          (5-min interval)
         ↓ (connection restored)
Resume:    Watch API        (0-2s latency again)
```

---

## Data Flow Example

**Scenario: Admin accidentally binds admin role to a service account**

### T=0: Human runs kubectl
```bash
kubectl create rolebinding risky-binding \
  --clusterrole=admin \
  --serviceaccount=default:default
```

### T=0.1s: K8s event generated
```json
{
  "type": "ADDED",
  "object": {
    "kind": "ClusterRoleBinding",
    "metadata": {
      "name": "risky-binding",
      "uid": "a1b2c3d4"
    },
    "subjects": [{"kind": "ServiceAccount", "name": "default"}],
    "roleRef": {"kind": "ClusterRole", "name": "admin"}
  }
}
```

### T=0.2s: Watch listener receives event
```
watch_service.py:
  event['type'] = "ADDED"
  event['resource_type'] = "clusterrolebindings"
  → queue to debouncer
```

### T=2.0s: Debounce timer expires
```
event_debouncer.py:
  Events in window: [rolebinding ADDED, pod MODIFIED]
  Deduplicate: keep both (different resources)
  → call analyze_changes()
```

### T=2.1s: Analysis triggered
```
watch_decision_engine.py:
  1. previous_run_id = "b8e1d4f2" (from history)
  2. ingest_and_build()
     → fetch pods, roles, rolebindings from K8s
     → parse_cluster_data()
     → build_graph()
     → in-memory graph now includes risky-binding
  3. new_run_id = "c5f2e1a3"
  4. diff_runs("b8e1d4f2", "c5f2e1a3")
     → node changes detected (new binding)
     → risk increased from 6.2 to 8.1 (+1.9)
     → new attack path found: default-sa → admin-role → all-resources
```

### T=2.2s: Alert thresholds checked
```
Check 1: Risk delta (+1.9) > threshold (1.0) → TRUE
  Alert: RISK_INCREASE, severity="critical"

Check 2: New attack paths (1 new) → TRUE
  Alert: NEW_ATTACK_PATHS, severity="critical"

Check 3: New cycles → FALSE
  (no privilege escalation loop detected in this example)
```

### T=2.3s: Alerts sent
```
1. Slack alert posted:
   #alerts-infra
   "🚨 CRITICAL: Risk increased from 6.2→8.1 (+29%)"
   "1 new attack path discovered"
   "Run: c5f2e1a3 | Cluster: nokia-telecom"

2. SSE broadcast to frontend:
   {
     "type": "GRAPH_UPDATE",
     "run_id": "c5f2e1a3",
     "diff": {...full diff...},
     "timestamp": "2026-04-04T14:30:12Z"
   }

3. Monitoring event recorded:
   INSERT INTO monitoring_events VALUES (
     run_id='c5f2e1a3',
     event_type='RISK_INCREASE',
     severity='critical',
     summary='Risk +1.9 from rolebinding creation',
     triggered_alerts='slack,websocket,history'
   )
```

### T=2.4s: Frontend receives update
```
useMonitoring hook receives SSE message
  → dispatch 'graphUpdate' event
  → trigger graph reload
  → show toast: "Graph updated: risk +1.9"
  → switch to Diff tab
  → show before/after comparison
```

### T=2.5s: User sees the change
Frontend dashboard now shows:
- Graph refreshed with new rolebinding visible
- Diff panel showing what changed
- Notification badge: "3 alerts in last 5 min"
- History sidebar: new entry for run c5f2e1a3

---

## State Diagrams

### Watch Service Lifecycle
```
┌─────────────┐
│  Stopped    │
└──────┬──────┘
       │ POST /monitor/start
       ▼
┌──────────────────────┐
│  Connecting to K8s   │────► Error: cannot connect
└──────┬───────────────┘
       │ K8s connection successful
       ▼
┌──────────────────────┐
│  Watching Active     │ ◄───── Network error → Reconnect after 5s
│                      │
│ Streaming events     │
│ from Watch API       │
└──────┬───────────────┘
       │ POST /monitor/stop
       ▼
┌─────────────┐
│  Stopped    │
└─────────────┘
```

### Event Processing Pipeline
```
Event Queue
    │
    ├─ [2ms] Queue event
    │
    ├─ [100ms] Queue more events (burst)
    │
    └─ [2s] Timer expires ──► Debouncer ──► Analyze Changes
                                  │
                          Deduplicate & Batch
                                  │
                          ┌───────▼────────┐
                          │ Rebuild graph  │
                          │ from K8s state │
                          └───────┬────────┘
                                  │
                          ┌───────▼────────┐
                          │ Compare with   │
                          │ previous run   │
                          └───────┬────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │ Check alert thresholds     │
                    └─────────────┬──────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                │
         Threshold   Threshold   No
         Met (1)     Met (2)     Threshold
            │          │            │
            ▼          ▼            ▼
         ALERT1   ALERT2      No alerts
            │       │
            └───┬───┘
                │
        ┌───────▼────────┐
        │ Broadcast SSE  │
        │ Slack alert    │
        │ Record event   │
        └────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# Enable Watch API
ENABLE_WATCH_API=true

# Debounce window (milliseconds)
WATCH_DEBOUNCE_MS=2000

# Alert thresholds
ALERT_RISK_DELTA_THRESHOLD=1.0        # Risk increase to trigger
ALERT_ON_NEW_PATHS=true                # Alert on new attack paths
ALERT_ON_NEW_CYCLES=true               # Alert on priv-esc cycles

# Resilience
WATCH_RECONNECT_DELAY_SEC=5            # Seconds before reconnect
FALLBACK_POLL_INTERVAL_SEC=300         # 5 minutes

# K8s connection
KUBECTL_TIMEOUT=30                     # Seconds
```

### Threshold Tuning

**Conservative (fewer alerts):**
```
ALERT_RISK_DELTA_THRESHOLD=2.0         # Only big jumps
ALERT_ON_NEW_PATHS=false                # Ignore new paths
ALERT_ON_NEW_CYCLES=false               # Ignore cycles
```

**Aggressive (all changes):**
```
ALERT_RISK_DELTA_THRESHOLD=0.5         # Any increase
ALERT_ON_NEW_PATHS=true
ALERT_ON_NEW_CYCLES=true
```

**Recommended (balanced):**
```
ALERT_RISK_DELTA_THRESHOLD=1.0         # Moderate increase
ALERT_ON_NEW_PATHS=true                 # Always critical
ALERT_ON_NEW_CYCLES=true                # Priv-esc always important
```

---

## Performance Characteristics

### Latency

| Event | Latency | Notes |
|-------|---------|-------|
| K8s resource change | 100ms | Propagate to Watch API |
| Watch API → Backend | 50-200ms | Depends on network |
| Debounce window | 2000ms | Intentional delay |
| Analysis (graph rebuild) | 100-500ms | Depends on cluster size |
| SSE broadcast | 10-50ms | In-memory only |
| Frontend update | 16-33ms | Browser rendering |
| **Total E2E** | **2.2-2.8 seconds** | Most common case |

### Scalability

| Metric | Small Cluster | Large Cluster |
|--------|---|---|
| Nodes | <100 | 1000+ |
| Watch events/min | 10-50 | 500-2000 |
| Debouncer latency | 2s | 2s (same) |
| Graph rebuild time | 50ms | 500ms |
| Memory/watch stream | ~1MB | ~5MB |

---

## Troubleshooting

### Watch API Not Connecting
```bash
# Check kubeconfig
kubectl cluster-info
kubectl get pods

# Check logs
tail -f backend/app/logs/app.log | grep -i watch

# Verify Python kubernetes lib
python -c "from kubernetes import client, config; config.load_kube_config(); print('OK')"
```

### Alerts Not Arriving
```bash
# Check SSE stream
curl -N http://localhost:8000/api/monitor/events/stream

# Check Slack webhook
curl -X POST -d '{"text":"test"}' $SLACK_WEBHOOK_URL

# Check database
sqlite3 data/history.db "SELECT * FROM monitoring_events ORDER BY created_at DESC LIMIT 5"
```

### Graph Not Updating
```bash
# Check monitor status
curl http://localhost:8000/api/monitor/status

# Check frontend connection
# Open DevTools → Network → look for EventSource stream

# Manually trigger reload
curl -X POST http://localhost:8000/api/graph/reload
```

---

## Security Considerations

### K8s RBAC Permissions Required

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: attack-path-analyzer
rules:
- apiGroups: [""]
  resources: ["pods", "serviceaccounts", "secrets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["rbac.authorization.k8s.io"]
  resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
  verbs: ["get", "list", "watch"]
```

**What we DON'T need:**
- create, delete, patch (read-only)
- escalate (no privilege needed)
- impersonate (no impersonation)

---

## Monitoring the Monitor

How to ensure the monitor itself is healthy:

```bash
# Check it's watching
curl http://localhost:8000/api/monitor/status

# Check recent events
sqlite3 data/history.db "SELECT COUNT(*) FROM monitoring_events WHERE created_at > datetime('now', '-1 hour')"

# Check error logs
grep ERROR backend/app/logs/app.log

# Check K8s connection
kubectl auth can-i list pods --as=system:serviceaccount:default:attack-path-analyzer
```

---

