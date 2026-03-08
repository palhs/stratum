---
phase: 01-infrastructure-and-storage-foundation
plan: 02
subsystem: database
tags: [postgres, flyway, neo4j, qdrant, sql, cypher, apoc, migrations, schema, docker-compose]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-storage-foundation/01-01
    provides: Docker Compose stack with flyway, neo4j-init, and qdrant-init one-shot services

provides:
  - Flyway migration V1 creating pipeline_run_log with data_as_of/ingested_at timestamp convention
  - n8n metadata database bootstrap via PostgreSQL initdb mechanism
  - Neo4j uniqueness constraints on Regime.id and TimePeriod.id
  - Neo4j APOC trigger enforcing RESEMBLES relationship property requirements
  - Qdrant macro_embeddings_v1 collection (384 dimensions, Cosine) with macro_embeddings alias
  - Fully initialized storage layer from first docker compose up

affects:
  - Phase 2: data ingestion pipelines write to pipeline_run_log with timestamp convention
  - Phase 3: Qdrant macro_embeddings collection used for regime analogue retrieval (MACRO-04)
  - Phase 4: RESEMBLES relationships enforced by trigger before analogue reasoning begins

# Tech tracking
tech-stack:
  added:
    - Flyway SQL migration (V{version}__{description}.sql naming convention)
    - Cypher DDL for Neo4j constraints (Community Edition)
    - APOC Core apoc.trigger.install/start (Neo4j 5.x API)
    - FastEmbed BAAI/bge-small-en-v1.5 (384-dimension vector size decision)
  patterns:
    - Flyway versioned migrations for PostgreSQL schema evolution
    - TIMESTAMPTZ for all timestamps; data_as_of + ingested_at on every time-series table
    - Neo4j init split by database: constraints against neo4j, APOC triggers against system
    - Qdrant alias versioning: stable alias (macro_embeddings) -> versioned collection (macro_embeddings_v1)
    - Idempotent init scripts: IF NOT EXISTS, drop-before-install, check-before-create

key-files:
  created:
    - db/migrations/V1__initial_schema.sql
    - db/init/create-n8n-db.sql
    - neo4j/init/01_constraints.cypher
    - neo4j/init/02_apoc_triggers.cypher
  modified:
    - scripts/init-qdrant.sh (updated 1536 -> 384 dimensions for FastEmbed)
    - docker-compose.yml (postgres initdb volume mount; neo4j-init entrypoint per-database targeting)

key-decisions:
  - "Vector size 384 (FastEmbed BAAI/bge-small-en-v1.5) instead of 1536 (OpenAI) — more memory-efficient for 8GB VPS; FastEmbed is the chosen embedding approach per ROADMAP Phase 3"
  - "Neo4j init entrypoint split: 01_constraints.cypher runs -d neo4j, 02_apoc_triggers.cypher runs -d system — constraints cannot be created on system database"
  - "apoc.trigger.drop before install for idempotency — apoc.trigger.install has no IF NOT EXISTS; drop fails silently on first run"
  - "n8n database created via PostgreSQL initdb mechanism (create-n8n-db.sql) — CREATE DATABASE cannot run inside a Flyway transaction"

patterns-established:
  - "Timestamp convention: every time-series table MUST have data_as_of TIMESTAMPTZ NOT NULL and ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
  - "Flyway naming: V{N}__{snake_case_description}.sql — double underscore separator"
  - "Qdrant collection versioning: {name}_v{N} collection with {name} alias for zero-downtime model upgrades"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 2min
completed: "2026-03-03"
---

# Phase 1 Plan 2: Storage Initialization Scripts Summary

