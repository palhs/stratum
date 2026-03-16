---
phase: 09-production-hardening-and-batch-validation
plan: "03"
subsystem: database
tags: [postgres, psycopg, langgraph, cleanup, ttl, checkpoints]

# Dependency graph
requires:
  - phase: 03-infrastructure-and-data-foundations
    provides: langgraph checkpoint schema (langgraph.checkpoints, checkpoint_blobs, checkpoint_writes) created by init-langgraph-schema.py
provides:
  - created_at TIMESTAMPTZ column on langgraph.checkpoints with DEFAULT NOW() (idempotent ALTER TABLE)
  - scripts/cleanup-checkpoints.py TTL-based purge script with dry-run, configurable TTL_DAYS and DATABASE_URL
  - Unit tests verifying DELETE cascade order, dry-run no-op, early exit on zero expired rows
affects: [phase-09, phase-10, docker-compose, langgraph-init service]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TTL-based manual cascade cleanup (writes -> blobs -> checkpoints) — used because no FK cascade exists on langgraph tables
    - argparse --dry-run pattern for safe production scripts
    - sys.argv mock in tests for argparse-consuming scripts loaded via importlib

key-files:
  created:
    - scripts/cleanup-checkpoints.py
    - reasoning/tests/integration/__init__.py
    - reasoning/tests/integration/test_checkpoint_cleanup.py
  modified:
    - scripts/init-langgraph-schema.py

key-decisions:
  - "ALTER TABLE uses ADD COLUMN IF NOT EXISTS — idempotent on re-runs of langgraph-init container"
  - "Cleanup script uses context manager psycopg.connect() with manual conn.commit() — autocommit=False for multi-statement transactional batch delete"
  - "DELETE cascade order: checkpoint_writes THEN checkpoint_blobs THEN checkpoints — required because no FK cascade exists; deleting checkpoints first would orphan write/blob rows"
  - "sys.argv patched in unit tests when loading argparse-consuming scripts via importlib — prevents pytest argv from being parsed as script args"

patterns-established:
  - "Manual cascade delete pattern: delete child tables before parent when no FK cascade exists"
  - "Dry-run guard: count expired rows first, exit early if zero, exit early if --dry-run"

requirements-completed: [SRVC-08]

# Metrics
duration: 15min
completed: 2026-03-17
---

# Phase 9 Plan 03: Checkpoint Cleanup TTL Script Summary

**TTL-based LangGraph checkpoint purge with created_at column, dry-run support, and unit tests — satisfies SRVC-08 (prevent unbounded PostgreSQL growth)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-17T00:45:00Z
- **Completed:** 2026-03-17T01:00:00Z
- **Tasks:** 1 (TDD — 2 commits: RED test + GREEN impl)
- **Files modified:** 4

## Accomplishments

- Added `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` to `langgraph.checkpoints` via idempotent `ADD COLUMN IF NOT EXISTS` in init-langgraph-schema.py
- Implemented `scripts/cleanup-checkpoints.py` with correct manual cascade delete order (checkpoint_writes -> checkpoint_blobs -> checkpoints), `--dry-run` flag, and configurable `CHECKPOINT_TTL_DAYS` / `DATABASE_URL`
- 6 unit tests pass without Docker: DELETE order, dry-run no-op, early exit on zero expired rows, init script DDL verification, --help flag, and valid syntax check

## Task Commits

Each task was committed atomically:

1. **TDD RED: failing tests** - `5186873` (test)
2. **TDD GREEN: implementation** - `b7e3ba3` (feat)

_Note: TDD tasks have two commits (test RED, then feat GREEN). Test file was also updated during GREEN to fix sys.argv mock and context manager mock patterns._

## Files Created/Modified

- `scripts/init-langgraph-schema.py` - Added `ALTER_DDL` constant and `conn.execute(ALTER_DDL)` call to add `created_at TIMESTAMPTZ` column after main DDL execution
- `scripts/cleanup-checkpoints.py` - New TTL-based cleanup script with argparse, psycopg context manager, manual cascade DELETE, commit, dry-run path
- `reasoning/tests/integration/test_checkpoint_cleanup.py` - 6 unit tests using `importlib` + `unittest.mock` to test cleanup behavior without Docker
- `reasoning/tests/integration/__init__.py` - Package marker (empty)

## Decisions Made

- `ADD COLUMN IF NOT EXISTS` ensures the init script is fully idempotent — safe to re-run langgraph-init container without error.
- Cleanup script uses `psycopg.connect()` as context manager with explicit `conn.commit()` (not `autocommit=True`) — batch delete should be transactional; if a DELETE fails mid-way, nothing is committed.
- DELETE cascade order (writes -> blobs -> checkpoints) is mandatory because no FK cascade constraint exists. Reversing the order would orphan rows in child tables.
- Tests mock `sys.argv` to `["cleanup-checkpoints.py"]` when loading the script via `importlib` — argparse reads `sys.argv` globally and would otherwise parse pytest's own arguments, causing `SystemExit(2)`.
- Mock connection wires `__enter__` to return the mock itself — required because the script wraps `psycopg.connect()` in a context manager (`with psycopg.connect(...) as conn`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sys.argv mock missing from two tests**
- **Found during:** Task 1 GREEN phase (test execution)
- **Issue:** `test_cleanup_deletes_in_correct_order` and `test_cleanup_no_expired_exits_early` did not mock `sys.argv`. When loaded via `importlib`, argparse parsed pytest's own arguments and raised `SystemExit(2)`.
- **Fix:** Added `with patch("sys.argv", ["cleanup-checkpoints.py"])` context manager to both tests.
- **Files modified:** `reasoning/tests/integration/test_checkpoint_cleanup.py`
- **Verification:** Both tests pass after fix.
- **Committed in:** `b7e3ba3` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Context manager mock wiring in _mock_conn_returning_count()**
- **Found during:** Task 1 GREEN phase (test execution)
- **Issue:** `test_cleanup_deletes_in_correct_order` asserted 0 DELETE calls because `psycopg.connect` context manager `__enter__` returned a new auto-generated MagicMock instead of `mock_conn`. All `conn.execute` calls went to the auto-mock, not `mock_conn`.
- **Fix:** Added explicit `mock_conn.__enter__ = MagicMock(return_value=mock_conn)` and `mock_conn.__exit__ = MagicMock(return_value=False)` to force context manager to return the trackable mock.
- **Files modified:** `reasoning/tests/integration/test_checkpoint_cleanup.py`
- **Verification:** All 6 tests pass after fix.
- **Committed in:** `b7e3ba3` (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug in test setup; plan's action section described test structure but didn't account for argparse/context-manager interaction details)
**Impact on plan:** No scope creep. Both fixes necessary for tests to correctly verify the implementation.

## Issues Encountered

- System Python3.11 has brownie pytest plugin installed which fails to load due to missing `web3` dependency (same issue documented in Phase 07-05 decisions). Used `reasoning/.venv` (Python 3.11 venv) with pytest + psycopg installed to run tests cleanly.

## User Setup Required

None - no external service configuration required. Cleanup script runs on demand or as a scheduled Docker container with `DATABASE_URL` and optionally `CHECKPOINT_TTL_DAYS` environment variables.

## Next Phase Readiness

- `scripts/cleanup-checkpoints.py` is ready to wire into a cron job or Docker scheduled task in Phase 9 (batch validation / ops hardening).
- The `created_at` column will be present after next `docker-compose up` runs `langgraph-init` service.
- No blockers for remaining Phase 9 plans.

---
*Phase: 09-production-hardening-and-batch-validation*
*Completed: 2026-03-17*
