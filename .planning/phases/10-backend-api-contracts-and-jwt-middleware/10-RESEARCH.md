# Phase 10: Backend API Contracts and JWT Middleware - Research

**Researched:** 2026-03-18
**Domain:** FastAPI JWT authentication, Supabase JWT validation, SQLAlchemy Core window functions, Pydantic v2 response schemas
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase boundary:**
- Secure the reasoning-engine FastAPI service with Supabase JWT validation and add two new read-only endpoints: OHLCV chart data and report history.
- No frontend code, no Supabase project setup (Phase 11), no new database tables.
- Works with existing tables: stock_ohlcv, gold_etf_ohlcv, reports, report_jobs.

**OHLCV endpoint shape:**
- Single unified endpoint: GET /tickers/{symbol}/ohlcv serves both stocks (stock_ohlcv table) and gold (gold_etf_ohlcv table) — API resolves which table internally based on symbol
- Response includes precomputed 50MA and 200MA fields alongside raw OHLCV — frontend just renders, no client-side MA computation
- Time format: Unix timestamp (integer seconds since epoch) — TradingView Lightweight Charts native format, no parsing needed
- Default data range: 52 weeks (1 year) of weekly resolution data
- Response shape per data point: `{ time, open, high, low, close, volume, ma50, ma200 }` (ma50/ma200 may be null for early points without enough history)

**Report history contract:**
- GET /reports/by-ticker/{symbol} with offset pagination: `?page=1&per_page=20`
- Server extracts tier from report_json — frontend receives flat summary, no JSONB parsing on client
- One entry per generation run — group vi+en reports by generated_at timestamp, not separate rows per language
- Each history item includes: `{ report_id, tier, generated_at, verdict }` — verdict is the one-line summary from report_json
- Sort order: newest first (generated_at DESC)

**JWT protection scope:**
- Claude's Discretion — decide which endpoints get the auth wall vs remain public (e.g., /health stays public)
- Auth mechanism locked: Supabase JWT with `audience="authenticated"` via auth.py dependency

**Error response format:**
- Claude's Discretion — keep consistent with existing HTTPException(detail=...) pattern or evolve as needed

### Claude's Discretion

1. Which endpoints get the auth wall (JWT required) vs remain public
2. Whether to keep existing HTTPException(detail=...) or add WWW-Authenticate headers

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFR-03 | FastAPI reasoning-engine validates Supabase JWT on protected endpoints | PyJWT 2.12.1 decode with HS256 + audience="authenticated"; HTTPBearer(auto_error=False) pattern; SUPABASE_JWT_SECRET env var |
| INFR-04 | New GET /tickers/{symbol}/ohlcv endpoint serves chart data | SQLAlchemy Core window functions (func.avg().over()) for MA computation; symbol routing between stock_ohlcv and gold_etf_ohlcv tables; Unix timestamp conversion |
| INFR-05 | New GET /reports/by-ticker/{symbol} endpoint serves report history | SQLAlchemy Core pagination with LIMIT/OFFSET; DISTINCT ON or GROUP BY generated_at for deduplication; JSONB accessor for tier/verdict extraction |
</phase_requirements>

---

## Summary

Phase 10 adds two capabilities to the existing FastAPI reasoning-engine: (1) Supabase JWT validation as a FastAPI dependency injectable on any route, and (2) two new read-only endpoints that serve chart data and report history to the frontend. The codebase already has strong patterns to follow: SQLAlchemy Core with autoload_with=db_engine, Pydantic v2 BaseModel response schemas, HTTPException(detail=...) for errors, and a clean router-per-resource structure.

The JWT layer is straightforward: add PyJWT 2.12.1 to requirements.txt, create reasoning/app/auth.py with a get_current_user dependency using HTTPBearer(auto_error=False), and apply it via Depends() to all new endpoints plus the existing POST /reports/generate endpoint. The /health endpoint stays public. The Supabase JWT uses HS256 and audience="authenticated" — the SUPABASE_JWT_SECRET environment variable is the only new secret needed.

The OHLCV endpoint is the technically interesting piece: computing MA50 and MA200 in-database using SQLAlchemy Core window functions (func.avg().over()), then converting TIMESTAMPTZ to Unix integers in the query response. The report history endpoint is simpler: a grouped query that returns one row per generation run (using MIN(report_id) where language='vi' since both language rows share the same generated_at), extracts tier and verdict from the JSONB report_json column, and returns a paginated list.

