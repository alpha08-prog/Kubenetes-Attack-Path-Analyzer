# Judge Demo Guide - B2 & B3 Features

## Quick Start (2 minutes)

### 1. Start Backend & Frontend
```bash
# Terminal 1: Backend
cd backend
C:/Users/agraw/miniconda3/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Then open: http://localhost:5173

---

## B2: CVE Scoring Demo (1 minute)

### Show Live Container Security:
1. Go to **Dashboard** (click Dashboard button)
2. Click any **Pod node** (blue circles like `coredns-7d764666f9`, `etcd-minikube`)
3. Right sidebar appears with "Node Details"
4. Scroll down to **"Container Security"** section
5. You'll see:
   - Container image names
   - CVSS scores from NVD API
   - Severity badges (critical/high/medium/low)

**Judge Impact:**
- ✅ Automatic CVSS scoring from real vulnerabilities
- ✅ Per-image risk assessment
- ✅ Severity color-coded

---

## B3: Temporal Analysis Demo (1-2 minutes)

### One-Click Demo (No K8s Needed):

1. Click **"Temporal"** button in header
2. Scroll to top and find the **purple "Judge Demo" section**
3. Click **"Run Judge Demo"** button
4. Wait 3-5 seconds...

**What happens:**
- ✅ Baseline snapshot recorded (baseline state)
- ✅ Risk increased on all pods (simulate vulnerability discovered)
- ✅ New snapshot created (after-change state)
- ✅ Automatic comparison shown
- ✅ SSE event broadcast to Monitor tab

### See the Results:

**Timeline Tab** (default):
- Shows 2 data points on the risk chart
- First point (lower) = baseline
- Second point (higher) = after simulated change

**Compare Tab** (auto-selected):
- "Before" and "After" snapshots automatically populated
- **Key Metrics Shown:**
  - Nodes Δ: how many nodes changed
  - Edges Δ: relationship changes
  - New Paths: new attack paths discovered
  - New Cycles: new privilege escalation loops
  - Aggregate Risk Δ: risk increase amount
  - Severity badge: HIGH/CRITICAL alert

**Alerts Tab:**
- Shows the triggered alert with changes detected

---

## Demo Flow Explained

```
Step 1: Record Baseline
   └─ Cluster state captured

Step 2: Simulate Risk Increase
   └─ All pod risk scores increased by 2.5 (simulating CVE discovery)

Step 3: Create New Snapshot
   └─ New cluster state recorded

Step 4: Compare Snapshots
   └─ Shows attack path changes
   └─ Shows risk delta
   └─ Triggers severity alert

Step 5: Broadcast SSE Event
   └─ Real-time event sent to Monitor tab
   └─ Demonstrates streaming capabilities
```

---

## Real K8s Demo (Optional - 3 minutes)

If judges want to see **real cluster changes**:

### Step 1: Record Baseline
```
Monitor tab → "Record Baseline"
Shows: 155 nodes, 80 edges, 0 attack paths
```

### Step 2: Deploy Vulnerable Scenario
```
Monitor tab → "Deploy Vulnerable Scenario"
Creates: 7 K8s manifests
  • rogue pod (entry point)
  • backend service account (overprivileged)
  • admin role (wildcard)
  • db credentials (sensitive)
  • Plus 3 more misconfigured resources
```

### Step 3: Trigger Analysis
```
Monitor tab → "Trigger Analysis"
Graph rebuilds from kubectl
Detects new attack path:
  rogue-pod → backend-sa → admin-role → db-credentials → billing-db
```

### Step 4: View Temporal Diff in B3
```
B3 "Compare" tab
Before: 155 nodes, 0 paths
After: 162 nodes, 11 paths
Risk Δ: +1.5
Severity: HIGH
```

---

## Key Features to Highlight

### B2 - CVE Scoring
- [ ] Container image CVSS scores auto-fetched from NVD
- [ ] Per-image risk tracking
- [ ] Severity color coding (red=critical, orange=high)
- [ ] Works on real pod deployments

### B3 - Temporal Analysis
- [ ] One-click baseline recording
- [ ] Snapshot diff with granular changes
- [ ] Attack path delta detection
- [ ] Privilege escalation cycle detection
- [ ] Risk trend visualization
- [ ] Real-time SSE event broadcasting
- [ ] Severity-based alerts

---

## Judges Questions - Prepared Answers

**Q: How does it detect new attack paths?**
A: Dijkstra algorithm runs on all entry-to-target pairs between snapshots. If a path that didn't exist before now exists, it's detected as "new attack path."

**Q: What if the cluster doesn't change?**
A: Use the "Run Judge Demo" button - it simulates a vulnerability discovery (risk increase) between snapshots, showing the diff capability.

**Q: Can this work without Kubernetes?**
A: Yes! The demo button works in any mode. Real K8s demo requires kubectl and minikube running.

**Q: How accurate are the CVSS scores?**
A: They come directly from NIST NVD API, the official US government vulnerability database.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "0 snapshots stored" | Click "Run Judge Demo" to create snapshots |
| No CVSS scores showing | Click "Refresh" button in Container Security section |
| Compare tab shows all 0s | Create at least 2 snapshots first via "Run Judge Demo" |
| SSE not working | Check Monitor tab is open, SSE connection status shown |
| K8s deploy fails | Run `minikube start` first, ensure kubectl in PATH |

