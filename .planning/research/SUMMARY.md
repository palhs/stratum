# Project Research Summary

**Project:** Stratum v3.0 — Product Frontend and User Experience
**Domain:** Invite-only investment advisory platform — Next.js dashboard, Supabase auth, TradingView charts, document ingestion, and Vietnamese financial dictionary expansion over an existing FastAPI + PostgreSQL + Docker Compose v2.0 analytical reasoning engine
**Researched:** 2026-03-17
**Confidence:** HIGH

---

## Executive Summary

Stratum v3.0 is a product UX layer built on top of a fully operational v2.0 analytical reasoning engine. The backend is already running: FastAPI report generation, LangGraph 7-node pipeline, PostgreSQL with OHLCV and structure markers, Neo4j regime graph, Qdrant vector store, and n8n ingestion orchestration. The entire v3.0 effort is frontend-first — building the interfaces, auth flow, and data connections that turn the engine into something users can actually open in a browser. The recommended approach is Next.js 15 App Router with Supabase Cloud for invite-only auth, TradingView Lightweight Charts for OHLCV visualization, and minimal additions to the existing backend (JWT middleware, 2–3 new read-only endpoints, one new data-sidecar endpoint for document ingestion). The frontend requires two new Docker services (Next.js at 512m and nginx at 64m) that fit within the ~1.5GB headroom remaining after existing services commit 6.5GB of the 8GB VPS.

The architecture decision that shapes all of v3.0 is a deliberate two-database split: Supabase Cloud handles auth and watchlists (tiny user data, zero self-hosted overhead), while VPS PostgreSQL retains all analytical data (reports, OHLCV, structure markers). Self-hosting Supabase would add 7+ containers consuming 2–3GB RAM and blow the VPS budget. The frontend only talks to Supabase (for identity) and the reasoning-engine API (for analytical data). The reasoning-engine validates all requests via a new JWT middleware using only the Supabase JWT secret — no Supabase SDK required on the Python side. Watchlists live in Supabase with RLS; reports, OHLCV, and structure data stay in VPS PostgreSQL. These two databases are never joined — the boundary is enforced in application code.

The primary risks are operational rather than architectural. SSE proxy buffering silently breaks progress streaming unless explicitly disabled in nginx and bypassed in Next.js rewrites. VPS memory pressure is real with only ~1.5GB headroom for new services. TradingView Lightweight Charts crashes Next.js builds unless wrapped in `dynamic(..., { ssr: false })`. The Supabase service role key must never carry a `NEXT_PUBLIC_` prefix. All of these are known failure modes with documented prevention patterns — they are manageable when addressed at the right phase and verified before declaring that phase complete.

---

## Key Findings

### Recommended Stack

The frontend stack centers on Next.js 15.3 App Router (React 19, TypeScript 5, Tailwind v4, shadcn/ui) as the dashboard framework, deployed as a standalone Docker image via nginx reverse proxy on the existing VPS. Supabase JS SDK v2.99.x with `@supabase/ssr` handles invite-only cookie-based auth for the App Router. TradingView Lightweight Charts v5.1.0 renders OHLCV candlestick and MA overlay charts client-only. React Query v5 manages server state from the FastAPI backend; Zustand v5 handles UI state (SSE progress, open sections). `@microsoft/fetch-event-source` is required for authenticated SSE because the native `EventSource` API cannot send Authorization headers.

On the Python side, `pymupdf4llm` handles PDF-to-Markdown extraction for the document ingestion pipeline (faster than pdfplumber, outputs clean Markdown for Qdrant). `APScheduler 3.11` runs scheduled ingestion jobs inside the FastAPI lifespan context, keeping FOMC ingestion co-located with the FastEmbed model already loaded in the sidecar. All stack versions verified against official npm and PyPI registries on 2026-03-17.

