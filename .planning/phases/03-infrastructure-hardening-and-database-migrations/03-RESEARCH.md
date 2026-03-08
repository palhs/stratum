# Phase 3: Infrastructure Hardening and Database Migrations - Research

**Researched:** 2026-03-09
**Domain:** PostgreSQL migrations (Flyway), Docker memory limits, VPS swap, Neo4j JVM tuning, Gemini API key, LangGraph PostgreSQL checkpointing
**Confidence:** HIGH (all critical areas verified against official docs or Context7)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Reports table schema (V6 migration)**
- Keep all historical reports — every pipeline run creates a new row, no upsert/overwrite
- One row per language — report_id + asset_id + language ('vi'/'en') as the model; each language version is a separate row
- Claude's discretion on whether to store both JSON and Markdown columns or JSON-only with on-demand rendering
- Claude's discretion on additional metadata columns (data_as_of, model_version, pipeline_duration_ms) — pick what downstream phases need

**Report jobs table schema (V7 migration)**
- Simple state machine: pending → running → completed / failed (four states, no node-level tracking in the table)
- FK relationship: report_jobs.report_id references reports.report_id (nullable until job completes)
- Error column: TEXT column for error message/traceback when status='failed'
- One job per asset — batch runs (Phase 9) create 20 individual job rows, not a parent-child hierarchy

**Checkpoint lifecycle**
- Checkpoints in stratum database but in a dedicated 'langgraph' schema (CREATE SCHEMA langgraph) — isolated from business tables
- Claude's discretion on init approach — either a one-shot Docker init service (consistent with flyway/neo4j-init/qdrant-init pattern) or reasoning-engine startup logic
- psycopg3 (async psycopg) in reasoning-engine, psycopg2 stays in data-sidecar — separate Docker containers, no conflict

**Memory limits and VPS configuration**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Flyway V6 migration creates `reports` table for storing generated report JSON and metadata | SQL schema design patterns; existing V1-V5 conventions; timestamp convention established in V1 |
| INFRA-02 | Flyway V7 migration creates `report_jobs` table for tracking pipeline run status | State machine modeling in SQL; FK to reports; existing pipeline_run_log precedent in V1 |
| INFRA-03 | Docker Compose has explicit `mem_limit` on all services (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, reasoning-engine 2GB) | Docker Compose `mem_limit` syntax verified; current compose file has no limits — all must be added |
| INFRA-04 | VPS swap configured at 4GB and Neo4j JVM heap explicitly set | Swap file creation steps verified; Neo4j env var naming convention verified against official docs |
| INFRA-05 | `GEMINI_API_KEY` added to environment configuration | google-genai SDK env var behavior verified; .env.example pattern established |
| INFRA-06 | LangGraph checkpoint database schema initialized (psycopg3-based AsyncPostgresSaver) | AsyncPostgresSaver.setup() behavior verified; schema isolation constraint clarified |
</phase_requirements>

---

## Summary

Phase 3 is a pure infrastructure phase: SQL schema, Docker configuration, VPS configuration, and a one-time init script. No reasoning logic is written. All six requirements are independently deliverable and can be planned as separate tasks.

The critical technical finding is about LangGraph checkpoint schema isolation. The user decision specifies checkpoints in a dedicated `langgraph` schema (not `public`). However, the Python `AsyncPostgresSaver` does NOT natively support a custom schema parameter — it always creates tables in the `public` schema. The workaround is to run the DDL manually (creating tables with `langgraph.checkpoints`, `langgraph.checkpoint_blobs`, etc.) before calling `.setup()` — but `.setup()` will still target `public`. The cleaner solution is to run the init as a one-shot Docker service that executes raw SQL against the `langgraph` schema, bypassing `AsyncPostgresSaver.setup()` entirely. This aligns with the existing `flyway`, `neo4j-init`, and `qdrant-init` one-shot service pattern.

