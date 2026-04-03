# Frontend Implementation Guide
## Attack Path Analyzer - QA Fixes

This guide provides code-level implementation details for all QA issues. Start with **Phase 1: Critical Fixes** and test after each change.

---

## Phase 1: Critical Fixes ⚠️

### Fix 1: Metrics Bar Overflow (Tablet 768px)

**Files to Modify**:
- `frontend/src/components/StatCard.tsx`
- `frontend/src/components/ThreatScoreCard.tsx`
- `frontend/src/pages/Dashboard.tsx`

**Issue**: Metrics bar elements overflow at 768px. Threat score card is 160px fixed, stat cards don't shrink.

#### Step 1.1: Update Dashboard.tsx Metrics Bar

**Current Code** (lines 120-157):
```jsx
<div className="flex-shrink-0 flex gap-2 px-3 sm:px-6 py-2 border-b border-border/60 overflow-x-auto scrollbar-thin">
  {/* Threat Score — compact */}
  <div className="w-40 flex-shrink-0">
    <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
  </div>

  {/* Stat cards — single row, flex layout */}
  <div className="flex-1 flex gap-2 min-w-0">
    <StatCard {...} />
    <StatCard {...} />
    <StatCard {...} />
    <StatCard {...} />
  </div>
</div>
```

**Replace with**:
```jsx
<div className="flex-shrink-0 flex gap-2 px-3 sm:px-6 py-2 border-b border-border/60 overflow-x-auto scrollbar-thin">
  {/* Threat Score — responsive width */}
  <div className="w-32 sm:w-36 md:w-40 flex-shrink-0">
    <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
  </div>

  {/* Stat cards — grid on mobile, flex on tablet+ */}
  <div className="flex-1 grid grid-cols-2 md:flex md:flex-row gap-1.5 sm:gap-2 min-w-0">
    <StatCard
      title="Total Nodes"
      value={summary?.total_nodes ?? '—'}
      icon={<Network className="w-3.5 h-3.5" />}
      color="#378ADD"
      loading={graphLoading}
    />
    <StatCard
      title="Total Edges"
      value={summary?.total_edges ?? '—'}
      icon={<GitBranch className="w-3.5 h-3.5" />}
      color="#1D9E75"
      loading={graphLoading}
    />
    <StatCard
      title="Critical Findings"
      value={summary?.critical_findings ?? '—'}
      icon={<AlertTriangle className="w-3.5 h-3.5" />}
      color="#E24B4A"
      loading={graphLoading}
    />
    <StatCard
      title="Cycles Detected"
      value={summary?.cycles_detected ?? '—'}
      icon={<RotateCcw className="w-3.5 h-3.5" />}
      color="#7F77DD"
      loading={graphLoading}
    />
  </div>
</div>
```

**What Changed**:
- Threat score width: responsive `w-32 sm:w-36 md:w-40`
- Stat cards: `grid grid-cols-2` on mobile (2x2), `md:flex` on tablet+ (1 row)
- Gap: reduced on mobile (`gap-1.5`), normal on tablet+ (`sm:gap-2`)

**Test**: Save and run `npm run test:e2e` to verify no overflow at 768px

---

#### Step 1.2: Update StatCard.tsx

**Current Code** (lines 13-42):
```jsx
export default function StatCard({ title, value, icon, color = 'hsl(var(--primary))', loading }: Props) {
  return (
    <div
      className="relative flex flex-col justify-between rounded-xl bg-card border border-border px-4 py-1.5 overflow-hidden h-full"
      style={{ borderLeftColor: color, borderLeftWidth: '3px' }}
    >
      {/* ... */}

      {/* Icon + title row */}
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-medium text-muted-foreground tracking-wide uppercase whitespace-nowrap">{title}</p>
        <div className="p-1 rounded-lg flex-shrink-0"
          style={{ backgroundColor: color + '1a' }}>
          <span style={{ color }}>{icon}</span>
        </div>
      </div>

      {/* Value */}
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      ) : (
        <p className="text-lg font-black tabular-nums text-foreground leading-tight whitespace-nowrap">{value}</p>
      )}
    </div>
  );
}
```

