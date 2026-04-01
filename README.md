# Attack Path Analyzer

> **Nokia Hackathon 2024** — Security Analytics Engine for Kubernetes Infrastructure

A full-stack security tool that models Kubernetes cluster resources as a directed graph and automatically identifies hidden attack paths, blast radius zones, privilege escalation loops, and critical chokepoints using classical graph algorithms — with AI-generated kill chain narratives powered by Gemini.

---

## Demo

```
Web Server → [uses] → backend-sa → [bound-to] → admin-role
          → [can-read] → db-credentials → [unlocks] → billing-db

⚠️  4-hop attack path detected
🔁  1 privilege escalation cycle: backend-sa → admin-role → backend-sa
🎯  Critical node: admin-role (betweenness centrality: 0.847)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│   Cytoscape.js Graph  │  Analysis Panels  │  AI Report      │
└────────────────────────────────┬────────────────────────────┘
                                 │ REST API
┌────────────────────────────────▼────────────────────────────┐
│                       Backend (FastAPI)                      │
│                                                             │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────┐  │
│  │ Ingestion│  │   Parser   │  │  Graph   │  │  Risk   │  │
│  │ Service  │→ │ (kubectl)  │→ │ Builder  │→ │ Engine  │  │
│  └──────────┘  └────────────┘  └────┬─────┘  └─────────┘  │
│                                     │                       │
│  ┌──────────────────────────────────▼──────────────────┐   │
│  │                   Algorithms                         │   │
│  │  BFS Blast Radius  │  Dijkstra Path  │  DFS Cycles  │   │
│  │  Betweenness Centrality                              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Gemini AI Narrator                       │   │
│  │  Algorithm results → Plain-English kill chain report │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │
         │ kubectl get pods/rolebindings/secrets
         ▼
┌─────────────────┐
│ Kubernetes      │
│ Cluster         │
│ (minikube/k3s)  │
└─────────────────┘
```

---

## Features

| Feature | Algorithm | Description |
|---|---|---|
| **Attack Path Detection** | Dijkstra | Finds lowest-cost route from any entry point to sensitive assets |
| **Blast Radius Mapping** | BFS | Identifies all reachable resources within N hops of a compromised node |
| **Privilege Escalation Detection** | DFS | Detects cyclic permission loops that allow indefinite privilege gain |
| **Critical Node Identification** | Betweenness Centrality | Ranks nodes by how many attack paths run through them |
| **Node Removal Simulation** | Graph diffing | Shows before/after impact of hardening any single node |
| **AI Kill Chain Narratives** | Gemini 2.0 Flash | Translates raw graph results into actionable security findings |

---

## Project Structure

```
attack-path-analyzer/
├── backend/
│   └── app/
│       ├── api/            # 7 FastAPI route files
│       ├── algorithms/     # BFS, Dijkstra, DFS, Centrality
│       ├── core/           # Graph builder, parser, risk engine, serializer
│       ├── models/         # Pydantic schemas
│       ├── services/       # Business logic + Gemini narrator
│       └── utils/          # Logger, helpers, prompt templates
├── frontend/
│   └── src/
│       ├── components/     # Cytoscape graph, panels, tables, modals
│       ├── pages/          # Dashboard + DemoMode
│       ├── hooks/          # useGraph, useAnalysis
│       └── api/            # Axios API client
├── data/
│   └── scenarios/
│       └── nokia_telecom.json   # 18-node demo scenario
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── Makefile
```

---

## Quick Start

### Option A — Docker (recommended)

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Clone the repo
git clone https://github.com/your-team/attack-path-analyzer.git
cd attack-path-analyzer

# 2. Set up environment
cp .env.example .env
# Edit .env — add your GEMINI_API_KEY (free at aistudio.google.com)

# 3. One command to start everything
make demo
```

Open `http://localhost:3000` — done.

---

### Option B — Local development

**Prerequisites:** Python 3.11+, Node.js 20+

