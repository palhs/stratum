# Pitfalls Research

**Domain:** Adding Next.js frontend, Supabase auth, TradingView charts, and automated document ingestion to an existing FastAPI + PostgreSQL + Docker system on a self-hosted 8GB VPS
**Researched:** 2026-03-17
**Confidence:** MEDIUM-HIGH (SSE proxy, TradingView SSR, Supabase service key exposure verified via official docs and multiple community sources; VPS memory validated via Docker official docs; PDF ingestion pitfalls from community post-mortems)

---

## Critical Pitfalls

### Pitfall 1: SSE Proxy Buffering Silently Breaks Progress Streaming

**What goes wrong:**
The existing FastAPI SSE endpoint works in direct testing. Once Next.js is added in front of it — either via `next.config.js` rewrites or an API route proxy — SSE events are buffered and delivered as a single dump at the end of the pipeline instead of streaming progressively. This breaks the "Generate Report" progress display entirely. The failure mode is silent: no errors, progress just never updates until it all arrives at once.

**Why it happens:**
Two layers of buffering collude. First, Nginx (which almost certainly sits in front on a self-hosted VPS) buffers proxied responses by default. Second, when SSE is proxied through a Next.js API route, Next.js buffers the response body until the handler function resolves — the App Router `Response` object does not flush partial writes. Both must be explicitly disabled.

**How to avoid:**
Do not proxy SSE through a Next.js API route. Use `next.config.js` rewrites to forward `/api/stream/*` directly to the FastAPI origin at the network level — rewrites bypass Next.js response buffering entirely. On the Nginx side, add these directives to the location block serving FastAPI:
```
proxy_buffering off;
proxy_cache off;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_read_timeout 86400s;
add_header X-Accel-Buffering no;
```
FastAPI must set `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no` on the SSE response.

**Warning signs:**
- Progress bar never updates during generation, then jumps to 100% at the end
- SSE works when hitting FastAPI directly on its port but not through the domain
- `curl -N` to the FastAPI port streams correctly; browser does not

**Phase to address:**
Phase 1 (Next.js scaffold + FastAPI integration). Verify SSE streaming before building any UI that depends on it.

---

### Pitfall 2: Supabase Auth Creates a Second PostgreSQL Database You Cannot Fully Avoid

**What goes wrong:**
Supabase Auth stores user identity in a managed PostgreSQL instance Supabase controls (`auth.users` table). The project's existing PostgreSQL (the operational DB) stores watchlists, reports, and all analytical data. These are two separate databases. Any query joining a user's identity to their watchlist requires either duplicating user IDs across both databases or making two separate calls and joining in application code. Developers discover this late when they try to write a single SQL query like "get all watchlist tickers for user X" and realize `auth.users` is unreachable from the app's PostgreSQL.

**Why it happens:**
Supabase's pitch as a "Postgres backend" implies one database. In reality, the managed Supabase instance is separate from any existing PostgreSQL. You cannot run JOINs across them. Row Level Security policies on the Supabase-hosted database are powerful, but the app database has no awareness of them.

**How to avoid:**
Establish a clear data ownership rule: **Supabase hosts only auth identity** (`user_id`, email, session). The app's PostgreSQL stores all product data (watchlists, reports, preferences) with a `user_id` UUID column as the foreign-key anchor that references Supabase's `auth.users.id`. FastAPI validates the Supabase JWT on every request (extracting `sub` as `user_id`) and enforces data isolation in SQL queries using parameterized `WHERE user_id = $1` clauses. Never rely on Supabase RLS to protect the app database — it cannot.

**Warning signs:**
- A query to "get user's watchlist" hits both Supabase client and PostgreSQL in the same handler
- `watchlists` table is being created in the Supabase-hosted database (wrong location)
- Cross-database JOIN attempt fails with "relation does not exist"

**Phase to address:**
Phase 2 (Supabase auth integration). Define the data ownership contract and migration schema before writing any auth-dependent feature.

---

### Pitfall 3: Supabase JWT Validation on FastAPI — Incorrect Audience Claim Silently Passes or Fails

