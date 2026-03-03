---
phase: 02-data-ingestion-pipeline
plan: 01
subsystem: database, ingestion
tags: [python, fastapi, vnstock, sqlalchemy, flyway, postgresql, docker, uvicorn]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-storage-foundation
    provides: postgres service with V1 migration (pipeline_run_log), Docker Compose networks and profiles, Flyway container

provides:
  - Flyway V2-V5 migrations creating all 7 Phase 2 tables (stock_ohlcv, stock_fundamentals, gold_price, gold_etf_ohlcv, gold_wgc_flows, fred_indicators, structure_markers)
  - data-sidecar FastAPI container on ingestion network with health check
  - POST /ingest/vnstock/ohlcv — VN30 weekly OHLCV ingestion via vnstock VCI source
  - POST /ingest/vnstock/fundamentals — VN30 annual fundamentals ingestion via vnstock VCI source
  - SQLAlchemy Core Table() models for all 8 Phase 2 tables
  - Idempotent upsert pattern (INSERT ON CONFLICT DO UPDATE) for all ingestion endpoints
  - data-sidecar service added to docker-compose.yml (ingestion profile, no host port)
  - Makefile up-sidecar target

affects:
  - 02-data-ingestion-pipeline (Plans 02-05 — gold, FRED, WGC, structure markers will add routers/services to this sidecar)
  - 03-reasoning-graph (structure_markers and stock_fundamentals feed into valuation/structure analysis nodes)
  - 04-reasoning-implementation (VN30 OHLCV feeds StructureAnalyzer; fundamentals feed ValuationAnalyzer)

# Tech tracking
tech-stack:
  added:
    - vnstock==3.2.3 (Vietnamese stock market data — VCI source only, TCBS broken as of 2025)
    - fastapi>=0.115.0 (Python web framework for sidecar API)
    - uvicorn>=0.30.0 (ASGI server)
    - sqlalchemy>=2.0.0 (ORM/Core, used Core Table() style for upserts)
    - psycopg2-binary>=2.9.9 (PostgreSQL driver)
    - pandas>=2.2.0 (DataFrame manipulation for vnstock response normalization)
    - python-dotenv>=1.0.0 (env var loading)
    - yfinance>=0.2.48 (gold ETF data — used in Plan 02)
    - fredapi>=0.5.2 (FRED macroeconomic data — used in Plan 02)
  patterns:
    - FastAPI router-per-datasource pattern (health.py, vnstock.py; future: gold.py, fred.py, wgc.py, markers.py)
    - SQLAlchemy Core Table() + pg_insert().on_conflict_do_update() for idempotent upserts
    - IngestRequest/IngestResponse Pydantic contract for all ingestion endpoints
    - VnstockAPIError custom exception mapped to HTTP 502 at router layer
    - data_as_of/ingested_at timestamp convention on every table row (DATA-07)

key-files:
  created:
    - db/migrations/V2__stock_data.sql
    - db/migrations/V3__gold_data.sql
    - db/migrations/V4__fred_indicators.sql
    - db/migrations/V5__structure_markers.sql
    - sidecar/Dockerfile
    - sidecar/requirements.txt
    - sidecar/app/__init__.py
    - sidecar/app/main.py
    - sidecar/app/db.py
    - sidecar/app/models.py
    - sidecar/app/routers/__init__.py
    - sidecar/app/routers/health.py
    - sidecar/app/routers/vnstock.py
    - sidecar/app/services/__init__.py
    - sidecar/app/services/vnstock_service.py
  modified:
    - docker-compose.yml (data-sidecar service added)
    - .env.example (VNSTOCK_API_KEY, FRED_API_KEY added)
    - Makefile (up-sidecar target added)

key-decisions:
  - "VCI source used for all vnstock calls (TCBS source broken as of 2025)"
  - "VN30 symbols fetched live via Listing.symbols_by_group() — never hard-coded"
  - "Single stock_ohlcv table with resolution column — no separate tables per resolution (locked from plan)"
  - "SQLAlchemy Core Table() style chosen over ORM for upsert compatibility with pg_insert().on_conflict_do_update()"
  - "data-sidecar has no host port mapping — n8n calls it via service name on ingestion network"
  - "playwright excluded from requirements.txt (browser install step needed in Plan 02 when WGC scraping is added)"
  - "UNIQUE constraint with COALESCE in V3 gold_wgc_flows implemented as CREATE UNIQUE INDEX (PostgreSQL does not support expressions in table-level UNIQUE constraint definition)"

patterns-established:
  - "Router-per-datasource: each data source gets its own router file (routers/vnstock.py, future: routers/gold.py)"
  - "Service layer separation: routers call service functions, services own all vnstock/API/DB logic"
  - "IngestRequest/IngestResponse: standardized Pydantic contract for all ingestion endpoints"
  - "Idempotent upsert: ON CONFLICT DO UPDATE on (symbol/series_id/ticker, resolution, data_as_of)"
  - "Partial failure handling: per-symbol try/except with anomaly_detected flag in response"

requirements-completed: [DATA-01, DATA-02, DATA-07]

# Metrics
duration: 7min
completed: 2026-03-04
---

# Phase 2 Plan 01: Data Sidecar Foundation and vnstock Ingestion Summary

