---
phase: 07-graph-assembly-and-end-to-end-report-generation
plan: "05"
subsystem: pipeline
tags: [postgresql, storage, sqlalchemy, generate_report, e2e, bilingual, integration-test, tdd, rept-05, reas-06]
dependency_graph:
  requires:
    - phase: 07-04
      provides: compose_report_node with bilingual Markdown rendering and Vietnamese Gemini narrative re-generation
  provides:
    - write_report() function — SQLAlchemy Core INSERT into PostgreSQL reports table; returns report_id
    - generate_report() — async public entry point for Phase 8 FastAPI (prefetch → vi graph → write → en graph → write)
    - End-to-end integration test suite (9 mocked tests + 1 integration placeholder)
  affects: [Phase 8 FastAPI — calls generate_report() as the single pipeline entry point]
tech-stack:
  added:
    - SQLAlchemy Core Table reflection + insert().returning() pattern for report storage
    - pytest asyncio auto mode for async E2E test coverage
  patterns:
    - write_report() uses Table("reports", MetaData(), autoload_with=db_engine) — schema-agnostic reflection
    - generate_report() deep-copies prefetch state between vi and en runs — prevents cross-language state mutation
    - E2E tests mock all infrastructure (Gemini, AsyncPostgresSaver, DB) via unittest.mock.patch
    - integration marker registered in pytest.ini — distinguishes Docker-required tests from always-runnable tests
key-files:
  created:
    - reasoning/app/pipeline/storage.py
    - reasoning/tests/pipeline/test_storage.py
    - reasoning/tests/pipeline/test_e2e.py
  modified:
    - reasoning/app/pipeline/__init__.py
    - reasoning/pytest.ini
key-decisions:
  - "write_report() uses SQLAlchemy Core Table reflection (not ORM) — consistent with postgres_retriever.py pattern; schema reflection via autoload_with=db_engine"
  - "generate_report() deep-copies prefetch state between vi and en invocations — prevents vi run from contaminating en state via shared mutable objects"
  - "pipeline_duration_ms measured as int(monotonic elapsed * 1000) — millisecond resolution, monotonic clock immune to wall-clock drift"
  - "E2E tests are fully mocked (no Docker required for non-integration mark) — fast CI execution without infrastructure dependency"
  - "pytest.ini 'integration' marker registered — PytestUnknownMarkWarning suppressed; Docker-dependent tests cleanly separable with -m 'not integration'"
  - "venv created at reasoning/.venv — project lacked virtual environment; pip install -r requirements.txt succeeded in isolated venv"
requirements-completed: [REPT-05, REAS-06, REPT-01, REPT-02, REPT-03, REPT-04]

duration: ~15 min
completed: 2026-03-16
---

# Phase 7 Plan 05: PostgreSQL Storage and End-to-End Integration Summary

**PostgreSQL report storage (write_report via SQLAlchemy Core) + generate_report() async entry point that orchestrates prefetch → run_graph(vi) → write → run_graph(en) → write; validated by 9 E2E mocked tests covering equity/gold paths, bilingual independence, prohibited term scanning, and schema validation.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-16T04:56:50Z
- **Completed:** 2026-03-16T05:11:50Z
- **Tasks:** 2 (Task 1 TDD: storage.py + __init__.py; Task 2: E2E tests)
- **Files created:** 3 new, 2 modified

## Accomplishments

- write_report() performs a SQLAlchemy Core INSERT into reports table with asset_id, language, report_json (JSONB dict), report_markdown, data_as_of, model_version, pipeline_duration_ms, and generated_at; returns report_id via RETURNING clause
- generate_report() is the single async public entry point for Phase 8: calls prefetch() once, invokes run_graph() twice (vi then en) with copy.deepcopy() isolation between runs, calls write_report() twice, returns (vi_id, en_id) tuple
- E2E test suite validates all 6 Phase 7 requirements with full infrastructure mocking — 130 pipeline tests pass, 1 integration test deselected in non-integration runs

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for storage + generate_report** - `450d04c` (test)
2. **Task 1 GREEN: implement write_report() and generate_report()** - `4244eff` (feat)
3. **Task 2: End-to-end integration test suite** - `292a6d2` (feat)

## Files Created/Modified

- `reasoning/app/pipeline/storage.py` — write_report() function with SQLAlchemy Core Table reflection + insert().returning(report_id); explicit conn.commit()
- `reasoning/app/pipeline/__init__.py` — generate_report() async orchestrator added; __all__ updated; copy/uuid/time imported at module level
- `reasoning/tests/pipeline/test_storage.py` — 19 unit tests for write_report() (INSERT values, return type, commit) and generate_report() (prefetch once, run_graph twice, write_report twice, deepcopy, tuple return)
- `reasoning/tests/pipeline/test_e2e.py` — 9 non-integration + 1 integration E2E tests covering equity/gold pipeline, schema validation, prohibited terms, bilingual independence, state isolation
- `reasoning/pytest.ini` — 'integration' marker registered to suppress PytestUnknownMarkWarning

## Decisions Made

- write_report() uses Table reflection (not ORM) — matches established pattern from postgres_retriever.py; stateless, no model imports needed
- copy.deepcopy between vi and en — prevents the vi LangGraph execution from mutating the state dict before the en run starts
- pipeline_duration_ms uses time.monotonic() — immune to clock adjustments; measured per-language run (two separate timings)
- venv created at reasoning/.venv — the project had no virtual environment; the system python3.11 had brownie registered as a pytest11 plugin (missing web3 dependency caused pytest startup failures); isolated venv resolved this cleanly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created venv to resolve pytest startup failure**
- **Found during:** Task 1 (RED phase — running tests for the first time)
- **Issue:** System python3.11 had brownie registered as a pytest11 entry point, but brownie's web3 dependency was missing — pytest crashed on startup with ModuleNotFoundError: No module named 'web3'
- **Fix:** Created isolated venv at reasoning/.venv; installed requirements.txt; all test runs use .venv/bin/python
- **Files modified:** reasoning/.venv/ (new directory, not tracked by git)
- **Verification:** 130 pipeline tests pass cleanly
- **Committed in:** Not committed (venv added to .gitignore or inherently excluded)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** Necessary environment fix. No scope creep. All plan tasks executed as specified.

## Issues Encountered

- System python3.11 had brownie pytest plugin with broken web3 dependency — caused pytest startup crash. Resolved by creating reasoning/.venv and running all tests via venv interpreter.
- Prior test runs (07-01 through 07-04) were run in the same environment — likely the user had previously configured a working interpreter or the issue appeared due to environment changes. The venv approach is the robust solution going forward.

## Next Phase Readiness

- generate_report() is the complete Phase 7 public API — Phase 8 FastAPI calls this function with ticker, asset_type, db_engine, neo4j_driver, qdrant_client, db_uri
- All 6 Phase 7 requirements satisfied: REAS-06 (LangGraph pipeline), REPT-01 (report_json structure), REPT-02 (Markdown output), REPT-03 (Vietnamese bilingual), REPT-04 (conclusion-first ordering), REPT-05 (PostgreSQL storage)
- 130 pipeline tests pass total — comprehensive regression coverage for Phase 8

---
*Phase: 07-graph-assembly-and-end-to-end-report-generation*
*Completed: 2026-03-16*