Neo4j JVM tuning requires matching heap + pagecache to stay within the 2GB container limit with OS overhead. The rule is: `heap + pagecache < container_mem_limit - 300MB OS overhead`. Current config (512m initial, 1G max, 512m pagecache = 1.5GB at max) is within the 2GB limit. The recommendation is to raise initial heap to 1G to match max (eliminates GC pause from heap growth) and keep pagecache at 512m, for a total JVM footprint of 1.5GB within the 2GB container.

**Primary recommendation:** Implement each of the six INFRA requirements as independent tasks; the only non-trivial technical decision is checkpoint schema isolation — implement as raw SQL in a one-shot Docker init service using `psycopg3` directly, mirroring the `qdrant-init` pattern, rather than relying on `AsyncPostgresSaver.setup()`.

---

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Flyway | 10 (already in use) | Versioned SQL migrations for PostgreSQL | Already deployed; V1-V5 exist; naming convention established |
| psycopg[binary,pool] | 3.x (psycopg3) | Async PostgreSQL driver for checkpoint init | Required by LangGraph's AsyncPostgresSaver |
| langgraph-checkpoint-postgres | latest (3.x) | Provides checkpoint schema and saver class | Official LangGraph persistence layer |
| google-genai | latest | Gemini API client (replaces deprecated google-generativeai) | Official Google SDK as of 2025 |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| Docker Compose `mem_limit` | Hard memory ceiling per container | Specified directly under service in compose file (legacy-style `mem_limit` key still works in current Compose) |
| `fallocate` / `swapon` / `/etc/fstab` | VPS swap configuration | One-time VPS provisioning; must be run on the host, NOT inside Docker |
| `neo4j-admin server memory-recommendation` | JVM heap/pagecache sizing guidance | Run inside the neo4j container to validate settings |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw SQL for checkpoint tables | `AsyncPostgresSaver.setup()` | `.setup()` creates tables in `public` schema only; raw SQL lets us target `langgraph` schema per locked decision |
| One-shot Docker service for checkpoint init | reasoning-engine startup logic | Docker service pattern is more consistent with existing qdrant-init/neo4j-init; avoids coupling init to service startup failures |
| `mem_limit` (legacy key) | `deploy.resources.limits.memory` (v3 syntax) | Both work in current Docker Compose; `mem_limit` is simpler for non-Swarm deployments and is already the established style in this project |

**Installation (reasoning-engine future Dockerfile):**
```bash
pip install psycopg[binary,pool] langgraph-checkpoint-postgres google-genai
```

---

## Architecture Patterns

### Recommended Project Structure for This Phase
```
db/
├── migrations/
│   ├── V1__initial_schema.sql          # exists
│   ├── V2__stock_data.sql              # exists
│   ├── V3__gold_data.sql               # exists
│   ├── V4__fred_indicators.sql         # exists
│   ├── V5__structure_markers.sql       # exists
│   ├── V6__reports.sql                 # Phase 3 — NEW
│   └── V7__report_jobs.sql             # Phase 3 — NEW
scripts/
└── init-langgraph-schema.py            # Phase 3 — NEW (one-shot checkpoint schema init)
docker-compose.yml                      # Phase 3 — add mem_limit to all services, add langgraph-init service
.env.example                            # Phase 3 — add GEMINI_API_KEY entry
```

### Pattern 1: Flyway Versioned Migration Naming
**What:** Files named `V{N}__{Description}.sql` — double underscore separator, version ascending.
**When to use:** Every schema change. V6 and V7 continue V1-V5 convention.
**Example:**
```sql
-- V6__reports.sql
-- V7__report_jobs.sql
```
Flyway in this project runs via docker-compose one-shot service: `entrypoint: ["flyway", "migrate"]`. It automatically applies all unapplied versioned migrations in order.

