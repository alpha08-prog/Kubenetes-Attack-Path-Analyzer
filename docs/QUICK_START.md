# Quick Start Guide (5 Minutes)

> Get the Attack Path Analyzer running in 5 minutes — no Kubernetes cluster required

## Prerequisites

- Python 3.10+ OR Docker
- 5 minutes
- A terminal

---

## Option A: Docker (Recommended - 2 minutes)

**1. Clone and navigate:**
```bash
cd attack-path-analyzer
```

**2. Start everything:**
```bash
make demo
```

**3. Open your browser:**
```
Frontend: http://localhost:3000
API Docs: http://localhost:8000/docs
```

**Done!** The tool is analyzing a demo cluster. See the attack paths on the graph.

---

## Option B: CLI Only (3 minutes)

**1. Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Run analysis:**
```bash
python main.py --full-report
```

**Expected output:**
```
==================================================================
  KILL CHAIN REPORT  -  2026-04-04 12:48:15
  Cluster : mock-prod-cluster
  Nodes   : 41  |  Edges: 48
==================================================================

[ SECTION 1 - ATTACK PATH DETECTION ]
   46 attack path(s) detected

  Path #1  |  3 hops  |  Risk Score: 9.5  [CRITICAL]
  dev-1 → web-frontend → sa-webapp → secret-reader → db-credentials
  → production-db

...
```

**Done!** All attack paths detected. Try other commands:

```bash
# Blast radius from a node
python main.py --blast-radius --source pod-webfront --hops 3

# Shortest attack path
python main.py --source user-dev1 --target db-production

# Find cycles
python main.py --cycles

# Critical nodes
python main.py --critical-node
```

---

## Option C: Local Development (5 minutes)

**Terminal 1 — Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Open:** `http://localhost:5173`

---

## What You're Looking At

### The Graph
- **Red nodes** = High risk
- **Green nodes** = Low risk
- **Arrows** = Attack relationships
- **Click nodes** = See details

### Attack Paths
- The system found 46 ways an attacker could move through the cluster
- Shortest/easiest path shown first

### Critical Nodes
- **web-frontend** — Removing this blocks 70% of attacks
- **api-server** — Removing this blocks 52% of attacks

### Cycles
- **Privilege loops** where attackers can escalate infinitely
- Example: `svc-service-a` → `svc-service-b` → back to `svc-service-a`

---

## Common Commands

| Goal | Command |
|------|---------|
| See all attacks | `python main.py --full-report` |
| From compromised pod | `python main.py --blast-radius --source pod-webfront --hops 3` |
| To database | `python main.py --source user-dev1 --target db-production` |
| Find loops | `python main.py --cycles` |
| Find weak points | `python main.py --critical-node` |

---

## Using Your Own Data

Replace `docs/mock-cluster-graph.json` with your own cluster data:

```bash
# Export from real Kubernetes cluster
bash scripts/fetch_k8s_data.sh --context minikube

# Or use a different scenario
python main.py --input vulnerable-cluster.json --full-report
```

**Format:** Standard cluster-graph.json (see [docs/CLUSTER_GRAPH_SCHEMA.md](CLUSTER_GRAPH_SCHEMA.md))

---

## Troubleshooting

**"Module not found" error?**
```bash
cd backend
pip install -r requirements.txt
```

**"Port already in use"?**
```bash
# Use a different port
python -m uvicorn app.main:app --port 8001
```

**Graph looks empty?**
```bash
# Reload the graph
curl -X POST http://localhost:8000/api/graph/reload
```

---

## Next Steps

1. **Run full analysis:** `python main.py --full-report`
2. **Try all commands:** See [CLI_COMMAND_REFERENCE.md](CLI_COMMAND_REFERENCE.md)
3. **Understand algorithms:** Read [algorithms.md](algorithms.md)
4. **Integrate API:** See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

---

## Documentation Map

- **[README.md](../README.md)** — Full project overview
- **[QUICK_START.md](QUICK_START.md)** — You are here
- **[CLI_COMMAND_REFERENCE.md](CLI_COMMAND_REFERENCE.md)** — All CLI commands
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** — REST API endpoints
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design
- **[CLUSTER_GRAPH_SCHEMA.md](CLUSTER_GRAPH_SCHEMA.md)** — Data format
- **[algorithms.md](algorithms.md)** — Algorithm deep-dive
- **[TESTING.md](TESTING.md)** — Test strategy

---

## 5-Minute Demo Transcript

```bash
# Step 1: See all attacks
$ python main.py --full-report
# Output: 46 attack paths found, 1 cycle, critical nodes identified

# Step 2: From web server (compromised), where can attacker reach?
$ python main.py --blast-radius --source pod-webfront --hops 3
# Output: 13 nodes in 3 hops (includes database!)

# Step 3: What's the easiest path to the database?
$ python main.py --source user-dev1 --target db-production
# Output: 5-hop path through web-server → sa-webapp → secret-reader

# Step 4: Where are the choke points?
$ python main.py --critical-node
# Output: web-frontend is critical (69.6% of paths go through it)

# Step 5: Are there privilege loops?
$ python main.py --cycles
# Output: Found 1 cycle: svc-service-a ↔ svc-service-b
```

**Key findings in 5 commands:**
Attack paths discovered
Blast radius mapped
Critical nodes identified
Privilege loops detected
Remediation advice generated

---

**Ready? Try it:** `python main.py --help`
