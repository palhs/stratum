# Phase 10: Backend API Contracts and JWT Middleware - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Secure the reasoning-engine FastAPI service with Supabase JWT validation and add two new read-only endpoints: OHLCV chart data and report history. No frontend code, no Supabase project setup (Phase 11), no new database tables — this phase works with existing tables (stock_ohlcv, gold_etf_ohlcv, reports, report_jobs).

</domain>

<decisions>
## Implementation Decisions

### OHLCV endpoint shape
- Single unified endpoint: GET /tickers/{symbol}/ohlcv serves both stocks (stock_ohlcv table) and gold (gold_etf_ohlcv table) — API resolves which table internally based on symbol
- Response includes precomputed 50MA and 200MA fields alongside raw OHLCV — frontend just renders, no client-side MA computation
- Time format: Unix timestamp (integer seconds since epoch) — TradingView Lightweight Charts native format, no parsing needed
- Default data range: 52 weeks (1 year) of weekly resolution data
- Response shape per data point: `{ time, open, high, low, close, volume, ma50, ma200 }` (ma50/ma200 may be null for early points without enough history)

### Report history contract
- GET /reports/by-ticker/{symbol} with offset pagination: `?page=1&per_page=20`
- Server extracts tier from report_json — frontend receives flat summary, no JSONB parsing on client
- One entry per generation run — group vi+en reports by generated_at timestamp, not separate rows per language
- Each history item includes: `{ report_id, tier, generated_at, verdict }` — verdict is the one-line summary from report_json
- Sort order: newest first (generated_at DESC)

### JWT protection scope
- Claude's Discretion — decide which endpoints get the auth wall vs remain public (e.g., /health stays public)
- Auth mechanism locked: Supabase JWT with `audience="authenticated"` via auth.py dependency

### Error response format
- Claude's Discretion — keep consistent with existing HTTPException(detail=...) pattern or evolve as needed

</decisions>

<specifics>
## Specific Ideas

- The 52-week default for OHLCV aligns with the sparkline spec (DASH-03: "52-week weekly close") — the same endpoint serves both the sparkline and the full TradingView chart (Phase 14 can request more data via query param if needed)
- Report history grouping by run matches the Phase 14 timeline UX: each entry = one assessment event, not two language rows
- Tier + verdict in history items enables a rich timeline without N+1 fetches — hover/preview shows the verdict without loading the full report

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/routers/reports.py`: Existing router with POST /generate, GET /stream/{job_id}, GET /{job_id} — new endpoints added alongside
- `reasoning/app/dependencies.py`: Lifespan with db_engine, neo4j_driver, qdrant_client on app.state — new endpoints use db_engine
- `reasoning/app/routers/health.py`: Health endpoint pattern — stays public

### Established Patterns
- SQLAlchemy Core with `Table(..., autoload_with=db_engine)` for all DB operations — no ORM
- Pydantic v2 BaseModel for request/response schemas
- `reasoning/app/models/tables.py`: Existing model definitions
- HTTPException for error responses with `detail` string

### Integration Points
- `stock_ohlcv` table: symbol, resolution, open, high, low, close, volume, data_as_of — filter by resolution='weekly'
- `gold_etf_ohlcv` table: ticker, resolution, open, high, low, close, volume, data_as_of — same schema, different key column
- `reports` table: asset_id (format "TICKER:asset_type"), language, report_json (JSONB with tier/verdict), generated_at
- FastAPI app in `reasoning/app/__init__.py` — router registration point
- Docker network: reasoning — no new services, just new routes on existing service

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-backend-api-contracts-and-jwt-middleware*
*Context gathered: 2026-03-18*
