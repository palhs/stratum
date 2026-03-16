---
phase: 07-graph-assembly-and-end-to-end-report-generation
plan: "03"
subsystem: pipeline
tags: [vietnamese, i18n, term-dictionary, bilingual, json, python]

# Dependency graph
requires:
  - phase: 07-01
    provides: StateGraph assembly and ReportState schema that defines structured label fields needing translation
  - phase: 06-04
    provides: NAMED_CONFLICT_PATTERNS used as conflict_patterns keys in term dictionary
provides:
  - term_dict_vi.json with 160 Vietnamese financial terms across 10 categories
  - load_term_dict() loader with module-level caching
  - apply_terms(report_json) function — deterministic, idempotent, gracefully degrading label replacement
affects:
  - 07-04-PLAN: compose_report_node imports apply_terms to produce Vietnamese structured labels

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Module-level dict cache (_TERM_DICT) — loaded once on first call, reused across pipeline runs
    - apply_terms accepts plain dict (not Pydantic model) — keeps Plan 03 parallel-safe in Wave 2 with no dependency on Plan 02 report_schema.py
    - copy.deepcopy semantics — input dict never mutated, apply_terms is idempotent
    - dict.get(value, value) graceful degradation — unknown labels pass through unchanged

key-files:
  created:
    - reasoning/app/pipeline/term_dict_vi.json
    - reasoning/app/pipeline/term_dict.py
    - reasoning/tests/pipeline/test_term_dict.py
  modified: []

key-decisions:
  - "English financial abbreviations (P/E, ATH, ETF, P/B, MA, RSI, FOMC, SBV, GDP, CPI) not included as translation targets — kept inline in Vietnamese narrative text per CONTEXT.md"
  - "apply_terms replaces structured label fields only (tier, macro/valuation/structure labels, conflict pattern_name) — narrative text is NOT replaced; Gemini handles Vietnamese narrative in compose_report_node (Plan 04)"
  - "User reviewed and approved term dictionary as-is — no corrections required"

patterns-established:
  - "Term dictionary pattern: JSON controlled vocabulary + Python loader + apply function — for all structured label i18n"
  - "Idempotency via deepcopy + dict.get fallback — applying apply_terms twice produces identical output to applying once"

requirements-completed: [REPT-03]

# Metrics
duration: ~15min
completed: "2026-03-16"
---

# Phase 7 Plan 03: Vietnamese Term Dictionary Summary

**160-term Vietnamese financial term dictionary (term_dict_vi.json) with deterministic label application via apply_terms() — covering tier labels, macro/valuation/structure labels, card headers, conflict patterns, data warnings, metrics, macro concepts, and narrative connectors; user-reviewed and approved**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-16T04:30:00Z
- **Completed:** 2026-03-16T04:45:00Z
- **Tasks:** 2 (1 auto TDD + 1 checkpoint:user)
- **Files modified:** 3

## Accomplishments
- Created term_dict_vi.json with 160 Vietnamese financial terms across 10 categories (tiers, macro_labels, valuation_labels, structure_labels, card_headers, conflict_patterns, data_warning, metrics, macro_concepts, narrative_connectors)
- Implemented load_term_dict() with module-level caching and apply_terms() with deep copy semantics, idempotency, and graceful degradation for unknown terms
- All 25 TDD tests pass (73 total pipeline tests pass); user reviewed and approved the term dictionary with no corrections needed

## Task Commits

Each task was committed atomically:

1. **Task 1: Vietnamese term dictionary JSON and application logic** - `60f67cf` (feat)
   - RED: `f60431a` (test)
   - GREEN: `60f67cf` (feat)

**Plan metadata:** TBD (docs commit from this summary)

_Note: TDD task had RED + GREEN commits. No REFACTOR commit needed._

## Files Created/Modified
- `reasoning/app/pipeline/term_dict_vi.json` - 160-term Vietnamese financial term dictionary organized by 10 categories
- `reasoning/app/pipeline/term_dict.py` - load_term_dict() with module caching; apply_terms() with deepcopy, graceful degradation, idempotency
- `reasoning/tests/pipeline/test_term_dict.py` - 25 unit tests covering all label replacements, idempotency, unknown term pass-through, English abbreviation preservation, and total term count >= 150

## Decisions Made
- English financial abbreviations (P/E, ATH, ETF, P/B, MA, RSI, FOMC, SBV, GDP, CPI) are not included as translation targets — they are kept inline in Vietnamese narrative text per CONTEXT.md, consistent with the bilingual-from-structured-data approach
- apply_terms() replaces only structured label fields (tier, macro/valuation/structure labels, conflict pattern_name); narrative text is left to Gemini in compose_report_node (Plan 04), keeping Plan 03 parallel-safe in Wave 2
- User reviewed and approved the Vietnamese term dictionary as-is — no corrections required

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- term_dict.py is ready for import by compose_report_node in Plan 04
- apply_terms() API is stable: accepts plain dict (serialized report JSON), returns new dict with Vietnamese structured labels
- User has reviewed and approved all Vietnamese translations — dictionary is integration-ready

---
*Phase: 07-graph-assembly-and-end-to-end-report-generation*
*Completed: 2026-03-16*
