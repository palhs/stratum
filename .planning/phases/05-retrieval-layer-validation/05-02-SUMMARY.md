---
phase: 05-retrieval-layer-validation
plan: 02
subsystem: retrieval
tags: [neo4j, postgresql, llama-index, cypher, sqlalchemy, pydantic, tdd, integration-tests]

# Dependency graph
requires:
  - phase: 05-01
    provides: "Pydantic return types (RegimeAnalogue, FundamentalsRow, etc.), freshness.py, conftest.py fixtures"
  - phase: 04-knowledge-graph-population
    provides: "Neo4j regime analogue graph with HAS_ANALOGUE relationships and Phase 4 Gemini narratives"
  - phase: 02-data-ingestion
    provides: "PostgreSQL tables (stock_fundamentals, structure_markers, gold_etf_ohlcv) with seeded data"

provides:
  - "Neo4j CypherTemplateRetriever with get_all_analogues() (deterministic) and get_regime_analogues() (LLM-parameterized)"
  - "PostgreSQL direct query functions for 5 tables with freshness warnings"
  - "NoDataError raised on empty results for all retrievers"
  - "10 Neo4j integration tests + 17 PostgreSQL integration tests (16 pass, 1 skipped)"
  - "Complete retrieval public API in reasoning/app/retrieval/__init__.py"

affects:
  - "05-03 (Qdrant retriever — completes Plan 03)"
  - "06-reasoning-engine (LangGraph nodes import get_all_analogues, get_fundamentals, get_structure_markers)"
  - "07-report-generator"

# Tech tracking
tech-stack:
  added:
    - "llama-index-graph-stores-neo4j>=0.3.0 — Neo4jPropertyGraphStore for structured_query"
    - "llama-index-core — CypherTemplateRetriever for LLM-parameterized Cypher"
    - "psycopg2-binary + sqlalchemy Core — sync PostgreSQL direct queries"
  patterns:
    - "Deterministic retrieval: structured_query(CYPHER_ALL_ANALOGUES) returns all HAS_ANALOGUE relationships"
    - "LLM-parameterized retrieval: CypherTemplateRetriever + RegimeParams Pydantic model"
    - "NoDataError pattern: raise on empty rows, callers catch and handle gracefully"
    - "Freshness injection: check_freshness(row.data_as_of, threshold, source, now_override) per row"
    - "Engine injection: each retriever accepts optional engine= parameter for test isolation"
    - "TDD: failing tests committed (RED) before implementation (GREEN) for both tasks"

key-files:
  created:
    - "reasoning/app/retrieval/neo4j_retriever.py — get_all_analogues(), get_regime_analogues(), _query_analogues_by_cypher()"
    - "reasoning/app/retrieval/postgres_retriever.py — get_fundamentals(), get_structure_markers(), get_fred_indicators(), get_gold_price(), get_gold_etf()"
    - "reasoning/tests/test_neo4j_retriever.py — 10 integration tests against live Neo4j"
    - "reasoning/tests/test_postgres_retriever.py — 17 integration tests against live PostgreSQL"
  modified:
    - "reasoning/app/retrieval/__init__.py — added exports for all 7 retriever functions"

key-decisions:
  - "Neo4jPropertyGraphStore used (not PropertyGraphIndex.from_documents) — graph already exists from Phase 4; avoid re-indexing"
  - "CypherTemplateRetriever with RegimeParams Pydantic model — LLM fills regime_keywords from natural language query"
  - "get_regime_analogues() falls back to empty list on LLM failure — caller handles gracefully"
  - "PostgreSQL tests run inside Docker reasoning network — postgres has no host port mapping (locked decision)"
  - "1 test skipped (FEDFUNDS) — fred_indicators table is empty until FRED ingestion runs; test designed to skip gracefully"
  - "RegimeParams Field descriptions include actual regime node IDs — mitigates LLM hallucination on keyword extraction (Pitfall 2)"
  - "_query_analogues_by_cypher() helper centralized — NoDataError raised consistently for all Cypher queries"

requirements-completed: [RETR-01, RETR-03]

# Metrics
duration: 15min
completed: 2026-03-13
---

# Phase 5 Plan 02: Neo4j and PostgreSQL Retriever Implementation Summary

