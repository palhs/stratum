# Phase 12: Next.js Core Shell and Dashboard - Research

**Researched:** 2026-03-18
**Domain:** Next.js 15 App Router, Supabase SSR Auth, Tailwind CSS v4, shadcn/ui, Docker standalone output
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dashboard card layout**
- Responsive grid: 3 columns on desktop, 2 on tablet, 1 on mobile
- Cards reflow naturally — max 30 tickers in watchlist, all visible without pagination
- Cards are clickable — clicking navigates to `/reports/{symbol}` (placeholder page until Phase 14)

**Card visual hierarchy**
- Tier badge is the dominant/hero element — large, color-coded, centered on the card
- Visual order top-to-bottom: symbol + company name → tier badge (large) → sparkline → last report date
- Tier badge color scheme: muted/professional tones (teal for Favorable, slate for Neutral, warm amber for Cautious, muted rose for Avoid) — not traffic-light green/red

**Sparkline rendering**
- Simple inline SVG polyline from 52 weekly close prices — zero dependencies
- No axes, labels, tooltips, or interactivity — purely static visual indicator
- Color: green if price up year-over-year, red if down
- Full interactive chart is deferred to Phase 14 (TradingView Lightweight Charts)

**Empty state**
- "Your watchlist is empty" message with prompt to add tickers
- Show 3-5 suggested popular tickers as quick-add buttons (VNM, FPT, HPG, GLD, MWG)
- Quick-add calls PUT /watchlist to add the ticker

**Loading state**
- Skeleton cards with shimmer animation in the same responsive grid layout
- User immediately sees the dashboard structure before data loads

**Error state**
- Toast notification (non-blocking) for API errors
- First load failure: centered error message with Retry button
- Refresh failure: show stale cached data + toast "Refresh failed"

### Claude's Discretion
- CSS framework / component library choice (Tailwind, shadcn/ui, etc.)
- Next.js app router structure and route organization
- Auth middleware implementation (Next.js middleware vs route guards)
- Toast library choice
- Skeleton shimmer implementation approach
- Docker configuration details (multi-stage build, standalone output)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFR-01 | Next.js frontend runs as Docker service with mem_limit on VPS | Standalone output + multi-stage Dockerfile reduces runtime to ~150-200MB; node:20-alpine + `output: 'standalone'` pattern confirmed viable for 512MB limit |
| DASH-01 | User sees watchlist as cards on dashboard landing page | GET /watchlist returns `{ tickers: [{ symbol, name, asset_type }] }`; Supabase JWT from cookie passed as Bearer in server component fetch; responsive grid via Tailwind |
| DASH-02 | Each card shows entry quality tier badge (color-coded Favorable/Neutral/Cautious/Avoid) | Tier comes from GET /reports/by-ticker/{symbol} first result; shadcn/ui Badge component with custom color mapping; muted palette via Tailwind CSS variables |
| DASH-03 | Each card shows sparkline price chart (52-week weekly close) | GET /tickers/{symbol}/ohlcv returns 52 weekly data points; pure inline SVG `<polyline>` with normalized coordinates — zero external dependency |
| DASH-04 | Each card shows last report date | Returned in report history response as `generated_at`; formatted with `Intl.DateTimeFormat` or `date-fns` |
| DASH-05 | Dashboard shows appropriate empty/loading/error states | Skeleton via `animate-pulse` Tailwind classes; Sonner for toast; React `useState`/`useEffect` in client component for fetch lifecycle |
</phase_requirements>

---

## Summary

Phase 12 scaffolds a greenfield Next.js service — there is no existing frontend code. The core challenges are: (1) wiring Supabase cookie-based auth so the JWT flows correctly from browser through Next.js middleware to the FastAPI backend; (2) implementing the dashboard as a client component that orchestrates three parallel API calls (watchlist, OHLCV, report history) with proper loading/error/empty states; (3) containerizing within a 512MB `mem_limit` using `output: 'standalone'` and a three-stage Dockerfile.

The recommended stack is **Next.js 15 + Tailwind CSS v4 + shadcn/ui (canary, Tailwind v4 flavor) + Sonner for toasts + @supabase/ssr for auth**. shadcn/ui is particularly well-suited because it copies component source code directly into the project — no runtime dependency, no bundle weight beyond what you use, and full control over the tier badge color scheme the user specified. The sparkline is hand-rolled as a pure SVG `<polyline>` per the locked decision — this is the correct call given the 512MB memory budget and zero-interaction requirement.

The primary risk is the parallel data-fetching pattern for dashboard cards: each card needs both the watchlist entry AND its OHLCV data AND its last report date, creating potential for N+1 fetch patterns if not batched. The OHLCV endpoint is per-symbol, so the dashboard must fan out up to 30 calls. This should be handled with `Promise.all` in a single client-side fetch pass after the watchlist loads.

