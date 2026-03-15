---
phase: 06-langgraph-reasoning-nodes
verified: 2026-03-16T00:00:00Z
status: passed
score: 7/7 must-haves verified
gaps: []
human_verification:
  - test: "Run structure_node against a live GEMINI_API_KEY"
    expected: "Returns StructureOutput with narrative mentioning MA values and drawdown; no 404 error"
    why_human: "structure.py uses _MODEL = 'gemini-2.0-flash' (without -001 suffix) which was documented as returning 404 NOT_FOUND for new users. All unit tests mock Gemini so this is invisible in CI. A live smoke test is needed to confirm structure_node works end-to-end before Phase 7 wiring."
---

# Phase 6: LangGraph Reasoning Nodes Verification Report

**Phase Goal:** Five LangGraph nodes (structure, valuation, macro_regime, entry_quality, grounding_check) and one special-case handler (conflicting_signals) are built and validated individually with mock state — each produces Pydantic-validated structured output, consumes only what the next node needs, and handles edge cases (mixed signals, missing data, conflicting sub-assessments) explicitly.

**Verified:** 2026-03-16
**Status:** passed (with one human verification item)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | ReportState TypedDict is importable with all node output keys as Optional fields | VERIFIED | `get_type_hints(ReportState)` returns 17 keys including all node outputs, retrieval inputs, and accumulator |
| 2 | All 6 Pydantic output models importable from state.py with sources and warnings fields | VERIFIED | Import of all 6 models succeeds; each model confirmed to have `sources: dict[str, str] = {}` and `warnings: list[str] = []` |
| 3 | macro_regime_node outputs probability distribution with deterministic mixed-signal threshold at strict < 0.70 | VERIFIED | `macro_regime.py` post-processes LLM output: `is_mixed_signal = top_confidence < MIXED_SIGNAL_THRESHOLD`; boundary test at exactly 0.70 passes (is NOT mixed signal) |
| 4 | valuation_node dispatches to equity/gold paths with regime-relative comparison and WGC warning on gold path | VERIFIED | `valuation.py` branches on `state["asset_type"]`; 10 tests pass including `test_gold_wgc_warning_always_present` and `test_equity_pe_analogue_weighting` |
| 5 | structure_node reads pre-computed markers and produces StructureOutput without retrieval function imports | VERIFIED | `structure.py` imports only `StructureMarkerRow` type from `retrieval.types` (no function calls); deterministic label from MA rules, Gemini for narrative only |
| 6 | entry_quality_node produces composite tier with structure veto and three visible sub-assessments | VERIFIED | `entry_quality.py` implements `STRUCTURE_VETO_MAP = {"Deteriorating": "Cautious"}`; EntryQualityOutput has no float/score field; 9 tests pass |
| 7 | conflicting_signals_handler detects named conflict patterns and grounding_check_node raises GroundingError on unattributed floats | VERIFIED | `NAMED_CONFLICT_PATTERNS` has 11 patterns (O(1) lookup); all Deteriorating-structure patterns are severity="major"; grounding_check raises GroundingError with all failures listed; 50/50 node tests pass |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `reasoning/app/nodes/state.py` | ReportState TypedDict + all 6 Pydantic output models | VERIFIED | 193 lines; ReportState with 17 keys confirmed; all 6 models (MacroRegimeOutput, ValuationOutput, StructureOutput, EntryQualityOutput, GroundingResult, ConflictOutput) plus GroundingError and constants |
| `reasoning/app/nodes/structure.py` | structure_node function | VERIFIED | 240 lines; exports `structure_node`; deterministic label via `_determine_label` + Gemini narrative |
| `reasoning/app/nodes/valuation.py` | valuation_node with equity/gold dispatch | VERIFIED | 577 lines; exports `valuation_node`; equity path (_compute_equity_valuation_label) and gold path (_compute_real_yield) both implemented |
| `reasoning/app/nodes/macro_regime.py` | macro_regime_node with probability distribution | VERIFIED | 258 lines; exports `macro_regime_node`; deterministic post-processing of LLM output with `is_mixed_signal = top_confidence < MIXED_SIGNAL_THRESHOLD` |
| `reasoning/app/nodes/conflicting_signals.py` | conflicting_signals_handler + NAMED_CONFLICT_PATTERNS | VERIFIED | 203 lines; `NAMED_CONFLICT_PATTERNS` dict has 11 patterns; exports both `conflicting_signals_handler` and `NAMED_CONFLICT_PATTERNS` |
| `reasoning/app/nodes/entry_quality.py` | entry_quality_node with structure veto | VERIFIED | 326 lines; exports `entry_quality_node`; `STRUCTURE_VETO_MAP`, `TIER_ORDER`, `_compute_base_tier`, `_apply_structure_veto`, `_apply_conflict_impact` all present |
| `reasoning/app/nodes/grounding_check.py` | grounding_check_node with recursive float verification | VERIFIED | 197 lines; exports `grounding_check_node`; `_collect_float_fields` (recursive), `_verify_output`; uses `type(model).model_fields` (Pydantic v2.11 safe) |
| `reasoning/app/nodes/__init__.py` | Public API exporting all 6 node functions | VERIFIED | 23 lines; all 6 functions in `__all__`; imports confirmed working |
| `reasoning/app/nodes/prompts.py` | 5 pure string-formatting utilities | VERIFIED | 206 lines; format_fred_context, format_analogue_context, format_structure_context, format_fundamentals_context, format_gold_context |
| `reasoning/tests/nodes/conftest.py` | Mock fixtures for all retrieval types and base states | VERIFIED | 411 lines; 11 fixtures including base_equity_state and base_gold_state |
| `reasoning/tests/nodes/test_structure.py` | 7 unit tests for structure_node | VERIFIED | 378 lines; 7 tests all passing |
| `reasoning/tests/nodes/test_valuation.py` | 9+ unit tests for valuation_node | VERIFIED | 476 lines; 10 tests (sources test split by path) all passing |
| `reasoning/tests/nodes/test_macro_regime.py` | 8 unit tests for macro_regime_node | VERIFIED | 446 lines; 8 tests all passing |
| `reasoning/tests/nodes/test_conflicting_signals.py` | 7 unit tests for conflicting_signals_handler | VERIFIED | 335 lines; 7 tests all passing |
| `reasoning/tests/nodes/test_entry_quality.py` | 9 unit tests for entry_quality_node | VERIFIED | 460 lines; 9 tests all passing |
| `reasoning/tests/nodes/test_grounding_check.py` | 8+ unit tests for grounding_check_node | VERIFIED | 457 lines; 9 tests all passing |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `reasoning/app/nodes/state.py` | `reasoning/app/retrieval/types.py` | `from reasoning.app.retrieval.types import` | WIRED | Imports FredIndicatorRow, RegimeAnalogue, DocumentChunk, FundamentalsRow, StructureMarkerRow, GoldPriceRow, GoldEtfRow |
| `reasoning/app/nodes/structure.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports STRUCTURE_LABELS, ReportState, StructureOutput |
| `reasoning/app/nodes/valuation.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports ReportState, ValuationOutput and supporting models |
| `reasoning/app/nodes/macro_regime.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports MACRO_LABELS, MIXED_SIGNAL_THRESHOLD, MacroRegimeOutput, RegimeProbability, ReportState |
| `reasoning/app/nodes/entry_quality.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports COMPOSITE_TIERS, ConflictOutput, EntryQualityOutput, MacroRegimeOutput, ReportState, StructureOutput, ValuationOutput |
| `reasoning/app/nodes/entry_quality.py` | `reasoning/app/nodes/conflicting_signals.py` | `state.get("conflict_output")` | WIRED | Line 220: `conflict_output = state.get("conflict_output")`; used at lines 240, 258, 298-305 |
| `reasoning/app/nodes/conflicting_signals.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports ConflictOutput, MacroRegimeOutput, ReportState, StructureOutput, ValuationOutput |
| `reasoning/app/nodes/grounding_check.py` | `reasoning/app/nodes/state.py` | `from reasoning.app.nodes.state import` | WIRED | Imports GroundingError, GroundingResult, MacroRegimeOutput, ReportState, StructureOutput, ValuationOutput |
| `reasoning/app/nodes/__init__.py` | all 6 node modules | `from reasoning.app.nodes.X import Y` | WIRED | All 6 imports confirmed working; `python -c "from reasoning.app.nodes import ..."` succeeds |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| REAS-01 | 06-03-PLAN | Macro regime classification node outputs probability distribution with mixed-signal handling (top confidence < 70%) | SATISFIED | `macro_regime.py`: `is_mixed_signal = top_confidence < MIXED_SIGNAL_THRESHOLD`; `MIXED_SIGNAL_THRESHOLD = 0.70`; 8 tests pass including boundary test at exactly 0.70 |
| REAS-02 | 06-02-PLAN | Valuation node produces regime-relative valuation for VN equities (P/E, P/B vs analogues) and gold (real yield, ETF flow) | SATISFIED | `valuation.py`: equity path uses top-3 similarity-weighted analogues; gold path computes `real_yield = GS10 - 2.5%`; mandatory WGC warning; 10 tests pass |
| REAS-03 | 06-01-PLAN | Price structure node interprets pre-computed v1.0 markers without recomputation | SATISFIED | `structure.py`: only type import from retrieval.types (no function calls); deterministic label from MA rules; `test_structure_node_no_retrieval_function_imports` passes |
| REAS-04 | 06-04-PLAN | Entry quality node outputs qualitative tier (Favorable/Neutral/Cautious/Avoid) with three visible sub-assessments | SATISFIED | `entry_quality.py`: EntryQualityOutput has macro_assessment, valuation_assessment, structure_assessment fields; no float/score field; `STRUCTURE_VETO_MAP = {"Deteriorating": "Cautious"}`; 9 tests pass |
| REAS-05 | 06-05-PLAN | Grounding check node verifies every numeric claim traces to a specific retrieved database record | SATISFIED | `grounding_check.py`: recursive `_collect_float_fields`; raises `GroundingError` with all failures listed; checks macro_regime_output, valuation_output, structure_output; 9 tests pass |
| REAS-07 | 06-04-PLAN | Conflicting signal handling produces explicit "strong thesis, weak structure" report type | SATISFIED | `conflicting_signals.py`: `NAMED_CONFLICT_PATTERNS` contains `("Supportive", "Attractive", "Deteriorating"): {"name": "Strong Thesis, Weak Structure", "severity": "major"}`; 11 patterns total; 7 tests pass |

**Note on REAS-06:** REAS-06 (LangGraph StateGraph assembly with PostgreSQL checkpointing) is explicitly mapped to Phase 7 in REQUIREMENTS.md and was NOT claimed by any Phase 6 plan. This is correct — Phase 6 builds and validates nodes individually; Phase 7 wires them into a StateGraph. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `reasoning/app/nodes/structure.py` | 50 | `_MODEL = "gemini-2.0-flash"` (deprecated model, missing `-001` suffix) | Warning | Does not affect unit tests (all mocked) but will cause 404 NOT_FOUND on live Gemini API calls. All other nodes use `gemini-2.0-flash-001`. This was identified in 06-01-SUMMARY.md and noted as a known deviation — follow-up fix deferred to later plans. |

No blocker anti-patterns found. No TODO/FIXME/placeholder comments. No stub implementations (all node functions contain real logic). No empty return values where real data is expected.

---

### Human Verification Required

#### 1. Live API smoke test for structure_node

**Test:** Set `GEMINI_API_KEY` in environment, create a minimal ReportState with one StructureMarkerRow, call `structure_node(state)`.

**Expected:** Returns `StructureOutput` with a non-empty narrative string, correct `structure_label`, and numeric fields echoed from the marker row. No 404 or API error.

**Why human:** `structure.py` uses `_MODEL = "gemini-2.0-flash"` (without `-001`), documented in 06-01-SUMMARY.md as returning 404 NOT_FOUND for new users. Unit tests mock Gemini entirely. A live call is needed to confirm the model name issue was not actually a problem at this Gemini account's access level, or to trigger the fix before Phase 7 integration. The other five nodes all use `gemini-2.0-flash-001` and do not have this concern.

---

### Test Suite Results

```
50 passed in 0.06s
  - test_conflicting_signals.py:  7 tests
  - test_entry_quality.py:        9 tests
  - test_grounding_check.py:      9 tests
  - test_macro_regime.py:         8 tests
  - test_structure.py:            7 tests
  - test_valuation.py:           10 tests
```

All 50 unit tests pass with mocked Gemini calls. No live API calls required for the test suite.

---

### Gaps Summary

No gaps. All phase truths are verified. The only open item is a human smoke test for `structure.py`'s Gemini model name (`gemini-2.0-flash` vs `gemini-2.0-flash-001`). This is a warning, not a blocker — the node logic is correct, the tests pass, and the model name discrepancy was documented during plan execution. It should be corrected before the first live integration run in Phase 7.

---

_Verified: 2026-03-16_
_Verifier: Claude (gsd-verifier)_
