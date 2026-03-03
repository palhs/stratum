# Phase 2: Data Ingestion Pipeline - Research

**Researched:** 2026-03-03
**Domain:** Data pipeline orchestration — vnstock (Vietnamese stocks), FRED (macroeconomic), yfinance (gold ETF), World Gold Council scraping, FastAPI sidecar, n8n scheduling, PostgreSQL ingestion, pre-computed structure markers
**Confidence:** HIGH (core stack), MEDIUM (WGC scraping approach), HIGH (patterns and pitfalls)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Stock Universe & vnstock Scope**
- Stock universe: VN30 index components + user's Supabase watchlist
- Fundamental data: core valuation (P/E, P/B, EPS, market cap) + profitability (ROE, ROA, revenue growth, net margin)
- OHLCV storage: single `stock_ohlcv` table with `resolution` column ('weekly'/'monthly') — not separate tables
- vnstock integration: dedicated sidecar Python container (FastAPI) with pinned vnstock version, called by n8n via HTTP Request node
- Historical backfill: 5 years on first run for Vietnamese stocks

**Gold Data Sourcing**
- Gold spot price: FRED GOLDAMGBD228NLBM series (London fix, USD)
- Gold ETF data: yfinance for GLD ETF OHLCV with volume (added to the sidecar container)
- Gold ETF flows + central bank buying: web scraping World Gold Council Goldhub pages
- Historical backfill: 10 years for gold data
- WGC scraping runs monthly (matches quarterly publication cadence), gold price and GLD run weekly

**Pipeline Scheduling & Alerting**
- Cadence: weekly for all sources, running Sunday night Vietnam time (Asia/Ho_Chi_Minh timezone)
- WGC scraping: monthly cadence (separate from weekly runs)
- Failure alerts: Telegram bot notification via n8n Telegram node
- Retry behavior: 3 retries with exponential backoff (1min, 5min, 15min) before alerting
- Anomaly detection (DATA-09): vnstock row-count >50% deviation from 4-week moving average triggers Telegram alert but does NOT block ingestion
- Every pipeline run logged to `pipeline_run_log` table (already exists from Phase 1)

**Structure Marker Definitions**
- Drawdown: compute BOTH full-history ATH drawdown and 52-week high drawdown for each asset
- Valuation percentiles: rolling window matches backfill period per asset (5 years for stocks, 10 years for gold)

### Claude's Discretion
- Sidecar scope: whether gold/FRED data routes through the Python sidecar or uses n8n HTTP nodes directly
- MA set selection for structure markers
- Structure marker recompute strategy (full vs incremental)
- Publication lag modeling approach (metadata columns vs `data_as_of` alone)
- PostgreSQL table design for new data tables (following existing `data_as_of` + `ingested_at` convention)
- n8n workflow structure and organization

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | System ingests Vietnamese stock OHLCV data (weekly/monthly) via vnstock with version pinning and error handling | vnstock==3.2.3, `stock.quote.history()` with VCI source, FastAPI endpoint wrapping with try/except, single `stock_ohlcv` table |
| DATA-02 | System ingests Vietnamese stock fundamental data (P/E, P/B, EPS, etc.) via vnstock | `stock.finance.ratio()` and `finance.balance_sheet()` via VCI/KBS sources; TCBS financial ratios broken as of 2025 |
| DATA-03 | System ingests gold price data (weekly/monthly) from available free-tier sources | FRED GOLDAMGBD228NLBM via direct REST API call from sidecar; yfinance GLD ETF via `yf.download("GLD", interval="1wk")` |
| DATA-04 | System ingests gold ETF flow data and central bank buying data from World Gold Council | WGC Goldhub is JS-rendered; Playwright network-intercept approach recommended; monthly Excel download as fallback |
| DATA-05 | System ingests macroeconomic indicators (GDP, inflation, unemployment, interest rates) from FRED | FRED REST API `/fred/series/observations`; series: GDP, CPIAUCSL, UNRATE, FEDFUNDS; `date` field = period covered = `data_as_of` |
| DATA-06 | System pre-computes structure markers (moving averages, drawdown from ATH, valuation percentiles) during ingestion and stores in PostgreSQL | pandas `rolling().mean()`, `expanding().max()` for ATH, `rolling().quantile()` for percentiles; stored in separate `structure_markers` table |
| DATA-07 | Every ingested data row includes `data_as_of` and `ingested_at` timestamps | Established convention from Phase 1 V1 migration; all new Flyway migrations must follow this pattern |
| DATA-08 | System logs every pipeline run to `pipeline_run_log` table with success/failure status | Table already exists from Phase 1; sidecar returns row count, n8n writes log record via Postgres node |
| DATA-09 | System detects anomalous row counts from vnstock (>50% deviation from 4-week moving average) and flags them | Computed in sidecar Python code post-fetch; deviation check against historical 4-week average stored in DB; alert-only, does not block ingestion |
</phase_requirements>

---

## Summary

Phase 2 builds the complete data ingestion pipeline on top of the Phase 1 infrastructure foundation. The architecture is well-defined: a Python FastAPI sidecar container handles all data fetching that requires Python libraries (vnstock, yfinance, FRED, and WGC scraping), while n8n orchestrates scheduling, retry logic, error routing, and database writes via its Postgres node. The sidecar joins the existing `ingestion` Docker network as a new service under the `ingestion` profile.

The primary technical risk is the World Gold Council Goldhub scraping. Goldhub is a JavaScript-rendered site with no public API. The recommended approach is Playwright (Python async) with network request interception to capture underlying JSON/CSV payloads — this is more reliable than parsing rendered HTML and survives minor page redesigns. Because this runs monthly and the data changes quarterly, a simple Playwright script that downloads the monthly Excel file is a viable alternative that trades fragility risk for maintenance simplicity.