**Primary recommendation:** Use Next.js 15 App Router with `output: 'standalone'`, Tailwind CSS v4, shadcn/ui (canary), Sonner, and @supabase/ssr. Structure the dashboard as a Client Component with a single loading state gate, fetching watchlist first then fanning out OHLCV + report history in parallel per ticker.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 15.x | App framework, routing, SSR | App Router + standalone Docker output; cookies() async API needed for Supabase SSR |
| react | 19.x | UI rendering | Peer dep of Next 15 |
| @supabase/supabase-js | 2.x | Supabase client | Base client |
| @supabase/ssr | 0.x | SSR cookie-based auth | Official package replacing deprecated auth-helpers; createServerClient + createBrowserClient |
| tailwindcss | 4.x | Utility CSS | v4 auto-scans content — no config file needed; @import "tailwindcss" in globals.css |
| @tailwindcss/postcss | 4.x | PostCSS integration | Required for Tailwind v4 in Next.js |
| shadcn/ui (canary) | canary | Component primitives | Tailwind v4 + React 19 support; components copied into project — no runtime bundle cost |
| sonner | 1.x | Toast notifications | shadcn/ui default toast; minimal API, works with App Router Server Components |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| date-fns | 3.x | Date formatting | Format `generated_at` timestamp on cards (`formatDistanceToNow` or `format`) |
| clsx + tailwind-merge | 2.x | Conditional class merging | Bundled with shadcn/ui `cn()` utility — use for tier badge dynamic classes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind v4 + shadcn/ui canary | Tailwind v3 + shadcn/ui stable | v3 is mature but v4 is now the official recommendation; canary shadcn has full v4 support |
| Sonner | react-hot-toast | Both work; Sonner is shadcn/ui official and supports Server Actions natively |
| Pure SVG sparkline | react-sparklines or recharts | Zero-dep is the locked decision; also keeps Docker image lean |
| @supabase/ssr | @supabase/auth-helpers | auth-helpers is deprecated — ssr is the current package |

**Installation:**
```bash
# Bootstrap project
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir

# Supabase
npm install @supabase/supabase-js @supabase/ssr

# Install Tailwind v4 (replaces v3 if create-next-app installs v3)
npm install tailwindcss @tailwindcss/postcss postcss

# shadcn/ui (canary for Tailwind v4 support)
npx shadcn@canary init

# Supporting
npm install sonner date-fns
```

---

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── Dockerfile                    # Multi-stage standalone build
├── next.config.ts                # output: 'standalone', rewrites for SSE (Phase 13+)
├── postcss.config.mjs            # @tailwindcss/postcss plugin
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   └── login/
│   │   │       └── page.tsx      # Login form — public route
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx        # Auth guard — redirects if no session
│   │   │   └── page.tsx          # Dashboard page (Server Component shell)
│   │   ├── reports/
│   │   │   └── [symbol]/
│   │   │       └── page.tsx      # Placeholder until Phase 14
│   │   ├── globals.css           # @import "tailwindcss" + CSS variables
│   │   └── layout.tsx            # Root layout, Toaster provider
│   ├── components/
│   │   ├── ui/                   # shadcn/ui copied components (Badge, Card, Skeleton, Button)
│   │   ├── dashboard/
│   │   │   ├── DashboardClient.tsx   # "use client" — owns fetch lifecycle
│   │   │   ├── WatchlistGrid.tsx     # Responsive grid wrapper
│   │   │   ├── TickerCard.tsx        # Individual card: badge + sparkline + date
│   │   │   ├── TickerCardSkeleton.tsx # Shimmer loading placeholder
│   │   │   ├── TierBadge.tsx         # Color-coded entry quality badge
│   │   │   ├── Sparkline.tsx         # Pure SVG polyline component
│   │   │   └── EmptyState.tsx        # Empty watchlist + quick-add buttons
│   │   └── login/
│   │       └── LoginForm.tsx     # "use client" — email/password form
│   ├── lib/
│   │   ├── supabase/
│   │   │   ├── server.ts         # createServerClient (Server Components, middleware)
│   │   │   └── client.ts         # createBrowserClient (Client Components)
│   │   ├── api.ts                # Typed fetch functions: getWatchlist, getOhlcv, getReportHistory
│   │   └── utils.ts              # cn() utility from shadcn
│   └── middleware.ts             # Token refresh + route protection
```

### Pattern 1: Supabase SSR Middleware (Route Protection)
**What:** Middleware refreshes the Supabase auth token on every request and redirects unauthenticated users away from protected routes.
**When to use:** Every protected route. The middleware runs before Server Components can render.

```typescript
// Source: https://supabase.com/docs/guides/auth/server-side/creating-a-client
// src/middleware.ts
import { createServerClient } from '@supabase/ssr'
import { NextRequest, NextResponse } from 'next/server'

