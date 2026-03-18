# Phase 13: Report Generation with SSE Progress - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the "Generate Report" button on dashboard ticker cards to the existing FastAPI POST /reports/generate endpoint. Show real-time pipeline progress via SSE with per-node granularity (7 named LangGraph steps). Disable the button during active generation. No report view (Phase 14), no nginx SSE proxy (Phase 15).

</domain>

<decisions>
## Implementation Decisions

### Generate button placement
- Button lives inside each ticker card, at the bottom below the sparkline and last report date
- Small, secondary-style button labeled "Generate Report"
- Button is per-ticker: only the generating card's button is replaced by progress — other cards remain interactive

### Card in-progress state
- Generate button area is replaced by a vertical step list showing all 7 pipeline steps
- Card expands in place to fit the step list, pushing grid cards below it down
- Sparkline and last report date section hidden during generation, replaced by step list
- Tier badge remains visible at the top of the card during generation
- Card click (navigate to /reports/{symbol}) remains functional during generation

### Step list display
- All 7 steps shown vertically with status icons:
  - `checkmark` = completed (green)
  - `filled circle` = in progress (animated/pulsing)
  - `empty circle` = pending (gray)
  - `x mark` = failed (red)
- Friendly English labels mapped from node names:
  - macro_regime -> "Macro Analysis"
  - valuation -> "Valuation"
  - structure -> "Price Structure"
  - conflict -> "Conflict Check"
  - entry_quality -> "Entry Quality"
  - grounding_check -> "Grounding"
  - compose_report -> "Compose Report"
- No timing information (no elapsed time, no estimates)
- Single combined pass — bilingual vi+en generation treated as one unified progress

### Per-node SSE events (backend change required)
- Use LangGraph's built-in callback system to emit SSE events on node start and node complete
- Both `node_start` and `node_complete` events emitted per node (not just start-only)
- Events flow: LangGraph callback -> asyncio.Queue -> SSE stream -> EventSource on frontend
- Existing coarse events (job_started, pipeline_vi_start, etc.) can remain for backwards compatibility

### Concurrency model
- Per-ticker disabled state only — user can trigger generation on multiple tickers simultaneously
- Backend already returns 409 if same ticker has an active job (no frontend-only guard needed)
- No global generation limit in this phase

### Completion flow
- On success: step list collapses back to normal card layout
- Card refreshes to show updated last report date and potentially updated tier badge
- Toast notification: "{SYMBOL} report ready"
- Generate button re-appears

### Error flow
- On failure: the failed step shows red x icon, steps after it remain empty circles
- Card stays expanded briefly (3-5 seconds) so user can see which step failed
- Toast notification: "Report generation failed"
- Card then collapses back to normal, Generate button re-appears for retry

### Navigation away handling
- EventSource.close() called on component unmount / route navigation (satisfies success criterion #4)
- Backend pipeline continues running (BackgroundTask is independent of SSE connection)
- On return to dashboard: check for active jobs for user's tickers, re-connect SSE if still running, or show completed/failed state

### Claude's Discretion
- EventSource connection management implementation (reconnect logic, error handling)
- LangGraph callback implementation details (which callback hooks to use)
- Step list animation/transition details
- Card expand/collapse animation approach
- How to detect active jobs on dashboard load (poll vs check on mount)
- next.config.ts rewrite rules for SSE proxy path

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend SSE & report generation
- `reasoning/app/routers/reports.py` — POST /generate (202 + job_id), GET /stream/{job_id} (SSE with asyncio.Queue), _run_pipeline background task, _emit helper
- `reasoning/app/pipeline/graph.py` — 7-node LangGraph StateGraph: macro_regime, valuation, structure, conflict, entry_quality, grounding_check, compose_report
- `reasoning/app/pipeline/__init__.py` — generate_report entry point (two-stage vi+en pipeline)

### Frontend existing code
- `frontend/src/components/dashboard/DashboardClient.tsx` — Dashboard state management, WatchlistGrid rendering, toast pattern (sonner)
- `frontend/src/lib/api.ts` — fetchAPI helper, NEXT_PUBLIC_API_URL base, existing endpoint functions
- `frontend/src/lib/types.ts` — TickerData, WatchlistItem, ReportHistoryItem types
- `frontend/next.config.ts` — Needs SSE rewrite rules added

### Prior phase context
- `.planning/phases/12-next-js-core-shell-and-dashboard/12-CONTEXT.md` — Card layout decisions (responsive grid, tier badge hero, sparkline, muted color scheme)
- `.planning/phases/11-supabase-auth-and-per-user-watchlist/11-CONTEXT.md` — JWT auth, watchlist API contracts

### Requirements
- `.planning/REQUIREMENTS.md` section "Report Generation" — RGEN-01, RGEN-02, RGEN-03

### LangGraph callbacks
- LangGraph documentation on callbacks/event streaming — researcher should investigate `astream_events` or callback handlers for node-level events

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/routers/reports.py`: Full SSE infrastructure already built — asyncio.Queue per job, EventSourceResponse, ping keepalive, cleanup in finally block
- `frontend/src/lib/api.ts`: fetchAPI helper with auth header injection — extend for POST /generate
- `frontend/src/components/dashboard/DashboardClient.tsx`: Dashboard state management with useCallback pattern — extend for generation state
- `sonner` toast library already installed and used in DashboardClient

### Established Patterns
- Backend: sse_starlette.EventSourceResponse for SSE, asyncio.Queue for event dispatch, BackgroundTasks for pipeline execution
- Frontend: "use client" components with useState/useCallback, Promise.all for parallel data fetching, toast.error() for notifications
- Auth: Bearer token passed in Authorization header on all API calls

### Integration Points
- WatchlistGrid component needs to pass generation state and handlers down to individual card components
- next.config.ts needs rewrite rule for /api/reports/stream/* to proxy SSE to reasoning-engine
- POST /reports/generate needs to be called from frontend with ticker and asset_type from WatchlistItem
- EventSource connection on frontend needs access token (query param or custom header via fetch-based SSE)

</code_context>

<specifics>
## Specific Ideas

- Vertical step list during generation mirrors a "pipeline execution log" aesthetic — gives the user confidence that analysis is thorough (7 distinct analytical steps)
- Card-expands-in-place approach keeps the user on the dashboard where they can monitor multiple tickers, rather than navigating to a separate generation status page
- Friendly English labels (not Vietnamese) chosen because the pipeline concepts are financial/technical terms that don't benefit from translation in the UI chrome

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-report-generation-with-sse-progress*
*Context gathered: 2026-03-19*
