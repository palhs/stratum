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

## Milestone: v2.0 — Analytical Reasoning Engine

**Shipped:** 2026-03-17
**Phases:** 8 (3-9 + 8.1 gap closure) | **Plans:** 28

### What Was Built
- 7-node LangGraph reasoning pipeline (macro_regime → valuation → structure → conflict → entry_quality → grounding_check → compose_report) with PostgreSQL checkpointing
- Neo4j knowledge graph: 17 macro regime nodes with cosine-similarity HAS_ANALOGUE relationships and Gemini narratives
- Triple-store hybrid retrieval: Neo4j CypherTemplateRetriever, Qdrant dense+sparse, PostgreSQL direct queries — all with freshness monitoring
- Bilingual reports: Vietnamese (162-term dictionary + Gemini narrative rewrite) and English, with DATA WARNING sections
- FastAPI reasoning-engine: POST /reports/generate (BackgroundTask), GET /reports/{id}, SSE streaming, health endpoint
- Production tooling: 20-stock batch validation, Gemini spend cap, checkpoint TTL cleanup

### What Worked
- Deterministic labels with LLM-generated narratives — every node computes its classification in Python, Gemini only writes the narrative. Made grounding check possible and debugging straightforward
- Phase-by-phase dependency chain — data → retrieval → nodes → graph → API → hardening. Each phase validated independently before building on top. Never hit a "works locally, breaks integrated" issue
- TDD approach across all phases — 200+ tests caught real issues (import path conflicts, route ordering, structured output schema mismatches) before they reached integration
- Milestone audit with integration checker — caught the Docker import path mismatch and missing langgraph-init dependency before deployment, not after
- Wave-based parallel execution — Phases 6 (5 plans) and 9 (3 plans) executed multiple agents in parallel, cutting wall-clock time significantly

### What Was Inefficient
- Docker import path mismatch (Phase 8.1) — the Dockerfile `COPY app/ ./app/` created a namespace that didn't match `from reasoning.app.*` imports. Should have been caught by a container smoke test in Phase 8, not discovered during milestone audit
- Phase 6 SUMMARY frontmatter authoring — 4 out of 5 SUMMARYs had empty `requirements_completed` lists despite the VERIFICATION confirming all requirements satisfied. Caused noise in the 3-source cross-reference
- Gemini model name confusion — `gemini-2.0-flash` vs `gemini-2.0-flash-001` vs `gemini-2.5-pro` naming changed during development. One node had the wrong suffix initially
- No live E2E test until after Phase 8 — all tests mocked the LLM and database. The first actual pipeline run will be during the batch validation (Phase 9), not during development

### Patterns Established
- Labels deterministic, LLM for narrative only — prevents hallucinated classifications while still getting natural language output
- Shared `ReportState` TypedDict with `total=False` — each node reads only what it needs, no full-state coupling
- `with_structured_output(PydanticModel)` pattern — consistent across all 7 LLM call sites, easy to swap models later
- Lazy import for pipeline entry point — `_get_generate_report()` defers heavy import chain, keeping FastAPI startup fast
- Route ordering matters — `GET /stream/{id}` before `GET /{id}` prevents FastAPI treating "stream" as a path parameter
- Cascade delete order for checkpoint tables — writes → blobs → checkpoints (no FKs, manual ordering required)

### Key Lessons
1. Always run a container smoke test (build + import + basic request) as part of the Docker phase — don't defer to milestone audit
2. SUMMARY frontmatter `requirements_completed` should be enforced, not optional — empty lists create audit noise
3. The gap closure pattern (audit → insert phase → fix → re-verify) works well for post-phase integration issues
4. Cost analysis BEFORE choosing models — gemini-2.5-pro works but at $0.04-0.07/report when flash-lite at $0.002/report would suffice for structured output with deterministic labels
5. Vietnamese narrative quality is the only place premium model quality matters — all other nodes produce short structured output that any model can handle

### Cost Observations
- Model mix: sonnet for all executor/verifier/researcher agents, opus for orchestration
- Sessions: ~10 sessions across 9 days
- Notable: parallel wave execution in Phase 6 and Phase 9 was the biggest velocity win — 5 independent nodes built simultaneously

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~8 | 2 | Established infrastructure and data pipeline patterns |
| v2.0 | ~10 | 8 | Parallel wave execution, milestone audit with integration checker, gap closure pattern |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 59 (46 pass, 13 skip) | 9/9 DATA requirements | 7 tables, 7 endpoints |
| v2.0 | 200+ (all pass) | 34/34 requirements | 7 nodes, 4 API routes, 3 scripts |

### Top Lessons (Verified Across Milestones)

1. Pin dependency versions from day one — verified by vnstock, n8n, and Gemini model naming issues across v1.0 and v2.0
2. Integration gaps between containers are invisible until end-to-end testing — Telegram env vars (v1.0), Docker import paths (v2.0)
3. Milestone audit catches issues that phase-level verification misses — cross-phase wiring, import namespace conflicts, missing depends_on declarations
4. Deterministic logic + LLM narrative is more reliable than pure LLM reasoning — grounding check validates what Python computed, not what the LLM decided
