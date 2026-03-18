# Roadmap: Stratum

## Overview

Stratum is built in phases following the hard dependency chain of its two-pipeline architecture. v1.0 delivered infrastructure and data ingestion (Phases 1-2). v2.0 built the analytical reasoning engine (Phases 3-9). v3.0 delivers the user-facing product layer: auth, watchlist, dashboard, report view, TradingView chart, document ingestion, and dictionary expansion.

## Milestones

- ✅ **v1.0 Infrastructure and Data Ingestion** — Phases 1-2 (shipped 2026-03-09)
- ✅ **v2.0 Analytical Reasoning Engine** — Phases 3-9 (shipped 2026-03-17)
- 🚧 **v3.0 Product Frontend & User Experience** — Phases 10-16 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Infrastructure and Data Ingestion (Phases 1-2) — SHIPPED 2026-03-09</summary>

- [x] **Phase 1: Infrastructure and Storage Foundation** (2/2 plans) — completed 2026-03-03
- [x] **Phase 2: Data Ingestion Pipeline** (5/5 plans) — completed 2026-03-08

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

<details>
<summary>✅ v2.0 Analytical Reasoning Engine (Phases 3-9) — SHIPPED 2026-03-17</summary>

- [x] **Phase 3: Infrastructure Hardening and Database Migrations** (4/4 plans) — completed 2026-03-09
- [x] **Phase 4: Knowledge Graph and Document Corpus Population** (4/4 plans) — completed 2026-03-09
- [x] **Phase 5: Retrieval Layer Validation** (3/3 plans) — completed 2026-03-12
- [x] **Phase 6: LangGraph Reasoning Nodes** (5/5 plans) — completed 2026-03-15
- [x] **Phase 7: Graph Assembly and End-to-End Report Generation** (5/5 plans) — completed 2026-03-16
- [x] **Phase 8: FastAPI Gateway and Docker Service** (3/3 plans) — completed 2026-03-16
- [x] **Phase 8.1: Docker Runtime Fixes** (1/1 plan) — completed 2026-03-16
- [x] **Phase 9: Production Hardening and Batch Validation** (3/3 plans) — completed 2026-03-17

See: `.planning/milestones/v2.0-ROADMAP.md` for full details.

</details>

### 🚧 v3.0 Product Frontend & User Experience (In Progress)

**Milestone Goal:** Make Stratum usable as a product — invite-only auth, per-user watchlists, dashboard with entry quality cards, full report view with TradingView chart, report history, SSE progress, document ingestion, and Vietnamese dictionary expansion.

- [x] **Phase 10: Backend API Contracts and JWT Middleware** — JWT auth on reasoning-engine + new read-only endpoints for dashboard, OHLCV, and report history (completed 2026-03-18)
- [ ] **Phase 11: Supabase Auth and Per-User Watchlist** — Invite-only Supabase project, watchlist schema in VPS PostgreSQL, per-user data isolation
- [ ] **Phase 12: Next.js Core Shell and Dashboard** — Scaffolded Next.js Docker service, login page, dashboard with watchlist cards (tier badge, sparkline, last report date)
- [ ] **Phase 13: Report Generation with SSE Progress** — Generate Report button wired to FastAPI, real-time named pipeline steps via SSE, disabled state during active run
- [ ] **Phase 14: Report View, TradingView Chart, and History** — Full report expand, bilingual toggle, TradingView OHLCV chart, report history timeline with assessment change indicators
- [ ] **Phase 15: nginx and Docker Compose Integration** — nginx reverse proxy with SSE buffering disabled, TLS, CORS, end-to-end production wiring
- [ ] **Phase 16: Document Ingestion and Dictionary Expansion** — FOMC/SBV n8n ingestion pipelines with Qdrant deduplication, Vietnamese financial dictionary expanded to 300+ terms

## Phase Details

