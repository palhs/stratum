# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Infrastructure and Data Ingestion

**Shipped:** 2026-03-09
**Phases:** 2 | **Plans:** 7

### What Was Built
- Docker Compose infrastructure stack with 7 services, dual ingestion/reasoning network isolation, Docker profiles, Flyway migrations
- FastAPI data-sidecar with vnstock VN30 OHLCV + fundamentals, FRED gold/macro, GLD ETF ingestion endpoints
- Pre-computed structure markers (MAs, ATH/52w drawdowns, percentile rank) — 9,985 rows
- Pipeline monitoring: run logging, row-count anomaly detection, n8n weekly/monthly workflows, Telegram error handler
- pytest suite validating all 9 DATA requirements (46 pass, 13 skip, 0 fail)

### What Worked
- SQLAlchemy Core `pg_insert().on_conflict_do_update()` pattern — clean idempotent upserts across all services, consistent and testable
- Flyway migrations for schema evolution — V1-V5 cleanly layered, each phase adds tables without touching previous ones
- Docker network isolation enforcing INFRA-02 at infrastructure level rather than relying on application-level discipline
- TDD via pytest caught 3 real bugs (MultiIndex flattening, SystemExit propagation, NaN-to-PostgreSQL conversion) before they reached production
- n8n visual workflow debugging — made it easy to trace pipeline execution step-by-step

### What Was Inefficient
- WGC Goldhub research: investigated scraping approaches before concluding the portal is JS-rendered with no stable API — could have identified this earlier with a quick browser DevTools check
- n8n workflow JSON format incompatibility (1.78.0 vs 2.10.2) required upgrading n8n and rewriting workflow JSONs — version pinning from the start would have avoided this
- n8n HTTP Request nodes defaulting to GET instead of POST caused 405 errors on all sidecar endpoints — discovered during end-to-end testing, not during workflow creation
- TELEGRAM env vars omitted from docker-compose.yml n8n service — integration gap not caught until milestone audit

### Patterns Established
- Every time-series table includes `data_as_of` (period the data covers) and `ingested_at` (when ingested) — never confuse observation time with ingestion time
- Pipeline run logging on every endpoint call — success or failure — via `pipeline_log_service.log_pipeline_run()`
- Anomaly detection is alert-only, never blocks ingestion — `anomaly_service` never raises exceptions
- Full recompute strategy for derived data at VN30 scale (< 5s) — avoid incremental complexity until scale demands it
- VN30 symbols fetched dynamically via `Listing.symbols_by_group()` — never hard-coded

### Key Lessons
1. Pin external dependency versions from day one (vnstock, n8n) — breaking changes in minor versions are common in smaller open-source projects
2. Test n8n workflows end-to-end immediately after creating them — JSON authoring without the UI leads to subtle defaults (method, cross-node references)
3. Inject all referenced `$env.*` variables into Docker container environments — n8n silently resolves missing vars to empty string instead of erroring
4. WGC-class data sources (JS-rendered portals with no API) should be flagged as "manual import" from the start — don't plan automation endpoints that will always return 501

### Cost Observations
- Model mix: primarily sonnet for executor/verifier agents, opus for orchestration
- Sessions: ~8 sessions across 6 days
- Notable: yolo mode with comprehensive depth kept velocity high — 7 plans in 6 days with full verification

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~8 | 2 | Established infrastructure and data pipeline patterns |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 59 (46 pass, 13 skip) | 9/9 DATA requirements | 7 tables, 7 endpoints |

### Top Lessons (Verified Across Milestones)

1. Pin dependency versions from day one — verified by vnstock 3.2.3→3.4.2 and n8n 1.78.0→2.10.2 breaking changes
2. Integration gaps between containers are invisible until end-to-end testing — Telegram env vars, n8n method defaults
