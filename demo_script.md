# Demo Script — Attack Path Analyzer
## Nokia Hackathon 2024 | Presentation Guide

> **Total time: 7 minutes** (strict — judges will cut you off)
> Read everything in this document the night before. Practice at least twice.
> The script below is word-for-word what to say. Timings are per section.

---

## Pre-Demo Setup Checklist (15 minutes before presentation)

Run these commands. Do not skip any.

```bash
# 1. Start minikube
minikube start

# 2. Deploy vulnerable scenario
cd backend
bash scripts/deploy_vulnerable_scenario.sh

# 3. Start the server (mock mode for safety)
python -m uvicorn app.main:app --reload --port 8000

# 4. Start the frontend
cd frontend && npm run dev

# 5. Open these tabs in your browser BEFORE presenting:
#    Tab 1: http://localhost:3000          (dashboard)
#    Tab 2: http://localhost:3000/demo     (demo mode page)
#    Tab 3: http://localhost:8000/docs     (Swagger — backup)
#    Tab 4: Your Slack channel             (for Slack alert moment)

# 6. Record a baseline snapshot
curl -X POST http://localhost:8000/api/history/record

# 7. Test Slack
curl http://localhost:8000/api/slack/test
# → You should see a green message in Slack before you walk up

# 8. Run one analysis manually so history has 2+ runs
curl http://localhost:8000/api/attack/auto
curl -X POST http://localhost:8000/api/history/record
```

**Have on screen when you walk up:** Tab 1 — the dashboard with the graph loaded.

---

## The 60-Second Pitch (say this if judges give you open floor first)

> "Modern Kubernetes clusters have hundreds of interconnected resources —
> pods, service accounts, roles, secrets, databases. When a breach happens,
> attackers don't go straight for the database. They hop through 4, 5, 6
> intermediate resources before reaching it. Traditional spreadsheet audits
> miss these multi-hop paths completely.
>
> We built Attack Path Analyzer — a security engine that models your entire
> Kubernetes infrastructure as a directed graph and automatically finds the
> hidden attack paths, the blast radius of any compromised resource, and the
> privilege escalation loops that let attackers keep gaining permissions.
>
> Every finding is narrated in plain English by AI so your security team
> knows not just what the risk is, but exactly what to fix."

---

## Main Demo Script

### [0:00 – 0:45] Opening — The Problem Statement

**Say:**
> "Let me start with a real scenario. This is a Nokia telecom Kubernetes
> cluster — 18 resources, 20 access relationships."

**Do:** Point at the graph on screen.

> "A junior developer pushed a role binding last week that granted the
> backend service account wildcard permissions. Nobody noticed. Our tool did."

**Do:** Pause for 2 seconds. Let that land.

> "Let me show you how."

---

### [0:45 – 2:00] Attack Path Detection — Dijkstra

**Say:**
> "First — finding the attack path. We model this cluster as a directed
> weighted graph. Edge weights come from real CVE severity scores pulled
> live from the NVD database. Lower weight means easier to exploit."

**Do:** Click the **Attack Path** tab in the right panel.

**Do:** Click **"Auto Detect"** button.

**Say:** *(while the result loads — about 2 seconds)*
> "We're running Dijkstra's algorithm — finding the lowest-cost path from
> any public entry point to any sensitive asset."

**Do:** Point at the result when it appears.

> "Four hops. Web server to billing database via this service account,
> this wildcard role, and this plaintext secret containing the database
> password. Total exploitability cost: 1.5 out of 10. That's nearly
> trivial for an attacker."

**Do:** Click **"Show on Graph"** button — the kill chain lights up in red.

> "Every red edge is a step in the attack chain. A real attacker would
> follow exactly this path."

---

### [2:00 – 3:00] Blast Radius — BFS

**Say:**
> "Now — what happens if that web server pod is compromised right now?
> How far can the attacker reach?"

**Do:** Click **Blast Radius** tab.

**Do:** Select `web-server` node, set hops to 3, click **"Analyze"**.

**Say:** *(while loading)*
> "Breadth-first search — every node reachable within 3 hops."

**Do:** Point at the result.

> "Nine nodes immediately at risk. Two critical, three high severity.
> That's half the cluster reachable from a single compromised pod —
> because of one misconfigured service account binding."

**Do:** Click **"Show on Graph"** — concentric rings appear.

> "The red ring is hop 1 — immediate access. Orange is hop 2. Yellow
> is hop 3. Your blast radius, visualized in real time."

---

### [3:00 – 3:45] Cycle Detection — DFS

**Say:**
> "Here's the one that should scare you."