export async function middleware(request: NextRequest) {
  const response = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() { return request.cookies.getAll() },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // CRITICAL: use getClaims() not getSession() in middleware
  const { data: { user } } = await supabase.auth.getClaims()

  const isAuthRoute = request.nextUrl.pathname.startsWith('/login')
  const isDashboardRoute = request.nextUrl.pathname === '/' ||
    request.nextUrl.pathname.startsWith('/reports')

  if (!user && isDashboardRoute) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
  if (user && isAuthRoute) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

### Pattern 2: Server Component Auth + JWT Extraction
**What:** Server Components retrieve the Supabase session and extract the JWT to pass as Bearer token to the FastAPI backend.
**When to use:** Any Server Component that calls the reasoning-engine API.

```typescript
// Source: Supabase SSR docs — server client pattern
// src/lib/supabase/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() { return cookieStore.getAll() },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options))
        },
      },
    }
  )
}
```

```typescript
// Usage in a Server Component to get the JWT for API calls
// src/app/(dashboard)/layout.tsx
import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

export default async function DashboardLayout({ children }) {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) redirect('/login')

  return (
    <div>
      {/* Pass access_token to Client Component via props */}
      {children}
    </div>
  )
}
```

### Pattern 3: Client Component Dashboard — Parallel Fetch
**What:** The dashboard Client Component fetches the watchlist first, then fans out per-ticker OHLCV + report history fetches in parallel using `Promise.all`.
**When to use:** Dashboard page where each card needs data from two different endpoints.

```typescript
// src/components/dashboard/DashboardClient.tsx
'use client'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

type TickerData = {
  symbol: string
  name: string
  asset_type: string
  ohlcv: OhlcvPoint[] | null
  lastReport: { tier: string; generated_at: string } | null
}

export function DashboardClient({ accessToken }: { accessToken: string }) {
  const [tickers, setTickers] = useState<TickerData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const watchlist = await getWatchlist(accessToken)
        if (watchlist.tickers.length === 0) {
          setTickers([])
          return
        }
        // Fan out: fetch OHLCV + report history for all tickers in parallel
        const enriched = await Promise.all(
          watchlist.tickers.map(async (t) => {
            const [ohlcv, report] = await Promise.all([
              getOhlcv(t.symbol, accessToken).catch(() => null),
              getLastReport(t.symbol, accessToken).catch(() => null),
            ])
            return { ...t, ohlcv, lastReport: report }
          })
        )
        setTickers(enriched)
      } catch (err) {
        setError('Failed to load dashboard')
        toast.error('Failed to load dashboard')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [accessToken])

  if (loading) return <WatchlistGridSkeleton />
  if (error) return <ErrorState message={error} onRetry={() => { setError(null); setLoading(true) }} />
  if (tickers.length === 0) return <EmptyState />
  return <WatchlistGrid tickers={tickers} />
}
```

### Pattern 4: Pure SVG Sparkline Component
**What:** Inline SVG polyline that maps 52 weekly close prices to normalized viewport coordinates.
**When to use:** Each ticker card. Zero external dependency, renders server-side.

```typescript
// src/components/dashboard/Sparkline.tsx
// Source: https://dev.to/gnykka/how-to-create-a-sparkline-component-in-react-4e1
type SparklineProps = {
  data: number[]           // weekly close prices, oldest first
  width?: number
  height?: number
}

export function Sparkline({ data, width = 120, height = 40 }: SparklineProps) {
  if (data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1  // avoid division by zero for flat prices

  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * width
      const y = height - ((value - min) / range) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const isUp = data[data.length - 1] >= data[0]
  const color = isUp ? '#16a34a' : '#dc2626'  // green-600 / red-600

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
```

### Pattern 5: Tier Badge with Muted Color Scheme
**What:** shadcn/ui Badge with color overrides matching the muted research-report palette.
**When to use:** Every ticker card — this is the hero element.

```typescript
// src/components/dashboard/TierBadge.tsx
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const TIER_STYLES: Record<string, string> = {
  Favorable: 'bg-teal-100 text-teal-800 border-teal-200 dark:bg-teal-900/30 dark:text-teal-300',
  Neutral:   'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300',
  Cautious:  'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300',
  Avoid:     'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300',
}

export function TierBadge({ tier }: { tier: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'text-lg font-semibold px-4 py-1.5 border',
        TIER_STYLES[tier] ?? 'bg-gray-100 text-gray-600'
      )}
    >
      {tier}
    </Badge>
  )
}
```

### Pattern 6: Skeleton Shimmer Cards
**What:** Tailwind `animate-pulse` shimmer cards that mirror the real card layout.
**When to use:** Initial dashboard load before data arrives.

```typescript
// src/components/dashboard/TickerCardSkeleton.tsx
export function TickerCardSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="animate-pulse space-y-2">
        <div className="h-4 bg-muted rounded w-1/3" />   {/* symbol */}
        <div className="h-3 bg-muted rounded w-2/3" />   {/* company name */}
      </div>
      <div className="animate-pulse h-10 bg-muted rounded w-1/2 mx-auto" /> {/* tier badge */}
      <div className="animate-pulse h-10 bg-muted rounded" />               {/* sparkline */}
      <div className="animate-pulse h-3 bg-muted rounded w-1/4" />          {/* date */}
    </div>
  )
}

export function WatchlistGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <TickerCardSkeleton key={i} />
      ))}
    </div>
  )
}
```

### Pattern 7: Next.js Docker Standalone Build
**What:** Three-stage Dockerfile using `output: 'standalone'` to produce a ~150-200MB production image.
**When to use:** Production Docker service definition.

```dockerfile
# Source: https://oneuptime.com/blog/post/2026-02-17-how-to-build-a-docker-image-for-a-nextjs-application-with-standalone-output-and-deploy-to-cloud-run/view

# Stage 1: deps
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 3: runner
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

RUN chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

```typescript
// next.config.ts — required for standalone
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
}
export default nextConfig
```

```yaml
# docker-compose.yml addition
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  mem_limit: 512m
  restart: unless-stopped
  depends_on:
    reasoning-engine:
      condition: service_healthy
  environment:
    NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: ${SUPABASE_PUBLISHABLE_KEY}
    REASONING_ENGINE_URL: http://reasoning-engine:8000
  ports:
    - "3000:3000"
  networks:
    - reasoning
  profiles: ["reasoning"]
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 30s
```

### Anti-Patterns to Avoid
- **Using `getSession()` in middleware or Server Components:** Supabase docs are explicit — `getClaims()` validates the JWT signature; `getSession()` does not. Always `getClaims()` for route protection.
- **Calling the FastAPI backend from Client Components directly:** The FastAPI reasoning-engine is on the Docker internal network (`reasoning-engine:8000`). Client Components run in the browser — they cannot reach this URL. Either (a) create Next.js Route Handlers as a proxy, or (b) pass the JWT + base URL to the client and use the VPS-exposed port (8001). Given no nginx yet in Phase 12, option (b) with the host-mapped port is the pragmatic choice.
- **Using `NEXT_PUBLIC_` prefix on the Supabase service role key:** The service role key must NEVER have `NEXT_PUBLIC_` — it would be exposed to the browser. (Established project convention from STATE.md.)
- **ISR or page-level caching for authenticated dashboard pages:** Any Next.js caching on user-specific pages risks serving another user's session data. Authenticated routes must be dynamically rendered.
- **N+1 serial fetches per card:** Fetching OHLCV and report history sequentially per ticker for 30 cards = 60 serial round trips. Always use `Promise.all` to fan out in parallel.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth cookie management and token refresh | Custom cookie logic | `@supabase/ssr` createServerClient | Edge cases in token expiry, refresh race conditions, HttpOnly cookie serialization |
| Toast notifications | Custom toast component | Sonner | Queueing, deduplication, accessible ARIA roles, z-index management |
| Component primitives (buttons, cards, badges) | Custom design system | shadcn/ui | Keyboard navigation, focus trapping, ARIA attributes all pre-handled |
| Conditional className merging | String concatenation | `cn()` from shadcn (clsx + tailwind-merge) | Tailwind class conflict resolution (e.g., two `bg-*` classes — last wins unexpectedly without merge) |

**Key insight:** In Next.js App Router, auth cookie handling has subtle ordering requirements (middleware must run before Server Component renders; cookies() must be awaited in Next.js 15). The `@supabase/ssr` package encodes all of this — building it manually introduces subtle bugs around token refresh timing.

---

## Common Pitfalls

### Pitfall 1: `getClaims()` vs `getSession()` in Middleware
**What goes wrong:** Calling `supabase.auth.getSession()` in middleware and trusting the result. The session object is returned from the cookie without re-validating the JWT signature, so a tampered or revoked token passes the check.
**Why it happens:** `getSession()` was the documented method before `@supabase/ssr` was released; many tutorials still show it.
**How to avoid:** Always use `getClaims()` in middleware and Server Components. `getClaims()` validates against Supabase's published JWKS keys.
**Warning signs:** Auth works in dev but production has users bypassing auth with stale tokens.

### Pitfall 2: Next.js 15 Async `cookies()`
**What goes wrong:** Using `cookies()` synchronously. In Next.js 15, `cookies()` from `next/headers` is async and must be awaited.
**Why it happens:** Next.js 14 and below had synchronous `cookies()`. The API changed in 15.
**How to avoid:** `const cookieStore = await cookies()` in all server utilities.
**Warning signs:** TypeScript error "cannot call .getAll on Promise<...>" or runtime crash.

### Pitfall 3: Client Component Calling Internal Docker URL
**What goes wrong:** Setting `REASONING_ENGINE_URL=http://reasoning-engine:8000` as `NEXT_PUBLIC_REASONING_ENGINE_URL` and using it in a Client Component fetch. This resolves to the Docker network hostname, which is unreachable from the browser.
**Why it happens:** Confusion between server-side and client-side rendering contexts.
**How to avoid:** Either use Next.js Route Handlers to proxy API calls (safest — hides backend URL), OR use the host-mapped port (8001) for client-side calls via the VPS IP. In Phase 12 (no nginx), client-side calls should target port 8001 directly. Keep `REASONING_ENGINE_URL` (no `NEXT_PUBLIC_`) for server-only use.
**Warning signs:** `fetch failed` or `ECONNREFUSED` errors in browser console.