### Pattern 2: Existing Timestamp Convention (MUST follow)
**What:** Every table in this project includes `data_as_of TIMESTAMPTZ NOT NULL` and `ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
**When to use:** All time-series tables. The `reports` table is not time-series in the traditional sense but tracks generative output over time — `generated_at` serves the same role as `data_as_of`.
**Key question:** For `reports`, `generated_at` is when the report was produced (the "data_as_of" equivalent). Include `data_as_of` to indicate the freshness of the source data used in report generation (downstream phases use this for DATA WARNING).

### Pattern 3: One-Shot Docker Init Service
**What:** A Docker service with no `restart` policy that runs a script once, exits cleanly, and depends on the target service being healthy.
**When to use:** LangGraph checkpoint schema initialization.
**Existing examples in this project:**
```yaml
# flyway: runs flyway migrate, exits
# neo4j-init: runs cypher-shell, exits
# qdrant-init: runs init-qdrant.sh curl script, exits
```
**Proposed langgraph-init pattern:**
```yaml
langgraph-init:
  image: python:3.12-slim
  depends_on:
    postgres:
      condition: service_healthy
  volumes:
    - ./scripts/init-langgraph-schema.py:/init-langgraph-schema.py:ro
  entrypoint: >
    bash -c "
      pip install psycopg[binary] --quiet &&
      python /init-langgraph-schema.py
    "
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
  networks:
    - reasoning
  profiles: ["storage", "reasoning"]
  # No restart policy — one-shot init
```

### Pattern 4: Docker Compose Memory Limits
**What:** `mem_limit` key directly under service definition (not under `deploy.resources`).
**When to use:** All services in this project (non-Swarm deployment).
**Example:**
```yaml
neo4j:
  image: neo4j:5.26.21
  mem_limit: 2g
  # existing config continues...

qdrant:
  image: qdrant/qdrant:v1.15.3
  mem_limit: 1g

postgres:
  image: postgres:16-alpine
  mem_limit: 512m

n8n:
  image: n8nio/n8n:2.10.2
  mem_limit: 512m

data-sidecar:
  build: ./sidecar
  mem_limit: 512m

