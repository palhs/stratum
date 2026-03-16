---
phase: 08-fastapi-gateway-and-docker-service
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, background-tasks, postgresql, report-jobs, tdd]

requires:
  - phase: 07-graph-assembly-and-end-to-end-report-generation
    provides: generate_report() async entry point, report_jobs and reports table schemas
  - phase: 08-01
    provides: FastAPI app with lifespan (db_engine, neo4j_driver, qdrant_client, job_queues on app.state)

provides:
  - POST /reports/generate — 202 async job submission with job_id; 409 on active-job conflict
  - GET /reports/{job_id} — 200 completed (report JSON+markdown), 202 pending/running, 404 not found
  - _run_pipeline background task — pending→running→completed/failed lifecycle with SSE queue sentinel

affects:
  - 08-03-SSE-streaming (consumes job_queues, uses same job_id from POST)

tech-stack:
  added: []
  patterns:
    - SQLAlchemy Core Table reflection (autoload_with=db_engine) — consistent with storage.py
    - Lazy module-level import for generate_report — allows test patching without reasoning package on sys.path
    - BackgroundTasks with asyncio.Queue SSE sentinel — enables Plan 03 streaming

key-files:
  created:
    - reasoning/app/routers/reports.py
    - reasoning/tests/api/test_reports.py
  modified:
    - reasoning/app/main.py

key-decisions:
  - "report_id FK in report_jobs points to vi_id (Vietnamese report) — primary language per locked project decision"
  - "generate_report assigned as module-level None and lazily populated via _get_generate_report() — avoids import chain failure in test environments where reasoning package root is not on sys.path"
  - "BackgroundTasks used (not asyncio.create_task) — FastAPI's BackgroundTasks executes synchronously in TestClient, enabling clean unit test assertions on status transitions"
  - "SSE asyncio.Queue created at POST time and stored in app.state.job_queues[job_id] — prepared for Plan 03 streaming without blocking Plan 02"

patterns-established:
  - "Router endpoints mock app.state via test_app.state = MagicMock() — no lifespan needed in unit tests"
  - "_update_job_status(db_engine, job_id, status) call signature — positional args, status at index 2"

requirements-completed: [SRVC-01, SRVC-02]

duration: 4min
completed: 2026-03-16
---

# Phase 8 Plan 02: Report Generation and Retrieval Endpoints Summary

**POST /reports/generate with BackgroundTasks job lifecycle and GET /reports/{job_id} with 200/202/404 status routing, wrapping Phase 7 generate_report() pipeline.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-16T09:18:29Z
- **Completed:** 2026-03-16T09:22:36Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 3

## Accomplishments

- POST /reports/generate returns 202 with job_id+status immediately; BackgroundTasks invokes Phase 7 pipeline asynchronously
- 409 conflict detection via _find_active_job (pending/running jobs only); failed jobs allow retry
- GET /reports/{job_id} routes by job status: 200+report for completed, 202+status for pending/running, 404 for unknown
- Full job lifecycle: pending → running → completed/failed with _update_job_status on each transition
- SSE asyncio.Queue created at submit time and stored in app.state.job_queues for Plan 03 streaming
- All 8 report tests pass; all 10 API tests pass (health + reports)

## Task Commits

Each task was committed atomically using TDD:

1. **RED: Failing tests** - `abb25a6` (test)
2. **GREEN: Router implementation** - `dc12196` (feat)

_Note: Test assertion bug (args[1] vs args[2]) fixed inline before GREEN commit._

## Files Created/Modified

- `reasoning/app/routers/reports.py` — GenerateRequest/ReportResponse models, 5 SQLAlchemy Core DB helpers, _run_pipeline background task, POST /generate and GET /{job_id} endpoints
- `reasoning/tests/api/test_reports.py` — 8 tests covering all SRVC-01/SRVC-02 behaviors with mocked DB helpers and pipeline
- `reasoning/app/main.py` — Added reports router import and include_router(prefix="/reports")

## Decisions Made

- `generate_report` is a module-level `None` sentinel lazily populated by `_get_generate_report()` — required because `app/pipeline/__init__.py` uses `reasoning.app.pipeline.*` absolute imports that fail when `reasoning/` is the working root (as in pytest runs). This allows tests to patch `app.routers.reports.generate_report` without triggering the broken import chain.
- `report_id` in `_update_job_status` on completion is set to `vi_id` — Vietnamese report is the primary FK per project decision (both report IDs are stored in the reports table).
- `BackgroundTasks` preferred over `asyncio.create_task` — FastAPI's BackgroundTasks runs synchronously inside `TestClient`, making `_update_job_status("completed")` assertions reliable without async test plumbing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertion using wrong positional index for status arg**
- **Found during:** Task 1 (GREEN phase execution)
- **Issue:** `test_background_task_calls_pipeline` used `call.args[1]` to read the status argument but `_update_job_status(db_engine, job_id, status)` puts status at `args[2]`
- **Fix:** Changed assertion to `call.args[2]`
- **Files modified:** `reasoning/tests/api/test_reports.py`
- **Verification:** `test_background_task_calls_pipeline` passes
- **Committed in:** dc12196 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test assertion)
**Impact on plan:** Minor — off-by-one index in test assertion. No scope creep.

## Issues Encountered

- `app/pipeline/__init__.py` uses `reasoning.app.pipeline.*` absolute imports that fail when running pytest from within `reasoning/` (where `reasoning` is not a discoverable package). Resolved by making `generate_report` a lazily-initialized module-level attribute, avoiding the import chain at module load time. Existing pipeline tests had the same limitation and were already skipping due to conftest import errors.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- POST /reports/generate and GET /reports/{job_id} are production-ready
- job_queues[job_id] set up at submission time — Plan 03 (SSE) can wire GET /reports/stream/{job_id} directly to the queue
- SSE endpoint should be registered in main.py BEFORE the /{job_id} GET route to avoid path parameter capture

---
*Phase: 08-fastapi-gateway-and-docker-service*
*Completed: 2026-03-16*