```bash
# Terminal 1 — Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
python scripts/generate_mock_data.py
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

- Frontend → `http://localhost:5173`
- Backend API → `http://localhost:8000`
- Swagger UI → `http://localhost:8000/docs`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes (for AI report) | Free key from [aistudio.google.com](https://aistudio.google.com) |
| `MOCK_MODE` | No | `true` = load demo data, `false` = live kubectl (default: `true`) |
| `CLUSTER_NAME` | No | Display name in reports (default: `nokia-telecom-cluster`) |
| `DEBUG` | No | Verbose logging (default: `false`) |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/graph/` | Full graph in Cytoscape.js format |
| `GET` | `/api/graph/summary` | Node/edge counts and entry points |
| `POST` | `/api/graph/reload` | Re-ingest cluster data |
| `POST` | `/api/attack/path` | Dijkstra shortest attack path |
| `GET` | `/api/attack/auto` | Auto-detect and run best path |
| `POST` | `/api/blast/radius` | BFS blast radius from a node |
| `GET` | `/api/cycles/` | All privilege escalation cycles |
| `GET` | `/api/critical/nodes` | Centrality-ranked critical nodes |
| `POST` | `/api/simulate/remove` | Node removal what-if analysis |
| `GET` | `/api/report/` | AI-generated security report |

Full interactive docs at `http://localhost:8000/docs`

---

## Using with a Real Kubernetes Cluster

```bash
# Make sure minikube is running
minikube start

# Fetch live cluster data
bash backend/scripts/fetch_k8s_data.sh

# Set live mode in .env
MOCK_MODE=false

# Restart the backend
make dev-backend
```

For a realistic vulnerable cluster, deploy [Kubernetes Goat](https://github.com/madhuakula/kubernetes-goat) on minikube — it provides intentional misconfigurations that your tool detects as real attack paths.

```bash
git clone https://github.com/madhuakula/kubernetes-goat.git
cd kubernetes-goat
bash setup-kubernetes-goat.sh
```

---

## Demo Scenario

The default `nokia_telecom.json` scenario models a realistic Nokia telecom cluster with 18 nodes and 20 edges:

| Node | Type | Risk | Role in scenario |
|---|---|---|---|
| `web-server` | Pod | 7.5 | Public-facing entry point |
| `backend-sa` | Service Account | 8.5 | Overbroad permissions |
| `admin-role` | Role | 9.5 | Wildcard `*` permissions |
| `db-credentials` | Secret | 9.0 | Plaintext DB password |
| `billing-db` | Database | 9.5 | Primary target |
| `cluster-admin` | Role | 10.0 | Full cluster access |
| `ci-bot` | User | 7.5 | Over-privileged CI/CD user |

**Guaranteed findings:**
- 4-hop attack path: `web-server → backend-sa → admin-role → db-credentials → billing-db`
- 1 privilege escalation cycle: `backend-sa → admin-role → backend-sa`
- Critical node: `admin-role` (removing it breaks all attack paths to `billing-db`)

---

## Makefile Commands

```bash
make demo          # generate mock data + docker-compose up --build
make dev-backend   # run backend locally with hot reload
make dev-frontend  # run frontend locally with hot reload
make test          # run all backend tests
make mock          # regenerate nokia_telecom.json
make fetch         # fetch live data from kubectl
make logs          # tail all container logs
make down          # stop all containers
make clean         # remove containers, images, volumes
```

---

## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework
- [NetworkX](https://networkx.org/) — Graph construction and algorithms
- [Pydantic v2](https://docs.pydantic.dev/) — Data validation
- [Google Generative AI](https://ai.google.dev/) — Gemini 2.0 Flash narration
- [httpx](https://www.python-httpx.org/) — NVD CVE API client
- [Tenacity](https://tenacity.readthedocs.io/) — Retry logic

**Frontend**
- [React 18](https://react.dev/) + [Vite](https://vitejs.dev/)
- [Cytoscape.js](https://js.cytoscape.org/) — Interactive graph visualization
- [Tailwind CSS](https://tailwindcss.com/) — Styling
- [Recharts](https://recharts.org/) — Risk charts
- [Axios](https://axios-http.com/) — HTTP client

**Infrastructure**
- [Docker](https://www.docker.com/) + [Docker Compose](https://docs.docker.com/compose/)
- [nginx](https://nginx.org/) — Frontend serving + API proxy

---

## Team

Built for the Nokia Hackathon 2024.

---

## License

MIT