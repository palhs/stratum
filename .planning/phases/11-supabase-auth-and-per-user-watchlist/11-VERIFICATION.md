---
phase: 11-supabase-auth-and-per-user-watchlist
verified: 2026-03-18T16:00:00Z
status: human_needed
score: 13/14 must-haves verified
re_verification: false
human_verification:
  - test: "Verify Supabase dashboard is configured for invite-only auth (AUTH-03)"
    expected: "Public signups disabled, admin can invite new users, SUPABASE_JWKS_URL env var set from real Supabase project JWKS endpoint"
    why_human: "Dashboard configuration (disable signups, set Site URL, invite test user, verify JWKS JSON) cannot be verified programmatically from the codebase"
---

# Phase 11: Supabase Auth and Per-User Watchlist Verification Report

**Phase Goal:** Migrate JWT auth from HS256 to RS256/JWKS for Supabase compatibility, create watchlist database schema, and build per-user watchlist CRUD API
**Verified:** 2026-03-18T16:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | auth.py validates RS256 JWTs from Supabase JWKS endpoint (not HS256 shared secret) | VERIFIED | `reasoning/app/auth.py`: `PyJWKClient(os.environ["SUPABASE_JWKS_URL"], ...)`, `algorithms=["RS256"]`, no HS256 anywhere |
| 2 | PyJWKClient is a module-level singleton with 5-minute cache TTL | VERIFIED | `_jwks_client = PyJWKClient(..., cache_jwk_set=True, lifespan=300)` at module scope (lines 24-28) |
| 3 | All 5 auth test scenarios (no header=401, valid=200, expired=403, wrong audience=403, malformed=401) pass with RS256 mocks | VERIFIED | 28/28 tests PASSED; test_auth.py confirms all 5 scenarios pass using PyJWKClient mock |
| 4 | All test files that previously mocked SUPABASE_JWT_SECRET now mock PyJWKClient instead | VERIFIED | `grep -r "SUPABASE_JWT_SECRET" reasoning/` returns zero matches; all 4 test files use `patch("reasoning.app.auth._jwks_client")` |
| 5 | docker-compose.yml has SUPABASE_JWKS_URL replacing SUPABASE_JWT_SECRET for reasoning-engine | VERIFIED | `docker-compose.yml` line 318: `SUPABASE_JWKS_URL: ${SUPABASE_JWKS_URL}`; no SUPABASE_JWT_SECRET reference |
| 6 | Flyway V8 migration creates user_watchlist and watchlist_defaults tables with correct constraints | VERIFIED | `db/migrations/V8__watchlist.sql`: BIGSERIAL PK, UUID user_id, UNIQUE(user_id, symbol), INDEX on user_id, watchlist_defaults with 6 seed rows |
| 7 | GET /watchlist returns the user's watchlist with symbol, name, and asset_type per ticker | VERIFIED | `watchlist.py` GET endpoint returns `WatchlistResponse(tickers=[WatchlistItem(symbol, name, asset_type)])` from TICKER_METADATA lookup |
| 8 | GET /watchlist seeds default tickers on first call for a new user | VERIFIED | `_get_or_seed_watchlist`: if zero rows → INSERT from watchlist_defaults ON CONFLICT DO NOTHING; confirmed by `test_get_watchlist_seeds_defaults` PASSED |
| 9 | PUT /watchlist replaces the entire watchlist atomically | VERIFIED | `_replace_watchlist`: DELETE + INSERT in single connection with `conn.commit()`; `test_put_watchlist_replaces` PASSED |
| 10 | PUT /watchlist validates all symbols exist in TICKER_METADATA | VERIFIED | `_validate_symbols` checks against static TICKER_METADATA dict; invalid symbols → 422; `test_put_watchlist_invalid_symbol` PASSED |
| 11 | PUT /watchlist rejects more than 30 tickers | VERIFIED | `if len(body.tickers) > MAX_WATCHLIST_SIZE: raise HTTPException(422, ...)`; `test_put_watchlist_exceeds_max` PASSED |
| 12 | Watchlist data is isolated per user — user_id from JWT sub claim | VERIFIED | `user_id = payload["sub"]` in both endpoints; `test_watchlist_isolation` verifies user-a and user-b get separate data |
| 13 | Watchlist persists across sessions via VPS PostgreSQL | VERIFIED | user_watchlist table in V8 migration with PostgreSQL storage; `_replace_watchlist` and `_get_or_seed_watchlist` use SQLAlchemy against db_engine |
| 14 | Admin can invite users via Supabase dashboard (AUTH-03 — manual config) | NEEDS HUMAN | Supabase dashboard configuration cannot be verified from codebase; `11-02-SUMMARY.md` explicitly defers this to post-frontend |

