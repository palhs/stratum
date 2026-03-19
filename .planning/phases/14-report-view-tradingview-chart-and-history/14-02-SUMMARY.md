---
phase: 14-report-view-tradingview-chart-and-history
plan: 02
subsystem: ui
tags: [react, lightweight-charts, react-markdown, tailwind, vitest, typescript]

# Dependency graph
requires:
  - phase: 14-report-view-tradingview-chart-and-history
    provides: "OHLCVPoint and ReportContentResponse types in types.ts, @tailwindcss/typography plugin in globals.css"
  - phase: 12-next-js-core-shell-and-dashboard
    provides: "TierBadge component, shadcn Button/Card/Skeleton/Badge UI primitives"
provides:
  - "ReportSummaryCard: tier badge + Macro/Valuation/Structure sub-assessments + verdict + expand/collapse button"
  - "BilingualToggle: fixed-position VI/EN language switcher with aria-pressed"
  - "TradingViewChart: lightweight-charts v5 candlestick + MA50 (blue) + MA200 (orange) + volume histogram"
  - "ReportMarkdown: ReactMarkdown+remarkGfm prose renderer with lang attribute"
  - "ReportPageSkeleton: loading state placeholders"
affects: [14-03-report-page-client, future-report-view-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "vi.hoisted() for mocks referencing top-level variables in vi.mock factory (vitest)"
    - "lightweight-charts v5 addSeries(CandlestickSeries/LineSeries/HistogramSeries, options) API"
    - "chart.priceScale('volume').applyOptions() for secondary scale margins"

key-files:
  created:
    - frontend/src/components/report/ReportSummaryCard.tsx
    - frontend/src/components/report/BilingualToggle.tsx
    - frontend/src/components/report/TradingViewChart.tsx
    - frontend/src/components/report/ReportMarkdown.tsx
    - frontend/src/components/report/ReportPageSkeleton.tsx
    - frontend/src/components/report/__tests__/ReportSummaryCard.test.tsx
    - frontend/src/components/report/__tests__/BilingualToggle.test.tsx
    - frontend/src/components/report/__tests__/TradingViewChart.test.tsx
  modified: []

key-decisions:
  - "lightweight-charts v5 uses chart.addSeries(CandlestickSeries, opts) not chart.addCandlestickSeries(opts) — v4 convenience methods removed in v5"
  - "vi.hoisted() required when vi.mock factory references variables defined outside factory — hoisting prevents initialization order errors"

patterns-established:
  - "TDD Red-Green cycle: write failing tests first, then implement to pass"
  - "vi.hoisted() pattern for lightweight-charts mocks in vitest test files"

requirements-completed: [RVEW-01, RVEW-03, RVEW-04]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 14 Plan 02: Report Leaf Components Summary

**Five tested React components: ReportSummaryCard (tier+assessments+expand), BilingualToggle (fixed VI/EN), TradingViewChart (lightweight-charts v5 candlestick+MA50+MA200+volume), ReportMarkdown (prose), ReportPageSkeleton (loading state)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T06:41:20Z
- **Completed:** 2026-03-19T06:45:20Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- ReportSummaryCard renders TierBadge, three sub-assessment labels, verdict text, and expand/collapse button with aria-expanded
- BilingualToggle floats fixed top-4 right-4 with VI/EN buttons, aria-pressed state, and aria-label="Report language"
- TradingViewChart uses lightweight-charts v5 addSeries API with candlestick, MA50 (blue line), MA200 (orange line), and volume histogram with secondary price scale — chart.remove() cleanup on unmount
- ReportMarkdown renders prose-styled markdown via ReactMarkdown + remarkGfm with article lang attribute
- ReportPageSkeleton provides loading state placeholders for summary card, chart, and timeline rows

## Task Commits

Each task was committed atomically:

1. **Task 1: ReportSummaryCard and BilingualToggle components with tests** - `3d81770` (feat)
2. **Task 2: TradingViewChart, ReportMarkdown, and ReportPageSkeleton with tests** - `59ebbb2` (feat)

_Note: TDD tasks — tests written first (RED), then components implemented (GREEN)_

## Files Created/Modified
- `frontend/src/components/report/ReportSummaryCard.tsx` - Summary card with tier hero, sub-assessments, verdict, expand/collapse button
- `frontend/src/components/report/BilingualToggle.tsx` - Fixed-position language toggle with VI/EN buttons
- `frontend/src/components/report/TradingViewChart.tsx` - TradingView Lightweight Charts v5 wrapper with candlestick, MA50, MA200, volume
- `frontend/src/components/report/ReportMarkdown.tsx` - ReactMarkdown prose renderer with lang attribute
- `frontend/src/components/report/ReportPageSkeleton.tsx` - Loading skeleton placeholders
- `frontend/src/components/report/__tests__/ReportSummaryCard.test.tsx` - 6 tests
- `frontend/src/components/report/__tests__/BilingualToggle.test.tsx` - 6 tests
- `frontend/src/components/report/__tests__/TradingViewChart.test.tsx` - 5 tests

## Decisions Made
- lightweight-charts v5 uses `chart.addSeries(CandlestickSeries, opts)` — v4 convenience methods `addCandlestickSeries`, `addLineSeries`, `addHistogramSeries` were removed in v5
- `vi.hoisted()` is required when referencing outer variables inside `vi.mock()` factory due to hoisting behavior in vitest

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated lightweight-charts from v4 to v5 addSeries API**
- **Found during:** Task 2 (TradingViewChart component implementation)
- **Issue:** Plan used v4 API (`addCandlestickSeries`, `addLineSeries`, `addHistogramSeries`) which do not exist on `IChartApi` in v5 — TypeScript emitted errors
- **Fix:** Updated component to use `chart.addSeries(CandlestickSeries, opts)`, `chart.addSeries(LineSeries, opts)`, `chart.addSeries(HistogramSeries, opts)` per v5 API. Updated test mock to expose `addSeries` instead of per-type methods and added `vi.hoisted()` for safe mock initialization.
- **Files modified:** `TradingViewChart.tsx`, `TradingViewChart.test.tsx`
- **Verification:** All 48 tests pass, `npx tsc --noEmit` passes for all new files
- **Committed in:** `59ebbb2` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Necessary correctness fix — lightweight-charts v5 breaking change. No scope creep.

## Issues Encountered
- Pre-existing TypeScript error in `Sparkline.test.tsx` (unrelated to this plan) — out of scope, deferred

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All five leaf components are ready for consumption by ReportPageClient orchestrator in Plan 03
- TradingViewChart is a default export (compatible with Next.js `dynamic({ ssr: false })` wrapping in Plan 03)
- All components are "use client" — Plan 03 can import them directly

## Self-Check: PASSED

All created files confirmed present on disk. All task commits verified in git log.

---
*Phase: 14-report-view-tradingview-chart-and-history*
*Completed: 2026-03-19*