**Replace with**:
```jsx
export default function StatCard({ title, value, icon, color = 'hsl(var(--primary))', loading }: Props) {
  return (
    <div
      className="relative flex flex-col justify-between rounded-xl bg-card border border-border px-2 sm:px-4 py-1.5 overflow-hidden h-full"
      style={{ borderLeftColor: color, borderLeftWidth: '3px' }}
    >
      {/* Subtle background tint */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{ background: `radial-gradient(ellipse at top left, ${color}, transparent 70%)` }}
      />

      {/* Icon + title row */}
      <div className="flex items-start justify-between gap-1 mb-1">
        <p className="text-[9px] md:text-[10px] font-medium text-muted-foreground tracking-wide uppercase flex-1 truncate">
          {title}
        </p>
        <div className="p-1 rounded-lg flex-shrink-0"
          style={{ backgroundColor: color + '1a' }}>
          <span style={{ color }}>{icon}</span>
        </div>
      </div>

      {/* Value */}
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
      ) : (
        <p className="text-sm md:text-lg lg:text-xl font-black tabular-nums text-foreground leading-tight truncate">
          {value}
        </p>
      )}
    </div>
  );
}
```

**What Changed**:
- Padding: `px-4 py-1.5` → `px-2 sm:px-4 py-1.5` (responsive)
- Title: `text-[10px]` → `text-[9px] md:text-[10px]` + `truncate`
- Title row: `items-center` → `items-start` for better alignment
- Value: `text-lg` → `text-sm md:text-lg lg:text-xl` (responsive) + `truncate`
- Loader: `w-4` → `w-3.5` (consistent with icons)

**Test**: Verify stat cards fit on tablet (768px) without scrolling

---

#### Step 1.3: Update ThreatScoreCard.tsx

**Current Code** (lines 97-130):
```jsx
return (
  <div className={`rounded-xl border bg-card p-2.5 flex flex-col gap-2 ${cfg.borderColor} ${cfg.glowClass}`}>
    {/* Header row */}
    <div className="flex items-center justify-between">
      <span className="text-[9px] font-semibold tracking-widest text-muted-foreground uppercase">
        Threat
      </span>
      <span className={`flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${cfg.badgeBg} ${cfg.badgeText}`}>
        <Icon className="w-2.5 h-2.5" />
        {label}
      </span>
    </div>

    {/* Score + bar row */}
    <div className="flex items-center gap-2">
      <span className={`text-2xl font-black tabular-nums leading-none flex-shrink-0 ${cfg.scoreColor}`}>
        {loading ? '—' : score.toFixed(1)}
      </span>
      <div className="h-1 rounded-full bg-secondary overflow-hidden flex-1">
        <div className={`h-full rounded-full animate-fill-bar ${cfg.barColor}`}
          style={{ width: loading ? '0%' : `${pct}%` }} />
      </div>
    </div>

    {/* Description — single line only */}
    <p className="text-[9px] text-muted-foreground leading-tight line-clamp-1">
      {description}
    </p>
  </div>
);
```

**Replace with**:
```jsx
return (
  <div className={`rounded-xl border bg-card p-2 sm:p-2.5 flex flex-col gap-2 ${cfg.borderColor} ${cfg.glowClass}`}>
    {/* Header row */}
    <div className="flex items-center justify-between gap-1">
      <span className="text-[8px] md:text-[9px] font-semibold tracking-widest text-muted-foreground uppercase">
        Threat
      </span>
      <span className={`flex items-center gap-0.5 text-[9px] md:text-[10px] font-semibold px-1.5 md:px-2 py-0.5 rounded-full flex-shrink-0 ${cfg.badgeBg} ${cfg.badgeText}`}>
        <Icon className="w-2.5 h-2.5" />
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">{label.charAt(0)}</span>
      </span>
    </div>

    {/* Score + bar row */}
    <div className="flex items-center gap-1 sm:gap-2">
      <span className={`text-xl md:text-2xl lg:text-3xl font-black tabular-nums leading-tight flex-shrink-0 ${cfg.scoreColor}`}>
        {loading ? '—' : score.toFixed(1)}
      </span>
      <div className="h-1.5 rounded-full bg-secondary overflow-hidden flex-1">
        <div className={`h-full rounded-full animate-fill-bar ${cfg.barColor}`}
          style={{ width: loading ? '0%' : `${pct}%` }} />
      </div>
    </div>

    {/* Description — single line, responsive text */}
    <p className="text-[8px] md:text-[9px] text-muted-foreground leading-tight line-clamp-1">
      {description}
    </p>
  </div>
);
```

**What Changed**:
- Padding: `p-2.5` → `p-2 sm:p-2.5` (reduce padding on mobile)
- Header sizes: `text-[9px]` → `text-[8px] md:text-[9px]`
- Badge: hidden label on mobile, show only risk level letter
- Score: `text-2xl` → `text-xl md:text-2xl lg:text-3xl` (responsive)
- Bar height: `h-1` → `h-1.5` (more visible)
- Description: `text-[9px]` → `text-[8px] md:text-[9px]`

