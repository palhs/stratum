---
phase: 10-backend-api-contracts-and-jwt-middleware
plan: 01
subsystem: auth, api
tags: [jwt, pyjwt, supabase, fastapi, pydantic, sqlalchemy, ohlcv, window-functions]

# Dependency graph
requires: []
provides:
  - "require_auth FastAPI dependency — validates Supabase JWTs (HS256, audience=authenticated)"
  - "GET /tickers/{symbol}/ohlcv endpoint — OHLCV + MA50/MA200 in TradingView format"
  - "Shared Pydantic v2 schemas: OHLCVPoint, OHLCVResponse, ReportHistoryItem, ReportHistoryResponse"
affects:
  - "10-02 (report history endpoint will use ReportHistoryItem and ReportHistoryResponse)"
  - "11-frontend-auth (frontend will call GET /tickers/{symbol}/ohlcv with Supabase JWT)"
  - "Any future reasoning-engine endpoints that need JWT protection"

# Tech tracking
tech-stack:
  added:
    - "PyJWT>=2.12.1 — Supabase JWT validation in reasoning-engine"
  patterns:
    - "HTTPBearer(auto_error=False) pattern — allows returning 401 (not 403) on missing header"
    - "_query_ohlcv internal function pattern — testable by patching at module level"
    - "Table autoload_with=db_engine pattern — consistent with existing codebase for dynamic schema loading"
    - "SQL window function MAs — func.avg().over(partition_by=..., order_by=..., rows=(-N, 0))"

key-files:
  created:
    - "reasoning/app/auth.py — require_auth FastAPI dependency"
    - "reasoning/app/schemas.py — shared Pydantic v2 response schemas"
    - "reasoning/app/routers/tickers.py — GET /tickers/{symbol}/ohlcv endpoint"
    - "reasoning/tests/api/test_auth.py — 5 unit tests for JWT auth dependency"
    - "reasoning/tests/api/test_ohlcv.py — 4 unit tests for OHLCV endpoint"
  modified:
    - "reasoning/requirements.txt — added PyJWT>=2.12.1"
    - "docker-compose.yml — added SUPABASE_JWT_SECRET env var to reasoning-engine"
    - "reasoning/app/main.py — registered tickers router with /tickers prefix"

key-decisions:
  - "HTTPBearer(auto_error=False) used so missing header returns 401 not FastAPI's default 403"
  - "GOLD_TICKERS set routes GLD/IAU/SGOL to gold_etf_ohlcv (ticker column) vs stock_ohlcv (symbol column)"
  - "MA50/MA200 computed in SQL via window functions (rows frame), not Python — consistent with plan spec"
  - "Table autoload_with=db_engine chosen over pre-defined models/tables.py to avoid metadata coupling"
  - "main.py router registration added as Rule 2 deviation — endpoint must be mounted to be callable"

patterns-established:
  - "Auth pattern: require_auth Depends everywhere on protected endpoints, tested via patch.dict(os.environ)"
  - "OHLCV query: _query_ohlcv private function patched in tests, avoids real DB in unit tests"
  - "Test isolation: patch require_auth.os.environ to inject secret without setting real env var"

requirements-completed: [INFR-03, INFR-04]

# Metrics
duration: 5min
completed: 2026-03-18
---

# Phase 10 Plan 01: Backend API Contracts and JWT Middleware Summary

**Supabase JWT validation (HS256, audience=authenticated) and GET /tickers/{symbol}/ohlcv endpoint with SQL window function MA50/MA200 in TradingView Unix timestamp format**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-18T04:25:03Z
- **Completed:** 2026-03-18T04:29:15Z
- **Tasks:** 2 (Task 1: auth + schemas + infra; Task 2: TDD endpoint + tests)
- **Files modified:** 7 (5 created, 3 modified)

## Accomplishments

- JWT auth dependency (`require_auth`) correctly returns 401 for missing/malformed tokens and 403 for expired/wrong-audience tokens
- OHLCV endpoint serves candlestick data with MA50/MA200 computed via SQL window functions — no Python-side rolling average
- Gold ticker routing (GLD/IAU/SGOL -> gold_etf_ohlcv table with `ticker` column) works transparently via `GOLD_TICKERS` set
- All 9 unit tests pass (5 auth + 4 OHLCV)