**What goes wrong:**
FastAPI validates the Supabase-issued JWT using the project's JWT secret. Without specifying `audience="authenticated"` in the decode call, PyJWT either accepts tokens that should be rejected (if audience validation is skipped) or rejects all valid user tokens (if it defaults to a different audience expectation). Both modes are silent bugs: the endpoint either lets unauthenticated traffic through or blocks all users.

**Why it happens:**
Supabase JWTs use `"aud": "authenticated"` for user sessions. PyJWT's `decode()` does not enforce audience by default unless `audience=` is explicitly passed. Tutorials often omit this parameter, leading to insecure configurations that pass testing because the dev environment also uses unchecked tokens.

**How to avoid:**
```python
import jwt
payload = jwt.decode(
    token,
    supabase_jwt_secret,
    algorithms=["HS256"],
    audience="authenticated",
    options={"verify_exp": True},
)
```
Use a FastAPI `Depends()` dependency that wraps this decode, raises `HTTPException(401)` on any failure, and extracts `payload["sub"]` as the `user_id`. Apply the dependency to every route that touches user data. Test with a token from a different Supabase project (should be rejected) and with an expired token (should be rejected).

**Warning signs:**
- Auth "works" in dev but every token is accepted regardless of origin
- 403 errors for valid users with no server-side error logs
- JWT secret is in plaintext in `docker-compose.yml` instead of a secret manager

**Phase to address:**
Phase 2 (Supabase auth integration). Auth middleware must be the first thing built in that phase, before any user-data endpoints are added.

---

### Pitfall 4: TradingView Lightweight Charts Crashes During Next.js SSR Build

**What goes wrong:**
`lightweight-charts` uses `document`, `window`, and `HTMLCanvasElement` — all browser-only globals. When Next.js pre-renders a page that imports the chart component, the build crashes with `ReferenceError: window is not defined` or `document is not defined`. This happens at build time (`next build`), not just at runtime, so it blocks deployments.

**Why it happens:**
Next.js App Router renders server components on the server during build. Any import that touches browser globals at module evaluation time (not inside a function) will crash the Node.js process. `lightweight-charts` creates a canvas element on import.

**How to avoid:**
Wrap the chart component with `next/dynamic` and `ssr: false`:
```typescript
// components/PriceChart.tsx — must be client component
"use client";
import { createChart } from "lightweight-charts";

// app/page.tsx — import dynamically
const PriceChart = dynamic(() => import("@/components/PriceChart"), {
  ssr: false,
  loading: () => <div className="chart-skeleton" />,
});
```
The `"use client"` directive alone is not sufficient — the import must also be dynamic with `ssr: false` because App Router can still attempt to evaluate the module on the server.

**Warning signs:**
- `next build` fails with `window is not defined`
- Chart works in `next dev` (which does not pre-render) but fails in production build
- Importing `lightweight-charts` at the top level of any non-dynamic component

**Phase to address:**
Phase 1 (Next.js scaffold) or Phase 3 (TradingView chart integration). The dynamic import pattern must be established before the first chart component is written.

---

### Pitfall 5: Next.js Service Added to Docker Compose Blows the 8GB VPS Memory Budget

**What goes wrong:**
The current 8 Docker services already consume most of the 8GB VPS. Adding a Next.js container (Node.js, ~300-500MB baseline) plus a Supabase Auth connector puts the system over the edge. Peak memory during `next build` (which runs inside the container during startup or CI) can spike to 1.5-2GB. Neo4j's default heap configuration alone can balloon to 1GB if not capped. The OOM killer silently terminates whichever container it deems most expendable — often `reasoning-engine` or `postgres` — with no visible error in application logs.

**Why it happens:**
Docker containers have no memory limits by default. Each service is configured in isolation without accounting for the aggregate. Next.js standby memory is around 200-300MB but spikes significantly during initial compilation. Node.js's V8 heap defaults to 512MB-1GB. On a 8GB system, the combined baseline of 8 services plus a new Next.js service approaches the physical limit before any actual workload runs.

