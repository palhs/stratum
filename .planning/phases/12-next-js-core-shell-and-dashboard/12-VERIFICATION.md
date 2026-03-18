---
phase: 12-next-js-core-shell-and-dashboard
verified: 2026-03-19T00:00:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 12: Next.js Core Shell and Dashboard Verification Report

**Phase Goal:** Users can open a browser, log in, and see their watchlist as an actionable dashboard of entry quality cards with sparklines
**Verified:** 2026-03-19
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                        | Status     | Evidence                                                                          |
|----|------------------------------------------------------------------------------|------------|-----------------------------------------------------------------------------------|
| 1  | Next.js app starts in Docker with mem_limit 512m                             | VERIFIED   | docker-compose.yml line 341: `mem_limit: 512m` under `frontend:` service          |
| 2  | Unauthenticated users are redirected to /login                               | VERIFIED   | proxy.ts:28-30: `!user && isProtectedRoute` -> redirect to /login                |
| 3  | Authenticated users visiting /login are redirected to /                      | VERIFIED   | proxy.ts:31-33: `user && isAuthRoute` -> redirect to /                           |
| 4  | User can submit email and password on the login form                         | VERIFIED   | LoginForm.tsx: 'use client', onSubmit handler calls signInWithPassword            |
| 5  | Successful login redirects to dashboard                                      | VERIFIED   | LoginForm.tsx:35-36: `router.push('/'); router.refresh()` on no authError        |
| 6  | Vitest runs with jsdom environment and React Testing Library                 | VERIFIED   | vitest.config.ts: environment: 'jsdom'; setup.ts imports jest-dom/vitest         |
| 7  | Dashboard shows a card for each watchlist ticker                             | VERIFIED   | WatchlistGrid.tsx renders TickerCard per ticker; DashboardClient wires getWatchlist |
| 8  | Each card shows the entry quality tier badge color-coded (teal/slate/amber/rose) | VERIFIED | TierBadge.tsx: TIER_STYLES map with bg-teal-100/bg-slate-100/bg-amber-100/bg-rose-100 |
| 9  | Each card shows a 52-week sparkline (green if up, red if down)               | VERIFIED   | Sparkline.tsx: polyline with #16a34a (green) or #dc2626 (red) based on direction |
| 10 | Each card shows the last report date                                         | VERIFIED   | TickerCard.tsx:9-11: Intl.DateTimeFormat formats lastReport.generated_at          |
| 11 | Dashboard shows skeleton shimmer cards while loading                         | VERIFIED   | DashboardClient.tsx:73: `if (loading) return <WatchlistGridSkeleton />`          |
| 12 | Dashboard shows empty state with quick-add buttons when watchlist is empty   | VERIFIED   | DashboardClient.tsx:75: EmptyState rendered; EmptyState.tsx: 5 buttons (VNM,FPT,HPG,GLD,MWG) |
| 13 | Dashboard shows error state with retry button on fetch failure               | VERIFIED   | DashboardClient.tsx:74: `<ErrorState message={error} onRetry={loadDashboard} />`  |
| 14 | Clicking a card navigates to /reports/{symbol}                               | VERIFIED   | TickerCard.tsx:15: `<Link href={\`/reports/${ticker.symbol}\`}>`                  |

**Score:** 14/14 truths verified

---

### Required Artifacts

#### Plan 01 Artifacts (INFR-01)

| Artifact                                      | Provides                           | Status     | Details                                                    |
|-----------------------------------------------|------------------------------------|------------|------------------------------------------------------------|
| `frontend/Dockerfile`                         | Multi-stage standalone build       | VERIFIED   | 3 stages (deps/builder/runner); copies .next/standalone    |
| `frontend/next.config.ts`                     | Standalone output config           | VERIFIED   | `output: 'standalone'`                                     |
| `frontend/src/proxy.ts`                       | Auth route protection (was middleware.ts) | VERIFIED | createServerClient, getUser(), redirect logic        |
| `frontend/src/components/login/LoginForm.tsx` | Login form with Supabase auth      | VERIFIED   | 'use client', signInWithPassword, error + loading states   |
| `docker-compose.yml`                          | Frontend service definition        | VERIFIED   | mem_limit: 512m, context: ./frontend, depends_on engine    |

Note: The plan specifies `frontend/src/middleware.ts` but the actual file is `frontend/src/proxy.ts` — a documented deviation from Next.js 16.2's renamed convention. The artifact provides the same functionality under the correct filename.

#### Plan 02 Artifacts (DASH-01 through DASH-05)

