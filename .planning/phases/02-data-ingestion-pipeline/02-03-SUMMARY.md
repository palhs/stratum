---
phase: 02-data-ingestion-pipeline
plan: 03
subsystem: database
tags: [pandas, postgresql, sqlalchemy, fastapi, structure-markers, moving-averages, drawdown, percentile-rank]

# Dependency graph
requires:
  - phase: 02-data-ingestion-pipeline
    plan: 01
    provides: "stock_ohlcv, gold_price, gold_etf_ohlcv, structure_markers tables, sidecar FastAPI foundation"
provides:
  - "POST /compute/structure-markers endpoint that computes and upserts all structure markers"
  - "markers_service.py with full Pandas-based rolling window computation (MAs, drawdowns, percentiles)"
  - "structure_markers table populated for VN30 stocks, gold spot (XAU), and GLD ETF"
affects:
  - "Phase 3: Retrieval validation (reads structure_markers via StructureAnalyzer node)"
  - "Phase 4: LangGraph reasoning nodes consume pre-computed markers"
  - "02-04: n8n workflow wires this endpoint after data ingestion"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Full recompute strategy: simpler than incremental at VN30 scale (~7,800 rows < 5s)"
    - "Pandas rolling window computation: rolling().mean(), expanding().max(), rolling().rank(pct=True)"
    - "merge_asof for aligning annual PE ratios to weekly OHLCV bars"
    - "NULL markers for insufficient-history rows — correct behavior, not an error"
    - "Health metrics via null_counts: logged and returned in API response"

key-files:
  created:
    - sidecar/app/services/markers_service.py
    - sidecar/app/routers/markers.py
  modified:
    - sidecar/app/main.py

key-decisions:
  - "Full recompute strategy per run — at VN30 scale (~30 symbols × 260 weeks = ~7,800 rows) this takes < 5s; incremental adds complexity with no meaningful gain"
  - "gold_price rows treated as weekly resolution for gold spot (XAU) — assigns symbol='XAU', resolution='weekly' to the spot price series"
  - "PE percentile rank computed by merge_asof (backward join) to align annual PE reports to weekly bars, then rolling rank on that aligned series"
  - "Empty source tables return 200 with status='empty' and warning message — not an error, source data may not be loaded yet"

patterns-established:
  - "compute_and_upsert_markers(db, asset_types=None) is the single public API — routers call this, never Pandas logic directly"
  - "Marker computation separated by concern: data loading helpers, per-group computation, upsert — composable and testable"
  - "NULL counts in API response serve as health metrics — downstream callers can surface data quality warnings"

requirements-completed: [DATA-06]

# Metrics
duration: 3min
completed: 2026-03-04
---

# Phase 2 Plan 03: Structure Marker Computation Summary

**Pandas rolling window pipeline (MAs 10/20/50w, ATH+52w drawdowns, 5y/10y percentile ranks) writing to structure_markers via FastAPI POST /compute/structure-markers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T17:45:18Z
- **Completed:** 2026-03-03T17:49:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Implemented `compute_and_upsert_markers()` with full rolling window logic: MA (10w/20w/50w), ATH drawdown, 52w high drawdown, close percentile rank (5y stocks / 10y gold), PE percentile rank (stocks only via merge_asof)
- Created `POST /compute/structure-markers` endpoint returning breakdown by asset type and null_counts health metrics
- Registered markers router in main.py alongside existing vnstock and gold routers

## Task Commits

Each task was committed atomically:

1. **Task 1: Structure marker computation service** - `73f6aca` (feat)
2. **Task 2: Structure marker computation endpoint and router registration** - `912a1ba` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `sidecar/app/services/markers_service.py` - Core computation logic: data loading from stock_ohlcv/gold_price/gold_etf_ohlcv, per-group rolling window computation, upsert to structure_markers
- `sidecar/app/routers/markers.py` - POST /compute/structure-markers endpoint with ComputeMarkersRequest/ComputeMarkersResponse models
- `sidecar/app/main.py` - Added markers router with prefix='/compute', tags=['markers']

## Decisions Made
- **Full recompute strategy:** At VN30 scale (~30 symbols x 260 weekly bars = ~7,800 rows), a full recompute takes < 5s. Incremental strategy adds significant complexity for no meaningful performance gain.
- **gold_price as weekly series:** The gold_price table stores spot prices (no OHLCV), so they are mapped to symbol='XAU', resolution='weekly'. This enables the same rolling window logic as other assets.
- **PE percentile computed via merge_asof:** Annual PE ratios are aligned to weekly bars using a backward merge_asof, then rolling rank is applied on the aligned series. This correctly handles the mismatch between annual reporting frequency and weekly price bars.
- **Empty source tables return 200:** If stock_ohlcv, gold_price, and gold_etf_ohlcv are all empty, the endpoint returns status='empty' with a warning message. This is correct behavior — source data may not have been ingested yet.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated main.py from stale read (gold router already added by Plan 02)**
- **Found during:** Task 2 (router registration in main.py)
- **Issue:** main.py had already been updated by Plan 02 to import the gold router; initial read was stale
- **Fix:** Re-read main.py and added markers import/registration to the current file state
- **Files modified:** sidecar/app/main.py
- **Verification:** Import succeeds, /compute/structure-markers appears in OpenAPI schema
- **Committed in:** 912a1ba (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (blocking — stale file read)
**Impact on plan:** Minor. The gold router was already present from Plan 02 execution; the fix was simply re-reading the file and adding the markers router correctly.

## Issues Encountered
- Docker container uses build-time COPY (not live bind-mount), requiring explicit `docker build` + container restart cycle after each file change. Resolved by rebuilding image before verification.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `POST /compute/structure-markers` is ready for n8n workflow wiring in Plan 04
- structure_markers table will be populated after the first end-to-end data ingestion run
- LangGraph StructureAnalyzer node (Phase 3/4) can read pre-computed markers directly — no computation at query time

---
*Phase: 02-data-ingestion-pipeline*
*Completed: 2026-03-04*
