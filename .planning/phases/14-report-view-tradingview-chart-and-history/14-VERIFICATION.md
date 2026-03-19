---
phase: 14-report-view-tradingview-chart-and-history
verified: 2026-03-19T07:30:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 14: Report View with TradingView Chart and History — Verification Report

**Phase Goal:** Report View with TradingView Chart and History
**Verified:** 2026-03-19T07:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /reports/by-report-id/{report_id} returns both vi and en report content for a given report_id | VERIFIED | `@router.get("/by-report-id/{report_id}", response_model=ReportContentResponse)` at line 432 of reports.py; `_get_report_content_by_id` helper at line 217 fetches anchor row then sibling rows by asset_id+generated_at |
| 2 | Frontend types include ReportContentResponse with all required fields | VERIFIED | types.ts lines 76-85: `report_id`, `generated_at`, `tier`, `verdict`, `macro_assessment`, `valuation_assessment`, `structure_assessment`, `report_markdown_vi`, `report_markdown_en` |
| 3 | Frontend API has getReportContent() and getReportHistory() functions | VERIFIED | api.ts lines 56-72: both exported async functions present, import ReportContentResponse from ./types |
| 4 | lightweight-charts, react-markdown, remark-gfm, @tailwindcss/typography are installed | VERIFIED | package.json: `lightweight-charts@^5.1.0`, `react-markdown@^10.1.0`, `remark-gfm@^4.0.1`, `@tailwindcss/typography@^0.5.19` |
| 5 | @tailwindcss/typography prose class available via @plugin directive in globals.css | VERIFIED | globals.css line 2: `@plugin "@tailwindcss/typography";` |
| 6 | ReportSummaryCard renders tier badge, three sub-assessments, and expand/collapse button | VERIFIED | ReportSummaryCard.tsx: `TierBadge` import used, Macro/Valuation/Structure labels rendered, "Read full report" / "Collapse report" copy present |
| 7 | BilingualToggle floats fixed top-right with VI/EN buttons and accessibility attributes | VERIFIED | BilingualToggle.tsx: `className="fixed top-4 right-4 z-50"`, `aria-label="Report language"`, `aria-pressed={lang === 'vi'}` and `aria-pressed={lang === 'en'}` |
| 8 | TradingViewChart renders candlestick + MA50 + MA200 without SSR crash | VERIFIED | TradingViewChart.tsx: `createChart` called, `addSeries(CandlestickSeries)`, `addSeries(LineSeries)` x2 (MA50/MA200), `addSeries(HistogramSeries)` for volume; `chart.remove()` cleanup; `aria-label="Price chart"` |
| 9 | ReportMarkdown renders markdown with prose typography and lang attribute | VERIFIED | ReportMarkdown.tsx: `import ReactMarkdown from 'react-markdown'`, `import remarkGfm from 'remark-gfm'`, `<article lang={lang} className="prose prose-zinc dark:prose-invert max-w-none">` |
| 10 | History timeline shows past reports with tier change arrows, active row highlighting, and load-more | VERIFIED | HistoryTimeline.tsx: `TIER_RANK` map, `getTierChange` function, `ArrowUp`/`ArrowDown` from lucide-react, `aria-label` with "Upgraded from"/"Downgraded from", `border-l-2 border-primary bg-muted/50` active state, "Load more reports" button |
| 11 | ReportPageClient wires all components; page.tsx provides auth guard; URL unchanged on history row click | VERIFIED | ReportPageClient.tsx: imports all 5 leaf components + 3 API functions; `dynamic(() => import('./TradingViewChart'), { ssr: false })` pattern; `localStorage.getItem/setItem('stratum-report-lang')`; `handleSelectReport` sets state without router.push. page.tsx: `if (!session) redirect('/login')`, `symbol.toUpperCase()`, `export const dynamic = 'force-dynamic'` |

**Score:** 11/11 truths verified

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `reasoning/app/routers/reports.py` | GET /reports/by-report-id/{report_id} endpoint | VERIFIED | Endpoint at line 432, registered after `/by-ticker/{symbol}` and before `/stream/{job_id}` — route order correct |
| `reasoning/app/schemas.py` | ReportContentResponse Pydantic model | VERIFIED | `class ReportContentResponse(BaseModel):` at line 59; all 9 fields present including nullable vi/en markdown |
| `reasoning/tests/api/test_reports_by_id.py` | Tests for new endpoint | VERIFIED | 4 tests: 200 full shape, nullable markdown, 404 not found, 401 without auth |
| `frontend/src/lib/types.ts` | ReportContentResponse TypeScript type | VERIFIED | Interface exported at line 76 with all required fields |
| `frontend/src/lib/api.ts` | getReportContent, getReportHistory functions | VERIFIED | Both exported; `getReportHistory` at line 56, `getReportContent` at line 68; `ReportContentResponse` imported from ./types |
| `frontend/src/app/globals.css` | @plugin @tailwindcss/typography | VERIFIED | Line 2: `@plugin "@tailwindcss/typography";` |