**Primary recommendation:** Create auth.py with a single `require_auth` dependency, add a tickers router for OHLCV, extend the reports router with the history endpoint, then apply require_auth to all new routes plus /reports/generate. All MA computation happens in SQL using window functions — no pandas needed.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.12.1 | Decode and verify Supabase HS256 JWTs | Official PyPI package, actively maintained, direct Supabase community use documented |
| fastapi | >=0.115.0 | HTTPBearer security scheme + Depends | Already in project; HTTPBearer provides automatic OpenAPI security docs |
| pydantic | >=2.0.0 | Response schema validation | Already in project; v2 BaseModel used throughout codebase |
| sqlalchemy | >=2.0.0 | Window functions via func.avg().over() for MA computation | Already in project; Core API used for all DB ops |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi.security.HTTPBearer | built-in | Extract Bearer token from Authorization header | Use with auto_error=False to control 401 vs 403 behavior |
| sqlalchemy.func | built-in | func.avg().over(order_by=..., rows=...) for SQL window MA | Use in OHLCV query for server-side MA50/MA200 computation |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT (HS256) | JWKS endpoint (asymmetric) | JWKS adds network call + caching complexity; HS256 with shared secret is acceptable for internal service; Supabase Cloud uses HS256 by default on existing projects |
| SQL window functions for MA | pandas rolling in Python | Pandas requires loading all rows into memory; SQL window keeps computation in DB, returns only computed values |
| Manual pagination with LIMIT/OFFSET | fastapi-pagination library | fastapi-pagination adds dependency for a trivial feature; LIMIT/OFFSET is 3 lines of SQLAlchemy Core |

**Installation:**
```bash
pip install "PyJWT>=2.12.1"
```
(Add to reasoning/requirements.txt)

---

## Architecture Patterns

### Recommended Project Structure

```
reasoning/app/
├── auth.py              # NEW: require_auth dependency (SUPABASE_JWT_SECRET)
├── routers/
│   ├── health.py        # UNCHANGED: stays public
│   ├── reports.py       # MODIFIED: add /by-ticker/{symbol}, apply require_auth to /generate
│   └── tickers.py       # NEW: GET /tickers/{symbol}/ohlcv
├── models/
│   └── tables.py        # UNCHANGED: stock_ohlcv and gold_etf_ohlcv already defined
├── dependencies.py      # UNCHANGED: lifespan, no new env vars beyond SUPABASE_JWT_SECRET
└── main.py              # MODIFIED: register tickers router with prefix /tickers
```

### Pattern 1: Supabase JWT Dependency (auth.py)

**What:** A single reusable FastAPI dependency that validates the Bearer token against the Supabase JWT secret.
**When to use:** Apply as `Depends(require_auth)` to every protected endpoint.

```python
# Source: https://dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf
# and https://pyjwt.readthedocs.io/en/latest/usage.html
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

async def require_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Supabase JWT. Returns decoded payload on success.

    Raises:
        401 — no Authorization header or malformed token
        403 — valid token structure but wrong audience or expired
    """
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    secret = os.environ["SUPABASE_JWT_SECRET"]
    try:
        payload = jwt.decode(
            cred.credentials,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token expired",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token audience",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

**Key detail:** `HTTPBearer(auto_error=False)` returns None when no header is present instead of raising 403, letting us raise 401 ourselves. This is the established FastAPI workaround (confirmed in fastapi/fastapi issues #2026 and #10177).

### Pattern 2: OHLCV Query with Window Function MAs

**What:** SQLAlchemy Core subquery that computes MA50 and MA200 using SQL window functions. Symbol routing logic selects the right table.
**When to use:** The /tickers/{symbol}/ohlcv endpoint handler.

```python
# Source: https://docs.sqlalchemy.org/en/20/core/functions.html
# func.avg().over() — window function with ROWS BETWEEN frame
from sqlalchemy import func, select, MetaData, Table
from datetime import datetime, timezone, timedelta

