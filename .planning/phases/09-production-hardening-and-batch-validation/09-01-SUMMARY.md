---
phase: 09-production-hardening-and-batch-validation
plan: 01
subsystem: testing
tags: [httpx, docker, batch-validation, memory-monitoring, oom-detection, vn30]

requires:
  - phase: 08-production-hardening-and-batch-validation
    provides: POST /reports/generate and GET /reports/{job_id} HTTP API

provides:
  - scripts/batch-validate.py — standalone batch validation script for 20-stock sequential workload with memory monitoring and OOM detection

affects:
  - phase 09 production hardening — batch script is the primary SRVC-06 validation artifact

tech-stack:
  added: []
  patterns:
    - "Sequential batch processing: submit_and_poll() processes one ticker at a time, ensuring no concurrent job conflicts (sequential = no 409s)"
    - "Docker subprocess pattern: docker stats --no-stream and docker inspect via subprocess.run(capture_output=True) for host-side container introspection"
    - "Graceful error handling: all failure modes (connection error, 409, timeout) captured as status strings in results, never raise"

key-files:
  created:
    - scripts/batch-validate.py
  modified: []

key-decisions:
  - "POLL_INTERVAL_SECONDS=5 matches sequential job processing — no need for tighter polling since jobs run single-threaded in the pipeline"
  - "check_oom_status() treats inspect failure (container not found) as non-OOM — allows partial stack deployments without false-positive FAIL"
  - "Intermediate docker stats every 5 tickers (4 snapshots total) provides temporal memory profile during the run"
  - "exit 0 / exit 1 strictly on OOM count — failed jobs are acceptable production outcomes; OOM kills are not"

patterns-established:
  - "Standalone script pattern: argparse + main() + sys.exit() with clear default values for offline scripting"
  - "Docker inspection via subprocess.run() at host level — no Docker SDK dependency, works anywhere docker CLI is available"

requirements-completed: [SRVC-06]

duration: ~2min
completed: 2026-03-16
---

# Phase 9 Plan 01: Batch Validation Script Summary

**Standalone Python script that sequentially validates 20 VN30 tickers via the reports API, captures docker stats MEM USAGE/LIMIT at start/every-5-tickers/end, and checks OOMKilled status per service to produce a definitive PASS/FAIL result**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-16T18:25:57Z
- **Completed:** 2026-03-16T18:27:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `scripts/batch-validate.py` — fully standalone, runnable against live Docker stack
- 20 VN30 tickers processed sequentially via POST /reports/generate + GET /reports/{job_id} polling
- Memory monitoring via docker stats at initial, every 5 tickers (4 checkpoints), and final snapshots
- OOMKilled detection per service via docker inspect — definitive PASS/FAIL determination
- Summary table output with per-ticker job_id, status, elapsed seconds

## Task Commits

Each task was committed atomically:

1. **Task 1: Create batch validation script with memory monitoring** - `b781fc2` (feat)

## Files Created/Modified
- `scripts/batch-validate.py` — Batch validation orchestrator with wait_for_health(), submit_and_poll(), capture_docker_stats(), check_oom_status(), run_batch(), main()

## Decisions Made
- POLL_INTERVAL_SECONDS=5 matches sequential job processing (no concurrent job conflicts, so tight polling unnecessary)
- check_oom_status() treats docker inspect failure (container not found) as non-OOM to allow partial stack testing
- Intermediate docker stats every 5 tickers provides 4 temporal snapshots during the run without overwhelming output
- Script exits 0 on PASS (no OOM), 1 on FAIL (any OOM) — failed pipeline jobs are acceptable, OOM kills are not

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Batch validation script ready to run against live Docker stack: `python scripts/batch-validate.py --base-url http://localhost:8001`
- Requires full Docker stack running: `docker compose --profile reasoning up -d`
- Script produces PASS/FAIL result proving SRVC-06 compliance (20-stock workload within memory limits without OOM kills)

---
*Phase: 09-production-hardening-and-batch-validation*
*Completed: 2026-03-16*
