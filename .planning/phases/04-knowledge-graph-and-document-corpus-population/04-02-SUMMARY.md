---
phase: 04-knowledge-graph-and-document-corpus-population
plan: "02"
subsystem: knowledge-graph
tags: [neo4j, cosine-similarity, sklearn, scipy, numpy, gemini, HAS_ANALOGUE, regime-analogues]

requires:
  - phase: 04-01
    provides: neo4j/seed/regime_data.json with 17 regime nodes (FRED + VN macro dimensions)

provides:
  - scripts/seed-neo4j-analogues.py — idempotent Python script that computes HAS_ANALOGUE relationships

affects: [phase-05-retrieval, phase-06-reasoning, macro-regime-node]

tech-stack:
  added:
    - scipy (cdist cosine distance)
    - scikit-learn MinMaxScaler (FRED vector normalization)
    - google-generativeai (Gemini 2.0 Flash narrative generation)
    - numpy (feature matrix construction)
  patterns:
    - MinMaxScaler normalization before cosine similarity (prevent FRED scale bias)
    - UNWIND+MERGE idempotent Neo4j relationship batch write
    - Gemini narrative caching to JSON (prevent redundant API spend on re-runs)
    - Exponential backoff retry for Gemini API (2s/4s/8s, max 3 retries)
    - Null-dim exclusion: regimes with any null FRED dimension skipped with warning (no zero-substitution)

key-files:
  created:
    - scripts/seed-neo4j-analogues.py
  modified: []

key-decisions:
  - "SIMILARITY_THRESHOLD=0.75 chosen as conservative starting point — sparse connectivity for edge regimes is acceptable per plan spec"
  - "Both-direction HAS_ANALOGUE creation: if A is analogue of B, also create B->A relationship for Phase 5/6 directional traversal"
  - "new_regime_2025 excluded from similarity computation due to null gdp_avg — 16 of 17 regimes participate in analogue graph"
  - "dimensions_matched always the 4 FRED dims list — VN dims (sbv_rate, vn_cpi, vnd_usd) not used in similarity (insufficient global comparability)"
  - "period_start/period_end on HAS_ANALOGUE carry SOURCE regime dates (from_id regime) per plan spec"

patterns-established:
  - "Narrative caching pattern: cache_key = from_id::to_id in flat JSON dict — simple, human-readable, easy to inspect"
  - "Gemini GEMINI_API_KEY absent → skip with warning, empty string narrative — allows non-narrative runs without API key"

requirements-completed: [DATA-02]

duration: ~2min
completed: 2026-03-09
---

# Phase 04 Plan 02: HAS_ANALOGUE Seed Script Summary

**MinMaxScaler + cosine similarity across 4 FRED dimensions seeds HAS_ANALOGUE relationships into Neo4j, with Gemini 2.0 Flash static narrative generation and JSON caching for idempotent re-runs.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-09T07:37:24Z
- **Completed:** 2026-03-09T07:39:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Cosine similarity computation on 4-dimensional normalized FRED vectors (gdp, cpi, unrate, fedfunds) using MinMaxScaler + scipy cdist
- Top 5 analogues per regime above 0.75 threshold selected in both directions — produces a sparse analogue graph (not fully connected)
- Gemini 2.0 Flash narrative generation for each analogue pair with exponential backoff retry and JSON caching to prevent redundant API spend
- UNWIND+MERGE pattern ensures idempotent relationship creation with all 5 required properties per ROADMAP.md Phase 4 SC #2
- Post-write validation: null-property check ensures data integrity before reporting success

## Task Commits

1. **Task 1: Create HAS_ANALOGUE relationship seed script** - `aa569c8` (feat)

## Files Created/Modified

- `scripts/seed-neo4j-analogues.py` - 415-line Python script: loads regime_data.json, normalizes FRED vectors, computes cosine similarity, generates Gemini narratives with caching, MERGEs HAS_ANALOGUE relationships into Neo4j with post-write validation

## Decisions Made

- **Threshold 0.75:** Conservative starting point per plan spec (Claude's discretion). Sparse connectivity for edge regimes (e.g., covid_crisis with extreme GDP -9.5%) is acceptable — log warning but do not lower threshold per-regime.
- **Both-direction relationships:** Plan spec requires HAS_ANALOGUE in both directions. From top-N selection of A's analogues, A->B and from B's selection A<-B are created. Directional traversal in Phase 5/6 queries works correctly.
- **new_regime_2025 excluded:** gdp_avg is null (period still unfolding). Only 1 FRED dimension null triggers exclusion per plan spec. 16 regimes participate in the analogue graph.
- **dimensions_matched is always FRED 4-dim list:** VN macro dimensions (sbv_rate, vn_cpi, vnd_usd) are not included in similarity computation — FRED dimensions have global comparability; VN-specific values captured in regime node properties for narrative context only.
- **period_start/period_end on relationship:** Carries SOURCE regime dates (from_id), not target. This enables Phase 6 reasoning node to understand "when was this comparison made from."

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required beyond existing `NEO4J_PASSWORD` and `GEMINI_API_KEY` environment variables (already documented).

## Next Phase Readiness

- `scripts/seed-neo4j-analogues.py` is ready to run once Neo4j is up with regime nodes (requires `seed-neo4j-regimes.py` to have been run first)
- Script will compute and persist HAS_ANALOGUE relationships needed by Phase 5 retrieval and Phase 6 macro_regime reasoning node
- Gemini narrative cache (`neo4j/seed/analogue_narratives.json`) will be created on first run and reused on subsequent runs — no redundant API spend
- No blockers for Phase 5 (retrieval layer) or Phase 6 (reasoning engine) — analogue relationship design is complete

---
*Phase: 04-knowledge-graph-and-document-corpus-population*
*Completed: 2026-03-09*

## Self-Check: PASSED

Files verified on disk:
- `scripts/seed-neo4j-analogues.py` — FOUND (415 lines, aa569c8 commit)

Commits verified:
- `aa569c8` — FOUND in git log