The FRED and vnstock components are the most straightforward: both have well-documented Python interfaces, clear data structures, and the `date` field in FRED observations maps directly to `data_as_of` (the period the observation covers, not the API call date). Structure marker pre-computation using pandas rolling/expanding functions is standard, deterministic, and fast at VN30 scale — full recompute on each weekly run is the right call.

**Primary recommendation:** Build the sidecar as a single FastAPI service with one endpoint per data source. Route all Python-library-dependent fetching through the sidecar (vnstock, yfinance, FRED via fredapi, WGC via Playwright). n8n calls each endpoint in sequence via HTTP Request node, handles retry/backoff via built-in retry settings, and writes results to PostgreSQL via the native Postgres node. This keeps n8n as the orchestrator and the sidecar as a pure data fetcher.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vnstock | 3.2.3 | Vietnamese stock OHLCV + fundamentals | Official library; `vnstock3` is deprecated (merged Jan 2025) |
| yfinance | 0.2.x | GLD ETF OHLCV with volume | De-facto standard for Yahoo Finance data; `Ticker.history()` supports weekly/monthly intervals |
| fredapi | 0.5.x | FRED economic series | Official Python wrapper; cleaner than raw REST; handles pagination |
| FastAPI | 0.115.x | Python sidecar REST API | Production-grade, async, auto-docs; standard n8n sidecar pattern |
| pandas | 2.x | Structure marker computation | Required for rolling/expanding calculations; already a vnstock dependency |
| playwright | 1.x | WGC Goldhub scraping | Handles JS-rendered sites; built-in network interception; no external driver needed |
| psycopg2-binary | 2.9.x | PostgreSQL client for sidecar | Standard Python/PostgreSQL adapter; needed if sidecar writes directly |
| sqlalchemy | 2.x | ORM/upsert for sidecar writes | Supports `ON CONFLICT DO UPDATE` for idempotent upserts |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pangres | latest | DataFrame → PostgreSQL upsert | If batch DataFrame upserts are needed; handles ON CONFLICT cleanly |
| uvicorn | 0.x | ASGI server for FastAPI | Standard FastAPI deployment server |
| httpx | 0.x | Async HTTP in sidecar | If async HTTP calls needed inside sidecar (e.g., FRED REST directly) |
| python-dotenv | 1.x | Load .env in sidecar | Consistent with project .env pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright for WGC | Selenium | Playwright is 35-45% faster, bundles browsers (no chromedriver), better network interception |
| Playwright for WGC | requests + BeautifulSoup | WGC is JS-rendered — requests alone cannot access chart data; only works if Excel download URL is static |
| fredapi | Direct FRED REST | fredapi is a thin wrapper that simplifies pagination and key handling; minimal overhead |
| FastAPI sidecar | n8n Python Code node | Code node has 30s timeout limit and restricted imports; not suitable for vnstock + Playwright |
| sqlalchemy upsert | pangres | Both work; sqlalchemy is already in the ecosystem; pangres adds a dependency for marginal convenience |

**Installation:**
```bash
# requirements.txt for Python sidecar
vnstock==3.2.3
yfinance>=0.2.48
fredapi>=0.5.2
fastapi>=0.115.0
uvicorn>=0.30.0
playwright>=1.47.0
pandas>=2.2.0
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.0
python-dotenv>=1.0.0

# After building container: install playwright browsers
playwright install chromium
```

---

## Architecture Patterns

### Recommended Project Structure

```
sidecar/
├── app/
│   ├── main.py              # FastAPI app, router registration
│   ├── routers/
│   │   ├── vnstock.py       # POST /ingest/vnstock/ohlcv, POST /ingest/vnstock/fundamentals
│   │   ├── gold.py          # POST /ingest/gold/fred-price, POST /ingest/gold/gld-etf
│   │   ├── fred.py          # POST /ingest/fred/indicators
│   │   └── wgc.py           # POST /ingest/wgc/etf-flows (Playwright)
│   ├── services/
│   │   ├── vnstock_service.py
│   │   ├── gold_service.py
│   │   ├── fred_service.py
│   │   └── wgc_service.py
│   ├── db.py                # SQLAlchemy engine, session
│   └── models.py            # SQLAlchemy table models
├── requirements.txt
└── Dockerfile

db/migrations/
├── V1__initial_schema.sql   # Phase 1 (existing)
├── V2__stock_ohlcv.sql      # Phase 2: stock_ohlcv, stock_fundamentals
├── V3__gold_data.sql        # Phase 2: gold_price, gold_etf_ohlcv, gold_wgc_flows
├── V4__fred_indicators.sql  # Phase 2: fred_indicators
└── V5__structure_markers.sql # Phase 2: structure_markers
```

### Pattern 1: FastAPI Endpoint per Data Source

**What:** Each ingestion source gets a dedicated POST endpoint. The endpoint fetches, validates, upserts to PostgreSQL, runs anomaly checks, and returns a summary `{rows_ingested, data_as_of, status}`.

**When to use:** Always — one endpoint per source keeps n8n workflows independently triggerable and testable.

