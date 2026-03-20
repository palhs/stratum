# Stratum — Project Rules

## Tech Stack

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS v4, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy Core (no ORM), Pydantic v2, LangGraph + Gemini
- **Databases**: PostgreSQL 16, Neo4j 5, Qdrant
- **Proxy**: nginx (dev: `host.docker.internal`, prod: Docker DNS + TLS)
- **Auth**: Supabase (ES256 JWTs, validated via JWKS in backend with PyJWT)
- **Migrations**: Flyway SQL (versioned V1–V8+)

## Project Structure

```
frontend/          Next.js app (src/ with App Router)
reasoning/         FastAPI reasoning engine (app/ with routers, nodes, pipeline)
nginx/             dev.conf, local.conf, production.conf
db/                Flyway migrations and init scripts
sidecar/           Data ingestion FastAPI service
scripts/           Seed scripts, provisioning
.planning/         GSD planning artifacts
```

## Coding Conventions

### Frontend
- Components: PascalCase files (`TierBadge.tsx`), utils: lowercase (`api.ts`)
- Imports: absolute with `@/` prefix (`@/components/ui/badge`)
- Styling: Tailwind utilities, `cn()` for class merging, CVA for variants
- State: server components by default, `'use client'` only when needed
- IMPORTANT: Next.js 16 has breaking changes. Read `node_modules/next/dist/docs/` before using any API

### Backend
- SQLAlchemy **Core only** — no ORM. Use `Table()` with `autoload_with=db_engine`
- PostgreSQL-specific features: use `from sqlalchemy.dialects.postgresql import insert`
- Auth: `Depends(require_auth)` returns JWT payload dict, extract `payload["sub"]` for user ID
- Resources on `request.app.state` (db_engine, neo4j_driver, qdrant_client)
- Routers in `reasoning/app/routers/`, shared schemas in `reasoning/app/schemas.py`

### General
- No docstrings/comments on code you didn't change
- No over-engineering — solve what's asked, nothing more
- Import order: stdlib, third-party, local

## MCP Tools

### context7 — Library Documentation
Before using any library API, fetch current docs instead of relying on training data:
```
mcp__context7__resolve-library-id → mcp__context7__query-docs
```
MUST use for: Next.js 16 APIs, LangGraph, Supabase SSR, any library where version matters.

### auggie — Codebase Retrieval
Use `mcp__auggie__codebase-retrieval` to search the indexed codebase for existing patterns, implementations, and conventions before writing new code. Helps avoid duplicating logic or breaking established patterns.

## Testing Requirements

### Unit Tests (every change)
- **Frontend**: Vitest + Testing Library. Tests in `__tests__/` next to components
  ```bash
  cd frontend && npm test
  ```
- **Backend**: pytest + pytest-asyncio. Tests in `reasoning/tests/`
  ```bash
  cd reasoning && .venv/bin/python -m pytest tests/
  ```

### E2E Validation (every phase completion)
After completing a phase, the coding agent MUST:

1. **Run all existing tests** and confirm zero regressions
   ```bash
   cd frontend && npm test
   cd reasoning && .venv/bin/python -m pytest tests/ -x
   ```

2. **Start the local stack** and verify the feature works end-to-end
   ```bash
   make dev          # Terminal 1: storage + nginx
   make dev-frontend # Terminal 2
   make dev-reasoning # Terminal 3
   ```

3. **Test through nginx** (not direct ports) — use `http://localhost`

4. **Write a validation report** in the phase SUMMARY.md containing:
   - What was implemented (features, files, routes)
   - Manual validation steps the user can follow to verify
   - Screenshots or curl commands proving it works
   - Any known limitations or edge cases

### What to Validate
- API endpoints return correct status codes and data
- Frontend pages render without console errors
- Auth flow works (login, protected routes, token refresh)
- nginx routes correctly (API paths vs frontend pages)
- SSE streaming works unbuffered through nginx

## Local Development

```bash
make dev            # Storage + nginx
make dev-frontend   # Next.js on :3000 (hot reload)
make dev-reasoning  # FastAPI on :8000 (auto-reload)
```

Access via `http://localhost` (nginx). See `DEPLOYMENT.md` for full guide.

### Env Vars
- Copy `.env.example` to `.env.local`
- Frontend needs `NEXT_PUBLIC_*` prefixed vars when running natively
- Backend needs `DATABASE_URL`, `NEO4J_URI`, `QDRANT_HOST` pointing to `localhost`

## nginx Routing

API routes proxy to reasoning-engine, everything else to frontend:
- `/watchlist`, `/tickers/*`, `/health` → reasoning-engine
- `/reports/generate`, `/reports/by-ticker/*`, `/reports/by-report-id/*`, `/reports/stream/*` → reasoning-engine
- `/reports/{symbol}` → frontend (page route, NOT API)
- `/*` → frontend

IMPORTANT: The reasoning engine has NO `/api` prefix. Routes are `/watchlist`, `/reports/*`, `/tickers/*` directly.

## Common Pitfalls

- SQLAlchemy `insert` from core doesn't have `on_conflict_do_nothing` — use `sqlalchemy.dialects.postgresql.insert`
- Supabase JWTs use ES256 (not RS256) — auth must accept both algorithms
- `NEXT_PUBLIC_*` vars are baked at build time in production but read at runtime in dev
- nginx `location /reports/` catches frontend page routes — use specific sub-paths instead
- Docker Compose override auto-applies — VPS must exclude it or delete it
