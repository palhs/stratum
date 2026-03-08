# Phase 3: Infrastructure Hardening and Database Migrations - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

All infrastructure prerequisites in place before any reasoning code is written — Flyway V6 and V7 migrations create the reports and report_jobs tables, all Docker services have explicit memory limits, VPS swap is configured, Neo4j JVM heap is set, GEMINI_API_KEY is available, and the LangGraph checkpoint schema is initialized in PostgreSQL. This phase touches docker-compose.yml, Flyway SQL, environment configuration, and a lightweight Python init script — no reasoning logic.

</domain>

<decisions>
## Implementation Decisions

### Reports table schema (V6 migration)
- Keep all historical reports — every pipeline run creates a new row, no upsert/overwrite
- One row per language — report_id + asset_id + language ('vi'/'en') as the model; each language version is a separate row
- Claude's discretion on whether to store both JSON and Markdown columns or JSON-only with on-demand rendering
- Claude's discretion on additional metadata columns (data_as_of, model_version, pipeline_duration_ms) — pick what downstream phases need

### Report jobs table schema (V7 migration)
- Simple state machine: pending → running → completed / failed (four states, no node-level tracking in the table)
- FK relationship: report_jobs.report_id references reports.report_id (nullable until job completes)
- Error column: TEXT column for error message/traceback when status='failed'
- One job per asset — batch runs (Phase 9) create 20 individual job rows, not a parent-child hierarchy

### Checkpoint lifecycle
- Checkpoints in stratum database but in a dedicated 'langgraph' schema (CREATE SCHEMA langgraph) — isolated from business tables
- Claude's discretion on init approach — either a one-shot Docker init service (consistent with flyway/neo4j-init/qdrant-init pattern) or reasoning-engine startup logic
- psycopg3 (async psycopg) in reasoning-engine, psycopg2 stays in data-sidecar — separate Docker containers, no conflict

### Memory limits and VPS configuration
- VPS is 16GB RAM — conservative limits are fine, leaves ~9GB headroom
- Keep requirements' specified limits: Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, reasoning-engine 2GB
- Add data-sidecar mem_limit: 512MB (not in original requirements but consistent with limiting all services)
- VPS swap: 4GB as specified (safety net even with 16GB RAM)
- Neo4j JVM heap already partially configured (512m initial, 1G max, 512m pagecache) — verify these values are appropriate for the 2GB container limit

### Claude's Discretion
- Reports table: whether to include report_markdown column or render on-demand from JSON
- Reports table: which metadata columns to include beyond the basics (report_id, asset_id, language, generated_at, report_json)
- Checkpoint init: one-shot Docker service vs reasoning-engine startup — pick what's most consistent with existing patterns
- Exact Neo4j JVM heap tuning within the 2GB container limit

</decisions>

<specifics>
## Specific Ideas

- Reports table must support "how did the assessment change over time" queries — keeping all versions, not just latest
- One row per language enables clean API querying: GET /reports?asset_id=X&language=vi
- Error column on report_jobs avoids digging through Docker logs for failed pipeline debugging
- One job per asset keeps the model simple — no batch orchestration complexity in the jobs table

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- Flyway V1-V5 migrations exist in `db/migrations/` — V6 and V7 follow the established naming convention
- Docker Compose already has one-shot init pattern: flyway, neo4j-init, qdrant-init — checkpoint init can follow same pattern
- `.env.example` exists — GEMINI_API_KEY needs to be added here

### Established Patterns
- Flyway naming: `V{N}__{description}.sql` — V6 and V7 continue this
- Docker init services: depends_on with service_healthy, no restart policy, one-shot execution
- Dual-network isolation: storage services on both networks, consumer services on one only
- Environment variables: loaded from `.env.local` (dev) / `.env.production` (VPS)

### Integration Points
- `docker-compose.yml`: add mem_limit to all existing services, add GEMINI_API_KEY to reasoning-engine environment
- `db/migrations/`: add V6__reports.sql and V7__report_jobs.sql
- `.env.example`: add GEMINI_API_KEY entry
- No reasoning-engine service exists yet — Phase 3 may need a placeholder service definition or defer to Phase 8

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-infrastructure-hardening-and-database-migrations*
*Context gathered: 2026-03-09*