**Score:** 13/14 truths verified (automated); 1 pending human verification

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `db/migrations/V8__watchlist.sql` | user_watchlist + watchlist_defaults tables | VERIFIED | File exists; CREATE TABLE user_watchlist (BIGSERIAL PK, UUID user_id, UNIQUE(user_id,symbol)), INDEX idx_user_watchlist_user, CREATE TABLE watchlist_defaults (6 seed rows: GLD+VNM+VHM+VCB+HPG+MSN) |
| `reasoning/app/auth.py` | RS256/JWKS auth dependency | VERIFIED | Contains `PyJWKClient`, `_jwks_client` module-level singleton, `algorithms=["RS256"]`, `signing_key.key` unwrapping, same 401/403 public interface |
| `reasoning/tests/api/test_auth.py` | RS256-based auth tests | VERIFIED | Contains `get_signing_key_from_jwt` (mock target), RSA key pair, all 5 test scenarios; 5/5 PASSED |
| `reasoning/app/routers/watchlist.py` | GET /watchlist and PUT /watchlist endpoints | VERIFIED | Contains `get_watchlist`, `put_watchlist`, `_get_or_seed_watchlist`, `_replace_watchlist`, `_validate_symbols`, `TICKER_METADATA` (33 tickers) |
| `reasoning/app/schemas.py` | WatchlistItem, WatchlistResponse, WatchlistUpdate schemas | VERIFIED | All three classes appended after ReportHistoryResponse |
| `reasoning/app/main.py` | Watchlist router registration | VERIFIED | `from reasoning.app.routers import watchlist`; `app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])` at line 46 |
| `reasoning/tests/api/test_watchlist.py` | Watchlist endpoint tests | VERIFIED | Contains `test_get_watchlist` and 8 more tests; 9/9 PASSED |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `reasoning/app/auth.py` | SUPABASE_JWKS_URL env var | `os.environ["SUPABASE_JWKS_URL"]` → `PyJWKClient` | WIRED | Line 25: `_jwks_client = PyJWKClient(os.environ["SUPABASE_JWKS_URL"], ...)` |
| `docker-compose.yml` | `reasoning/app/auth.py` | SUPABASE_JWKS_URL environment variable | WIRED | Line 318: `SUPABASE_JWKS_URL: ${SUPABASE_JWKS_URL}` in reasoning-engine service |
| `reasoning/app/routers/watchlist.py` | `reasoning/app/auth.py` | `Depends(require_auth)` on both endpoints | WIRED | Both `get_watchlist` and `put_watchlist` have `payload: dict = Depends(require_auth)` |
| `reasoning/app/routers/watchlist.py` | `db/migrations/V8__watchlist.sql` | SQLAlchemy Core queries against user_watchlist and watchlist_defaults | WIRED | `Table("user_watchlist", ...), Table("watchlist_defaults", ...)` in `_get_or_seed_watchlist`; `Table("user_watchlist", ...)` in `_replace_watchlist` |
| `reasoning/app/main.py` | `reasoning/app/routers/watchlist.py` | `app.include_router(watchlist.router, prefix="/watchlist")` | WIRED | Line 46: `app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-01 | 11-01 | User can log in with email and password via Supabase | SATISFIED | RS256/JWKS auth accepts Supabase-issued JWTs; `require_auth` validates sub, aud, exp claims |
| AUTH-02 | 11-01 | User session persists across browser refresh via HTTP-only cookies | SATISFIED | Backend validates Supabase JWTs — session management is Supabase-side (HTTP-only cookies handled by Supabase SDK on frontend); backend correctly validates the resulting JWTs |
| AUTH-03 | 11-02 | Admin can invite new users via Supabase admin API (signup disabled) | PENDING HUMAN | Code infrastructure complete; dashboard config (disable signups, invite user) requires human verification |
| AUTH-04 | 11-01, 11-02 | User data is isolated per account | SATISFIED | `user_id = payload["sub"]` used in all DB queries; UNIQUE(user_id, symbol) constraint; isolation test passes |
| AUTH-05 | 11-02 | Invited user receives pre-seeded watchlist on first login | SATISFIED | `_get_or_seed_watchlist`: zero rows → INSERT from watchlist_defaults ON CONFLICT DO NOTHING; confirmed by test |
| WTCH-01 | 11-02 | User can add tickers from VN30 + gold universe to watchlist | SATISFIED | `PUT /watchlist` with `_validate_symbols` against TICKER_METADATA (33 tickers: all VN30 + GLD/IAU/SGOL) |
| WTCH-02 | 11-02 | User can remove tickers from their watchlist | SATISFIED | `PUT /watchlist` with empty list → 204; full list replacement via DELETE + INSERT; `test_put_watchlist_empty` PASSED |
| WTCH-03 | 11-02 | Watchlist is persisted per user across sessions | SATISFIED | user_watchlist table in PostgreSQL; queries use db_engine (VPS PostgreSQL); data persists between requests |

**Requirement AUTH-03:** Marked as pending in `REQUIREMENTS.md` (checkbox unchecked). The code infrastructure (RS256 JWT validation) is complete and correctly rejects invalid tokens. The Supabase dashboard configuration step (disabling public signups, setting Site URL, inviting the first user) was explicitly deferred by the executor per `11-02-SUMMARY.md`. This is a one-time operator action, not a code deficiency.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder/return null patterns found in any phase-11 files. All implementations are substantive.

**Note on AUTH-02:** The REQUIREMENTS.md description says "HTTP-only cookies." The backend implementation validates Bearer tokens (not cookies directly). This is architecturally correct — the Supabase JS SDK manages the HTTP-only cookie session on the frontend and provides the JWT as a Bearer token to the API. The backend's responsibility is validating the JWT, which it does correctly. No issue.

---

### Human Verification Required

#### 1. Supabase Dashboard — Invite-Only Auth Configuration (AUTH-03)

**Test:** Log in to the Supabase dashboard for the project referenced by SUPABASE_JWKS_URL.

**Steps to verify:**
1. Navigate to Authentication → Settings → User Signups
2. Confirm "Allow new users to sign up" is toggled **OFF**
3. Navigate to Authentication → URL Configuration — confirm Site URL is set to the frontend domain
4. Navigate to Authentication → Users — confirm at least one user has been invited (or attempt to invite a test user)
5. Open `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` in a browser — confirm it returns JSON with a `keys` array containing at least one RS256 key (`"alg": "RS256"`)
6. Confirm `.env` file has `SUPABASE_JWKS_URL` set (and no `SUPABASE_JWT_SECRET` line)

**Expected:** All six steps confirm. Signup attempt via POST to Supabase auth endpoint returns an error (signup disabled).

**Why human:** Supabase dashboard is an external cloud service. Its configuration state cannot be read from the local codebase. The SUPABASE_JWKS_URL env var value in `.env` is a runtime secret not tracked in git.

---

### Gaps Summary

No automated gaps. All code artifacts are present, substantive, and correctly wired. All 28 tests pass (5 auth + 4 ohlcv + 6 reports_history + 4 openapi + 9 watchlist).

The single pending item (AUTH-03) is a human-action checkpoint explicitly deferred by the plan executor. The code fully supports the invite-only flow — the Supabase dashboard configuration is an operator step that cannot be automated or verified from the codebase.

---

## Test Run Evidence

```
28 passed in 0.60s
Platform: darwin — Python 3.11.2, pytest-9.0.2
PYTHONPATH: /Users/phananhle/Desktop/phananhle/stratum
Venv: reasoning/.venv/bin/python3.11

