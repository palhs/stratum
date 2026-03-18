---
phase: 10-backend-api-contracts-and-jwt-middleware
plan: 02
subsystem: api, auth
tags: [fastapi, sqlalchemy, pydantic, jwt, report-history, openapi, jsonb]

# Dependency graph
requires:
  - "10-01 (require_auth dependency, ReportHistoryItem/ReportHistoryResponse schemas)"
provides:
  - "GET /reports/by-ticker/{symbol} endpoint — paginated report history with tier and verdict"
  - "JWT auth on POST /reports/generate"
  - "OpenAPI spec with all 5 endpoints and Pydantic schemas documented"
affects:
  - "11-frontend-auth (frontend will call GET /reports/by-ticker/{symbol} with Supabase JWT)"
  - "12-14 (dashboard phases that display report history)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "dependency_overrides[require_auth] pattern in tests — override FastAPI deps without patching auth internals"
    - "JSONB extraction via text() in SQLAlchemy Core — MIN(report_json->'entry_quality'->>'tier') AS tier"
    - "GROUP BY generated_at pattern — collapses vi+en rows into one entry per generation run"
    - "Route ordering discipline — by-ticker registered before /{job_id} to prevent 422 on string match"

key-files:
  created:
    - "reasoning/tests/api/test_reports_history.py — 6 tests for /by-ticker/{symbol} endpoint and auth guards"
    - "reasoning/tests/api/test_openapi.py — 4 tests for OpenAPI spec completeness"
  modified:
    - "reasoning/app/routers/reports.py — added _query_report_history(), GET /by-ticker/{symbol}, auth on /generate"
    - "reasoning/app/main.py — updated docstring to list all routes with auth markers"
    - "reasoning/tests/api/test_reports.py — added dependency_overrides[require_auth] to fix auth regression"

key-decisions:
  - "dependency_overrides[require_auth] in test_reports.py — cleanest way to bypass auth in endpoint logic tests (vs patching require_auth globally)"
  - "Route order: generate -> by-ticker -> stream -> {job_id} — prevents FastAPI treating string literals as integer job_id (422)"
  - "GROUP BY generated_at collapses vi+en language rows — one history entry per generation run as required"
  - "text() for JSONB extraction — MIN(report_json->'entry_quality'->>'tier') avoids SQLAlchemy type casting issues with JSONB operators"

requirements-completed: [INFR-05]

# Metrics
duration: 2min
completed: 2026-03-18
---

# Phase 10 Plan 02: Backend API Contracts and JWT Middleware Summary

**Report history endpoint (GET /reports/by-ticker/{symbol}) with JWT auth, JSONB tier/verdict extraction, and grouped generation runs — plus OpenAPI spec verification for all 5 endpoints**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-18T04:32:28Z
- **Completed:** 2026-03-18T04:34:49Z
- **Tasks:** 2 (Task 1: TDD endpoint + auth; Task 2: OpenAPI tests + full suite)
- **Files modified:** 5 (2 created tests, 1 created openapi test, 2 modified source/test)

## Accomplishments

- `GET /reports/by-ticker/{symbol}` serves paginated report history grouped by `generated_at` — one entry per run, not per language
- JSONB extraction via `text()` pulls `tier` and `narrative` from `report_json->'entry_quality'` correctly
- `POST /reports/generate` now requires JWT auth (401 without Authorization header)
- `GET /health` remains public — verified by test
- Route order enforced: by-ticker registered before `/{job_id}` to prevent FastAPI 422 on string match
- OpenAPI spec documents all 6 routes (`/health`, `/reports/generate`, `/reports/by-ticker/{symbol}`, `/reports/stream/{job_id}`, `/reports/{job_id}`, `/tickers/{symbol}/ohlcv`) with Pydantic response schemas
- All 33 API tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `c0dc0ec` (test)
2. **Task 1 GREEN: Endpoint + auth** - `bbaa51f` (feat)
3. **Task 2: OpenAPI tests + fix regression** - `fc935fb` (feat)