**Example:**
```python
# Source: FastAPI official docs + project convention
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date

class IngestRequest(BaseModel):
    start_date: date
    end_date: date
    symbols: list[str] | None = None  # None = use VN30

class IngestResponse(BaseModel):
    status: str           # "success" | "partial" | "failure"
    rows_ingested: int
    data_as_of: date
    error_message: str | None = None
    anomaly_detected: bool = False

@app.post("/ingest/vnstock/ohlcv", response_model=IngestResponse)
async def ingest_vnstock_ohlcv(req: IngestRequest):
    try:
        df = fetch_vnstock_ohlcv(req.symbols or get_vn30_symbols(), req.start_date, req.end_date)
        rows = upsert_ohlcv(df)
        anomaly = check_row_count_anomaly(rows, pipeline="stock_ohlcv")
        return IngestResponse(status="success", rows_ingested=rows,
                              data_as_of=req.end_date, anomaly_detected=anomaly)
    except VnstockAPIError as e:
        raise HTTPException(status_code=502, detail=f"vnstock API error: {e}")
    except VnstockEmptyResult:
        raise HTTPException(status_code=204, detail="vnstock returned empty result")
```

### Pattern 2: vnstock Data Fetching

**What:** Use VCI source for OHLCV and historical data. Use KBS source for financial ratios (TCBS financials are broken as of 2025). Fetch VN30 symbol list dynamically via `Listing.symbols_by_group('VN30')`.

**Example:**
```python
# Source: Context7 /thinh-vu/vnstock
from vnstock import Vnstock, Listing

def get_vn30_symbols() -> list[str]:
    lst = Listing(source="vci")
    df = lst.symbols_by_group(group="VN30")
    return df["symbol"].tolist()

def fetch_vnstock_ohlcv(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        stock = Vnstock().stock(symbol=sym, source='VCI')
        # interval '1W' for weekly, '1M' for monthly
        df = stock.quote.history(start=start, end=end, interval='1W')
        df['symbol'] = sym
        df['resolution'] = 'weekly'
        frames.append(df)
    return pd.concat(frames, ignore_index=True)

def fetch_vnstock_fundamentals(symbols: list[str]) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        stock = Vnstock().stock(symbol=sym, source='VCI')
        # ratio() returns PE, PB, EPS, ROE, ROA, etc.
        df = stock.finance.ratio(period='year', lang='en', dropna=True)
        df['symbol'] = sym
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
```

### Pattern 3: FRED Data with Correct data_as_of

**What:** The FRED API `date` field on each observation represents the **period the data covers** — this is `data_as_of`, not the ingestion date. For quarterly GDP, `date="2024-10-01"` means Q4 2024. Store `date` as `data_as_of`, `NOW()` as `ingested_at`.

**Example:**
```python
# Source: FRED API docs (fred.stlouisfed.org/docs/api/fred/)
import fredapi

FRED_SERIES = {
    "GDP": {"frequency": "q", "description": "US GDP quarterly"},
    "CPIAUCSL": {"frequency": "m", "description": "US CPI monthly"},
    "UNRATE": {"frequency": "m", "description": "US Unemployment Rate"},
    "FEDFUNDS": {"frequency": "m", "description": "Federal Funds Rate"},
    "GOLDAMGBD228NLBM": {"frequency": "d", "description": "Gold London Fix USD"},
}

def fetch_fred_series(series_id: str, start: str, end: str) -> pd.DataFrame:
    fred = fredapi.Fred(api_key=os.environ["FRED_API_KEY"])
    s = fred.get_series(series_id, observation_start=start, observation_end=end)
    df = s.reset_index()
    df.columns = ["data_as_of", "value"]
    df["series_id"] = series_id
    df["ingested_at"] = pd.Timestamp.now(tz="UTC")
    # CRITICAL: data_as_of is the period the observation covers,
    # NOT the date we fetched it
    return df.dropna(subset=["value"])
```

### Pattern 4: yfinance GLD ETF Data

**What:** Use `yf.Ticker("GLD").history()` with `interval="1wk"` for weekly OHLCV + volume. Gold ETF volume is a demand proxy.

**Example:**
```python
# Source: Context7 /websites/ranaroussi_github_io
import yfinance as yf

def fetch_gld_etf(start: str, end: str, interval: str = "1wk") -> pd.DataFrame:
    ticker = yf.Ticker("GLD")
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df["symbol"] = "GLD"
    df["data_as_of"] = df["date"].dt.normalize()
    df["ingested_at"] = pd.Timestamp.now(tz="UTC")
    return df[["symbol", "data_as_of", "open", "high", "low", "close", "volume", "ingested_at"]]
```

### Pattern 5: Structure Markers Pre-computation

**What:** Compute moving averages, ATH drawdown, 52-week drawdown, and valuation percentiles using pandas rolling/expanding windows. Store in a `structure_markers` table keyed by `(symbol, resolution, data_as_of)`.

**When to use:** After each successful OHLCV/fundamentals ingest run. Full recompute is correct at VN30 scale (~30 symbols × 5 years of weekly data ≈ 7,800 rows).

**Example:**
```python
# Source: pandas docs (pandas.pydata.org) + WebSearch verification
import pandas as pd

def compute_structure_markers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: stock_ohlcv DataFrame sorted by (symbol, data_as_of) ASC
    Output: structure_markers DataFrame
    """
    results = []
    for symbol, grp in df.sort_values("data_as_of").groupby("symbol"):
        g = grp.set_index("data_as_of").sort_index()
        close = g["close"]

        # Moving averages — MA set: 10wk, 20wk, 50wk (entry timing context)
        # 10wk ≈ 2.5 months (short-term trend), 20wk ≈ 5 months (medium),
        # 50wk ≈ 1 year (structural trend)
        g["ma_10w"] = close.rolling(10, min_periods=8).mean()
        g["ma_20w"] = close.rolling(20, min_periods=16).mean()
        g["ma_50w"] = close.rolling(50, min_periods=40).mean()

        # Full-history ATH drawdown
        ath = close.expanding().max()
        g["drawdown_from_ath"] = (close / ath) - 1.0

        # 52-week high drawdown (52 weeks = 52 weekly bars)
        high_52w = close.rolling(52, min_periods=26).max()
        g["drawdown_from_52w_high"] = (close / high_52w) - 1.0

        # Valuation percentile (rolling window = backfill period)
        # 5 years × 52 weeks = 260 bars for stocks
        g["close_pct_rank"] = close.rolling(260, min_periods=52).rank(pct=True)

        g["symbol"] = symbol
        results.append(g.reset_index())

    return pd.concat(results, ignore_index=True)
```