### Pitfall 4: `output: 'standalone'` Missing Static File Copy
**What goes wrong:** Dockerfile that only copies `.next/standalone` but omits `.next/static` and `public/`. The app starts but all CSS/JS assets 404.
**Why it happens:** standalone output doesn't include static assets; they must be copied separately.
**How to avoid:** Three COPY lines are mandatory: `standalone`, `static`, and `public`.
**Warning signs:** App shell loads but is unstyled; DevTools shows 404 on `/_next/static/**` routes.

### Pitfall 5: Memory Pressure from In-Process Next.js Build Cache
**What goes wrong:** Next.js default in-memory cache (50MB) causes the container to creep toward the 512MB `mem_limit` during normal use, and the VPS OOM killer terminates the container.
**Why it happens:** ISR and data cache share a 50MB in-memory pool by default.
**How to avoid:** Since the dashboard is fully dynamic (no ISR), add `export const dynamic = 'force-dynamic'` to dashboard pages. This disables the data cache for those routes. Monitor with `docker stats` after deployment.
**Warning signs:** Container memory grows over time without stabilizing; process restarts observed in `docker events`.

### Pitfall 6: shadcn/ui Canary Requires `--legacy-peer-deps` with npm
**What goes wrong:** `npm install` fails on peer dependency conflicts when installing shadcn/ui canary with React 19.
**Why it happens:** Some component dependencies haven't declared React 19 compatibility.
**How to avoid:** Use `npm install --legacy-peer-deps` when adding shadcn components, OR switch to pnpm which handles peer deps more gracefully.
**Warning signs:** `ERESOLVE` errors during `npm install` or `npx shadcn@canary add`.

