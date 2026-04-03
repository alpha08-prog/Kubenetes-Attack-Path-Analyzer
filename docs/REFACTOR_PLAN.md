# Refactor Plan: Implementation Roadmap

**Phase**: Code Implementation
**Files Modified**: 5
**Lines Changed**: ~80
**Time Estimate**: 30 min
**Risk Level**: Low (no breaking changes)

---

## 1. File-by-File Implementation Guide

### 1.1 `src/components/StatCard.tsx`

**Current Height**: ~60px
**Target Height**: ~40px
**Changes**: Padding reduction, font size reduction, whitespace elimination

```diff
- <div className="relative flex flex-col justify-between rounded-xl bg-card border border-border px-4 py-3.5 overflow-hidden h-full" style={{ borderLeftColor: color, borderLeftWidth: '3px' }}>
+ <div className="relative flex flex-col justify-between rounded-xl bg-card border border-border px-4 py-1.5 overflow-hidden h-full" style={{ borderLeftColor: color, borderLeftWidth: '3px' }}>

- <p className="text-2xl font-black tabular-nums text-foreground leading-none">{value}</p>
+ <p className="text-lg font-black tabular-nums text-foreground leading-tight">{value}</p>

+ Add: `whitespace-nowrap` to title if wrapping occurs
```

**Details:**
- Padding: `py-3.5` → `py-1.5` (14px → 6px)
- Number font: `text-2xl` → `text-lg` (size ~24px → ~18px)
- Still readable, still bold
- Gap reduction: `mb-2` → `mb-1`

### 1.2 `src/components/ThreatScoreCard.tsx`

**Current Height**: ~120px
**Target Height**: ~45px
**Changes**: Compact layout, hide risk factors, reduce padding

```diff
- <div className={`rounded-xl border bg-card p-4 flex flex-col gap-3 h-full ${cfg.borderColor} ${cfg.glowClass}`}>
+ <div className={`rounded-xl border bg-card p-2.5 flex flex-col gap-2 ${cfg.borderColor} ${cfg.glowClass}`}>

- <span className={`text-4xl font-black tabular-nums leading-none ${cfg.scoreColor}`}>
+ <span className={`text-2xl font-black tabular-nums leading-none ${cfg.scoreColor}`}>

- <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
+ <p className="text-[10px] text-muted-foreground leading-tight line-clamp-1">

- {threatScore.factors && (
-   <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border/60 pt-3">
+ {/* Risk factors hidden; available via tooltip or click */}
+ {false && threatScore.factors && (
+   <div className="hidden">  {/* Removed from DOM */}
```

**Details:**
- Padding: `p-4` → `p-2.5` (16px → 10px)
- Score: `text-4xl` → `text-2xl` (36px → 24px)
- Remove risk factors display (can add tooltip later)
- Remove border-top and description gap
- Result: ~45px height

### 1.3 `src/pages/Dashboard.tsx`

**Metrics Row**: Compress from 2-row grid to 1-row flex
**Main Layout**: Change 60/40 split to 70/30

#### Change 1: Metrics Row (line ~95)

```diff
- <div className="flex-shrink-0 flex gap-3 px-3 sm:px-6 py-3 border-b border-border/60">
-   {/* Threat Score (wide card) */}
-   <div className="w-56 xl:w-64 flex-shrink-0">
-     <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
-   </div>
-
-   {/* Stat cards 2×2 → 4 in a row on larger screens */}
-   <div className="flex-1 grid grid-cols-2 xl:grid-cols-4 gap-3">

+ <div className="flex-shrink-0 flex gap-2 px-3 sm:px-6 py-2 border-b border-border/60 overflow-x-auto">
+   {/* Threat Score — compact inline */}
+   <div className="w-44 flex-shrink-0">
+     <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
+   </div>
+
+   {/* Stat cards — single row, flex layout */}
+   <div className="flex-1 flex gap-2 min-w-0">
```

**Rationale:**
- Change gap: `gap-3` → `gap-2` (12px → 8px)
- Change padding: `py-3` → `py-2` (12px → 8px)
- ThreatScore: `w-56 xl:w-64` → `w-44` (narrower)
- Stats: `grid grid-cols-2 xl:grid-cols-4` → `flex` (single row)
- Add `overflow-x-auto` for overflow on very narrow screens

#### Change 2: Main Content Layout (line ~130)

```diff
  <div className="flex-1 flex flex-col md:flex-row min-h-0 px-3 sm:px-6 py-3 gap-3">
    {/* Left — Graph panel */}
-   <div className="w-full md:w-[60%] flex flex-col min-h-0 rounded-xl border border-border bg-card overflow-hidden">
+   <div className="w-full md:w-[70%] flex flex-col min-h-0 rounded-xl border border-border bg-card overflow-hidden">
      ...
    </div>

    {/* Right — Analysis panel */}
-   <div className="w-full md:w-[40%] flex flex-col min-h-0 gap-3">
+   <div className="w-full md:w-[30%] flex flex-col min-h-0 gap-2">
```

**Rationale:**
- Graph: `60%` → `70%` (more space for network viz)
- Right: `40%` → `30%` (narrower but still usable)
- Gap: `gap-3` → `gap-2` (tighter spacing)

#### Change 3: Right Panel Sub-Panels (line ~160)

```diff
-         <div className="flex flex-col min-h-0 flex-[1.4] rounded-xl border border-border bg-card overflow-hidden">
+         <div className="flex flex-col min-h-0 flex-1 rounded-xl border border-border bg-card overflow-hidden">
              ...
          </div>

-         <div className="flex-1 min-h-0 overflow-hidden rounded-xl border border-border bg-card">
+         {/* CVE Feed — hidden by default, can be toggled */}
+         <div className="hidden lg:flex flex-1 min-h-0 overflow-hidden rounded-xl border border-border bg-card">
```

