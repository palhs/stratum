---
phase: 07-graph-assembly-and-end-to-end-report-generation
plan: "02"
subsystem: pipeline
tags: [compose-report, report-schema, pydantic, data-warnings, json-report, tdd]
dependency_graph:
  requires:
    - "07-01 (build_graph placeholder compose_report_node, ReportOutput model)"
    - "06-04 (EntryQualityOutput, ConflictOutput)"
    - "06-01 (StructureOutput, MacroRegimeOutput)"
    - "06-02 (ValuationOutput)"
  provides:
    - "compose_report_node — 7th and final graph node producing structured ReportOutput"
    - "report_schema.py — Pydantic card models (EntryQualityCard, MacroRegimeCard, ValuationCard, StructureCard, ConflictCard, ReportCard)"
    - "_collect_data_warnings() — aggregates warnings from retrieval, entry_quality, WGC gold gap, node warnings"
    - "graph.py updated to use real compose_report_node (placeholder removed)"
  affects:
    - "07-03 (report storage — persists ReportOutput.report_json to JSONB column)"
    - "07-05 (generate_report end-to-end orchestrator — calls run_graph() which now produces real ReportOutput)"
tech_stack:
  added:
    - "reasoning/app/pipeline/compose_report.py"
    - "reasoning/app/pipeline/report_schema.py"
    - "reasoning/tests/pipeline/conftest.py"
    - "reasoning/tests/pipeline/test_compose_report.py"
  patterns:
    - "TDD: RED (15 failing compose_report tests) → GREEN (all 29 pass)"
    - "Flat card serialization: model_dump_json(exclude_none=True) — no nested Pydantic instances in JSONB"
    - "Conclusion-first ordering: entry_quality → conflict (optional) → macro_regime → valuation → structure"
    - "WGC gold warning always present for gold assets (known 501 gap)"
    - "Deduplication with insertion-order preservation in _collect_data_warnings"
key_files:
  created:
    - reasoning/app/pipeline/report_schema.py
    - reasoning/app/pipeline/compose_report.py
    - reasoning/tests/pipeline/conftest.py
    - reasoning/tests/pipeline/test_compose_report.py
  modified:
    - reasoning/app/pipeline/graph.py
decisions:
  - "report_json uses json.loads(card.model_dump_json(exclude_none=True)) — flat dict suitable for JSONB storage, no nested Pydantic instances"
  - "WGC gold data gap always flagged for gold assets with fixed warning string — known HTTP 501 on central bank buying endpoint"
  - "conflict card excluded via exclude_none=True serialization (not explicit if-branch) — ReportCard.conflict=None omits key"
  - "report_markdown='' placeholder — real Markdown rendering deferred to Plan 03"
  - "data_as_of=datetime.now(timezone.utc) placeholder — refined in Plan 03 using oldest source timestamp"
  - "_collect_data_warnings uses set for O(1) deduplication while preserving insertion order"
metrics:
  duration: "~6 min"
  completed_date: "2026-03-16"
  tasks_completed: 1
  files_created: 4
  files_modified: 1
  tests_written: 29
  tests_passing: 48
---

# Phase 7 Plan 02: Compose Report Node and JSON Report Schema Summary

**One-liner:** Flat Pydantic card schema (EntryQualityCard through ConflictCard) with compose_report_node that serializes all upstream outputs into conclusion-first JSONB-ready report JSON with deduplicated data warnings.

## What Was Built

### reasoning/app/pipeline/report_schema.py (created)

Flat Pydantic card models — no nested sub-objects:

