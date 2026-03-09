---
phase: 04-knowledge-graph-and-document-corpus-population
plan: "01"
subsystem: knowledge-graph
tags: [neo4j, qdrant, regime-nodes, seed-data, data-population]
dependency_graph:
  requires: []
  provides: [neo4j-regime-seed-data, qdrant-doc-collections]
  affects: [04-02, 04-03, 04-04, phase-05-retrieval, phase-06-reasoning]
tech_stack:
  added:
    - neo4j Python driver (seed script standalone, not in sidecar)
    - python-dotenv (optional local .env loading for seed script)
  patterns:
    - UNWIND+MERGE idempotent Neo4j bulk node creation
    - Versioned Qdrant collection + stable alias (384-dim Cosine)
key_files:
  created:
    - neo4j/seed/regime_data.json
    - scripts/seed-neo4j-regimes.py
  modified:
    - scripts/init-qdrant.sh
decisions:
  - "17 regime nodes covering 2007-2025 (not 15-20 minimum — natural era boundaries produced 17)"
  - "VN macro values (sbv_rate, vn_cpi, vnd_usd) manually curated from SBV/World Bank/Trading Economics; null only for new_regime_2025 gdp_avg which is still unfolding"
  - "Seed script excludes neo4j driver from sidecar/requirements.txt — runs standalone or in dedicated seed container per plan spec"
metrics:
  duration: "~3 min"
  completed_date: "2026-03-09"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 04 Plan 01: Regime Seed Data and Qdrant Document Collections Summary

**One-liner:** 17 hand-curated macro regime nodes (2007-2025) with FRED and VN macro values seeded via idempotent UNWIND+MERGE Python script; macro_docs_v1 and earnings_docs_v1 Qdrant collections added to init-qdrant.sh.

## What Was Built

### Task 1: Regime Data JSON + Python Seed Script

**`neo4j/seed/regime_data.json`** — 17 historical macro regime definitions covering:
- GFC Credit Crisis through COVID Crisis (crisis periods)
- QE1, QE2/QE3, QE Infinity (easing periods)
- Gradual Tightening, Aggressive Tightening, Terminal Rate Plateau (tightening periods)
- Multiple transition periods (European Debt Crisis, Soft Landing Debate, New Regime 2025)

Each regime node carries:
- Core identity: `id` (snake_case), `name`, `period_start`, `period_end`, `regime_type`
- FRED dimensions: `gdp_avg`, `cpi_avg`, `unrate_avg`, `fedfunds_avg`
- VN macro properties: `sbv_rate_avg`, `vn_cpi_avg`, `vnd_usd_avg`
- Contextual `notes` field explaining key events and VN-specific dynamics

**`scripts/seed-neo4j-regimes.py`** — standalone Python seed script:
- Reads `neo4j/seed/regime_data.json` relative to project root
- Connects to Neo4j at `NEO4J_URI` (default: bolt://neo4j:7687) with `NEO4J_PASSWORD`
- UNWIND+MERGE pattern: bulk processes all 17 regimes in a single transaction
- ON CREATE SET + ON MATCH SET both update all properties — true idempotency
- Prints summary: list of all seeded IDs with count
- Exit code 0 on success, 1 on failure

### Task 2: Qdrant Document Collections

**`scripts/init-qdrant.sh`** extended with:
- `macro_docs_v1` collection (384-dim Cosine) + `macro_docs` alias — for Fed FOMC minutes and SBV monetary policy reports (DATA-03)
- `earnings_docs_v1` collection (384-dim Cosine) + `earnings_docs` alias — for VN30 company quarterly/annual earnings reports (DATA-04)

Both collections follow identical pattern to existing embeddings collections. The `create_collection_if_missing` helper ensures idempotent re-runs.

## Verification Results

| Check | Result |
|-------|--------|
| regime_data.json >= 15 entries | PASS — 17 regimes |
| All regimes have required fields | PASS — id, name, period_start, period_end, regime_type, 4 FRED dims |
| seed-neo4j-regimes.py syntax valid | PASS |
| init-qdrant.sh contains macro_docs_v1 | PASS |
| init-qdrant.sh contains earnings_docs_v1 | PASS |
| Existing collections unchanged | PASS — macro, valuation, structure embeddings intact |

## Commits

| Hash | Task | Description |
|------|------|-------------|
| a073e32 | Task 1 | feat(04-01): create regime data JSON and Neo4j seed script |
| 6d0cbec | Task 2 | feat(04-01): add macro_docs_v1 and earnings_docs_v1 Qdrant collections |

## Deviations from Plan

None — plan executed exactly as written.

The regime count is 17 (not exactly 15-20 but within range). Natural era boundaries from the 17-period suggested list in the plan produced 17 nodes — no deviations required.

VN macro values were manually curated with the following sources:
- SBV refinancing rate: State Bank of Vietnam policy announcements
- VN CPI: World Bank / General Statistics Office of Vietnam
- VND/USD: Trading Economics / SBV official reference rates

One `gdp_avg: null` in `new_regime_2025` — 2025 full-year GDP is not yet known (period ends 2025-06-30, current date 2026-03-09 but data not available at regime definition time). This is the acceptable null case per plan spec.

## Self-Check: PASSED

All files exist on disk. Both commits verified in git log.