---

## Code Examples

### API Helper — Typed Fetch Functions
```typescript
// src/lib/api.ts
// All API calls go through this module — centralizes auth header injection
const API_BASE = process.env.NEXT_PUBLIC_REASONING_ENGINE_URL ?? 'http://localhost:8001'

async function apiFetch<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',  // authenticated data — never cache
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

export const getWatchlist = (token: string) =>
  apiFetch<{ tickers: { symbol: string; name: string; asset_type: string }[] }>('/watchlist', token)

export const getOhlcv = (symbol: string, token: string) =>
  apiFetch<{ data: { time: number; close: number }[] }>(`/tickers/${symbol}/ohlcv`, token)

export const getLastReport = (symbol: string, token: string) =>
  apiFetch<{ items: { tier: string; generated_at: string }[] }>(
    `/reports/by-ticker/${symbol}?page=1&per_page=1`,
    token
  )
```

### Login Form Pattern
```typescript
// src/components/login/LoginForm.tsx
'use client'
import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'

export function LoginForm() {
  const router = useRouter()
  const supabase = createClient()

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const { error } = await supabase.auth.signInWithPassword({
      email: form.get('email') as string,
      password: form.get('password') as string,
    })
    if (error) {
      // show error toast
    } else {
      router.push('/')
      router.refresh()  // critical: forces middleware to re-read the new cookie
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <button type="submit">Sign in</button>
    </form>
  )
}
```

### Tailwind v4 globals.css
```css
/* src/app/globals.css */
@import "tailwindcss";

:root {
  --background: hsl(0 0% 100%);
  --foreground: hsl(0 0% 3.9%);
  --card: hsl(0 0% 100%);
  --muted: hsl(210 40% 96%);
  --muted-foreground: hsl(215.4 16.3% 46.9%);
}

.dark {
  --background: hsl(222.2 84% 4.9%);
  --foreground: hsl(210 40% 98%);
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@supabase/auth-helpers` | `@supabase/ssr` | 2024 | auth-helpers deprecated; ssr package is the only maintained path |
| `getSession()` for route protection | `getClaims()` | 2024 | Security: getClaims validates JWT signature; getSession does not |
| `tailwind.config.js` with `content[]` | `@import "tailwindcss"` in globals.css, no config | Tailwind v4 (2025) | Auto-scanning removes manual content config |
| shadcn stable (Tailwind v3) | shadcn canary (Tailwind v4 + React 19) | 2025 | Canary is the only path for v4 compatibility |
| `cookies()` synchronous | `await cookies()` | Next.js 15 (2024) | Breaking change from Next.js 14 |
| Standard Docker output (2GB+) | `output: 'standalone'` (~150-200MB) | Next.js 12+ | Essential for 512MB mem_limit containers |

**Deprecated/outdated:**
- `@supabase/auth-helpers-nextjs`: Deprecated — use `@supabase/ssr` exclusively
- `supabase.auth.getUser()` for middleware token validation: Replaced by `getClaims()` per latest Supabase docs (getClaims validates JWT locally without round-trip; getUser makes a network request to Supabase Auth server)
- `tailwind.config.js` for content array: No longer needed in v4 (auto-scan)

---

## Open Questions

