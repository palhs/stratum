# Stack Research

**Domain:** Investment advisor product frontend — Next.js dashboard, Supabase auth, TradingView charts, document ingestion, dictionary expansion
**Researched:** 2026-03-17
**Confidence:** HIGH (versions verified against npm, official docs, and GitHub releases)

---

## Scope: v3.0 Additions Only

This document covers only what is NEW for v3.0. The existing stack is validated and operational:

| Already Operational (DO NOT re-add) | Version |
|--------------------------------------|---------|
| Docker Compose (8 services) | — |
| PostgreSQL (Flyway V1-V7) | `postgres:16-alpine` |
| Neo4j | `neo4j:5.26.21` |
| Qdrant | `qdrant/qdrant:v1.15.3` |
| FastAPI reasoning-engine | `fastapi>=0.115.0` |
| LangGraph 7-node pipeline | `langgraph==1.0.10` |
| httpx (Python) | `>=0.27.0` |
| SQLAlchemy Core | `>=2.0.0` |
| Pydantic v2 | `>=2.0.0` |
| pymupdf / pdfplumber | — (not yet installed — see Document Ingestion below) |

---

## Recommended Stack

### Core Technologies (Frontend)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `next` | 15.3.x (latest 15.x) | React framework for the frontend service | App Router is stable and the standard for new Next.js projects. SSR is needed for the report view (SEO-irrelevant here, but SSR enables Server Components for direct Supabase data fetching without an extra API layer). v16 is in development; building on 15.x avoids canary instability. `create-next-app` scaffolds with TypeScript + App Router by default. |
| `react` + `react-dom` | 19.x (pulled by Next 15.3) | UI rendering | Next.js 15 ships with React 19 as the default. React 19 stabilizes `useOptimistic` and improves concurrent features. Do not pin to React 18 — it introduces unnecessary version conflicts. |
| `typescript` | 5.x | Type safety across the frontend | Already expected for a finance UI. Next.js 15.5 added stable `typedRoutes` — compile-time type checking of all `<Link href>` values. Worth enabling in `next.config.ts`. |
| `tailwindcss` | 4.x | Utility-first CSS | Tailwind v4 is the current release (January 2025). No `tailwind.config.ts` file required — configuration lives in `globals.css`. Next.js 15 + shadcn/ui have documented Tailwind v4 setup guides. Use v4, not v3 — v3 is in maintenance mode. |
| `shadcn/ui` | latest CLI | Component library | Not a versioned npm package — it's a CLI that copies components into your repo. Built on Radix UI primitives + Tailwind. Correct choice for a dashboard: accessible, composable, no runtime overhead from unused components. Use `npx shadcn@latest init` with the New York style and CSS variables. |

### Core Technologies (Auth)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `@supabase/supabase-js` | 2.99.2 | Supabase JS client (auth + DB queries) | v2 is the current stable SDK. Provides `supabase.auth.admin.inviteUserByEmail()` — the correct mechanism for invite-only access. Disable public signups in Supabase project settings (Authentication → General → User Signups toggle off) and issue all accounts via admin invite. |
| `@supabase/ssr` | latest | Cookie-based auth for Next.js App Router | Required package when using Supabase auth with Next.js. Server Components cannot set cookies — this package provides `createServerClient()` and `createBrowserClient()` helpers that manage cookie-based session refresh. Without it, sessions expire silently in Server Components. The Supabase official docs mandate this package for App Router projects. |

### Core Technologies (Charting)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `lightweight-charts` | 5.1.0 | OHLCV candlestick + MA overlay chart | TradingView's open-source charting library. 45KB, canvas-rendered, handles large OHLCV datasets without frame drops. v5.1.0 adds data conflation (automatic performance optimization when zoomed out) — relevant for multi-year VN stock history. This is a canvas-based library: it must be wrapped in a `'use client'` component and loaded with `next/dynamic` + `{ ssr: false }` to avoid `window is not defined` errors during SSR. |

