# Attack Path Analyzer — Start Guide

Complete guide to run the project from scratch, verify real-time monitoring works, and test every feature end-to-end.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| minikube | latest | https://minikube.sigs.k8s.io |
| kubectl | latest | https://kubernetes.io/docs/tasks/tools |

---

## Step 1 — Clone & Install Dependencies

```bash
# 1A. Python backend
cd Attack_path_analyzer/backend
pip install -r requirements.txt

# Verify key packages
python -c "import fastapi, networkx, kubernetes; print('Backend deps OK')"

# 1B. Frontend
cd ../frontend
npm install
```

---

## Step 2 — Configure Environment

The `.env` file at `backend/app/.env` is already set up correctly.
Verify or edit these values:

```env
# backend/app/.env

GROQ_API_KEY=your_groq_key_here          # from console.groq.com (free)
GROQ_MODEL=llama-3.3-70b-versatile

MOCK_MODE=false                           # false = real kubectl data
CLUSTER_NAME=nokia-telecom-cluster

# Real-time monitoring
ENABLE_WATCH_API=true
WATCH_DEBOUNCE_MS=2000                   # 2-second event batching window
ALERT_RISK_DELTA_THRESHOLD=1.0           # alert when risk jumps by +1.0
ALERT_ON_NEW_PATHS=true
ALERT_ON_NEW_CYCLES=true
WATCH_RECONNECT_DELAY_SEC=5
FALLBACK_POLL_INTERVAL_SEC=300           # fallback polling every 5 minutes

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...   # optional
```

> **MOCK_MODE=true** → loads `nokia_telecom.json` (no K8s needed, good for UI demo)
> **MOCK_MODE=false** → fetches live data via kubectl (real monitoring)

---

## Step 3 — Start Kubernetes Cluster (for real-data mode)

```bash
# Start minikube
minikube start

# Verify it's running
kubectl cluster-info
kubectl get nodes
# Should show: minikube   Ready
```

If you don't have a cluster, use **MOCK_MODE=true** and skip to Step 5.

---

## Step 4 — Fetch Kubernetes Data (first time only)

```bash
cd Attack_path_analyzer/backend

# Fetch live cluster data into data/raw/
bash app/scripts/fetch_k8s_data.sh

# Expected output:
#   Fetching pods...           ✓ 8 items
#   Fetching serviceaccounts...✓ 5 items
#   Fetching secrets...        ✓ 12 items
#   Fetching roles...          ✓ 3 items
#   Fetching clusterroles...   ✓ 67 items
#   Fetching rolebindings...   ✓ 3 items
#   Fetching clusterrolebindings... ✓ 20 items
#   Total resources fetched: 118
```

---

## Step 5 — Start the Backend

```bash
cd Attack_path_analyzer/backend

uvicorn app.main:app --reload --port 8000
```

**Expected startup output:**
```
INFO  Attack Path Analyzer v1.0.0
INFO  MOCK_MODE   : False
INFO  CLUSTER     : nokia-telecom-cluster
INFO  Graph loaded — 18 nodes, 22 edges (source: kubectl)
INFO  K8s Watch API started: Watching 7 resource types
```

If Watch API fails (no cluster), you'll see:
```
WARNING  Watch API failed to start. Activating fallback poller (every 300s).
```
This is fine — the app still works with polling.

**Verify backend is running:**
```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/ready
# {"status":"ready","node_count":18,"edge_count":22,...}

curl http://localhost:8000/api/monitor/status
# {"watching":true,"resources_watched":7,"events_processed":0,...}
```

---

## Step 6 — Start the Frontend

```bash
cd Attack_path_analyzer/frontend

npm run dev
# Vite server starts at http://localhost:5173
```

Open **http://localhost:5173** in your browser.

**What you should see:**
- Network topology graph with colored nodes
- Threat score card (top-left)
- Stat cards: nodes, edges, critical findings, cycles
- Header shows **"Monitoring"** badge (green with pulse) when Watch API is active
- Analysis panel on the right with 5 tabs: Attack Path, Blast Radius, Cycles & Critical, Simulation, **Diff**

---

## Step 7 — Verify Real-Time Monitoring is Working

### 7A. Check monitoring status
```bash
curl http://localhost:8000/api/monitor/status
```
```json
{
  "watching": true,
  "cluster": "nokia-telecom-cluster",
  "resources_watched": 7,
  "events_processed": 0,
  "sse_clients": 1
}
```
`sse_clients: 1` confirms the frontend Dashboard is connected to the SSE stream.

### 7B. Test SSE stream directly
Open a new terminal:
```bash
curl -N http://localhost:8000/api/monitor/events/stream
# You should see:
# : heartbeat
# : heartbeat
# (every 25 seconds)
```

### 7C. Trigger a real cluster change

**Option 1 — Deploy a new pod:**
```bash
kubectl create deployment monitor-test --image=nginx
```

