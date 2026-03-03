---
phase: 02-data-ingestion-pipeline
plan: "02"
subsystem: api
tags: [fastapi, fredapi, yfinance, gold, fred, macroeconomics, postgresql, sqlalchemy]

requires:
  - phase: 02-data-ingestion-pipeline
    provides: data-sidecar FastAPI container, vnstock ingestion, SQLAlchemy upsert pattern, DB models

provides:
  - Gold spot price ingestion from FRED GOLDAMGBD228NLBM with correct data_as_of semantics
  - GLD ETF weekly OHLCV ingestion via yfinance
  - WGC flows endpoint stub (501) — known limitation documented
  - FRED macroeconomic indicator ingestion (GDP, CPI, UNRATE, FEDFUNDS)
  - Four new POST endpoints under /ingest/gold/* and /ingest/fred/*

affects:
  - 02-data-ingestion-pipeline
  - 03-retrieval-and-rag
  - 04-reasoning-pipeline

tech-stack:
  added:
    - fredapi>=0.5.2 (already in requirements.txt from Plan 01)
    - yfinance>=0.2.48 (already in requirements.txt from Plan 01)
  patterns:
    - FRED date = observation period date, stored as data_as_of (NOT ingestion timestamp)
    - WGC stub pattern: raise WGCNotImplemented → router catches → 501 with documented limitation
    - DEBUG log of data_as_of range after each FRED fetch for correctness verification
    - yfinance bar date normalized to midnight UTC for gold_etf_ohlcv data_as_of

key-files:
  created:
    - sidecar/app/services/gold_service.py
    - sidecar/app/routers/gold.py
    - sidecar/app/services/fred_service.py
    - sidecar/app/routers/fred.py
  modified:
    - sidecar/app/main.py (registered gold and fred routers)

key-decisions:
  - "WGC flows implemented as a 501 stub — Goldhub is JS-rendered with no stable direct-download URL; Playwright excluded to avoid Chromium in the sidecar container"
  - "FRED_API_KEY absence returns 503 (not 500) with direct link to free key registration"
  - "GLD ETF bar dates normalized to midnight UTC using dt.normalize() for consistent data_as_of"

patterns-established:
  - "FRED data_as_of anti-pattern guard: DEBUG log showing min/max data_as_of after each series fetch makes the bug immediately visible in logs"
  - "Known limitation stub: raise custom NotImplementedError subclass, router catches and returns 501 with explanation"
  - "EnvironmentError for missing API keys: distinct from upstream API errors (502) and missing data (204)"

requirements-completed: [DATA-03, DATA-04, DATA-05]

duration: 15min
completed: 2026-03-04
---

# Phase 2 Plan 02: Gold and FRED Macroeconomic Data Ingestion Summary

**Four new ingestion endpoints: FRED gold spot price (GOLDAMGBD228NLBM), GLD ETF weekly OHLCV, WGC flows stub (501), and FRED macro indicators (GDP/CPI/UNRATE/FEDFUNDS) — all with correct data_as_of = observation period date semantics**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-03T17:45:16Z
- **Completed:** 2026-03-03T18:00:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Gold FRED price endpoint fetches LBMA PM fix with data_as_of = the observation date (not ingestion time), upserts idempotently on (source, data_as_of)
- GLD ETF endpoint fetches 10+ years of weekly OHLCV via yfinance, normalizes bar dates to midnight UTC, upserts on (ticker, resolution, data_as_of)
- WGC flows endpoint documented as a 501 stub — JS-rendered portal has no stable download URL; Playwright excluded to avoid Chromium bloat
- FRED macro indicator endpoint fetches GDP (quarterly), CPI/UNRATE/FEDFUNDS (monthly) with observation period dates as data_as_of; DEBUG log verifies date range spans years not ingestion time
- All upserts use pg_insert().on_conflict_do_update() — identical to Plan 01 vnstock pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: Gold data ingestion endpoints (FRED price, GLD ETF, WGC flows)** - `8f308c3` (feat)
2. **Task 2: FRED macroeconomic indicator ingestion endpoint** - `b0fa0a9` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `sidecar/app/services/gold_service.py` - FRED gold price + GLD ETF fetching with data_as_of semantics; WGC stub
- `sidecar/app/routers/gold.py` - POST /ingest/gold/fred-price, /gld-etf, /wgc-flows
- `sidecar/app/services/fred_service.py` - FRED_SERIES config + fetch_and_upsert_fred_indicators
- `sidecar/app/routers/fred.py` - POST /ingest/fred/indicators with 503 for missing API key
- `sidecar/app/main.py` - Registered gold and fred routers

## Decisions Made

- **WGC flows as 501 stub**: The World Gold Council Goldhub portal is JS-rendered and does not expose a stable direct-download URL. Rather than adding Playwright + Chromium to the sidecar container, the endpoint returns 501 with a documented limitation message. WGC data can be imported manually via CSV when needed.
- **FRED_API_KEY = 503 not 500**: Missing API key is a configuration issue (service unavailable), not an internal server error. HTTP 503 with a direct link to the FRED key registration page is more actionable for operators.
- **GLD ETF bar date normalization**: yfinance returns bar dates as week-start timestamps with timezone info. `dt.normalize()` strips the time component to midnight UTC, matching the storage pattern used for stock_ohlcv.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] main.py already modified by concurrent Plan 03 executor**
- **Found during:** Task 1 (registering gold router)
- **Issue:** Plan 03 executor had already modified main.py to add markers router and gold import; the gold router registration was already present in the committed main.py
- **Fix:** Task 1 commit included only gold_service.py and gold.py (main.py was already correct); Task 2 added the fred router import and registration to main.py
- **Files modified:** sidecar/app/main.py (Task 2 commit)
- **Verification:** Container boots and all routers respond; `from app.routers.fred import router` succeeds in container
- **Committed in:** b0fa0a9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (blocking — concurrent plan modification)
**Impact on plan:** No scope change. All planned endpoints implemented as specified.

## Issues Encountered

- Docker buildx plugin missing — used `docker build` directly instead of `docker compose build`. Container image rebuilt successfully with both commands.
- Container required full rebuild to pick up new Python files (no volume mount — code is baked into image at build time).

## User Setup Required

This plan requires FRED API key configuration. See the plan frontmatter `user_setup` section:

- **FRED_API_KEY**: Free registration at https://fred.stlouisfed.org/docs/api/api_key.html — instant key
- **TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID**: Required for Plan 04 alert wiring (not needed for this plan)

Without FRED_API_KEY set in the container environment, all FRED-dependent endpoints return HTTP 503 with a clear error message pointing to the key registration page.

## Next Phase Readiness

- All four external data source integrations are complete: Vietnamese stocks (Plan 01), gold spot price, GLD ETF, and FRED macro indicators
- Structure markers computation (Plan 03) can now read from gold_price and gold_etf_ohlcv
- n8n workflow wiring (Plan 04) can now schedule all ingestion endpoints
- WGC flows remains a known gap — document in deferred-items.md for future implementation

## Self-Check: PASSED

- FOUND: sidecar/app/services/gold_service.py
- FOUND: sidecar/app/routers/gold.py
- FOUND: sidecar/app/services/fred_service.py
- FOUND: sidecar/app/routers/fred.py
- FOUND: .planning/phases/02-data-ingestion-pipeline/02-02-SUMMARY.md
- COMMIT 8f308c3: feat(02-02): add gold data ingestion endpoints
- COMMIT b0fa0a9: feat(02-02): add FRED macroeconomic indicator ingestion endpoint
- Container verification: `Gold service imports OK`, `Gold router imports OK`, `FRED service OK`, `FRED router imports OK`

---
*Phase: 02-data-ingestion-pipeline*
*Completed: 2026-03-04*