1. **Client-side API calls before nginx (Phase 15)**
   - What we know: Phase 12 has no nginx. FastAPI is on host port 8001. Client Components cannot reach the Docker internal hostname `reasoning-engine:8000`.
   - What's unclear: Should Phase 12 use Next.js Route Handlers as proxy (adds complexity), or point `NEXT_PUBLIC_REASONING_ENGINE_URL` at `http://{VPS_IP}:8001` (simpler but exposes port 8001 in frontend bundle)?
   - Recommendation: Use Next.js Route Handlers (`/api/watchlist`, `/api/ohlcv/[symbol]`, `/api/reports/[symbol]`) as thin proxies. This keeps the FastAPI URL out of the browser, works in both Docker and local dev, and requires no changes when nginx arrives in Phase 15.

2. **Access token passing from Server Component to Client Component**
   - What we know: Dashboard layout (Server Component) has access to the Supabase session and JWT. Client Components need the JWT to call the API.
   - What's unclear: Is it acceptable to pass `session.access_token` as a prop? This puts the JWT in the serialized HTML payload.
   - Recommendation: Use Next.js Route Handlers on the server side for all API calls. The server handler extracts the JWT from the cookie server-side without ever sending it to the client. This is the cleaner pattern and avoids JWT exposure in props.

3. **Node.js memory leak with `fetch` in Next.js 15 standalone**
   - What we know: GitHub issue #85914 reports memory growth with `fetch` + standalone in Next.js 15.x. The underlying cause is the `undici` HTTP client.
   - What's unclear: Is this fixed in the version we'll use? Which exact Next.js 15 patch version should be pinned?
   - Recommendation: Pin to the latest stable patch (e.g., `15.2.4` or later), monitor with `docker stats` after deployment. If memory grows, switch API calls in Route Handlers from `fetch` to `node-fetch` or `axios` as a mitigation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None pre-existing — this is a greenfield Next.js service |
| Config file | Wave 0 creates `frontend/playwright.config.ts` (E2E) + `frontend/vitest.config.ts` (unit) |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` |
| Full suite command | `cd frontend && npx vitest run && npx playwright test` |

### Success Criteria → Validation Map

Each success criterion from the phase goal maps to one or more concrete, automatable checks.

#### SC-1: Unauthenticated redirect / authenticated landing (INFR-01, DASH-01)
**Criterion:** Unauthenticated users are redirected to `/login`; authenticated users land on the dashboard.

| Check | Type | Command / Assertion | Pass Threshold |
|-------|------|---------------------|----------------|
| Unauthenticated GET `/` returns redirect | Automated (curl) | `curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://localhost:3000/` | Status 307 or 302; redirect URL contains `/login` |
| Unauthenticated GET `/` final URL is `/login` | Automated (curl follow) | `curl -sL -o /dev/null -w "%{url_effective}" http://localhost:3000/` | Final URL ends with `/login` |
| Unauthenticated GET `/login` returns 200 | Automated (curl) | `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login` | `200` |
| middleware.ts exists with route protection logic | Automated (file check) | `grep -q "redirect.*login" frontend/src/middleware.ts` | Exit code 0 |
| middleware.ts uses getClaims not getSession | Automated (grep) | `grep -q "getClaims" frontend/src/middleware.ts && ! grep -q "getSession" frontend/src/middleware.ts` | Exit code 0 |
| Authenticated user session reaches dashboard | Manual / E2E | Playwright: log in with test credentials, assert `page.url()` ends with `/` | URL is `/` (not `/login`) |

#### SC-2: Dashboard cards with tier badge, sparkline, last report date (DASH-01, DASH-02, DASH-03, DASH-04)
**Criterion:** Dashboard shows a card per watchlist ticker with entry quality tier badge, 52-week sparkline, and last report date.

| Check | Type | Command / Assertion | Pass Threshold |
|-------|------|---------------------|----------------|
| TickerCard component renders tier badge element | Unit (Vitest + React Testing Library) | `render(<TickerCard .../>); screen.getByText(/Favorable|Neutral|Cautious|Avoid/)` | Element found, no throw |
| TierBadge renders correct CSS class for each tier | Unit (Vitest) | Test each of 4 tiers: assert `bg-teal-100` for Favorable, `bg-slate-100` for Neutral, `bg-amber-100` for Cautious, `bg-rose-100` for Avoid | All 4 assertions pass |
| Sparkline renders SVG polyline element | Unit (Vitest) | `render(<Sparkline data={[...52 values...]} />); container.querySelector('polyline')` | Not null |
| Sparkline polyline points attribute contains 52 coordinate pairs | Unit (Vitest) | Parse `polyline.getAttribute('points').trim().split(' ').length` | Equals 52 |
| Sparkline color is green when last > first | Unit (Vitest) | `data[51] > data[0]`: assert `stroke="#16a34a"` | Passes |
| Sparkline color is red when last < first | Unit (Vitest) | `data[51] < data[0]`: assert `stroke="#dc2626"` | Passes |
| Last report date renders on card | Unit (Vitest) | `render(<TickerCard lastReport={{ tier: 'Favorable', generated_at: '2026-01-15T00:00:00Z' }} .../>); screen.getByText(/Jan|2026/)` | Date text present |
| Dashboard page responds 200 for authenticated session | E2E (Playwright) | After login: `await page.goto('/'); expect(response.status()).toBe(200)` | Status 200 |
| Dashboard HTML contains tier badge colors | E2E (Playwright) | After login with seeded watchlist: `page.locator('[class*="bg-teal"], [class*="bg-slate"], [class*="bg-amber"], [class*="bg-rose"]').count()` | Count > 0 |
| Dashboard HTML contains SVG polyline | E2E (Playwright) | After login: `page.locator('polyline').count()` | Count >= number of watchlist tickers with OHLCV data |

