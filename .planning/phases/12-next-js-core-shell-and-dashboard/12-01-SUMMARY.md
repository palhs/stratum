---
phase: 12-next-js-core-shell-and-dashboard
plan: 01
subsystem: ui
tags: [nextjs, react, tailwind, shadcn, supabase, ssr, docker, vitest, typescript]

# Dependency graph
requires:
  - phase: 11-supabase-auth-and-per-user-watchlist
    provides: Supabase auth setup (JWKS URL, project URL, anon key) required for SSR middleware
provides:
  - Next.js 16.2 app with standalone Docker output
  - Supabase SSR client helpers (browser + server contexts)
  - Auth proxy (route protection: unauthenticated -> /login, authenticated -> /)
  - Login page with email/password form, loading and error states
  - Dashboard route group layout with server-side auth guard
  - Report placeholder page at /reports/[symbol]
  - Vitest + React Testing Library + jsdom test infrastructure
  - shadcn/ui components: badge, card, button, input, label, sonner, skeleton
  - Docker frontend service with 512m mem_limit in docker-compose.yml
affects: [12-02-next-js-dashboard-components, 13-report-detail-page, 14-tradingview-charts]

# Tech tracking
tech-stack:
  added:
    - next@16.2.0 (App Router, standalone output)
    - react@19.2.4 + react-dom@19.2.4
    - @supabase/ssr@0.9.0 (server-side cookie management)
    - @supabase/supabase-js@2.99.2
    - tailwindcss@4.2.2 + @tailwindcss/postcss
    - shadcn/ui components (manually installed — canary CLI non-interactive)
    - class-variance-authority, clsx, tailwind-merge (CVA pattern)
    - lucide-react (icon library)
    - sonner@2.0.7 (toast notifications)
    - date-fns@4.1.0
    - next-themes@0.4.6
    - vitest@4.1.0 + @vitejs/plugin-react + jsdom
    - @testing-library/react + @testing-library/jest-dom + @testing-library/user-event
    - @playwright/test
  patterns:
    - Next.js route groups: (auth) for /login, (dashboard) for / protected routes
    - Supabase SSR: createBrowserClient for client components, createServerClient for server/proxy
    - proxy.ts (Next.js 16 file convention, replaces deprecated middleware.ts)
    - CVA (class-variance-authority) pattern for component variants
    - 3-stage Docker build: deps -> builder -> runner (standalone output)

key-files:
  created:
    - frontend/src/proxy.ts (auth route protection proxy)
    - frontend/src/lib/supabase/client.ts (createBrowserClient helper)
    - frontend/src/lib/supabase/server.ts (createServerClient helper)
    - frontend/src/app/(auth)/login/page.tsx (login page)
    - frontend/src/components/login/LoginForm.tsx (client-side auth form)
    - frontend/src/app/(dashboard)/layout.tsx (server-side auth guard layout)
    - frontend/src/app/(dashboard)/page.tsx (dashboard shell, force-dynamic)
    - frontend/src/app/reports/[symbol]/page.tsx (report placeholder)
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/button.tsx
    - frontend/src/components/ui/card.tsx
    - frontend/src/components/ui/input.tsx
    - frontend/src/components/ui/label.tsx
    - frontend/src/components/ui/sonner.tsx
    - frontend/src/components/ui/skeleton.tsx
    - frontend/src/lib/utils.ts (cn helper)
    - frontend/Dockerfile (3-stage standalone build)
    - frontend/vitest.config.ts
    - frontend/src/test/setup.ts
    - frontend/.env.example
    - frontend/components.json (shadcn config)
  modified:
    - docker-compose.yml (added frontend service with mem_limit: 512m)
    - frontend/next.config.ts (output: standalone, poweredByHeader: false)
    - frontend/postcss.config.mjs (@tailwindcss/postcss plugin)
    - frontend/src/app/globals.css (shadcn/ui zinc CSS variables)
    - frontend/src/app/layout.tsx (Inter font, Toaster provider)
    - frontend/package.json (added test/test:watch scripts)

key-decisions:
  - "proxy.ts (not middleware.ts) is the correct file convention for Next.js 16.2 — middleware.ts is deprecated, export must be named 'proxy'"
  - "shadcn/ui canary CLI is fully interactive — components.json created manually with New York style, zinc base color, CSS variables enabled"
  - "Supabase getUser() used in proxy.ts (not getSession()) — validates JWT signature, not just cookie presence"
  - "force-dynamic on dashboard page prevents ISR cache pressure from authenticated content"
  - "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (not ANON_KEY) — matches Supabase v2 env var naming convention"

patterns-established:
  - "Route groups (auth) and (dashboard) separate public and protected page trees"
  - "Server components use createClient() from lib/supabase/server.ts; client components use lib/supabase/client.ts"
  - "shadcn/ui CVA components follow new-york style with zinc base color and HSL CSS variables"

requirements-completed: [INFR-01]

# Metrics
duration: 11min
completed: 2026-03-19
---

# Phase 12 Plan 01: Next.js Core Shell and Dashboard Summary