### Pattern 6: Row-Count Anomaly Detection

**What:** After each vnstock ingest, compare the row count to the 4-week moving average of previous successful runs. If deviation > 50%, send Telegram alert but continue ingestion.

**Example:**
```python
def check_row_count_anomaly(new_row_count: int, pipeline: str,
                             db_session) -> bool:
    """
    Returns True if anomaly detected. Alert is sent by caller.
    Does NOT raise — anomaly detection must not block ingestion.
    """
    # Fetch last 4 successful runs for this pipeline
    result = db_session.execute(
        text("""
            SELECT AVG(rows_ingested) as avg_rows
            FROM (
                SELECT rows_ingested
                FROM pipeline_run_log
                WHERE pipeline_name = :pipeline
                  AND status = 'success'
                  AND rows_ingested IS NOT NULL
                ORDER BY run_at DESC
                LIMIT 4
            ) recent
        """),
        {"pipeline": pipeline}
    ).fetchone()

    if result.avg_rows is None or result.avg_rows == 0:
        return False  # Insufficient history — skip check

    deviation = abs(new_row_count - result.avg_rows) / result.avg_rows
    return deviation > 0.50
```

### Pattern 7: n8n Error Workflow with Telegram Alert

**What:** A dedicated n8n "Error Handler" workflow uses the `Error Trigger` node and sends formatted messages to Telegram. Each data pipeline workflow sets this as its error workflow in settings.

**Structure:**
```
Error Trigger → Set (format message) → Telegram node
```

**Telegram message fields to include:**
- Workflow name: `{{ $('Error Trigger').first().json.workflow.name }}`
- Error message: `{{ $('Error Trigger').first().json.execution.error.message }}`
- Failed node: `{{ $('Error Trigger').first().json.execution.lastNodeExecuted }}`
- Timestamp: `{{ $now.toISO() }}`

### Pattern 8: n8n Retry Configuration

**What:** n8n has built-in per-node retry settings (up to 5 retries, with exponential backoff option). For the sidecar HTTP Request nodes, enable retry with 3 max tries. For longer delays (1min, 5min, 15min per the user decision), implement a custom loop using a Code node with `Wait` nodes between iterations.

**Important:** The built-in retry max delay is capped at 5,000ms (5 seconds). For delays of 1min/5min/15min as specified, you MUST use the custom loop pattern with `Wait` nodes.

**Custom 3-retry pattern:**
```javascript
// Code node: compute delay for current attempt
const attempt = $input.first().json.attempt || 1;
const delays = [60, 300, 900]; // seconds: 1min, 5min, 15min
const delay = delays[attempt - 1] || 900;
return [{ json: { attempt, delay_seconds: delay } }];
```

### Anti-Patterns to Avoid