| Artifact                                                        | Provides                                       | Status   | Details                                            |
|-----------------------------------------------------------------|------------------------------------------------|----------|----------------------------------------------------|
| `frontend/src/lib/types.ts`                                     | TypeScript types mirroring backend schemas     | VERIFIED | TickerData, WatchlistResponse, OHLCVResponse, ReportHistoryResponse all present |
| `frontend/src/lib/api.ts`                                       | Typed fetch functions for backend API          | VERIFIED | getWatchlist, getOhlcv, getLastReport, addTickerToWatchlist all exported with Bearer auth |
| `frontend/src/components/dashboard/TierBadge.tsx`               | Color-coded tier badge component               | VERIFIED | TIER_STYLES map, all 4 tier colors, em-dash fallback |
| `frontend/src/components/dashboard/Sparkline.tsx`               | Pure SVG polyline sparkline                    | VERIFIED | polyline, #16a34a/#dc2626, flat-data guard (range \|\| 1), aria-hidden |
| `frontend/src/components/dashboard/DashboardClient.tsx`         | Client component owning fetch lifecycle        | VERIFIED | 'use client', getWatchlist call, Promise.all fan-out, 5 render states |
| `frontend/src/components/dashboard/EmptyState.tsx`              | Empty watchlist UI with quick-add buttons      | VERIFIED | "Your watchlist is empty", VNM + 4 others, aria-labels |
| `frontend/src/components/dashboard/TickerCard.tsx`              | Card linking to /reports/{symbol}              | VERIFIED | Link href=/reports/{symbol}, TierBadge + Sparkline + date |
| `frontend/src/components/dashboard/WatchlistGrid.tsx`           | Responsive grid with aria-live                 | VERIFIED | grid-cols-1 sm:grid-cols-2 lg:grid-cols-3, aria-live="polite" |
| `frontend/src/components/dashboard/WatchlistGridSkeleton.tsx`   | 6 skeleton shimmer cards                       | VERIFIED | renders 6 TickerCardSkeleton instances             |
| `frontend/src/components/dashboard/ErrorState.tsx`              | Error message + retry button                   | VERIFIED | "Couldn't load your watchlist", Try again button   |
| `frontend/src/components/dashboard/__tests__/TierBadge.test.tsx`   | TierBadge unit tests                        | VERIFIED | file exists, 4 tests                              |
| `frontend/src/components/dashboard/__tests__/Sparkline.test.tsx`   | Sparkline unit tests                        | VERIFIED | file exists, 5 tests                              |
| `frontend/src/components/dashboard/__tests__/EmptyState.test.tsx`  | EmptyState unit tests                       | VERIFIED | file exists, 4 tests                              |
| `frontend/src/components/dashboard/__tests__/DashboardClient.test.tsx` | DashboardClient fetch lifecycle tests   | VERIFIED | file exists, vi.mock(@/lib/api), 5 tests          |

---

### Key Link Verification

#### Plan 01 Key Links

| From                                | To                              | Via                           | Status  | Details                                              |
|-------------------------------------|---------------------------------|-------------------------------|---------|------------------------------------------------------|
| `frontend/src/proxy.ts`             | `frontend/src/lib/supabase/server.ts` | createServerClient import | WIRED   | proxy.ts line 1: `import { createServerClient } from '@supabase/ssr'`; uses same pattern as server.ts |
| `frontend/src/components/login/LoginForm.tsx` | `frontend/src/lib/supabase/client.ts` | signInWithPassword | WIRED   | LoginForm.tsx:24: `supabase.auth.signInWithPassword({email, password})`                      |
| `docker-compose.yml`                | `frontend/Dockerfile`           | build context ./frontend      | WIRED   | docker-compose.yml line 339: `context: ./frontend`                                            |

Note: Plan 01 specified link from `frontend/src/middleware.ts` — actual file is `frontend/src/proxy.ts`. The link is fully wired; only the filename changed due to Next.js 16 convention.

#### Plan 02 Key Links

