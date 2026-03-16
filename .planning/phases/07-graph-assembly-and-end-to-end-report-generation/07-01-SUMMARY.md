---
phase: 07-graph-assembly-and-end-to-end-report-generation
plan: "01"
subsystem: pipeline
tags: [langgraph, stategraph, prefetch, two-stage-pipeline, checkpointing]
dependency_graph:
  requires:
    - "06-05 (grounding_check_node, all 6 Phase 6 nodes)"
    - "05-01 (retrieval types and freshness)"
    - "05-02 (neo4j_retriever)"
    - "05-03 (qdrant_retriever)"
    - "03-03 (langgraph schema in PostgreSQL)"
  provides:
    - "build_graph() — 7-node linear StateGraph ready for compilation"
    - "run_graph() — async graph invocation with AsyncPostgresSaver checkpointing"
    - "prefetch() — two-stage data retrieval for equity and gold asset paths"
    - "ReportOutput Pydantic model for structured report output"
    - "ReportState extended with language and report_output fields"
  affects:
    - "07-02 (compose_report_node — replaces placeholder in graph.py)"
    - "07-05 (generate_report — end-to-end orchestrator)"
tech_stack:
  added:
    - "reasoning/app/pipeline/ module (3 files)"
    - "ReportOutput Pydantic model (state.py)"
  patterns:
    - "TDD: RED (19 failing tests) → GREEN (all 19 pass)"
    - "Two-stage pipeline: prefetch() retrieves data, run_graph() executes nodes"
    - "Placeholder node pattern: compose_report_node returns None until Plan 02"
key_files:
  created:
    - reasoning/app/pipeline/__init__.py
    - reasoning/app/pipeline/graph.py
    - reasoning/app/pipeline/prefetch.py
    - reasoning/tests/pipeline/__init__.py
    - reasoning/tests/pipeline/test_graph.py
  modified:
    - reasoning/app/nodes/state.py
decisions:
  - "Placeholder compose_report_node in graph.py returns {report_output: None} — real implementation in Plan 02; avoids blocking graph assembly on report generation logic"
  - "prefetch() accepts db_engine/neo4j_driver/qdrant_client for test injection — consistent with Phase 5 retrieval function patterns"
  - "get_regime_analogues() called with a default macro query string in prefetch — avoids requiring caller to construct query text; Plan 06 macro_regime node uses this data"
  - "prefetch() silently catches retrieval exceptions and returns empty lists — graceful degradation; node warnings propagate the gap to callers"
  - "run_graph() uses copy.deepcopy(state) before mutation — prevents caller side-effects when run_graph modifies state['language']"
  - "AsyncPostgresSaver imported inside run_graph() body (not module level) — avoids psycopg3 import errors in test environments where only psycopg2 is available"
metrics:
  duration: "~5 min"
  completed_date: "2026-03-16"
  tasks_completed: 1
  files_created: 5
  files_modified: 1
  tests_written: 19
  tests_passing: 19
---

# Phase 7 Plan 01: Graph Assembly and Prefetch Summary

**One-liner:** 7-node linear StateGraph with AsyncPostgresSaver checkpointing and two-stage prefetch for equity/gold asset paths using all Phase 6 nodes.

## What Was Built

### reasoning/app/nodes/state.py (modified)
- Added `ReportOutput` Pydantic model with 7 fields: `report_json`, `report_markdown`, `language`, `data_as_of`, `data_warnings`, `model_version` (default `"gemini-2.5-pro"`), `warnings` (default `[]`)
- Added `datetime` import (required by `data_as_of: datetime` field)
- Extended `ReportState` TypedDict with:
  - `language: str` — set by `run_graph()` caller ("vi" or "en")
  - `report_output: Optional[ReportOutput]` — written by `compose_report_node` in Plan 02

### reasoning/app/pipeline/graph.py (created)
- `build_graph() -> StateGraph` — assembles 7 nodes with 8 linear edges
  - Node names: `macro_regime`, `valuation`, `structure`, `conflict`, `entry_quality`, `grounding_check`, `compose_report`
  - Placeholder `compose_report_node` returns `{"report_output": None}`
- `run_graph(state, language, thread_id, db_uri) -> ReportState` — async, compiles with `AsyncPostgresSaver`, uses `?options=-csearch_path%3Dlanggraph` connection suffix

### reasoning/app/pipeline/prefetch.py (created)
- `prefetch(ticker, asset_type, db_engine, neo4j_driver, qdrant_client) -> dict`
  - **Equity path:** `get_fundamentals`, `get_structure_markers`, `get_fred_indicators`, `search_earnings_docs`, `search_macro_docs`, `get_regime_analogues`
  - **Gold path:** `get_gold_price`, `get_gold_etf`, `get_structure_markers("GOLD")`, `get_fred_indicators`, `search_macro_docs`, `get_regime_analogues`
  - Invalid `asset_type` raises `ValueError`
  - All retrieval failures caught and logged; returns empty lists (graceful degradation)
  - Returns complete `ReportState`-shaped dict with all node outputs as `None`

### reasoning/app/pipeline/__init__.py (created)
- Exports `build_graph`, `run_graph`, `prefetch` (generate_report added in Plan 05)

## Deviations from Plan

None — plan executed exactly as written.

## TDD Execution

- **RED phase:** 19 failing tests committed (`test(07-01)` commit)
- **GREEN phase:** All 19 tests pass after implementation (`feat(07-01)` commit)
- No REFACTOR phase needed — code is clean as written

## Verification Results

```
reasoning/.venv/bin/python -m pytest reasoning/tests/pipeline/test_graph.py -x -v
19 passed in 1.67s
```

```
python -c "from reasoning.app.pipeline import build_graph, run_graph, prefetch"
# SUCCESS
python -c "from reasoning.app.nodes.state import ReportOutput, ReportState"
# SUCCESS
```

## Self-Check: PASSED
- `reasoning/app/pipeline/__init__.py` — FOUND
- `reasoning/app/pipeline/graph.py` — FOUND
- `reasoning/app/pipeline/prefetch.py` — FOUND
- `reasoning/app/nodes/state.py` — MODIFIED (ReportOutput + language + report_output)
- `reasoning/tests/pipeline/test_graph.py` — FOUND (19 tests)
- Commits: `98b95b5` (RED), `89a358e` (GREEN)
