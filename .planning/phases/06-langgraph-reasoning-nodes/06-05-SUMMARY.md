---
phase: 06-langgraph-reasoning-nodes
plan: 05
subsystem: reasoning
tags: [langgraph, pydantic, grounding, numeric-attribution, quality-gate, phase6]

# Dependency graph
requires:
  - phase: 06-01
    provides: ReportState TypedDict, GroundingError exception, GroundingResult model, all Pydantic node output types
  - phase: 06-02
    provides: valuation_node and ValuationOutput (float fields pe_ratio, pb_ratio, real_yield)
  - phase: 06-03
    provides: macro_regime_node and MacroRegimeOutput (float field top_confidence, nested RegimeProbability.confidence)
provides:
  - grounding_check_node with recursive float-field attribution verification
  - _collect_float_fields helper walking Pydantic models recursively
  - _verify_output helper checking sources dict + source_analogue_id on nested models
  - Finalized reasoning.app.nodes public API exporting all 6 node functions
  - 9 TDD unit tests covering all grounding check behaviors
affects: [07-graph-wiring, 08-fastapi-service]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Grounding check via type(model).model_fields iteration — avoids Pydantic v2.11 instance deprecation"
    - "Nested BaseModel list items grounded via source_analogue_id (not parent sources dict)"
    - "GroundingError raises with all unattributed claims joined — never just first"
    - "None-valued float fields skipped — only non-None floats require attribution"

key-files:
  created:
    - reasoning/app/nodes/grounding_check.py
    - reasoning/tests/nodes/test_grounding_check.py
  modified:
    - reasoning/app/nodes/__init__.py

key-decisions:
  - "type(model).model_fields used instead of model.model_fields — avoids Pydantic v2.11 DeprecationWarning (instance access deprecated, removed in v3)"
  - "List[BaseModel] items (e.g., RegimeProbability) grounded via their own source_analogue_id — empty string treated as unattributed; non-list BaseModel fields recurse into _collect_float_fields normally"
  - "grounding_check_node checks only macro_regime_output, valuation_output, structure_output — entry_quality_output and conflict_output intentionally excluded (no raw numeric claims)"

patterns-established:
  - "Phase 6 node pattern finalized: standalone (state: ReportState) -> dict[str, Any] functions, one state key returned"
  - "Quality gate pattern: raise exception (not return warning) on attribution failure — GroundingError is a hard stop"

requirements-completed: [REAS-05]

# Metrics
duration: 5min
completed: 2026-03-16
---

# Phase 6 Plan 05: Grounding Check Node Summary

**grounding_check_node raises GroundingError with all unattributed float fields listed; RegimeProbability.confidence grounded via source_analogue_id; all 6 nodes exported from public API; 50 Phase 6 unit tests pass**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-15T19:27:03Z
- **Completed:** 2026-03-15T19:32:00Z
- **Tasks:** 2 (Task 1 TDD, Task 2 API finalization)
- **Files modified:** 3

## Accomplishments

- grounding_check_node recursively walks Pydantic model fields to find all non-None float values and verifies each has a sources dict entry or (for list[BaseModel] items) a non-empty source_analogue_id
- GroundingError raised with comprehensive error listing — all unattributed claims reported in one error, not just first
- Partial and empty state handled cleanly — None outputs are skipped; empty state passes with checked_outputs=[]
- All 6 Phase 6 node functions exported from reasoning.app.nodes public API
- Full test suite: 81 tests pass, 23 skipped (integration tests requiring live services)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement grounding_check_node with numeric claim verification** - `b442edc` (feat)
2. **Task 2: Finalize nodes __init__.py public API and run full test suite** - `b6d7e0c` (feat)

_Note: Task 1 was TDD — RED (import error confirmed), GREEN (9 tests pass), REFACTOR (Pydantic deprecation fix, tests still pass)_

## Files Created/Modified

- `reasoning/app/nodes/grounding_check.py` - grounding_check_node with _collect_float_fields and _verify_output helpers
- `reasoning/tests/nodes/test_grounding_check.py` - 9 TDD unit tests covering all 8 specified behaviors plus nested source pass/fail
- `reasoning/app/nodes/__init__.py` - Finalized public API exporting all 6 node functions

## Decisions Made

- `type(model).model_fields` used instead of `model.model_fields` — Pydantic v2.11 deprecated instance access, will be removed in v3.0; accessing via class avoids the warning and future breakage
- List[BaseModel] items (RegimeProbability in regime_probabilities) grounded via their own source_analogue_id field — empty string = unattributed; this matches how macro_regime_node populates these nested objects
- grounding_check_node checks only macro_regime_output, valuation_output, structure_output — entry_quality_output and conflict_output are excluded because they contain only derived labels and narrative (no raw numeric claims that require record-level attribution)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Pydantic v2.11 DeprecationWarning on model_fields instance access**
- **Found during:** Task 1 REFACTOR phase
- **Issue:** Accessing `model.model_fields` on an instance triggers `PydanticDeprecatedSince211` warning — "Accessing the 'model_fields' attribute on the instance is deprecated. Instead, you should access this attribute from the model class."
- **Fix:** Changed `model.model_fields` to `type(model).model_fields` and `output.model_fields` to `type(output).model_fields` in grounding_check.py
- **Files modified:** reasoning/app/nodes/grounding_check.py
- **Verification:** 9 tests pass with zero warnings after fix
- **Committed in:** b442edc (Task 1 commit, part of REFACTOR phase)

---

**Total deviations:** 1 auto-fixed (Rule 1 - deprecated API)
**Impact on plan:** Fix eliminates a future breaking change at Pydantic v3.0 upgrade. No scope creep.

## Issues Encountered

- System-level Python (python3.11) has a brownie pytest plugin with broken web3 import — must use project venv at `reasoning/.venv/bin/pytest` with `PYTHONPATH=/path/to/stratum`. This is consistent with how previous Phase 6 plans were executed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 Phase 6 LangGraph reasoning nodes are individually validated and exported
- Phase 7 (graph wiring) can now assemble nodes into a StateGraph using `from reasoning.app.nodes import *`
- grounding_check_node is ready to be wired as a conditional edge or final validation step in the StateGraph
- 50 unit tests provide regression coverage for all node behaviors

---
*Phase: 06-langgraph-reasoning-nodes*
*Completed: 2026-03-16*
