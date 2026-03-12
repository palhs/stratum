---
phase: 05-retrieval-layer-validation
plan: 01
subsystem: retrieval
tags: [pydantic, sqlalchemy, fastembed, qdrant, llama-index, bm25, hybrid-search, pytest]

# Dependency graph
requires:
  - phase: 04-knowledge-graph-population
    provides: "Qdrant macro_docs_v1 and earnings_docs_v1 collections; Neo4j regime analogue graph"

provides:
  - "reasoning/ service directory scaffold with shared retrieval modules"
  - "check_freshness() with FRESHNESS_THRESHOLDS for 7 data sources"
  - "7 Pydantic v2 return types (RegimeAnalogue, DocumentChunk, FundamentalsRow, StructureMarkerRow, FredIndicatorRow, GoldPriceRow, GoldEtfRow) + NoDataError"
  - "SQLAlchemy Core table definitions copied from sidecar (all 8 tables)"
  - "Qdrant named-vector hybrid config for macro_docs_v1 and earnings_docs_v1"
  - "Seed scripts updated to compute and store BM25 sparse vectors alongside dense vectors"
  - "21 passing unit tests for freshness logic (including timezone edge cases, now_override)"

affects:
  - "05-02 (postgres retriever)"
  - "05-03 (qdrant + neo4j retriever)"
  - "06-reasoning-engine (LangGraph nodes import these types)"
  - "07-report-generator"

# Tech tracking
tech-stack:
  added:
    - "pydantic v2 (Pydantic BaseModel for typed retrieval returns)"
    - "fastembed SparseTextEmbedding (Qdrant/bm25 for BM25 sparse vectors)"
    - "qdrant-client SparseVector (named vector format for hybrid search)"
    - "pytest + pytest-asyncio (test infrastructure for reasoning/ service)"
  patterns:
    - "Named vector format: {'text-dense': dense_vec, 'text-sparse': SparseVector} for LlamaIndex hybrid search"
    - "now_override parameter pattern for deterministic time-dependent testing"
    - "Warnings-as-return-values pattern: all retrieval types carry warnings: list[str] = []"
    - "recreate_hybrid_collection() in init-qdrant.sh ensures collections always have correct named-vector config"

key-files:
  created:
    - "reasoning/app/retrieval/freshness.py — check_freshness() with FRESHNESS_THRESHOLDS"
    - "reasoning/app/retrieval/types.py — 7 Pydantic v2 return types + NoDataError"
    - "reasoning/app/retrieval/__init__.py — public API exports for retrieval layer"
    - "reasoning/app/models/tables.py — SQLAlchemy Core table definitions (all 8 tables, copied from sidecar)"
    - "reasoning/requirements.txt — Phase 5 dependencies"
    - "reasoning/pytest.ini — test configuration"
    - "reasoning/tests/conftest.py — session-scoped fixtures for Neo4j, Qdrant, PostgreSQL"
    - "reasoning/tests/test_freshness.py — 21 unit tests for freshness logic"
  modified:
    - "scripts/init-qdrant.sh — added recreate_hybrid_collection() for macro_docs_v1 and earnings_docs_v1"
    - "scripts/seed-qdrant-macro-docs.py — updated to use named vectors (text-dense + text-sparse BM25)"
    - "scripts/seed-qdrant-earnings-docs.py — updated to use named vectors (text-dense + text-sparse BM25)"

key-decisions:
  - "Pydantic v2 BaseModel for all retrieval return types — enables IDE autocomplete and runtime validation for Phase 6 LangGraph nodes"
  - "warnings: list[str] = [] on all return types — allows freshness/data-quality warnings to propagate through the pipeline without exceptions"
  - "recreate_hybrid_collection() deletes and recreates doc collections — guarantees named-vector config on every init run"
  - "BM25 sparse vectors computed at index time by seed scripts (not at query time) — LlamaIndex only generates sparse QUERY vectors at runtime"
  - "now_override parameter on check_freshness() — enables deterministic test assertions without mocking datetime"
  - "Session scope for Neo4j/Qdrant/PostgreSQL fixtures — avoids expensive reconnection per test"

patterns-established:
  - "Named vector pattern: {'text-dense': dense_vec, 'text-sparse': SparseVector(indices, values)} for all Qdrant upserts in hybrid collections"
  - "Freshness check pattern: call check_freshness(data_as_of, FRESHNESS_THRESHOLDS[source], source) and append result to warnings list"
  - "NoDataError pattern: raise NoDataError when retriever returns empty results; Phase 6 nodes catch and handle gracefully"

