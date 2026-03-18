# Phase 11: Supabase Auth and Per-User Watchlist - Research

**Researched:** 2026-03-18
**Domain:** Supabase Auth (JWT/JWKS), FastAPI auth middleware, PostgreSQL watchlist schema
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase Boundary:**
Set up invite-only Supabase authentication, create watchlist schema in VPS PostgreSQL (Flyway V8), build watchlist CRUD endpoints on the reasoning-engine FastAPI, and migrate JWT verification from HS256/raw-secret to RS256/JWKS (Supabase's current default). No frontend code (Phase 12), no new data ingestion pipelines.

**JWT verification migration:**
- Current auth.py uses HS256 with SUPABASE_JWT_SECRET — must migrate to RS256 with JWKS endpoint
- User's Supabase project only has JWK-format signing keys (no legacy plain-text secret available)
- Fetch public keys from `https://<project>.supabase.co/auth/v1/jwks` for verification
- Replace PyJWT HS256 decode with RS256 decode using JWKS-fetched public key

**Default watchlist seeding:**
- Curated 5-8 tickers seeded on first login (not at invite time)
- Default tickers stored in a config table in the database (admin-editable without redeploying)
- Gold (GLD) always included in defaults
- Backend detects no watchlist rows for user_id on first authenticated request and seeds from defaults table

**Admin invite workflow:**
- Use Supabase dashboard's built-in "Invite user" — no custom invite code needed
- Public signup disabled at Supabase project level only (no additional frontend/backend enforcement)
- User sets their own password via Supabase invite email link
- Default Supabase email template (no custom branding or Vietnamese text)

**Watchlist ticker universe:**
- VN30 (fixed list of current constituents) + GLD
- XAUUSD desired but data source not yet ingested — deferred to separate phase
- Watchlist only accepts tickers that exist in stock_ohlcv or gold_etf_ohlcv (backend validates on add)
- VN30 list hardcoded for now; manual update on index rebalance

**Watchlist API design:**
- Lives on existing reasoning-engine FastAPI alongside /reports and /tickers
- GET /watchlist — returns full list with metadata: `{ tickers: [{ symbol, name, asset_type }] }`
- PUT /watchlist — replaces entire list (frontend sends full array on any change), returns 204
- Max watchlist size: 30 tickers
- All watchlist endpoints protected by JWT auth (user_id extracted from token `sub` claim)

### Claude's Discretion
- Flyway V8 migration table design details (columns, indexes, constraints)
- JWKS key caching strategy (TTL, refresh logic)
- Error response details for validation failures (duplicate ticker, max size exceeded, invalid symbol)
- Ticker metadata source (static mapping vs database lookup)

### Deferred Ideas (OUT OF SCOPE)
- XAUUSD spot price ingestion — user wants XAUUSD in the watchlist universe, but data pipeline doesn't exist yet. Add as Phase 11.1 or fold into Phase 16.
- Custom Vietnamese invite email template — can be configured in Supabase dashboard later without code changes
- Dynamic VN30 list from index rebalance feed — manual update sufficient for now
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | User can log in with email and password via Supabase | Handled entirely in Supabase Cloud — no backend code. Frontend (Phase 12) handles login UI. This phase's backend work: RS256/JWKS migration so tokens issued by Supabase are verifiable. |
| AUTH-02 | User session persists across browser refresh via HTTP-only cookies | Frontend concern (Phase 12). Backend validates Bearer tokens; token storage strategy is frontend's responsibility. |
| AUTH-03 | Admin can invite new users via Supabase admin API (signup disabled) | Supabase dashboard "Invite user" button OR POST /auth/v1/invite with service_role key. Disable signup via Supabase dashboard toggle (Authentication > Settings > Disable signups). No code required. |
| AUTH-04 | User data is isolated per account (watchlists, report access) | Enforced in app code: watchlist queries always filter by `user_id = payload["sub"]`. No cross-user data is exposed. RLS in Supabase Cloud DB is not applicable (watchlist table is on VPS PostgreSQL). |
| AUTH-05 | Invited user receives pre-seeded watchlist on first login | Backend seeds watchlist from `watchlist_defaults` table when GET /watchlist finds zero rows for user_id. Idempotent seeding check on every GET. |
| WTCH-01 | User can add tickers from VN30 + gold universe to their watchlist | PUT /watchlist replaces full list; backend validates all symbols exist in stock_ohlcv or gold_etf_ohlcv. |
| WTCH-02 | User can remove tickers from their watchlist | Same PUT /watchlist endpoint — omit ticker from array to remove. |
| WTCH-03 | Watchlist is persisted per user across sessions | VPS PostgreSQL `user_watchlist` table with user_id (UUID from JWT sub). GET /watchlist reads from DB on every request. |
</phase_requirements>

---

## Summary

Phase 11 consists of three independent workstreams that can be planned separately:

1. **JWT migration** (`auth.py`): Replace HS256 + shared secret with RS256 + JWKS. PyJWT 2.12.1 (already installed) ships `PyJWKClient` which handles key fetching, caching (5-minute TTL by default), and automatic key rotation detection. The migration is a surgical replacement of ~10 lines in `auth.py` plus an env var swap (`SUPABASE_JWT_SECRET` → `SUPABASE_URL` or direct `SUPABASE_JWKS_URL`). Tests in `test_auth.py` currently use HS256 + mocked secret — they must be rewritten to mock `PyJWKClient` instead.

2. **Database schema** (Flyway V8): Two new tables — `user_watchlist` (per-user ticker rows) and `watchlist_defaults` (admin-editable seed list). Standard Flyway V8 migration file in `db/migrations/`. No ORM; uses the project's existing SQLAlchemy Core + Table autoload pattern.

3. **Watchlist API** (new FastAPI router): `GET /watchlist` with first-login seeding logic, and `PUT /watchlist` with full-replace + validation. Follows the exact router registration pattern of `tickers.py` and `reports.py`. New Pydantic schemas in `schemas.py`. New router registered in `main.py`.

The admin invite workflow and disabling public signup are **manual Supabase dashboard actions** — no code.

**Primary recommendation:** Implement in task order: (1) Flyway V8 migration, (2) auth.py RS256 migration + updated tests, (3) watchlist router + schemas + tests. Each is independently verifiable.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.12.1 (installed) | RS256 JWT decode via JWKS | Already in requirements.txt; ships PyJWKClient with built-in caching |
| cryptography | 46.0.5 (installed) | RSA key operations required by PyJWT RS256 | Auto-installed as PyJWT[crypto] dep; already present in venv |
| SQLAlchemy Core | 2.x (installed) | Watchlist DB queries | Project-wide pattern; Table autoload, no ORM |
| FastAPI | 0.115+ (installed) | Watchlist router | Existing app framework |
| Pydantic v2 | 2.x (installed) | WatchlistResponse, WatchlistUpdate schemas | Project-wide pattern in schemas.py |
| Flyway | 10 (docker-compose) | V8 migration for watchlist tables | Project-wide migration tool |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ (installed) | Only needed if PyJWKClient cannot reach JWKS URL in tests | Use to mock JWKS responses in unit tests |
| pytest + pytest-asyncio | installed | Testing watchlist endpoints and auth | All existing tests use this |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT PyJWKClient | python-jose | python-jose is less actively maintained; PyJWT is already installed |
| PyJWT PyJWKClient | Authlib | Authlib is heavier; no reason to add a new dep when PyJWT covers the use case |
| Full-replace PUT /watchlist | Individual POST/DELETE per ticker | PUT is simpler for small lists (max 30); avoids N-round-trips from frontend |

**Installation:** No new packages needed. `cryptography` is already installed as a transitive dep of PyJWT. All required libraries are present in `reasoning/.venv/`.

---

## Architecture Patterns

### Recommended Project Structure

```
reasoning/app/
├── auth.py                  # MODIFY: HS256 → RS256/JWKS, PyJWKClient singleton
├── schemas.py               # MODIFY: add WatchlistItem, WatchlistResponse, WatchlistUpdate
├── main.py                  # MODIFY: register watchlist router
└── routers/
    └── watchlist.py         # NEW: GET /watchlist, PUT /watchlist

db/migrations/
└── V8__watchlist.sql        # NEW: user_watchlist + watchlist_defaults tables

reasoning/tests/api/
├── test_auth.py             # MODIFY: update for RS256/JWKS mock
└── test_watchlist.py        # NEW: watchlist endpoint tests
```

### Pattern 1: RS256/JWKS Auth Migration

**What:** Replace PyJWT HS256 decode with `PyJWKClient.get_signing_key_from_jwt()` + `jwt.decode(..., algorithms=["RS256"])`. Create `PyJWKClient` as a module-level singleton (initialized at import time from env var `SUPABASE_JWKS_URL`).

**When to use:** All JWT verification in auth.py going forward.

**Example:**
```python
# Source: PyJWT docs (Context7 /jpadilla/pyjwt) + Supabase docs
import jwt
from jwt import PyJWKClient

# Module-level singleton — created once, cached JWK set reused for 5 minutes
_jwks_url = os.environ["SUPABASE_JWKS_URL"]
_jwks_client = PyJWKClient(
    _jwks_url,
    cache_jwk_set=True,
    lifespan=300,  # 5-minute TTL; Supabase edge caches for 10min so this is safe
)

async def require_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if cred is None:
        raise HTTPException(status_code=401, ...)
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(cred.credentials)
        payload = jwt.decode(
            cred.credentials,
            signing_key,
            algorithms=["RS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=403, detail="Invalid token audience")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token", ...)
    return payload
```

**JWKS URL note:** Supabase official docs show `/auth/v1/.well-known/jwks.json` (verified via Context7 and Supabase signing-keys guide). CONTEXT.md mentions `/auth/v1/jwks` — the correct standard URL is `.well-known/jwks.json`. Verify with actual Supabase project before deploying. Recommend using `.well-known/jwks.json` as it is the documented standard.

**Caching behavior (from source code inspection):**
- `PyJWKClient` has a two-tier cache: JWK Set cache (TTL-based, 5min default) and per-key LRU cache
- When a `kid` is not found in current cached set, it auto-refreshes once from the endpoint
- This handles Supabase key rotation transparently
- Supabase edge caches the JWKS endpoint for 10 minutes — using a 300s TTL in `PyJWKClient` is safe

### Pattern 2: Watchlist Router (Full-Replace PUT)

**What:** GET returns full list with metadata; PUT replaces entire list atomically (DELETE existing + INSERT new in one transaction).

**When to use:** Small bounded collections (max 30 tickers) where atomic replacement is simpler than tracking diffs.

**Example:**
```python
# Source: project pattern from reasoning/app/routers/tickers.py
@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    request: Request,
    payload: dict = Depends(require_auth),
) -> WatchlistResponse:
    user_id = payload["sub"]
    db_engine = request.app.state.db_engine
    tickers = _get_or_seed_watchlist(db_engine, user_id)
    return WatchlistResponse(tickers=tickers)

@router.put("", status_code=204)
async def put_watchlist(
    body: WatchlistUpdate,
    request: Request,
    payload: dict = Depends(require_auth),
) -> None:
    user_id = payload["sub"]
    db_engine = request.app.state.db_engine
    _replace_watchlist(db_engine, user_id, body.tickers)
```

### Pattern 3: First-Login Seeding Logic

**What:** On `GET /watchlist`, if zero rows exist for `user_id`, seed from `watchlist_defaults` before returning. Idempotent — safe to call on every request.

**When to use:** AUTH-05 requirement; decouples seeding from the invite/auth flow.

**Example:**
```python
def _get_or_seed_watchlist(db_engine, user_id: str) -> list[dict]:
    rows = _query_watchlist(db_engine, user_id)
    if not rows:
        defaults = _query_defaults(db_engine)
        if defaults:
            _insert_watchlist_rows(db_engine, user_id, defaults)
            rows = _query_watchlist(db_engine, user_id)
    return rows
```

### Pattern 4: Ticker Validation on PUT

**What:** Before replacing the watchlist, validate all submitted symbols exist in `stock_ohlcv` (symbol column) or `gold_etf_ohlcv` (ticker column). Return 422 with invalid symbols listed.

**When to use:** WTCH-01 — prevents phantom tickers entering the watchlist.

```python
GOLD_TICKERS = {"GLD", "IAU", "SGOL"}  # matches tickers.py constant

def _validate_symbols(db_engine, symbols: list[str]) -> list[str]:
    """Return list of symbols not found in any valid table. Empty = all valid."""
    invalid = []
    for sym in symbols:
        if sym in GOLD_TICKERS:
            # check gold_etf_ohlcv.ticker
        else:
            # check stock_ohlcv.symbol
        ...
    return invalid
```

### Pattern 5: Ticker Metadata — Static Mapping

**What:** WatchlistResponse includes `name` and `asset_type` per ticker. The cleanest source is a static dict in the router (no extra DB query), given VN30 is hardcoded and the ticker universe is small (~31 symbols including GLD).

**When to use:** When the ticker universe is static and known at deploy time.

**Recommendation (Claude's Discretion):** Use a static dict `TICKER_METADATA: dict[str, dict]` defined in the watchlist router module. Keys are symbol strings; values are `{name: str, asset_type: "equity"|"gold_etf"}`. This avoids an extra DB round-trip on every GET and is trivially updatable at rebalance time (same as updating the hardcoded VN30 list).

Alternative (database lookup): Query ticker name from a separate metadata table. Adds complexity for marginal benefit — avoid for now.

### Anti-Patterns to Avoid

- **Initializing PyJWKClient inside `require_auth` function body:** Creates a new HTTP client on every request. Always create it as a module-level singleton.
- **HS256 tests for RS256 auth:** After migration, `test_auth.py` must mock `PyJWKClient.get_signing_key_from_jwt` rather than patching `SUPABASE_JWT_SECRET`. Test the same 5 scenarios (no header, valid, expired, wrong audience, malformed) via a mocked signing key.
- **Cross-DB JOINs:** `user_watchlist` lives on VPS PostgreSQL; Supabase user table is in Supabase Cloud. Never JOIN across these. User identity comes from JWT `sub` claim only.
- **RLS in Supabase Cloud:** The watchlist table is on VPS PostgreSQL, not Supabase. Supabase RLS policies are not applicable. Enforce isolation in application code (`WHERE user_id = ?`).
- **PUT /watchlist without transaction:** DELETE existing + INSERT new must be atomic. If INSERT fails, the user's watchlist should not be empty. Use a single connection/transaction context.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWKS key fetching and caching | Custom HTTP + cache layer | `PyJWKClient` (PyJWT 2.x) | Built-in 2-tier cache, auto-refresh on unknown kid, already installed |
| RSA key parsing from JWK | Manual RSA key construction | `PyJWKClient.get_signing_key_from_jwt()` | Handles `kid` matching, key type dispatch, JWK → cryptography key conversion |
| Supabase invite flow | Custom token/email system | Supabase dashboard "Invite user" | Dashboard handles token generation, email delivery, password-set redirect — zero code |

**Key insight:** The `PyJWKClient` class already handles every edge case of JWKS-based auth: cache expiry, automatic refresh on unknown `kid` (handles key rotation), timeout, custom headers. There is no reason to write a custom JWKS fetching layer.

---

## Common Pitfalls

### Pitfall 1: Wrong JWKS URL Path

**What goes wrong:** Auth fails with `PyJWKClientConnectionError` or empty signing keys list.
**Why it happens:** CONTEXT.md mentions `/auth/v1/jwks` but Supabase official docs specify `/auth/v1/.well-known/jwks.json`. Both may work but the documented standard is `.well-known/jwks.json`.
**How to avoid:** Manually verify the JWKS URL by curling `https://<project>.supabase.co/auth/v1/.well-known/jwks.json` before coding. Use that exact URL in `SUPABASE_JWKS_URL` env var.
**Warning signs:** Empty `keys` array in JWKS response; `PyJWKClientError: The JWKS endpoint did not contain any signing keys`.

### Pitfall 2: PyJWKClient Initialized Per-Request

**What goes wrong:** Slow auth (network fetch on every request), Supabase rate limits hit.
**Why it happens:** If `PyJWKClient` is created inside `require_auth()` body, it creates a new instance (no cache sharing) on every API call.
**How to avoid:** Create `_jwks_client = PyJWKClient(url, cache_jwk_set=True, lifespan=300)` at module level in `auth.py`. One instance for the lifetime of the process.
**Warning signs:** Latency spikes on every authenticated request, JWKS fetch appearing in network logs on every call.

### Pitfall 3: Supabase Invite Email Redirect

**What goes wrong:** User clicks invite email link, lands on wrong page (login page instead of password-set page), cannot complete registration.
**Why it happens:** Supabase invite flow requires the **Site URL** (Authentication > URL Configuration in Supabase dashboard) to be set correctly. The invite email links to `{SITE_URL}/auth/confirm?token=...&type=invite`. If Site URL points to the app root or login page, the user sees a confusing redirect.
**How to avoid:** Set Supabase Site URL to the deployed frontend URL. The Phase 12 frontend must handle the `/auth/confirm` path with `type=invite` to redirect to a password-set form. This is a known edge case flagged in STATE.md — verify during Phase 11 before Phase 12 starts.
**Warning signs:** Invite emails work but user cannot set password; redirect loop after clicking email link.

### Pitfall 4: Watchlist Seeding Race Condition

**What goes wrong:** If two simultaneous requests for the same new user both detect "zero rows" and both insert defaults, the user gets duplicate watchlist entries.
**Why it happens:** SELECT + INSERT is not atomic without a constraint or transaction isolation.
**How to avoid:** Add a `UNIQUE(user_id, symbol)` constraint to `user_watchlist`. The second INSERT will fail silently (ON CONFLICT DO NOTHING). The seeding function uses INSERT ... ON CONFLICT DO NOTHING.
**Warning signs:** Duplicate ticker rows in watchlist; GET /watchlist returning same ticker twice.

### Pitfall 5: test_auth.py Fails After RS256 Migration

**What goes wrong:** All 5 existing `test_auth.py` tests fail because they use HS256 token creation and patch `SUPABASE_JWT_SECRET`.
**Why it happens:** The migration changes `require_auth` to use `PyJWKClient`; the old HS256 test setup no longer matches.
**How to avoid:** Rewrite `test_auth.py` to mock `PyJWKClient.get_signing_key_from_jwt` (return a mock RSA signing key) and use `jwt.encode(..., algorithm="RS256", private_key=...)` with a test RSA key pair. Alternatively, mock at the `_jwks_client` module attribute level.
**Warning signs:** ImportError or mock mismatch errors in test_auth.py; tests passing when they should fail because the mock is too broad.

### Pitfall 6: docker-compose.yml SUPABASE_JWT_SECRET Is No Longer Used

**What goes wrong:** Old env var lingers in docker-compose.yml, misleads future maintainers, or conflicts if auth.py tries to read it.
**Why it happens:** The migration removes the `SUPABASE_JWT_SECRET` reference from auth.py but the env var remains in docker-compose.yml.
**How to avoid:** Remove `SUPABASE_JWT_SECRET` from `docker-compose.yml` reasoning-engine environment block; add `SUPABASE_JWKS_URL`. Update `.env.example` if it exists.
**Warning signs:** Code reviews finding dead env vars; confusion about which var is active.

### Pitfall 7: PUT /watchlist Not Atomic

**What goes wrong:** DELETE succeeds but INSERT fails (e.g., invalid symbol validation fails after delete), leaving user with empty watchlist.
**Why it happens:** Validation should happen before mutation; deletion and insertion should be in one transaction.
**How to avoid:** (1) Validate all symbols before any DB write; (2) wrap DELETE + INSERT in a single SQLAlchemy connection with explicit `conn.execute(...)` calls and `conn.commit()` only on success.
**Warning signs:** User submits an update with one invalid ticker and their entire watchlist disappears.

---

## Code Examples

Verified patterns from official sources:

### RS256 JWT Decode with PyJWKClient

```python
# Source: PyJWT docs (Context7 /jpadilla/pyjwt) — verified against installed jwks_client.py
from jwt import PyJWKClient
import jwt

_jwks_client = PyJWKClient(
    "https://<project>.supabase.co/auth/v1/.well-known/jwks.json",
    cache_jwk_set=True,
    lifespan=300,
)

# In require_auth:
signing_key = _jwks_client.get_signing_key_from_jwt(token_string)
payload = jwt.decode(
    token_string,
    signing_key,            # PyJWK object — PyJWT extracts .key internally
    algorithms=["RS256"],
    audience="authenticated",
)
```

### Supabase JWKS Endpoint (verified)

```text
# Source: Supabase signing-keys guide (Context7 /supabase/supabase)
GET https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json

# Response shape:
{
  "keys": [
    { "kid": "...", "alg": "RS256", "kty": "RSA", "key_ops": ["verify"], "n": "...", "e": "AQAB" }
  ]
}
```

### Flyway V8 Watchlist Schema (recommended design)

```sql
-- V8__watchlist.sql
-- user_watchlist: one row per (user, symbol)
CREATE TABLE user_watchlist (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL,               -- Supabase user UUID (JWT sub)
    symbol      VARCHAR(20) NOT NULL,
    asset_type  VARCHAR(20) NOT NULL
                    CHECK (asset_type IN ('equity', 'gold_etf')),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, symbol)                        -- prevents seeding race + duplicates
);

CREATE INDEX idx_user_watchlist_user ON user_watchlist (user_id);

-- watchlist_defaults: admin-editable seed list
CREATE TABLE watchlist_defaults (
    symbol      VARCHAR(20) PRIMARY KEY,
    asset_type  VARCHAR(20) NOT NULL
                    CHECK (asset_type IN ('equity', 'gold_etf')),
    sort_order  INTEGER     NOT NULL DEFAULT 0
);

-- Seed defaults (VN30 core + GLD)
INSERT INTO watchlist_defaults (symbol, asset_type, sort_order) VALUES
    ('GLD',  'gold_etf', 0),
    ('VNM',  'equity',   1),
    ('VHM',  'equity',   2),
    ('VCB',  'equity',   3),
    ('HPG',  'equity',   4),
    ('MSN',  'equity',   5);
-- Admin can UPDATE/INSERT/DELETE rows without redeploying
```

### Supabase Invite User (dashboard — no code)

```text
# Source: Supabase Auth docs (Context7 /supabase/auth)
# Authentication > Users > Invite user

# OR via service_role API:
POST https://<project>.supabase.co/auth/v1/invite
Authorization: Bearer <SERVICE_ROLE_KEY>
Content-Type: application/json
{ "email": "newuser@example.com" }
```

### Mock Pattern for RS256 test_auth.py

```python
# Pattern for updated test_auth.py — mock at PyJWKClient level
from unittest.mock import MagicMock, patch

def test_auth_valid_token_passes(client):
    mock_signing_key = MagicMock()
    mock_signing_key.key = _TEST_RSA_PUBLIC_KEY  # from test RSA key pair
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        # ... test with RS256-signed token using test private key
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HS256 + shared secret (SUPABASE_JWT_SECRET) | RS256 + JWKS (`PyJWKClient`) | Supabase changed default signing algorithm; projects without legacy secret must use JWKS | auth.py needs rewrite; test_auth.py needs rewrite |
| Supabase HS256 legacy secret | JWK-format asymmetric keys only | Recent Supabase projects | No fallback; JWKS is the only option |

**Deprecated/outdated:**
- `SUPABASE_JWT_SECRET` env var + HS256 decode: No longer valid for this project. User confirmed no plain-text secret is available.
- Patching `os.environ["SUPABASE_JWT_SECRET"]` in tests: Tests must be redesigned to mock `PyJWKClient` after migration.

---

## Open Questions

1. **JWKS URL path: `/auth/v1/jwks` vs `/auth/v1/.well-known/jwks.json`**
   - What we know: CONTEXT.md says `/auth/v1/jwks`; Supabase official docs say `/auth/v1/.well-known/jwks.json` (verified in Context7)
   - What's unclear: Whether Supabase serves both paths or only the standard one
   - Recommendation: Verify by curling the actual project URL before coding. Use `.well-known/jwks.json` as the primary; if `/auth/v1/jwks` also works it is likely a redirect alias. Make the full URL an env var (`SUPABASE_JWKS_URL`) so it can be corrected without a code change.

2. **Ticker metadata for WatchlistResponse (Claude's Discretion)**
   - What we know: GET /watchlist must return `{ symbol, name, asset_type }` per ticker; no DB table currently stores display names
   - What's unclear: Whether to use a static dict or add a `ticker_metadata` DB table
   - Recommendation: **Use a static dict** in the watchlist router. VN30 is hardcoded (31 symbols + GLD = 32 total). A static `TICKER_METADATA` dict avoids an extra DB round-trip and is trivially maintained alongside the hardcoded VN30 list. Add the dict to `watchlist.py` or a constants module.

3. **JWKS client initialization in FastAPI lifespan vs module-level**
   - What we know: Module-level singleton works for most FastAPI apps; lifespan context manager is used for DB/Neo4j/Qdrant
   - What's unclear: Whether PyJWKClient initialization should move into `lifespan()` in `dependencies.py` (consistent with other clients) or stay module-level in `auth.py` (simpler, no dependency injection change needed)
   - Recommendation: **Module-level singleton in `auth.py`** is correct for this case. `PyJWKClient` is stateless infrastructure (no connection pool to tear down) and the lazy-init pattern (initialized on first import, fetches JWKS on first auth request) is appropriate. This avoids changing the lifespan interface and the `require_auth` dependency signature stays the same.

---

## Sources

### Primary (HIGH confidence)

- Context7 `/jpadilla/pyjwt` — PyJWKClient class, `get_signing_key_from_jwt`, caching parameters, RS256 decode pattern
- Context7 `/supabase/supabase` — JWKS endpoint URL (`/auth/v1/.well-known/jwks.json`), JWT verification examples, signing-keys guide
- Context7 `/supabase/auth` — invite user endpoint, GOTRUE_DISABLE_SIGNUP env var, JWT secret config
- Source code inspection: `reasoning/.venv/lib/python3.11/site-packages/jwt/jwks_client.py` — verified two-tier cache behavior, `lifespan=300` default, auto-refresh on unknown kid
- Existing codebase: `reasoning/app/auth.py`, `reasoning/app/routers/tickers.py`, `reasoning/app/schemas.py`, `reasoning/app/dependencies.py`, `reasoning/tests/api/test_auth.py`, `db/migrations/V6-V7`

### Secondary (MEDIUM confidence)

- STATE.md noted edge case: "Supabase invite flow with signups disabled has a known edge case: Site URL must point to password-set page" — flagged as known concern for Phase 11

### Tertiary (LOW confidence)

- CONTEXT.md claim that JWKS URL is `/auth/v1/jwks` (not `/auth/v1/.well-known/jwks.json`) — LOW because it contradicts Supabase official docs; flagged as Open Question 1.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and verified in venv; PyJWKClient source code read directly
- Architecture: HIGH — follows existing project patterns (tickers.py, auth.py) with well-documented PyJWT API
- Pitfalls: HIGH — most are direct consequence of the migration (test rewrite, env var change, JWKS URL); caching and atomicity pitfalls verified from source code
- JWKS URL path: LOW — one discrepancy between CONTEXT.md and official docs; must be verified before coding

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (PyJWT and Supabase Auth APIs are stable; key risk is JWKS URL ambiguity which is resolved by manual verification)