### Phase 10: Backend API Contracts and JWT Middleware
**Goal**: The reasoning-engine API is secured with Supabase JWT validation and exposes the data contracts needed by every dashboard and report UI component
**Depends on**: Phase 9 (v2.0 reasoning-engine fully shipped)
**Requirements**: INFR-03, INFR-04, INFR-05
**Success Criteria** (what must be TRUE):
  1. A request with no Authorization header to any `/reports/*` endpoint returns 401
  2. A request with a valid Supabase JWT returns the expected response; a request with an expired or wrong-audience token returns 403
  3. `GET /tickers/{symbol}/ohlcv` returns OHLCV + MA series in the exact format `{ time, open, high, low, close, volume }` consumed by TradingView Lightweight Charts
  4. `GET /reports/by-ticker/{symbol}` returns a paginated list of historical reports with tier badges and dates
  5. All new endpoints have Pydantic response schemas and are documented in the FastAPI OpenAPI spec
**Plans**: 2 plans
Plans:
- [ ] 10-01-PLAN.md — JWT auth dependency, Pydantic schemas, OHLCV endpoint with window function MAs
- [ ] 10-02-PLAN.md — Report history endpoint, auth wiring to all routes, OpenAPI verification

### Phase 11: Supabase Auth and Per-User Watchlist
**Goal**: Users can be invited by the admin, log in with email/password, and have a private watchlist that persists across sessions
**Depends on**: Phase 10 (JWT secret from Supabase project needed by auth.py)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, WTCH-01, WTCH-02, WTCH-03
**Success Criteria** (what must be TRUE):
  1. Admin can invite a user by email; invited user receives an email and can set a password to activate their account
  2. User can log in with email and password and remain logged in across browser refreshes (HTTP-only cookie session)
  3. Public signup is disabled — visiting the signup URL returns an error or redirects
  4. User can add and remove tickers from their watchlist; changes persist after closing and reopening the browser
  5. User A's watchlist is not visible to User B (per-user isolation enforced by RLS)
  6. A newly invited user's watchlist is pre-seeded with default tickers on first login
**Plans**: TBD

### Phase 12: Next.js Core Shell and Dashboard
**Goal**: Users can open a browser, log in, and see their watchlist as an actionable dashboard of entry quality cards with sparklines
**Depends on**: Phase 10 (JWT-protected API endpoints), Phase 11 (Supabase auth + watchlist schema)
**Requirements**: INFR-01, DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. Unauthenticated users are redirected to the login page; authenticated users land on the dashboard
  2. Dashboard shows a card for each watchlist ticker displaying the entry quality tier badge (color-coded Favorable/Neutral/Cautious/Avoid), a 52-week sparkline, and the last report date
  3. Dashboard shows a loading skeleton while data is fetching and an error toast if the API call fails
  4. Dashboard shows an appropriate empty state when the watchlist has no tickers
  5. Next.js Docker service starts with `mem_limit: 512m` and passes `docker stats` without exceeding its limit during normal dashboard load
**Plans**: TBD

### Phase 13: Report Generation with SSE Progress
**Goal**: Users can trigger a report generation from the dashboard and watch named pipeline steps update in real time as the LangGraph pipeline runs
**Depends on**: Phase 12 (dashboard with ticker cards)
**Requirements**: RGEN-01, RGEN-02, RGEN-03
**Success Criteria** (what must be TRUE):
  1. Clicking "Generate Report" on a ticker card triggers the FastAPI POST and shows an in-progress state immediately
  2. Named LangGraph pipeline steps (macro_regime, valuation, structure, etc.) appear in the UI in sequence as the pipeline progresses
  3. The Generate button is disabled and cannot be clicked again while a generation is active for that ticker
  4. SSE connection is cleanly closed when the user navigates away (no abandoned runs burning Gemini API budget)
**Plans**: TBD

### Phase 14: Report View, TradingView Chart, and History
**Goal**: Users can read any report in full with a bilingual toggle, see price structure in context via an interactive chart, and browse the history of assessments for a ticker
**Depends on**: Phase 13 (report generation produces reports to view)
**Requirements**: RVEW-01, RVEW-02, RVEW-03, RVEW-04, RHST-01, RHST-02, RHST-03, RHST-04
**Success Criteria** (what must be TRUE):
  1. Report view shows the summary card (entry quality tier, sub-assessments, one-line verdict) collapsed by default; user can expand to the full markdown report
  2. User can toggle between Vietnamese and English report versions; preference is remembered across page loads
  3. Report view includes a TradingView candlestick chart with weekly OHLCV, 50MA, and 200MA overlays that is zoomable and does not crash the Next.js build
  4. Report history timeline shows all past reports for a ticker with date, tier badge, and upgrade/downgrade arrows between consecutive assessments
  5. User can click any historical report in the timeline and open it in the full report view
