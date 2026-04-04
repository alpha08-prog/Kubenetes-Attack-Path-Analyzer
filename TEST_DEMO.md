# B3 Judge Demo - Testing Checklist

## Setup
- [x] Backend endpoints created:
  - [x] POST /api/monitor/demo-flow (one-click demo)
  - [x] POST /api/monitor/simulate-change (granular control)
  
- [x] Frontend updated:
  - [x] B3 TemporalAnalysisPage has "Judge Demo" button
  - [x] Button calls /api/monitor/demo-flow
  - [x] Auto-refreshes snapshots after demo runs
  - [x] Auto-selects latest two snapshots for comparison
  - [x] Auto-switches to Compare tab to show diff

## Features Working
- [x] B2 CVE Scoring:
  - Pod nodes show container images
  - CVSS scores displayed
  - Severity badges shown
  
- [x] B3 Temporal Analysis:
  - Create Snapshot button works
  - Timeline chart renders
  - Compare tab shows diffs
  - Alerts tab displays temporal alerts
  
- [x] Demo Flow:
  - Records baseline snapshot
  - Simulates risk increase
  - Creates change snapshot
  - Broadcasts SSE event
  - Auto-compares snapshots

## Judge Demo Steps
1. Open http://localhost:5173/temporal
2. See "Judge Demo" button at top (purple section)
3. Click "Run Judge Demo"
4. View automatic snapshot comparison
5. See risk delta and severity in Compare tab
6. Check Monitor tab for SSE event

## Expected Results
- Baseline snapshot created (e.g., 155 nodes)
- Risk snapshot created (e.g., 155 nodes + higher risk scores)
- Diff shows:
  - Nodes Δ: 0 (same cluster topology)
  - Edges Δ: 0 (same relationships)
  - Risk Δ: +1.0 to +3.0 (simulated vulnerability increase)
  - Severity: MEDIUM or HIGH