### Supporting Libraries (Frontend)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@tanstack/react-query` | 5.90.x | Server state, caching, background refetch | For all data-fetching from the FastAPI backend (report lists, watchlist, pipeline status). v5 is stable and 20% smaller than v4. Eliminates manual loading/error state boilerplate. Use `useQuery` for reports and `useMutation` for watchlist changes. Required — do not use plain `fetch` in components. |
| `zustand` | 5.0.x | Minimal client-side state | For UI state only: SSE progress events, open/collapsed report sections, watchlist optimistic updates. v5 uses `useSyncExternalStore` natively (React 18+). Do not use for server data — that belongs in React Query. |
| `@microsoft/fetch-event-source` | 2.0.1 | SSE client that supports POST + headers | The native `EventSource` API does not support POST requests or custom headers, making it incompatible with the existing FastAPI SSE endpoint (which requires auth headers). This package wraps `fetch` with SSE semantics. **Note:** Last published ~3 years ago, but stable and widely deployed. No maintained alternative with equivalent API. |
| `recharts` | 2.x | Sparkline mini-charts on watchlist cards | Lightweight SVG charts for the dashboard watchlist cards (7-day price sparkline). TradingView Lightweight Charts is overkill for tiny sparklines — Recharts provides a `<LineChart>` with minimal config. Recharts requires `"use client"` directive. |

### Supporting Libraries (Python — Document Ingestion)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pymupdf4llm` | latest (`pip install -U pymupdf4llm`) | PDF → Markdown extraction for ingestion pipeline | Converts PDFs (Fed minutes, SBV reports, earnings) to clean Markdown that maps directly to the existing Qdrant document schema. `pymupdf4llm.to_markdown("doc.pdf")` handles multi-column layouts and tables. Chosen over `pdfplumber` because: outputs Markdown (matching Qdrant chunk format), faster (PyMuPDF C bindings), and has LlamaIndex integration. Install with `pip install -U pymupdf4llm` — auto-installs `PyMuPDF` dependency. |
| `httpx` | `>=0.27.0` (already installed) | Async PDF download from Fed website, SBV, etc. | Already in the sidecar `requirements.txt`. Use `httpx.AsyncClient` with streaming for PDF downloads. No new library needed — reuse existing. |
| `apscheduler` | 3.11.x | Scheduled ingestion job triggering inside FastAPI | For triggering weekly/monthly document ingestion jobs (FOMC schedule, SBV publication dates). Use `AsyncIOScheduler` with `CronTrigger` inside FastAPI's `lifespan` context manager. **Alternative considered: n8n cron.** Prefer APScheduler here because document ingestion is tightly coupled to the Python embedding pipeline (FastEmbed → Qdrant) — keeping it in Python avoids an n8n → FastAPI HTTP roundtrip for each document. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `eslint` + `eslint.config.mjs` | Frontend linting | Next.js 15.5 deprecated `next lint` — create-next-app now generates explicit ESLint config. Do not use `next lint` in scripts; call `eslint` directly. |
| `@types/node`, `@types/react`, `@types/react-dom` | TypeScript definitions | Generated by `create-next-app` — ensure these are in `devDependencies`. |
| `next` standalone output mode | Minimizes Docker image size for self-hosted VPS | Set `output: 'standalone'` in `next.config.ts`. The standalone build includes only the files needed to run the server, reducing image size significantly. Required for VPS deployment. |

---

## Installation

New `frontend/` service in the repository:

```bash
# Scaffold (run once)
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir

# Core auth
npm install @supabase/supabase-js @supabase/ssr

# Charting
npm install lightweight-charts recharts

# Data fetching + state
npm install @tanstack/react-query zustand

# SSE client (for FastAPI pipeline progress)
npm install @microsoft/fetch-event-source

# shadcn/ui (CLI — installs components on demand)
npx shadcn@latest init
npx shadcn@latest add card button badge skeleton table
```

New Python packages for document ingestion (add to `sidecar/requirements.txt` or a new `ingestion/requirements.txt`):