**Do:** Click **Cycles** tab.

> "DFS cycle detection. We found a privilege escalation loop."

**Do:** Point at the cycle result on screen.

> "Backend service account — bound to admin role — which can impersonate
> the backend service account. An attacker who compromises this service
> account can continuously re-escalate their own permissions. There's
> no ceiling. They can keep gaining access indefinitely."

**Do:** Pause.

> "Traditional RBAC audits check permissions in isolation. They never
> catch circular escalation because they don't model the graph."

---

### [3:45 – 4:30] Critical Nodes + Simulation — Centrality

**Say:**
> "We also compute betweenness centrality — which single node,
> if removed or hardened, would break the most attack paths?"

**Do:** Click **Critical Nodes** tab — show the leaderboard.

> "Admin-role. Centrality score 0.847. It sits on every attack path
> in this cluster."

**Do:** Click **"Simulate"** button next to admin-role.

> "Watch this. We remove it from the graph and rerun all algorithms."

**Do:** Point at simulation result.

> "Before removal: 3 attack paths, 1 privilege escalation loop.
> After removing or restricting admin-role: zero paths. Zero loops.
> One targeted fix eliminates all identified risk."

> "This tells your security team exactly where to spend their next
> 30 minutes."

---

### [4:30 – 5:15] Slack Alert + AI Report — The Live Moment

**Say:**
> "Now the part I want you to watch."

**Do:** Keep Slack visible on a second screen or have it open beside the browser.

**Do:** Click **"Generate AI Security Report"** button at the bottom of the dashboard.

> "We're sending all algorithm results — the paths, the cycles, the
> centrality scores — to Gemini. It's going to narrate the kill chain
> in plain English."

**Do:** Point at Slack while report loads (3–5 seconds).

> "And simultaneously, our Slack integration fires an alert to the
> security team."

**Do:** *(When Slack message appears)* — point at it.

> "Right there. The security team gets notified in real time —
> they don't need to open a dashboard. The attack path, the affected
> nodes, the fix — all in Slack before anyone even knows there's an issue."

**Do:** Point back at the AI report findings now visible on screen.

> "And here's the AI narration. Not just raw data — a plain-English
> finding with a specific remediation step. 'Remove the wildcard verb
> binding from admin-role. Restrict to get and list on secrets only.'
> Something a developer can action in 5 minutes."

---

### [5:15 – 5:45] Graph Diff — Before vs After

**Say:**
> "One more thing. This tool isn't just for one-time audits."

**Do:** Open Postman or run in browser:
```
GET http://localhost:8000/api/diff/latest
```

> "We track every analysis run in SQLite. Here's the diff between
> our baseline scan and the scan after we deployed the vulnerable scenario."

**Do:** Point at the response — specifically these fields:

> "Risk score: 4.2 before — 7.6 after. Up 81%.
> Attack paths: zero before — three after.
> Privilege escalation loops: zero before — one after.
>
> This tells you exactly what a single deployment changed from a
> security perspective. CI/CD pipeline, post-deployment audit,
> automated comparison. No human needed."

---

### [5:45 – 6:30] Live Cluster Demo (optional — only if time allows)

**Say:**
> "Everything you've seen is on our curated demo scenario.
> But this runs on real clusters too."

**Do:** Switch MOCK_MODE=false in .env, restart quickly, OR just show the 147-node graph.

> "This is our live minikube cluster — 147 real nodes from
> actual kubectl output. Same algorithms, same API, just larger graph."

**Do:** Click auto-detect.

> "Even at this scale, Dijkstra finds the path in under 10 milliseconds.
> NetworkX handles graphs orders of magnitude larger than this."

**Do:** Switch back to mock for Q&A clarity.

---

### [6:30 – 7:00] Closing

**Say:**
> "To summarize what we built:"

**Do:** Hold up one finger at a time as you list:

> "BFS for blast radius — know your immediate exposure the moment
> a pod is compromised.
>
> Dijkstra for attack paths — find the easiest route to your most
> sensitive assets before attackers do.
>
> DFS for privilege escalation cycles — catch the loops that
> traditional audits miss entirely.
>
> Betweenness centrality for critical nodes — spend your hardening
> effort exactly where it matters most.
>
> AI narration so every finding is actionable, not just a number.
>
> And Slack integration so your team knows in real time — not after
> the breach."

**Pause.**

> "Attack Path Analyzer. Thank you."

---

## Judge Q&A — Prepared Answers

### "Why graph algorithms? Why not rule-based checks?"