**Core technologies:**
- `next@15.3.x` + `react@19.x` + `typescript@5.x`: App Router dashboard framework — stable release, SSR enables Server Components for direct Supabase calls without an extra API layer
- `tailwindcss@4.x` + `shadcn/ui` (latest CLI): UI foundation — Tailwind v4 CSS-first config (no config file); shadcn/ui copies components into repo for zero unused runtime overhead
- `@supabase/supabase-js@2.99.x` + `@supabase/ssr` (latest): Invite-only auth for Next.js App Router — `@supabase/ssr` mandatory for cookie-based session refresh in Server Components; `@supabase/auth-helpers-nextjs` is deprecated and must not be used
- `lightweight-charts@5.1.0`: OHLCV candlestick + MA overlay — 45KB canvas library; v5.1 adds data conflation for large datasets; requires `dynamic({ ssr: false })` in Next.js
- `@tanstack/react-query@5.90.x` + `zustand@5.0.x`: Server state and UI state — React Query for all FastAPI data; Zustand for SSE progress and UI-only state; Redux is explicitly wrong for this scope
- `@microsoft/fetch-event-source@2.0.1`: Authenticated SSE client — only maintained option supporting Authorization headers; native `EventSource` (WHATWG spec issue #2177) cannot send headers
- `recharts@2.x`: Sparkline charts on watchlist cards — lightweight SVG for 52-week price mini-charts; TradingView is overkill for sparklines
- `pymupdf4llm` + `apscheduler@3.11.x`: Document ingestion — PDF-to-Markdown extraction and FOMC/SBV scheduled ingestion inside FastAPI lifespan

**Version constraints:**
- Do not pin React 18 — Next.js 15.3 ships React 19 by default; manual React 18 pin causes peer dependency conflicts
- Use Tailwind v4, not v3 — v3 is in maintenance mode; shadcn/ui now defaults to v4
- `@supabase/supabase-js` and `@supabase/ssr` must be installed together; both must stay in sync

### Expected Features

All three research files agree: auth is the unblocking dependency for everything per-user, and the core MVP is a tight set of 8 deliverables. The feature dependency chain is strict and documented.

**Must have (table stakes for v3.0 launch — P1):**
- Supabase Auth invite-only configuration (signup disabled, admin invite API) — gates all per-user state; without this, there is no user_id to scope anything to
- Per-user watchlist management (add/remove, VN30 + gold universe only, ~31 items max) — gates dashboard content
- Dashboard with watchlist cards (entry quality tier badge as primary signal, sparkline, last report date) — product entry point
- Manual "Generate Report" trigger with SSE progress display — core user action; POST and SSE endpoints already exist in FastAPI
- Report summary + full expand view — progressive disclosure of structured JSON report cards; markdown rendering for full view
- Bilingual toggle (Vietnamese default / English) — both language variants already in PostgreSQL; toggle is a React state change
- TradingView chart in report view (weekly OHLCV + 50MA + 200MA) — contextualizes price structure analysis in reports
- Report history timeline per ticker with assessment change indicators (upgrade/downgrade arrows) — enables monitoring regime shifts over time
- New `GET /tickers/{symbol}/ohlcv` FastAPI endpoint — required by the TradingView chart; simple PostgreSQL read but must be added

**Should have (competitive differentiators, add after first users validate — P2):**
- Automated FOMC minutes ingestion via n8n (monthly cron, Fed RSS feed confirmed reliable)
- Vietnamese dictionary expansion (+80–120 terms covering earnings vocabulary, sector terms, VAS-to-IFRS)
- Assessment change email digest via n8n (existing n8n email infrastructure)

**Defer to v4.0+:**
- Automated SBV ingestion — sbv.gov.vn has no RSS feed; CSS scraping is fragile; manual PDF upload is the safe fallback for v3.0
- Real-time price feed — contradicts weekly analytical cadence; show `last_close_price` with "as of [date]" label; link to Vietstock for live lookup
- Portfolio P&L tracking, AI chat, social features, PDF export, push notifications — all disproportionately complex relative to value at this stage
- Ticker universe beyond VN30 + gold — hard-code to supported universe until VN30 coverage is validated

**Anti-features to explicitly reject:**
- Portfolio P&L tracking opens compliance questions under Vietnamese financial regulations
- AI chat over reports creates uncontrolled LLM responses with liability risk; structured report expansion handles this use case
- Real-time price feeds create expectation mismatch with weekly analytical cadence

### Architecture Approach

v3.0 adds exactly two new Docker services (Next.js `frontend` at 512m and `nginx` at 64m) to the existing 8-service Docker Compose stack, consuming ~576m of the ~1.5GB headroom within the 8GB VPS. A new `frontend` Docker network bridges nginx and the Next.js container. Nginx joins both the `frontend` network and the existing `reasoning` network — it is the sole gateway between the public internet and all internal services. The reasoning-engine receives a new `auth.py` JWT verification dependency and 2–3 new read-only endpoints. The data-sidecar receives a new `POST /documents/ingest` endpoint that enforces the locked 384-dim FastEmbed embedding model as the single embedding entrypoint. Supabase Cloud is external — never a Docker service.

The two-database design is the central architectural constraint: user identity and watchlists in Supabase Cloud; all analytical data in VPS PostgreSQL. No cross-database JOINs. Dashboard makes two sequential calls: Supabase for ticker list, reasoning-engine for report summaries. This is acceptable at invite-only scale.

**Major components:**
1. `Next.js frontend` (new Docker service, 512m) — Dashboard, report view, login; reads Supabase for watchlist/identity, reads reasoning-engine API for all analytical data; never touches PostgreSQL, Neo4j, or Qdrant directly
2. `nginx` (new Docker service, 64m) — TLS termination, reverse proxy (`/api/*` to reasoning-engine, `/` to frontend), SSE buffering disabled; bridges `frontend` and `reasoning` networks
3. `reasoning-engine` (modified) — JWT middleware added (`auth.py`); new read-only endpoints for dashboard batch data, OHLCV series, and reports list
4. `Supabase Cloud` (external, free tier) — Auth tokens, user identity, `watchlists` table with RLS policy (`user_id = auth.uid()`)
5. `data-sidecar` (modified) — New `POST /documents/ingest` endpoint: PDF download → text extraction → chunking → FastEmbed 384-dim → Qdrant upsert; the only component that embeds into Qdrant
6. `n8n` (modified) — New FOMC monthly cron workflow and SBV manual trigger workflow; sends to data-sidecar, never embeds directly into Qdrant

**Key patterns:**
- TradingView chart always loaded via `dynamic(() => import(...), { ssr: false })` — `"use client"` alone is insufficient
- JWT passed as `Authorization: Bearer <token>` header on all reasoning-engine calls — not via cookie (cross-service boundary)
- n8n document ingestion always calls data-sidecar, never Qdrant directly — preserves FastEmbed 384-dim constraint
- nginx is the only service that bridges `frontend` and `reasoning` networks — Next.js cannot reach storage services directly

### Critical Pitfalls

1. **SSE proxy buffering silently breaks progress streaming** — nginx buffers proxied responses by default; Next.js API routes buffer response bodies until the handler function resolves. Use `next.config.js` rewrites (not API routes) for SSE; set `proxy_buffering off`, `X-Accel-Buffering: no`, `proxy_read_timeout 300s` in the nginx SSE location block. Verify with `curl -N` against the production domain before building any SSE UI — this is the single most common silent failure in this stack.

2. **TradingView Lightweight Charts crashes Next.js builds at build time** — `lightweight-charts` accesses `window` and `document` on import; Next.js pre-renders server components during `next build`. `"use client"` directive alone is insufficient — the import must also be `dynamic(..., { ssr: false })`. This causes build-time failures (not just runtime), blocking all deployments.

3. **VPS OOM kills when adding Next.js Docker service without memory limits** — existing 8 services commit 6.5GB; Next.js build spikes to 1.5–2GB. Set `mem_limit: 512m` and `NODE_OPTIONS=--max-old-space-size=256` on the frontend service; pre-build the Docker image externally (never run `next build` at container startup). OOM kills leave no application-level error — `dmesg | grep -i oom` is the only trace.

4. **Supabase service role key exposed in client-side bundle** — `NEXT_PUBLIC_` prefix injects env vars into the browser bundle. Only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` may carry this prefix. `SUPABASE_SERVICE_ROLE_KEY` must be server-only. Key bypass all RLS — if exposed, any browser has full database write access.

5. **JWT validation missing audience claim passes or blocks all tokens silently** — Supabase JWTs use `"aud": "authenticated"`; PyJWT does not enforce audience by default. Always decode with `audience="authenticated"` and `options={"verify_exp": True}`. Test with an expired token and a token from a different Supabase project — both must return 403.

**Additional high-priority pitfalls:**
- **SSE connection leak on page navigation** — `AbortController` in `useEffect` cleanup is mandatory; add `await request.is_disconnected()` guard in FastAPI SSE generator to stop burning Gemini API budget on abandoned runs
- **Supabase dual-database confusion** — `watchlists` table belongs in VPS PostgreSQL with `user_id UUID` column, not in Supabase-managed DB; never attempt cross-database JOINs
- **PDF re-ingestion creates duplicate Qdrant vectors** — add document hash deduplication to n8n FOMC workflow before upserting
- **CORS wildcard with credentials** — FastAPI `CORSMiddleware` explicitly disallows `allow_origins=["*"]` with `allow_credentials=True`; list exact Next.js production origin

---

## Implications for Roadmap

The architecture defines a clear dependency chain that maps directly to phase structure. JWT middleware must exist and be tested before any frontend code calls the API. API response schemas must be defined before UI components consume them. All services must work independently before nginx wires them together. Document ingestion is independent of the frontend and should be deferred until after users validate the core product.

### Phase 1: Backend Auth and API Contracts

**Rationale:** The frontend cannot be built without JWT protection and defined data contracts. Auth middleware must exist before any user-data endpoint is added. Undefined response schemas cause cascading rework in UI components. This is pure Python — no frontend code written in this phase. The Supabase JWT secret (from Phase 2 Supabase project creation) is needed here; Phase 1 and Phase 2 can proceed in parallel if Supabase project setup starts simultaneously.
**Delivers:** `auth.py` JWTBearer dependency applied to all existing `/reports/*` endpoints; new `GET /reports` (list by ticker, paginated); new `GET /watchlist-data?tickers=...` (batch entry quality for dashboard cards); new `GET /tickers/{symbol}/ohlcv` (OHLCV + MA series for TradingView chart); all endpoints documented with Pydantic response schemas
**Addresses:** OHLCV chart endpoint (TradingView data contract), watchlist dashboard batch query
**Avoids:** Pitfall 5 (JWT audience validation built in from first line), Pitfall 2 (data ownership boundary defined in schema before watchlist code is written)

### Phase 2: Supabase Project Setup and Watchlist Schema

**Rationale:** Supabase Cloud project must be configured before Next.js client code can be scaffolded. Watchlist schema decision (VPS PostgreSQL, not Supabase DB) must be locked before any watchlist code is written. JWT secret from Supabase is needed by Phase 1 — can proceed in parallel.
**Delivers:** Supabase project created; public signups disabled; `inviteUserByEmail` admin invite flow verified working; `watchlists` table with `user_id UUID` column added to VPS PostgreSQL via Flyway migration (not in Supabase DB); Supabase `watchlists` RLS policy created for frontend reads; `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` documented as required env vars
**Avoids:** Pitfall 4 (service role key exposure — code review rules established before any Supabase client code is written), Pitfall on dual-database confusion (data ownership contract locked in schema before implementation)

### Phase 3: Next.js Core Shell and Dashboard

**Rationale:** With JWT-protected API endpoints available (Phase 1) and Supabase configured (Phase 2), the Next.js scaffold can be built against real APIs. This phase delivers the product entry point and establishes all critical patterns (Docker standalone, memory limits, SSE rewrites) before any user-facing feature depends on them.
**Delivers:** Next.js 15 App Router scaffolded with `@supabase/ssr`; auth middleware (`middleware.ts`) with `getUser()` route protection; login page; dashboard with watchlist cards (entry quality tier badge, 52-week sparkline via recharts, last report date); watchlist add/remove (VN30 + gold universe); Docker service with `mem_limit: 512m` and `NODE_OPTIONS=--max-old-space-size=256`; empty and loading states (skeleton loaders, error toasts)
**Uses:** Next.js 15, Supabase SSR, React Query v5, recharts, shadcn/ui, Tailwind v4, Zustand
**Avoids:** Pitfall 3 (VPS memory — `mem_limit` and `NODE_OPTIONS` set before first deploy); SSE rewrite pattern established in `next.config.ts` even before SSE UI is built

### Phase 4: Report View, TradingView Chart, and SSE Progress

**Rationale:** Depends on the dashboard shell (Phase 3) for navigation context. TradingView chart is the most technically constrained component (SSR crash, canvas lifecycle) — isolating it here prevents blocking the dashboard. SSE progress display introduces `@microsoft/fetch-event-source` and the `AbortController` cleanup pattern.
**Delivers:** Full report view page with markdown rendering (progressive disclosure: summary → expand sections); bilingual toggle (Vietnamese default / English; preference via `localStorage`); TradingView OHLCV chart (candlestick + 50MA + 200MA, weekly, 1Y/2Y/5Y/All zoom); report history timeline per ticker with assessment change indicators (upgrade/downgrade arrows); "Generate Report" button with SSE progress display (named LangGraph nodes); `@microsoft/fetch-event-source` with `AbortController` cleanup
**Uses:** `lightweight-charts@5.1.0` (dynamic import, `ssr: false`), `@microsoft/fetch-event-source`, Zustand (SSE state)
**Avoids:** Pitfall 1 (TradingView SSR — `dynamic({ ssr: false })` enforced from first chart component line), Pitfall 7 (SSE connection leak — `AbortController` in `useEffect` cleanup built from the start, FastAPI `is_disconnected()` guard)

### Phase 5: nginx, Docker Compose Integration, and Production TLS

**Rationale:** nginx is the final integration layer. All services must work independently before wiring nginx routing and TLS. This phase brings v3.0 to production-ready state. SSE streaming through nginx must be verified before declaring this phase complete.
**Delivers:** `nginx.conf` with SSE buffering disabled (`proxy_buffering off`, `X-Accel-Buffering: no`, `proxy_read_timeout 300s`); `frontend` Docker network; `frontend` and `nginx` services added to `docker-compose.yml`; TLS certificates (certbot); `next.config.ts` rewrites for SSE (bypasses Next.js response buffering); CORS configured with exact production origin; end-to-end auth flow verified browser → nginx → FastAPI; SSE streaming verified with `curl -N` against production domain
**Avoids:** Pitfall 1 (SSE proxy buffering — `curl -N` to production domain is the acceptance test before declaring done), CORS with credentials configured correctly

### Phase 6: Document Ingestion Pipelines

**Rationale:** Document ingestion improves report quality but does not block any frontend feature. The reasoning-engine already works with the existing Qdrant corpus. Ship the UI and validate it with real users first, then expand the document corpus based on feedback about which macro context gaps matter most.
**Delivers:** `POST /documents/ingest` endpoint on data-sidecar (PDF download → pypdf extraction → 512-token chunking → FastEmbed 384-dim → Qdrant upsert with document hash deduplication); n8n FOMC monthly cron workflow (Fed RSS → PDF → data-sidecar); n8n SBV manual trigger workflow (PDF upload → data-sidecar); deduplication verified by running each workflow twice
**Uses:** `pymupdf4llm`, existing `httpx` (already installed), existing FastEmbed 384-dim (dimension constraint enforced via data-sidecar as sole embedding entrypoint)
**Avoids:** Embedding documents in n8n directly (incompatible vector dimensions with existing Qdrant collections), PDF re-ingestion duplicate Qdrant vectors

### Phase 7: Vietnamese Dictionary Expansion

**Rationale:** Content work fully independent of all other phases. Can run in parallel with any phase above. Listed last because it has the lowest blocking risk — it improves report quality incrementally but never blocks a feature.
**Delivers:** 162-term base dictionary expanded to 300+ terms covering earnings vocabulary (KQKD, EBITDA transliteration, earnings-season terminology), sector-specific terms, and VAS-to-IFRS mapping; optional Flyway V8 migration to store dictionary in PostgreSQL rather than a JSON file
**Addresses:** Report quality for Vietnamese-language readers during earnings season; identified gap from FEATURES.md

### Phase Ordering Rationale

- Backend security (JWT middleware) before frontend code — no period where the API is unprotected during development
- API contracts (Pydantic response schemas) before UI — prevents cascading rework when response shapes change
- Docker memory audit and `mem_limit` configuration before first deploy — prevents silent OOM kills of production services
- nginx wired last — all services must function independently before introducing a routing and TLS layer
- Document ingestion after user-facing product ships — real user feedback should inform which document sources matter most before investing engineering time in fragile SBV scraping
- Dictionary expansion runs in parallel — pure content work with no code dependencies

### Research Flags

Phases needing deeper research during planning:

- **Phase 6 (Document Ingestion — SBV sub-feature):** sbv.gov.vn structure is unstable with no confirmed RSS feed. Automated SBV ingestion should be treated as experimental; prototype the n8n HTTP scraping workflow before committing it to a roadmap deliverable. Manual PDF upload via n8n file trigger is the safe fallback and should be the Phase 6 baseline. LOW confidence on automated SBV specifically.
- **Phase 5 (nginx TLS — certbot renewal):** TLS certificate renewal in Docker (certbot + nginx lifecycle) has known edge cases on self-hosted VPS; verify renewal cron does not conflict with nginx container restart behavior before going to production.

Phases with well-established patterns (can skip additional research):

- **Phase 1 (JWT middleware):** Supabase JWT + FastAPI + PyJWT with `audience="authenticated"` is the single documented correct approach; official Supabase docs and multiple community sources agree.
- **Phase 2 (Supabase setup):** Official Supabase invite-only quickstart is unambiguous; one known quirk (invite fails if Site URL points to login page, not password-set page) is documented with a clear workaround.
- **Phase 3 (Next.js scaffold):** Next.js 15 App Router + Supabase SSR has an official Supabase quickstart; patterns are unambiguous.
- **Phase 4 (TradingView chart):** Official TradingView docs confirm the `dynamic({ ssr: false })` + `useRef` + `useEffect` pattern; 30-line wrapper, no official React package needed.
- **Phase 7 (Dictionary expansion):** Pure content work with no integration risk.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against npm and PyPI on 2026-03-17. No canary or beta dependencies. One MEDIUM-confidence item: `@microsoft/fetch-event-source` is unmaintained (last published ~5 years ago) but has 1.1M downloads/week, no known issues, and no maintained alternative with equivalent API. |
| Features | MEDIUM-HIGH | Financial platform UX patterns are HIGH confidence (industry standard conventions from Robinhood, Bloomberg, Simply Wall St). Supabase invite-only flow is MEDIUM (documented, known quirk with invite + signups disabled — workaround exists). SBV automated ingestion is LOW confidence due to unstable website structure. |
| Architecture | HIGH | Existing v2.0 codebase fully inspected; service topology, Docker networks, and memory budgets verified against actual running system. Integration patterns (Supabase JWT → FastAPI, TradingView SSR, nginx SSE) verified against official docs and confirmed community sources. Two-database split is the only viable approach given VPS memory budget. |
| Pitfalls | MEDIUM-HIGH | SSE proxy buffering, TradingView SSR crash, service role key exposure, and CORS with credentials all verified via official docs and multiple community post-mortems. VPS memory budget validated against measured `docker stats` on existing services. PDF ingestion pitfalls from community post-mortems. |

**Overall confidence:** HIGH

### Gaps to Address

- **SBV automated ingestion viability:** sbv.gov.vn has no confirmed stable scraping target. Prototype the n8n HTTP Request + CSS selector workflow before committing to this as a Phase 6 deliverable. Manual PDF upload is the v3.0 baseline — automated SBV is a stretch goal contingent on prototype results.

- **Supabase invite flow with signups disabled:** There is a documented edge case where `inviteUserByEmail()` fails when public signups are disabled — the workaround is to ensure the Supabase project's Site URL points to a password-set page (not a login page). Validate this specific flow in Phase 2 before building any user onboarding.

- **OHLCV endpoint response contract:** The new `GET /tickers/{symbol}/ohlcv` endpoint response schema must precisely match the TradingView Lightweight Charts data format (`{ time, open, high, low, close, volume }` with Unix timestamps). This contract must be defined in Phase 1 before the chart component is built in Phase 4 — misaligned formats cause silent rendering failures, not errors.

- **n8n memory ceiling for large PDFs:** FOMC minutes PDFs can reach 50–100 pages. Verify the n8n FOMC workflow completes within the 512m `mem_limit` on the n8n service with a realistic-size PDF. n8n HTTP Request nodes have no default timeout (GitHub issue #7081) — set explicit timeouts in the workflow before the first production cron run.

- **Vietnamese number/date formatting hydration mismatch:** `toLocaleString()` with `"vi-VN"` locale produces different output in Node.js (SSR) vs. Chrome (client) due to ICU data differences. Establish a single locale-aware formatting utility used only in client components or inside `useEffect` — validate with React devtools hydration warnings before Phase 3 is declared complete.

---

## Sources

### Primary (HIGH confidence)

- [Next.js 15.5 blog](https://nextjs.org/blog/next-15-5) — current stable release confirmed
- [TradingView Lightweight Charts GitHub releases](https://github.com/tradingview/lightweight-charts/releases) — v5.1.0 latest confirmed
- [TradingView Lightweight Charts SSR Issue #543](https://github.com/tradingview/lightweight-charts/issues/543) — `dynamic({ ssr: false })` workaround confirmed in official repo
- [@supabase/supabase-js npm](https://www.npmjs.com/package/@supabase/supabase-js) — v2.99.2 current as of 2026-03-17
- [Supabase SSR docs for Next.js](https://supabase.com/docs/guides/auth/server-side/nextjs) — `@supabase/ssr` mandatory for App Router; `@supabase/auth-helpers-nextjs` deprecated
- [Supabase inviteUserByEmail API](https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail) — invite-only admin pattern confirmed
- [Supabase Pricing free tier](https://supabase.com/pricing) — 50K MAU, 500MB DB confirmed sufficient for invite-only scale
- [Federal Reserve RSS feeds](https://www.federalreserve.gov/feeds/feeds.htm) — FOMC RSS feed confirmed operational
- [EventSource headers WHATWG issue #2177](https://github.com/whatwg/html/issues/2177) — native `EventSource` cannot send headers, unresolved as of 2026
- [FastAPI SSE official docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — SSE endpoint pattern confirmed
- [Docker Resource Limits](https://docs.docker.com/engine/containers/resource_constraints/) — `mem_limit` behavior confirmed
- [Tailwind CSS v4 install for Next.js](https://tailwindcss.com/docs/guides/nextjs) — v4 current, compatible with Next.js 15 and shadcn/ui
- [shadcn/ui Next.js install](https://ui.shadcn.com/docs/installation/next) — CLI-based, Tailwind v4 supported
- [@tanstack/react-query npm](https://www.npmjs.com/package/@tanstack/react-query) — v5.90.21 confirmed
- [pymupdf4llm PyPI](https://pypi.org/project/pymupdf4llm/) — active, install command confirmed
- [APScheduler docs](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — `AsyncIOScheduler` for asyncio FastAPI confirmed

### Secondary (MEDIUM confidence)

- [FastAPI + Supabase JWT verification (DEV Community)](https://dev.to/j0/integrating-fastapi-with-supabase-auth-780) — `audience="authenticated"` requirement; verified against JWT spec
- [Supabase invite-only discussion #4296](https://github.com/orgs/supabase/discussions/4296) — disable signups + admin invite pattern; Site URL quirk documented
- [Surviving SSE Behind Nginx Proxy Manager (Medium)](https://medium.com/@dsherwin/surviving-sse-behind-nginx-proxy-manager-npm-a-real-world-deep-dive-69c5a6e8b8e5) — nginx SSE buffering directives; verified against nginx official docs
- [Next.js SSE don't work in API routes #48427](https://github.com/vercel/next.js/discussions/48427) — use `next.config.js` rewrites, not API routes, for SSE
- [n8n PDF → Qdrant RAG workflow template](https://n8n.io/workflows/4400-build-a-pdf-document-rag-system-with-mistral-ocr-qdrant-and-gemini-ai/) — document ingestion flow pattern (official n8n template)
- [Qdrant n8n Integration Tutorial](https://qdrant.tech/documentation/tutorials-build-essentials/qdrant-n8n/) — confirmed data-sidecar as sole embedding entrypoint pattern

### Tertiary (LOW confidence — needs validation)

- [sbv.gov.vn](https://sbv.gov.vn) — no confirmed RSS feed or stable scraping target for automated SBV ingestion; must be prototyped before committing
- [n8n HTTP requests default timeout issue #7081](https://github.com/n8n-io/n8n/issues/7081) — timeout behavior in n8n HTTP Request nodes; verify against current n8n version in use

---
*Research completed: 2026-03-17*
*Ready for roadmap: yes*
