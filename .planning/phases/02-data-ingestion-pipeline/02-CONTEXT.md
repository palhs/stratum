# Phase 2: Data Ingestion Pipeline - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

All external data sources flowing into PostgreSQL on schedule with pre-computed structure markers, full timestamp metadata, and automatic detection of pipeline failures and data anomalies. Orchestrated by n8n with a sidecar Python container for vnstock. Covers: Vietnamese stock OHLCV and fundamentals (vnstock), gold price (FRED + yfinance), gold ETF flows and central bank buying (World Gold Council scraping), FRED macroeconomic indicators, pre-computed structure markers, and pipeline health monitoring with Telegram alerting.

</domain>

<decisions>
## Implementation Decisions

### Stock Universe & vnstock Scope
- Stock universe: VN30 index components + user's Supabase watchlist
- Fundamental data: core valuation (P/E, P/B, EPS, market cap) + profitability (ROE, ROA, revenue growth, net margin)
- OHLCV storage: single `stock_ohlcv` table with `resolution` column ('weekly'/'monthly') — not separate tables
- vnstock integration: dedicated sidecar Python container (FastAPI) with pinned vnstock version, called by n8n via HTTP Request node
- Sidecar scope: Claude's discretion on whether all sources route through the sidecar or just vnstock (other sources may use n8n HTTP nodes directly if they're standard REST APIs)
- Historical backfill: 5 years on first run for Vietnamese stocks

### Gold Data Sourcing
- Gold spot price: FRED GOLDAMGBD228NLBM series (London fix, USD)
- Gold ETF data: yfinance for GLD ETF OHLCV with volume (added to the sidecar container)
- Gold ETF flows + central bank buying: web scraping World Gold Council Goldhub pages
- Publication lag handling: Claude's discretion — `data_as_of` timestamp captures real-world validity, may add source metadata columns if it helps downstream reasoning nodes flag stale data explicitly
- Historical backfill: 10 years for gold data (longer macro cycles, captures 2015 bottom through 2025 run)
- WGC scraping runs monthly (matches quarterly publication cadence), gold price and GLD run weekly

### Structure Marker Definitions
- Moving averages: Claude's discretion on MA set — optimize for StructureAnalyzer's entry timing context without being overly technical
- Drawdown: compute BOTH full-history ATH drawdown and 52-week high drawdown for each asset
- Valuation percentiles: rolling window matches backfill period per asset (5 years for stocks, 10 years for gold)
- Recompute strategy: Claude's discretion — at VN30 scale, full recompute is likely fast enough

### Pipeline Scheduling & Alerting
- Cadence: weekly for all sources, running Sunday night Vietnam time (Asia/Ho_Chi_Minh timezone)
- WGC scraping: monthly cadence (separate from weekly runs)
- Failure alerts: Telegram bot notification via n8n Telegram node
- Retry behavior: 3 retries with exponential backoff (1min, 5min, 15min) before alerting
- Anomaly detection (DATA-09): vnstock row-count >50% deviation from 4-week moving average triggers Telegram alert but does NOT block ingestion — data is still ingested, user investigates
- Every pipeline run logged to `pipeline_run_log` table (already exists from Phase 1)

### Claude's Discretion
- Sidecar scope: whether gold/FRED data routes through the Python sidecar or uses n8n HTTP nodes directly
- MA set selection for structure markers
- Structure marker recompute strategy (full vs incremental)
- Publication lag modeling approach (metadata columns vs `data_as_of` alone)
- PostgreSQL table design for new data tables (following existing `data_as_of` + `ingested_at` convention)
- n8n workflow structure and organization

</decisions>

<specifics>
## Specific Ideas

- Single `stock_ohlcv` table with resolution column — user confirmed after discussing performance tradeoffs (negligible at VN30 scale)
- Sidecar container as FastAPI app with REST endpoints (e.g., POST /ingest/vnstock) — chosen over CLI approach for cleaner n8n integration and independent testability
- Both FRED spot gold and yfinance GLD ETF — two complementary views (institutional fix price vs ETF-traded with volume)
- Alert-only anomaly detection — user explicitly chose not to block ingestion on anomalies to avoid false positive pipeline stalls

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline_run_log` table: already exists in V1 migration with `pipeline_name`, `status`, `rows_ingested`, `error_message`, `duration_ms`, `data_as_of`, `ingested_at` columns — Phase 2 writes to this directly
- Docker Compose infrastructure: dual-network isolation (ingestion + reasoning) ready for the sidecar container to join the ingestion network
- Flyway migration framework: V1 migration exists, Phase 2 adds V2+ migrations for new data tables
- Makefile: `make up`, `make migrate` commands already work

### Established Patterns
- Timestamp convention: every time-series table must include `data_as_of` (real-world validity) and `ingested_at` (write time) — NOT NULL
- Named Docker volumes for persistent data
- `.env` file for secrets (gitignored), `--env-file` in compose
- Docker Compose profiles: `storage`, `ingestion`, `reasoning` — sidecar should use `ingestion` profile
- Init containers (flyway, neo4j-init, qdrant-init) as one-shot services with no restart policy

### Integration Points
- n8n (port 5678) orchestrates all pipeline runs on the ingestion network
- Sidecar Python container joins the `ingestion` network alongside n8n and storage services
- PostgreSQL is the primary data target (internal port 5432, no host mapping)
- Neo4j available for any regime seed data loading (port 7687 internal)
- Telegram Bot API for failure/anomaly notifications (configured in n8n)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-ingestion-pipeline*
*Context gathered: 2026-03-03*
