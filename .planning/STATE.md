---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Product Frontend & User Experience
status: in_progress
last_updated: "2026-03-18"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 1
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-17)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** v3.0 Phase 10 — Backend API Contracts and JWT Middleware

## Current Position

Milestone: v3.0 — Product Frontend & User Experience
Phase: 10 of 16 (Backend API Contracts and JWT Middleware)
Plan: 1 of 1 (10-01 complete)
Status: In progress
Last activity: 2026-03-18 — 10-01 complete (JWT auth dependency, OHLCV endpoint, Pydantic schemas)

Progress: [░░░░░░░░░░] 3%

## Performance Metrics

**Velocity:**
- Total plans completed: 1 (v3.0)
- Average duration: 5 min
- Total execution time: 5 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 10-backend-api-contracts-and-jwt-middleware | 1 | 5 min | 5 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key decisions active for v3.0:
- Two-database split: Supabase Cloud for auth/watchlists, VPS PostgreSQL for all analytical data — no cross-DB JOINs
- JWT validation on reasoning-engine via auth.py with `audience="authenticated"` — Phase 10 sets this before any frontend code calls the API
- Watchlists table lives in VPS PostgreSQL (not Supabase DB) — user_id UUID column, RLS enforced in app code
- TradingView chart loaded via `dynamic({ ssr: false })` — "use client" alone is insufficient
- SSE proxied via next.config.ts rewrites (not API routes) — nginx buffering disabled on /api/stream/* routes
- Supabase service role key must NEVER carry NEXT_PUBLIC_ prefix

Decisions from 10-01 execution:
- HTTPBearer(auto_error=False) pattern — returns 401 on missing header, not FastAPI default 403
- GOLD_TICKERS set (GLD/IAU/SGOL) routes to gold_etf_ohlcv (ticker column) vs stock_ohlcv (symbol column)
- MA50/MA200 via SQL window functions rows=(-49,0) and rows=(-199,0) — no Python-side calculation
- Table autoload_with=db_engine chosen over pre-defined ORM models to avoid metadata coupling

### Pending Todos

None yet.

### Blockers/Concerns

- WGC gold data still 501 — carried from v2.0 (does not block v3.0)
- Supabase invite flow with signups disabled has a known edge case: Site URL must point to password-set page, not login page — verify in Phase 11 before building onboarding
- SBV automated ingestion confidence is LOW (sbv.gov.vn has no stable scraping target) — Phase 16 baseline is manual PDF upload, not automation

## Session Continuity

Last session: 2026-03-18
Stopped at: Completed 10-01-PLAN.md — JWT auth dependency, OHLCV endpoint, Pydantic schemas
Resume file: None