- `EntryQualityCard`: tier, macro_assessment, valuation_assessment, structure_assessment, conflict_pattern (Optional), structure_veto_applied, narrative
- `MacroRegimeCard`: label, top_confidence, is_mixed_signal, regime_probabilities (list[dict] — dumped from RegimeProbability), narrative
- `ValuationCard`: label, pe_ratio (Optional), pb_ratio (Optional), real_yield (Optional), etf_flow_context (Optional), narrative
- `StructureCard`: label, close (Optional), drawdown_from_ath (Optional), drawdown_from_52w_high (Optional), close_pct_rank (Optional), narrative
- `ConflictCard`: pattern_name, severity, tier_impact, narrative
- `ReportCard`: entry_quality, conflict (Optional), macro_regime, valuation, structure, data_warnings, language — conclusion-first field ordering

### reasoning/app/pipeline/compose_report.py (created)

- `compose_report_node(state)` — 7th and final LangGraph node
  - Reads all upstream outputs from state
  - Builds each card via dedicated `_build_*_card()` helper
  - Skips ConflictCard when `state.conflict_output is None`
  - Serializes with `model_dump_json(exclude_none=True)` → flat JSONB-ready dict
  - Returns `{"report_output": ReportOutput(...)}`
- `_collect_data_warnings(state)` — aggregates from 4 sources with deduplication:
  1. `retrieval_warnings` from prefetch layer
  2. `entry_quality_output.stale_data_caveat` when present
  3. WGC gold data gap warning — always present for gold assets
  4. `.warnings` lists from macro_regime, valuation, structure, conflict outputs

### reasoning/app/pipeline/graph.py (modified)

- Removed placeholder `compose_report_node` definition
- Added `from reasoning.app.pipeline.compose_report import compose_report_node`
- No changes to build_graph() topology or run_graph() — only the import changed

### reasoning/tests/pipeline/conftest.py (created)

Four pytest fixtures with realistic mock state:
- `mock_report_state_with_conflict` — equity, all outputs populated, ConflictOutput present
- `mock_report_state_no_conflict` — equity, conflict_output=None
- `mock_report_state_gold` — gold asset, triggers WGC warning
- `mock_report_state_with_retrieval_warnings` — with retrieval_warnings + stale_data_caveat

### reasoning/tests/pipeline/test_compose_report.py (created)

29 TDD tests covering:
- Schema field presence and validation for all 6 card models
- compose_report_node with conflict — conflict card present in report_json
- compose_report_node without conflict — conflict key excluded
- 4 required sections always present (entry_quality, macro_regime, valuation, structure)
- report_json is flat dict (not nested Pydantic instances)
- language propagated from state to ReportOutput and report_json
- WGC data gap warning for gold assets
- Stale data caveat from entry_quality_output
- Retrieval warnings from state
- data_as_of is datetime instance
- report_markdown is empty string placeholder
- _collect_data_warnings unit tests (3 scenarios)
- graph.py source includes real import statement

## Deviations from Plan

None — plan executed exactly as written.

## TDD Execution

- **RED phase:** 15 tests failing (compose_report_node tests) → committed `682cf6c`
- **GREEN phase:** All 29 tests pass after implementation → committed `0fcaa59`
- No REFACTOR phase needed — implementation is clean

## Verification Results

```
PYTHONPATH=/Users/phananhle/Desktop/phananhle/stratum reasoning/.venv/bin/pytest reasoning/tests/pipeline/test_compose_report.py -v
29 passed in 0.09s

PYTHONPATH=/Users/phananhle/Desktop/phananhle/stratum reasoning/.venv/bin/pytest reasoning/tests/pipeline/ -v
48 passed in 0.10s
```

Import checks:
```
from reasoning.app.pipeline.compose_report import compose_report_node  # OK
from reasoning.app.pipeline.report_schema import ReportCard             # OK
```

## Self-Check: PASSED

- `reasoning/app/pipeline/report_schema.py` — FOUND
- `reasoning/app/pipeline/compose_report.py` — FOUND
- `reasoning/app/pipeline/graph.py` — MODIFIED (real import replaces placeholder)
- `reasoning/tests/pipeline/conftest.py` — FOUND
- `reasoning/tests/pipeline/test_compose_report.py` — FOUND (29 tests)
- Commits: `682cf6c` (RED), `0fcaa59` (GREEN)
