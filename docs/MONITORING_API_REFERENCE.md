# Real-Time Monitoring API Reference

## Overview

These endpoints control real-time Kubernetes cluster monitoring and receive live graph updates.

**Base URL:** `http://localhost:8000/api`

---

## Monitoring Control Endpoints

### 1. Start Monitoring

**Endpoint:** `POST /api/monitor/start`

**Purpose:** Start watching Kubernetes cluster for changes

**Request:**
```http
POST /api/monitor/start
Content-Type: application/json
```

**Response:** `200 OK`
```json
{
  "status": "watching",
  "resources": 7,
  "message": "Watching 7 resource types"
}
```

**Error Responses:**

`400 Bad Request` - MOCK_MODE is enabled
```json
{
  "detail": "Cannot enable monitoring in MOCK_MODE. Set MOCK_MODE=false in .env"
}
```

`400 Bad Request` - Cannot connect to K8s
```json
{
  "detail": "Cannot connect to Kubernetes cluster. Check kubeconfig or in-cluster config."
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/monitor/start
```

**Python:**
```python
import httpx

client = httpx.Client()
response = client.post('http://localhost:8000/api/monitor/start')
print(response.json())
# {'status': 'watching', 'resources': 7, ...}
```

---

### 2. Stop Monitoring

**Endpoint:** `POST /api/monitor/stop`

**Purpose:** Stop watching Kubernetes cluster

**Request:**
```http
POST /api/monitor/stop
Content-Type: application/json
```

**Response:** `200 OK`
```json
{
  "status": "stopped",
  "message": "Watch stopped"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/monitor/stop
```

---

### 3. Get Monitoring Status

**Endpoint:** `GET /api/monitor/status`

**Purpose:** Get current monitoring status and health

**Request:**
```http
GET /api/monitor/status
```

**Response:** `200 OK`
```json
{
  "watching": true,
  "started_at": "2026-04-04T14:25:30.123456",
  "cluster": "nokia-telecom-cluster",
  "debounce_ms": 2000,
  "alert_threshold": 1.0,
  "resources_watched": 7
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| watching | boolean | Is monitoring currently active? |
| started_at | ISO 8601 | When monitoring started (or null if stopped) |
| cluster | string | Cluster name from config |
| debounce_ms | integer | Event debounce window (ms) |
| alert_threshold | float | Risk delta threshold for alerts |
| resources_watched | integer | Number of K8s resource types being watched |

**Example:**
```bash
curl http://localhost:8000/api/monitor/status
```

**JavaScript:**
```javascript
const response = await fetch('/api/monitor/status');
const status = await response.json();
console.log(`Monitoring: ${status.watching ? 'Active' : 'Inactive'}`);
```

---

## Real-Time Event Stream

### 4. Subscribe to Graph Updates (SSE)

**Endpoint:** `GET /api/monitor/events/stream`

**Purpose:** Subscribe to Server-Sent Events (SSE) stream of graph updates

**Request:**
```http
GET /api/monitor/events/stream
Accept: text/event-stream
```

**Response:** `200 OK` with continuous event stream
```
: heartbeat
data: {"type":"GRAPH_UPDATE","run_id":"a3f9b2c1","diff":{...},"timestamp":"2026-04-04T14:30:12Z"}

: heartbeat
data: {"type":"GRAPH_UPDATE","run_id":"b5d3e1f4","diff":{...},"timestamp":"2026-04-04T14:35:15Z"}
```

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**Event Format:**

Each message is a JSON object:
```json
{
  "type": "GRAPH_UPDATE",
  "run_id": "a3f9b2c1",
  "diff": {
    "meta": {
      "run_before": "a3f9b2c0",
      "run_after": "a3f9b2c1",
      "time_before": "2026-04-04T14:25:00Z",
      "time_after": "2026-04-04T14:30:12Z",
      "cluster": "nokia-telecom-cluster"
    },
    "risk_delta": {
      "before": 6.2,
      "after": 7.5,
      "delta": 1.3,
      "delta_pct": 20.9,
      "direction": "increased",
      "severity_before": "high",
      "severity_after": "critical"
    },
    "node_changes": {
      "total_before": 18,
      "total_after": 19,
      "new_count": 1,
      "removed_count": 0,
      "changed_count": 0,
      "new_nodes": [
        {
          "node_id": "rolebinding:cluster:risky-binding",
          "label": "risky-binding",
          "type": "rolebinding",
          "risk": 9.5,
          "severity": "critical",
          "namespace": "cluster"
        }
      ],
      "risk_increased": [],
      "risk_decreased": []
    },
    "path_delta": {
      "before": 0,
      "after": 1,
      "delta": 1,
      "direction": "more_paths",
      "label": "1 new attack path introduced"
    },
    "cycle_delta": {
      "before": 0,
      "after": 0,
      "delta": 0,
      "direction": "unchanged"
    },
    "top_new_risks": [
      {
        "node_id": "rolebinding:cluster:risky-binding",
        "label": "risky-binding",
        "type": "rolebinding",
        "risk_before": 0,
        "risk_after": 9.5,
        "delta": 9.5,
        "is_new": true
      }
    ],
    "recommendation": "Security posture has degraded: 1 new attack path(s) were introduced. Review newly added roles and service account bindings immediately..."
  },
  "timestamp": "2026-04-04T14:30:12Z"
}
```

**Usage - JavaScript:**

```javascript
const eventSource = new EventSource('/api/monitor/events/stream');

