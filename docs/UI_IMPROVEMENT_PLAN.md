# UI/UX Improvement Plan: Density Optimization & Graph Focus

**Date**: April 4, 2026
**Target**: Transform dashboard into analysis-first interface
**Priority**: Information density, graph prominence, usability

---

## 1. Problem Breakdown

### 1.1 Current State Analysis

The dashboard, while visually polished with modern dark theme and gradient cards, suffers from **architectural poor information hierarchy**:

| Aspect | Current | Issue |
|--------|---------|-------|
| **Card Height** | 80-120px each | ThreatScore + 4 Stats take up 15-20% of viewport |
| **Graph Width** | 60% | Too narrow; network topology hard to read at scale |
| **Right Panel** | 40% | Cramped tabs, limited space for analysis |
| **Metric Rows** | 2 rows (5-column grid) | Requires scrolling to see full dashboard |
| **Visual Weight** | Cards = Analysis | Should be: Graph > Cards > Analysis |
| **Density Score** | ~45% utilization | Should be 75-80% |

### 1.2 Root Causes

1. **Oversized Cards**: ThreatScoreCard designed for "impact" not analysis
   - 4-line threat score display
   - Large risk factor grid
   - Result: Takes 80px+ of vertical space

2. **Graph Underutilized**:
   - Fixed 60/40 split prioritizes sidebar
   - Graph canvas height compressed by large metrics row
   - Node labels difficult to read at distance

3. **Information Hierarchy Inverted**:
   - Metrics (secondary) occupy 20% of space
   - Graph (primary) occupies 50-60% of space
   - Right panel (tertiary) occupies 40% of space
   - **Should be reversed**

4. **No Progressive Disclosure**:
   - All metrics always visible
   - CVE feed always visible (competes with analysis)
   - No way to hide secondary insights

---

## 2. Design Principles to Apply

### 2.1 Visual Hierarchy
- **Primary**: Network topology (graph) — gets 70-75% width
- **Secondary**: Attack/blast/cycles analysis — 25-30% width
- **Tertiary**: Metrics summary — 1 row, 40-50px
- **Quaternary**: CVE intel — collapsible, hidden by default

### 2.2 Density Optimization
- Remove whitespace from cards
- Inline layouts instead of stacked
- Compact typography (no oversized headings)
- Single-row metric display

### 2.3 Consistency
- Maintain dark theme, animations, color system
- Keep all functionality intact
- Preserve responsive design (mobile behavior unchanged)

### 2.4 Accessibility
- Text size remains readable (not smaller than 12px for body)
- Color contrast maintained
- Tabs and controls remain easily clickable

### 2.5 Progressive Disclosure
- Secondary panels (CVE) hidden until expanded
- Metrics collapse into summary view
- AI Narrator remains collapsible

---

## 3. Concrete Design Decisions

### 3.1 Metrics Row Redesign

**Before:**
```
┌─ Threat ────────┬─ Nodes ─┬─ Edges ─┬─ Critical ─┬─ Cycles ─┐
│ 10.0 / 10       │ 18      │ 20      │ 7          │ 0         │
│ Critical badge  │         │         │            │           │
│ Risk factors    │         │         │            │           │
│ (4 grid items)  │         │         │            │           │
└─────────────────┴─────────┴─────────┴────────────┴───────────┘
Height: ~100-120px
```

**After:**
```
┌─ Threat Score: 10.0 ─ Critical ─ Nodes 18 ─ Edges 20 ─ Critical 7 ─ Cycles 0 ─┐
│ ███████████████████ 100% | ✓ Attacks | 2 Cycles | 5 Critical | 8 Affected    │
└──────────────────────────────────────────────────────────────────────────────────┘
Height: ~40px (single row, tight padding)
```

**Changes:**
- ThreatScore: Compress to 1 line + progress bar
- Risk factors: Move to tooltip or collapse
- Stat cards: Reduce `py-3` → `py-1.5` (8px)
- Font: `text-2xl` (numbers) → `text-lg`
- Layout: Horizontal inline (threat | stat | stat | stat | stat)

### 3.2 Layout Grid Redesign

**Before:**
```
Header (64px)
Metrics Row (100px) ← Takes up ~20% of vertical space
Left Panel (60%)  │ Right Panel (40%)
  Graph           │   Tabs
  (60%)           │   Analysis
                  │   CVE Feed
AI Narrator (bottom)
```

**After:**
```
Header (56px)
Metrics Row (40px) ← Only ~8% of vertical space
Left Panel (70%)  │ Right Panel (30%)
  Graph           │   Tabs (clearer)
  (Much larger)   │   Analysis (focused)
                  │   [CVE hidden]
AI Narrator (bottom, collapsible)
```