- **Routing WGC scraping through n8n HTTP nodes:** Goldhub is JS-rendered. n8n HTTP Request node uses curl-like requests — it cannot execute JavaScript. WGC MUST go through the Playwright-enabled sidecar.
- **Using TCBS source for financial ratios in vnstock:** TCBS financial ratio endpoint is broken as of 2025. Use VCI or KBS source.
- **Storing ingestion timestamp as data_as_of for FRED:** The FRED `date` field = the period covered (e.g., "2024-01-01" for January unemployment). Storing `NOW()` as `data_as_of` breaks downstream reasoning nodes.
- **Computing structure markers in LangGraph:** Per project requirements, LangGraph reads pre-computed markers — it never computes them. Computing them at read time would violate INFRA-02 and slow the reasoning pipeline.
- **Separate tables per resolution for OHLCV:** User confirmed single table with `resolution` column. Do not create `stock_ohlcv_weekly` and `stock_ohlcv_monthly` as separate tables.
- **Blocking ingestion on anomaly detection:** Per DATA-09, anomalies trigger an alert but do NOT prevent data from being written. An anomaly may be real data (a market crash), not a pipeline error.
- **Hard-coding VN30 symbols:** Always fetch the live VN30 symbol list via `Listing.symbols_by_group('VN30')` on each run. Index composition changes quarterly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vietnamese stock data | Custom HOSE/HNX scraper | vnstock 3.2.3 | vnstock handles auth, rate limits, data normalization, and multiple exchanges |
| FRED data fetching | Custom REST client for FRED | fredapi Python wrapper | fredapi handles API key injection, pagination, series metadata |
| GLD ETF historical data | Custom Yahoo Finance scraper | yfinance | Rate limit handling, data normalization, historical adjustments already solved |
| JS-rendered site scraping | DOM parsing with requests | Playwright | Network interception captures raw API payloads; survives page redesigns |
| PostgreSQL upsert | Custom INSERT + UPDATE | `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy | Handles race conditions and partial failures atomically |
| n8n error alerts | Custom HTTP webhook to Telegram | n8n Error Trigger + Telegram node | Native integration; no extra code; same credentials store |
| Moving average / drawdown | Custom loop calculations | pandas `rolling()` / `expanding()` | Vectorized, tested, handles NaN/edge cases properly |
| DB schema versioning | Manual SQL files + tracking | Flyway (already in project) | Already running; V2+ migrations just need to follow V1 naming pattern |

**Key insight:** vnstock 3.2.3 already wraps all the complexity of accessing HOSE, HNX, and UPCOM data. The sidecar's value is version isolation and providing a clean HTTP interface — not re-implementing data access logic.

---

## Common Pitfalls

### Pitfall 1: vnstock3 vs vnstock Package Name Confusion

**What goes wrong:** Docker build fails or installs wrong/outdated library. `pip install vnstock3` installs a deprecated package that no longer receives updates.

**Why it happens:** The package was renamed from `vnstock3` to `vnstock` on PyPI in January 2025. Many tutorials and StackOverflow answers still reference `vnstock3`.

**How to avoid:** Always use `vnstock==3.2.3` (new name, exact pin) in requirements.txt. The Dockerfile should pin exactly to prevent drift.

**Warning signs:** `ModuleNotFoundError: No module named 'vnstock'` when using `vnstock3` import aliases, or outdated API responses.

### Pitfall 2: WGC Goldhub Is JavaScript-Rendered

**What goes wrong:** `requests.get("https://www.gold.org/goldhub/data/...")` returns HTML shell with no data. BeautifulSoup finds empty tables.

**Why it happens:** Goldhub loads chart data via async JavaScript API calls after initial page load. The server-rendered HTML has no data.

**How to avoid:** Use Playwright with network request interception to capture the underlying JSON API calls, OR locate the direct Excel download URL via DevTools Network tab and download it with requests.

**Warning signs:** `requests` returns 200 but HTML has empty `<table>` elements or `data-loading="true"` attributes.

### Pitfall 3: FRED data_as_of Semantics

**What goes wrong:** Every row in `fred_indicators` has `data_as_of = ingested_at` (the time the pipeline ran). Downstream LangGraph reasoning nodes see "GDP as of last Sunday" instead of "GDP for Q3 2024."

**Why it happens:** Confusing the API call date with the period the observation represents.

**How to avoid:** `data_as_of` = the `date` field from the FRED observation (the period covered). `ingested_at` = `NOW()` when written to the DB. These are always different and must never be the same column.

**Warning signs:** All rows in `fred_indicators` have `data_as_of` timestamps clustered around Sunday night run times rather than spread over years.

### Pitfall 4: n8n Schedule Trigger Timezone

**What goes wrong:** Weekly Sunday pipeline runs at wrong time (e.g., Sunday 1pm UTC instead of Sunday night Vietnam time).

**Why it happens:** n8n's default timezone for self-hosted instances is America/New_York. The project already sets `GENERIC_TIMEZONE: Asia/Ho_Chi_Minh` in docker-compose.yml, but individual workflow-level timezone settings can override this.

**How to avoid:** Set workflow-level timezone to `Asia/Ho_Chi_Minh` explicitly in each workflow's settings (Workflow → Three dots → Settings → Timezone). Confirm `GENERIC_TIMEZONE: Asia/Ho_Chi_Minh` is in the n8n service environment — already done in Phase 1.

**Warning signs:** Pipeline runs at unexpected UTC times; check `pipeline_run_log.run_at` timestamps.

### Pitfall 5: n8n Built-in Retry Delay Cap (5 seconds)

**What goes wrong:** Configuring retry delays of 1min/5min/15min in n8n's built-in per-node retry settings. The UI accepts the value but silently caps at 5,000ms.

**Why it happens:** n8n's built-in "Retry on Fail" maximum delay is 5,000ms (5 seconds). The user requirement specifies 1min/5min/15min delays.

**How to avoid:** Implement custom retry loop: HTTP Request node → error branch → Code node (compute delay) → Wait node (use delay value) → loop back. The loop counter and delay sequence must be tracked in the workflow data.

**Warning signs:** After retries, the next attempt fires much faster than expected.

### Pitfall 6: Structure Markers Computed with Insufficient History

**What goes wrong:** `ma_50w` is NULL for the first 40 weeks of data (min_periods enforced) or the percentile rank is computed against only 2 years when 5 years are available.

**Why it happens:** Rolling window functions require a minimum number of non-null observations. If the backfill is incomplete or the window exceeds available data, results are NULL.

**How to avoid:** Ensure the initial backfill (5 years for stocks, 10 years for gold) runs successfully before reporting structure markers. Use `min_periods` set to ~80% of window size to allow useful early results. Log NULL counts per symbol/column as part of pipeline health check.

**Warning signs:** `structure_markers` table has many NULL rows for `ma_50w` or `close_pct_rank`.

### Pitfall 7: WGC 45-Day Publication Lag Unmarked

**What goes wrong:** Gold ETF flows for "December" are published in mid-February. Without proper `data_as_of` tracking, the reasoning node sees February-ingested data and assumes it is current, when it actually covers a period 45 days prior.

**Why it happens:** World Gold Council publishes ETF flow data with approximately a 45-day lag after the reporting period ends.

**How to avoid:** The `data_as_of` field on WGC flow records must be the **period end date of the data** (e.g., 2024-12-31), not the ingestion date. Consider adding a `source_lag_days` or `publication_lag_note` column to the `gold_wgc_flows` table as a source metadata property, enabling downstream reasoning nodes to flag whether the most recent available data is current or lagged.

---

## Code Examples

Verified patterns from official sources:

### VN30 Symbol Listing (vnstock)
```python
# Source: Context7 /thinh-vu/vnstock + /vnstock-hq/vnstock_insider_guide
from vnstock import Listing

