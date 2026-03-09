---
phase: 03-infrastructure-hardening-and-database-migrations
plan: "03"
subsystem: infra
tags: [postgres, psycopg3, docker, langgraph, schema-init, checkpoint]

# Dependency graph
requires:
  - phase: 03-02
    provides: docker-compose.yml with memory limits and established init service pattern
  - phase: 03-01
    provides: Flyway migrations and postgres service definitions

provides:
  - LangGraph checkpoint schema (4 tables) isolated in dedicated langgraph PostgreSQL schema
  - One-shot langgraph-init Docker service that runs DDL and exits cleanly
  - Idempotent init script using psycopg3 synchronous connection with autocommit=True
affects:
  - 06-reasoning-pipeline (connects AsyncPostgresSaver using ?options=-csearch_path=langgraph)
  - Any phase requiring LangGraph checkpoint persistence

# Tech tracking
tech-stack:
  added: [psycopg3 (psycopg[binary]) — installed at runtime in langgraph-init container]
  patterns:
    - One-shot Docker init service with python:3.12-slim image
    - Raw DDL schema init instead of library setup() (avoids public schema assumption)
    - autocommit=True for DDL statements in psycopg3

key-files:
  created:
    - scripts/init-langgraph-schema.py
  modified:
    - docker-compose.yml

key-decisions:
  - "Checkpoints in stratum database but isolated in langgraph schema (not public) — avoids table collision with business schema"
  - "psycopg3 synchronous connection for init script — async unnecessary for one-shot DDL, avoids asyncio overhead"
  - "Does NOT use AsyncPostgresSaver.setup() — that targets public schema only and has no schema parameter"
  - "langgraph-init depends on flyway (completed_successfully) — ensures business tables exist before checkpoint schema"
  - "Profiles: reasoning only — checkpoint schema is reasoning-pipeline concern, not needed for ingestion-only deployments"
  - "pip install psycopg[binary] at runtime — acceptable for one-shot init; no custom Docker image needed"

patterns-established:
  - "One-shot Python init service: python:3.12-slim + pip install at entrypoint + raw DDL script"
  - "Schema isolation: use dedicated PostgreSQL schemas (langgraph, public) to prevent table namespace collisions"

requirements-completed: [INFRA-06]

# Metrics
duration: 2min
completed: "2026-03-09"
---

# Phase 3 Plan 03: LangGraph Checkpoint Schema Init Summary

**PostgreSQL langgraph schema with 4 AsyncPostgresSaver checkpoint tables created via one-shot psycopg3 DDL init service isolated from public schema**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-09T02:22:53Z
- **Completed:** 2026-03-09T02:24:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `scripts/init-langgraph-schema.py` — synchronous psycopg3 DDL script creating 4 LangGraph checkpoint tables in `langgraph` schema with full idempotency and post-DDL validation
- Added `langgraph-init` one-shot Docker service to docker-compose.yml following established init service pattern, scoped to reasoning profile only
- Established schema isolation pattern: checkpoint tables live in `langgraph`, business tables in `public`, future connection uses `?options=-csearch_path=langgraph`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create LangGraph checkpoint schema init script** - `97cf6ea` (feat)
2. **Task 2: Add langgraph-init one-shot Docker service to docker-compose.yml** - `b23f5a9` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `scripts/init-langgraph-schema.py` - One-shot DDL script: creates langgraph schema + 4 checkpoint tables using psycopg3 synchronous connection (autocommit=True); validates table count post-DDL; exits 0 on success, non-zero on failure
- `docker-compose.yml` - Added langgraph-init service in MIGRATION / INIT TIER section; depends on postgres (healthy) and flyway (completed_successfully); reasoning profile and network only; no restart policy

## Decisions Made
- Used synchronous psycopg3 (not async) for the init script — async is unnecessary for one-shot DDL and adds asyncio overhead without benefit; Phase 6 reasoning-engine will use async
- Raw DDL instead of `AsyncPostgresSaver.setup()` — the library method targets public schema only with no schema parameter override
- `depends_on: flyway: condition: service_completed_successfully` — prevents race condition where langgraph-init connects before Flyway finishes; ensures business tables exist first
- `profiles: ["reasoning"]` — checkpoint schema is reasoning-pipeline concern only; ingestion deployments do not need it

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- LangGraph checkpoint schema is ready for Phase 6 AsyncPostgresSaver connection
- Phase 6 connects via: `AsyncPostgresSaver.from_conn_string(db_url + "?options=-csearch_path%3Dlanggraph")`
- Run `docker compose --profile reasoning up` to create the schema before reasoning-engine starts
- Run idempotency check: `docker compose --profile reasoning up langgraph-init` a second time — should succeed without errors

---
*Phase: 03-infrastructure-hardening-and-database-migrations*
*Completed: 2026-03-09*