**Python FastAPI sidecar container with Flyway V2-V5 migrations creating 7 Phase 2 tables and idempotent VN30 OHLCV + fundamentals ingestion via vnstock VCI source**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-03T17:35:43Z
- **Completed:** 2026-03-03T17:42:05Z
- **Tasks:** 2
- **Files modified:** 18 (15 created, 3 modified)

## Accomplishments

- All 7 Phase 2 tables created via Flyway (V2-V5): stock_ohlcv, stock_fundamentals, gold_price, gold_etf_ohlcv, gold_wgc_flows, fred_indicators, structure_markers
- data-sidecar FastAPI container builds, starts, and passes health check at GET /health
- POST /ingest/vnstock/ohlcv and POST /ingest/vnstock/fundamentals endpoints functional with IngestRequest/IngestResponse contract
- VN30 symbols fetched live (not hard-coded) via Listing.symbols_by_group("VN30")
- All tables enforce data_as_of/ingested_at timestamp convention (DATA-07)
- Idempotent upsert logic (ON CONFLICT DO UPDATE) on every ingestion endpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Flyway V2-V5 migrations for all Phase 2 data tables** - `04a7f0e` (feat)
2. **Task 2: Create sidecar FastAPI container with vnstock ingestion endpoints** - `443a616` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `db/migrations/V2__stock_data.sql` - stock_ohlcv and stock_fundamentals tables with constraints and indexes
- `db/migrations/V3__gold_data.sql` - gold_price, gold_etf_ohlcv, gold_wgc_flows tables
- `db/migrations/V4__fred_indicators.sql` - fred_indicators table for FRED series
- `db/migrations/V5__structure_markers.sql` - structure_markers table for computed metrics
- `sidecar/Dockerfile` - python:3.12-slim with curl healthcheck, uvicorn CMD
- `sidecar/requirements.txt` - vnstock==3.2.3, fastapi, uvicorn, sqlalchemy, pandas, psycopg2-binary
- `sidecar/app/main.py` - FastAPI app with health and vnstock routers, startup log
- `sidecar/app/db.py` - SQLAlchemy engine from DATABASE_URL with get_db() dependency
- `sidecar/app/models.py` - Core Table() definitions for all 8 Phase 2 tables
- `sidecar/app/routers/health.py` - GET /health endpoint
- `sidecar/app/routers/vnstock.py` - POST /ingest/vnstock/ohlcv and /fundamentals
- `sidecar/app/services/vnstock_service.py` - VCI fetch, column mapping, upsert logic
- `docker-compose.yml` - data-sidecar service (ingestion profile, no host port)
- `.env.example` - VNSTOCK_API_KEY and FRED_API_KEY with documentation
- `Makefile` - up-sidecar target added

## Decisions Made

- VCI source used exclusively for vnstock calls (TCBS source is broken as of 2025)
- VN30 symbols fetched live via Listing.symbols_by_group() — never hard-coded (per plan spec)
- Single stock_ohlcv table with resolution column — no separate tables per resolution (locked plan decision)
- SQLAlchemy Core Table() style chosen over ORM declarative for compatibility with pg_insert().on_conflict_do_update()
- data-sidecar has no host port mapping — n8n calls it as data-sidecar:8000 on ingestion network
- playwright excluded from requirements.txt for now (browser install needed in Plan 02 for WGC scraping)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UNIQUE constraint with COALESCE in V3 migration**
- **Found during:** Task 1 (V3__gold_data.sql migration run)
- **Issue:** PostgreSQL does not support function expressions (COALESCE) inside a table-level UNIQUE constraint definition — migration failed with syntax error at line 68
- **Fix:** Removed UNIQUE(...COALESCE...) from table definition and replaced with `CREATE UNIQUE INDEX idx_gold_wgc_flows_unique ON gold_wgc_flows (period_end, COALESCE(region, ''), COALESCE(fund_name, ''))` — functionally equivalent, PostgreSQL-compatible
- **Files modified:** db/migrations/V3__gold_data.sql
- **Verification:** Flyway repair ran V3-V5 successfully; \dt showed all 7 tables
- **Committed in:** `04a7f0e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Single syntax fix for PostgreSQL constraint syntax limitation. No scope creep. Functionally equivalent outcome.

## Issues Encountered

- `docker buildx` plugin not installed on this machine — used `docker build` directly for verification. `make up-sidecar` uses `docker compose ... up -d --build` which falls back to legacy builder without buildx (warning printed but build succeeds).

## User Setup Required

External services require API keys for full functionality. Add to `.env.local`:

- `VNSTOCK_API_KEY` — Free Community tier at https://vnstocks.com/login (optional but recommended — increases rate limit from 20 to 60 req/min for VN30 batch ingestion)
- `FRED_API_KEY` — Free at https://fred.stlouisfed.org/docs/api/api_key.html (required for Plan 02 gold price and macroeconomic indicators)

## Next Phase Readiness

- data-sidecar container is functional and ready for Plans 02-04 to add routers/services
- All 7 Phase 2 tables exist in PostgreSQL with correct schemas, constraints, and indexes
- Upsert pattern established — subsequent plans follow the same IngestRequest/IngestResponse/ON CONFLICT pattern
- Plans 02 (gold + FRED) can add `routers/gold.py`, `routers/fred.py`, and their service files
- FRED_API_KEY needed before Plan 02 gold ingestion can be tested end-to-end

---
*Phase: 02-data-ingestion-pipeline*
*Completed: 2026-03-04*