def get_vn30_symbols() -> list[str]:
    lst = Listing(source="vci")
    df = lst.symbols_by_group(group="VN30")
    return df["symbol"].tolist()
```

### Historical OHLCV Fetch (vnstock)
```python
# Source: Context7 /thinh-vu/vnstock README
from vnstock import Vnstock

stock = Vnstock().stock(symbol='ACB', source='VCI')
df = stock.quote.history(start='2019-01-01', end='2024-01-01', interval='1W')
# interval options: '1D', '1W', '1M'
```

### Financial Ratios Fetch (vnstock)
```python
# Source: Context7 /thinh-vu/vnstock README
from vnstock import Vnstock

stock = Vnstock().stock(symbol='VCI', source='VCI')
# Returns PE, PB, EPS, ROE, ROA, revenue growth, net margin
ratios = stock.finance.ratio(period='year', lang='en', dropna=True)
```

### FRED Series Fetch
```python
# Source: Context7 /websites/fred_stlouisfed_api_fred (FRED official docs)
import fredapi
import os

fred = fredapi.Fred(api_key=os.environ["FRED_API_KEY"])

# GDP quarterly — date field IS the quarter start date (period covered)
gdp = fred.get_series("GDP", observation_start="2015-01-01")

# For gold price from FRED (London fix)
gold_price = fred.get_series("GOLDAMGBD228NLBM", observation_start="2015-01-01")
```

### GLD ETF Historical Data (yfinance)
```python
# Source: Context7 /websites/ranaroussi_github_io
import yfinance as yf

# 10 years of weekly GLD data
gld = yf.Ticker("GLD")
df = gld.history(start="2015-01-01", interval="1wk", auto_adjust=True)
# Columns: Open, High, Low, Close, Volume, Dividends, Stock Splits
```

### ATH Drawdown + 52-Week Drawdown (pandas)
```python
# Source: pandas docs (verified via WebSearch)
import pandas as pd

# Expanding max = all-time high at each point in time
ath = close_series.expanding().max()
drawdown_ath = (close_series / ath) - 1.0

# Rolling 52-bar max = 52-week high (weekly bars)
high_52w = close_series.rolling(52, min_periods=26).max()
drawdown_52w = (close_series / high_52w) - 1.0
```

### PostgreSQL Upsert (SQLAlchemy ON CONFLICT)
```python
# Source: SQLAlchemy docs + WebSearch verification
from sqlalchemy.dialects.postgresql import insert as pg_insert

def upsert_ohlcv(df: pd.DataFrame, engine) -> int:
    records = df.to_dict("records")
    stmt = pg_insert(StockOHLCV).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "resolution", "data_as_of"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "ingested_at": stmt.excluded.ingested_at,
        }
    )
    with engine.begin() as conn:
        result = conn.execute(stmt)
    return result.rowcount
```

### Docker Compose Sidecar Addition
```yaml
# Addition to existing docker-compose.yml — ingestion network, ingestion profile
  data-sidecar:
    build:
      context: ./sidecar
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      FRED_API_KEY: ${FRED_API_KEY}
    # No host port mapping — internal only (n8n calls it by service name)
    networks:
      - ingestion
    profiles: ["ingestion"]
```

### n8n Schedule Trigger Cron (Sunday 2:00 AM Vietnam Time)
```
# Cron expression for weekly Sunday 2:00 AM Vietnam time
# Set in n8n Schedule Trigger node → Custom → Cron Expression
0 2 * * 0
# Combined with Workflow Settings → Timezone: Asia/Ho_Chi_Minh
# GENERIC_TIMEZONE is already set in docker-compose.yml n8n service
```

---

## Proposed PostgreSQL Schema (Flyway Migrations)

Phase 2 requires 4 new Flyway migration files following the V1 pattern:

### V2__stock_data.sql (DATA-01, DATA-02)
```sql
-- stock_ohlcv: single table, resolution column per user decision
CREATE TABLE stock_ohlcv (
    id          BIGSERIAL    PRIMARY KEY,
    symbol      VARCHAR(20)  NOT NULL,
    resolution  VARCHAR(10)  NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    open        NUMERIC(18,4),
    high        NUMERIC(18,4),
    low         NUMERIC(18,4),
    close       NUMERIC(18,4) NOT NULL,
    volume      BIGINT,
    data_as_of  TIMESTAMPTZ  NOT NULL,  -- the bar date (period start)
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, resolution, data_as_of)
);

CREATE TABLE stock_fundamentals (
    id            BIGSERIAL    PRIMARY KEY,
    symbol        VARCHAR(20)  NOT NULL,
    period_type   VARCHAR(10)  NOT NULL CHECK (period_type IN ('year', 'quarter')),
    pe_ratio      NUMERIC(12,4),
    pb_ratio      NUMERIC(12,4),
    eps           NUMERIC(12,4),
    market_cap    NUMERIC(24,2),
    roe           NUMERIC(10,4),
    roa           NUMERIC(10,4),
    revenue_growth NUMERIC(10,4),
    net_margin    NUMERIC(10,4),
    data_as_of    TIMESTAMPTZ  NOT NULL,  -- period end date
    ingested_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, period_type, data_as_of)
);
```

### V3__gold_data.sql (DATA-03, DATA-04)
```sql
CREATE TABLE gold_price (
    id          BIGSERIAL    PRIMARY KEY,
    source      VARCHAR(50)  NOT NULL DEFAULT 'FRED_GOLDAMGBD228NLBM',
    price_usd   NUMERIC(12,4) NOT NULL,
    data_as_of  TIMESTAMPTZ  NOT NULL,
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (source, data_as_of)
);