**Test**: Verify threat score card fits alongside stat cards at 768px

---

### Fix 2: Header Text Overflow (Mobile 375px)

**File**: `frontend/src/pages/Dashboard.tsx`

**Current Code** (lines 79-117):
```jsx
<header className="flex-shrink-0 flex flex-wrap items-center justify-between gap-2 px-4 sm:px-6 py-3 border-b border-border bg-card/80">
  {/* Left: branding */}
  <div className="flex items-center gap-3">
    {/* Live indicator */}
    <span className="hidden sm:flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 tracking-widest uppercase">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-live" />
      Live
    </span>

    <div className="w-px h-4 bg-border hidden sm:block" />

    <Shield className="w-5 h-5 text-primary flex-shrink-0" />
    <h1 className="text-sm font-bold text-foreground tracking-tight whitespace-nowrap">
      Attack Path Analyzer
    </h1>
    <span className="text-[11px] bg-primary/15 text-primary border border-primary/20 px-2 py-0.5 rounded-full font-medium hidden md:inline">
      nokia-telecom-cluster
    </span>
  </div>

  {/* Right: actions */}
  <div className="flex items-center gap-2">
    <button
      onClick={reload}
      disabled={graphLoading}
      className="flex items-center gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
    >
      <RefreshCw className={`w-3.5 h-3.5 ${graphLoading ? 'animate-spin' : ''}`} />
      <span className="hidden sm:inline">Reload Graph</span>
    </button>
    <button
      onClick={() => navigate('/demo')}
      className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-primary-foreground px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity"
    >
      <Play className="w-3.5 h-3.5" />
      Run Demo
    </button>
  </div>
</header>
```

**Replace with**:
```jsx
<header className="flex-shrink-0 flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 md:px-6 py-2 sm:py-3 border-b border-border bg-card/80">
  {/* Left: branding */}
  <div className="flex items-center gap-1.5 sm:gap-2 md:gap-3 min-w-0 flex-1">
    {/* Live indicator */}
    <span className="hidden sm:flex items-center gap-1 text-[8px] md:text-[10px] font-semibold text-emerald-400 tracking-widest uppercase flex-shrink-0">
      <span className="w-1 h-1 md:w-1.5 md:h-1.5 rounded-full bg-emerald-400 animate-live" />
      Live
    </span>

    <div className="w-px h-3 md:h-4 bg-border hidden sm:block flex-shrink-0" />

    <Shield className="w-4 md:w-5 h-4 md:h-5 text-primary flex-shrink-0" />
    <h1 className="text-xs md:text-sm lg:text-base font-bold text-foreground tracking-tight truncate">
      Attack Path Analyzer
    </h1>
    <span className="hidden md:inline text-[10px] lg:text-[11px] bg-primary/15 text-primary border border-primary/20 px-1.5 md:px-2 py-0.5 rounded-full font-medium flex-shrink-0">
      nokia-telecom-cluster
    </span>
  </div>

  {/* Right: actions */}
  <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
    <button
      onClick={reload}
      disabled={graphLoading}
      className="flex items-center gap-1 sm:gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-colors disabled:opacity-50"
      title="Reload graph data"
    >
      <RefreshCw className={`w-3 sm:w-3.5 h-3 sm:h-3.5 ${graphLoading ? 'animate-spin' : ''}`} />
      <span className="hidden sm:inline">Reload</span>
    </button>
    <button
      onClick={() => navigate('/demo')}
      className="flex items-center gap-1 sm:gap-1.5 bg-primary hover:opacity-90 text-primary-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-opacity"
      title="Start interactive demo"
    >
      <Play className="w-3 sm:w-3.5 h-3 sm:h-3.5" />
      <span className="hidden sm:inline">Demo</span>
    </button>
  </div>
</header>
```

**What Changed**:
- Header layout: Added `flex-wrap` already present, improved gap sizing
- Left side: Added `min-w-0 flex-1` for text truncation, reduced gaps on mobile
- Title: `text-sm` → `text-xs md:text-sm lg:text-base` (responsive), added `truncate`
- Cluster badge: Hidden on tablet and below (`hidden md:inline`)
- Buttons: Responsive padding, hidden labels on mobile (show only icon), reduced gaps
- Icons: Responsive sizes (`w-3 sm:w-3.5`)
- Added `title` attributes for tooltips on mobile

**Test**: Verify header fits without wrapping on mobile (375px)

---

### Fix 3: Stats Cards Layout on Mobile

**Already partially fixed in Fix 1**, but here's the verification:

After implementing Fix 1, the stats cards will automatically:
- Display as 2x2 grid on mobile (375px)
- Display as single row on tablet and above (768px+)
- Proper padding and spacing at all sizes