eventSource.onopen = () => {
  console.log('Connected to monitoring stream');
};

eventSource.onmessage = (event) => {
  const update = JSON.parse(event.data);

  console.log(`Graph updated: risk ${update.diff.risk_delta.before} → ${update.diff.risk_delta.after}`);

  // Refresh graph
  reloadGraph();

  // Show notification
  showNotification({
    title: 'Security Alert',
    message: `Risk increased by ${update.diff.risk_delta.delta}`,
    severity: update.diff.risk_delta.severity_after
  });

  // Switch to diff panel
  setActiveTab('diff');
};

eventSource.onerror = (error) => {
  console.error('Stream error:', error);
  eventSource.close();
  // Reconnect after delay
  setTimeout(() => {
    window.location.reload();
  }, 5000);
};

// Cleanup on unmount
// eventSource.close();
```

**Usage - React Hook:**

```typescript
import { useEffect, useState } from 'react';

function useMonitoringStream() {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const eventSource = new EventSource('/api/monitor/events/stream');

    eventSource.onopen = () => {
      setConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setLastUpdate(update);
    };

    eventSource.onerror = (err) => {
      setConnected(false);
      setError('Connection lost');
      eventSource.close();
    };

    return () => eventSource.close();
  }, []);

  return { connected, lastUpdate, error };
}

// Usage in component
function Dashboard() {
  const { connected, lastUpdate } = useMonitoringStream();

  return (
    <div>
      <div className={`status ${connected ? 'connected' : 'disconnected'}`}>
        {connected ? '🟢 Live' : '🔴 Offline'}
      </div>

      {lastUpdate && (
        <AlertPanel diff={lastUpdate.diff} />
      )}
    </div>
  );
}
```

---

## Data Models

### DiffResult

Returned in graph update events. Complete comparison between two analysis runs.

```typescript
interface DiffResult {
  meta: {
    run_before: string;      // e.g., "a3f9b2c0"
    run_after: string;       // e.g., "a3f9b2c1"
    time_before: string;     // ISO 8601
    time_after: string;      // ISO 8601
    cluster: string;         // e.g., "nokia-telecom-cluster"
  };

  risk_delta: {
    before: number;          // e.g., 6.2
    after: number;           // e.g., 7.5
    delta: number;           // e.g., 1.3
    delta_pct: number;       // e.g., 20.9
    direction: string;       // "increased" | "decreased" | "unchanged"
    severity_before: string; // "critical" | "high" | "medium" | "low" | "none"
    severity_after: string;
  };

  node_changes: {
    total_before: number;
    total_after: number;
    new_count: number;
    removed_count: number;
    changed_count: number;
    new_nodes: Array<NodeInfo>;
    removed_nodes: Array<string>;
    risk_increased: Array<NodeDelta>;
    risk_decreased: Array<NodeDelta>;
  };

  severity_shift: {
    before: Record<string, number>;  // {critical: 2, high: 5, ...}
    after: Record<string, number>;
    deltas: Record<string, number>;  // {critical: +1, high: -1, ...}
    summary: string;                 // "No significant severity changes"
  };

  path_delta: {
    before: number;
    after: number;
    delta: number;
    direction: string;  // "more_paths" | "fewer_paths" | "unchanged"
    label: string;      // Human-readable summary
  };

  cycle_delta: {
    before: number;
    after: number;
    delta: number;
    direction: string;
    label: string;
  };

  finding_delta: {
    new_count: number;
    resolved_count: number;
    new_findings: Array<Finding>;
    resolved: Array<Finding>;
  };

  top_new_risks: Array<{
    node_id: string;
    label: string;
    type: string;
    risk_before: number;
    risk_after: number;
    delta: number;
    is_new: boolean;
  }>;