## Task Commits

Each task was committed atomically:

1. **Task 1: Auth dependency, schemas, infra** - `8f6ed84` (feat)
2. **Task 2 RED: Failing tests** - `83dce99` (test)
3. **Task 2 GREEN: OHLCV endpoint** - `13c7b16` (feat)
4. **Task 2 deviation: Register router in main.py** - `a4d5547` (feat)

_Note: TDD task has test commit then implementation commit per TDD protocol_

## Files Created/Modified

- `reasoning/app/auth.py` — require_auth dependency, 401/403 error handling for Supabase JWTs
- `reasoning/app/schemas.py` — OHLCVPoint, OHLCVResponse, ReportHistoryItem, ReportHistoryResponse (Pydantic v2)
- `reasoning/app/routers/tickers.py` — GET /tickers/{symbol}/ohlcv with SQLAlchemy window function MAs
- `reasoning/tests/api/test_auth.py` — 5 tests: no header, valid, expired, wrong audience, malformed
- `reasoning/tests/api/test_ohlcv.py` — 4 tests: response shape, empty data, auth guard, gold routing
- `reasoning/requirements.txt` — added `PyJWT>=2.12.1`
- `docker-compose.yml` — added `SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET}` to reasoning-engine
- `reasoning/app/main.py` — registered tickers router with `/tickers` prefix

## Decisions Made

- `HTTPBearer(auto_error=False)` — FastAPI's default is 403 on missing bearer; `auto_error=False` lets us raise 401 ourselves, matching the spec
- `GOLD_TICKERS = {"GLD", "IAU", "SGOL"}` — explicit set routing vs. trying to detect by schema introspection
- `Table(table_name, metadata, autoload_with=db_engine)` — consistent with Phase 8 pattern of not coupling to pre-defined SQLAlchemy ORM models
- MA window: `rows=(-49, 0)` for MA50, `rows=(-199, 0)` for MA200 — row-based frame (not range-based) to get exact N-period MA

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Registered tickers router in main.py**
- **Found during:** Task 2 (tickers.py endpoint creation)
- **Issue:** Plan specified creating the tickers router but didn't include registering it in main.py — without registration, the endpoint would be unreachable
- **Fix:** Added `from reasoning.app.routers import tickers` and `app.include_router(tickers.router, prefix="/tickers", tags=["tickers"])` to main.py
- **Files modified:** `reasoning/app/main.py`
- **Verification:** Module imports cleanly, router registered on app
- **Committed in:** `a4d5547`

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical registration)
**Impact on plan:** Necessary for correct operation. No scope creep.

## Issues Encountered

- PyJWT was not installed in the `reasoning/.venv` (requirements.txt has it but venv was created before this plan). Installed it with `pip install "PyJWT>=2.12.1"` to enable local test execution.

## User Setup Required

**SUPABASE_JWT_SECRET must be added to the `.env` file on the VPS before deploying the reasoning-engine container.**

Add this line to `.env` (or `.env.local` for local dev):
```
SUPABASE_JWT_SECRET=<your-supabase-jwt-secret>
```

To find your Supabase JWT secret: Supabase Dashboard -> Project Settings -> API -> JWT Secret.

Verification after deployment:
```bash
# Should return 401 (no auth):
curl -sf http://localhost:8001/tickers/VHM/ohlcv

# Should return 200 with OHLCV data (valid Supabase token):
curl -H "Authorization: Bearer <your-supabase-token>" http://localhost:8001/tickers/VHM/ohlcv
```

## Next Phase Readiness

- `require_auth` is a reusable dependency ready for all future protected endpoints in Phase 10-02+
- `ReportHistoryItem` and `ReportHistoryResponse` schemas are defined and ready for Phase 10-02 (report history endpoint)
- Frontend (Phase 11+) can now call `/tickers/{symbol}/ohlcv` with a Supabase session JWT

---
*Phase: 10-backend-api-contracts-and-jwt-middleware*
*Completed: 2026-03-18*