**Verification**:
```bash
npm run test:e2e -- --grep "stats flex row"
```

Should pass: ✅ `[mobile] stats flex row does not overflow at 375px`

---

## Phase 2: High Priority UX Fixes 🟠

### Fix 4: Add Loading States to Analysis Panels

**Files**:
- `frontend/src/components/AttackPathPanel.tsx`
- `frontend/src/components/BlastRadiusPanel.tsx`
- `frontend/src/components/CyclesPanel.tsx`
- `frontend/src/components/CriticalNodeTable.tsx`

**Pattern to Add**:

```jsx
// Add this pattern to each component that has loading prop:

{loading ? (
  <div className="flex flex-col items-center justify-center py-8 gap-2">
    <Loader2 className="w-4 h-4 animate-spin text-primary" />
    <span className="text-xs text-muted-foreground">Analyzing...</span>
  </div>
) : (
  // Existing content here
)}
```

**Example for AttackPathPanel** (add after tab content section):

```jsx
{loading ? (
  <div className="p-6 flex flex-col items-center justify-center gap-3">
    <Loader2 className="w-5 h-5 animate-spin text-primary" />
    <div className="text-center">
      <p className="text-sm font-medium text-foreground">Analyzing paths...</p>
      <p className="text-xs text-muted-foreground mt-1">This may take a few seconds</p>
    </div>
  </div>
) : (
  // Existing attack path content
)}
```

**Import Required**:
```jsx
import { Loader2 } from 'lucide-react';
```

---

### Fix 5: NarratorPanel Expand/Collapse Animation

**File**: `frontend/src/components/NarratorPanel.tsx`

**Current Code** (lines 62-107):
```jsx
<div className="flex-shrink-0 border-t border-border bg-card/90">
  {/* Trigger bar */}
  <button
    onClick={() => {
      setExpanded(!expanded);
      if (!expanded && !report && !loading) onFetchReport();
    }}
    className="w-full flex items-center justify-between px-4 sm:px-6 py-2.5 hover:bg-secondary/40 transition-colors group"
  >
    {/* ... */}
  </button>

  {/* Expanded content */}
  {expanded && (
    <div className="px-4 sm:px-6 pb-6 max-h-[50vh] overflow-y-auto scrollbar-thin border-t border-border/60">
      {/* content */}
    </div>
  )}
</div>
```

**Replace with**:
```jsx
<div className="flex-shrink-0 border-t border-border bg-card/90">
  {/* Trigger bar */}
  <button
    onClick={() => {
      setExpanded(!expanded);
      if (!expanded && !report && !loading) onFetchReport();
    }}
    className="w-full flex items-center justify-between px-4 sm:px-6 py-2.5 hover:bg-secondary/40 transition-colors duration-200 group"
  >
    {/* ... */}
  </button>

  {/* Expanded content */}
  {expanded && (
    <div className="px-4 sm:px-6 pb-6 max-h-[50vh] overflow-y-auto scrollbar-thin border-t border-border/60
      animate-in fade-in slide-in-from-top-2 duration-300"
    >
      {/* content */}
    </div>
  )}
</div>
```

**What Changed**:
- Button: Added `duration-200` to transition
- Content div: Added Shadcn animation classes:
  - `animate-in` - enable animations
  - `fade-in` - fade in effect
  - `slide-in-from-top-2` - slide down from top
  - `duration-300` - animation duration

**Note**: These classes are already available in Shadcn UI via `globals.css`

---

### Fix 6: Tab Underline Styling

**File**: `frontend/src/pages/Dashboard.tsx`

**Current Code** (lines 233-235):
```jsx
{activeTab === t.key && (
  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full" />
)}
```

**Replace with**:
```jsx
{activeTab === t.key && (
  <span className="absolute bottom-0 left-0 right-0 h-1 bg-primary" />
)}
```

**What Changed**:
- Removed `rounded-t-full` (makes underline look disconnected)
- Increased height: `h-0.5` → `h-1` (2px → 4px, more visible)

---

## Phase 3: Medium Priority Polish 🟡

### Fix 7: Standardize Icon Sizes

**Approach**: Create a consistent icon sizing system in components.

**Icon Size Standards**:
```
xs:  w-3 h-3      (12px)   → inline badges, labels
sm:  w-3.5 h-3.5  (14px)   → UI elements, buttons
md:  w-4 h-4      (16px)   → standard UI
lg:  w-5 h-5      (20px)   → prominent elements
xl:  w-6 h-6      (24px)   → major UI
2xl: w-8 h-8      (32px)   → large spinners
```