# reasoning-engine: mem_limit: 2g (when added in Phase 8)
```
Unit suffixes: `b`, `k`, `m`, `g` (lowercase). `2g` = 2GB.

### Pattern 5: Neo4j JVM Heap Configuration
**What:** Neo4j uses Docker environment variables that map directly to `neo4j.conf` keys (double-underscore replaces dot and hyphen).
**Existing config in docker-compose.yml:**
```yaml
NEO4J_server_memory_heap_initial__size: "512m"  # currently 512m — should be raised to 1G
NEO4J_server_memory_heap_max__size: "1G"
NEO4J_server_memory_pagecache_size: "512m"
```
**Recommended adjustment** (within 2GB container limit):
```yaml
NEO4J_server_memory_heap_initial__size: "1G"    # match max to prevent GC heap-growth pauses
NEO4J_server_memory_heap_max__size: "1G"
NEO4J_server_memory_pagecache_size: "512m"
# Total JVM: 1.5GB — leaves ~500MB for OS overhead within 2g mem_limit
```
**Rule:** Neo4j official docs state initial and max heap should be equal to avoid garbage collection pauses from heap growth.

### Anti-Patterns to Avoid
- **Using `AsyncPostgresSaver.setup()` for schema isolation:** `.setup()` creates tables in `public`, not a named schema. Do not rely on it for the `langgraph` schema isolation requirement.
- **Missing `autocommit=True` in psycopg3 connections:** The checkpoint saver requires `autocommit=True` and `row_factory=dict_row` when passing a manual connection — omitting either causes silent failures or TypeErrors.
- **Heap initial < heap max in Neo4j:** Causes garbage collector to grow heap dynamically, producing GC pause spikes. Set initial = max.
- **Swap in `/etc/fstab` without the entry:** Swap survives the current session but is lost on reboot without the fstab entry.
- **Using `google-generativeai` (legacy):** Deprecated as of 2025. Use `google-genai` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Checkpoint schema DDL | Custom Python ORM models for checkpoints | Raw SQL DDL with `langgraph` schema prefix | The checkpoint table structure is version-managed by LangGraph; hand-rolling it risks schema drift when library updates |
| DB migration sequencing | Custom migration runner | Flyway (already in use) | Handles checksums, version locking, re-run protection; V1-V5 already proven |
| Gemini API client | Manual `httpx` requests to Gemini REST API | `google-genai` SDK | Handles auth, retry, streaming, model version routing |
| Container memory enforcement | `ulimit` syscalls, cgroup config | Docker `mem_limit` | Compose translates `mem_limit` directly to cgroup v2 `memory.max` — zero custom code |

**Key insight:** Every infrastructure primitive in this phase has a purpose-built mechanism. The only "code" in this phase is the checkpoint schema init script and the Flyway SQL files — everything else is configuration.

---

## Common Pitfalls

### Pitfall 1: LangGraph Schema Isolation — `AsyncPostgresSaver.setup()` Cannot Target a Custom Schema
**What goes wrong:** The user decision requires checkpoint tables in the `langgraph` schema (not `public`). `AsyncPostgresSaver.setup()` always creates tables in `public`. If `.setup()` is called at runtime (e.g., on reasoning-engine startup), checkpoint tables end up in `public` and cannot be easily moved.
**Why it happens:** The Python `AsyncPostgresSaver` has no `schema` parameter (the JS version does). This is a known open documentation and feature gap (GitHub issue #465 in langchain-ai/docs).
**How to avoid:** Implement checkpoint schema init as a one-shot Docker service that runs raw SQL DDL against the `langgraph` schema. Do NOT call `AsyncPostgresSaver.setup()` at runtime. The schema tables must exist before `AsyncPostgresSaver` is used, and they must be in `langgraph`, not `public`.
**Warning signs:** If you run `\dn` in psql and see checkpoint tables in `public` instead of `langgraph`, the init ran incorrectly.

### Pitfall 2: Flyway Checksum Failure on Existing Migrations
**What goes wrong:** If any V1-V5 migration file is modified (even whitespace), Flyway will fail with a checksum mismatch error and refuse to run V6/V7.
**Why it happens:** Flyway hashes every applied migration and compares on each run.
**How to avoid:** Never modify V1-V5 files. Only add new V6 and V7 files.
**Warning signs:** `Flyway: ERROR: Found non-empty schema(s)... but no schema history table` or `checksum mismatch` in flyway container logs.

### Pitfall 3: Neo4j OOM Kill Inside 2GB Container
**What goes wrong:** Neo4j's heap grows beyond `heap_max_size` plus OS memory, causing the container to be OOM-killed by the kernel even with `mem_limit: 2g`.
**Why it happens:** `mem_limit` is a hard ceiling. Heap + pagecache + JVM overhead + OS must fit within 2GB.
**How to avoid:** heap (1G) + pagecache (512m) = 1.5GB total JVM footprint, leaving ~500MB for OS. This fits within 2GB safely. Do NOT raise pagecache further without recalculating.
**Warning signs:** `docker inspect <neo4j-container>` shows `OOMKilled: true` in State.

### Pitfall 4: VPS Swap Not Persistent After Reboot
**What goes wrong:** Swap is active after provisioning (`free -h` shows 4G) but disappears after VPS reboot.
**Why it happens:** `swapon /swapfile` activates swap for the current session only. Without the fstab entry, it is not re-enabled on boot.
**How to avoid:** Always add `/swapfile none swap sw 0 0` to `/etc/fstab` immediately after creating the swap file.
**Warning signs:** After a reboot, `free -h` shows `Swap: 0`.

### Pitfall 5: GEMINI_API_KEY Not Passed to Future reasoning-engine Container
**What goes wrong:** `.env.example` is updated with `GEMINI_API_KEY`, but the reasoning-engine service in `docker-compose.yml` does not include `GEMINI_API_KEY` in its `environment` block, so the SDK cannot auto-detect it.
**Why it happens:** Docker Compose requires explicit environment variable forwarding per service; env vars are not automatically inherited by containers.
**How to avoid:** Add `GEMINI_API_KEY: ${GEMINI_API_KEY}` to the reasoning-engine service environment block when the service is defined (Phase 8). For Phase 3, the `.env.example` addition is sufficient as the service does not yet exist.
**Warning signs:** `genai.Client()` raises `google.auth.exceptions.DefaultCredentialsError` at reasoning-engine startup.

### Pitfall 6: psycopg3 `prepare_threshold` Causing DuplicatePreparedStatement
**What goes wrong:** When the checkpoint init script reconnects or retries, psycopg3 raises `psycopg.errors.DuplicatePreparedStatement: prepared statement "_pg3_0" already exists`.
**Why it happens:** psycopg3 auto-prepares statements after a threshold number of executions; on reconnect, the same statement name is re-prepared while the server still has it cached.
**How to avoid:** In the init script, set `connection_kwargs={"prepare_threshold": 0}` to disable auto-prepare, or use `from_conn_string` which handles this correctly.
**Warning signs:** `psycopg.errors.InvalidSqlStatementName` or `DuplicatePreparedStatement` in init script output.

---

## Code Examples

Verified patterns from official sources:

### V6 reports Migration (SQL Pattern)
```sql
-- V6__reports.sql
-- Follows project convention: TIMESTAMPTZ for all timestamp columns
-- One row per (asset_id, language, pipeline_run) — all history retained
CREATE TABLE reports (
    report_id           BIGSERIAL        PRIMARY KEY,
    asset_id            VARCHAR(20)      NOT NULL,
    language            VARCHAR(5)       NOT NULL CHECK (language IN ('vi', 'en')),
    report_json         JSONB            NOT NULL,
    report_markdown     TEXT,                          -- Claude's discretion: include for Phase 7 render speed
    data_as_of          TIMESTAMPTZ      NOT NULL,     -- freshness of source data used
    model_version       VARCHAR(100),                  -- e.g., 'gemini-2.5-flash'
    pipeline_duration_ms INTEGER,                      -- wall-clock time for the pipeline run
    generated_at        TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    ingested_at         TIMESTAMPTZ      NOT NULL DEFAULT NOW()  -- timestamp convention
);

