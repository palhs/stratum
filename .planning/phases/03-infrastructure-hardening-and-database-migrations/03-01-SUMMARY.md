---
phase: 03-infrastructure-hardening-and-database-migrations
plan: 01
subsystem: database
tags: [flyway, postgres, migrations, sql, jsonb]

# Dependency graph
requires:
  - phase: 01-foundation (implied)
    provides: V1-V5 Flyway migrations and established migration conventions
provides:
  - reports table with JSONB payload, language check constraint, and historical row-per-run storage
  - report_jobs table with four-state status machine and FK to reports
  - Flyway V6 and V7 migration files applied cleanly to PostgreSQL
affects:
  - 04-sidecar-neo4j-langgraph (LangGraph checkpoint init)
  - 06-reasoning-pipeline (writes report rows after each pipeline run)
  - 08-fastapi-gateway (reads report_jobs for pipeline status tracking)
  - 09-batch-validation (creates one report_jobs row per asset)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Flyway double-underscore naming convention (V{N}__{Description}.sql)
    - One row per language per pipeline run — no upsert/overwrite, full history preserved
    - Nullable FK (report_id) populated only on job completion
    - TIMESTAMPTZ data_as_of + ingested_at dual-timestamp convention followed

key-files:
  created:
    - db/migrations/V6__reports.sql
    - db/migrations/V7__report_jobs.sql
  modified: []

key-decisions:
  - "Include report_markdown column alongside report_json — pre-renders Markdown for Phase 7 API response speed"
  - "Include data_as_of, model_version, pipeline_duration_ms metadata on reports — downstream phases need freshness signals and audit trail"
  - "report_jobs FK to reports is nullable — allows job creation before report exists, set on completion"
  - "Four-state machine only (pending/running/completed/failed) — no node-level tracking in table"

patterns-established:
  - "Migration header: -- V{N}__{name}.sql — [description] / -- Phase X | Plan Y | Requirement: [ID]"
  - "New tables without data_as_of use created_at/updated_at/ingested_at triple-timestamp pattern"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 2min
completed: 2026-03-09
---

# Phase 3 Plan 01: Database Migrations V6 and V7 Summary

**Flyway V6 (reports) and V7 (report_jobs) migrations applied cleanly — JSONB report storage with language-scoped rows and four-state job tracking with FK to reports**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-09T02:18:04Z
- **Completed:** 2026-03-09T02:19:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `reports` table with JSONB payload, language CHECK constraint ('vi'/'en'), pre-rendered Markdown column, and full metadata (data_as_of, model_version, pipeline_duration_ms)
- Created `report_jobs` table with four-state status machine CHECK constraint, nullable FK to reports.report_id (set on completion), and error TEXT column for traceback capture
- Both migrations applied via `flyway migrate` without checksum errors — V6 and V7 visible in flyway_schema_history with success=true
- All constraints verified: language check, status check, FK enforcement tested with deliberate invalid inserts

## Task Commits

Each task was committed atomically:

1. **Task 1: Create V6 reports migration** - `6baf9ec` (feat)
2. **Task 2: Create V7 report_jobs migration** - `92c8489` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `db/migrations/V6__reports.sql` - Reports table DDL with JSONB payload, language check, timestamp convention, and two indexes
- `db/migrations/V7__report_jobs.sql` - Report jobs DDL with four-state status machine, FK to reports, error column, and two indexes

## Decisions Made
- Included `report_markdown TEXT` column alongside `report_json JSONB` — pre-rendered Markdown avoids on-demand rendering overhead during Phase 7 API reads; storage cost is negligible versus latency benefit
- Included `data_as_of`, `model_version`, `pipeline_duration_ms` metadata on reports — `data_as_of` needed by downstream phases for DATA WARNING sections; `model_version` provides LLM audit trail; `pipeline_duration_ms` feeds Phase 9 batch performance monitoring
- report_jobs FK to reports is nullable — enables job creation (status=pending) before report exists; set to actual report_id when status transitions to 'completed'
- Kept indexes purpose-annotated with comments in SQL files for future maintainability

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — both migrations applied on first attempt, all constraint tests passed immediately.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- V6 and V7 tables are in PostgreSQL — Phase 6 reasoning pipeline can begin writing report rows immediately
- Phase 8 FastAPI gateway has the report_jobs table ready for status endpoint implementation
- Phase 9 batch validation can create one report_jobs row per asset (20 rows per batch run)
- No blockers — V1-V5 checksums untouched, Flyway history clean through v7

---
*Phase: 03-infrastructure-hardening-and-database-migrations*
*Completed: 2026-03-09*

## Self-Check: PASSED
- FOUND: db/migrations/V6__reports.sql
- FOUND: db/migrations/V7__report_jobs.sql
- FOUND: .planning/phases/03-infrastructure-hardening-and-database-migrations/03-01-SUMMARY.md
- FOUND: commit 6baf9ec (feat(03-01): create V6 reports migration)
- FOUND: commit 92c8489 (feat(03-01): create V7 report_jobs migration)