```bash
pip install -U pymupdf4llm
pip install apscheduler>=3.11.0
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Next.js 15 App Router | Next.js Pages Router | Never for new projects — Pages Router is legacy. App Router is the default since Next.js 13 and the only one receiving new features. |
| `@supabase/ssr` + cookie auth | JWT in localStorage | Never for production auth — localStorage tokens are vulnerable to XSS. Cookie-based auth with httpOnly cookies is the secure default. |
| Supabase cloud (free tier) | Self-hosted Supabase via Docker | Self-hosted Supabase requires ~15 Docker containers and significant operational overhead. The cloud free tier (50,000 MAU, 500MB DB) is sufficient for an invite-only product with <20 users. Accept the managed-service dependency for auth — the free tier cost is zero. |
| `lightweight-charts` (v5, direct) | `react-lightweight-charts` wrapper | The community wrapper packages are unmaintained or lag behind LWC versions. Use the official library directly in a `'use client'` component with `useRef` + `useEffect` — the pattern is 30 lines and requires no wrapper. |
| `recharts` for sparklines | Victory, Nivo, Chart.js | Recharts is the lightest option with native React integration. Victory is heavier. Nivo requires D3. Chart.js (canvas) requires `'use client'` + `dynamic` like LWC — more setup for identical output. |
| `pymupdf4llm` | `pdfplumber` | Use `pdfplumber` only if you need precise character-level coordinates or table extraction with cell boundaries. For LLM/RAG ingestion where Markdown output is the goal, `pymupdf4llm` is faster and produces cleaner output. |
| `pymupdf4llm` | `pypdf` | `pypdf` is pure-Python with no C deps (good for Lambda). On a self-hosted VPS, `pymupdf4llm`'s C bindings are an asset (speed). pypdf also produces spacing artifacts on complex financial PDFs (multi-column Fed minutes). |
| `apscheduler` in FastAPI | n8n cron → FastAPI HTTP | n8n cron is correct for data ingestion (vnstock OHLCV, FRED) because those workflows are self-contained shell scripts. Document ingestion requires Python embedding (FastEmbed → Qdrant) — keeping that in Python avoids a second HTTP hop and lets the scheduler share the same FastEmbed model instance already loaded in memory. |
| `@tanstack/react-query` | SWR | React Query v5 has better DevTools, mutation handling, and background refetch logic. SWR is simpler but lacks the `useMutation` + optimistic update patterns needed for watchlist management. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `@supabase/auth-helpers-nextjs` | Deprecated — replaced by `@supabase/ssr`. The auth-helpers package has known issues with App Router cookie refresh and is no longer maintained. Official Supabase docs redirect to `@supabase/ssr`. | `@supabase/ssr` |
| `EventSource` (native browser API) | Does not support POST requests or custom Authorization headers. The FastAPI SSE endpoint requires auth headers. `EventSource` silently falls back to a GET-only request. | `@microsoft/fetch-event-source` |
| Redux / Redux Toolkit | Vastly over-engineered for this use case. Stratum frontend has two concerns: server data (reports, watchlist) and UI state (open sections, SSE progress). React Query handles server data; Zustand handles UI state. Redux adds boilerplate with no architectural benefit. | `@tanstack/react-query` + `zustand` |
| `next-auth` / Auth.js | Adds a separate auth layer that duplicates Supabase's auth infrastructure. Supabase auth is already chosen (PROJECT.md). Mixing Auth.js with Supabase creates two session systems. | `@supabase/supabase-js` + `@supabase/ssr` |
| TradingView Advanced Charting Library | Not open-source — requires a commercial license and a private npm registry token. The Lightweight Charts library (open-source, Apache 2.0) provides exactly what v3.0 needs: candlestick series, line series (MAs), crosshair, time scale zoom. | `lightweight-charts` (open-source) |
| Vercel deployment | VPS constraint in PROJECT.md. Vercel's free tier has 100GB bandwidth limit and no persistent filesystem. The reasoning engine and PostgreSQL run on the VPS — frontend must be co-located to avoid cross-origin SSE complexity and latency. | Docker container on the existing VPS, proxied via Nginx |
| `tailwindcss` v3 | Maintenance mode. v4 is current with CSS-first configuration, no config file required, and better performance. Shadcn/ui now ships with v4 support as default. | `tailwindcss` v4 |
| Tremor (component library) | Tremor wraps Recharts and adds another abstraction. For this project, direct Recharts usage for sparklines + shadcn/ui for layout components is sufficient. Tremor's opinionated dashboard components would require fighting the library to match Stratum's research-report aesthetic. | `recharts` for charts + `shadcn/ui` for components |

---

## Stack Patterns by Variant

**For the TradingView chart component (OHLCV + moving averages):**
- Create a `'use client'` React component
- Use `next/dynamic` with `{ ssr: false }` to import it in any Server Component page
- Initialize chart inside `useEffect` with `chartContainerRef`
- Destroy chart in cleanup: `chart.remove()`
- Because: `lightweight-charts` accesses `window` and `document` on import — SSR will throw `window is not defined` without `{ ssr: false }`

**For the Supabase invite-only pattern:**
- Disable "Allow new users to sign up" in Supabase Dashboard → Authentication → General
- Issue invites via `supabase.auth.admin.inviteUserByEmail(email)` from a server-side admin route
- Protect all pages with middleware: `supabase.auth.getUser()` (not `getSession()`) in `middleware.ts`
- Because: `getSession()` reads from the cookie without server-side validation — it can be spoofed. `getUser()` validates the JWT against Supabase servers on every request.

**For FastAPI SSE consumption in Next.js:**
- Use `@microsoft/fetch-event-source` in a `'use client'` component
- Pass the Supabase JWT from `supabase.auth.getSession()` as `Authorization: Bearer <token>` header
- Pipe SSE events into Zustand store for progress display
- Because: FastAPI SSE endpoint already exists and streams pipeline progress. The frontend needs to consume it with auth headers — not possible with native `EventSource`.

**For document ingestion scheduling:**
- Add `AsyncIOScheduler` to the existing FastAPI reasoning-engine `lifespan` context
- Schedule FOMC ingestion jobs against the Fed calendar (8 meetings/year) using `CronTrigger`
- SBV reports: weekly poll of the SBV website with `httpx` + hash-based deduplication
- Earnings PDFs: triggered manually or by a date-based cron aligned with VN reporting season
- Because: All ingestion ultimately calls FastEmbed (loaded in-process) and writes to Qdrant — co-location avoids serializing the embedding pipeline over HTTP.

---

## Docker Compose Integration

Add a new `frontend` service to `docker-compose.yml`:

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
      NEXT_PUBLIC_API_URL: http://reasoning:8000   # internal Docker network
    depends_on:
      - reasoning
    networks:
      - reasoning
    ports:
      - "3000:3000"
    profiles: ["frontend"]
```

