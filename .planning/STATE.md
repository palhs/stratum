---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Analytical Reasoning Engine
status: unknown
last_updated: "2026-03-12T18:26:41Z"
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-09)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** v2.0 Analytical Reasoning Engine — Phase 4 complete. Phase 5 in progress.

## Current Position

Milestone: v2.0 — Analytical Reasoning Engine
Phase: 5 of 9 complete (Retrieval Layer Validation)
Plan: 03 of 3 complete — Phase 5 DONE (Qdrant hybrid retriever, 6 integration tests; full retrieval layer validated)
Status: Phase 5 complete — Phase 6 (Reasoning Engine) is next
Last activity: 2026-03-12 — 05-03 complete: Qdrant hybrid dense+sparse retriever, language + ticker filtering, freshness warnings, 6 integration tests pass; full retrieval layer (Neo4j + PostgreSQL + Qdrant) validated

Progress: [████░░░░░░] 37% (10/27 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 3 (v2.0)
- Average duration: ~7 min
- Total execution time: ~22 min

| Phase-Plan | Duration | Tasks | Files |
|---|---|---|---|
| 03-01 | ~10 min | - | - |
| 03-02 | ~10 min | - | - |
| 03-03 | ~2 min | 2 | 2 |
| 03-04 | ~1 min | 2 | 2 |
| 04-01 | ~3 min | 2 | 3 |
| 04-03 | ~8 min | 1 | 3 |
| 04-04 | ~15 min | 1 | 2 |
| 04-02 | ~2 min | 1 | 1 |
| 05-01 | ~7 min | 2 | 11 |
| 05-02 | ~15 min | 2 | 6 |
| 05-03 | ~15 min | 2 | 3 |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key decisions active for v2.0:
- Gemini API only (no local LLM fallback) — simplify reasoning pipeline
- Manual document corpus for v2.0 — validate quality before automating ingestion
- Split v2.0 (engine) / v3.0 (UI) — ship analytical quality first
- Both-layer regime classification — quantitative similarity + LLM interpretation
- JSON + Markdown report output — PDF deferred to v3.0
- Bilingual (VN + EN) in v2.0, generated from structured data (not translation)
- Entry quality is qualitative tier only — no numeric score (anti-feature)
- FastAPI stays in v2.0 (SRVC-01 to SRVC-08) — research suggested deferral but requirements include it
- mem_limit via legacy Docker key (not deploy.resources) — project uses non-Swarm Docker deployment [03-02]
- Neo4j heap initial=max=1G to eliminate GC heap-growth pauses — total JVM 1.5GB within 2g container [03-02]
- GEMINI_API_KEY env block in docker-compose deferred to Phase 8 when reasoning-engine service exists [03-02]
- [Phase 03-01]: Include report_markdown column alongside report_json in reports table — pre-rendered Markdown for Phase 7 API speed
- [Phase 03-01]: report_jobs FK to reports is nullable — job created at pending state before report_id exists, set on completion
- [Phase 03-03]: Checkpoints in langgraph schema (not public) — avoids table collision, Phase 6 connects via ?options=-csearch_path=langgraph
- [Phase 03-03]: psycopg3 synchronous (not async) for init script — async unnecessary for one-shot DDL
- [Phase 03-03]: Raw DDL instead of AsyncPostgresSaver.setup() — library targets public schema only with no schema parameter
- [Phase 03-03]: langgraph-init profiles reasoning only — checkpoint schema not needed for ingestion-only deployments
- [Phase 03-04]: ROADMAP.md Phase 3 SC #2 lists 5 existing services with data-sidecar 512MB; reasoning-engine mem_limit deferred to Phase 8 when SRVC-05 creates the service
- [Phase 03-04]: ROADMAP.md Phase 3 SC #4 references .env.example as deliverable; live Gemini API validation deferred to Phase 8
- [Phase 03-04]: INFRA-03 scope is 5 existing services; reasoning-engine 2GB is not a Phase 3 deliverable
- [Phase 04-03]: FOMC manifest covers 15 key monetary policy turning points (2008-2024) focused on regime-defining moments rather than complete coverage
- [Phase 04-03]: SBV manifest uses null-filename sentinel pattern — script skips entries gracefully, user downloads PDFs manually and updates manifest
- [Phase 04-03]: uuid5 with fixed namespace UUID for deterministic Qdrant point IDs — idempotent re-runs overwrite same points without duplication
- [Phase 04-01]: 17 regime nodes defined (within 15-20 range); natural era boundaries drove count — no forced truncation
- [Phase 04-01]: VN macro values (sbv_rate, vn_cpi, vnd_usd) manually curated from SBV/World Bank; null only for new_regime_2025 gdp_avg (still unfolding)
- [Phase 04-01]: Seed script excludes neo4j from sidecar/requirements.txt — runs standalone or in dedicated seed container
- [Phase 04-04]: All 120 manifest entries start filename=null — intentional; seed script skips null entries with count log; user downloads then updates filename and re-runs
- [Phase 04-04]: 12 large-cap VN30 tickers marked lang=en (English IR reports available); 18 marked lang=vi with degraded-embedding-quality warning
- [Phase 04-04]: Batch-per-ticker upload pattern for earnings_docs — all chunks for a ticker accumulated then uploaded in single upload_points call
- [Phase 04-02]: SIMILARITY_THRESHOLD=0.75 chosen as conservative starting point — sparse connectivity for edge regimes is acceptable
- [Phase 04-02]: Both-direction HAS_ANALOGUE creation: if A is analogue of B, also create B->A relationship for Phase 5/6 directional traversal
- [Phase 04-02]: new_regime_2025 excluded from similarity computation due to null gdp_avg — 16 of 17 regimes participate in analogue graph
- [Phase 05-01]: Pydantic v2 BaseModel for all retrieval return types — enables IDE autocomplete for Phase 6 LangGraph nodes
- [Phase 05-01]: recreate_hybrid_collection() deletes + recreates Qdrant doc collections — guarantees named-vector config on every init run; seed scripts must be re-run after init
- [Phase 05-01]: BM25 sparse vectors computed at index time by seed scripts — LlamaIndex only generates sparse query vectors at search time
- [Phase 05-01]: warnings: list[str] = [] on all Pydantic return types — freshness/data-quality warnings propagate through pipeline without exceptions
- [Phase 05-01]: now_override parameter on check_freshness() — deterministic test assertions without mocking datetime
- [Phase 05-02]: Neo4jPropertyGraphStore used (not PropertyGraphIndex.from_documents) — Phase 4 graph already exists; avoid re-indexing
- [Phase 05-02]: get_regime_analogues() falls back to empty list on LLM failure — graceful degradation for Phase 6 nodes
- [Phase 05-02]: PostgreSQL tests run in Docker reasoning network — postgres has no host port mapping (locked INFRA decision)
- [Phase 05-02]: RegimeParams Field descriptions include actual node ID format hints — mitigates LLM hallucination on keyword extraction
- [Phase 05-03]: Explicit BM25 sparse encoder injection bypasses SPLADE auto-detection — LlamaIndex 0.9.x treats "text-sparse" as old-format, falls back to torch-dependent SPLADE; explicit sparse_doc_fn/sparse_query_fn with fastembed_sparse_encoder fixes this
- [Phase 05-03]: Language filter via MetadataFilters at retriever level (not constructor-level qdrant_filters) — stable across LlamaIndex versions, correctly builds Qdrant FieldCondition
- [Phase 05-03]: Collection-specific alpha weights: macro=0.7 (dense-favored for FOMC policy language), earnings=0.5 (balanced for keyword-heavy financial data + narrative)

### Pending Todos

- Vietnamese financial term dictionary must be authored before Phase 6 compose_report node is built (content asset, not code)
- Gemini model selection (2.0-flash vs 2.5-flash) — benchmark during Phase 6 before committing to production config
- Neo4j historical regime data coverage plan — RESOLVED in 04-01: 17 regime nodes defined with FRED averages; pending: compute actual FRED period averages from fred_indicators table (Plans 04-02+)

### Blockers/Concerns

- WGC gold data still 501 — gold valuation must function without central bank buying data; reports must explicitly flag this as a known gap via DATA WARNING section
- REQUIREMENTS.md traceability section stated 30 requirements; actual count is 34 (6 INFRA + 4 DATA + 4 RETR + 7 REAS + 5 REPT + 8 SRVC) — traceability table corrected

## Session Continuity

Last session: 2026-03-12
Stopped at: Completed 05-03-PLAN.md — Qdrant hybrid retriever (search_macro_docs, search_earnings_docs), 6 integration tests pass; full retrieval layer validated; Phase 5 complete
Resume file: None