def _query_ohlcv(db_engine, symbol: str) -> list[dict]:
    metadata = MetaData()
    # Route to correct table based on symbol
    gold_tickers = {"GLD", "IAU", "SGOL"}  # configurable — gold ETF symbols
    if symbol.upper() in gold_tickers:
        tbl = Table("gold_etf_ohlcv", metadata, autoload_with=db_engine)
        sym_col = tbl.c.ticker
    else:
        tbl = Table("stock_ohlcv", metadata, autoload_with=db_engine)
        sym_col = tbl.c.symbol

    # Cutoff: 52 weeks ago
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=52)

    # Window function: AVG over preceding N-1 rows (0-indexed: 49 preceding = 50 rows)
    ma50_expr = func.avg(tbl.c.close).over(
        partition_by=sym_col,
        order_by=tbl.c.data_as_of,
        rows=(-49, 0),  # 50-period: 49 preceding + current
    )
    ma200_expr = func.avg(tbl.c.close).over(
        partition_by=sym_col,
        order_by=tbl.c.data_as_of,
        rows=(-199, 0),  # 200-period: 199 preceding + current
    )

    stmt = (
        select(
            tbl.c.data_as_of,
            tbl.c.open,
            tbl.c.high,
            tbl.c.low,
            tbl.c.close,
            tbl.c.volume,
            ma50_expr.label("ma50"),
            ma200_expr.label("ma200"),
        )
        .where(sym_col == symbol.upper())
        .where(tbl.c.resolution == "weekly")
        .where(tbl.c.data_as_of >= cutoff)
        .order_by(tbl.c.data_as_of.asc())
    )

    with db_engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    result = []
    for row in rows:
        mapping = dict(row._mapping)
        result.append({
            "time": int(mapping["data_as_of"].timestamp()),  # Unix seconds
            "open": float(mapping["open"]) if mapping["open"] is not None else None,
            "high": float(mapping["high"]) if mapping["high"] is not None else None,
            "low": float(mapping["low"]) if mapping["low"] is not None else None,
            "close": float(mapping["close"]),
            "volume": mapping["volume"],
            "ma50": float(mapping["ma50"]) if mapping["ma50"] is not None else None,
            "ma200": float(mapping["ma200"]) if mapping["ma200"] is not None else None,
        })
    return result
```

**Important:** MA values for early rows (fewer than 50/200 prior data points in the 52-week window) will be null because the window frame cannot be satisfied. This is expected behavior per the CONTEXT.md decision.

**Note on window function rows vs range:** The `rows` parameter uses integer offsets, not date intervals. `rows=(-49, 0)` means "49 preceding rows to current row" in the ORDER BY sequence. This is correct for weekly OHLCV data where each row is one week.

### Pattern 3: Report History Query with JSONB Extraction

**What:** Query the reports table returning one entry per generation run by deduplicating on generated_at, extracting tier and verdict from JSONB.
**When to use:** The /reports/by-ticker/{symbol} endpoint handler.

```python
# Source: SQLAlchemy Core text() for JSONB accessor pattern
# (autoload_with reflection works for JSONB columns as Text/JSON type)
from sqlalchemy import select, func, text, distinct, MetaData, Table