reasoning/tests/api/test_auth.py::test_auth_no_header_returns_401       PASSED
reasoning/tests/api/test_auth.py::test_auth_valid_token_passes           PASSED
reasoning/tests/api/test_auth.py::test_auth_expired_token_returns_403    PASSED
reasoning/tests/api/test_auth.py::test_auth_wrong_audience_returns_403   PASSED
reasoning/tests/api/test_auth.py::test_auth_malformed_token_returns_401  PASSED
reasoning/tests/api/test_ohlcv.py::test_ohlcv_returns_data_with_ma       PASSED
reasoning/tests/api/test_ohlcv.py::test_ohlcv_empty_symbol_returns_empty_data PASSED
reasoning/tests/api/test_ohlcv.py::test_ohlcv_requires_auth              PASSED
reasoning/tests/api/test_ohlcv.py::test_ohlcv_gold_symbol_routes_to_gold_table PASSED
reasoning/tests/api/test_reports_history.py (6 tests)                    6 PASSED
reasoning/tests/api/test_openapi.py (4 tests)                            4 PASSED
reasoning/tests/api/test_watchlist.py (9 tests)                          9 PASSED
```

## Commit Verification

All documented commits verified present in git history:
- `fe435cb` — feat(11-01): migrate auth to RS256/JWKS and create watchlist V8 migration
- `4cc2d3e` — feat(11-01): rewrite all test files for RS256/JWKS mock pattern
- `b7eb8bd` — feat(11-02): watchlist CRUD API with first-login seeding and per-user isolation

---

*Verified: 2026-03-18T16:00:00Z*
*Verifier: Claude (gsd-verifier)*