**Option 2 — Create a dangerous role binding:**
```bash
kubectl create rolebinding risky-binding \
  --clusterrole=admin \
  --serviceaccount=default:default
```

**Expected sequence within 2-5 seconds:**
1. Watch API receives ADDED event
2. Debouncer waits 2 seconds, batches events
3. Graph is rebuilt from kubectl
4. Diff is computed vs previous run
5. If risk delta > 1.0 or new paths found:
   - 🔴 Red banner appears in Dashboard: **"Security Change Detected"**
   - Dashboard auto-switches to **Diff tab**
   - Slack alert sent (if webhook configured)
6. Graph automatically reloads with new data

**Clean up test resources:**
```bash
kubectl delete deployment monitor-test
kubectl delete rolebinding risky-binding
```

---

## Step 8 — Record Analysis Snapshots for Diff

To use the **Diff** tab, you need at least 2 recorded runs:

```bash
# Record baseline snapshot
curl -X POST http://localhost:8000/api/history/record
# Returns: {"run_id":"a3f9b2c1","message":"Run recorded"}

# Deploy something to change the cluster...
kubectl create deployment vuln-app --image=nginx

# Record second snapshot
curl -X POST http://localhost:8000/api/history/record
# Returns: {"run_id":"b8e1d4f2","message":"Run recorded"}

# View diff of latest two runs
curl http://localhost:8000/api/diff/latest
```

In the Dashboard, go to the **Diff tab** → click **"Run Diff"** (Latest 2 mode).

---

## Step 9 — Deploy Vulnerable Scenario (Demo Mode)

A pre-built vulnerable scenario script is included:

```bash
cd Attack_path_analyzer/backend

# Record baseline first
curl -X POST http://localhost:8000/api/history/record

# Deploy vulnerable K8s resources
bash app/scripts/deploy_vulnerable_scenerio.sh

# Reload graph to pick up changes
curl -X POST http://localhost:8000/api/graph/reload

# Record post-deploy snapshot
curl -X POST http://localhost:8000/api/history/record

# View the diff (API)
curl http://localhost:8000/api/diff/latest

# View the diff (UI)
# → Dashboard → Diff tab → "Latest 2" → Run Diff
```

---

## Step 10 — Full Feature Verification Checklist

Run these to confirm every feature works:

```bash
BASE=http://localhost:8000

# Graph
curl $BASE/api/graph/summary

# Attack path (auto-detect)
curl $BASE/api/attack/auto

# Blast radius
curl -X POST $BASE/api/blast/radius \
  -H "Content-Type: application/json" \
  -d '{"node_id":"pod:default:web-server","max_hops":3}'

# Cycles
curl $BASE/api/cycles/

# Critical nodes
curl "$BASE/api/critical/nodes?top_n=5"

# History
curl $BASE/api/history/

# Diff (latest 2 runs)
curl $BASE/api/diff/latest

# Monitoring status
curl $BASE/api/monitor/status

# Recent monitoring events (from Watch API)
curl $BASE/api/monitor/events

# AI Report (requires GROQ_API_KEY)
curl "$BASE/api/report/?cluster_name=nokia-telecom-cluster"

# Slack test (requires SLACK_WEBHOOK_URL)
curl $BASE/api/slack/test
```

All endpoints should return `200 OK` with JSON data.

---

## Monitoring Control (Manual)

You can start/stop monitoring independently of server restart:

```bash
# Start watch
curl -X POST http://localhost:8000/api/monitor/start

# Check status
curl http://localhost:8000/api/monitor/status

# Stop watch
curl -X POST http://localhost:8000/api/monitor/stop

# Recent security events
curl http://localhost:8000/api/monitor/events?limit=10
```

---

## Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # needs 3.11+

# Reinstall deps
pip install -r requirements.txt

# Check .env is in the right place
ls backend/app/.env
```

### "Graph not loaded" error
```bash
# If MOCK_MODE=false and no cluster:
# Option 1: Switch to mock mode
# Edit backend/app/.env → MOCK_MODE=true

# Option 2: Run the fetch script first
bash backend/app/scripts/fetch_k8s_data.sh
curl -X POST http://localhost:8000/api/graph/reload
```

### Watch API won't start
```bash
# Check minikube is running
minikube status

# Check kubectl works
kubectl cluster-info

# Check Python kubernetes library
python -c "import kubernetes; print(kubernetes.__version__)"

# Fallback polling will activate automatically — app still works
```

### Frontend shows "Monitoring disconnected"
```bash
# Check backend is running
curl http://localhost:8000/health

# Check SSE endpoint
curl -N http://localhost:8000/api/monitor/events/stream

# Check browser console for CORS errors
# All localhost:5173 requests are whitelisted in config.py
```

### Slack alerts not sending
```bash
# Test the webhook directly
curl -X POST -d '{"text":"test"}' $SLACK_WEBHOOK_URL