CREATE TABLE gold_etf_ohlcv (
    id          BIGSERIAL    PRIMARY KEY,
    ticker      VARCHAR(10)  NOT NULL DEFAULT 'GLD',
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4) NOT NULL,
    volume      BIGINT,
    resolution  VARCHAR(10)  NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    data_as_of  TIMESTAMPTZ  NOT NULL,
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, resolution, data_as_of)
);

CREATE TABLE gold_wgc_flows (
    id                    BIGSERIAL    PRIMARY KEY,
    period_end            DATE         NOT NULL,    -- reporting period end
    region                VARCHAR(100),             -- 'North America', 'Europe', 'Asia', 'Other'
    fund_name             VARCHAR(255),             -- NULL for regional aggregates
    holdings_tonnes       NUMERIC(12,4),
    flows_usd_millions    NUMERIC(14,4),
    central_bank_net_tonnes NUMERIC(12,4),          -- NULL for ETF rows
    source_lag_note       TEXT,                     -- e.g. "~45 day publication lag"
    data_as_of            TIMESTAMPTZ  NOT NULL,    -- = period_end cast to TIMESTAMPTZ
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (period_end, COALESCE(region, ''), COALESCE(fund_name, ''))
);
```

### V4__fred_indicators.sql (DATA-05)
```sql
CREATE TABLE fred_indicators (
    id          BIGSERIAL    PRIMARY KEY,
    series_id   VARCHAR(50)  NOT NULL,  -- e.g. 'GDP', 'UNRATE', 'FEDFUNDS', 'CPIAUCSL'
    value       NUMERIC(20,6) NOT NULL,
    frequency   VARCHAR(10)  NOT NULL,  -- 'daily', 'monthly', 'quarterly'
    data_as_of  TIMESTAMPTZ  NOT NULL,  -- the period the observation covers (FRED 'date' field)
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (series_id, data_as_of)
);

CREATE INDEX idx_fred_indicators_series_date
    ON fred_indicators (series_id, data_as_of DESC);
```

### V5__structure_markers.sql (DATA-06)
```sql
CREATE TABLE structure_markers (
    id                    BIGSERIAL    PRIMARY KEY,
    symbol                VARCHAR(20)  NOT NULL,
    asset_type            VARCHAR(20)  NOT NULL CHECK (asset_type IN ('stock', 'gold_spot', 'gold_etf')),
    resolution            VARCHAR(10)  NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    close                 NUMERIC(18,4),
    ma_10w                NUMERIC(18,4),
    ma_20w                NUMERIC(18,4),
    ma_50w                NUMERIC(18,4),
    drawdown_from_ath     NUMERIC(8,6),   -- e.g. -0.234567 = -23.46%
    drawdown_from_52w_high NUMERIC(8,6),
    close_pct_rank        NUMERIC(6,4),   -- 0.0 to 1.0 (valuation percentile)
    pe_pct_rank           NUMERIC(6,4),   -- NULL for gold
    data_as_of            TIMESTAMPTZ  NOT NULL,
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, resolution, data_as_of)
);

CREATE INDEX idx_structure_markers_symbol_date
    ON structure_markers (symbol, resolution, data_as_of DESC);
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `vnstock3` package | `vnstock` package (same codebase) | Jan 2025 | `vnstock3` no longer updated; use `vnstock==3.2.3` |
| TCBS financial ratios source | VCI or KBS source for ratios | 2025 (API broken) | Must change source for fundamental data |
| n8n built-in simple retry | Custom wait-node retry loop for long delays | n8n built-in capped at 5s | Required for 1min/5min/15min retry cadence |
| requests + BeautifulSoup for all scraping | Playwright for JS-rendered sites | 2022-2024 industry shift | Goldhub requires Playwright or network interception |

**Deprecated/outdated:**
- `vnstock3` on PyPI: deprecated January 2025, no further updates, replaced by `vnstock`
- TCBS source for `finance.ratio()` in vnstock: API endpoint broken as of 2025; use VCI or KBS

---

## Open Questions

1. **WGC Goldhub exact API endpoint structure**
   - What we know: Goldhub is JS-rendered; data is loaded via async API calls; monthly Excel downloads exist
   - What's unclear: Whether the underlying JSON API endpoint is stable and publicly accessible without auth; whether the Excel download URL is a static path or session-dependent
   - Recommendation: During Wave 0 (setup), open Goldhub in browser DevTools → Network tab and document the actual XHR endpoint. If it requires auth headers, Playwright session cookie capture is the path. If static, a `requests.get(excel_url)` is simpler and more maintainable.
   - This was flagged as a blocker in STATE.md: "[Phase 2]: World Gold Council data ingestion method and specific API endpoint structure not confirmed — validate before Phase 2 planning begins."

2. **Neo4j regime graph seed data**
   - What we know: STATE.md flags "Neo4j initial regime graph seed data source is unresolved" — this is mentioned as a Phase 2 concern
   - What's unclear: Whether seeding the Neo4j regime graph is in scope for Phase 2 or Phase 3
   - Recommendation: Treat Neo4j seed data as Phase 3 scope (Retrieval Validation). Phase 2's scope ends at PostgreSQL. The Phase 2 context doc does not mention Neo4j seed data — it should not be in Phase 2 plans.