**Plans**: TBD

### Phase 15: nginx and Docker Compose Integration
**Goal**: All services are wired through nginx with TLS; SSE streaming works end-to-end from browser to FastAPI through the proxy; the system is production-ready
**Depends on**: Phase 14 (all frontend features complete before wiring nginx)
**Requirements**: INFR-02
**Success Criteria** (what must be TRUE):
  1. `curl -N https://<domain>/api/reports/stream/<id>` receives SSE events in real time (not buffered); nginx does not batch events
  2. All HTTP traffic is redirected to HTTPS; TLS certificate is valid and auto-renewing via certbot
  3. Unauthenticated requests to protected API routes through nginx return 401 (not a 502 or proxy error)
  4. All 10 Docker services start cleanly with `docker compose up -d` and pass health checks
**Plans**: TBD

### Phase 16: Document Ingestion and Dictionary Expansion
**Goal**: The macro document corpus grows automatically when FOMC minutes are released, SBV reports can be manually ingested without touching the filesystem, and the Vietnamese financial dictionary covers earnings-season vocabulary
**Depends on**: Phase 15 (production system available for end-to-end ingestion verification)
**Requirements**: DING-01, DING-02, DING-03, DICT-01
**Success Criteria** (what must be TRUE):
  1. The n8n FOMC cron workflow runs monthly, fetches new minutes from the Fed RSS feed, and upserts them into Qdrant via the data-sidecar; running the workflow twice does not create duplicate vectors
  2. An SBV report PDF can be ingested via n8n manual trigger without requiring direct filesystem access
  3. Ingested documents are chunked, embedded at 384 dimensions via FastEmbed, and searchable in Qdrant within 5 minutes of ingestion
  4. The Vietnamese financial dictionary contains 300+ terms and correctly translates earnings-season vocabulary (KQKD, EBITDA, earnings per share) in generated reports
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure and Storage Foundation | v1.0 | 2/2 | Complete | 2026-03-03 |
| 2. Data Ingestion Pipeline | v1.0 | 5/5 | Complete | 2026-03-08 |
| 3. Infrastructure Hardening | v2.0 | 4/4 | Complete | 2026-03-09 |
| 4. Knowledge Graph Population | v2.0 | 4/4 | Complete | 2026-03-09 |
| 5. Retrieval Layer Validation | v2.0 | 3/3 | Complete | 2026-03-12 |
| 6. LangGraph Reasoning Nodes | v2.0 | 5/5 | Complete | 2026-03-15 |
| 7. Graph Assembly & E2E Reports | v2.0 | 5/5 | Complete | 2026-03-16 |
| 8. FastAPI Gateway | v2.0 | 3/3 | Complete | 2026-03-16 |
| 8.1. Docker Runtime Fixes | v2.0 | 1/1 | Complete | 2026-03-16 |
| 9. Production Hardening | v2.0 | 3/3 | Complete | 2026-03-17 |
| 10. Backend API Contracts and JWT Middleware | 2/2 | Complete    | 2026-03-18 | - |
| 11. Supabase Auth and Per-User Watchlist | v3.0 | 0/? | Not started | - |
| 12. Next.js Core Shell and Dashboard | v3.0 | 0/? | Not started | - |
| 13. Report Generation with SSE Progress | v3.0 | 0/? | Not started | - |
| 14. Report View, TradingView Chart, and History | v3.0 | 0/? | Not started | - |
| 15. nginx and Docker Compose Integration | v3.0 | 0/? | Not started | - |
| 16. Document Ingestion and Dictionary Expansion | v3.0 | 0/? | Not started | - |