# Check .env has correct URL (no typos)
grep SLACK_WEBHOOK backend/app/.env
# Must be: SLACK_WEBHOOK_URL=https://...  (capital URL at end)
```

### Diff tab shows "Need at least 2 analysis runs"
```bash
# Record two snapshots manually
curl -X POST http://localhost:8000/api/history/record
# wait a moment
curl -X POST http://localhost:8000/api/history/record
# now run diff
curl http://localhost:8000/api/diff/latest
```

---

## Project Structure Reference

```
Attack_path_analyzer/
├── backend/
│   ├── app/
│   │   ├── .env                         ← Environment config
│   │   ├── main.py                      ← FastAPI entry point
│   │   ├── config.py                    ← Settings (pydantic)
│   │   ├── api/
│   │   │   ├── routes_monitor.py        ← NEW: /api/monitor/* endpoints
│   │   │   ├── routes_diff.py           ← /api/diff/* endpoints
│   │   │   ├── routes_history.py        ← /api/history/* endpoints
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── watch_service.py         ← NEW: K8s Watch API core
│   │   │   ├── watch_decision_engine.py ← NEW: Alert decision logic
│   │   │   ├── event_debouncer.py       ← NEW: 2-second event batching
│   │   │   ├── broadcast_service.py     ← NEW: SSE broadcaster
│   │   │   ├── fallback_poller.py       ← NEW: 5-min polling fallback
│   │   │   ├── ingestion_service.py     ← kubectl data fetcher
│   │   │   ├── graph_diff_service.py    ← Run comparison logic
│   │   │   ├── history_service.py       ← SQLite history
│   │   │   └── slack_service.py         ← Slack alerts
│   │   └── core/
│   │       ├── database.py              ← SQLite + monitoring tables
│   │       ├── graph_builder.py         ← NetworkX graph
│   │       └── parser.py                ← kubectl JSON parser
│   ├── requirements.txt
│   └── scripts/
│       ├── fetch_k8s_data.sh            ← Fetch raw K8s data
│       └── deploy_vulnerable_scenerio.sh← Deploy test scenario
├── frontend/
│   └── src/
│       ├── hooks/
│       │   ├── useMonitoring.ts         ← NEW: SSE hook
│       │   ├── useGraph.ts
│       │   └── useAnalysis.ts
│       ├── components/
│       │   ├── DiffPanel.tsx            ← NEW: Graph diff UI
│       │   └── ...
│       └── pages/
│           └── Dashboard.tsx            ← Main dashboard (updated)
├── data/
│   ├── raw/          ← kubectl JSON output
│   ├── processed/    ← parsed graph files
│   ├── scenarios/    ← mock data (nokia_telecom.json)
│   └── history.db    ← SQLite (auto-created)
└── docs/
    ├── MONITORING_ARCHITECTURE.md
    ├── BACKEND_AGENT_IMPLEMENTATION.md
    ├── MONITORING_API_REFERENCE.md
    └── IMPLEMENTATION_CHECKLIST.md
```

---

## Quick Reference — All API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (graph loaded?) |
| GET | `/api/graph/` | Full graph (Cytoscape format) |
| GET | `/api/graph/summary` | Node/edge counts |
| POST | `/api/graph/reload` | Reload from kubectl |
| GET | `/api/attack/auto` | Auto-detect attack path |
| POST | `/api/attack/path` | Find path between 2 nodes |
| POST | `/api/blast/radius` | Blast radius from node |
| GET | `/api/cycles/` | Privilege escalation cycles |
| GET | `/api/critical/nodes` | Top N critical nodes |
| POST | `/api/simulate/remove` | Simulate removing a node |
| GET | `/api/report/` | AI security report |
| GET | `/api/history/` | Recent analysis runs |
| POST | `/api/history/record` | Record manual snapshot |
| GET | `/api/diff/latest` | Diff latest 2 runs |
| POST | `/api/diff/compare` | Diff specific run IDs |
| GET | `/api/diff/vs-current/{run_id}` | Diff run vs live |
| **POST** | **`/api/monitor/start`** | **Start Watch API** |
| **POST** | **`/api/monitor/stop`** | **Stop Watch API** |
| **GET** | **`/api/monitor/status`** | **Monitoring status** |
| **GET** | **`/api/monitor/events/stream`** | **SSE live event stream** |
| **GET** | **`/api/monitor/events`** | **Recent security events** |
| GET | `/api/cves/` | CVE feed |
| GET | `/api/slack/test` | Test Slack webhook |

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Backend API | 8000 | http://localhost:8000 |
| Frontend | 5173 | http://localhost:5173 |
| API Docs | 8000 | http://localhost:8000/docs |
| Redoc | 8000 | http://localhost:8000/redoc |
