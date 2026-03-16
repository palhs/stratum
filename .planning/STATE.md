---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Analytical Reasoning Engine
status: unknown
last_updated: "2026-03-16T05:19:01.079Z"
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 21
  completed_plans: 21
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-09)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** v2.0 Analytical Reasoning Engine — Phase 7 in progress (Graph Assembly and End-to-End Report Generation).

## Current Position

Milestone: v2.0 — Analytical Reasoning Engine
Phase: 7 of 9 in progress (Graph Assembly and End-to-End Report Generation)
Plan: 05 of 5 complete — PostgreSQL report storage (write_report via SQLAlchemy Core), generate_report() async public entry point (prefetch → run_graph(vi) → write → run_graph(en) → write), E2E integration test suite (9 mocked tests + 1 integration placeholder); all 6 Phase 7 requirements satisfied (REAS-06, REPT-01 through REPT-05)
Status: Phase 7 COMPLETE — all 5 plans complete (07-01 through 07-05); Phase 8 FastAPI next
Last activity: 2026-03-16 — 07-05 complete: storage.py (write_report SQLAlchemy Core INSERT + RETURNING), __init__.py updated (generate_report() entry point with deepcopy isolation between vi/en), test_storage.py (19 tests), test_e2e.py (9 mocked E2E + 1 integration placeholder); 130 pipeline tests pass; REPT-05 + REAS-06 satisfied

Progress: [██████░░░░] 66% (19/29 plans)

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
| 06-01 | ~25 min | 2 | 8 |
| 06-02 | ~4 min | 1 (TDD) | 2 |
| 06-03 | ~6 min | 1 (TDD) | 2 |
| 06-04 | ~5 min | 2 (TDD) | 4 |
| 06-05 | ~5 min | 2 (TDD) | 3 |