**Next.js 16.2 app scaffolded with Supabase SSR auth proxy, login page, dashboard route group, shadcn/ui components, and Vitest test infrastructure — all building and type-checking cleanly in Docker standalone output.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-18T17:18:29Z
- **Completed:** 2026-03-19T00:00:00Z
- **Tasks:** 2 (+ 1 auto-fix deviation)
- **Files modified:** 35

## Accomplishments

- Next.js 16.2 app builds to standalone output (`.next/standalone`) — Docker-ready
- Supabase SSR auth working: proxy.ts routes unauthenticated users to /login, blocks authenticated users from revisiting /login
- Login page renders email/password form with loading spinner (Loader2) and inline error display
- Dashboard layout enforces server-side auth guard via getSession() — double protection with proxy
- Vitest configured with jsdom environment and React Testing Library — test:watch and test:run scripts ready
- Docker frontend service added to docker-compose.yml with 512m mem_limit and depends_on reasoning-engine

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold Next.js 15 project with Tailwind v4, shadcn/ui, Supabase SSR, Docker, and test infra** - `9b39d30` (feat)
2. **Task 2: Auth middleware, login page, and dashboard layout with route protection** - `851d195` (feat)
3. **Deviation fix: Rename middleware.ts to proxy.ts** - `0938db7` (fix)

## Files Created/Modified

- `frontend/src/proxy.ts` - Auth route protection proxy using createServerClient + getUser()
- `frontend/src/lib/supabase/client.ts` - createBrowserClient for 'use client' components
- `frontend/src/lib/supabase/server.ts` - createServerClient for server components/layouts
- `frontend/src/components/login/LoginForm.tsx` - 'use client' form with signInWithPassword, Loader2 spinner, error state
- `frontend/src/app/(auth)/login/page.tsx` - Centered Card layout with LoginForm
- `frontend/src/app/(dashboard)/layout.tsx` - Server-side auth guard + header shell
- `frontend/src/app/(dashboard)/page.tsx` - Dashboard shell (force-dynamic, placeholder for Plan 02)
- `frontend/src/app/reports/[symbol]/page.tsx` - Report placeholder with back button
- `frontend/src/components/ui/` - badge, button, card, input, label, sonner, skeleton
- `frontend/Dockerfile` - 3-stage build: deps/builder/runner, standalone output
- `docker-compose.yml` - Added frontend service (mem_limit: 512m, depends_on reasoning-engine)
- `frontend/next.config.ts` - output: standalone, poweredByHeader: false
- `frontend/vitest.config.ts` - jsdom environment, @vitejs/plugin-react, @/* alias
- `frontend/src/test/setup.ts` - @testing-library/jest-dom/vitest import

## Decisions Made

- **proxy.ts over middleware.ts:** Next.js 16.2 renamed the middleware file convention to proxy.ts with a `proxy` named export. Using deprecated middleware.ts still builds but emits a deprecation warning — fixed to use the new convention.
- **shadcn/ui components created manually:** The canary CLI (`npx shadcn@canary init`) is fully interactive with no non-interactive flags. Created components.json manually with New York style/zinc/CSS variables, then wrote component files following the shadcn/ui New York style.
- **getUser() in proxy.ts:** Uses `supabase.auth.getUser()` (validates JWT with Supabase JWKS) rather than `getSession()` (trusts cookie without verification) — matches Supabase's own recommendation for middleware/proxy auth validation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed middleware.ts to proxy.ts per Next.js 16 deprecation**
- **Found during:** Task 2 verification (build warning)
- **Issue:** Next.js 16.2.0 (installed version) deprecated the `middleware.ts` file convention in favor of `proxy.ts`. Build succeeded but emitted: "The 'middleware' file convention is deprecated. Please use 'proxy' instead." The plan was written for Next.js 15, but `create-next-app@latest` installed 16.2.0.
- **Fix:** Renamed `src/middleware.ts` to `src/proxy.ts` and renamed the exported function from `middleware` to `proxy`.
- **Files modified:** frontend/src/proxy.ts (was middleware.ts)
- **Verification:** Build produces no deprecation warnings; TypeScript passes; `ƒ Proxy (Middleware)` shown in route table
- **Committed in:** `0938db7`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug, Next.js version convention mismatch)
**Impact on plan:** Necessary for forward compatibility with Next.js 16. All plan functionality implemented as specified. No scope creep.

## Issues Encountered

- `npx shadcn@canary init` is fully interactive with no non-interactive mode — worked around by creating `components.json` manually and writing component files directly using New York style conventions.
- `create-next-app@latest` installed Next.js 16.2.0 (not 15 as plan specified) — plan worked except for the middleware->proxy rename.

## User Setup Required

None — no external service configuration required by this plan. Supabase credentials are needed at runtime (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) — documented in frontend/.env.example.

## Next Phase Readiness

- Plan 02 (Dashboard Components) can build directly on this foundation
- DashboardClient component placeholder exists in (dashboard)/page.tsx — Plan 02 fills it in
- Supabase client helpers are ready for use in all components
- Test infrastructure is configured — Plan 02 can add Vitest tests immediately
- All shadcn/ui components needed for dashboard cards are installed

---
*Phase: 12-next-js-core-shell-and-dashboard*
*Completed: 2026-03-19*