**Neo4j CypherTemplateRetriever with deterministic get_all_analogues() and LLM-parameterized get_regime_analogues(), plus PostgreSQL direct query functions for 5 tables with freshness warnings and NoDataError on empty results**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-13T01:00:00Z
- **Completed:** 2026-03-13T01:15:00Z
- **Tasks:** 2
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- Implemented Neo4j retriever with two retrieval paths: `get_all_analogues()` (deterministic via `structured_query`) and `get_regime_analogues()` (LLM-parameterized via `CypherTemplateRetriever`). Validated against 75 live HAS_ANALOGUE relationships with Phase 4 Gemini narratives.
- Implemented PostgreSQL retriever with 5 query functions covering all required tables. All functions call `check_freshness()` and attach warnings to returned Pydantic rows. Engine injection pattern enables test isolation without mocking.
- Completed full public API in `reasoning/app/retrieval/__init__.py` — all 7 retriever functions plus types and freshness utilities now importable from `reasoning.app.retrieval`.
- Applied TDD throughout: failing tests committed first (RED), then implementation (GREEN). 26 total integration tests (25 pass, 1 skipped for empty FRED table).

## Task Commits

Each task was committed atomically with TDD RED then GREEN:

1. **Task 1 RED: Failing Neo4j tests** — `79f3457` (test)
2. **Task 1 GREEN: Neo4j retriever implementation** — `5c80175` (feat)
3. **Task 2 RED: Failing PostgreSQL tests** — `8070c19` (test)
4. **Task 2 GREEN: PostgreSQL retriever + public API** — `59c47b4` (feat)

## Files Created/Modified

- `reasoning/app/retrieval/neo4j_retriever.py` — Neo4j retriever with get_all_analogues(), get_regime_analogues(), _query_analogues_by_cypher(); 3 Cypher templates; RegimeParams Pydantic model
- `reasoning/app/retrieval/postgres_retriever.py` — 5 PostgreSQL query functions with freshness checks, NoDataError, INFO logging
- `reasoning/tests/test_neo4j_retriever.py` — 10 integration tests: RegimeAnalogue validation, NoDataError behavior, narrative presence
- `reasoning/tests/test_postgres_retriever.py` — 17 integration tests: all 5 tables, lookback params, freshness warnings via now_override
- `reasoning/app/retrieval/__init__.py` — added get_regime_analogues, get_all_analogues, get_fundamentals, get_structure_markers, get_fred_indicators, get_gold_price, get_gold_etf to __all__

## Decisions Made

- Neo4jPropertyGraphStore (not PropertyGraphIndex) — the Phase 4 seeded graph exists; PropertyGraphIndex.from_documents() would attempt to re-index, which is incorrect
- CypherTemplateRetriever falls back to empty list on LLM failure — graceful degradation for Phase 6 nodes that call get_all_analogues() as fallback
- PostgreSQL tests run in Docker (not host) — postgres has no host port mapping (locked INFRA decision); used `docker run --network stratum_reasoning`
- RegimeParams Field descriptions include actual node ID format hints — reduces LLM hallucination risk when extracting keywords

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- venv had no llama-index or sqlalchemy installed — ran `pip install` in existing reasoning/.venv (not committed; production installs from requirements.txt)
- PostgreSQL not accessible from macOS host (no port mapping per locked decision) — used `docker run --network stratum_reasoning` for integration tests
- fred_indicators and gold_price tables empty — 1 test skipped (FEDFUNDS); gold_price NoDataError test validates correct behavior when empty; tests designed to handle this gracefully

## Test Results

```
Neo4j (host):     10 passed in 1.17s
PostgreSQL (Docker): 16 passed, 1 skipped in 0.21s
```

## Next Phase Readiness

- Plan 05-03 can now implement Qdrant hybrid retriever — public API is ready for DocumentChunk return type
- Phase 6 LangGraph nodes can import `get_all_analogues`, `get_fundamentals`, `get_structure_markers` directly from `reasoning.app.retrieval`
- NoDataError pattern established — Phase 6 nodes should catch NoDataError and omit that data source from report rather than failing

---
*Phase: 05-retrieval-layer-validation*
*Completed: 2026-03-13*
