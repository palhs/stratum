---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Product Frontend & User Experience
status: ready_to_plan
last_updated: "2026-03-18"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-17)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** v3.0 Phase 10 — Backend API Contracts and JWT Middleware

## Current Position

Milestone: v3.0 — Product Frontend & User Experience
Phase: 10 of 16 (Backend API Contracts and JWT Middleware)
Plan: 0 of ? (not yet planned)
Status: Ready to plan
Last activity: 2026-03-18 — v3.0 roadmap created (7 phases, 33 requirements)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0 (v3.0)
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| — | — | — | — |

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

### Pending Todos

None yet.

### Blockers/Concerns

- WGC gold data still 501 — carried from v2.0 (does not block v3.0)
- Supabase invite flow with signups disabled has a known edge case: Site URL must point to password-set page, not login page — verify in Phase 11 before building onboarding
- SBV automated ingestion confidence is LOW (sbv.gov.vn has no stable scraping target) — Phase 16 baseline is manual PDF upload, not automation

## Session Continuity

Last session: 2026-03-18
Stopped at: v3.0 roadmap created — ready to plan Phase 10
Resume file: None