**How to avoid:**
Audit all `mem_limit` values in `docker-compose.yml` before adding the Next.js service:
1. Run `docker stats --no-stream` on the live system to measure actual usage per service
2. Assign hard `mem_limit` to every service, including Next.js (`512m` is a reasonable starting cap)
3. Build the Next.js container externally (CI or local) and ship a pre-built image — avoid running `next build` inside the container at startup
4. Set `NODE_OPTIONS=--max-old-space-size=256` in the Next.js service environment to cap V8 heap

Reserve at least 1GB headroom for kernel and OS operations.

**Warning signs:**
- `docker stats` shows any service frequently near its memory ceiling
- Services restart unexpectedly with no error logs (OOM kill leaves no application trace)
- `dmesg | grep -i oom` shows killed processes
- Neo4j or Qdrant consuming more memory than expected due to default heap settings

**Phase to address:**
Phase 1 (Next.js scaffold + Docker integration). Before the first `docker compose up`, audit memory budget. Do not ship a Docker service without a `mem_limit`.

---

### Pitfall 6: Supabase Service Role Key Exposed in Client-Side Code

**What goes wrong:**
The Supabase service role key bypasses all Row Level Security and has full database access. If it is included in any environment variable prefixed `NEXT_PUBLIC_` or otherwise shipped in the JavaScript bundle, it is exposed to every browser that loads the application. An attacker with this key can read, write, or delete any data in the Supabase-managed database.

**Why it happens:**
Next.js environment variable naming is the trap: `NEXT_PUBLIC_` prefixed variables are intentionally injected into the client bundle. Developers copy-paste Supabase client initialization code from tutorials that do not distinguish between the `anon` key (safe to expose) and the `service_role` key (must never leave the server).

