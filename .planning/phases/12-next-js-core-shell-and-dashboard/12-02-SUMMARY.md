---
phase: 12-next-js-core-shell-and-dashboard
plan: 02
subsystem: ui
tags: [nextjs, react, tailwind, shadcn, typescript, vitest, svg, testing-library]

# Dependency graph
requires:
  - phase: 12-next-js-core-shell-and-dashboard (plan 01)
    provides: shadcn/ui components, Supabase SSR helpers, Vitest infra, dashboard route group
  - phase: 11-supabase-auth-and-per-user-watchlist
    provides: Backend watchlist/OHLCV/report API endpoints with Bearer auth
provides:
  - TypeScript interfaces mirroring all backend Pydantic schemas (lib/types.ts)
  - Typed fetch layer for watchlist, OHLCV, report history, and watchlist mutation (lib/api.ts)
  - TierBadge component with TIER_STYLES map (teal/slate/amber/rose per tier)
  - Sparkline pure SVG polyline with green/red directional color
  - TickerCard: symbol+name, tier badge, sparkline, last report date, link to /reports/{symbol}
  - TickerCardSkeleton: shimmer skeleton matching card layout
  - WatchlistGrid: responsive 3-column grid with aria-live
  - WatchlistGridSkeleton: 6 skeleton cards
  - EmptyState: "Your watchlist is empty" + 5 quick-add buttons with aria-labels
  - ErrorState: centered message + Try again button
  - DashboardClient: 'use client' fetch lifecycle (loading/empty/error/stale-data states)
  - 18 unit tests across TierBadge, Sparkline, EmptyState, DashboardClient
affects: [13-report-detail-page, 14-tradingview-charts]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TIER_STYLES Record<string, string> map pattern for badge color mapping
    - Pure SVG polyline sparkline with no external dependencies
    - Promise.all fan-out pattern for parallel per-ticker data fetching
    - satisfies TickerData — TypeScript satisfies operator for type-safe object construction

key-files:
  created:
    - frontend/src/lib/types.ts (WatchlistItem, WatchlistResponse, OHLCVPoint, OHLCVResponse, ReportHistoryItem, ReportHistoryResponse, TickerData)
    - frontend/src/lib/api.ts (getWatchlist, getOhlcv, getLastReport, addTickerToWatchlist)
    - frontend/src/components/dashboard/TierBadge.tsx
    - frontend/src/components/dashboard/Sparkline.tsx
    - frontend/src/components/dashboard/TickerCard.tsx
    - frontend/src/components/dashboard/TickerCardSkeleton.tsx
    - frontend/src/components/dashboard/WatchlistGrid.tsx
    - frontend/src/components/dashboard/WatchlistGridSkeleton.tsx
    - frontend/src/components/dashboard/EmptyState.tsx
    - frontend/src/components/dashboard/ErrorState.tsx
    - frontend/src/components/dashboard/DashboardClient.tsx
    - frontend/src/components/dashboard/__tests__/TierBadge.test.tsx
    - frontend/src/components/dashboard/__tests__/Sparkline.test.tsx
    - frontend/src/components/dashboard/__tests__/EmptyState.test.tsx
    - frontend/src/components/dashboard/__tests__/DashboardClient.test.tsx
  modified:
    - frontend/src/app/(dashboard)/page.tsx (DashboardClient + accessToken wiring)
    - docker-compose.yml (NEXT_PUBLIC_API_URL for frontend service)

key-decisions:
  - "NEXT_PUBLIC_API_URL env var targets host-mapped reasoning-engine port (8001) for client-side fetches — no nginx proxy in Phase 12"
  - "satisfies TickerData in Promise.all map — TypeScript structural type check at construction site without losing inference"
  - "range = max - min || 1 in Sparkline — guards against division by zero on flat OHLCV data"
  - "loadDashboard in useCallback with accessToken dep — stable reference prevents useEffect infinite loop"

patterns-established:
  - "DashboardClient pattern: 'use client' component receives accessToken prop from server page, owns all async fetch state"
  - "Parallel ticker enrichment: getWatchlist then Promise.all per ticker for OHLCV + last report — O(1) round trips after watchlist fetch"
  - "Stale data toast pattern: if tickers.length > 0 on error, show toast and keep existing data; only show ErrorState on first-load failure"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05]

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 12 Plan 02: Dashboard Components and DashboardClient Summary

**Watchlist dashboard built end-to-end: TierBadge (teal/slate/amber/rose), pure SVG sparkline (green/red), TickerCard linking to /reports/{symbol}, DashboardClient with parallel fan-out fetch lifecycle and stale-data toast — 18 unit tests passing, Next.js build clean.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T00:33:16Z
- **Completed:** 2026-03-19T00:37:54Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments

- All dashboard presentational components implemented with correct tier badge colors and sparkline direction colors per UI-SPEC.md
- DashboardClient orchestrates the full fetch lifecycle: getWatchlist -> parallel getOhlcv + getLastReport per ticker, all 5 states handled (loading/empty/error/stale/data)
- 18 unit tests cover TierBadge (4), Sparkline (5), EmptyState (4), DashboardClient (5) — all passing
- Next.js 16.2 build compiles cleanly with TypeScript passing

## Task Commits

Each task was committed atomically:

1. **Task 1: TypeScript types, API fetch layer, and dashboard presentational components with tests** - `1c091b1` (feat)
2. **Task 2: DashboardClient wiring and dashboard page integration with fetch lifecycle tests** - `983eb75` (feat)

## Files Created/Modified

- `frontend/src/lib/types.ts` - WatchlistItem, WatchlistResponse, OHLCVPoint, OHLCVResponse, ReportHistoryItem, ReportHistoryResponse, TickerData
- `frontend/src/lib/api.ts` - fetchAPI helper with Bearer auth, getWatchlist, getOhlcv, getLastReport, addTickerToWatchlist
- `frontend/src/components/dashboard/TierBadge.tsx` - TIER_STYLES map, teal/slate/amber/rose, em-dash no-report state
- `frontend/src/components/dashboard/Sparkline.tsx` - pure SVG polyline, green-600/red-600 directional color, flat-data guard
- `frontend/src/components/dashboard/TickerCard.tsx` - Link wrapper to /reports/{symbol}, hover:shadow-md, tier badge + sparkline + date
- `frontend/src/components/dashboard/TickerCardSkeleton.tsx` - animate-pulse shimmer skeleton
- `frontend/src/components/dashboard/WatchlistGrid.tsx` - responsive grid-cols-1/2/3, aria-live="polite"
- `frontend/src/components/dashboard/WatchlistGridSkeleton.tsx` - 6 skeleton instances
- `frontend/src/components/dashboard/EmptyState.tsx` - "Your watchlist is empty", 5 quick-add buttons, aria-labels, min-h-[44px]
- `frontend/src/components/dashboard/ErrorState.tsx` - "Couldn't load your watchlist", Try again button
- `frontend/src/components/dashboard/DashboardClient.tsx` - 'use client', useCallback loadDashboard, Promise.all fan-out, 5 render states
- `frontend/src/app/(dashboard)/page.tsx` - DashboardClient with accessToken from server session
- `docker-compose.yml` - NEXT_PUBLIC_API_URL: http://${VPS_HOST:-localhost}:8001 for frontend service
- `frontend/src/components/dashboard/__tests__/TierBadge.test.tsx` - 4 tests
- `frontend/src/components/dashboard/__tests__/Sparkline.test.tsx` - 5 tests
- `frontend/src/components/dashboard/__tests__/EmptyState.test.tsx` - 4 tests
- `frontend/src/components/dashboard/__tests__/DashboardClient.test.tsx` - 5 tests

## Decisions Made

- **NEXT_PUBLIC_API_URL for client-side fetches:** Phase 12 has no nginx proxy — client-side API calls target the host-mapped reasoning-engine port directly (8001). env var approach avoids hardcoding and allows dev/prod differentiation.
- **satisfies TickerData operator:** Used at the Promise.all return site to get structural type checking without losing inference on the mapped object properties.
- **range || 1 in Sparkline:** Flat OHLCV data (all close prices equal) produces min===max, causing range=0 and NaN coordinates. Defaulting to 1 renders a flat horizontal line correctly.
- **useCallback with [accessToken] dep on loadDashboard:** Required to keep the useEffect stable — without it, every render creates a new function reference and triggers infinite fetch loops.

## Deviations from Plan

None — plan executed exactly as written. The `.env.example` update was skipped from git commit because the project's `.gitignore` has `.env*` pattern which catches `.env.example`. The file was updated on disk but not committed (consistent with existing project convention).

## Issues Encountered

None.

## User Setup Required

Add `NEXT_PUBLIC_API_URL` to your `.env.local` (or deployment environment):
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```
On VPS deployment: set to `http://{vps-ip}:8001` or use the `VPS_HOST` variable in docker-compose.yml.

## Next Phase Readiness

- Dashboard is fully functional — all 5 states (loading/empty/error/stale/data) implemented
- `/reports/[symbol]` placeholder page accepts navigation from TickerCard clicks
- All TypeScript interfaces in lib/types.ts are ready for Phase 13 (report detail page)
- API fetch layer in lib/api.ts can be extended with report/analytics endpoints in Phase 14

---
*Phase: 12-next-js-core-shell-and-dashboard*
*Completed: 2026-03-19*