CREATE INDEX idx_reports_asset_language ON reports (asset_id, language, generated_at DESC);
CREATE INDEX idx_reports_asset_id ON reports (asset_id, generated_at DESC);
```

### V7 report_jobs Migration (SQL Pattern)
```sql
-- V7__report_jobs.sql
CREATE TABLE report_jobs (
    job_id      BIGSERIAL        PRIMARY KEY,
    asset_id    VARCHAR(20)      NOT NULL,
    status      VARCHAR(20)      NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed'))
                                 DEFAULT 'pending',
    report_id   BIGINT           REFERENCES reports(report_id),  -- nullable until job completes
    error       TEXT,            -- error message/traceback when status='failed'
    created_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ      NOT NULL DEFAULT NOW()  -- timestamp convention
);

CREATE INDEX idx_report_jobs_asset_status ON report_jobs (asset_id, status);
CREATE INDEX idx_report_jobs_status ON report_jobs (status, created_at DESC);
```

### LangGraph Checkpoint Schema Init Script (Raw SQL via psycopg3)
```python
# scripts/init-langgraph-schema.py
# One-shot script — run as Docker init service
# Creates checkpoint tables in 'langgraph' schema (not 'public')
# Does NOT use AsyncPostgresSaver.setup() (targets public schema only)

import asyncio
import os
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]

SCHEMA_DDL = """
CREATE SCHEMA IF NOT EXISTS langgraph;

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_migrations (
    v INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoints (
    thread_id           TEXT NOT NULL,
    checkpoint_ns       TEXT NOT NULL DEFAULT '',
    checkpoint_id       TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type                TEXT,
    checkpoint          JSONB NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_blobs (
    thread_id      TEXT   NOT NULL,
    checkpoint_ns  TEXT   NOT NULL DEFAULT '',
    channel        TEXT   NOT NULL,
    version        TEXT   NOT NULL,
    type           TEXT   NOT NULL,
    blob           BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_writes (
    thread_id      TEXT    NOT NULL,
    checkpoint_ns  TEXT    NOT NULL DEFAULT '',
    checkpoint_id  TEXT    NOT NULL,
    task_id        TEXT    NOT NULL,
    idx            INTEGER NOT NULL,
    channel        TEXT    NOT NULL,
    type           TEXT,
    blob           BYTEA   NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
"""