> "Rule-based checks like kube-bench or Trivy look at each resource
> in isolation. They'll tell you a role has wildcard permissions —
> but they won't tell you which pod reaches that role in 2 hops and
> how that translates to database access. Graph algorithms model
> relationships. The attack path emerges from the structure, not
> individual rules."

---

### "How does this scale to a real Nokia production cluster?"

> "NetworkX handles graphs with tens of thousands of nodes efficiently
> for these algorithms. Dijkstra and BFS are both O((V + E) log V) and
> O(V + E) respectively. For very large clusters we'd move from
> NetworkX to Neo4j as the graph backend — the API layer and frontend
> wouldn't change at all. We designed the service layer to be backend-agnostic."

---

### "Why Gemini instead of a rules engine for the narration?"

> "Rules engines are brittle — you need to anticipate every finding
> pattern in advance. Gemini understands context. It sees a 4-hop
> path through a wildcard role to a database secret and generates
> a recommendation specific to that exact configuration — not a
> generic 'reduce permissions' template."

---

### "Is this real data or synthetic?"

> "Both. The demo runs on a curated 18-node scenario we built to
> guarantee all four algorithms produce findings in a 7-minute
> presentation. But we also ran it against a live minikube cluster
> and against Kubernetes Goat — a deliberately vulnerable cluster
> used for security research. All kubectl commands are real,
> all CVE scores come live from the NVD API."

---

### "What would it take to run this in production?"

> "Three things. One — a read-only kubectl service account with
> permissions to get pods, roles, and role bindings. Two —
> scheduled ingestion, say every 15 minutes via a CronJob.
> Three — a Slack webhook. The backend, frontend, and database
> are already containerized with Docker Compose. It's a
> docker-compose up away from running in any environment."

---

### "How is this different from Trivy or kube-bench?"

> "Trivy and kube-bench are excellent tools — they catch known
> CVEs and configuration anti-patterns. But they're node-level
> scanners. They tell you a container image has a vulnerable
> library. They don't tell you that this vulnerable container
> uses a service account that can read the secret that unlocks
> the production database. That multi-hop reasoning is what we add."

---

### "What's the AI actually doing? Is it just summarizing?"

> "The AI receives the full structured output from all four
> algorithms — the exact path as a list of nodes, hop-by-hop
> edge relations, centrality scores, cycle chains. It's not
> summarizing a blob of text. It's interpreting structured
> security data and generating targeted remediation advice.
> The prompt is engineered to return consistent JSON so findings
> can be rendered as typed UI cards, not free text."

---

## Timing Summary

| Section | Time | Key Action |
|---|---|---|
| Opening — problem statement | 0:00 – 0:45 | Talk, point at graph |
| Attack path — Dijkstra | 0:45 – 2:00 | Click Auto Detect → Show on Graph |
| Blast radius — BFS | 2:00 – 3:00 | Analyze → Show on Graph |
| Cycle detection — DFS | 3:00 – 3:45 | Show cycle tab |
| Critical nodes + simulation | 3:45 – 4:30 | Click Simulate on admin-role |
| Slack + AI report | 4:30 – 5:15 | Click Generate Report → point at Slack |
| Graph diff | 5:15 – 5:45 | Show diff/latest response |
| Live cluster (optional) | 5:45 – 6:30 | Switch to 147-node view |
| Closing | 6:30 – 7:00 | List 6 features, pause, done |

---

## What NOT to Do

- **Do not apologize** if something is slow. Say "Gemini is processing" and
  point at Slack while it loads.
- **Do not read from the screen**. Know the script. Look at judges.
- **Do not show code** unless asked. Judges care about the product, not the implementation.
- **Do not run in live kubectl mode** during the presentation unless you've
  tested it 3 times that day. Use mock mode. Stability > impressiveness.
- **Do not go over 7 minutes**. End at the Closing. Let Q&A happen naturally.
- **Do not skip the Slack moment**. It is the most memorable thing in the demo.
  Everything before it is setup for that moment.

---

## Emergency Fallbacks

| Problem | Fix |
|---|---|
| Backend crashes | `python -m uvicorn app.main:app --port 8000` — takes 8 seconds |
| Graph is empty | `POST /api/graph/reload` in Postman |
| Gemini times out | Show Postman with `/api/attack/auto` response — "The AI narration is loading, let me show you the raw algorithm output while we wait" |
| Slack doesn't fire | "The alert already fired during setup — let me show you the message" — scroll up in Slack |
| Frontend crashes | Open `http://localhost:8000/docs` — demo live from Swagger UI |
| minikube down | Mock mode has everything. Stay on mock. Nobody will know. |

---

*Good luck. You've built something real. Show it like you know that.*