### Plan 02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/components/report/ReportSummaryCard.tsx` | Summary card with tier hero, sub-assessments, verdict, expand button | VERIFIED | TierBadge imported from `@/components/dashboard/TierBadge`; Macro/Valuation/Structure labels rendered; aria-expanded present |
| `frontend/src/components/report/BilingualToggle.tsx` | Floating language toggle | VERIFIED | Fixed position, aria-label, aria-pressed; VI/EN buttons present |
| `frontend/src/components/report/TradingViewChart.tsx` | Lightweight Charts candlestick wrapper | VERIFIED | `createChart` imported and called; v5 `addSeries(CandlestickSeries/LineSeries/HistogramSeries)` API used (correct deviation from plan's v4 API spec); cleanup via `chart.remove()` |
| `frontend/src/components/report/ReportMarkdown.tsx` | Markdown renderer with prose styling | VERIFIED | ReactMarkdown + remarkGfm; `prose prose-zinc dark:prose-invert max-w-none` classes |
| `frontend/src/components/report/ReportPageSkeleton.tsx` | Loading skeleton | VERIFIED | `export function ReportPageSkeleton()` with Skeleton placeholders |

### Plan 03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/components/report/HistoryTimeline.tsx` | History timeline with tier arrows and row click | VERIFIED | TIER_RANK map, getTierChange, ArrowUp/ArrowDown with aria-labels, border-l-2 active state, min-h-[44px] touch target, empty/loading states |
| `frontend/src/components/report/ReportPageClient.tsx` | Client orchestrator wiring all report components | VERIFIED | All 5 leaf components imported; all 3 API functions imported; dynamic TradingViewChart (ssr:false); localStorage lang persistence; in-place report switching |
| `frontend/src/app/reports/[symbol]/page.tsx` | Server page with auth + ReportPageClient | VERIFIED | `export const dynamic = 'force-dynamic'`; auth guard with redirect('/login'); `symbol.toUpperCase()` passed to ReportPageClient |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `reasoning/app/routers/reports.py` | `reasoning/app/schemas.py` | ReportContentResponse import | WIRED | Line 35: `from reasoning.app.schemas import ReportHistoryItem, ReportHistoryResponse, ReportContentResponse` |
| `frontend/src/lib/api.ts` | `frontend/src/lib/types.ts` | ReportContentResponse type import | WIRED | Line 1: `import type { ..., ReportContentResponse } from './types'` |
| `frontend/src/components/report/ReportSummaryCard.tsx` | `frontend/src/components/dashboard/TierBadge.tsx` | TierBadge import | WIRED | `import { TierBadge } from '@/components/dashboard/TierBadge'` |
| `frontend/src/components/report/TradingViewChart.tsx` | `lightweight-charts` | createChart import | WIRED | `import { createChart, ColorType, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts'` |
| `frontend/src/components/report/ReportMarkdown.tsx` | `react-markdown` | ReactMarkdown import | WIRED | `import ReactMarkdown from 'react-markdown'` + `import remarkGfm from 'remark-gfm'` |
| `frontend/src/components/report/ReportPageClient.tsx` | `frontend/src/lib/api.ts` | getReportContent, getReportHistory, getOhlcv imports | WIRED | `import { getOhlcv, getReportHistory, getReportContent } from '@/lib/api'`; all three called in component body |
| `frontend/src/components/report/ReportPageClient.tsx` | `frontend/src/components/report/ReportSummaryCard.tsx` | ReportSummaryCard import | WIRED | Imported and rendered with all required props |
| `frontend/src/components/report/ReportPageClient.tsx` | `frontend/src/components/report/HistoryTimeline.tsx` | HistoryTimeline import | WIRED | Imported and rendered with all required props |
| `frontend/src/components/report/ReportPageClient.tsx` | `frontend/src/components/report/TradingViewChart.tsx` | dynamic import (ssr: false) | WIRED | `dynamic(() => import('./TradingViewChart'), { ssr: false, loading: ... })` |
| `frontend/src/app/reports/[symbol]/page.tsx` | `frontend/src/components/report/ReportPageClient.tsx` | ReportPageClient import | WIRED | `import { ReportPageClient } from '@/components/report/ReportPageClient'`; rendered with symbol and accessToken |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RVEW-01 | 14-01, 14-02 | User sees report summary card (tier, sub-assessments, one-line verdict) | SATISFIED | ReportSummaryCard renders TierBadge, Macro/Valuation/Structure labels, and verdict text |
| RVEW-02 | 14-03 | User can expand summary to full bilingual markdown report | SATISFIED | ReportPageClient toggles `isExpanded`; `{isExpanded && currentMarkdown && <ReportMarkdown ... />}` with fade-in animation |
| RVEW-03 | 14-02 | User can toggle between Vietnamese and English report versions | SATISFIED | BilingualToggle calls onLanguageChange; ReportPageClient switches `currentMarkdown` based on `lang` state; localStorage persistence |
| RVEW-04 | 14-01, 14-02 | Report view includes interactive TradingView chart (weekly OHLCV + 50MA + 200MA, zoomable) | SATISFIED | TradingViewChart renders candlestick + MA50 (LineSeries blue) + MA200 (LineSeries orange) + volume histogram; 52-bar visible range set |
| RHST-01 | 14-03 | User can view timeline of past reports per ticker | SATISFIED | HistoryTimeline renders history items list; ReportPageClient fetches via getReportHistory |
| RHST-02 | 14-03 | Timeline shows date and entry quality tier badge per report | SATISFIED | HistoryTimeline renders `format(parseISO(item.generated_at), 'dd MMM yyyy')` and `<TierBadge tier={item.tier} />` per row |
| RHST-03 | 14-01, 14-03 | User can open any historical report from the timeline | SATISFIED | Backend GET /reports/by-report-id/{report_id} delivers content; handleSelectReport calls getReportContent in-place; URL unchanged |
| RHST-04 | 14-03 | Timeline shows assessment change indicators (upgrade/downgrade arrows) | SATISFIED | getTierChange computes rank delta; ArrowUp (teal) for upgrade, ArrowDown (rose) for downgrade, with screen-reader aria-labels |

All 8 requirement IDs declared across the three plans are satisfied. No orphaned requirements detected — REQUIREMENTS.md maps all 8 IDs to Phase 14 with status "Complete".

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/report/ReportPageClient.tsx` | 69 | `return null` | Info | Legitimate: error-path return inside `getOhlcv(...).catch()` callback — not a stub |

No blockers or warnings found. The single `return null` on line 69 is inside a `.catch()` callback that also calls `setOhlcvError(true)`, which is correct error-handling behaviour, not a placeholder.

---

## Commit Verification

All 6 task commits documented in the SUMMARYs are confirmed present in the git history:

| Commit | Description |
|--------|-------------|
| `20aca8e` | feat(14-01): add GET /reports/by-report-id/{report_id} backend endpoint |
| `3bc8bb4` | feat(14-01): install npm packages, configure typography, extend frontend types and API |
| `3d81770` | feat(14-02): ReportSummaryCard and BilingualToggle components with tests |
| `59ebbb2` | feat(14-02): TradingViewChart, ReportMarkdown, and ReportPageSkeleton components with tests |
| `138f5be` | feat(14-03): add HistoryTimeline component with upgrade/downgrade arrows and tests |
| `e905f6f` | feat(14-03): add ReportPageClient orchestrator, server page.tsx, and tests |

---

## Notable Deviations (Correctly Handled)

**lightweight-charts v4 → v5 API migration:** Plan 02 specified `addCandlestickSeries()`, `addLineSeries()`, `addHistogramSeries()` (v4 convenience methods). The executor correctly identified these do not exist in v5 and switched to `chart.addSeries(CandlestickSeries, opts)` etc. The installed package is `lightweight-charts@^5.1.0`, so the v5 API is the correct implementation. This is a legitimate auto-fix, not a spec violation.

---

## Human Verification Required

The following behaviors require running the development server:

### 1. Chart Interactive Rendering

**Test:** Navigate to `/reports/VCB` (or any ticker with reports). View the TradingView chart.
**Expected:** Weekly candlestick bars with blue MA50 line, orange MA200 line, and volume histogram in secondary scale. Chart responds to zoom/pan. No SSR crash on initial load.
**Why human:** DOM rendering of canvas-based chart and dynamic import cannot be verified by grep.

### 2. Language Toggle Persistence

**Test:** Toggle to EN. Reload the page.
**Expected:** Page reopens in EN — localStorage key `stratum-report-lang` was persisted and read on init.
**Why human:** localStorage initializer `(() => { if (typeof window === 'undefined') return 'vi'; return localStorage.getItem('stratum-report-lang') ?? 'vi' })()` executes in browser, not statically verifiable.

### 3. In-Place History Row Click (URL Unchanged)

**Test:** Click a history row in the timeline.
**Expected:** Summary card content updates, chart remains, expand collapses — URL stays `/reports/{symbol}`.
**Why human:** State-driven content swap without router navigation cannot be verified statically.

### 4. Upgrade/Downgrade Arrow Visual Appearance

**Test:** View a ticker with multiple historical reports where tier changed between runs.
**Expected:** Teal ArrowUp on improved tier rows, rose ArrowDown on worsened tier rows. No arrow when tier unchanged.
**Why human:** Visual correctness and colour rendering requires browser inspection.

---

## Gaps Summary

No gaps. All truths verified, all artifacts substantive and wired, all key links confirmed, all 8 requirements satisfied. Phase goal is achieved.

---

_Verified: 2026-03-19T07:30:00Z_
_Verifier: Claude (gsd-verifier)_
