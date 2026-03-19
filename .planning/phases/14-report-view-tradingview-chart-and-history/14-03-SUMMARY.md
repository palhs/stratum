---
phase: 14-report-view-tradingview-chart-and-history
plan: 03
subsystem: ui
tags: [react, next.js, typescript, vitest, lucide-react, date-fns, tailwind]

# Dependency graph
requires:
  - phase: 14-01
    provides: "API functions (getOhlcv, getReportHistory, getReportContent) and types (ReportHistoryItem, ReportContentResponse, OHLCVPoint)"
  - phase: 14-02
    provides: "ReportSummaryCard, BilingualToggle, TradingViewChart, ReportMarkdown, ReportPageSkeleton components"
provides:
  - "HistoryTimeline component: report history list with tier change arrows, active row highlighting, load-more pagination"
  - "ReportPageClient orchestrator: wires all report page components with state management"
  - "reports/[symbol]/page.tsx: server wrapper with auth guard and token passing"
  - "Complete /reports/[symbol] page with chart, history timeline, bilingual toggle"
affects: [future phases using report view, any phase building on /reports routing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TIER_RANK map for ordinal tier comparison (Favorable=0 through Avoid=3)"
    - "getTierChange function: up/down/none based on rank delta"
    - "cancelled flag pattern in useEffect for safe async state updates"
    - "Promise.all for parallel OHLCV + history fetch on mount"
    - "dynamic({ ssr: false }) for TradingViewChart to avoid SSR crashes"
    - "localStorage persistence for language preference with key 'stratum-report-lang'"
    - "In-place report switching: URL unchanged, content swapped via state"

key-files:
  created:
    - frontend/src/components/report/HistoryTimeline.tsx
    - frontend/src/components/report/__tests__/HistoryTimeline.test.tsx
    - frontend/src/components/report/ReportPageClient.tsx
    - frontend/src/components/report/__tests__/ReportPageClient.test.tsx
  modified:
    - frontend/src/app/reports/[symbol]/page.tsx

key-decisions:
  - "ArrowUp/ArrowDown from lucide-react with aria-label attributes for screen reader accessibility on tier change arrows"
  - "getAllByText used in ReportPageClient tests because verdict and tier appear in both ReportSummaryCard and HistoryTimeline rows"
  - "Pre-existing TypeScript error in Sparkline.test.tsx (unrelated to Plan 03 changes) deferred — confirmed pre-existing via git stash check"

patterns-established:
  - "TDD: test file created first (RED), component created second (GREEN) — HistoryTimeline followed this pattern"
  - "Tier comparison via TIER_RANK record + integer comparison — reusable pattern for any tier-ranked logic"
  - "History row is a <button> inside <li> for semantic HTML and keyboard accessibility"

requirements-completed: [RVEW-02, RHST-01, RHST-02, RHST-03, RHST-04]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 14 Plan 03: HistoryTimeline + ReportPageClient Orchestrator Summary

**HistoryTimeline component with upgrade/downgrade arrows plus ReportPageClient wiring all report components into a complete /reports/[symbol] page**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T06:47:56Z
- **Completed:** 2026-03-19T06:51:58Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- HistoryTimeline renders report history rows with date, TierBadge, verdict snippet, and teal/rose ArrowUp/ArrowDown arrows with accessibility aria-labels
- ReportPageClient orchestrates state for report content, OHLCV chart, language toggle, expand/collapse, and paginated history — all wired in a single client component
- Server page.tsx replaces placeholder with auth guard (redirect /login) and passes symbol.toUpperCase() + accessToken to ReportPageClient
- 26 tests passing across both new test files (15 HistoryTimeline, 11 ReportPageClient)

## Task Commits

Each task was committed atomically:

1. **Task 1: HistoryTimeline component with upgrade/downgrade arrows and tests** - `138f5be` (feat)
2. **Task 2: ReportPageClient orchestrator and page.tsx server wrapper** - `e905f6f` (feat)

## Files Created/Modified
- `frontend/src/components/report/HistoryTimeline.tsx` - History timeline list with tier rank arrows, active row, load-more, empty/loading states
- `frontend/src/components/report/__tests__/HistoryTimeline.test.tsx` - 15 tests for all HistoryTimeline behaviors
- `frontend/src/components/report/ReportPageClient.tsx` - Client orchestrator managing all report page state and component composition
- `frontend/src/components/report/__tests__/ReportPageClient.test.tsx` - 11 tests for ReportPageClient behaviors
- `frontend/src/app/reports/[symbol]/page.tsx` - Server page with Supabase auth guard and ReportPageClient rendering

## Decisions Made
- Used `getAllByText` in ReportPageClient tests where verdict/tier appear in both ReportSummaryCard and HistoryTimeline — same content visible in two places by design
- Confirmed via git stash that TypeScript error in Sparkline.test.tsx is pre-existing and out of scope for Plan 03
- ArrowUp/ArrowDown use `aria-label` attribute (not `aria-description`) matching the plan spec: "Upgraded from {prev} to {curr}"

## Deviations from Plan

None - plan executed exactly as written. The test file adjustment (using `getAllByText` instead of `getByText`) was a test correctness fix, not a deviation from plan spec — the component behavior matched spec exactly; the test needed to account for duplicate text that the full rendered page naturally produces.

## Issues Encountered
- `getByText('Strong entry quality.')` threw "Found multiple elements" because the verdict appears in both ReportSummaryCard and HistoryTimeline. Fixed by using `getAllByText` and asserting length > 0.
- Same issue for `getByText('Favorable')`. Fixed identically.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 14 complete: all 3 plans executed. The /reports/[symbol] page is fully built with chart, bilingual toggle, history timeline, and expand/collapse markdown.
- Ready for Phase 15 (Settings/Profile or next planned phase per ROADMAP.md)
- No blockers

---
*Phase: 14-report-view-tradingview-chart-and-history*
*Completed: 2026-03-19*
