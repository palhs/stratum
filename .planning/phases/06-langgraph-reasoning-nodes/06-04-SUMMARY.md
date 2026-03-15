---
phase: 06-langgraph-reasoning-nodes
plan: 04
subsystem: reasoning
tags: [langgraph, gemini, pydantic, conflict-detection, entry-quality, structure-veto, tdd]

# Dependency graph
requires:
  - phase: 06-langgraph-reasoning-nodes/06-01
    provides: "ReportState TypedDict, EntryQualityOutput, ConflictOutput Pydantic models, conftest.py fixtures"
  - phase: 06-langgraph-reasoning-nodes/06-02
    provides: "valuation_node, ValuationOutput with valuation_label (Attractive/Fair/Stretched)"
  - phase: 06-langgraph-reasoning-nodes/06-03
    provides: "macro_regime_node, MacroRegimeOutput with macro_label (Supportive/Mixed/Headwind)"
provides:
  - "conflicting_signals_handler — deterministic named pattern lookup with Gemini narrative"
  - "NAMED_CONFLICT_PATTERNS — 11 patterns covering major/minor severities"
  - "entry_quality_node — composite tier with structure veto and conflict impact"
  - "Structure veto: Deteriorating caps tier at Cautious (STRUCTURE_VETO_MAP)"
  - "Major conflict forces tier downgrade 1 level; minor conflict has no automatic downgrade"
  - "Stale data caveat added without forcing Avoid tier"
  - "16 passing unit tests with mocked Gemini calls"
affects:
  - 06-langgraph-reasoning-nodes/06-05 (grounding_node — reads entry_quality_output from state)
  - 07-report-composer (reads entry_quality_output and conflict_output from final ReportState)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deterministic-before-LLM: conflict pattern and severity from rules table, not LLM inference"
    - "LLM-for-narrative-only: Gemini writes explanation; all decision fields overridden post-LLM"
    - "Structure veto pattern: STRUCTURE_VETO_MAP + TIER_ORDER index comparison for tier cap"
    - "Score-based tier derivation: label → int score, sum → threshold bucket → tier"
    - "Stale detection: scan warning strings for STALE keyword across all input node warnings"
    - "No-LLM fast path: non-conflicting combinations short-circuit without calling Gemini"

key-files:
  created:
    - reasoning/app/nodes/conflicting_signals.py
    - reasoning/app/nodes/entry_quality.py
    - reasoning/tests/nodes/test_conflicting_signals.py
    - reasoning/tests/nodes/test_entry_quality.py
  modified: []

key-decisions:
  - "NAMED_CONFLICT_PATTERNS is a static dict — conflict detection is O(1) lookup, not LLM inference"
  - "Pattern_name and severity overridden post-LLM — Gemini cannot hallucinate severity classification"
  - "Composite_tier and structure_veto_applied are deterministic — LLM generates narrative only"
  - "Structure veto records veto_applied=True even when tier is already at or below the cap"
  - "Stale detection scans all three node output warning lists for STALE keyword"
  - "Minor conflict: no downgrade; major conflict: +1 tier index (Favorable→Neutral, etc.)"
  - "No-conflict fast path: Gemini not called when pattern not in NAMED_CONFLICT_PATTERNS"

# Metrics
duration: ~5min
completed: 2026-03-16
---

# Phase 6 Plan 04: conflicting_signals_handler and entry_quality_node Summary

**Conflict detection with named patterns (REAS-07) and composite entry quality assessment with structure veto (REAS-04) — 16 TDD unit tests pass with deterministic tier logic and mocked Gemini**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-15T19:19:42Z
- **Completed:** 2026-03-15T19:24:16Z
- **Tasks:** 2 (TDD with RED/GREEN phases each)
- **Files created:** 4

## Accomplishments

### Task 1: conflicting_signals_handler

