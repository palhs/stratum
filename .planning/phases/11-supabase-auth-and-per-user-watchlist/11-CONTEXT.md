# Phase 11: Supabase Auth and Per-User Watchlist - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up invite-only Supabase authentication, create watchlist schema in VPS PostgreSQL (Flyway V8), build watchlist CRUD endpoints on the reasoning-engine FastAPI, and migrate JWT verification from HS256/raw-secret to RS256/JWKS (Supabase's current default). No frontend code (Phase 12), no new data ingestion pipelines.

</domain>

<decisions>
## Implementation Decisions

### JWT verification migration
- Current auth.py uses HS256 with SUPABASE_JWT_SECRET — must migrate to RS256 with JWKS endpoint
- User's Supabase project only has JWK-format signing keys (no legacy plain-text secret available)
- Fetch public keys from `https://<project>.supabase.co/auth/v1/jwks` for verification
- Replace PyJWT HS256 decode with RS256 decode using JWKS-fetched public key

### Default watchlist seeding
- Curated 5-8 tickers seeded on first login (not at invite time)
- Default tickers stored in a config table in the database (admin-editable without redeploying)
- Gold (GLD) always included in defaults
- Backend detects no watchlist rows for user_id on first authenticated request and seeds from defaults table

### Admin invite workflow
- Use Supabase dashboard's built-in "Invite user" — no custom invite code needed
- Public signup disabled at Supabase project level only (no additional frontend/backend enforcement)
- User sets their own password via Supabase invite email link
- Default Supabase email template (no custom branding or Vietnamese text)

### Watchlist ticker universe
- VN30 (fixed list of current constituents) + GLD
- XAUUSD desired but data source not yet ingested — deferred to separate phase
- Watchlist only accepts tickers that exist in stock_ohlcv or gold_etf_ohlcv (backend validates on add)
- VN30 list hardcoded for now; manual update on index rebalance

### Watchlist API design
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

</decisions>

<specifics>
## Specific Ideas

- The GET /watchlist response includes name and asset_type so the frontend can render cards without a second lookup — matches the dashboard card spec (DASH-01, DASH-02)
- PUT /watchlist batch approach keeps the API simple for a small watchlist (max 30) — no need for individual add/remove endpoints
- First-login seeding is decoupled from invite flow — Supabase handles auth, VPS PostgreSQL handles data

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/auth.py`: require_auth dependency — needs RS256/JWKS migration but same interface (returns decoded JWT payload)
- `reasoning/app/dependencies.py`: Lifespan with db_engine on app.state — watchlist endpoints use same DB connection
- `reasoning/app/schemas.py`: Pydantic v2 schemas pattern — add WatchlistResponse, WatchlistUpdate
- `reasoning/app/routers/`: Router registration pattern — add watchlist.py router

### Established Patterns
- SQLAlchemy Core with Table autoload for all DB operations (no ORM)
- Flyway migrations V1-V7 for schema changes — watchlist = V8
- HTTPException with detail string for errors
- JWT payload `sub` claim contains Supabase user UUID

### Integration Points
- `docker-compose.yml`: SUPABASE_JWT_SECRET env var — needs replacement with SUPABASE_URL or JWKS URL
- `stock_ohlcv` and `gold_etf_ohlcv` tables: source of valid ticker symbols for watchlist validation
- FastAPI app in `reasoning/app/__init__.py`: router registration point for /watchlist

</code_context>

<deferred>
## Deferred Ideas

- XAUUSD spot price ingestion — user wants XAUUSD in the watchlist universe, but data pipeline doesn't exist yet. Add as Phase 11.1 or fold into Phase 16.
- Custom Vietnamese invite email template — can be configured in Supabase dashboard later without code changes
- Dynamic VN30 list from index rebalance feed — manual update sufficient for now

</deferred>

---

*Phase: 11-supabase-auth-and-per-user-watchlist*
*Context gathered: 2026-03-18*