_Note: TDD task has test commit then implementation commit per TDD protocol_

## Files Created/Modified

- `reasoning/app/routers/reports.py` — `_query_report_history()` helper (GROUP BY generated_at, JSONB extraction), `GET /by-ticker/{symbol}` endpoint with `require_auth`, `Depends(require_auth)` on `POST /generate`, route order updated
- `reasoning/app/main.py` — docstring updated to list all routes with [auth] markers
- `reasoning/tests/api/test_reports_history.py` — 6 tests: paginated list shape, pagination params, empty symbol, auth guard on by-ticker, auth guard on generate, health public
- `reasoning/tests/api/test_openapi.py` — 4 tests: OHLCV endpoint in paths, report history in paths, health in paths, all 4 schemas in components.schemas
- `reasoning/tests/api/test_reports.py` — added `dependency_overrides[require_auth]` to test app fixture to restore endpoint logic tests after auth was added to `/generate`

## Decisions Made

- `dependency_overrides[require_auth]` in `test_reports.py` — cleanest way to bypass auth in existing endpoint logic tests; avoids patching auth internals and doesn't affect test_reports_history.py which tests auth separately
- Route order `generate -> by-ticker -> stream -> {job_id}` — string paths registered before parameterized `/{job_id}` to prevent FastAPI treating "by-ticker" as an integer and returning 422
- `text()` for JSONB extraction — `MIN(report_json->'entry_quality'->>'tier') AS tier` avoids SQLAlchemy's type inference issues with PostgreSQL JSONB operators in `select()` statements
- `GROUP BY generated_at` collapses vi+en rows — each generation run produces 2 report rows (Vietnamese + English); grouping collapses them to one history item per run

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_reports.py regression from adding auth to /generate**
- **Found during:** Task 2 (full suite run)
- **Issue:** Existing tests call `POST /reports/generate` without auth tokens — adding `Depends(require_auth)` to the endpoint caused all 5 existing generate/report tests to return 401 instead of 202
- **Fix:** Added `app.dependency_overrides[require_auth] = _mock_require_auth` to the test app fixture in test_reports.py; the mock returns a dummy payload, restoring endpoint logic test behavior
- **Files modified:** `reasoning/tests/api/test_reports.py`
- **Commit:** `fc935fb`

---

**Total deviations:** 1 auto-fixed (Rule 1 — regression from intended auth addition)
**Impact on plan:** Necessary to restore existing test suite. No scope creep.

## OpenAPI Spec Verification

All 6 endpoints appear in `app.openapi()['paths']`:
- `/health` — public
- `/reports/generate` — POST, auth required
- `/reports/by-ticker/{symbol}` — GET, auth required, `ReportHistoryResponse` schema
- `/reports/stream/{job_id}` — GET, no auth (SSE polling)
- `/reports/{job_id}` — GET, no auth (job polling)
- `/tickers/{symbol}/ohlcv` — GET, auth required, `OHLCVResponse` schema

All 4 Pydantic schemas in `components.schemas`: `OHLCVPoint`, `OHLCVResponse`, `ReportHistoryItem`, `ReportHistoryResponse`

## Next Phase Readiness

- `GET /reports/by-ticker/{symbol}` is ready for frontend consumption in Phases 12-14
- All protected endpoints (`/generate`, `/by-ticker/{symbol}`, `/tickers/{symbol}/ohlcv`) enforce Supabase JWT validation
- The reasoning-engine API is fully secured and exposes all data contracts for the dashboard

---
*Phase: 10-backend-api-contracts-and-jwt-middleware*
*Completed: 2026-03-18*

## Self-Check: PASSED

- FOUND: reasoning/tests/api/test_reports_history.py
- FOUND: reasoning/tests/api/test_openapi.py
- FOUND: .planning/phases/10-backend-api-contracts-and-jwt-middleware/10-02-SUMMARY.md
- FOUND: commit c0dc0ec (test RED)
- FOUND: commit bbaa51f (feat GREEN)
- FOUND: commit fc935fb (feat Task 2)