  top_improved: Array<{
    node_id: string;
    label: string;
    type: string;
    risk_before: number;
    risk_after: number;
    delta: number;  // Negative
  }>;

  recommendation: string;  // Plain English summary of implications
}
```

---

## Typical Workflows

### Workflow 1: Start Monitoring & Listen for Updates

```python
import httpx
import json
from sseclient import SSEClient  # pip install sseclient-py

# Start monitoring
response = httpx.post('http://localhost:8000/api/monitor/start')
print(response.json())
# {'status': 'watching', 'resources': 7}

# Connect to event stream
url = 'http://localhost:8000/api/monitor/events/stream'
client = SSEClient(url)

for event in client:
    if event.event == 'message':
        update = json.loads(event.data)
        print(f"Risk: {update['diff']['risk_delta']['before']} → {update['diff']['risk_delta']['after']}")

        if update['diff']['risk_delta']['delta'] > 1.0:
            print("ALERT: Risk increased significantly!")
```

### Workflow 2: Manual Monitoring Control (for testing)

```bash
# Start monitoring
curl -X POST http://localhost:8000/api/monitor/start
# {"status":"watching","resources":7}

# Check status
curl http://localhost:8000/api/monitor/status
# {"watching":true,"started_at":"2026-04-04T14:30:00..."}

# Deploy something to K8s
kubectl create deployment test-app --image=nginx

# Watch for updates (in separate terminal)
curl -N http://localhost:8000/api/monitor/events/stream
# (waits for events...)

# Stop monitoring
curl -X POST http://localhost:8000/api/monitor/stop
```

### Workflow 3: Frontend Auto-Refresh on Changes

```typescript
import { useEffect, useState } from 'react';
import { useGraph } from '@/hooks/useGraph';

export function DashboardWithLiveUpdates() {
  const { reload, graphData } = useGraph();
  const [lastUpdateTime, setLastUpdateTime] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource('/api/monitor/events/stream');

    eventSource.onmessage = (event) => {
      const update = JSON.parse(event.data);

      // Auto-refresh graph
      reload();

      // Update UI
      setLastUpdateTime(update.timestamp);

      // Show toast
      toast.success(
        `Graph updated: risk ${update.diff.risk_delta.before}→${update.diff.risk_delta.after}`,
        { autoClose: 5000 }
      );
    };

    return () => eventSource.close();
  }, [reload]);

  return (
    <div>
      <div className="text-sm text-muted-foreground">
        Last update: {lastUpdateTime || 'Waiting...'}
      </div>
      {/* Rest of dashboard... */}
    </div>
  );
}
```

---

## Error Handling

### Connection Lost

The SSE connection may drop due to:
- Network issue
- Server restart
- Load balancer timeout
- Client tab inactive (browser suspends event source)

**Recommended handling:**
```javascript
const eventSource = new EventSource('/api/monitor/events/stream');

eventSource.onerror = () => {
  // Close the broken connection
  eventSource.close();

  // Show offline indicator
  setStatus('offline');

  // Attempt reconnect after 5 seconds
  setTimeout(() => {
    window.location.reload();  // Or create new EventSource
  }, 5000);
};
```

### No Events Received

If you don't receive events but monitoring is running:

1. Check monitoring is actually started:
   ```bash
   curl http://localhost:8000/api/monitor/status
   # Should show "watching": true
   ```

2. Check backend logs for errors:
   ```bash
   tail -f backend/app/logs/app.log | grep -i watch
   ```

3. Manually trigger a cluster change:
   ```bash
   kubectl create deployment test --image=nginx
   ```

4. Check if events are being recorded:
   ```bash
   sqlite3 data/history.db "SELECT COUNT(*) FROM monitoring_events WHERE created_at > datetime('now', '-5 minutes')"
   ```

---

## Rate Limiting & Quotas

No explicit rate limiting is implemented, but note:

- **Alert threshold:** Only alerts sent if thresholds met (prevents spam)
- **Debounce:** Events batched every 2 seconds (prevents thrashing)
- **Slack:** Rate limited to 1 message per minute per channel
- **SSE:** Backpressure handled (slow clients don't block fast ones)

---

## Authentication & CORS

Currently **no authentication** on these endpoints (assumes internal use).

To add authentication:
1. Add JWT validation middleware
2. Require token in headers: `Authorization: Bearer <token>`
3. Check examples in `backend/app/middleware/`

CORS is enabled for:
```
localhost:3000
localhost:5173
127.0.0.1:3000
127.0.0.1:5173
```

To modify, edit `backend/app/config.py` → `CORS_ORIGINS`

---