| From                                | To                              | Via                              | Status | Details                                                                          |
|-------------------------------------|---------------------------------|----------------------------------|--------|----------------------------------------------------------------------------------|
| `DashboardClient.tsx`               | `frontend/src/lib/api.ts`       | getWatchlist + getOhlcv + getLastReport | WIRED  | DashboardClient.tsx:5: imports all four API functions; line 22 calls getWatchlist |
| `DashboardClient.tsx`               | `WatchlistGrid.tsx`             | renders WatchlistGrid when tickers loaded | WIRED  | DashboardClient.tsx:76: `return <WatchlistGrid tickers={tickers} />`           |
| `TickerCard.tsx`                    | `/reports/[symbol]`             | Next.js Link wrapping card       | WIRED  | TickerCard.tsx:15: `href={\`/reports/${ticker.symbol}\`}`                       |
| `frontend/src/app/(dashboard)/page.tsx` | `DashboardClient.tsx`       | passes accessToken from server session | WIRED  | page.tsx:14: `<DashboardClient accessToken={accessToken} />`                  |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                              | Status    | Evidence                                                                      |
|-------------|------------|--------------------------------------------------------------------------|-----------|-------------------------------------------------------------------------------|
| INFR-01     | 12-01      | Next.js frontend runs as Docker service with mem_limit on VPS            | SATISFIED | Dockerfile (3-stage standalone), docker-compose.yml mem_limit: 512m, next.config.ts output: standalone |
| DASH-01     | 12-02      | User sees watchlist as cards on dashboard landing page                   | SATISFIED | WatchlistGrid renders TickerCard per ticker; DashboardClient fetches and renders |
| DASH-02     | 12-02      | Each card shows entry quality tier badge (color-coded Favorable/Neutral/Cautious/Avoid) | SATISFIED | TierBadge.tsx with TIER_STYLES; teal/slate/amber/rose per tier             |
| DASH-03     | 12-02      | Each card shows sparkline price chart (52-week weekly close)             | SATISFIED | Sparkline.tsx pure SVG polyline; TickerCard passes closeData from ohlcv.close |
| DASH-04     | 12-02      | Each card shows last report date                                         | SATISFIED | TickerCard.tsx formats lastReport.generated_at with Intl.DateTimeFormat      |
| DASH-05     | 12-02      | Dashboard shows appropriate empty/loading/error states                   | SATISFIED | DashboardClient handles all 5 states: loading (skeleton), empty (EmptyState), error (ErrorState), stale (toast), data (WatchlistGrid) |

No orphaned requirements found — all 6 requirement IDs claimed across plans and all verified satisfied.

---

### Anti-Patterns Found

| File                                             | Line | Pattern                       | Severity | Impact                                                |
|--------------------------------------------------|------|-------------------------------|----------|-------------------------------------------------------|
| `frontend/src/app/reports/[symbol]/page.tsx`     | 17   | "Full report view coming soon." | Info    | Intentional placeholder — Phase 13 delivers this page. Not a blocker. |

No blocker or warning anti-patterns. The report page placeholder is explicitly scoped to Phase 13 per the ROADMAP.

---

### Human Verification Required

#### 1. Login Flow End-to-End

**Test:** Open browser, navigate to `http://localhost:3000`, provide valid Supabase credentials on login form.
**Expected:** Redirected to dashboard showing "Your Watchlist" heading; or EmptyState if watchlist is empty.
**Why human:** Requires live Supabase project credentials and running Docker services (reasoning-engine + frontend).

#### 2. Tier Badge Visual Appearance

**Test:** Navigate to dashboard with a watchlist containing tickers that have reports at each tier level (Favorable, Neutral, Cautious, Avoid).
**Expected:** Badges visually render as teal, slate/gray, amber, rose respectively.
**Why human:** CSS class rendering correctness requires visual inspection — can't verify Tailwind v4 JIT output programmatically.

#### 3. Sparkline Direction Color

**Test:** Dashboard with tickers where some are up and some are down over their OHLCV data.
**Expected:** Up tickers show green sparkline (#16a34a), down tickers show red sparkline (#dc2626).
**Why human:** SVG stroke color rendered in browser requires visual confirmation.

#### 4. Empty State Quick-Add Flow

**Test:** With an empty watchlist, click one of the 5 quick-add buttons (e.g., "VNM").
**Expected:** Button calls addTickerToWatchlist, then dashboard refreshes showing the new ticker card.
**Why human:** Requires live backend with auth token; involves network I/O and state transition.

---

### Commit Verification

All 5 commits documented in summaries were verified present in git history:

| Commit    | Description                                                              |
|-----------|--------------------------------------------------------------------------|
| `9b39d30` | feat(12-01): scaffold Next.js 15 with Tailwind v4, shadcn/ui, Supabase SSR, Docker, and test infra |
| `851d195` | feat(12-01): add auth middleware, login page, and dashboard layout with route protection |
| `0938db7` | fix(12-01): rename middleware.ts to proxy.ts per Next.js 16 breaking change |
| `1c091b1` | feat(12-02): TypeScript types, API layer, and dashboard presentational components |
| `983eb75` | feat(12-02): DashboardClient wiring and dashboard page integration       |

---

### Notable Deviation: middleware.ts -> proxy.ts

The plan specified `frontend/src/middleware.ts` but `create-next-app@latest` installed Next.js 16.2.0 (not 15), which deprecated the `middleware.ts` convention in favor of `proxy.ts`. The fix was committed in `0938db7`. All functionality is identical — only the filename and exported function name changed. This deviation is documented, intentional, and correct.

---

## Summary

Phase 12 goal is fully achieved. All 14 observable truths are verified against the actual codebase. Every artifact specified in both plan frontmatters exists, is substantive (not a stub), and is wired correctly. All 6 requirement IDs (INFR-01, DASH-01 through DASH-05) are satisfied with direct code evidence. No blocker anti-patterns found. Four items identified for human verification require a running deployment with live Supabase credentials — these are runtime concerns, not code defects.

---

_Verified: 2026-03-19_
_Verifier: Claude (gsd-verifier)_
