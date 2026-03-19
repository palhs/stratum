---
phase: 14-report-view-tradingview-chart-and-history
plan: 01
subsystem: api
tags: [fastapi, pydantic, sqlalchemy, typescript, tailwindcss, react-markdown, lightweight-charts]

# Dependency graph
requires:
  - phase: 10-backend-api-contracts-and-jwt-middleware
    provides: reports router pattern, require_auth dependency, SQLAlchemy autoload pattern
  - phase: 13-report-generation-with-sse-progress
    provides: reports table schema with language+report_markdown columns, report_json JSONB with entry_quality

provides:
  - GET /reports/by-report-id/{report_id} backend endpoint returning both vi and en markdown
  - ReportContentResponse Pydantic schema with all assessment fields
  - Frontend ReportContentResponse TypeScript type
  - Frontend getReportContent() and getReportHistory() API functions
  - lightweight-charts, react-markdown, remark-gfm, @tailwindcss/typography installed
  - @tailwindcss/typography prose class configured via @plugin in globals.css

affects:
  - 14-02 (TradingView chart component needs lightweight-charts)
  - 14-03 (Report view panel needs getReportContent API and ReportContentResponse type)

# Tech tracking
tech-stack:
  added:
    - lightweight-charts@5.1.0 (TradingView candlestick/OHLCV charts)
    - react-markdown@10.1.0 (render markdown report content)
    - remark-gfm@4.0.1 (GitHub Flavored Markdown tables in reports)
    - "@tailwindcss/typography@0.5.19 (prose classes for markdown rendering)"
  patterns:
    - _get_report_content_by_id fetches anchor row then sibling rows by asset_id+generated_at (same generation run)
    - String path routes (/by-report-id/{report_id}) registered before parameterized /{job_id} to avoid 422

key-files:
  created:
    - reasoning/tests/api/test_reports_by_id.py
  modified:
    - reasoning/app/schemas.py (added ReportContentResponse Pydantic model)
    - reasoning/app/routers/reports.py (added _get_report_content_by_id helper + endpoint)
    - frontend/src/lib/types.ts (added ReportContentResponse interface)
    - frontend/src/lib/api.ts (added getReportContent, getReportHistory functions)
    - frontend/src/app/globals.css (added @plugin "@tailwindcss/typography")
    - frontend/package.json (added 4 npm dependencies)

key-decisions:
  - "Anchor row fetched first by report_id, then sibling rows fetched by asset_id+generated_at — avoids JOIN complexity and keeps language split explicit"
  - "@plugin directive in globals.css (Tailwind v4 CSS-first config) — not tailwind.config.js which is Tailwind v3 pattern"

patterns-established:
  - "Pattern: _get_report_content_by_id — two-query approach: anchor lookup by PK, then sibling fetch by asset_id+generated_at"

requirements-completed: [RVEW-01, RVEW-04, RHST-03]

# Metrics
duration: 8min
completed: 2026-03-19
---

# Phase 14 Plan 01: Foundation — Backend Endpoint, npm Packages, Frontend Types Summary

**GET /reports/by-report-id/{report_id} FastAPI endpoint returning both vi+en markdown, plus lightweight-charts/react-markdown/remark-gfm/@tailwindcss/typography installed with TypeScript types and API functions wired**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-19T06:30:00Z
- **Completed:** 2026-03-19T06:38:37Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- New backend endpoint GET /reports/by-report-id/{report_id} returns full report content (tier, verdict, 3 assessments, vi and en markdown) — registered before /stream/{job_id} and /{job_id} to prevent route shadowing
- ReportContentResponse added to schemas.py and frontend types.ts; getReportContent() + getReportHistory() added to api.ts
- lightweight-charts@5.1.0, react-markdown@10.1.0, remark-gfm@4.0.1, @tailwindcss/typography@0.5.19 installed; typography @plugin configured in globals.css

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend GET /reports/by-report-id/{report_id} endpoint with tests** - `20aca8e` (feat)
2. **Task 2: Install npm packages, configure typography plugin, extend frontend types and API** - `3bc8bb4` (feat)

## Files Created/Modified

- `reasoning/app/schemas.py` - Added ReportContentResponse Pydantic model (7 fields + nullable vi/en markdown)
- `reasoning/app/routers/reports.py` - Added _get_report_content_by_id helper + get_report_content endpoint; updated docstring and import
- `reasoning/tests/api/test_reports_by_id.py` - 4 tests: 200 full shape, nullable markdown, 404, 401 without auth
- `frontend/src/lib/types.ts` - Added ReportContentResponse TypeScript interface
- `frontend/src/lib/api.ts` - Added getReportHistory() and getReportContent() exported functions; updated import
- `frontend/src/app/globals.css` - Added @plugin "@tailwindcss/typography" after @import "tailwindcss"
- `frontend/package.json` - Added 4 npm packages in dependencies

## Decisions Made

- Anchor row fetched first by report_id (PK lookup), then sibling rows fetched by asset_id+generated_at — avoids a JOIN and keeps the language-split logic explicit and readable
- @plugin directive is the Tailwind v4 CSS-first config approach — tailwind.config.js plugin array is v3 pattern and would be ignored

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `tsc --noEmit` surfaced a pre-existing error in `src/components/dashboard/__tests__/Sparkline.test.tsx` (Module '"@testing-library/react"' has no exported member 'container') — confirmed pre-existed before this plan's changes, logged as out-of-scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend endpoint ready for use by 14-02 and 14-03 components
- lightweight-charts available for TradingView chart component
- react-markdown + remark-gfm available for markdown report rendering
- @tailwindcss/typography prose classes available for styled markdown display

---
*Phase: 14-report-view-tradingview-chart-and-history*
*Completed: 2026-03-19*