requirements-completed: [RETR-04]

# Metrics
duration: 7min
completed: 2026-03-12
---

# Phase 5 Plan 01: Scaffold Retrieval Layer and Qdrant Hybrid Config Summary

**Pydantic v2 retrieval types, freshness validation with timezone-safe now_override, and Qdrant named-vector (text-dense + BM25 text-sparse) hybrid search migration for macro_docs_v1 and earnings_docs_v1**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-12T17:28:52Z
- **Completed:** 2026-03-12T17:35:53Z
- **Tasks:** 2
- **Files modified:** 11 (8 created, 3 modified)

## Accomplishments

- Scaffolded reasoning/ service directory as foundation for Plans 02-03 (postgres + qdrant/neo4j retrievers) and Phase 6 LangGraph engine
- Implemented check_freshness() with 7-source threshold table; 21 unit tests pass covering fresh/stale detection, timezone-naive handling, now_override, and all threshold constants
- Migrated Qdrant macro_docs_v1 and earnings_docs_v1 collections to named-vector hybrid config (text-dense 384-dim Cosine + text-sparse BM25 IDF) resolving the critical LlamaIndex QdrantVectorStore blocker
- Updated both seed scripts to compute BM25 sparse vectors at index time using fastembed SparseTextEmbedding(Qdrant/bm25)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold reasoning/ directory with shared modules** - `1730080` (feat)
2. **Task 2: Migrate Qdrant collections to named-vector hybrid config** - `27fc4ca` (feat)

## Files Created/Modified

- `reasoning/app/retrieval/freshness.py` — check_freshness() with FRESHNESS_THRESHOLDS dict for 7 sources
- `reasoning/app/retrieval/types.py` — RegimeAnalogue, DocumentChunk, FundamentalsRow, StructureMarkerRow, FredIndicatorRow, GoldPriceRow, GoldEtfRow, NoDataError
- `reasoning/app/retrieval/__init__.py` — public API exports for retrieval layer
- `reasoning/app/models/tables.py` — SQLAlchemy Core table definitions (8 tables, copied from sidecar)
- `reasoning/app/__init__.py` — package init
- `reasoning/app/models/__init__.py` — package init
- `reasoning/requirements.txt` — Phase 5/6+ dependencies
- `reasoning/pytest.ini` — testpaths=tests, asyncio_mode=auto
- `reasoning/tests/__init__.py` — package init
- `reasoning/tests/conftest.py` — session-scoped fixtures for Neo4j, Qdrant, PostgreSQL
- `reasoning/tests/test_freshness.py` — 21 unit tests
- `scripts/init-qdrant.sh` — added recreate_hybrid_collection() for document corpus collections
- `scripts/seed-qdrant-macro-docs.py` — updated embed_and_upsert() to use named vectors + BM25
- `scripts/seed-qdrant-earnings-docs.py` — updated worker_main() to use named vectors + BM25

## Decisions Made

- Pydantic v2 BaseModel (locked decision from research) — IDE autocomplete for Phase 6 LangGraph nodes is critical for maintainability
- recreate_hybrid_collection() deletes + recreates (not create-if-missing) — guarantees correct schema on every init run; seed scripts must be re-run after init
- BM25 sparse vectors at index time — LlamaIndex QdrantVectorStore only generates sparse query vectors at search time; index-time sparse vectors must be pre-computed by seed scripts

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Python test environment had no pydantic installed in system Python 3.11. Created a venv at reasoning/.venv to run tests locally. The venv is not committed; production/CI will install from reasoning/requirements.txt.

## User Setup Required

After running `docker compose up qdrant-init`, the macro_docs_v1 and earnings_docs_v1 collections will be recreated with hybrid named-vector config. Re-run both seed scripts to repopulate with BM25 sparse vectors:

```bash
python scripts/seed-qdrant-macro-docs.py
python scripts/seed-qdrant-earnings-docs.py
```

## Next Phase Readiness

- Plans 02-03 can now import from `reasoning.app.retrieval` — all shared types and freshness logic are ready
- Qdrant collections will have correct named-vector schema after next qdrant-init run + seed
- Phase 6 LangGraph nodes can import RegimeAnalogue, DocumentChunk, etc. directly from reasoning.app.retrieval

---
*Phase: 05-retrieval-layer-validation*
*Completed: 2026-03-12*