async def main():
    async with await psycopg.AsyncConnection.connect(
        DATABASE_URL, autocommit=True
    ) as conn:
        await conn.execute(SCHEMA_DDL)
        print("LangGraph checkpoint schema initialized in 'langgraph' schema.")

asyncio.run(main())
```
**Source:** Schema structure derived from LangGraph checkpoint-postgres source code and blog.lordpatil.com internals post. Table structure matches what `AsyncPostgresSaver.setup()` creates in `public`, transposed to the `langgraph` schema.

### AsyncPostgresSaver Usage (for Phase 6+ reasoning-engine reference)
```python
# Source: Context7 /langchain-ai/langgraph, README.md
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Connection string must point to tables in 'langgraph' schema
# Since AsyncPostgresSaver doesn't support schema param, use search_path
DB_URI = f"postgresql://user:pass@postgres:5432/stratum?options=-csearch_path%3Dlanggraph"

async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # DO NOT call checkpointer.setup() — tables already created by init-langgraph-schema.py
    graph = builder.compile(checkpointer=checkpointer)
```
**Note:** The `search_path` approach (`?options=-csearch_path=langgraph`) instructs psycopg to resolve unqualified table names in the `langgraph` schema first, making `AsyncPostgresSaver` operate on the correct schema without modification. This must be validated in Phase 6.

### VPS Swap Configuration (idempotent script fragment)
```bash
# Run on VPS host — NOT inside Docker
# Check if 4GB swap already exists
if [ "$(free -g | awk '/^Swap:/{print $2}')" -ge "4" ]; then
  echo "Swap already configured (4GB+). Skipping."
  exit 0
fi

sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

echo "Swap configured. Verify with: free -h"
```

### GEMINI_API_KEY .env.example Addition
```bash
# Google Gemini API (Phase 3+ — reasoning-engine service)
# Required for bilingual report generation.
# Get key: https://aistudio.google.com/app/apikey
# The google-genai SDK auto-detects GEMINI_API_KEY from environment.
GEMINI_API_KEY=your-gemini-api-key-here
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` Python SDK | `google-genai` Python SDK | 2025 | Old SDK deprecated; new SDK is unified for all Google AI models |
| `deploy.resources.limits.memory` (Compose v3 Swarm syntax) | `mem_limit` top-level key (Compose standalone) | Pre-2022 | Both work; `mem_limit` is simpler for non-Swarm and is the established style here |
| `PostgresSaver` (sync) | `AsyncPostgresSaver` (async) | LangGraph 0.2+ | reasoning-engine uses async Python; sync saver blocks event loop |

**Deprecated/outdated:**
- `google-generativeai`: Deprecated as of 2025; the `google-genai` package is the unified replacement
- `langchain_postgres.checkpoint.PostgresSaver`: Separate from `langgraph-checkpoint-postgres`; do not confuse the two

---

## Open Questions

1. **LangGraph `search_path` workaround validation**
   - What we know: Passing `?options=-csearch_path=langgraph` in the DB URI should cause psycopg3 to resolve unqualified table names in the `langgraph` schema
   - What's unclear: Whether `AsyncPostgresSaver.from_conn_string()` faithfully passes connection options through, or whether it strips/overrides them
   - Recommendation: The init script (raw DDL) is Phase 3 work and will succeed regardless. The `search_path` workaround is Phase 6 work. Flag it as a validation task in Phase 6: confirm `AsyncPostgresSaver` correctly reads from `langgraph.checkpoints` tables.

2. **LangGraph checkpoint table schema version**
   - What we know: `AsyncPostgresSaver.setup()` creates `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and `checkpoint_migrations` tables
   - What's unclear: Whether the exact DDL in the init script above matches what `setup()` would create (schema version may have changed in langgraph-checkpoint-postgres 3.x)
   - Recommendation: In the langgraph-init service, also install `langgraph-checkpoint-postgres` and use it to generate the DDL, or pin the library version and cross-reference its source code before writing the SQL.