*Updated after each plan completion*
| Phase 07 P01 | 5 min | 1 tasks | 6 files |
| Phase 07 P02 | 6 min | 1 tasks | 5 files |
| Phase 07 P03 | ~15 min | 2 tasks | 3 files |
| Phase 07 P04 | ~12 min | 2 tasks | 4 files |
| Phase 07 P05 | ~15 min | 2 tasks | 5 files |

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
- [Phase 06-01]: Deterministic label overrides Gemini label in structure_node — rules assign tier, Gemini writes narrative only; prevents hallucination of tier labels
- [Phase 06-01]: patch.object(structure_module, 'ChatGoogleGenerativeAI') in tests vs string-path patch — avoids module reload ordering issues with pytest import caching
- [Phase 06-01]: gemini-2.0-flash deprecated for new users (404 NOT_FOUND); update to gemini-2.0-flash-001 before first live integration test in later plans
- [Phase 06-01]: MIXED_SIGNAL_THRESHOLD=0.70 uses strict less-than semantics (top_confidence < 0.70 → is_mixed_signal=True)
- [Phase 06-01]: Node function signature: (state: ReportState) -> dict[str, Any] — single dict return with state update key; established as canonical pattern for all nodes
- [Phase 06-02]: Real yield proxy = GS10 - 2.5% (constant breakeven) — CPIAUCSL index level cannot be directly converted to YoY without prior period; approximation acceptable for regime-level gold assessment
- [Phase 06-02]: pe_vs_analogue_avg = None (not parsed from narrative text) — analogue P/E is prose context for Gemini, not a structured field in RegimeAnalogue; Gemini contextualizes the comparison in narrative
- [Phase 06-02]: VN equity valuation thresholds: P/E <10x = Attractive, >20x = Stretched (VN30 historical range 10-18x); P/B <1.0 = Attractive, >3.5 = Stretched
- [Phase 06-02]: Gemini model updated to gemini-2.0-flash-001 in valuation.py (gemini-2.0-flash returns 404 for new users — confirmed in 06-01 issues)
- [Phase 06-03]: is_mixed_signal computed deterministically in Python (not LLM-dependent) — prevents LLM from misapplying strict <0.70 threshold; 0.70 exactly is NOT mixed signal
- [Phase 06-03]: top_two_analogues derived from sorted regime_probabilities[0:2].source_analogue_id; cleared to [] when not mixed signal
- [Phase 06-03]: macro_label sanitized via _sanitize_macro_label() with case-insensitive fallback — handles LLM casing variations
- [Phase 06-03]: MIXED_SIGNAL_THRESHOLD imported from state.py (canonical source) not redefined locally; temperature=0.1 for probability distribution consistency
- [Phase 06-04]: NAMED_CONFLICT_PATTERNS is a static dict — conflict detection is O(1) lookup; Gemini writes narrative only; pattern_name and severity are rule-derived (not LLM)
- [Phase 06-04]: composite_tier and structure_veto_applied always overridden deterministically in entry_quality_node — LLM generates narrative only; tier is rules-based
- [Phase 06-04]: structure_veto_applied=True recorded even when tier is already at or below the veto cap — preserves signal for downstream consumers
- [Phase 06-04]: Minor conflict: no automatic downgrade; major conflict: +1 TIER_ORDER index (exactly one level worse)
- [Phase 06-04]: No-conflict fast path in conflicting_signals_handler: returns None without calling Gemini when pattern not in NAMED_CONFLICT_PATTERNS
- [Phase 06]: type(model).model_fields used instead of model.model_fields — Pydantic v2.11 deprecated instance access, removed in v3; accessing via class is correct pattern
- [Phase 06]: grounding_check_node checks only macro_regime_output, valuation_output, structure_output — entry_quality_output and conflict_output excluded (no raw numeric claims requiring record-level attribution)
- [Phase 07-01]: Placeholder compose_report_node in graph.py returns None — real implementation in Plan 02; avoids blocking graph assembly on report generation logic
- [Phase 07-01]: prefetch() silently catches retrieval exceptions and returns empty lists — graceful degradation pattern; nodes must handle empty inputs
- [Phase 07-01]: AsyncPostgresSaver imported inside run_graph() body — avoids psycopg3 import errors in test environments where only psycopg2 is available
- [Phase 07]: report_json uses json.loads(card.model_dump_json(exclude_none=True)) — flat dict suitable for JSONB storage, no nested Pydantic instances
- [Phase 07]: WGC gold data gap always flagged for gold assets with fixed warning string — known HTTP 501 on central bank buying endpoint
- [Phase 07]: conflict card excluded via exclude_none=True serialization — ReportCard.conflict=None omits key from JSONB output
- [Phase 07-04]: _rewrite_narrative_vi is synchronous (model.invoke()) — compose_report_node is sync LangGraph node; async would require graph restructuring
- [Phase 07-04]: apply_terms() applied to serialized dict after narrative re-generation — term_dict.py design contract: operates on plain dict, not Pydantic model
- [Phase 07-04]: render_markdown called with ReportCard containing Vietnamese narratives (labels still English in model) — Markdown renderer uses card_headers from term_dict for section headers
- [Phase 07-04]: _rewrite_narrative_vi has graceful degradation — returns English narrative if Gemini call fails; pipeline never blocked by translation failure
- [Phase 07-04]: data_as_of computed from min timestamp across retrieval row lists; falls back to datetime.now(UTC) when no timestamps present in rows
- [Phase 07-05]: write_report() uses SQLAlchemy Core Table reflection (autoload_with=db_engine) — consistent with postgres_retriever.py; stateless, no model imports needed
- [Phase 07-05]: generate_report() deep-copies prefetch state between vi and en invocations — prevents vi LangGraph execution from contaminating en state via shared mutable objects
- [Phase 07-05]: pipeline_duration_ms measured via time.monotonic() per-language run — immune to clock drift; millisecond resolution
- [Phase 07-05]: E2E tests fully mocked (no Docker required for non-integration mark) — fast CI execution; 'integration' marker registered in pytest.ini for Docker-dependent tests
- [Phase 07-05]: venv created at reasoning/.venv — system python3.11 had brownie pytest plugin with broken web3 dependency; isolated venv resolves pytest startup failures cleanly

### Pending Todos

- [RESOLVED 07-03] Vietnamese financial term dictionary authored, user-approved, and ready for import by compose_report_node in Plan 04
- Gemini model selection (2.0-flash vs 2.5-flash) — benchmark during Phase 6 before committing to production config
- Neo4j historical regime data coverage plan — RESOLVED in 04-01: 17 regime nodes defined with FRED averages; pending: compute actual FRED period averages from fred_indicators table (Plans 04-02+)

### Blockers/Concerns

- WGC gold data still 501 — gold valuation must function without central bank buying data; reports must explicitly flag this as a known gap via DATA WARNING section
- REQUIREMENTS.md traceability section stated 30 requirements; actual count is 34 (6 INFRA + 4 DATA + 4 RETR + 7 REAS + 5 REPT + 8 SRVC) — traceability table corrected

## Session Continuity

Last session: 2026-03-16
Stopped at: Completed 07-05-PLAN.md — storage.py (write_report SQLAlchemy Core INSERT + RETURNING), generate_report() async entry point with deepcopy isolation, test_storage.py (19 tests), test_e2e.py (9 mocked E2E tests); 130 pipeline tests pass; Phase 7 COMPLETE — all 6 requirements satisfied (REAS-06, REPT-01 through REPT-05)
Resume file: None