**Fix Application**:
- **StatCard icons**: `w-3.5 h-3.5` ✅ correct
- **Header icons**: `w-4 md:w-5` → standardize to `sm` size
- **Threat badge icons**: `w-2.5 h-2.5` → `w-3 h-3` (too small)
- **Loading spinners**: `w-4 h-4` → `w-5 h-5` (large spinners should be bigger)

**Example Fix - ThreatScoreCard Badge Icon**:
```jsx
// Current:
<Icon className="w-2.5 h-2.5" />

// Better:
<Icon className="w-3 h-3" />
```

---

### Fix 8: StatCard Alignment Improvements

**File**: `frontend/src/components/StatCard.tsx`

Already partially fixed in Fix 1. Verify these are applied:
- `items-center` → `items-start` (line 24)
- Added `truncate` to value
- Added `gap-1` to container

---

### Fix 9: ThreatScoreCard Value Alignment

**Already fixed in Fix 1.3** with:
- Changed `leading-none` → `leading-tight`
- Changed `h-1` → `h-1.5` (bar height)
- Responsive sizing

---

### Fix 10: Error State UI Pattern

**Create reusable error component**:

`frontend/src/components/ErrorBoundary.tsx`:
```jsx
import { AlertCircle } from 'lucide-react';

interface Props {
  error: string;
  onRetry: () => void;
}

export function ErrorState({ error, onRetry }: Props) {
  return (
    <div className="flex items-center gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
      <AlertCircle className="w-4 h-4 flex-shrink-0 text-destructive" />
      <div className="flex-1">
        <p className="text-sm font-medium text-destructive">{error}</p>
        <button
          onClick={onRetry}
          className="text-xs underline mt-2 hover:no-underline text-destructive hover:text-destructive/80"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
```

**Usage in Panels**:
```jsx
{error && <ErrorState error={error} onRetry={onAnalyze} />}
```

---

## Testing After Each Fix

### Test Command
```bash
# Run all tests
npm run test:e2e

# Run specific test
npm run test:e2e -- --grep "metrics bar"

# Run on specific viewport
npm run test:e2e -- --project=mobile
```

### Manual Testing Checklist
```
[ ] Desktop (1440x900)
  [ ] Header fits without wrap
  [ ] Metrics bar single row
  [ ] All content visible

[ ] Tablet (768x1024)
  [ ] Header fits without wrap
  [ ] Metrics bar fits (no h-scroll)
  [ ] Cards sized appropriately

[ ] Mobile (375x812)
  [ ] Header fits, title truncates
  [ ] Metrics cards in 2x2 grid
  [ ] No horizontal overflow
  [ ] Buttons still clickable
```

---

## File Modification Order

**Recommended order to minimize conflicts**:

1. `frontend/src/pages/Dashboard.tsx` (metrics bar, header, tabs)
2. `frontend/src/components/StatCard.tsx` (card styling)
3. `frontend/src/components/ThreatScoreCard.tsx` (threat card styling)
4. `frontend/src/components/NarratorPanel.tsx` (animations)
5. Analysis panels (AttackPathPanel, BlastRadiusPanel, etc.)

---

## Verification Steps

After implementing all Phase 1 fixes:

```bash
# 1. Start dev server
npm run dev

# 2. Run tests
npm run test:e2e

# 3. Verify all 111 tests pass
# Expected output: "111 passed"

# 4. Manual visual check at each viewport
# Desktop: check proportions
# Tablet: check no overflow
# Mobile: check readability and layout

# 5. Check console for errors
# Should be clean (except expected 404 for /nonexistent route)
```

---

## Notes for Implementation

- **Don't remove existing styles** - build on top of them
- **Test early and often** - run tests after each file change
- **Check responsiveness** - resize browser window to verify
- **Look for regressions** - ensure fixes don't break other areas
- **Mobile first** - make sure fixes work at 375px first, then scale up

---

## Common Issues & Solutions

### "Grid layout not working on mobile"
**Solution**: Ensure parent has `flex-wrap` or `grid` class. Double-check Tailwind classes are spelled correctly.

### "Text still overflows"
**Solution**: Add `truncate` or `line-clamp-1` classes. Verify container has max-width.

### "Icons misaligned"
**Solution**: Use `flex items-center` on container. Check icon sizes match expected values.

### "Animations not playing"
**Solution**: Ensure `@layer utilities` CSS is loaded. Check class names match Tailwind animation names.

---

**Implementation Status**: Ready to Code
**Estimated Time**: 2-4 hours for all fixes
**Difficulty**: Medium (mostly CSS/Tailwind adjustments)

Good luck! 🚀
