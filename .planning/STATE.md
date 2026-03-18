---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Product Frontend & User Experience
status: executing
stopped_at: Completed 12-02-PLAN.md
last_updated: "2026-03-18T17:39:39.886Z"
last_activity: 2026-03-18 — 11-02 Task 1 complete (watchlist GET/PUT API, 42 tests passing)
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
  percent: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-17)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** v3.0 Phase 11 — Supabase Auth and Per-User Watchlist

## Current Position

Milestone: v3.0 — Product Frontend & User Experience
Phase: 11 of 16 (Supabase Auth and Per-User Watchlist)
Plan: 2 of 3 (11-01 complete, 11-02 Task 1 complete — checkpoint on Task 2)
Status: In progress — awaiting Supabase dashboard config (checkpoint:human-action)
Last activity: 2026-03-18 — 11-02 Task 1 complete (watchlist GET/PUT API, 42 tests passing)

Progress: [░░░░░░░░░░] 5%

## Performance Metrics

**Velocity:**
- Total plans completed: 3 (v3.0)
- Average duration: 4.7 min
- Total execution time: 14 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 10-backend-api-contracts-and-jwt-middleware | 2 | 7 min | 3.5 min |
| 11-supabase-auth-and-per-user-watchlist | 1 | 7 min | 7 min |
| 11-supabase-auth-and-per-user-watchlist (02) | 1 | 5 min | 5 min |

*Updated after each plan completion*
| Phase 12-next-js-core-shell-and-dashboard P01 | 11 | 2 tasks | 35 files |
| Phase 12-next-js-core-shell-and-dashboard P02 | 4 | 2 tasks | 17 files |

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

Decisions from 10-02 execution:
- dependency_overrides[require_auth] in test_reports.py — cleanest way to bypass auth in endpoint logic tests
- Route order: generate -> by-ticker -> stream -> {job_id} — string paths before parameterized /{job_id} prevents 422
- text() for JSONB extraction — avoids SQLAlchemy type casting issues with JSONB operators in select()
- GROUP BY generated_at collapses vi+en rows — one history entry per generation run

Decisions from 11-01 execution:
- signing_key.key (not signing_key directly) passed to jwt.decode — PyJWT's isinstance(key, PyJWK) check fails on MagicMock; unwrapping .key works in production and tests
- PyJWKClient module-level singleton initialized from SUPABASE_JWKS_URL — at module level for 300s JWKS cache to be shared across requests
- [Phase 11-supabase-auth-and-per-user-watchlist]: Static TICKER_METADATA dict used for symbol validation — ticker universe is static for VN30+gold; faster and avoids coupling to DB state
- [Phase 11-supabase-auth-and-per-user-watchlist]: Zero-rows triggers seeding on GET /watchlist — explicitly clearing re-seeds on next GET, acceptable for v3.0
- [Phase 12-next-js-core-shell-and-dashboard]: proxy.ts (not middleware.ts) is the Next.js 16 file convention — middleware.ts deprecated, export must be named 'proxy'
- [Phase 12-next-js-core-shell-and-dashboard]: Supabase getUser() used in proxy.ts (not getSession()) — validates JWT with JWKS, not just cookie presence
- [Phase 12-next-js-core-shell-and-dashboard]: force-dynamic on (dashboard)/page.tsx prevents ISR cache pressure from authenticated content
- [Phase 12-next-js-core-shell-and-dashboard]: NEXT_PUBLIC_API_URL targets host-mapped reasoning-engine port 8001 for client-side fetches — no nginx proxy in Phase 12
- [Phase 12-next-js-core-shell-and-dashboard]: satisfies TickerData operator used at Promise.all return site — structural type check without losing inference
- [Phase 12-next-js-core-shell-and-dashboard]: range || 1 in Sparkline guards against division by zero on flat OHLCV data
- [Phase 12-next-js-core-shell-and-dashboard]: useCallback with [accessToken] dep on loadDashboard prevents infinite fetch loops in DashboardClient useEffect

### Pending Todos

None yet.

### Blockers/Concerns

- WGC gold data still 501 — carried from v2.0 (does not block v3.0)
- Supabase invite flow with signups disabled has a known edge case: Site URL must point to password-set page, not login page — verify in Phase 11 before building onboarding
- SBV automated ingestion confidence is LOW (sbv.gov.vn has no stable scraping target) — Phase 16 baseline is manual PDF upload, not automation

## Session Continuity

Last session: 2026-03-18T17:39:39.883Z
Stopped at: Completed 12-02-PLAN.md
Resume file: None