Key integration points:
- `output: 'standalone'` in `next.config.ts` is mandatory — reduces Docker image from ~1GB to ~150MB by including only the files needed to run the server.
- `NEXT_PUBLIC_API_URL` points to the `reasoning` service on the internal Docker network. Server Components call it directly (no CORS). Client Components must go through a Next.js API route that proxies the FastAPI call with the session token attached.
- Nginx must be configured with `proxy_buffering off` for SSE routes — buffering breaks streaming responses. Add to your Nginx server block: `location /api/sse { proxy_buffering off; proxy_pass http://frontend:3000; }`
- Supabase is cloud-hosted (free tier) — no Docker service needed for auth. The `SUPABASE_URL` and `SUPABASE_ANON_KEY` are environment variables pointing to the Supabase project.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `next@15.3.x` | React 19.x, TypeScript 5.x, Tailwind v4 | `create-next-app` pulls compatible React version automatically. Do not manually pin React 18 — causes peer dep conflicts. |
| `lightweight-charts@5.1.0` | Vanilla JS, React (manual wrapper) | No official React package. Build a 30-line wrapper with `useRef` + `useEffect`. Requires `dynamic` + `{ ssr: false }` in Next.js. |
| `@supabase/supabase-js@2.99.x` | `@supabase/ssr` latest | Both must be in sync — `@supabase/ssr` depends on `@supabase/supabase-js`. Install together: `npm install @supabase/supabase-js @supabase/ssr`. |
| `@tanstack/react-query@5.90.x` | React 19 | v5 supports React 18 and 19. Import from `@tanstack/react-query`, not the deprecated `react-query` package. |
| `tailwindcss@4.x` | `shadcn/ui` latest CLI | shadcn/ui now generates Tailwind v4-compatible CSS variable configs. Run `npx shadcn@latest init` after Tailwind v4 is installed — do not use the v3 init flow. |
| `pymupdf4llm` | `PyMuPDF>=1.24.0`, Python >=3.9 | `pip install -U pymupdf4llm` auto-installs the correct `PyMuPDF` version. No manual PyMuPDF pin needed. |
| `apscheduler@3.11.x` | Python >=3.8, asyncio | Use `AsyncIOScheduler` (not `BackgroundScheduler`) inside an async FastAPI app. Start/stop inside the `lifespan` context manager. |