**How to avoid:**
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` — safe in client code
- `SUPABASE_SERVICE_ROLE_KEY` (no `NEXT_PUBLIC_` prefix) — server-only, never in client components
- The service role client is only instantiated in Next.js Route Handlers (server-side) or server components where admin operations are needed
- The FastAPI backend uses the service role key only through its own environment (never returned to the client)

**Warning signs:**
- `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` appears anywhere in the codebase
- Service role client initialized in a client component or `"use client"` file
- Browser devtools Network tab shows the service role key in request headers from the frontend

**Phase to address:**
Phase 2 (Supabase auth). This constraint must be established as a code review rule before any Supabase client code is written.

---

### Pitfall 7: SSE Client Connections Leak on Page Navigation

**What goes wrong:**
When a user starts a report generation (which opens an SSE connection to FastAPI) and then navigates away before completion, the SSE connection remains open on both client and server. The FastAPI pipeline continues running and streaming events to a closed consumer. Over multiple navigations, leaked connections accumulate. On a single-user self-hosted instance this is a minor resource issue, but the FastAPI pipeline's background task continues consuming LLM API budget (Gemini API spend) for a report nobody will see.

**Why it happens:**
`EventSource` or `fetch` with a `ReadableStream` requires explicit client-side cleanup. React's `useEffect` cleanup function must close the connection on unmount, but this is frequently missed. The server side also needs to handle the client disconnect signal (`request.is_disconnected()` in FastAPI) to abort the background pipeline early.

**How to avoid:**
Client-side cleanup in the React hook:
```typescript
useEffect(() => {
  const controller = new AbortController();
  // ... open SSE connection with controller.signal
  return () => {
    controller.abort(); // triggers cleanup on unmount
  };
}, [jobId]);
```
Server-side early abort in FastAPI's SSE generator: check `await request.is_disconnected()` inside the event loop and break out of the generator, which cancels the LangGraph pipeline if it has not reached the LLM call yet.

**Warning signs:**
- Gemini API spend logs show completed pipeline calls with no corresponding stored report
- FastAPI logs show SSE generator still producing events after the browser disconnected
- `docker stats` shows `reasoning-engine` CPU active with no active UI session

**Phase to address:**
Phase 3 (SSE progress display for report generation). Build disconnect handling into the SSE integration from the start.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| No `mem_limit` on Next.js service | Faster setup | OOM kills other services without warning | Never — set limits before first deploy |
| Proxy SSE through Next.js API route | Simpler URL structure | Silent buffering breaks progress display | Never — use `next.config.js` rewrites instead |
| Store watchlists in Supabase-managed DB | One less database to think about | Cannot JOIN with app reports; Supabase subscription limits apply | Never — keep app data in app PostgreSQL |
| Import `lightweight-charts` in a server component | Fewer dynamic imports | Build-time crash; blocks all deployments | Never — always dynamic with `ssr: false` |
| Skip `audience` check in JWT decode | Simpler validation code | Tokens from any Supabase project accepted | Never |
| Use `NEXT_PUBLIC_` prefix for service role key | Easier client access | Full database access exposed to browser | Never |
| Run `next build` inside Docker container on startup | No CI setup required | Memory spike on container start can OOM the host | Only in dev — pre-build for production |
| Skip SSE cleanup on component unmount | Less boilerplate | Gemini API spend on abandoned pipeline runs | Only acceptable in single-user trusted environment with budget alerts active |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Next.js rewrites → FastAPI SSE | Routing SSE through an API route handler | Use `next.config.js` rewrites to bypass Next.js response buffering |
| Nginx → FastAPI SSE | Default `proxy_buffering on` | Set `proxy_buffering off` and `X-Accel-Buffering: no` on SSE routes |
| Supabase JWT → FastAPI | Omitting `audience="authenticated"` in PyJWT decode | Always pass `audience="authenticated"` explicitly |
| Supabase + App PostgreSQL | Attempting to JOIN across both databases | Sync only `user_id` (UUID) to app DB; enforce isolation in SQL `WHERE` clauses |
| TradingView + Next.js | Importing `lightweight-charts` in a server component | Wrap in `dynamic(..., { ssr: false })` with `"use client"` |
| n8n + PDF documents | Loading entire PDF binary into n8n workflow memory | Stream or chunk PDFs; use HTTP Request node with file-to-disk mode |
| Docker + Next.js | No `mem_limit` on the Next.js service | Set `mem_limit: 512m` and `NODE_OPTIONS=--max-old-space-size=256` |
| FastAPI CORS + Supabase Auth | Allowing `*` origin with `allow_credentials=True` | CORS does not allow wildcard origin with credentials; list explicit origins |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| TradingView re-renders on every React state change | Chart flickers or resets zoom on any UI update | Keep chart instance in a `useRef`, update data via chart API methods — not re-renders | First time any parent state updates while chart is visible |
| Loading full report JSON for dashboard card | Dashboard feels slow; mobile unusable | Create a `report_summaries` view or materialized table with only card-level fields (ticker, tier, timestamp) | When reports table exceeds ~50 rows with large JSON payloads |
| Spawning a fresh LangGraph pipeline per "Generate" click | Duplicate in-flight pipelines on double-click | Disable the "Generate" button immediately on click; check for an active `RUNNING` job before starting | Any user who double-clicks |
| SSE connection held for entire pipeline duration on mobile | Browser kills connection on screen lock | Send heartbeat `data: ping\n\n` every 15s; handle reconnection in `EventSource` `onerror` | Any mobile session that locks the screen during generation |
| FastEmbed model loaded fresh per request | First request after cold start takes 5-10s | Load FastEmbed model once at FastAPI startup via `lifespan` event handler | Any cold start after container restart |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` in env | Full database bypass; any user can read/write all data | Never prefix service role key with `NEXT_PUBLIC_`; server-only env var |
| Supabase `anon` key with no RLS on Supabase-managed tables | Direct API access to user data without auth check | Enable RLS on all Supabase-managed tables; `anon` key must have only public-read policies |
| FastAPI routes missing JWT dependency | Unauthenticated access to reports and watchlists | Apply `Depends(verify_supabase_jwt)` to every route that returns user-specific data |
| CORS `allow_origins=["*"]` with `allow_credentials=True` | FastAPI will raise an error or browsers will reject the response | FastAPI `CORSMiddleware` explicitly disallows wildcard with credentials; list exact Next.js origin |
| n8n admin UI exposed without authentication | Workflow configurations (including API keys stored in credentials) accessible to anyone | n8n must not be on a public port; use Nginx basic auth or restrict to localhost + VPN |
| JWT secret in `docker-compose.yml` | Secret committed to git repository | Use Docker secrets or `.env` file excluded from git; never hardcode in compose file |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Vietnamese number formatting differs between server and client | Hydration mismatch error; numbers display differently in dev vs production | Format numbers and dates only on the client using `useEffect` or in client components with a fixed locale (`"vi-VN"`) |
| No loading skeleton for report generation | User unsure if button worked; double-clicks | Disable button on click, show inline spinner, open SSE progress bar immediately |
| Report history shows raw ISO timestamps | Vietnamese retail investors see `2026-03-17T04:22:11Z`, not `17/03/2026` | Use a locale-aware date formatter (date-fns with vi locale) throughout; establish a single formatting utility |
| TradingView chart has no loading state | Canvas renders blank while data fetches; user thinks app is broken | Render chart container immediately with a skeleton; pass data to chart only when available |
| SSE disconnects with no user feedback | User stares at a frozen progress bar after network hiccup | Handle `EventSource` `onerror` event; show "Connection lost — retry?" with a manual refresh button |
| Watchlist add/remove has no optimistic update | UI lags 300-500ms on each change; feels unresponsive | Apply optimistic updates in React state immediately; revert on API error |

