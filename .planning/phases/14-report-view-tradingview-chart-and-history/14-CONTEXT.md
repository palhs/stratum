# Phase 14: Report View, TradingView Chart, and History - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can read any report in full with a bilingual toggle, see price structure in context via an interactive TradingView chart, and browse the history of assessments for a ticker. This phase builds the `/reports/[symbol]` page (currently a placeholder). No report generation (Phase 13 — done), no nginx proxy (Phase 15).

</domain>

<decisions>
## Implementation Decisions

### Report page layout
- Vertical single-column layout: Summary card on top → TradingView chart below → expanded full report below chart → history timeline at bottom
- Summary card is collapsed by default — user must click "Expand" to read the full report (matches success criterion #1)
- When expanded, full report appears below the chart — summary + chart stay above as context
- "Back to Dashboard" link at the top of the page

### Summary card content
- Show all available data: large tier badge (hero element), three sub-assessment labels (Macro, Valuation, Structure), and one-line narrative verdict
- Reuse TierBadge component from dashboard with the same muted color scheme (teal/slate/amber/rose)
- Expand/collapse button at the bottom of the summary card

### Bilingual toggle
- Floating toggle in the top-right of the report page, always visible even when scrolled
- Switches both the summary card verdict text and the full report markdown content
- Default language: Vietnamese (aligns with PROJECT.md "Vietnamese primary, English secondary")
- Language preference persisted in localStorage — survives page refreshes
- Both vi and en report content fetched upfront on page load — toggle is instant, no loading spinner

### TradingView chart
- Weekly candlestick chart with MA50 and MA200 line overlays visible by default
- Volume histogram below the candlestick area
- Default view: 1 year (52 weeks) of data, user can zoom/pan to see more
- Chart is zoomable and interactive (TradingView Lightweight Charts)
- Loaded via `dynamic({ ssr: false })` — decided in Phase 12

### Chart sizing
- Claude's Discretion — appropriate responsive sizing for desktop and mobile

### History timeline
- Vertical list below the chart section
- Each row shows: date, tier badge, verdict snippet, upgrade/downgrade arrow
- Arrows between consecutive reports: ↑ (green) for upgrade, ↓ (red) for downgrade, no arrow if tier unchanged
- Arrow colors use the muted color scheme from Phase 12
- Clicking a historical report replaces the current summary card and report content in-place (URL stays /reports/{symbol})
- Active/selected report is highlighted in the timeline list
- Load 10 most recent reports initially, "Load more" button if more exist

### Claude's Discretion
- Chart height and mobile sizing
- Full report markdown rendering approach (react-markdown, etc.)
- Loading/skeleton states for the report page
- Error handling for missing reports or API failures
- Animation/transition for expand/collapse
- How to fetch both vi and en report content (may need new backend endpoint — current GET /reports/{job_id} returns one language per row; researcher should investigate)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend API (report data)
- `reasoning/app/routers/reports.py` — GET /reports/{job_id} (report_json + report_markdown), GET /reports/by-ticker/{symbol} (paginated history with tier + verdict), report_jobs/reports table JOIN pattern
- `reasoning/app/schemas.py` — ReportHistoryItem (report_id, generated_at, tier, verdict), ReportHistoryResponse (paginated)
- `reasoning/app/pipeline/storage.py` — write_report() stores per-language rows (vi/en) with report_json JSONB + report_markdown text
- `reasoning/app/nodes/state.py` — ReportOutput model, entry_quality tier/narrative fields in report_json

### Frontend existing code
- `frontend/src/app/reports/[symbol]/page.tsx` — Placeholder page to be replaced
- `frontend/src/components/dashboard/TierBadge.tsx` — Reusable tier badge component with muted color scheme
- `frontend/src/lib/api.ts` — fetchAPI helper, getOhlcv() already fetches OHLCV with ma50/ma200, getLastReport() fetches history
- `frontend/src/lib/types.ts` — OHLCVPoint (time, open, high, low, close, volume, ma50, ma200), ReportHistoryItem, ReportHistoryResponse

### Prior phase context
- `.planning/phases/12-next-js-core-shell-and-dashboard/12-CONTEXT.md` — Card layout, muted color scheme, TierBadge, `dynamic({ ssr: false })` for TradingView
- `.planning/phases/13-report-generation-with-sse-progress/13-CONTEXT.md` — SSE infrastructure, DashboardClient patterns, sonner toast

### Requirements
- `.planning/REQUIREMENTS.md` §Report View — RVEW-01, RVEW-02, RVEW-03, RVEW-04
- `.planning/REQUIREMENTS.md` §Report History — RHST-01, RHST-02, RHST-03, RHST-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TierBadge` component: Muted color-coded badge (teal/slate/amber/rose) — reuse directly in summary card and history timeline
- `getOhlcv()` in api.ts: Already fetches OHLCV data with ma50/ma200 for TradingView chart
- `getLastReport()` in api.ts: Fetches paginated report history — extend for full history loading
- `fetchAPI()` helper: Auth-aware fetch with Bearer token — extend for new report content endpoints
- `OHLCVPoint` type: Already matches TradingView Lightweight Charts data format (time, open, high, low, close, volume)
- `sonner` toast: Already installed for notifications

### Established Patterns
- "use client" components with useState/useCallback for interactive features
- `dynamic({ ssr: false })` for browser-only libraries (TradingView)
- Supabase auth token passed via Authorization header on all API calls
- next.config.ts rewrites for API proxying

### Integration Points
- `/reports/[symbol]/page.tsx` — Replace placeholder with full report view
- Backend may need a new endpoint to fetch full report content (report_json + report_markdown) by report_id or by symbol+language — current GET /reports/{job_id} is job-based, not report-based
- History timeline needs to load report content for any clicked historical report

</code_context>

<specifics>
## Specific Ideas

- Summary card with all three sub-assessments (Macro, Valuation, Structure) gives users the analytical breakdown at a glance — aligns with the product's "three-pillar" reasoning architecture
- Chart below summary mirrors a research report flow: read the conclusion first, then examine the evidence (price chart)
- History timeline with upgrade/downgrade arrows creates a visual narrative of assessment changes over time — key for the "when is a reasonable time to enter" value proposition
- Floating language toggle ensures bilingual access is always one click away, even deep in a long report

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-report-view-tradingview-chart-and-history*
*Context gathered: 2026-03-19*