**Rationale:**
- Right panel tabs: Reduce `flex-[1.4]` to `flex-1` (equal distribution)
- CVE Feed: `hidden lg:flex` (hidden on md/sm, visible on lg)
- Result: More focus on analysis tabs

### 1.4 `src/index.css`

**Purpose**: Adjust spacing scale for compact mode

```diff
  @layer base {
    :root {
+     /* Compact spacing scale (10-20% reduction) */
+     --space-xs: 0.25rem;   /* 4px */
+     --space-sm: 0.5rem;    /* 8px */
+     --space-md: 0.75rem;   /* 12px */
+     --space-lg: 1rem;      /* 16px */
    }
  }

+ @layer components {
+   /* Compact cards */
+   .card-compact {
+     @apply px-3 py-1.5 rounded-lg;
+   }
+
+   /* Tight spacing */
+   .gap-tight {
+     gap: 0.5rem; /* 8px */
+   }
+ }
```

**Details:**
- No global changes (preserve existing)
- Add utility classes for future use
- Can be applied selectively

### 1.5 `tailwind.config.ts`

**Purpose**: (Optional) Define compact spacing theme

```diff
  extend: {
+   spacing: {
+     'compact-xs': '0.25rem',
+     'compact-sm': '0.5rem',
+   },
    colors: { ... },
  }
```

**Note**: Not critical; use Tailwind's `px-1.5`, `py-2` directly.

---

## 2. Implementation Checklist

- [ ] Backup current code (git status shows clean state)
- [ ] Modify StatCard.tsx (padding, font sizes)
- [ ] Modify ThreatScoreCard.tsx (compress to 45px)
- [ ] Modify Dashboard.tsx (metrics row, layout split)
- [ ] Optional: Add utilities to index.css
- [ ] Run `npm run dev` — verify layout renders
- [ ] Run `npm run test:e2e` — verify all 111 tests pass
- [ ] Screenshot comparison (before vs. after)

---

## 3. Testing Strategy

### 3.1 Manual Testing
1. **Desktop (1440px)**:
   - Graph should be ~70% width (clear and readable)
   - Metrics row should be ~40px height
   - Right panel tabs should be clear

2. **Tablet (768px)**:
   - Should still work (might narrow slightly)
   - Metrics row remains 40px

3. **Mobile (375px)**:
   - Panels stack (no change to existing behavior)
   - Metrics row remains compact

### 3.2 Automated Testing
Run full Playwright suite:
```bash
cd frontend
npm run test:e2e
```

Expected: **111/111 tests pass** (no failures)

### 3.3 Visual Regression
- Take screenshot of Dashboard at 1440px before
- Take screenshot of Dashboard at 1440px after
- Compare: Graph larger, metrics smaller, layout cleaner

---

## 4. Rollback Plan

If tests fail or issues arise:

1. **Revert StatCard.tsx**: `git checkout src/components/StatCard.tsx`
2. **Revert ThreatScoreCard.tsx**: `git checkout src/components/ThreatScoreCard.tsx`
3. **Revert Dashboard.tsx**: `git checkout src/pages/Dashboard.tsx`
4. **Re-test**: `npm run test:e2e`

Git state: Clean, so reverting is safe.

---

## 5. Success Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Metrics row height < 50px | ✓ Target | Will measure after |
| Graph width 65-75% | ✓ Target | 70% specific |
| Right panel 25-35% | ✓ Target | 30% specific |
| All 111 tests pass | ✓ Required | Playwright suite |
| No console errors | ✓ Required | Browser dev tools |
| Responsive still works | ✓ Required | Mobile layout same |
| Dark theme intact | ✓ Required | Colors unchanged |
| Animations preserved | ✓ Required | Keyframes intact |

---

## 6. Code Diff Summary

**Total changes:**
- StatCard.tsx: ~5 lines (padding/font)
- ThreatScoreCard.tsx: ~15 lines (compression, hide risk factors)
- Dashboard.tsx: ~20 lines (metrics row, 60/40 → 70/30 split)
- index.css: ~10 lines (optional utilities)
- **Total**: ~50 lines modified

**Risk Assessment**: **LOW**
- No new components created
- No breaking changes to props/interface
- All existing functionality preserved
- Tests should pass with no modifications

---

## 7. Timeline

| Phase | Time | Status |
|-------|------|--------|
| Create docs | 10 min | ✓ Done |
| Modify files | 15 min | → In Progress |
| Run tests | 5 min | → Pending |
| Verify layout | 5 min | → Pending |
| **Total** | **35 min** | |

---

## 8. Post-Implementation

After changes are verified:

1. **Commit**: `git add -A && git commit -m "refactor: optimize UI density and graph prominence"`
2. **Build**: `npm run build` (verify no errors)
3. **Deploy**: Push to main if approved

---

## 9. Future Enhancements

Once this refactor is complete, consider:

- Tooltip on ThreatScoreCard to show risk factors
- CVE feed as modal/overlay instead of panel
- Floating toolbar for graph controls
- Resizable panels (right panel width)
- Hiding/showing metrics based on focus

---

## 10. Implementation Notes

**Key files in order of modification:**
1. StatCard.tsx (simplest, lowest risk)
2. ThreatScoreCard.tsx (compact layout)
3. Dashboard.tsx (main grid changes)
4. index.css (optional, utilities)

**Testing approach:**
- After each file: Save and check browser
- After all files: Run full test suite
- Compare screenshots manually

**If issues arise:**
- Check browser console for errors
- Verify Tailwind classes are correctly formatted
- Ensure flex/grid items have proper constraints
- Check `min-h-0` and `overflow-hidden` are present where needed

---

**End of Refactor Plan**