- Implemented `conflicting_signals_handler` in `reasoning/app/nodes/conflicting_signals.py`
- `NAMED_CONFLICT_PATTERNS` dict with 11 patterns mapping `(macro_label, valuation_label, structure_label)` tuples to `{name, severity}` info
- Deterministic conflict detection: pattern lookup is O(1), no LLM involved in detection
- Gemini called only when a conflict is detected — generates structure-biased narrative
- `pattern_name` and `severity` fields overridden post-LLM (rules win, not hallucination)
- All patterns where `structure_label="Deteriorating"` have `severity="major"` (enforced by dict construction)
- No-conflict fast path: returns `{"conflict_output": None}` without calling Gemini

### Task 2: entry_quality_node

- Implemented `entry_quality_node` in `reasoning/app/nodes/entry_quality.py`
- Deterministic tier pipeline:
  1. `_compute_base_tier()`: label scores → sum → threshold bucket → tier
  2. `_apply_structure_veto()`: Deteriorating caps tier at Cautious (STRUCTURE_VETO_MAP)
  3. `_apply_conflict_impact()`: major → +1 tier index downgrade; minor → no change
- `composite_tier` and `structure_veto_applied` always overridden deterministically (LLM generates narrative only)
- Conflict fields (`conflict_pattern`, `conflict_narrative`) populated from state's `conflict_output` when present
- Stale data detected by scanning all three node output warning lists for "STALE" keyword; caveat added without changing tier
- No numeric score field anywhere in `EntryQualityOutput`

## Task Commits

Each TDD phase committed atomically:

1. **Task 1 RED: Failing tests for conflicting_signals_handler** — `710aa46` (test)
2. **Task 1 GREEN: conflicting_signals_handler implementation** — `f66ac5b` (feat)
3. **Task 2 RED: Failing tests for entry_quality_node** — `b85eaab` (test)
4. **Task 2 GREEN: entry_quality_node implementation** — `63db7d7` (feat)

## Files Created

- `reasoning/app/nodes/conflicting_signals.py` — `conflicting_signals_handler`, `NAMED_CONFLICT_PATTERNS` (11 patterns)
- `reasoning/app/nodes/entry_quality.py` — `entry_quality_node` with `_compute_base_tier`, `_apply_structure_veto`, `_apply_conflict_impact`, `_detect_stale_warnings`
- `reasoning/tests/nodes/test_conflicting_signals.py` — 7 tests covering all specified behaviors
- `reasoning/tests/nodes/test_entry_quality.py` — 9 tests covering all specified behaviors

## Decisions Made

- `NAMED_CONFLICT_PATTERNS` is a static dict — conflict detection is O(1) lookup, not LLM inference. Deterministic classification prevents LLM from misclassifying severity.
- `pattern_name` and `severity` overridden post-LLM in `conflicting_signals_handler` — Gemini writes narrative only; the rules table controls the conflict metadata.
- `composite_tier` and `structure_veto_applied` are always overridden deterministically in `entry_quality_node` — LLM is explicitly told the tier but cannot change it.
- `structure_veto_applied=True` recorded even when the tier is already at or below the veto cap — signals to downstream consumers that the veto logic engaged.
- Stale detection scans `warnings` lists of all three sub-assessment outputs; no separate stale state field needed.
- Minor conflict: no automatic downgrade; Favorable can remain if signals are otherwise strong.
- Major conflict: `+1 TIER_ORDER index` — exactly one level worse (Favorable→Neutral, Neutral→Cautious, Cautious→Avoid).
- No-conflict fast path: `conflicting_signals_handler` returns `None` without calling Gemini for combinations not in `NAMED_CONFLICT_PATTERNS`.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Test infrastructure (Homebrew Python 3.11 venv at `/tmp/stratum_venv`) consistent with prior plans.

## Next Phase Readiness

- `conflicting_signals_handler` fully tested — ready for LangGraph graph wiring in Phase 6 finale
- `entry_quality_output` is the final reasoning node output — ready for `grounding_node` (06-05) and `compose_report` (07-xx)
- All four key Phase 6 reasoning nodes now exist: `structure_node`, `valuation_node`, `macro_regime_node`, `conflicting_signals_handler`, `entry_quality_node`

---
*Phase: 06-langgraph-reasoning-nodes*
*Completed: 2026-03-16*
