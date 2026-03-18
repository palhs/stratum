# Phase 12: Next.js Core Shell and Dashboard - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Scaffold a Next.js Docker service with login page and dashboard. Dashboard displays the user's watchlist as a responsive grid of entry quality cards — each showing tier badge, 52-week sparkline, and last report date. No report generation (Phase 13), no full report view (Phase 14), no nginx wiring (Phase 15).

</domain>

<decisions>
## Implementation Decisions

### Dashboard card layout
- Responsive grid: 3 columns on desktop, 2 on tablet, 1 on mobile
- Cards reflow naturally — max 30 tickers in watchlist, all visible without pagination
- Cards are clickable — clicking navigates to `/reports/{symbol}` (placeholder page until Phase 14)

### Card visual hierarchy
- Tier badge is the dominant/hero element — large, color-coded, centered on the card
- Visual order top-to-bottom: symbol + company name → tier badge (large) → sparkline → last report date
- Tier badge color scheme: muted/professional tones (teal for Favorable, slate for Neutral, warm amber for Cautious, muted rose for Avoid) — not traffic-light green/red

### Sparkline rendering
- Simple inline SVG polyline from 52 weekly close prices — zero dependencies
- No axes, labels, tooltips, or interactivity — purely static visual indicator
- Color: green if price up year-over-year, red if down
- Full interactive chart is deferred to Phase 14 (TradingView Lightweight Charts)

### Empty state
- "Your watchlist is empty" message with prompt to add tickers
- Show 3-5 suggested popular tickers as quick-add buttons (VNM, FPT, HPG, GLD, MWG)
- Quick-add calls PUT /watchlist to add the ticker

### Loading state
- Skeleton cards with shimmer animation in the same responsive grid layout
- User immediately sees the dashboard structure before data loads

### Error state
- Toast notification (non-blocking) for API errors
- First load failure: centered error message with Retry button
- Refresh failure: show stale cached data + toast "Refresh failed"

### Login page
- Claude's Discretion — minimal login form with email/password, Supabase auth integration, redirect to dashboard on success, redirect unauthenticated users to login

### Claude's Discretion
- CSS framework / component library choice (Tailwind, shadcn/ui, etc.)
- Next.js app router structure and route organization
- Auth middleware implementation (Next.js middleware vs route guards)
- Toast library choice
- Skeleton shimmer implementation approach
- Docker configuration details (multi-stage build, standalone output)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API contracts
- `.planning/phases/10-backend-api-contracts-and-jwt-middleware/10-CONTEXT.md` — OHLCV endpoint shape (`{ time, open, high, low, close, volume, ma50, ma200 }`), report history contract, JWT auth scope
- `.planning/phases/11-supabase-auth-and-per-user-watchlist/11-CONTEXT.md` — Watchlist API (GET/PUT /watchlist), JWT RS256/JWKS verification, default watchlist seeding, ticker universe

### Infrastructure
- `docker-compose.yml` — Existing service definitions, network topology (reasoning network), port mappings (reasoning-engine on 8001:8000)

### Requirements
- `.planning/REQUIREMENTS.md` §Dashboard — DASH-01 through DASH-05, INFR-01

### State decisions
- `.planning/STATE.md` §Accumulated Context — TradingView `dynamic({ ssr: false })`, SSE via next.config.ts rewrites, Supabase service role key naming convention

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing frontend code — this is a greenfield Next.js scaffold
- `reasoning/app/auth.py`: RS256/JWKS JWT verification — frontend must send same Supabase JWT
- `reasoning/app/routers/reports.py`: Endpoints the dashboard will consume (OHLCV, report history)
- `reasoning/app/routers/watchlist.py`: GET/PUT /watchlist endpoints for watchlist data

### Established Patterns
- Backend: FastAPI on port 8000 (mapped to host 8001), SQLAlchemy Core, Pydantic v2 schemas
- Docker: `mem_limit` on all services, health checks, profile-based service grouping
- Auth: Supabase JWT with `audience="authenticated"`, `sub` claim = user UUID

### Integration Points
- `docker-compose.yml`: New `frontend` service needed, joins `reasoning` network, depends on reasoning-engine health
- Reasoning-engine API at `http://reasoning-engine:8000` (internal Docker network)
- Supabase Cloud for auth (external URL from env vars)
- Host port for frontend: TBD (likely 3000:3000)

</code_context>

<specifics>
## Specific Ideas

- Tier badge as hero element mirrors the product's core value — "what's the entry quality?" should be the first thing a user sees on each card
- Muted/professional color scheme (teal/slate/amber/rose) gives a research-report aesthetic rather than a trading terminal feel — aligns with the "research report, not trading tool" constraint
- SVG sparkline with zero dependencies keeps the 512MB Docker memory budget realistic for a Next.js service rendering up to 30 cards

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-next-js-core-shell-and-dashboard*
*Context gathered: 2026-03-18*