#### SC-3: Loading skeleton and error toast (DASH-05)
**Criterion:** Dashboard shows loading skeleton while data fetches; error toast if API call fails.

| Check | Type | Command / Assertion | Pass Threshold |
|-------|------|---------------------|----------------|
| WatchlistGridSkeleton renders 6 skeleton cards | Unit (Vitest) | `render(<WatchlistGridSkeleton />); screen.getAllByRole('...skeleton...').length` (or test aria-label on skeleton divs) | Count = 6 |
| Skeleton cards contain `animate-pulse` class | Unit (Vitest) | `container.querySelectorAll('.animate-pulse').length` | > 0 |
| DashboardClient shows skeleton on initial render (before fetch resolves) | Unit (Vitest + mock) | Mock `getWatchlist` to return pending promise; render `DashboardClient`; assert skeleton visible before resolution | Skeleton rendered synchronously |
| DashboardClient shows error state when fetch throws | Unit (Vitest + mock) | Mock `getWatchlist` to reject; render; await; assert error message text present | Error text visible |
| Sonner toast fires on API error | Unit (Vitest + spy) | Spy on `toast.error`; trigger fetch failure; assert spy called once | Called with error message |
| Error state renders Retry button | Unit (Vitest + mock) | After fetch rejection: `screen.getByRole('button', { name: /retry/i })` | Button present |

#### SC-4: Empty state when watchlist has no tickers (DASH-05)
**Criterion:** Dashboard shows empty state when watchlist has no tickers.

| Check | Type | Command / Assertion | Pass Threshold |
|-------|------|---------------------|----------------|
| EmptyState component renders "watchlist is empty" text | Unit (Vitest) | `render(<EmptyState />); screen.getByText(/watchlist is empty/i)` | Text present |
| EmptyState renders quick-add buttons for VNM, FPT, HPG, GLD, MWG | Unit (Vitest) | Assert 5 buttons with ticker names | All 5 found |
| DashboardClient renders EmptyState when watchlist returns 0 tickers | Unit (Vitest + mock) | Mock `getWatchlist` returning `{ tickers: [] }`; render; await; assert EmptyState visible | Empty state visible |
| Quick-add button calls PUT /watchlist with correct ticker | Unit (Vitest + mock) | Mock fetch; click VNM quick-add; assert fetch called with `{ symbol: 'VNM' }` | Fetch called correctly |

#### SC-5: Docker service starts within 512MB mem_limit (INFR-01)
**Criterion:** Next.js Docker service starts with `mem_limit: 512m` and passes `docker stats` without exceeding limit during normal dashboard load.

| Check | Type | Command / Assertion | Pass Threshold |
|-------|------|---------------------|----------------|
| docker-compose.yml frontend service has `mem_limit: 512m` | Automated (grep) | `grep -A 5 "frontend:" docker-compose.yml \| grep "mem_limit: 512m"` | Exit code 0 |
| next.config.ts has `output: 'standalone'` | Automated (grep) | `grep -q "standalone" frontend/next.config.ts` | Exit code 0 |
| Dockerfile has 3 stages (deps, builder, runner) | Automated (grep) | `grep -c "^FROM" frontend/Dockerfile` | Equals 3 |
| Dockerfile copies `.next/static` and `public` separately | Automated (grep) | `grep -q ".next/static" frontend/Dockerfile && grep -q "public" frontend/Dockerfile` | Exit code 0 |
| Container starts healthy within 60s | Integration (docker) | `docker compose --profile reasoning up -d frontend && docker compose ps frontend \| grep "healthy"` (poll 60s) | Service shows `healthy` |
| Container memory during cold start stays under 512MB | Integration (docker stats) | `docker stats --no-stream --format "{{.MemUsage}}" stratum-frontend-1` | Reported MiB < 512 |
| Container memory during dashboard load (30-ticker page) stays under 512MB | Manual / Integration | Open dashboard in browser with full 30-ticker watchlist; re-run docker stats | Reported MiB < 512 |
| `force-dynamic` export present on dashboard page | Automated (grep) | `grep -q "force-dynamic" frontend/src/app/\(dashboard\)/page.tsx` | Exit code 0 |

### Grouped by Validation Type