3. **reasoning-engine service placeholder in docker-compose.yml**
   - What we know: Phase 3 adds `GEMINI_API_KEY` to env config; Phase 8 adds the reasoning-engine service
   - What's unclear: CONTEXT.md notes "No reasoning-engine service exists yet — Phase 3 may need a placeholder service definition or defer to Phase 8"
   - Recommendation: Defer to Phase 8. The `langgraph-init` service can be added to the `reasoning` profile without requiring the reasoning-engine service to exist. Add `GEMINI_API_KEY` to `.env.example` only in Phase 3.

---

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json`. Skipping this section.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/langchain-ai/langgraph` — AsyncPostgresSaver usage, `.setup()` behavior, `autocommit` requirement, table names (checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations)
- Context7 `/websites/langchain_oss_python_langgraph` — Async LangGraph PostgreSQL checkpointing patterns, production setup guidance
- Context7 `/flyway/flyway` — SQL migration naming convention (`V{N}__{Description}.sql`), Docker environment variable configuration
- [Neo4j Operations Manual — Memory configuration](https://neo4j.com/docs/operations-manual/current/performance/memory-configuration/) — heap/pagecache tuning, docker env var naming, initial=max recommendation
- [Google AI for Developers — Gemini API Quickstart](https://ai.google.dev/gemini-api/docs/quickstart) — `GEMINI_API_KEY` auto-detection, `google-genai` SDK installation
- Existing project codebase — V1-V5 migration conventions, docker-compose.yml service patterns, one-shot init service pattern (flyway/neo4j-init/qdrant-init)

### Secondary (MEDIUM confidence)
- [langgraph-checkpoint-postgres PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) — version 3.0.2, package install command
- [Linuxize — Create a Linux Swap File](https://linuxize.com/post/create-a-linux-swap-file/) — swap creation steps, fstab entry, swappiness tuning
- [blog.lordpatil.com — Internals of LangGraph Postgres Checkpointer](https://blog.lordpatil.com/posts/langgraph-postgres-checkpointer/) — four checkpoint tables confirmed with purposes

### Tertiary (LOW confidence — flag for validation)
- [GitHub Issue #465 langchain-ai/docs — Postgres Schema for LangGraph Checkpointer](https://github.com/langchain-ai/docs/issues/465) — confirms Python `AsyncPostgresSaver` has no `schema` parameter; custom schema is not natively supported
- WebSearch result on `search_path` URL parameter workaround — not verified against official docs; needs validation in Phase 6

---

## Metadata

**Confidence breakdown:**
- INFRA-01 (V6 reports migration): HIGH — SQL pattern clear from V1-V5; schema locked by user decisions
- INFRA-02 (V7 report_jobs migration): HIGH — state machine SQL is straightforward; FK pattern well-understood
- INFRA-03 (Docker mem_limit): HIGH — `mem_limit` key verified; syntax confirmed via Docker docs
- INFRA-04 (VPS swap + Neo4j JVM): HIGH — swap commands verified; Neo4j env var naming confirmed via official docs
- INFRA-05 (GEMINI_API_KEY): HIGH — google-genai SDK env var auto-detection confirmed via official Google docs
- INFRA-06 (LangGraph checkpoint schema): MEDIUM — `.setup()` behavior confirmed; schema isolation workaround (raw DDL + search_path) is well-reasoned but `search_path` URL param behavior with AsyncPostgresSaver needs Phase 6 validation

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable infrastructure domain; LangGraph checkpoint library may update)