**Flyway V1 migration, Neo4j Community Edition constraints + APOC RESEMBLES trigger, and Qdrant 384-dim alias-versioned collection — fully initialized storage layer from first docker compose up.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-03T07:00:55Z
- **Completed:** 2026-03-03T07:03:14Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- PostgreSQL schema established with pipeline_run_log table and enforced data_as_of/ingested_at timestamp convention for all future time-series tables
- Neo4j uniqueness constraints on Regime and TimePeriod nodes (Community Edition compatible), plus APOC trigger that rejects RESEMBLES relationships missing similarity_score, dimensions_matched, or period properties
- Qdrant 3-collection setup with 384-dimension vectors (FastEmbed BAAI/bge-small-en-v1.5) and alias versioning for zero-downtime embedding model upgrades

## Task Commits

Each task was committed atomically:

1. **Task 1: PostgreSQL Flyway migration and n8n database init** - `1e5208c` (feat)
2. **Task 2: Neo4j constraints and APOC trigger init scripts** - `f16124e` (feat)
3. **Task 3: Qdrant collection init script update to 384 dimensions** - `851c55f` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `db/migrations/V1__initial_schema.sql` - Flyway V1 migration: pipeline_run_log table with status CHECK constraint, indexes, and timestamp convention documentation
- `db/init/create-n8n-db.sql` - PostgreSQL initdb script to create n8n_meta database idempotently
- `neo4j/init/01_constraints.cypher` - Uniqueness constraints on Regime.id and TimePeriod.id
- `neo4j/init/02_apoc_triggers.cypher` - APOC trigger enforcing RESEMBLES required properties (similarity_score, dimensions_matched, period)
- `scripts/init-qdrant.sh` - Updated vector size from 1536 to 384 (FastEmbed model); added wait-for-ready loop
- `docker-compose.yml` - Added postgres initdb volume mount; updated neo4j-init entrypoint to target correct DB per script

## Decisions Made
- **FastEmbed 384 dimensions vs OpenAI 1536:** Plan 01-02 specified 384 (BAAI/bge-small-en-v1.5) as more memory-efficient for the 8GB VPS. Plan 01-01 had created the file with 1536 as a placeholder. Updated to 384 per this plan's explicit architectural decision.
- **Neo4j init database targeting:** Cypher constraints must run against the `neo4j` user database; APOC triggers must be installed from the `system` database. Split the entrypoint into two explicit cypher-shell calls with `-d neo4j` and `-d system` respectively (Option A from plan).
- **APOC trigger idempotency via drop-before-install:** `apoc.trigger.install` has no IF NOT EXISTS. Added `apoc.trigger.drop` before install — fails silently on first run (trigger doesn't exist yet), succeeds on subsequent runs.

## Deviations from Plan

None — plan executed exactly as written. The update to `scripts/init-qdrant.sh` was explicitly required by Plan 01-02 (Task 3 specifies 384 dimensions), resolving the 1536-dimension placeholder set in Plan 01-01.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. All storage initialization scripts run inside Docker containers with credentials from `.env.local`.

## Next Phase Readiness
- Storage layer fully initialized: run `docker compose --profile storage up -d` and all services start with correct schemas
- PostgreSQL has pipeline_run_log table ready for Phase 2 data ingestion pipelines to log their runs
- Neo4j has regime/time-period uniqueness constraints and RESEMBLES property enforcement active
- Qdrant has macro_embeddings, valuation_embeddings, structure_embeddings collections with stable aliases
- Phase 2 can begin data ingestion pipeline design immediately

## Self-Check: PASSED

Files verified:
- db/migrations/V1__initial_schema.sql: FOUND
- db/init/create-n8n-db.sql: FOUND
- neo4j/init/01_constraints.cypher: FOUND
- neo4j/init/02_apoc_triggers.cypher: FOUND
- scripts/init-qdrant.sh: FOUND
- .planning/phases/01-infrastructure-and-storage-foundation/01-02-SUMMARY.md: FOUND

Commits verified:
- 1e5208c: feat(01-02): create PostgreSQL Flyway migration and n8n database init
- f16124e: feat(01-02): create Neo4j constraints and APOC trigger init scripts
- 851c55f: feat(01-02): update Qdrant init script to 384-dimension FastEmbed model

---
*Phase: 01-infrastructure-and-storage-foundation*
*Completed: 2026-03-03*