#### Automated (can run in CI with no live services)
```bash
# File/config checks — run anywhere
grep -q "mem_limit: 512m" docker-compose.yml
grep -q "standalone" frontend/next.config.ts
grep -c "^FROM" frontend/Dockerfile          # expect 3
grep -q "getClaims" frontend/src/middleware.ts
grep -q "force-dynamic" "frontend/src/app/(dashboard)/page.tsx"

# Unit tests (Vitest)
cd frontend && npx vitest run --reporter=verbose
```

#### Integration (requires running Docker stack)
```bash
# Start the frontend service
docker compose --profile reasoning up -d

# Health check
docker compose ps frontend | grep "healthy"

# Unauthenticated redirect
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# expect 307 (or 302)

curl -sL -o /dev/null -w "%{url_effective}" http://localhost:3000/
# expect URL ends with /login

# Login page available
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login
# expect 200

# Memory at idle
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | grep frontend
# MiB value must be < 512
```

#### Manual / E2E (requires live Supabase + seeded watchlist)
```bash
# Run Playwright E2E suite (requires TEST_EMAIL and TEST_PASSWORD env vars)
cd frontend && npx playwright test

# Manual memory check under load
# 1. Open dashboard in browser with 30-ticker watchlist
# 2. Run: docker stats --no-stream stratum-frontend-1
# 3. Confirm MemUsage < 512MiB
```

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run` (unit tests only, ~5-10s)
- **Per wave merge:** `cd frontend && npx vitest run && npx playwright test` (full suite)
- **Phase gate:** Full suite green + manual docker stats check before `/gsd:verify-work`

### Wave 0 Gaps
The following test infrastructure does not yet exist (greenfield project) and must be created before implementation tasks can be validated:

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment and React Testing Library
- [ ] `frontend/src/test/setup.ts` — Global test setup (jest-dom matchers, cleanup)
- [ ] `frontend/playwright.config.ts` — Playwright config with baseURL, test credentials from env
- [ ] `frontend/tests/e2e/auth.spec.ts` — E2E: unauthenticated redirect, login flow
- [ ] `frontend/tests/e2e/dashboard.spec.ts` — E2E: dashboard load, card rendering
- [ ] `frontend/src/components/dashboard/__tests__/TierBadge.test.tsx` — Unit: tier badge color classes
- [ ] `frontend/src/components/dashboard/__tests__/Sparkline.test.tsx` — Unit: SVG polyline math
- [ ] `frontend/src/components/dashboard/__tests__/DashboardClient.test.tsx` — Unit: loading/error/empty states
- [ ] `frontend/src/components/dashboard/__tests__/EmptyState.test.tsx` — Unit: quick-add buttons

**Framework install (Wave 0 task):**
```bash
cd frontend
npm install --save-dev vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @playwright/test
npx playwright install chromium
```

---

## Sources

### Primary (HIGH confidence)
- https://supabase.com/docs/guides/auth/server-side/creating-a-client — createServerClient / createBrowserClient patterns, middleware.ts template, getClaims() requirement
- https://supabase.com/docs/guides/auth/server-side/nextjs — Full Next.js SSR auth setup guide
- https://nextjs.org/docs/app/guides/self-hosting — standalone output, Docker, caching behavior
- https://nextjs.org/docs/app/getting-started/deploying — Docker deployment patterns and official examples
- https://tailwindcss.com/docs/guides/nextjs — Tailwind v4 installation with Next.js (official)
- https://ui.shadcn.com/docs/tailwind-v4 — shadcn/ui Tailwind v4 + React 19 canary support
- https://ui.shadcn.com/docs/changelog — shadcn/ui March 2026 v4 CLI release confirmation

### Secondary (MEDIUM confidence)
- https://oneuptime.com/blog/post/2026-02-17-how-to-build-a-docker-image-for-a-nextjs-application-with-standalone-output-and-deploy-to-cloud-run/view — Dockerfile pattern with 512Mi Cloud Run deployment, verified against Next.js official example
- https://dev.to/gnykka/how-to-create-a-sparkline-component-in-react-4e1 — SVG polyline coordinate math, verified correct against standard SVG coordinate system
- https://ui.shadcn.com/docs/changelog — Version and Tailwind v4 support status

### Tertiary (LOW confidence)
- https://github.com/vercel/next.js/issues/79588 — Memory usage concerns in Next.js 14/15 standalone; flagged for validation but not verified fixed
- https://github.com/vercel/next.js/issues/85914 — fetch/undici memory leak in Next.js 15 standalone; monitor in production

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified against official Supabase, Next.js, Tailwind, shadcn docs
- Architecture: HIGH — patterns derived from official docs; SVG sparkline math verified
- Pitfalls: HIGH for auth pitfalls (official docs explicit); MEDIUM for memory concerns (GitHub issues, not official docs)
- Docker: HIGH — Dockerfile pattern confirmed against official Next.js example and multiple 2025/2026 sources
- Validation Architecture: HIGH for unit/integration checks; MEDIUM for E2E (Playwright config is standard but test credentials depend on live Supabase)

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (30 days — stack is stable; shadcn/ui canary moves fast, verify before implementing)