def _query_report_history(
    db_engine,
    asset_id: str,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    """Returns (items, total_count)."""
    metadata = MetaData()
    reports = Table("reports", metadata, autoload_with=db_engine)

    offset = (page - 1) * per_page

    # One row per run: use MIN(report_id) for the vi language row
    # (vi and en share the same generated_at; we pick vi for report_id)
    # JSONB accessor: report_json->>'entry_quality'->>'tier'
    # In SQLAlchemy Core, use text() for JSONB path operators
    stmt = (
        select(
            func.min(reports.c.report_id).label("report_id"),
            reports.c.generated_at,
            text("MIN(report_json->'entry_quality'->>'tier') AS tier"),
            text("MIN(report_json->'entry_quality'->>'narrative') AS verdict"),
        )
        .where(reports.c.asset_id == asset_id)
        .group_by(reports.c.generated_at)
        .order_by(reports.c.generated_at.desc())
        .limit(per_page)
        .offset(offset)
    )

    count_stmt = (
        select(func.count(distinct(reports.c.generated_at)))
        .where(reports.c.asset_id == asset_id)
    )

    with db_engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        total = conn.execute(count_stmt).scalar_one()

    items = []
    for row in rows:
        mapping = dict(row._mapping)
        items.append({
            "report_id": mapping["report_id"],
            "generated_at": mapping["generated_at"].isoformat(),
            "tier": mapping["tier"],
            "verdict": mapping["verdict"],
        })
    return items, total
```

**Alternative approach for JSONB:** If text() SQL injection concern exists, use `column('report_json')` with cast or rely on the fact that `report_json` is autoloaded as a JSON type and access via Python after fetching. The text() approach is fine here since no user input flows into the JSONB accessor path.

### Pattern 4: Pydantic v2 Response Schemas

**What:** Declare response_model on each endpoint so FastAPI generates OpenAPI docs automatically.
**When to use:** All new endpoints must have Pydantic schemas per INFR-04/INFR-05.

```python
from pydantic import BaseModel
from typing import Optional

class OHLCVPoint(BaseModel):
    time: int           # Unix timestamp (seconds)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
    ma50: Optional[float] = None
    ma200: Optional[float] = None

class OHLCVResponse(BaseModel):
    symbol: str
    data: list[OHLCVPoint]

class ReportHistoryItem(BaseModel):
    report_id: int
    generated_at: str   # ISO 8601 string
    tier: str           # "Favorable" | "Neutral" | "Cautious" | "Avoid"
    verdict: str        # one-line narrative

class ReportHistoryResponse(BaseModel):
    symbol: str
    page: int
    per_page: int
    total: int
    items: list[ReportHistoryItem]
```

### Anti-Patterns to Avoid

- **Using HTTPBearer without auto_error=False:** Default HTTPBearer raises 403 when no Authorization header is present. 403 is semantically wrong for missing credentials — 401 is correct. Always use `HTTPBearer(auto_error=False)` and raise 401 manually.
- **Applying Depends(require_auth) globally via app.dependency_overrides or middleware:** This would break /health. Apply at the router or individual route level.
- **Computing MAs in Python after fetching all rows:** The stock_ohlcv table contains years of data. Only fetch the 52-week window and compute MAs in SQL to avoid pulling unnecessary rows.
- **Returning TIMESTAMPTZ as-is from SQLAlchemy:** TradingView Lightweight Charts requires Unix integer timestamps. Convert in the DB helper, not in the router.
- **Using report_id directly for deduplication:** Two rows exist per generation run (vi + en). Group by generated_at and use MIN(report_id) to select the canonical row.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT decode + signature verify | Custom HMAC comparison | `jwt.decode()` from PyJWT 2.12.1 | Handles exp claim, aud claim, signature verification, and all edge cases; PyJWT errors map cleanly to 401/403 |
| Moving average computation | Python loop over fetched rows | `func.avg().over(rows=...)` in SQLAlchemy | SQL window functions run in-DB; no need to fetch 200+ rows just to compute MA200 |
| Bearer token extraction | Manual header parsing | `HTTPBearer` from fastapi.security | Handles "Bearer " prefix stripping, malformed header cases, and integrates with OpenAPI docs |
| Pagination math | Custom offset calculation | `(page - 1) * per_page` as OFFSET | Simple arithmetic — only 1 line, no library needed; fastapi-pagination is overkill here |

**Key insight:** JWT validation is a solved problem with well-known edge cases (clock skew on exp, missing aud, malformed base64). PyJWT handles all of them; any custom implementation will miss some.

---

## Common Pitfalls

### Pitfall 1: HTTPBearer Returns 403 for Missing Header

**What goes wrong:** A request with no Authorization header receives 403 Forbidden instead of 401 Unauthorized. The success criteria require that `/reports/*` with no header returns 401.
**Why it happens:** FastAPI's HTTPBearer raises HTTPException(status_code=403) by default when credentials are absent — a known FastAPI bug (issues #2026, #10177).
**How to avoid:** Instantiate with `HTTPBearer(auto_error=False)` and raise 401 manually when `cred is None`.
**Warning signs:** Test returns 403 for no-header case when 401 is expected.

### Pitfall 2: MA Window Frame Size vs Data Range Mismatch

**What goes wrong:** MA200 returns None for all 52 weeks because the window function only sees 52 rows of data (52 weeks), which is not enough for a 200-period MA.
**Why it happens:** SQL window functions apply over the result set, not the full table. If you filter to 52 weeks first and then compute MA200, there are never 200 rows available.
**How to avoid:** Either (a) fetch more rows than displayed for MA computation using a CTE/subquery — compute MA over a larger window then filter the display range — or (b) accept that MA200 will be null for most of the 52-week range (which the CONTEXT.md decision already accepts). The decision is option (b): `ma50/ma200 may be null for early points without enough history`.
**Warning signs:** MA200 is always null in the response.

### Pitfall 3: asset_id Format Mismatch

**What goes wrong:** Query returns no results because asset_id in reports table is stored as `"TICKER:asset_type"` (e.g. "VHM:equity") but the endpoint receives just a symbol like "VHM".
**Why it happens:** The reports table uses `asset_id = f"{ticker}:{asset_type}"` (see storage.py). The new /reports/by-ticker/{symbol} endpoint gets only the symbol.
**How to avoid:** Use `LIKE` or `ILIKE` filter: `reports.c.asset_id.like(f"{symbol.upper()}:%")`, or use the startswith approach. Confirm with the actual stored data format.
**Warning signs:** Empty results for known symbols.

### Pitfall 4: SUPABASE_JWT_SECRET Not in docker-compose.yml

**What goes wrong:** Container fails to start or raises KeyError at runtime because SUPABASE_JWT_SECRET is read with `os.environ["SUPABASE_JWT_SECRET"]` which raises on missing key.
**Why it happens:** The existing docker-compose.yml environment block for reasoning-engine must be updated to pass the new secret.
**How to avoid:** Add `SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET}` to docker-compose.yml reasoning-engine environment, and add it to the .env file. Read with `os.environ["SUPABASE_JWT_SECRET"]` (not .get) so startup fails loudly rather than silently.
**Warning signs:** Service starts but auth dependency raises KeyError on first authenticated request.

### Pitfall 5: Numeric Type from SQLAlchemy Autoload

**What goes wrong:** OHLCV prices come back as `Decimal` objects from PostgreSQL NUMERIC columns. Pydantic float fields accept Decimal but JSON serialization may not.
**Why it happens:** SQLAlchemy returns `Decimal` for NUMERIC columns. FastAPI's JSONResponse uses Python's json.dumps which does not handle Decimal.
**How to avoid:** Explicitly convert to `float()` in the DB helper before returning. Already demonstrated in the code example above.
**Warning signs:** `TypeError: Object of type Decimal is not JSON serializable` in runtime logs.

### Pitfall 6: Router Registration Order for /reports/by-ticker/{symbol}

**What goes wrong:** FastAPI matches `GET /reports/by-ticker/VHM` as `GET /reports/{job_id}` with job_id="by-ticker", returning 422 (invalid int).
**Why it happens:** The existing reports router has `GET /{job_id}` as a catch-all. FastAPI route matching is order-dependent — earlier routes win.
**How to avoid:** Register `/by-ticker/{symbol}` BEFORE `/{job_id}` in the router. This is the same issue noted in reports.py for the `/stream/{job_id}` route — it's already documented as `IMPORTANT` in the existing code.
**Warning signs:** 422 with detail "value is not a valid integer" when calling /reports/by-ticker/{symbol}.

---

## Code Examples

### Endpoint Registration Pattern

```python
# reasoning/app/main.py — add tickers router
from reasoning.app.routers import health, reports, tickers

app.include_router(tickers.router, prefix="/tickers", tags=["tickers"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
```

```python
# reasoning/app/routers/tickers.py — OHLCV endpoint
from fastapi import APIRouter, Depends, Request
from reasoning.app.auth import require_auth

router = APIRouter()

@router.get("/{symbol}/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str,
    request: Request,
    _: dict = Depends(require_auth),
) -> OHLCVResponse:
    db_engine = request.app.state.db_engine
    data = _query_ohlcv(db_engine, symbol)
    return OHLCVResponse(symbol=symbol.upper(), data=data)
```

### Report History Endpoint (in reports.py, registered before /{job_id})

```python
# IMPORTANT: must be registered before @router.get("/{job_id}")
@router.get("/by-ticker/{symbol}", response_model=ReportHistoryResponse)
async def get_report_history(
    symbol: str,
    page: int = 1,
    per_page: int = 20,
    request: Request = ...,
    _: dict = Depends(require_auth),
) -> ReportHistoryResponse:
    db_engine = request.app.state.db_engine
    asset_id_prefix = symbol.upper()
    items, total = _query_report_history(db_engine, asset_id_prefix, page, per_page)
    return ReportHistoryResponse(
        symbol=symbol.upper(),
        page=page,
        per_page=per_page,
        total=total,
        items=items,
    )
```

### Applying require_auth to Existing /reports/generate

```python
# Add Depends(require_auth) to the existing generate() endpoint signature
@router.post("/generate", status_code=202)
async def generate(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    _: dict = Depends(require_auth),   # ADD THIS
) -> JSONResponse:
    ...
```

### SUPABASE_JWT_SECRET in docker-compose.yml

```yaml
reasoning-engine:
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    NEO4J_URI: bolt://neo4j:7687
    NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    QDRANT_HOST: qdrant
    QDRANT_PORT: "6333"
    QDRANT_API_KEY: ${QDRANT_API_KEY}
    GEMINI_API_KEY: ${GEMINI_API_KEY}
    SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET}   # ADD THIS
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-jose (archived) | PyJWT 2.12.1 | python-jose went unmaintained ~2023 | PyJWT is the maintained choice; python-jose is not recommended |
| HS256 shared secret (Supabase default) | ES256 asymmetric (new Supabase CLI default) | Supabase CLI v2.71.1 (2025) | Existing Supabase Cloud projects still use HS256; new CLI-initialized projects default to ES256. Since this is an existing Supabase Cloud project, HS256 with JWT_SECRET is correct |
| fastapi.security.OAuth2PasswordBearer | HTTPBearer for token-only flows | Always available | OAuth2PasswordBearer adds a /token URL concept that doesn't apply here — use HTTPBearer directly |

**Deprecated/outdated:**
- python-jose: No longer maintained; PyJWT is the correct choice
- `jwt.decode(token, secret, algorithms=["HS256"])` without `audience=` argument: Will not verify the `aud` claim — must pass `audience="authenticated"` explicitly

---

## Open Questions

1. **Which gold ETF symbols route to gold_etf_ohlcv vs stock_ohlcv?**
   - What we know: The tables have different key columns (ticker vs symbol). The context mentions "GLD" as the default gold ticker.
   - What's unclear: The complete list of valid gold symbols the endpoint should recognize as gold-routed.
   - Recommendation: Hardcode a small set (e.g. `{"GLD", "IAU", "SGOL"}`) or derive from a distinct query on gold_etf_ohlcv at startup. A simple set constant in the router is sufficient for v3.0.

2. **asset_id format for report history queries**
   - What we know: storage.py formats asset_id as `f"{ticker}:{asset_type}"` (e.g. "VHM:equity", "GLD:gold").
   - What's unclear: Whether a symbol like "VHM" could appear with multiple asset_types (e.g. VHM:equity and VHM:fund).
   - Recommendation: Use `asset_id LIKE '{symbol.upper()}:%'` to match regardless of asset_type. Confirm with actual data.

3. **Verdict field truncation**
   - What we know: The verdict is the narrative from report_json->entry_quality->narrative, which may be long (LLM-generated text).
   - What's unclear: Whether to truncate to a fixed length for the history list.
   - Recommendation: Return full narrative for now — the frontend will handle display truncation. Keep the API contract simple.

---

## Sources

### Primary (HIGH confidence)
- PyJWT 2.12.1 official docs (https://pyjwt.readthedocs.io/en/latest/usage.html) — HS256 decode, audience validation, exception types
- SQLAlchemy 2.0 official docs (https://docs.sqlalchemy.org/en/20/core/functions.html) — func.avg().over() window function with rows parameter
- FastAPI official docs (https://fastapi.tiangolo.com/reference/security/) — HTTPBearer, HTTPAuthorizationCredentials
- Supabase discussions (https://github.com/orgs/supabase/discussions/4762) — audience claim confirmed as "authenticated"
- Project codebase — exact table schemas from V2__stock_data.sql, V3__gold_data.sql, V6__reports.sql, V7__report_jobs.sql; existing patterns from reports.py, storage.py, report_schema.py

### Secondary (MEDIUM confidence)
- DEV Community article (https://dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf) — complete FastAPI implementation verified against PyJWT docs
- FastAPI GitHub issue #2026 / #10177 — HTTPBearer 401 vs 403 behavior, auto_error=False workaround
- Supabase self-hosting docs (https://supabase.com/docs/guides/self-hosting/self-hosted-auth-keys) — JWT_SECRET env var name for self-hosted; audience="authenticated" confirmed

### Tertiary (LOW confidence)
- None — all critical claims verified with primary or secondary sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyJWT 2.12.1 confirmed on PyPI (released 2026-03-13); all other libraries already in project
- Architecture: HIGH — based on direct reading of existing codebase patterns and official framework docs
- Pitfalls: HIGH — HTTPBearer 401/403 issue confirmed in official FastAPI GitHub; route ordering pitfall confirmed in existing codebase comments; Decimal serialization is a well-known SQLAlchemy behavior

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (30 days — stable libraries)