---

## "Looks Done But Isn't" Checklist

- [ ] **SSE streaming:** Works in `next dev` with direct FastAPI access — verify it also works through the Nginx reverse proxy at the production domain with `curl -N https://yourdomain.com/api/stream/...`
- [ ] **Auth middleware:** FastAPI endpoint returns 200 without auth header in dev — verify every user-data route returns 401 without a valid Supabase JWT
- [ ] **Memory limits:** `docker compose up` succeeds — verify `docker inspect <service> | grep Memory` shows non-zero limits for all services
- [ ] **TradingView chart:** Chart renders in `next dev` — verify `next build` completes without `window is not defined` errors
- [ ] **Supabase JWT expiry:** Login works on first try — verify that an expired JWT returns 401 (not 200) from FastAPI
- [ ] **PDF ingestion idempotency:** n8n workflow runs once successfully — verify re-running it does not create duplicate Qdrant vectors for the same document
- [ ] **CORS with credentials:** API calls work from `localhost:3000` — verify they also work from the production domain (different origin, credentials required)
- [ ] **Service role key server-only:** App functions — verify service role key does not appear in browser devtools under Network > Headers or Application > Local Storage
- [ ] **Vietnamese number formatting:** Numbers display correctly in Chrome — verify there is no React hydration mismatch warning in the browser console

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| SSE buffering discovered in production | MEDIUM | Add Nginx directives; update `next.config.js` rewrites; no code changes to FastAPI or frontend components |
| Watchlist data in wrong database (Supabase-managed) | HIGH | Migrate data: export from Supabase, import to app PostgreSQL, rewrite all watchlist queries; Flyway migration required |
| Service role key committed to git | HIGH | Rotate the Supabase service role key immediately (Supabase dashboard); remove from git history with `git filter-repo`; audit any logs for exploitation |
| OOM kill took down PostgreSQL | MEDIUM | Restart PostgreSQL container; check for checkpoint corruption (`pg_dump` to verify integrity); add `mem_limit` to all services before restarting |
| TradingView SSR crash blocks deployments | LOW | Wrap chart component in `dynamic(..., { ssr: false })`; fix is a 2-line change |
| Duplicate Qdrant vectors from PDF re-ingestion | MEDIUM | Query Qdrant for documents with matching source URL/hash; delete duplicates via Qdrant REST API; add idempotency check (document hash) to n8n workflow |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| SSE proxy buffering | Phase 1: Next.js scaffold + FastAPI integration | `curl -N` to production domain streams events progressively |
| Next.js service OOM on VPS | Phase 1: Docker integration | `docker stats` shows all services under limit; no unexpected restarts after 24h |
| TradingView SSR crash | Phase 1 (establish pattern) or Phase 3 (chart build) | `next build` completes without browser global errors |
| Supabase dual-database design | Phase 2: Supabase auth | Watchlist schema has `user_id UUID` in app PostgreSQL only; no watchlist table in Supabase |
| JWT validation (audience, expiry) | Phase 2: Supabase auth | Expired and cross-project tokens return 401 from FastAPI |
| Service role key exposure | Phase 2: Supabase auth | Key absent from browser devtools; absent from `NEXT_PUBLIC_` env vars |
| CORS with credentials | Phase 1: FastAPI API design | API calls from production domain succeed; wildcard origin removed |
| SSE client connection leak | Phase 3: Report generation UI | Navigating away during generation stops Gemini API spend; FastAPI logs show disconnection |
| Vietnamese number hydration mismatch | Phase 3 or Phase 4: UI | No hydration mismatch warnings in browser console on any data-display page |
| PDF re-ingestion duplicates | Phase 5: Document ingestion | Running the n8n workflow twice produces no duplicate Qdrant points |
| n8n memory exhaustion on large PDFs | Phase 5: Document ingestion | n8n workflow completes with a 50MB PDF; `docker stats` for n8n stays under limit |