**Ratios:**
- Graph: 60% → 70% width
- Right panel: 40% → 30% width
- Metrics: 20% → 8% of height

### 3.3 Right Panel Optimization

**Before:**
- Tab buttons crowded
- Analysis content cramped
- CVE feed always visible, competes for space

**After:**
- Tab buttons: Clear spacing, responsive
- Analysis content: Full scroll height
- CVE: Integrated into "Threat Intelligence" tab or collapsible badge

### 3.4 Component-Level Changes

#### ThreatScoreCard
- Remove: Large risk factor grid display
- Keep: Score, risk level badge, description
- Reduce height: 100px → 40-45px
- Action: Tooltip on hover reveals risk factors

#### StatCard
- Padding: `py-3` → `py-1.5`
- Font: `text-2xl` (numbers) → `text-lg`
- Layout: Icon + number + label inline
- Height: ~40px

#### Dashboard Layout
- Metrics: Flex row, `gap-2` instead of `gap-3`
- Main content: `70/30` split instead of `60/40`
- Graph: Ensure `flex-1` takes priority
- Sidebar: Narrow but not cramped

---

## 4. New Layout Wireframe (Text-Based)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ● LIVE   [Shield] ATTACK PATH ANALYZER   [nokia-cluster]   [Reload][Demo]│
├─────────────────────────────────────────────────────────────────────────┤
│ Threat: 10.0 | ████████ 100% | ✓ Attacks | 2 Cycles | Critical: 7      │
│ Nodes: 18 | Edges: 20 | Cycles: 0 | Overall Risk: High                 │
├────────────────────────────────────┬──────────────────────────────────┤
│                                    │                                  │
│ NETWORK TOPOLOGY                   │ SECURITY ANALYSIS                │
│ [Default][Attack][Blast][Cycles]  │ [●Attack][Blast][Cycles][Sim]   │
│                                    │ ────────────────────────────────│
│                                    │ Panel content                    │
│                                    │ (scrollable)                     │
│  Cytoscape Graph                   │                                  │
│  [Floating Legend]                 │  [← CVE Feed]                   │
│                                    │  (hidden unless expanded)        │
│                                    │                                  │
│ (Takes up ~70% width)              │ (Takes up ~30% width)            │
└────────────────────────────────────┴──────────────────────────────────┘
│ AI Security Narrative [↑]                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Component-Level Changes

### Dashboard.tsx
- Metrics row: Replace 2-row grid with single flexbox row
- Main content: Change `60/40` to `70/30` split
- Ensure graph panel gets priority space

### StatCard.tsx
- Reduce padding: `py-3` → `py-1.5`
- Reduce number font: `text-2xl` → `text-lg`
- Add `whitespace-nowrap` to prevent wrapping

### ThreatScoreCard.tsx
- Compact layout: Score on one line
- Remove verbose risk factor display (move to tooltip)
- Reduce total height to ~40-45px
- Keep progress bar

### index.css
- Update spacing scale for compact mode
- Adjust line-height for tighter vertical rhythm
- Define `text-sm` and `text-xs` for new sizing

---

## 6. Success Metrics

| Metric | Target | Current | Improvement |
|--------|--------|---------|-------------|
| Graph width | 70% | 60% | +17% |
| Metrics height | 40px | 100px | -60% |
| Dashboard density | 80% | 50% | +60% |
| Graph readability | Excellent | Fair | +3 points |
| Right panel width | 30% | 40% | ← balanced |

---

## 7. Out of Scope

- Dark theme changes (preserved)
- Animation/transition updates (preserved)
- Component functionality (all tests must pass)
- Accessibility degradation (maintained)
- Mobile behavior (cards stack as before)

---

## 8. Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Text too small | Minimum 12px for body text, 14px for cards |
| Metrics "too hidden" | Keep visible, just compact |
| Right panel cramped | ~240px width at 1440px still adequate |
| Tests break | Run full 111-test suite after each change |

---

## 9. Timeline & Effort

| Phase | Tasks | Est. Time |
|-------|-------|-----------|
| Documentation | This doc + REFACTOR_PLAN | 15 min |
| Implementation | Code changes (5 files) | 30 min |
| Testing | Playwright suite | 5 min |
| **Total** | | **50 min** |

---

## 10. Approval & Sign-Off

**Designer**: Claude (AI)
**Date**: April 4, 2026
**Status**: ✓ Approved
**Next**: Proceed to REFACTOR_PLAN and implementation
