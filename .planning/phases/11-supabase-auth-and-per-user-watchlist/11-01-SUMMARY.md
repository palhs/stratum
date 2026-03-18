---
phase: 11-supabase-auth-and-per-user-watchlist
plan: 01
subsystem: auth, db-migrations
tags: [jwt, rs256, jwks, pyjwkclient, supabase, fastapi, flyway, watchlist]

# Dependency graph
requires: []
provides:
  - "RS256/JWKS auth dependency (require_auth) — validates Supabase JWTs via PyJWKClient singleton"
  - "V8 Flyway migration — user_watchlist and watchlist_defaults tables with 6 seed rows"
affects:
  - "11-02 (watchlist API will use require_auth and user_watchlist table)"
  - "All existing endpoints using require_auth (auth contract unchanged, only key material changes)"

# Tech tracking
tech-stack:
  added:
    - "PyJWKClient (from PyJWT[cryptography]) — JWKS key fetching with 300s cache TTL"
    - "cryptography package — RSA key generation for test fixtures"
  patterns:
    - "PyJWKClient module-level singleton — initialized at import time, shared across requests"
    - "signing_key.key unwrapping — pass the raw key to jwt.decode for mock compatibility in tests"
    - "Mock _jwks_client at module path — cleaner than patching os.environ for RS256 tests"
    - "RSA key pair generated at test module level — shared across all tests in a file"

key-files:
  created:
    - "db/migrations/V8__watchlist.sql — user_watchlist (UNIQUE user_id+symbol, user_id index) and watchlist_defaults (6 seed rows)"
  modified:
    - "reasoning/app/auth.py — RS256/JWKS via PyJWKClient singleton, signing_key.key for jwt.decode"
    - "docker-compose.yml — SUPABASE_JWKS_URL replaces SUPABASE_JWT_SECRET in reasoning-engine environment"
    - "reasoning/tests/api/test_auth.py — RSA key pair, mock _jwks_client, all 5 RS256 scenarios"
    - "reasoning/tests/api/test_ohlcv.py — RS256 tokens, mock _jwks_client in all 4 tests"
    - "reasoning/tests/api/test_reports_history.py — RS256 tokens, mock _jwks_client in all 6 tests"
    - "reasoning/tests/api/test_openapi.py — SUPABASE_JWKS_URL env var replaces SUPABASE_JWT_SECRET"

key-decisions:
  - "signing_key.key (not signing_key directly) passed to jwt.decode — required for PyJWK mock compatibility; PyJWT's _verify_signature does isinstance(key, PyJWK) check and MagicMock fails it"
  - "Module-level PyJWKClient singleton initialized from SUPABASE_JWKS_URL — must be at module level for 300s JWKS cache to be shared across requests"
  - "cryptography package used for RSA test key generation — already available in system Python, no new requirement needed"

requirements-completed: [AUTH-01, AUTH-02, AUTH-04]

# Metrics
duration: 7min
completed: 2026-03-18
---

# Phase 11 Plan 01: RS256/JWKS Auth Migration and Watchlist Schema Summary

**Supabase RS256/JWKS JWT validation via PyJWKClient singleton and Flyway V8 watchlist schema (user_watchlist + watchlist_defaults with 6 seed rows)**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-18T05:08:48Z
- **Completed:** 2026-03-18T05:16:00Z
- **Tasks:** 2 (Task 1: V8 migration + auth.py RS256 + docker-compose; Task 2: TDD test file rewrites)
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- RS256/JWKS authentication dependency `require_auth` in `auth.py` — PyJWKClient singleton with 300s JWKS cache, same 401/403 public interface preserved
- Flyway V8 migration creates `user_watchlist` (BIGSERIAL PK, UUID user_id, VARCHAR symbol, UNIQUE user_id+symbol, user_id index) and `watchlist_defaults` (6 seed rows: GLD + VNM/VHM/VCB/HPG/MSN)
- `docker-compose.yml` updated: `SUPABASE_JWKS_URL` replaces `SUPABASE_JWT_SECRET` in reasoning-engine environment block
- All 19 unit tests pass with RS256 mock pattern — zero references to `SUPABASE_JWT_SECRET` in any test file

## Task Commits

Each task was committed atomically:

1. **Task 1: V8 migration, auth.py RS256, docker-compose** - `fe435cb` (feat)
2. **Task 2: RS256 test file rewrites + auth.py signing_key fix** - `4cc2d3e` (feat)

## Files Created/Modified

- `db/migrations/V8__watchlist.sql` — V8 Flyway migration: user_watchlist and watchlist_defaults tables
- `reasoning/app/auth.py` — RS256/JWKS via PyJWKClient singleton (300s cache), signing_key.key for jwt.decode
- `docker-compose.yml` — SUPABASE_JWKS_URL replaces SUPABASE_JWT_SECRET in reasoning-engine service
- `reasoning/tests/api/test_auth.py` — RSA key pair at module level, mock _jwks_client, 5 RS256 scenarios
- `reasoning/tests/api/test_ohlcv.py` — RS256 _make_auth_header, mock _jwks_client in all 4 tests
- `reasoning/tests/api/test_reports_history.py` — RS256 _make_auth_header, mock _jwks_client in all 6 tests
- `reasoning/tests/api/test_openapi.py` — SUPABASE_JWKS_URL env var setdefault

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] signing_key.key unwrapping required for jwt.decode mock compatibility**
- **Found during:** Task 2 — test_auth_valid_token_passes failed with 500 on first test run
- **Issue:** auth.py called `jwt.decode(token, signing_key, ...)` where `signing_key` was a `PyJWK` instance in production but a `MagicMock` in tests. PyJWT's `_verify_signature` does `isinstance(key, PyJWK)` — the mock failed this check and PyJWT tried to use the mock object as a raw key, raising an error
- **Fix:** Changed `jwt.decode` call to use `signing_key.key` (the raw cryptographic key) instead of `signing_key` directly. This works in both production (PyJWK.key is the actual key material) and tests (mock.key is set to _TEST_PUBLIC_KEY)
- **Files modified:** `reasoning/app/auth.py`
- **Commit:** `4cc2d3e`
