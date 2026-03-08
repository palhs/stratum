# Project Milestones: Stratum

## v1.0 Infrastructure and Data Ingestion (Shipped: 2026-03-09)

**Delivered:** Complete Docker infrastructure with dual-network isolation and automated data ingestion pipeline for Vietnamese stocks, gold, and macroeconomic indicators.

**Phases completed:** 1-2 (7 plans total)

**Key accomplishments:**
- Docker Compose stack with 7 services, dual ingestion/reasoning network isolation, profiles for selective startup, and VPS provisioning
- Storage schemas: PostgreSQL Flyway migrations (V1-V5), Neo4j constraints + APOC triggers, Qdrant 384-dim FastEmbed collections with alias versioning
- FastAPI data-sidecar with vnstock VN30 OHLCV (9,411 rows) and fundamentals (399 rows) ingestion
- Gold (FRED spot price + GLD ETF via yfinance) and FRED macroeconomic indicator ingestion (GDP, CPI, unemployment, rates)
- Pre-computed structure markers: moving averages, ATH/52w drawdowns, percentile rank (9,985 rows)
- Pipeline monitoring: run logging, row-count anomaly detection, n8n weekly/monthly workflows with Telegram error handler
- pytest suite: 46 pass, 13 skip (FRED auth gate by design), 0 fail — validating all 9 DATA requirements

**Stats:**
- 80 files created/modified
- 3,801 lines Python, 317 lines SQL, 216 lines Docker Compose
- 2 phases, 7 plans, 44 commits
- 6 days from start to ship (2026-03-03 → 2026-03-09)

**Git range:** `feat(01-01)` → `feat(02-05)`

**Known tech debt (accepted):**
- Telegram env vars not injected into n8n container (alerts silently fail)
- WGC monthly retry does not short-circuit on 501 (~21 min wasted/month)
- FRED_API_KEY requires manual .env.local setup

**What's next:** Next milestone will cover Phases 3-7 — retrieval validation, analytical reasoning nodes, synthesis/reports, API layer, and frontend.

---