---

## Sources

- [Next.js 15.5 blog](https://nextjs.org/blog/next-15-5) — Confirmed current stable release (published August 18, 2025). Turbopack builds beta, stable Node.js middleware, typed routes stable. HIGH confidence.
- [next-changelog.vercel.app](https://next-changelog.vercel.app/) — Version history confirming 15.x is latest stable, 16 in development. HIGH confidence.
- [lightweight-charts GitHub releases](https://github.com/tradingview/lightweight-charts/releases) — v5.1.0 released December 16, 2024. Latest confirmed. HIGH confidence.
- [lightweight-charts React tutorial](https://tradingview.github.io/lightweight-charts/tutorials/react/simple) — Official guide confirms `useRef` + `useEffect` pattern; no official React wrapper package. HIGH confidence.
- [@supabase/supabase-js npm](https://www.npmjs.com/package/@supabase/supabase-js) — v2.99.2, published March 17, 2026. HIGH confidence.
- [Supabase SSR docs](https://supabase.com/docs/guides/auth/server-side/nextjs) — `@supabase/ssr` confirmed as mandatory package for Next.js App Router. `@supabase/auth-helpers-nextjs` deprecated. HIGH confidence.
- [Supabase inviteUserByEmail API docs](https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail) — Admin invite pattern confirmed. HIGH confidence.
- [Supabase invite-only discussion #4296](https://github.com/orgs/supabase/discussions/4296) — Confirmed: disable public signups + admin invite is the standard invite-only pattern. MEDIUM confidence (community discussion, consistent with official docs).
- [@tanstack/react-query npm](https://www.npmjs.com/package/@tanstack/react-query) — v5.90.21, published ~1 month ago. HIGH confidence.
- [Zustand GitHub](https://github.com/pmndrs/zustand) — v5.0.x current, uses `useSyncExternalStore`. HIGH confidence.
- [pymupdf4llm PyPI](https://pypi.org/project/pymupdf4llm/) — Active, `pip install -U pymupdf4llm` is the install command. HIGH confidence.
- [APScheduler docs](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — v3.11.x, `AsyncIOScheduler` for asyncio apps. HIGH confidence.
- [@microsoft/fetch-event-source npm](https://www.npmjs.com/package/@microsoft/fetch-event-source) — v2.0.1, stable. Note: last published ~5 years ago but widely used (1.1M downloads/week). MEDIUM confidence (unmaintained but no known issues or maintained alternatives).
- [Tailwind CSS v4 install for Next.js](https://tailwindcss.com/docs/guides/nextjs) — v4 is current release, CSS-first config, compatible with Next.js 15 and shadcn/ui. HIGH confidence.
- [shadcn/ui Next.js install](https://ui.shadcn.com/docs/installation/next) — CLI-based, Tailwind v4 supported. HIGH confidence.

---

*Stack research for: Stratum v3.0 Product Frontend — new capabilities only*
*Researched: 2026-03-17*
