---
phase: 07-graph-assembly-and-end-to-end-report-generation
plan: "04"
subsystem: pipeline
tags: [markdown-renderer, bilingual, vietnamese, gemini, report-generation, tdd]
dependency_graph:
  requires: [07-02, 07-03]
  provides: [markdown_renderer.py, updated compose_report.py with bilingual generation]
  affects: [compose_report_node, ReportOutput.report_markdown]
tech_stack:
  added: []
  patterns:
    - f-string Markdown templates (no Jinja2)
    - Gemini-powered Vietnamese narrative re-generation per card (one call per card)
    - apply_terms() on serialized dict for Vietnamese structured label translation
    - synchronous _rewrite_narrative_vi() with graceful degradation fallback
key_files:
  created:
    - reasoning/app/pipeline/markdown_renderer.py
    - reasoning/tests/pipeline/test_markdown_renderer.py
  modified:
    - reasoning/app/pipeline/compose_report.py
    - reasoning/tests/pipeline/test_compose_report.py
decisions:
  - f-string templates used (not Jinja2) — RESEARCH.md confirmed Jinja2 unnecessary for static structure
  - Gemini narrative re-generation is synchronous (not async) — compose_report_node is sync LangGraph node
  - _rewrite_narrative_vi() has graceful degradation — returns English narrative if Gemini fails
  - apply_terms() applied to serialized dict (not Pydantic model) — term_dict.py design contract preserved
  - render_markdown() called with the ReportCard that has Vietnamese narratives already set
  - model_version updated to gemini-2.5-pro (used for narrative re-generation)
  - data_as_of computed from earliest timestamp in retrieval rows (fallback to datetime.now(UTC))
metrics:
  duration: "~12 min"
  completed: "2026-03-16"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
  tests_added: 29
  tests_total: 102
---

# Phase 7 Plan 04: Markdown Renderer and Bilingual Report Generation Summary

**One-liner:** Markdown renderer with conclusion-first card ordering and bilingual support — Vietnamese uses Gemini-rewritten narratives (gemini-2.5-pro) + term dictionary labels; English narratives pass through unchanged.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD) | Markdown renderer with bilingual support | 0f570f8 | markdown_renderer.py, test_markdown_renderer.py |
| 2 (TDD) | Integrate Markdown and bilingual into compose_report_node | f36ad52 | compose_report.py, test_compose_report.py |

## What Was Built

### Task 1: markdown_renderer.py

`render_markdown(report_card: ReportCard, language: str) -> str` produces a human-readable Markdown report with:

- Conclusion-first card ordering: DATA WARNING (if present) → Entry Quality → Signal Conflict (if present) → Macro Regime → Valuation → Structure
- Vietnamese mode: card headers loaded from `load_term_dict()["card_headers"]` (e.g., "Chất lượng điểm vào", "Chế độ vĩ mô")
- English mode: English headers ("Entry Quality", "Macro Regime", etc.)
- Optional metrics omitted entirely when value is None (no "P/E: None" lines)
- Metric formatting: 2 decimal places for ratios, 1 decimal for percentages
- No prohibited terms in templates: standalone 'buy', 'sell', 'entry confirmed' (English); 'mua vào', 'bán', 'xác nhận điểm vào' (Vietnamese)

### Task 2: compose_report.py update

compose_report_node now produces both `report_json` and `report_markdown` in `ReportOutput`:

**Vietnamese path (`language='vi'`):**
1. Call `_rewrite_narrative_vi()` (Gemini gemini-2.5-pro) for each card — entry_quality, macro_regime, valuation, structure, conflict (if present)
2. Rebuild ReportCard with Vietnamese narratives
3. Serialize to dict with `model_dump_json(exclude_none=True)`
4. Apply `apply_terms()` to translate structured labels (tier, label, pattern_name)
5. Call `render_markdown(report_card_with_vi_narratives, 'vi')` for Markdown

**English path (`language='en'`):**
1. Serialize ReportCard directly — English narratives pass through unchanged
2. No Gemini call, no `apply_terms()`
3. Call `render_markdown(report_card, 'en')`

**Additional improvements:**
- `_compute_data_as_of()`: finds earliest `data_as_of` timestamp across all retrieval row lists; falls back to `datetime.now(UTC)`
- `model_version` updated to `gemini-2.5-pro`

## Test Results

```
102 passed in 63.37s
```

- 20 tests for `test_markdown_renderer.py` (all new)
- 38 tests for `test_compose_report.py` (9 new, 29 existing)
- 25 tests for `test_term_dict.py` (all existing, no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] `_rewrite_narrative_vi` implemented as synchronous function**

- **Found during:** Task 2 implementation
- **Issue:** Plan suggested an `async def` pattern matching Phase 6 nodes, but `compose_report_node` is a synchronous LangGraph node (all Phase 6 nodes use sync `model.invoke()`). Making it async would require restructuring the entire graph.
- **Fix:** Implemented as synchronous function using `model.invoke()` (same pattern as Phase 6 nodes). The function signature matches the test mock pattern exactly.
- **Files modified:** reasoning/app/pipeline/compose_report.py

**2. [Rule 2 - Missing functionality] `_compute_data_as_of` implemented (plan noted it)**

- **Found during:** Task 2 implementation
- **Issue:** Plan specified data_as_of should be computed from retrieval rows, not always use `datetime.now(UTC)` placeholder.
- **Fix:** Implemented `_compute_data_as_of()` that iterates retrieval row lists from state and returns the minimum UTC-aware datetime, falling back to `datetime.now(UTC)`.
- **Files modified:** reasoning/app/pipeline/compose_report.py

## Self-Check: PASSED

All created files verified:
- FOUND: reasoning/app/pipeline/markdown_renderer.py
- FOUND: reasoning/app/pipeline/compose_report.py
- FOUND: reasoning/tests/pipeline/test_markdown_renderer.py
- FOUND: reasoning/tests/pipeline/test_compose_report.py

All commits verified:
- FOUND: ea491a1 test(07-04): add failing tests for markdown renderer (TDD RED)
- FOUND: 0f570f8 feat(07-04): implement render_markdown() with bilingual support
- FOUND: 2bab831 test(07-04): add failing tests for bilingual compose_report_node (TDD RED)
- FOUND: f36ad52 feat(07-04): integrate Markdown rendering and bilingual support into compose_report_node
