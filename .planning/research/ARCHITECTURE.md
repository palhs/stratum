# Architecture Patterns

**Domain:** Investment advisor platform — Next.js frontend + Supabase auth + TradingView charts + document ingestion over existing Docker Compose + FastAPI + PostgreSQL
**Researched:** 2026-03-17
**Confidence:** HIGH (existing codebase fully inspected; integration patterns verified against official docs and community sources)

---

## Context: What Already Exists (v2.0)

This document focuses exclusively on how v3.0 components integrate with the existing platform. Do not rebuild what exists.

**Existing Docker Compose services (9 active):**

| Service | Network | Role | mem_limit |
|---------|---------|------|-----------|
| `postgres` | ingestion + reasoning | Structured storage — OHLCV, fundamentals, structure markers, reports, report_jobs, LangGraph checkpoints | 512m |
| `neo4j` | ingestion + reasoning | Regime graph — 17 nodes, HAS_ANALOGUE relationships | 2g |
| `qdrant` | ingestion + reasoning | Vector store — macro_docs + earnings_docs hybrid collections | 1g |
| `n8n` | ingestion only | Cron orchestration — data ingestion pipelines | 512m |
| `data-sidecar` | ingestion only | FastAPI — vnstock, FRED, gold, structure marker computation | 512m |
| `reasoning-engine` | reasoning only | FastAPI + LangGraph — POST /reports/generate, GET /reports/{id}, SSE /reports/stream/{id} | 2g |
| `flyway` | ingestion | One-shot migration runner (V1–V7 applied) | — |
| `neo4j-init` | ingestion | One-shot constraints + APOC trigger installer | — |
| `qdrant-init` | ingestion | One-shot collection initializer | — |