3. **vnstock VN30 + Supabase watchlist integration**
   - What we know: Stock universe = VN30 + user's Supabase watchlist; Supabase is external to this project
   - What's unclear: How the sidecar accesses the Supabase watchlist (direct Supabase REST API call? Synchronized to a local PostgreSQL table?)
   - Recommendation: The simplest approach is a PostgreSQL `watchlist` table (populated by Phase 7's user management) that the sidecar queries. For Phase 2, treat the symbol list as VN30-only. The watchlist integration can be a thin addition once Phase 7 builds user management.

---

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` — this section is included because the config does not explicitly set it to false. The config only specifies `research`, `plan_check`, and `verifier` keys.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) — standard for FastAPI/Python projects |
| Config file | `sidecar/pytest.ini` or `sidecar/pyproject.toml` — Wave 0 gap |
| Quick run command | `pytest sidecar/tests/ -x -q` |
| Full suite command | `pytest sidecar/tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | OHLCV rows written with correct symbol/resolution/OHLCV columns | unit | `pytest sidecar/tests/test_vnstock_service.py::test_ohlcv_ingest -x` | Wave 0 |
| DATA-02 | Fundamental data includes PE, PB, EPS, ROE, ROA | unit | `pytest sidecar/tests/test_vnstock_service.py::test_fundamentals_ingest -x` | Wave 0 |
| DATA-03 | Gold price has correct data_as_of (FRED date, not ingestion date) | unit | `pytest sidecar/tests/test_fred_service.py::test_gold_price_data_as_of -x` | Wave 0 |
| DATA-04 | WGC flows table populated with period_end, holdings_tonnes | integration | `pytest sidecar/tests/test_wgc_service.py::test_wgc_flow_ingest -x` | Wave 0 |
| DATA-05 | FRED GDP/CPI/UNRATE/FEDFUNDS rows have data_as_of = observation period date | unit | `pytest sidecar/tests/test_fred_service.py::test_fred_data_as_of -x` | Wave 0 |
| DATA-06 | structure_markers has no NULL for ma_10w/ma_20w after 52-week minimum | unit | `pytest sidecar/tests/test_structure_service.py::test_ma_non_null -x` | Wave 0 |
| DATA-07 | Zero rows in any table with NULL data_as_of or ingested_at | integration | `pytest sidecar/tests/test_db_schema.py::test_no_null_timestamps -x` | Wave 0 |
| DATA-08 | pipeline_run_log has record for each run with correct status | integration | `pytest sidecar/tests/test_pipeline_log.py::test_run_log_written -x` | Wave 0 |
| DATA-09 | Anomaly detection returns True for >50% deviation, False otherwise | unit | `pytest sidecar/tests/test_anomaly.py::test_row_count_deviation -x` | Wave 0 |

### Wave 0 Gaps
- [ ] `sidecar/tests/__init__.py` — test package
- [ ] `sidecar/tests/conftest.py` — shared fixtures (test DB, mock vnstock responses)
- [ ] `sidecar/tests/test_vnstock_service.py` — covers DATA-01, DATA-02
- [ ] `sidecar/tests/test_fred_service.py` — covers DATA-03, DATA-05
- [ ] `sidecar/tests/test_wgc_service.py` — covers DATA-04
- [ ] `sidecar/tests/test_structure_service.py` — covers DATA-06
- [ ] `sidecar/tests/test_db_schema.py` — covers DATA-07
- [ ] `sidecar/tests/test_pipeline_log.py` — covers DATA-08
- [ ] `sidecar/tests/test_anomaly.py` — covers DATA-09
- [ ] `sidecar/pytest.ini` — framework config
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` — not yet in sidecar requirements

---

## Sources

### Primary (HIGH confidence)
- Context7 `/thinh-vu/vnstock` — OHLCV history, financials, VN30 listing, VCI/TCBS sources
- Context7 `/websites/fred_stlouisfed_api_fred` — FRED API series observations, vintage dates, data_as_of semantics
- Context7 `/websites/ranaroussi_github_io` — yfinance Ticker.history(), download(), intervals
- Context7 `/fastapi/fastapi` — HTTPException, request body error handling, POST endpoints
- Context7 `/vnstock-hq/vnstock_insider_guide` — VN30 group listing, financial ratio methods

### Secondary (MEDIUM confidence)
- WebSearch "vnstock3 version pinning Docker 2025" → confirmed package rename to `vnstock`, version 3.2.3, Jan 2025 change — verified against PyPI
- WebSearch "n8n Schedule Trigger timezone Vietnam 2025" → verified `Asia/Ho_Chi_Minh`, cron `0 H * * 0`, workflow-level timezone override
- WebSearch "n8n exponential backoff retry 2025" → confirmed 5s built-in cap; custom wait-node loop required for longer delays
- WebSearch "pandas rolling ATH drawdown percentile" → verified `expanding().max()` for ATH, `rolling().quantile()` for percentile — cross-checked against pandas docs
- WebSearch "n8n Telegram Error Trigger workflow 2025" → confirmed Error Trigger → Telegram node pattern; official n8n templates exist
- WebSearch "World Gold Council Goldhub scraping 2025" → confirmed JS-rendered, Playwright recommended, monthly Excel downloads available

### Tertiary (LOW confidence)
- WebSearch "WGC Goldhub API endpoint structure" — specific underlying API URL not confirmed; requires manual DevTools investigation during Wave 0

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — vnstock, yfinance, fredapi, FastAPI all verified via Context7 and PyPI; versions confirmed current
- Architecture: HIGH — sidecar/n8n pattern documented with multiple official sources; PostgreSQL schema follows established Phase 1 convention
- WGC Scraping: MEDIUM — approach (Playwright) is correct for JS-rendered sites; exact API endpoint requires hands-on investigation
- Pitfalls: HIGH — vnstock package rename, TCBS broken, FRED data_as_of semantics, n8n retry cap all verified from authoritative sources

**Research date:** 2026-03-03
**Valid until:** 2026-06-01 (stable domain; vnstock is actively maintained; re-check if vnstock minor version bumps break API)
