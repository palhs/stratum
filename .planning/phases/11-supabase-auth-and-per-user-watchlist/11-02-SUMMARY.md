---
phase: 11-supabase-auth-and-per-user-watchlist
plan: 02
subsystem: watchlist, api, auth
tags: [fastapi, watchlist, crud, pydantic, sqlalchemy, tdd, jwt, rs256]

# Dependency graph
requires:
  - "11-01 (require_auth RS256 dependency, V8 watchlist migration)"
provides:
  - "GET /watchlist — returns user's tickers with {symbol, name, asset_type}; seeds defaults for new users"
  - "PUT /watchlist — replaces full list atomically; validates symbols, enforces max 30"
  - "WatchlistItem, WatchlistResponse, WatchlistUpdate Pydantic schemas"
  - "TICKER_METADATA static dict — all VN30 + GLD/IAU/SGOL with names and asset_type"
affects:
  - "Phase 12 frontend — will call GET/PUT /watchlist with Supabase JWT"
  - "Auth flow — Task 2 (Supabase dashboard config) still pending user action"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static TICKER_METADATA dict for symbol validation — faster than DB query, covers full VN30+gold universe"
    - "INSERT ... ON CONFLICT DO NOTHING for idempotent watchlist seeding"
    - "DELETE + INSERT in single transaction for atomic watchlist replacement"
    - "TDD: test file with mocked internal functions + patched _jwks_client"

key-files:
  created:
    - "reasoning/app/routers/watchlist.py — GET and PUT /watchlist endpoints with seeding, validation, atomic replace"
    - "reasoning/tests/api/test_watchlist.py — 9 TDD tests covering all scenarios"
  modified:
    - "reasoning/app/schemas.py — WatchlistItem, WatchlistResponse, WatchlistUpdate appended"
    - "reasoning/app/main.py — watchlist router registered at /watchlist prefix"

key-decisions:
  - "Static TICKER_METADATA dict used for symbol validation instead of DB query — ticker universe is static for VN30+gold; static dict is faster and avoids coupling to DB state"
  - "Zero-rows → seed behavior is idempotent and correct for v3.0 — explicitly clearing the watchlist re-seeds on next GET, which is acceptable as documented in CONTEXT.md"
  - "ON CONFLICT DO NOTHING used for seeding insert — safe for concurrent first-request scenarios"

requirements-completed: [AUTH-05, WTCH-01, WTCH-02, WTCH-03]

# Metrics
duration: ~5min
completed: 2026-03-18
---

# Phase 11 Plan 02: Watchlist CRUD API Summary

**Watchlist GET/PUT endpoints with per-user isolation, first-login seeding from defaults, static TICKER_METADATA validation, and atomic list replacement — all 42 API tests passing**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-18T15:18:40Z
- **Completed:** 2026-03-18T15:23:28Z
- **Tasks:** 1 complete (Task 2: Supabase dashboard config — awaiting user action)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Watchlist router (`reasoning/app/routers/watchlist.py`) with `GET /watchlist` and `PUT /watchlist` endpoints, both protected by `require_auth`
- `GET /watchlist` seeds from `watchlist_defaults` on first call (zero rows for user) — idempotent via `INSERT ... ON CONFLICT DO NOTHING`
- `PUT /watchlist` replaces entire list atomically — validates symbols against `TICKER_METADATA` (all VN30 + 3 gold ETFs), enforces max 30 tickers
- Static `TICKER_METADATA` dict maps all 33 supported tickers to `{name, asset_type}` — covers VN30 constituents (equity) + GLD/IAU/SGOL (gold_etf)
- Three Pydantic schemas added to `schemas.py`: `WatchlistItem`, `WatchlistResponse`, `WatchlistUpdate`
- Watchlist router registered at `/watchlist` prefix in `main.py`
- 9 TDD tests (all scenarios: auth guards, seeding, existing list, replace, invalid symbol, max size, empty clear, isolation)
- Full API test suite: 42/42 passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Watchlist schemas, router, and endpoint tests** - `b7eb8bd` (feat)

## Files Created/Modified

- `reasoning/app/routers/watchlist.py` — GET/PUT /watchlist with _get_or_seed_watchlist, _validate_symbols, _replace_watchlist, TICKER_METADATA
- `reasoning/tests/api/test_watchlist.py` — 9 TDD tests; mocks internal functions + patches _jwks_client; includes os.environ.setdefault for SUPABASE_JWKS_URL
- `reasoning/app/schemas.py` — WatchlistItem, WatchlistResponse, WatchlistUpdate schemas appended
- `reasoning/app/main.py` — watchlist router import and include_router registration added

## Deviations from Plan

None — plan executed exactly as written. The `os.environ.setdefault("SUPABASE_JWKS_URL", ...)` line was added to `test_watchlist.py` following the existing pattern from `test_openapi.py` (required since `auth.py` reads the env var at module import time).

## Pending: Task 2 — Supabase Dashboard Configuration

Task 2 is a `checkpoint:human-action` requiring manual configuration of the Supabase project dashboard. This cannot be automated. See checkpoint return message for full instructions.

## Self-Check: PASSED

- `reasoning/app/routers/watchlist.py` — FOUND
- `reasoning/tests/api/test_watchlist.py` — FOUND
- `reasoning/app/schemas.py` modified — FOUND (WatchlistItem present)
- `reasoning/app/main.py` modified — FOUND (include_router watchlist present)
- Commit `b7eb8bd` — FOUND