**Existing FastAPI endpoints (reasoning-engine, port 8001):**

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/reports/generate` | 202 + job_id, triggers BackgroundTask LangGraph pipeline |
| GET | `/reports/{id}` | Fetch completed report JSON from PostgreSQL |
| GET | `/reports/stream/{id}` | SSE stream — per-node progress events during generation |
| GET | `/health` | Health check for Docker monitoring |

**Hard architectural constraints (locked, do not modify):**
- n8n on `ingestion` network only — cannot reach reasoning-engine
- reasoning-engine on `reasoning` network only — cannot reach n8n or data-sidecar
- PostgreSQL has no host port mapping — internal only
- Qdrant has no host port mapping — internal only
- FastEmbed 384-dim locked — cannot change Qdrant collection dimensions

**Current VPS memory budget (8GB total, 4GB swap):**

| Service | mem_limit | Actual Usage |
|---------|-----------|--------------|
| postgres | 512m | ~200MB typical |
| neo4j | 2g | ~1.5GB (heap + pagecache) |
| qdrant | 1g | ~200MB current corpus |
| n8n | 512m | ~300MB |
| data-sidecar | 512m | ~150MB |
| reasoning-engine | 2g | ~800MB–1.5GB during LangGraph run |
| **Total committed** | **6.5g** | **~3.1–4.1GB typical** |
| **Available for v3.0** | **~1.5g headroom** | Within 8GB total |

---

## System Overview (v3.0 Target State)

```
+=====================================================================+
|  PUBLIC INTERNET                                                    |
|                                                                     |
|  Browser ──────────────────────────────────────────────────────►   |
+=====================================================================+
|  NGINX (new — reverse proxy + TLS termination)                      |
|                                                                     |
|  /         → frontend:3000 (Next.js)                                |
|  /api/*    → reasoning-engine:8000 (FastAPI, existing)              |
|                                                                     |
|  All traffic must carry valid Supabase JWT to /api/* routes          |
+=====================================================================+
|  FRONTEND NETWORK (new — Next.js + nginx)                           |
|                                                                     |
|  ┌─────────────────────────────────────────────────────────┐        |
|  │  frontend  (new Docker service)                          │        |
|  │  Next.js 15 App Router — port 3000                       │        |
|  │                                                          │        |
|  │  Pages:                                                  │        |
|  │    /           → Dashboard (watchlist cards)             │        |
|  │    /report/[id] → Report view + TradingView chart        │        |
|  │    /login       → Supabase magic link / email+pw         │        |
|  │                                                          │        |
|  │  Client calls:                                           │        |
|  │    supabase-js → Supabase Cloud (auth + session)         │        |
|  │    fetch /api/reports/* → reasoning-engine (w/ JWT)      │        |
|  │    EventSource polyfill → reasoning-engine SSE (w/ JWT)  │        |
|  │    TradingView Lightweight Charts (CDN/npm, client-only) │        |
|  └─────────────────────────────────────────────────────────┘        |
+=====================================================================+
|  SUPABASE CLOUD (external — auth + watchlist + user profiles)       |
|                                                                      |
|  ┌─────────────────────────────────────────────────────────┐        |
|  │  Supabase Project (free tier)                            │        |
|  │    Auth: email/password, magic link, invite-only         │        |
|  │    Database: watchlists table (user_id, ticker, order)   │        |
|  │    RLS: watchlists rows gated by auth.uid()              │        |
|  └─────────────────────────────────────────────────────────┘        |
+=====================================================================+
|  REASONING NETWORK (existing — unchanged)                            |
|                                                                      |
|  reasoning-engine (FastAPI + LangGraph)                             |
|    + NEW: JWT verification middleware (Supabase JWT secret)          |
|    + NEW: GET /reports (list by ticker)                              |
|    + NEW: GET /watchlist-data (batch entry quality for tickers)      |
|    EXISTING: POST /reports/generate, GET /reports/{id}, SSE stream  |
+=====================================================================+
|  INGESTION NETWORK (existing — unchanged)                            |
|                                                                      |
|  n8n ──────────► data-sidecar (existing, unchanged)                 |
|    + NEW: n8n document ingestion workflows                           |
|      ├── FOMC minutes auto-fetch → PDF → Qdrant upsert              |
|      ├── SBV reports manual trigger → PDF → Qdrant upsert           |
|      └── Earnings transcripts fetch → text → Qdrant upsert          |
+=====================================================================+
|  STORAGE LAYER (existing — add new Flyway migrations only)           |
|                                                                      |
|  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐        |
|  │   PostgreSQL    │  │    Neo4j     │  │     Qdrant      │        |
|  │                 │  │  (unchanged) │  │                  │        |
|  │ v3.0 adds:      │  │              │  │ v3.0 adds:       │        |
|  │  V8__dictionary │  │              │  │  expanded doc    │        |
|  │  (terminology   │  │              │  │  corpus (FOMC,   │        |
|  │   expansion)    │  │              │  │  SBV, earnings)  │        |
|  └─────────────────┘  └──────────────┘  └─────────────────┘        |
+=====================================================================+
```

---

## New vs Modified Components

### New Docker Service: `frontend`

One new service. Joins a new `frontend` network shared with nginx.

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  mem_limit: 512m
  restart: unless-stopped
  environment:
    NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: ${SUPABASE_PUBLISHABLE_KEY}
    # Note: no direct DB connection — all data via reasoning-engine API
  networks:
    - frontend
  profiles: ["frontend"]
  # No host port — nginx proxies to frontend:3000
```

**Why 512m mem_limit:** Next.js standalone output (output: 'standalone') is a stripped Node.js server. At single-user invite-only scale, 512MB is sufficient. The standalone build produces ~150MB images vs 1GB+ default.

### New Docker Service: `nginx`

Reverse proxy providing TLS termination, routing, and SSE buffer disabling. Joins both `frontend` and `reasoning` networks to proxy both services.

```yaml
nginx:
  image: nginx:alpine
  mem_limit: 64m
  restart: unless-stopped
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro   # certbot-managed certs
  ports:
    - "80:80"
    - "443:443"
  depends_on:
    - frontend
    - reasoning-engine
  networks:
    - frontend
    - reasoning
  profiles: ["frontend"]
```

**Critical nginx config — SSE requires proxy buffering disabled:**

```nginx
# /api/* → reasoning-engine (FastAPI)
location /api/ {
    proxy_pass http://reasoning-engine:8000/;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header Host $host;

    # SSE: disable buffering, enable long-lived connections
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_set_header X-Accel-Buffering no;
    chunked_transfer_encoding on;
}

# / → Next.js frontend
location / {
    proxy_pass http://frontend:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### New Docker Network: `frontend`

```yaml
networks:
  ingestion:
    driver: bridge    # existing
  reasoning:
    driver: bridge    # existing
  frontend:
    driver: bridge    # NEW — nginx + Next.js only
```

Nginx joins both `frontend` (to reach Next.js) and `reasoning` (to reach reasoning-engine). Next.js joins `frontend` only — it cannot reach storage services directly, which is the correct isolation.

### Modified Service: `reasoning-engine`

Two additions only — no structural changes:

1. **JWT verification middleware:** FastAPI dependency that validates the Supabase JWT on protected routes.
2. **New endpoints:** `GET /reports` (list reports by ticker) and `GET /watchlist-data` (batch entry quality summary for multiple tickers).

The `reasoning-engine` service joins the `reasoning` network. Nginx proxies `/api/*` to it. No host port change needed (8001 can be removed from docker-compose in production — nginx handles routing).

### New Flyway Migration: V8

```
db/migrations/
├── V1–V7 (existing)
└── V8__dictionary_expansion.sql  # NEW — financial terminology table
```

V8 adds a `financial_terms` table for the expanded Vietnamese financial dictionary (162 existing terms + v3.0 additions). This is optional — the dictionary may remain in a JSON/Python file if the reasoning engine only needs it at runtime.

### Supabase Cloud Project (external, not Docker)

Not a Docker service — Supabase Cloud is called from Next.js client only.

**What lives in Supabase Cloud:**
- Auth: email/password + magic link, invite-only via email allowlist
- `watchlists` table: `(id, user_id uuid REFERENCES auth.users, ticker text, position int, created_at)`
- RLS policy on `watchlists`: `user_id = auth.uid()`

**What does NOT live in Supabase:**
- Reports, OHLCV data, fundamentals, structure markers — all stay in the existing PostgreSQL service
- Document embeddings — stay in Qdrant
- Regime graph — stays in Neo4j

**Why Supabase Cloud (not self-hosted):** Self-hosted Supabase requires 7+ additional Docker containers (GoTrue, PostgREST, Realtime, Kong, etc.) consuming ~2–3GB RAM — which would exceed the VPS budget. The cloud free tier supports 50K MAU and 500MB database — vastly more than needed for an invite-only platform. Watchlist data is small (< 1MB for any realistic user count). Using Supabase Cloud for auth + watchlist only is the memory-efficient choice.

---

## Auth Flow: Supabase → Next.js → FastAPI

### Flow Diagram

```
User (Browser)
  │
  │  1. POST credentials (email + password OR magic link)
  ▼
Supabase Cloud (auth.supabase.co)
  │
  │  2. Returns: access_token (JWT), refresh_token
  │     JWT payload: { sub: user_id, email, role: "authenticated", exp, aud: "authenticated" }
  │     JWT signed with HS256 using project JWT_SECRET
  ▼
Next.js (browser client — @supabase/ssr + @supabase/supabase-js)
  │
  │  3. Stores session in HTTP-only cookies via @supabase/ssr middleware
  │     Middleware refreshes expired tokens on each request (getClaims())
  │
  │  4. For API calls: reads access_token from session
  │     Attaches as Authorization: Bearer <access_token> header
  ▼
nginx (proxy — passes Authorization header unchanged)
  │
  ▼
FastAPI (reasoning-engine — JWT verification dependency)
  │
  │  5. JWTBearer dependency extracts Bearer token from Authorization header
  │     Decodes with python-jose: jwt.decode(token, JWT_SECRET, algorithms=["HS256"],
  │                                           audience="authenticated")
  │     JWT_SECRET = Supabase project JWT secret (env var SUPABASE_JWT_SECRET)
  │     On success: returns decoded payload (user_id, email available to route)
  │     On failure: raises HTTPException 403
  │
  │  6. Protected route runs with verified user context
  ▼
PostgreSQL / Neo4j / Qdrant (no change — existing services)
```

### SSE Auth: Special Handling Required

The browser-native `EventSource` API cannot send custom headers. For the SSE stream endpoint (`GET /api/reports/stream/{id}`), use a library that supports headers:

```typescript
// Next.js client — use @microsoft/fetch-event-source (npm)
import { fetchEventSource } from '@microsoft/fetch-event-source';

fetchEventSource(`/api/reports/stream/${jobId}`, {
  headers: {
    Authorization: `Bearer ${session.access_token}`,
  },
  onmessage(event) {
    // handle step completion events
  },
});
```

**Why `@microsoft/fetch-event-source` over native EventSource:** It supports Authorization headers, automatic reconnection, and handles HTTP error codes correctly. The native EventSource spec does not support custom headers (GitHub issue #2177 — WHATWG, still unresolved as of 2026).

### FastAPI JWT Middleware Implementation

```python
# reasoning/app/auth.py (NEW — add to existing reasoning-engine service)
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

class JWTBearer(HTTPBearer):
    async def __call__(self, request: Request) -> str:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if not credentials or credentials.scheme != "Bearer":
            raise HTTPException(status_code=403, detail="Invalid auth scheme")
        try:
            payload = jwt.decode(
                credentials.credentials,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            return payload  # contains sub (user_id), email, exp
        except JWTError:
            raise HTTPException(status_code=403, detail="Invalid or expired token")

jwt_bearer = JWTBearer()

# Apply to routes:
# @router.post("/reports/generate", dependencies=[Depends(jwt_bearer)])
# @router.get("/reports/{report_id}", dependencies=[Depends(jwt_bearer)])
# @router.get("/reports/stream/{job_id}", dependencies=[Depends(jwt_bearer)])
```

**Environment variable to add to reasoning-engine:**

```yaml
# docker-compose.yml — reasoning-engine service
environment:
  SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET}   # NEW — from Supabase Settings > Auth
```

---

## Document Ingestion Architecture

Document ingestion uses the existing n8n + data-sidecar + Qdrant architecture. No new Docker services needed.

### Three Document Pipelines

| Pipeline | Source | Trigger | Current Status |
|----------|--------|---------|---------------|
| FOMC Minutes | federalreserve.gov (HTML/PDF) | n8n cron (monthly) | Partially automated (v2.0) |
| SBV Reports | sbv.gov.vn (PDF) | n8n manual trigger | Manual PDF curation |
| VN Earnings Transcripts | company IR pages / HOSE disclosures | n8n cron (quarterly) | Manual curation |

### Document Ingestion Flow (via existing n8n + data-sidecar)

```
n8n cron / manual trigger
  │
  │  1. HTTP node: fetch PDF URL or upload file
  ▼
n8n workflow (ingestion network)
  │
  │  2. Call data-sidecar: POST /documents/ingest
  │     Body: { source_type: "fomc|sbv|earnings", url: "...", ticker?: "..." }
  ▼
data-sidecar (FastAPI — ingestion network)
  │
  │  3. Download PDF → extract text (pypdf or pdfminer)
  │  4. Chunk text: 512 tokens, 50 token overlap
  │  5. Embed with FastEmbed BAAI/bge-small-en-v1.5 (384-dim — LOCKED)
  │  6. Upsert into Qdrant: macro_docs or earnings_docs collection
  │     Payload metadata: { source, date, ticker?, chunk_index, total_chunks }
  ▼
Qdrant (ingestion network)
  │
  └── Vector stored → available to reasoning-engine LlamaIndex retrieval
```

**New data-sidecar endpoint to add:** `POST /documents/ingest` — handles PDF download, text extraction, chunking, embedding, and Qdrant upsert. This keeps the embedding logic server-side (not in n8n) and reuses the existing FastEmbed model already loaded by the sidecar.

**Why not embed directly in n8n:** n8n's LangChain nodes use different embedding libraries that may produce different vector dimensions or normalizations than FastEmbed BAAI/bge-small-en-v1.5. Mixing embedding models for the same Qdrant collection causes incorrect similarity scores. The data-sidecar is the single embedding entrypoint — this constraint is locked.

---

## Component Boundaries (v3.0 Full Picture)

| Component | Responsibility | Reads From | Writes To | Does NOT |
|-----------|---------------|------------|-----------|----------|
| Next.js frontend | UI, auth session management, user watchlist CRUD | Supabase (auth + watchlist), reasoning-engine (reports API) | Supabase (watchlist rows via RLS) | Read PostgreSQL, Neo4j, Qdrant directly |
| Supabase Cloud | Auth tokens, user identity, watchlist data, RLS enforcement | — | Supabase DB (watchlists) | Know about reports, OHLCV, structure markers |
| nginx | TLS termination, routing, SSE buffering config | — | — | Business logic |
| reasoning-engine (modified) | Report generation, report retrieval, SSE streaming, JWT verification | PostgreSQL (reports, jobs, structure_markers, fundamentals), Neo4j, Qdrant | PostgreSQL (reports, report_jobs) | Write watchlists, authenticate users |
| n8n (modified — new workflows) | Document ingestion orchestration | External URLs (Fed, SBV, IR sites) | data-sidecar (via HTTP) | Embed documents directly |
| data-sidecar (modified — new endpoint) | Data ingestion + document embedding | External APIs, PDF downloads | PostgreSQL (ingestion data), Qdrant (embeddings) | Generate reports, verify auth |
| PostgreSQL | Structured data — reports, structure markers, fundamentals | — | — | Store watchlists or user profiles |
| Supabase DB | User identity, watchlists | — | — | Store analytical data, reports |

**Design decision: two separate databases.** Analytical data (reports, OHLCV, structure markers) stays in the VPS PostgreSQL. User data (watchlist, identity) lives in Supabase Cloud. This is the correct separation — it keeps the VPS PostgreSQL internal-only (no host port) while Supabase Cloud handles auth complexity.

---

## Data Flows

### Flow 1: Dashboard Load (Watchlist Cards)

```
Browser → Next.js page (/dashboard)
  │
  ├── [Supabase client] GET watchlist (tickers for user)
  │     supabase.from('watchlists').select('*').eq('user_id', user.id)
  │     Returns: [{ticker: 'VIC', position: 1}, {ticker: 'VHM', position: 2}, ...]
  │
  ├── [fetch with JWT] GET /api/watchlist-data?tickers=VIC,VHM,...
  │     reasoning-engine queries PostgreSQL:
  │       SELECT r.asset_id, r.entry_quality_score, r.generated_at,
  │              s.close, s.ma_10w, s.ma_20w
  │       FROM reports r JOIN structure_markers s ON r.asset_id = s.symbol
  │       WHERE r.asset_id IN (tickers) AND r.generated_at = (latest per ticker)
  │     Returns: [{ticker, entry_quality_tier, last_report_date, sparkline_data}, ...]
  │
  └── Render watchlist cards (tier badge + sparkline + last report date)
```

### Flow 2: Report View + TradingView Chart

```
Browser → Next.js page (/report/[id])
  │
  ├── [fetch with JWT] GET /api/reports/{id}
  │     Returns: full report JSON (regime, valuation, structure, entry_quality, markdown_vn, markdown_en)
  │
  ├── [fetch with JWT] GET /api/ohlcv/{ticker}?weeks=52
  │     reasoning-engine queries PostgreSQL:
  │       SELECT date, open, high, low, close, volume FROM ohlcv
  │       WHERE symbol = ticker ORDER BY date DESC LIMIT 52
  │     Returns: OHLCV array + MA series (from structure_markers)
  │
  ├── Render report markdown (Vietnamese primary)
  │
  └── [Client-side only — dynamic import] TradingView Lightweight Charts
        createChart(container, { width, height })
        chart.addCandlestickSeries() → setData(ohlcvArray)
        chart.addLineSeries() → setData(ma10w), addLineSeries() → setData(ma20w)
        No SSR — dynamic import with { ssr: false } required
```

### Flow 3: Generate Report with SSE Progress

```
Browser → Next.js "Generate Report" button click
  │
  ├── [fetch with JWT] POST /api/reports/generate { asset_id: "VIC" }
  │     FastAPI creates report_job, returns { job_id }
  │
  └── [@microsoft/fetch-event-source] GET /api/reports/stream/{job_id}
        Headers: { Authorization: Bearer <jwt> }
        Events received:
          data: {"node": "macro_regime", "status": "complete", "elapsed_ms": 12400}
          data: {"node": "valuation", "status": "complete", "elapsed_ms": 8200}
          data: {"node": "structure", "status": "complete", "elapsed_ms": 3100}
          data: {"node": "entry_quality", "status": "complete", "elapsed_ms": 7800}
          data: {"node": "compose_report", "status": "complete", "elapsed_ms": 18500}
          data: {"status": "complete", "report_id": "uuid"}
        → redirect to /report/{report_id}
```

### Flow 4: Document Ingestion (n8n → data-sidecar → Qdrant)

```
n8n cron (monthly, ingestion network)
  │
  ├── HTTP node: GET https://federalreserve.gov/.../minutes.pdf
  │
  ├── HTTP node: POST http://data-sidecar:8000/documents/ingest
  │     { source_type: "fomc", content_url: "...", document_date: "2026-01-29" }
  │
  └── data-sidecar (/documents/ingest handler):
        1. Download PDF → pypdf.PdfReader → extract text
        2. Chunk: RecursiveCharacterTextSplitter(chunk_size=512, overlap=50)
        3. Embed: FastEmbed BAAI/bge-small-en-v1.5 → 384-dim vectors
        4. Qdrant upsert: macro_docs collection
           Payload: { source: "fomc", date: "2026-01-29", chunk_index: N }
        5. Return: { chunks_upserted: 47, collection: "macro_docs" }
```

---

## Recommended Project Structure (v3.0 additions)

```
stratum/
├── docker-compose.yml          # Add: frontend service, nginx service, frontend network
├── frontend/                   # NEW — Next.js App Router service
│   ├── Dockerfile              # Multi-stage: builder (node:20-alpine) → runner (node:20-alpine)
│   ├── next.config.ts          # output: 'standalone' (required for Docker)
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx      # Root layout — Supabase session provider
│   │   │   ├── page.tsx        # / → redirect to /dashboard or /login
│   │   │   ├── login/
│   │   │   │   └── page.tsx    # Email/password login form (Supabase auth)
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx    # Watchlist cards — server component fetches data
│   │   │   └── report/
│   │   │       └── [id]/
│   │   │           └── page.tsx  # Report view — TradingView chart (client component)
│   │   ├── components/
│   │   │   ├── WatchlistCard.tsx        # Entry quality tier + sparkline + date
│   │   │   ├── ReportView.tsx           # Markdown report + expand/collapse sections
│   │   │   ├── TradingViewChart.tsx     # Client-only — dynamic import wrapper
│   │   │   └── GenerateReportButton.tsx # SSE progress display
│   │   ├── lib/
│   │   │   ├── supabase/
│   │   │   │   ├── client.ts    # createBrowserClient (client components)
│   │   │   │   └── server.ts    # createServerClient with cookies (server components)
│   │   │   └── api.ts           # fetch wrappers for reasoning-engine endpoints (w/ JWT)
│   │   └── middleware.ts        # @supabase/ssr middleware — token refresh + route protection
│   └── public/
│
├── nginx/                      # NEW — reverse proxy config
│   ├── nginx.conf              # Proxy rules: /api/* → reasoning-engine, / → frontend
│   └── ssl/                    # certbot-managed TLS certificates
│
├── reasoning/                  # MODIFIED — add auth middleware + 2 new endpoints
│   └── app/
│       ├── auth.py             # NEW — JWTBearer dependency (Supabase JWT verification)
│       └── routers/
│           └── reports.py      # MODIFIED — add JWT deps + GET /reports + GET /watchlist-data
│
├── sidecar/                    # MODIFIED — add document ingestion endpoint
│   └── app/
│       └── routers/
│           └── documents.py    # NEW — POST /documents/ingest (PDF → chunk → embed → Qdrant)
│
└── db/migrations/
    ├── V1–V7 (existing)
    └── V8__dictionary_expansion.sql   # NEW (optional — if dictionary moves to DB)
```

---

## Architectural Patterns

### Pattern 1: Supabase Cloud for Auth, VPS PostgreSQL for Analytical Data

**What:** Supabase Cloud handles only auth + watchlist (tiny user data). All analytical data (reports, OHLCV, fundamentals, structure markers) stays in the self-hosted PostgreSQL service.

**When to use:** Always — this is the v3.0 design. Do not store analytical data in Supabase.

**Why:** Self-hosted Supabase requires 7+ containers (~2–3GB RAM) — exceeds the VPS budget. Supabase Cloud free tier is adequate for invite-only scale. The JWT from Supabase Cloud is verifiable by FastAPI with just the JWT secret — no Supabase SDK needed on the backend.

**Trade-offs:** Two databases to manage. Watchlist data (in Supabase) and report data (in VPS PostgreSQL) are never in the same query. Dashboard must make two separate calls: Supabase for tickers, reasoning-engine for report summaries. This is acceptable at invite-only scale.

---

### Pattern 2: TradingView Lightweight Charts as Client-Only Dynamic Import

**What:** The TradingView chart component is wrapped in `next/dynamic` with `{ ssr: false }`. The chart is never rendered on the server.

**When to use:** Always — TradingView Lightweight Charts uses `window` and DOM APIs not available in Node.js SSR context.

**Why:** TradingView Lightweight Charts is a pure client-side canvas library. SSR rendering would throw `window is not defined`. Dynamic import with `{ ssr: false }` tells Next.js to only load and render the component in the browser.

```typescript
// app/report/[id]/page.tsx
import dynamic from 'next/dynamic';

const TradingViewChart = dynamic(
  () => import('@/components/TradingViewChart'),
  { ssr: false, loading: () => <div>Loading chart...</div> }
);
```

**Trade-offs:** Chart is not included in initial HTML — it renders after hydration. For a research report tool (not a trading terminal), this is acceptable. The report text renders immediately; the chart loads ~200ms later.

---

### Pattern 3: JWT Passed as Authorization Header, Not Cookie

**What:** Next.js reads the Supabase access_token from the client-side session and passes it as `Authorization: Bearer <token>` on all calls to the FastAPI reasoning-engine.

**When to use:** Always for reasoning-engine calls.

**Why:** The reasoning-engine is a separate Docker service — it cannot read the Next.js cookie domain. HTTP Authorization header is the correct pattern for service-to-service auth where the backend is not a Supabase-aware service.

**SSE exception:** Native `EventSource` cannot send headers. Use `@microsoft/fetch-event-source` which wraps `fetch` (supports headers) with SSE semantics. Token is still in the Authorization header — same pattern, different client library.

---

### Pattern 4: n8n Document Ingestion Calls data-sidecar (Not Qdrant Directly)

**What:** n8n sends PDFs or document URLs to the data-sidecar via HTTP. The data-sidecar handles download, extraction, chunking, embedding, and Qdrant upsert. n8n never talks to Qdrant directly.

**When to use:** Always for document ingestion.

**Why:** The FastEmbed BAAI/bge-small-en-v1.5 384-dim embedding model is locked — it must match the dimensions of existing Qdrant collections. The data-sidecar already has FastEmbed loaded. If n8n called Qdrant directly via the n8n Qdrant node, it would use n8n's built-in embedding models (typically OpenAI 1536-dim or different FastEmbed configurations) which would produce incompatible vectors. Centralizing embedding in data-sidecar enforces the dimension constraint.

---

### Pattern 5: nginx Joins Both `frontend` and `reasoning` Networks

**What:** The nginx service is the only component that bridges the `frontend` network (for Next.js) and the `reasoning` network (for FastAPI). Next.js cannot reach reasoning-engine directly.

**When to use:** Always — this is the network isolation model.

**Why:** Maintains Docker network isolation. Next.js fetches go to nginx (`/api/*`), nginx proxies to reasoning-engine. If Next.js tried to call reasoning-engine directly (port 8001 on host), it would bypass nginx and TLS. All traffic goes through nginx, which enforces HTTPS and passes the Authorization header through.

---

## Anti-Patterns

### Anti-Pattern 1: Storing Analytical Data in Supabase Cloud

**What people do:** Use Supabase as the single database for both user data (watchlists) and analytical data (reports, OHLCV, structure markers).

**Why it's wrong:** Supabase free tier is 500MB — VN30 reports alone will exceed this at scale. The existing PostgreSQL service is already populated with V1–V7 migrations and 9,000+ rows of structured data. Migrating analytical data to Supabase requires rewriting all SQLAlchemy queries in the reasoning-engine. At 8GB VPS, self-hosted Supabase is memory-prohibitive.

**Do this instead:** Supabase Cloud for auth + watchlist only (tiny data). VPS PostgreSQL for all analytical data. Two separate databases with a clear boundary: user identity lives in Supabase, analytical outputs live in PostgreSQL.

---

### Anti-Pattern 2: Self-Hosting Supabase on the Same VPS

**What people do:** Run the full Supabase stack (GoTrue, PostgREST, Realtime, Kong, Storage, Analytics, Meta) alongside the existing services.

**Why it's wrong:** Supabase requires 7+ containers consuming 2–3GB RAM minimum. The current services already use ~6.5GB committed limit. Adding Supabase self-hosted would push total committed memory to ~9.5GB on an 8GB VPS, relying entirely on swap — which degrades performance and risks OOM kills on Neo4j or reasoning-engine during LangGraph runs.

**Do this instead:** Supabase Cloud free tier. 50K MAU limit and 500MB storage are more than sufficient for an invite-only platform. The JWT verification in FastAPI only needs the JWT secret — it does not require a Supabase SDK or any Supabase services running on the VPS.

---

### Anti-Pattern 3: Using Native `EventSource` for Authenticated SSE

**What people do:** Use the browser's built-in `EventSource` API for the report generation progress stream and try to attach authentication via URL parameters (e.g., `?token=xxx`).

**Why it's wrong:** Tokens in URL query parameters appear in server logs, browser history, and nginx access logs — a security exposure. Native `EventSource` cannot send Authorization headers (WHATWG spec issue #2177 — unresolved). URL-parameter auth is not acceptable even for an invite-only internal tool.

**Do this instead:** Use `@microsoft/fetch-event-source` which implements SSE over `fetch`. Supports Authorization header. Token never appears in URL. The FastAPI SSE endpoint can use the same `JWTBearer` dependency as other protected routes.

---

### Anti-Pattern 4: Next.js Directly Querying PostgreSQL

**What people do:** Add a PostgreSQL connection string to the Next.js environment and use it in Server Components to query reports, OHLCV, or structure markers directly.

**Why it's wrong:** PostgreSQL is on the `reasoning` network only — intentionally without a host port. Adding a host port for Next.js to reach it exposes PostgreSQL to the network. Next.js would also need SQLAlchemy or pg libraries, bypassing the reasoning-engine's data access layer. This violates the architecture where reasoning-engine is the single gateway to analytical data.

**Do this instead:** Next.js calls reasoning-engine API endpoints for all analytical data. The reasoning-engine is the data gateway. Next.js only has direct connections to Supabase Cloud (for auth + watchlist).

---

### Anti-Pattern 5: Embedding Documents in n8n Workflows Directly

**What people do:** Use n8n's built-in LangChain Embeddings + Qdrant nodes to process documents, bypassing data-sidecar.

**Why it's wrong:** n8n's embedding nodes use whatever model is configured in the node UI — typically OpenAI text-embedding-ada-002 (1536-dim) or a different FastEmbed configuration. The existing Qdrant collections (`macro_docs`, `earnings_docs`) were initialized with 384-dim vectors (BAAI/bge-small-en-v1.5). Upserting 1536-dim vectors into a 384-dim collection will fail at the Qdrant API level or silently corrupt retrieval quality.

**Do this instead:** n8n sends document sources to `data-sidecar:8000/documents/ingest`. The data-sidecar is the only component that embeds into Qdrant, ensuring BAAI/bge-small-en-v1.5 384-dim is used consistently.

---

## VPS Memory Budget (v3.0)

```
Existing committed:
  postgres:         512m
  neo4j:            2g
  qdrant:           1g
  n8n:              512m
  data-sidecar:     512m
  reasoning-engine: 2g
  ──────────────────────
  Existing total:   6.5g committed

New in v3.0:
  frontend:         512m  (Next.js standalone — typical 150-300MB runtime)
  nginx:            64m   (nginx:alpine — trivial)
  ──────────────────────
  v3.0 additions:   576m

Total committed v3.0:  ~7g
VPS RAM:               8g
Headroom:              ~1g  (+ 4g swap for spike handling)
```

**Memory pressure analysis:**
- neo4j (2g) is the most memory-intensive service with 1.5GB JVM heap + pagecache. It runs at near-constant memory use (heap is pre-allocated).
- reasoning-engine (2g) spikes during LangGraph pipeline runs (~800MB–1.5GB) then falls back to ~300MB idle.
- frontend (512m) and nginx (64m) are low-footprint additions.
- The system stays within 8GB committed at all times. The 4GB swap handles concurrent spikes (e.g., report generation while browser has dashboard open).
- No service should have its mem_limit reduced to fit — existing limits were tuned against measured usage. Accept the ~7GB committed total.

---

## Build Order (v3.0 Phase Dependencies)

Dependencies are strict — each phase must be complete before the next begins.

```
Phase 1: JWT Middleware in reasoning-engine
  ├── Add auth.py with JWTBearer to reasoning-engine
  ├── Add SUPABASE_JWT_SECRET env var to docker-compose.yml
  ├── Apply JWT dependency to all existing /reports/* endpoints
  └── Test: curl with invalid token → 403; curl with valid Supabase token → 200
  WHY FIRST: Auth must be in place before any frontend code calls the API.
             Without this, the API is unprotected during development.

Phase 2: New reasoning-engine Endpoints
  ├── GET /reports (list reports by ticker, paginated)
  ├── GET /reports/{id}/ohlcv (OHLCV + MA series for chart)
  └── GET /watchlist-data?tickers=VIC,VHM (batch entry quality summary)
  WHY SECOND: Frontend cannot be built without the data contracts being defined.
              Implement endpoints with clear Pydantic response schemas first.

Phase 3: Supabase Cloud Project Setup
  ├── Create Supabase project (free tier)
  ├── Configure invite-only: Auth → Email → disable sign-ups, manually invite users
  ├── Create watchlists table + RLS policy (user_id = auth.uid())
  └── Note: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_JWT_SECRET for env
  WHY THIRD: Frontend needs Supabase env vars to bootstrap.
             JWT secret needed for Phase 1 (can proceed in parallel with Phase 1 if
             Supabase project is created simultaneously).

Phase 4: Next.js Frontend (Core Shell)
  ├── Scaffold Next.js 15 App Router with @supabase/ssr
  ├── Implement auth middleware.ts (route protection)
  ├── Build login page (email/password)
  ├── Build dashboard page (watchlist cards from Supabase + report summaries from API)
  └── Wire Dockerfile (multi-stage, standalone output)
  WHY FOURTH: Auth and API endpoints must exist before frontend can function.

Phase 5: TradingView Charts + Report View
  ├── Add GET /reports/{id}/ohlcv endpoint to reasoning-engine (if not in Phase 2)
  ├── Build TradingViewChart component (dynamic import, ssr: false)
  ├── Build report view page (/report/[id]) — markdown render + chart
  └── Build SSE progress display (GenerateReportButton with @microsoft/fetch-event-source)
  WHY FIFTH: Depends on Phase 4 frontend shell being in place.
             TradingView chart is self-contained client-side — can be built in parallel
             with Phase 4 once the page shell exists.

Phase 6: nginx + Docker Compose Integration
  ├── Write nginx.conf (proxy rules + SSE config)
  ├── Add frontend + nginx services to docker-compose.yml
  ├── Add frontend network
  ├── Set up TLS (certbot or manual cert)
  └── End-to-end test: full auth flow from browser to FastAPI through nginx
  WHY SIXTH: nginx is the final integration layer. All services must work independently
             before wiring nginx routing. TLS is the last step.

Phase 7: Document Ingestion Pipelines
  ├── Add POST /documents/ingest to data-sidecar
  ├── Build n8n FOMC minutes workflow (monthly cron + HTTP to data-sidecar)
  ├── Build n8n SBV reports workflow (manual trigger + PDF upload)
  └── Test: ingest 2 FOMC documents, verify Qdrant query returns them in LangGraph
  WHY SEVENTH: Document ingestion improves report quality but does not block the
               product frontend. The reasoning-engine already works with existing corpus.
               Ship the UI first, then expand the document corpus.

Phase 8: Vietnamese Dictionary Expansion
  ├── Audit current 162-term dictionary for gaps in v3.0 report coverage
  ├── Expand dictionary (target: 300+ terms for full financial domain coverage)
  └── Optionally: V8 Flyway migration to store dictionary in PostgreSQL
  WHY EIGHTH: Dictionary expansion is independent of all other phases.
              Can be done any time, but is the lowest-priority item.
```

---

## Integration Points: Existing Services

| Existing Service | v3.0 Integration | What Changes |
|-----------------|-----------------|--------------|
| `reasoning-engine` | JWT middleware added; 2–3 new read-only endpoints | auth.py (new), reports.py (modified) |
| `data-sidecar` | New `/documents/ingest` endpoint for document pipelines | documents.py (new router) |
| `postgres` | No change — existing schema sufficient for v3.0 UI | None |
| `neo4j` | No change | None |
| `qdrant` | New documents upserted via data-sidecar (same collections, same 384-dim) | Data only |
| `n8n` | New document ingestion workflows added | New workflow definitions |
| `flyway` | V8 migration (optional — only if dictionary moves to DB) | V8__dictionary_expansion.sql |

---

## Sources

- [Supabase Auth Server-Side Next.js — Official Docs](https://supabase.com/docs/guides/auth/server-side/nextjs) — HIGH confidence (official)
- [Use Supabase Auth with Next.js — Official Quickstart](https://supabase.com/docs/guides/auth/quickstarts/nextjs) — HIGH confidence (official)
- [Supabase Self-Hosting Auth Config](https://supabase.com/docs/guides/self-hosting/auth/config) — HIGH confidence (official — confirms self-hosted complexity)
- [FastAPI + Supabase Auth JWT Verification (DEV Community)](https://dev.to/j0/integrating-fastapi-with-supabase-auth-780) — MEDIUM confidence (community, verified against official JWT spec)
- [Implementing Supabase Auth with Next.js and FastAPI (ByteGoblin)](https://bytegoblin.io/blog/implementing-supabase-authentication-with-next-js-and-fastapi.mdx) — MEDIUM confidence (community, pattern verified)
- [TradingView Lightweight Charts — Official Library](https://tradingview.github.io/lightweight-charts/docs) — HIGH confidence (official)
- [TradingView Lightweight Charts SSR Issue #543](https://github.com/tradingview/lightweight-charts/issues/543) — HIGH confidence (official repo — confirms SSR workaround requirement)
- [TradingView Charting Library Examples — Next.js](https://github.com/tradingview/charting-library-examples) — HIGH confidence (official TradingView)
- [Next.js Self-Hosting Guide](https://nextjs.org/docs/app/guides/self-hosting) — HIGH confidence (official)
- [Next.js Docker Standalone Output (Next.js Deploying Docs)](https://nextjs.org/docs/app/getting-started/deploying) — HIGH confidence (official)
- [n8n + Qdrant Workflow Template — Process Documents with Gemini](https://n8n.io/workflows/7882-process-documents-and-build-semantic-search-with-openai-gemini-and-qdrant/) — MEDIUM confidence (official n8n templates)
- [Qdrant n8n Integration Tutorial](https://qdrant.tech/documentation/tutorials-build-essentials/qdrant-n8n/) — HIGH confidence (official Qdrant)
- [EventSource Custom Headers — WHATWG Issue #2177](https://github.com/whatwg/html/issues/2177) — HIGH confidence (official spec issue — confirms EventSource cannot send headers)
- [Next.js + Nginx Reverse Proxy with Docker](https://www.slingacademy.com/article/how-to-set-up-next-js-with-docker-compose-and-nginx/) — MEDIUM confidence (community, verified against nginx official docs)
- [Supabase Pricing — Free Tier 50K MAU, 500MB DB](https://supabase.com/pricing) — HIGH confidence (official)

---

*Architecture research for: Stratum v3.0 — Product Frontend and User Experience*
*Researched: 2026-03-17*
