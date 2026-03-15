---
phase: 06-langgraph-reasoning-nodes
plan: 03
subsystem: reasoning
tags: [langgraph, gemini, pydantic, macro-regime, tdd, probability-distribution, mixed-signal]

# Dependency graph
requires:
  - phase: 06-langgraph-reasoning-nodes/06-01
    provides: "ReportState TypedDict, MacroRegimeOutput Pydantic model, RegimeProbability model, prompts.py utilities, conftest.py fixtures"
  - phase: 05-retrieval-layer-validation
    provides: "FredIndicatorRow, RegimeAnalogue, DocumentChunk types"
provides:
  - "macro_regime_node — macro regime classification with probability distribution"
  - "Deterministic mixed-signal logic: is_mixed_signal = (top_confidence < 0.70), strict less-than"
  - "top_two_analogues populated only when is_mixed_signal is True"
  - "macro_label validated against MACRO_LABELS (Supportive/Mixed/Headwind)"
  - "sources['top_confidence'] always populated with FRED series IDs"
  - "Warnings propagated from fred_rows and regime_analogues input fields"
  - "8 passing unit tests with mocked Gemini covering all specified behaviors"
affects:
  - 06-langgraph-reasoning-nodes/06-04 (entry_quality_node — consumes macro_regime_output)
  - 06-langgraph-reasoning-nodes/06-02 (valuation_node gold path — macro overlay uses macro_regime_output)
  - 07-report-composer (reads macro_regime_output from final ReportState)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deterministic-then-LLM: mixed-signal threshold computed in Python post-LLM, not LLM-evaluated"
    - "Strict less-than semantics: is_mixed_signal = (top_confidence < 0.70); exactly 0.70 is NOT mixed signal"
    - "Sort-then-derive: regime_probabilities sorted by confidence desc; top_regime_id/top_confidence derived from sorted list"
    - "Conditional field population: top_two_analogues and mixed_signal_label set only when is_mixed_signal=True, cleared when False"
    - "Source citation pattern: sources['top_confidence'] always populated; fallback to _build_fred_source_string if LLM omits"
    - "Warning propagation: warnings from all input list items (.warnings attribute) accumulated before LLM call"

key-files:
  created:
    - reasoning/app/nodes/macro_regime.py
    - reasoning/tests/nodes/test_macro_regime.py
  modified: []

key-decisions:
  - "is_mixed_signal computed deterministically in Python (not LLM-dependent) — prevents LLM from misapplying threshold boundary"
  - "top_two_analogues derived from sorted regime_probabilities[0:2].source_analogue_id — uses the probability distribution itself for mixed-signal disambiguation, not a separate field"
  - "macro_label sanitized via _sanitize_macro_label() with case-insensitive fallback map — handles LLM casing variations while ensuring valid output"
  - "MIXED_SIGNAL_THRESHOLD imported from state.py (canonical source at 0.70) — not a local constant"
  - "Empty analogues: produces output with warning instead of raising — matches partial assessment pattern established in valuation_node"
  - "Gemini temperature=0.1 (not 0.2 as in valuation_node) — probability distributions require higher consistency than narrative-only nodes"

# Metrics
duration: ~6min
completed: 2026-03-16
---

# Phase 6 Plan 03: macro_regime_node Summary

**Macro regime classification node with probability distribution over regime types, deterministic mixed-signal detection at strict <0.70 threshold, and macro_label validation — 8 TDD unit tests pass**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-15T19:10:06Z
- **Completed:** 2026-03-15T19:16:35Z
- **Tasks:** 1 (TDD with RED/GREEN phases)
- **Files modified:** 2

## Accomplishments

- Implemented `macro_regime_node` in `reasoning/app/nodes/macro_regime.py`
- Node reads `fred_rows`, `regime_analogues`, `macro_docs` from `ReportState`
- Calls `gemini-2.0-flash-001` at temperature=0.1 with structured output (`MacroRegimeOutput`)
- Post-processes LLM output deterministically:
  - Sorts `regime_probabilities` by confidence descending
  - Derives `top_regime_id` and `top_confidence` from sorted list
  - Applies strict less-than: `is_mixed_signal = (top_confidence < 0.70)`
  - When mixed: sets `mixed_signal_label = "Mixed Signal Environment"`, populates `top_two_analogues` with top 2 `source_analogue_id` values from sorted probabilities
  - When not mixed: clears `mixed_signal_label = None`, `top_two_analogues = []`
- Validates `macro_label` against `MACRO_LABELS` with case-insensitive sanitizer
- Ensures `sources["top_confidence"]` always has a FRED series citation
- Propagates warnings from `fred_rows[].warnings` and `regime_analogues[].warnings`
- Empty analogues path: appends warning about absent analogue context, still produces output

## Task Commits

Each TDD phase committed atomically:

1. **Task 1 RED: Failing tests for macro_regime_node** — `00bd9e4` (test)
2. **Task 1 GREEN: macro_regime_node implementation** — `bc16b89` (feat)

## Files Created/Modified

- `reasoning/app/nodes/macro_regime.py` — `macro_regime_node` with Gemini call, deterministic post-processing, helper functions: `_build_fred_source_string`, `_sanitize_macro_label`, `_build_human_prompt`
- `reasoning/tests/nodes/test_macro_regime.py` — 8 tests covering all specified behaviors with mocked Gemini chains

## Decisions Made

- `is_mixed_signal` is computed deterministically in Python post-LLM response (not LLM-evaluated) — prevents LLM from misapplying the strict threshold semantics
- `top_two_analogues` derived from sorted `regime_probabilities[0:2].source_analogue_id` — uses the probability distribution itself, no separate disambiguation field needed
- `macro_label` sanitized via `_sanitize_macro_label()` — handles LLM casing variations (uppercase, lowercase, etc.) while guaranteeing a valid MACRO_LABELS value
- `MIXED_SIGNAL_THRESHOLD = 0.70` imported from `state.py` (canonical source) — not a local constant; single point of truth across all nodes
- Empty analogues: produces valid output with warning string rather than raising — consistent with partial assessment pattern established in valuation_node
- `temperature=0.1` for probability distribution consistency — lower than valuation_node's 0.2 because probability distributions require higher repeatability

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

- Test infrastructure discovery: system Python 3.11 (`/Library/Frameworks`) has a `brownie` pytest plugin installed that fails to load due to missing `web3` and `requests` modules. Tests were run using a fresh venv (`/tmp/stratum_venv`) with `python3.11` from Homebrew and `PYTHONPATH=/Users/phananhle/Desktop/phananhle/stratum`. This is consistent with how prior plans ran tests — the same broken brownie plugin exists and the same workaround applies.
- The `pytest.ini` at `reasoning/pytest.ini` configures `testpaths = tests`, so tests are run from inside `reasoning/` directory with `PYTHONPATH` pointing to the project root.

## Issues Encountered

None.

## Next Phase Readiness

- `macro_regime_node` follows the canonical pattern: deterministic label + Gemini narrative + sources + warnings
- `MacroRegimeOutput` is now a tested, populated node output; ready for `entry_quality_node` consumption in 06-04
- `is_mixed_signal`, `mixed_signal_label`, `top_two_analogues` fields will drive conflict detection in `entry_quality_node`
- `valuation_node` gold path already accepts `macro_regime_output` as overlay context — this node fulfills that contract

---
*Phase: 06-langgraph-reasoning-nodes*
*Completed: 2026-03-16*