---

## Sources

- [Next.js SSE don't work in API routes — GitHub Discussion #48427](https://github.com/vercel/next.js/discussions/48427)
- [Surviving SSE Behind Nginx Proxy Manager — Medium](https://medium.com/@dsherwin/surviving-sse-behind-nginx-proxy-manager-npm-a-real-world-deep-dive-69c5a6e8b8e5)
- [How to Configure SSE Through Nginx — OneUptime Blog](https://oneuptime.com/blog/post/2025-12-16-server-sent-events-nginx/view)
- [Supabase Auth Architecture — Official Docs](https://supabase.com/docs/guides/auth/architecture)
- [Validating a Supabase JWT with Python and FastAPI — DEV Community](https://dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf)
- [Implementing Supabase Auth with Next.js and FastAPI — Medium](https://medium.com/@ojasskapre/implementing-supabase-authentication-with-next-js-and-fastapi-5656881f449b)
- [Performing admin tasks server-side with service_role secret — Supabase Docs](https://supabase.com/docs/guides/troubleshooting/performing-administration-tasks-on-the-server-side-with-the-servicerole-secret-BYM4Fa)
- [API Key Exposure in Supabase — VibeAppScanner](https://vibeappscanner.com/vulnerability-in/api-key-exposure-supabase-apps)
- [DOCS: How to use Lightweight Charts in SSR context — GitHub Issue #543](https://github.com/tradingview/lightweight-charts/issues/543)
- [Stop "Window Is Not Defined" in Next.js (2025) — DEV Community](https://dev.to/devin-rosario/stop-window-is-not-defined-in-nextjs-2025-394j)
- [Docker Resource Limits — Official Docs](https://docs.docker.com/engine/containers/resource_constraints/)
- [n8n Memory-Related Errors — Official Docs](https://docs.n8n.io/hosting/scaling/memory-errors/)
- [RLS Performance and Best Practices — Supabase Docs](https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv)
- [toLocaleString() hydration mismatch — Next.js Discussion #79397](https://github.com/vercel/next.js/discussions/79397)
- [Mastering CORS in FastAPI and Next.js — Medium](https://medium.com/@vaibhavtiwari.945/mastering-cors-configuring-cross-origin-sharing-in-fastapi-and-next-js-28c61272084b)
- [n8n HTTP requests should have default timeout — GitHub Issue #7081](https://github.com/n8n-io/n8n/issues/7081)

---
*Pitfalls research for: v3.0 — Next.js frontend + Supabase auth + TradingView charts + document ingestion on existing FastAPI + PostgreSQL + Docker*
*Researched: 2026-03-17*
