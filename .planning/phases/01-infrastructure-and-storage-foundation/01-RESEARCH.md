# Phase 1: Infrastructure and Storage Foundation - Research

**Researched:** 2026-03-03
**Domain:** Docker Compose, PostgreSQL, Neo4j, Qdrant, n8n, VPS provisioning
**Confidence:** HIGH (core findings verified via Context7 and official documentation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**VPS and Hosting**
- Own Ubuntu server, dedicated to Stratum
- 8GB RAM initially, scalable to 16GB if performance requires it
- IP-only access (no domain yet) — HTTP only, SSL deferred until domain is ready
- Docker and Docker Compose need to be installed as part of Phase 1 provisioning
- Deployment via git pull on VPS — no CI/CD pipeline for now
- No Nginx reverse proxy in Phase 1 — services expose ports directly on host

**Service Versions and Editions**
- Neo4j Community Edition (free, sufficient for single-user)
- PostgreSQL 16, Neo4j 5.x, Qdrant latest stable — all pinned to specific versions in compose file
- Supabase Cloud free tier for auth/user management (not self-hosted — saves ~6 containers worth of RAM)
- n8n self-hosted in Docker Compose stack (needs direct access to storage services)
- Named Docker volumes for all persistent data (not bind mounts)
- No container resource limits — let Docker manage dynamically on 8GB
- Secrets managed via .env files (gitignored), not Docker secrets

**Network Boundary Enforcement**
- Strict Docker network separation: two networks — `ingestion` (n8n + storage services) and `reasoning` (LangGraph/FastAPI + storage services)
- Storage services (PostgreSQL, Neo4j, Qdrant) attached to both networks — they are the only bridge
- n8n and LangGraph containers physically cannot reach each other
- Only admin UIs exposed on host: n8n UI (5678), Neo4j Browser (7474/7687), FastAPI (8000)
- Storage ports (PostgreSQL 5432, Qdrant 6333) internal only — not exposed on host
- Access control via built-in service auth (n8n auth, Neo4j auth) — no firewall rules

**Local Dev Workflow**
- Develop locally on Mac with Docker Compose, deploy to VPS via git pull
- Single `docker-compose.yml` with environment-specific `.env` files (`.env.local`, `.env.production`)
- Docker Compose profiles for selective service startup: `storage` (PG, Neo4j, Qdrant), `ingestion` (n8n), `reasoning` (LangGraph, FastAPI)
- Makefile for common operations: `make up`, `make down`, `make reset-db`, `make migrate`

### Claude's Discretion
- Exact PostgreSQL table naming conventions and migration tooling
- Neo4j constraint creation approach (Cypher scripts vs application-managed)
- Qdrant collection configuration (vector dimensions, distance metric)
- Docker Compose health check implementation details
- Makefile target specifics beyond the standard operations

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | All services run in Docker Compose on a self-hosted VPS | Docker Compose multi-service stack patterns, VPS provisioning scripts, health check patterns, named volumes, profile-based startup documented in Standard Stack and Architecture Patterns sections |
| INFRA-02 | Storage layer (PostgreSQL, Neo4j, Qdrant) is the hard boundary between n8n ingestion and LangGraph reasoning — they never communicate directly | Docker multi-network isolation pattern documented in Architecture Patterns; storage services attached to both networks, consumer services isolated from each other |
</phase_requirements>

---

## Summary

Phase 1 is a Docker Compose infrastructure problem. The technical challenge is not the individual services — each is well-documented with official Docker images — but the combination: correct multi-network topology, version pinning, health checks with proper dependency ordering, and schema initialization that will never need undoing.

The most significant finding is a **critical constraint**: Neo4j Community Edition does not support relationship property existence constraints. The success criterion "Neo4j schema enforces that RESEMBLES relationships carry `similarity_score`, `dimensions_matched`, and `period` properties" cannot be implemented at the database level in Community Edition. Only property uniqueness constraints are available in Community. Property existence, type, and key constraints are all Enterprise Edition only. This must be resolved via application-level validation (APOC triggers or write-time Cypher guards) — not database-level constraints.

PostgreSQL migration tooling choice falls to Claude's discretion. Flyway is the correct choice: SQL-first (no JVM needed for a separate Java runtime — the official Docker image handles it), single naming convention (`V1__description.sql`), and the community edition became fully free in 2025. It runs as a one-shot Docker Compose service that exits after migrations complete — no persistent process. n8n self-hosted with PostgreSQL as its metadata backend is well-documented via the official `n8n-hosting` repository.

**Primary recommendation:** Use Flyway for PostgreSQL migrations (one-shot Docker service), APOC Core triggers for Neo4j relationship property enforcement in Community Edition, Qdrant named collections with aliases for versioning, and a two-network Docker topology where storage services join both networks while n8n and LangGraph are strictly isolated.

---

## Standard Stack

### Core
| Service | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PostgreSQL | `postgres:16-alpine` | Primary time-series and relational storage | Locked decision; alpine tag reduces image size by ~60%; 16 is LTS |
| Neo4j | `neo4j:5.26.21` | Graph knowledge base (regime analogues, RESEMBLES relationships) | Locked: Community Edition, 5.x series; 5.26.21 is latest stable 5.x as of 2026-03 |
| Qdrant | `qdrant/qdrant:v1.15.3` | Vector similarity search | Locked: latest stable; official image; named volume required (POSIX compat issue with bind mounts on some hosts) |
| n8n | `n8nio/n8n` (pinned tag) | Ingestion workflow orchestration | Locked: self-hosted; PostgreSQL backend |
| Flyway | `flyway/flyway:latest` (pin to specific) | PostgreSQL schema migrations | Claude's discretion; SQL-first, Docker-native, free community edition |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| APOC Core | Neo4j procedures including triggers for relationship property validation | Required for Community Edition workaround for property existence constraints |
| Docker Compose Profiles | Selective service startup (`storage`, `ingestion`, `reasoning`) | All environments — allows running just DB for dev, full stack for integration |
| Makefile | Developer ergonomics (`make up`, `make migrate`, `make reset-db`) | All environments |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Flyway | golang-migrate | golang-migrate is lighter (no JVM), better for Go apps; Flyway is more mature, better documented for PostgreSQL, and its Docker image is the standard pattern when no app language is dominant |
| Flyway | Liquibase | Liquibase adds XML/YAML complexity with no benefit when targeting only PostgreSQL; Flyway's SQL-first approach matches this project's "write SQL, version it" philosophy |
| Flyway | `/docker-entrypoint-initdb.d` init scripts | Init scripts only run on empty databases; Flyway runs on every `docker compose up` and is idempotent — correct for migrations across environments |
| APOC triggers | Application-level guards only | Triggers enforce at write time from any client; application guards only protect one entry point |
| APOC triggers | Neo4j Enterprise constraints | Enterprise is not free; Community Edition is locked decision |

---

## Architecture Patterns

### Recommended Project Structure
```
stratum/
├── docker-compose.yml          # Single compose file, profiles control service groups
├── .env.local                  # Local dev overrides (gitignored)
├── .env.production             # VPS production values (gitignored)
├── .env.example                # Committed template with placeholder values
├── Makefile                    # Developer operations
├── db/
│   └── migrations/             # Flyway SQL files: V1__create_tables.sql, V2__...
├── neo4j/
│   └── init/                   # Cypher scripts for indexes, APOC trigger setup
│       ├── 01_constraints.cypher
│       └── 02_apoc_triggers.cypher
└── scripts/
    └── provision-vps.sh        # One-time Ubuntu/Docker install script
```

### Pattern 1: Docker Multi-Network Isolation

**What:** Two named Docker networks. Storage services join both. Consumer services are restricted to one.
**When to use:** Always — this is the INFRA-02 requirement.

```yaml
# Source: Docker Compose official docs + verified pattern
networks:
  ingestion:
    driver: bridge
  reasoning:
    driver: bridge

services:
  postgres:
    image: postgres:16-alpine
    networks:
      - ingestion    # n8n can reach postgres
      - reasoning    # LangGraph can reach postgres

  neo4j:
    image: neo4j:5.26.21
    networks:
      - ingestion
      - reasoning

  qdrant:
    image: qdrant/qdrant:v1.15.3
    networks:
      - ingestion
      - reasoning

  n8n:
    image: n8nio/n8n
    networks:
      - ingestion    # n8n ONLY — cannot reach reasoning services

  # LangGraph/FastAPI (Phase 6, placeholder):
  # fastapi:
  #   networks:
  #     - reasoning  # reasoning ONLY — cannot reach n8n
```

**Result:** n8n and LangGraph have no shared network — Docker prevents any communication between them. Storage services act as the only bridge, satisfying INFRA-02.

### Pattern 2: Health Checks with `service_healthy` Dependency

**What:** Services declare health checks; dependent services use `condition: service_healthy`.
**When to use:** Always — prevents startup race conditions that cause hard-to-diagnose failures.

```yaml
# Source: Docker Compose official docs (context7.com/docker/compose)
services:
  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  flyway:
    image: flyway/flyway:10
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./db/migrations:/flyway/sql
    environment:
      FLYWAY_URL: jdbc:postgresql://postgres:5432/${POSTGRES_DB}
      FLYWAY_USER: ${POSTGRES_USER}
      FLYWAY_PASSWORD: ${POSTGRES_PASSWORD}
    entrypoint: ["flyway", "migrate"]
    # Flyway exits after migration — not a persistent service

  n8n:
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
```

**Neo4j healthcheck pattern** (verified from Neo4j cluster tutorial):
```yaml
neo4j:
  image: neo4j:5.26.21
  healthcheck:
    test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider localhost:7474 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s  # Neo4j takes longer to boot
```

**Qdrant healthcheck:**
```yaml
qdrant:
  image: qdrant/qdrant:v1.15.3
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Pattern 3: Docker Compose Profiles for Selective Startup

**What:** Tag each service with a profile. Commands can start subsets.
**When to use:** Development (run only storage), integration testing (run full stack).

```yaml
# Source: Docker Compose official docs
services:
  postgres:
    profiles: ["storage", "ingestion", "reasoning"]
  neo4j:
    profiles: ["storage", "ingestion", "reasoning"]
  qdrant:
    profiles: ["storage", "ingestion", "reasoning"]
  n8n:
    profiles: ["ingestion"]
  # fastapi:
  #   profiles: ["reasoning"]
```

Usage:
```bash
docker compose --profile storage up -d        # Just databases
docker compose --profile ingestion up -d      # Databases + n8n
COMPOSE_PROFILES=storage,ingestion make up    # Via Makefile
```

### Pattern 4: Flyway Migration File Convention

**What:** SQL files named `V{version}__{description}.sql` in `db/migrations/`.
**When to use:** Every schema change — never modify existing migration files, always add new ones.

```sql
-- db/migrations/V1__create_pipeline_run_log.sql
-- Source: Flyway naming convention (verified)

CREATE TABLE pipeline_run_log (
    id            BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    run_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status        VARCHAR(50)  NOT NULL CHECK (status IN ('success', 'failure', 'partial')),
    rows_ingested INTEGER,
    error_message TEXT,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Every time-series table template: data_as_of + ingested_at required (DATA-07, DATA-08)
-- V2 and beyond will use this pattern.
```

### Pattern 5: Neo4j APOC Trigger for RESEMBLES Relationship Enforcement

**What:** Since Community Edition lacks relationship property existence constraints (Enterprise only), use APOC Core triggers to enforce that all RESEMBLES relationships carry `similarity_score`, `dimensions_matched`, and `period` before commit.
**When to use:** Neo4j initialization — run once via a Cypher init script.

```cypher
-- Source: APOC Core docs + Neo4j community patterns (verified workaround)
-- neo4j/init/02_apoc_triggers.cypher

// In Neo4j 5.x, triggers must be installed from the system database
// then enabled per database. Run this against the system database first:

// Step 1: Install trigger (run against system database)
CALL apoc.trigger.install(
  'neo4j',  -- target database name
  'enforce_resembles_properties',
  'UNWIND [rel IN $createdRelationships WHERE type(rel) = "RESEMBLES"] AS r
   CALL apoc.util.validate(
     r.similarity_score IS NULL OR r.dimensions_matched IS NULL OR r.period IS NULL,
     "RESEMBLES relationship missing required properties: similarity_score, dimensions_matched, period",
     []
   )
   RETURN null',
  {phase: 'before'}
);

// Step 2: Start the trigger (run against system database)
CALL apoc.trigger.start('neo4j', 'enforce_resembles_properties');
```

**Fallback if APOC trigger setup is complex:** Enforce in the write path via a Cypher guard pattern:
```cypher
// Enforced in application layer — every RESEMBLES relationship creation uses:
MERGE (a:Regime {id: $regime_a})-[r:RESEMBLES]->(b:Regime {id: $regime_b})
SET r.similarity_score = $similarity_score,
    r.dimensions_matched = $dimensions_matched,
    r.period = $period
// Never use bare CREATE (a)-[:RESEMBLES]->(b) without properties
```

### Pattern 6: Neo4j Node Uniqueness Constraints (Community Available)

**What:** Node uniqueness constraints ARE available in Community Edition. Create them for Regime and TimePeriod nodes.
**When to use:** Neo4j initialization.

```cypher
-- Source: Neo4j Cypher Manual 25 (context7: /websites/neo4j_cypher-manual_25)
CREATE CONSTRAINT regime_id_unique IF NOT EXISTS
FOR (r:Regime) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT time_period_id_unique IF NOT EXISTS
FOR (t:TimePeriod) REQUIRE t.id IS UNIQUE;
```

### Pattern 7: Qdrant Collection Setup with Alias Versioning

**What:** Create versioned collections (e.g., `macro_embeddings_v1`) and point a stable alias to the current version. Allows hot-swapping to a new collection without changing client code.

```python
# Source: Qdrant official docs (context7: /websites/qdrant_tech)
# Run via a Python init script or directly via HTTP at startup

from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://qdrant:6333", api_key=QDRANT_API_KEY)

# Create versioned collection
client.create_collection(
    collection_name="macro_embeddings_v1",
    vectors_config=models.VectorParams(
        size=1536,          # Claude's discretion — match embedding model dimensions
        distance=models.Distance.COSINE
    )
)

# Create stable alias pointing to versioned collection
client.update_collection_aliases(
    change_aliases_operations=[
        models.CreateAliasOperation(
            create_alias=models.CreateAlias(
                collection_name="macro_embeddings_v1",
                alias_name="macro_embeddings"
            )
        )
    ]
)
```

**HTTP equivalent (usable in a shell init script):**
```bash
# Source: Qdrant official docs
curl -X PUT http://localhost:6333/collections/macro_embeddings_v1 \
  -H 'Content-Type: application/json' \
  -H "api-key: ${QDRANT_API_KEY}" \
  --data-raw '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    }
  }'

curl -X POST http://localhost:6333/collections/aliases \
  -H 'Content-Type: application/json' \
  -H "api-key: ${QDRANT_API_KEY}" \
  --data-raw '{
    "actions": [{"create_alias": {"collection_name": "macro_embeddings_v1", "alias_name": "macro_embeddings"}}]
  }'
```

### Pattern 8: n8n with PostgreSQL Backend

**What:** n8n stores workflows, credentials, and execution history in PostgreSQL (not SQLite). Critical: also persist `/home/node/.n8n` for the encryption key.

```yaml
# Source: n8n official hosting repo (github.com/n8n-io/n8n-hosting)
n8n:
  image: n8nio/n8n:1.x.x  # pin specific version
  environment:
    DB_TYPE: postgresdb
    DB_POSTGRESDB_HOST: postgres
    DB_POSTGRESDB_PORT: 5432
    DB_POSTGRESDB_DATABASE: ${N8N_DB_NAME}
    DB_POSTGRESDB_USER: ${N8N_DB_USER}
    DB_POSTGRESDB_PASSWORD: ${N8N_DB_PASSWORD}
    N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}  # Required — generate once, never change
    GENERIC_TIMEZONE: Asia/Ho_Chi_Minh
    N8N_DIAGNOSTICS_ENABLED: "false"
  volumes:
    - n8n_data:/home/node/.n8n    # CRITICAL: persists encryption key
  ports:
    - "5678:5678"
  networks:
    - ingestion
```

### Anti-Patterns to Avoid

- **Bind mounts for Qdrant storage:** Use named volumes. Qdrant requires POSIX-compatible file systems — bind mounts on macOS (APFS) can cause "Incompatible file system" errors. Source: Qdrant docs.
- **`latest` image tags in compose file:** Pin every image to a specific version tag. `latest` changes silently and can break startups.
- **`depends_on` without `condition: service_healthy`:** Default `depends_on` only waits for container start, not service readiness. PostgreSQL containers accept connections ~10s after the process starts — using `service_healthy` with `pg_isready` prevents Flyway from failing on first run.
- **Exposing PostgreSQL or Qdrant ports on host:** The locked decision explicitly prohibits this. Storage ports stay internal to Docker networks.
- **Writing RESEMBLES relationships without all three properties:** The requirement is that no bare relationships exist. Without Enterprise constraints, this must be a team discipline enforced by convention + APOC trigger + code review.
- **Installing Docker via `apt install docker.io`:** This installs Ubuntu's unofficial, outdated package. Use Docker's official APT repository (`docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-compose-plugin`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema versioning and migration ordering | Custom SQL runner scripts | Flyway | Flyway handles idempotency, ordering, and tracking via `flyway_schema_history` table; custom runners miss concurrent migration protection |
| PostgreSQL readiness check | `sleep 10` in Makefile | `pg_isready` in Docker healthcheck | `sleep` is a race condition on slow hardware; `pg_isready` checks actual TCP + auth readiness |
| Relationship property enforcement | Custom write wrappers only | APOC Core triggers | Triggers fire regardless of which client writes; custom wrappers protect only one entry point |
| Qdrant collection versioning | Manual rename scripts | Alias API | Alias switch is atomic — no downtime, no concurrent request errors |
| VPS Docker installation | Custom apt script | Docker's official install script (or APT repo) | Official script handles GPG keys, repo setup, version pinning correctly |

**Key insight:** Infrastructure setup failures are almost always timing issues (startup order) or version drift issues (unpinned images). Both are solved by Compose health checks and pinned version tags, not by more code.

---

## Common Pitfalls

### Pitfall 1: Neo4j APOC Trigger API Changed in Neo4j 5.x

**What goes wrong:** `apoc.trigger.add()` is the old API (Neo4j 4.x). In Neo4j 5.x, the API is `apoc.trigger.install()` and must be called from the **system database**, not the user database.
**Why it happens:** Most tutorials and Stack Overflow answers document the 4.x API.
**How to avoid:** Use `apoc.trigger.install('neo4j', ...)` (first arg is the target database name) from the system database context. Then `apoc.trigger.start()` to activate it.
**Warning signs:** Error message "There is no procedure with the name `apoc.trigger.add`" or trigger silently not firing.

### Pitfall 2: Flyway Exits with Error on Clean DB (Wrong URL)

**What goes wrong:** Flyway can't connect to PostgreSQL even though PostgreSQL is healthy.
**Why it happens:** JDBC URL uses `localhost` instead of the service name. Inside Docker Compose, services reference each other by service name, not `localhost`.
**How to avoid:** Use `FLYWAY_URL=jdbc:postgresql://postgres:5432/${POSTGRES_DB}` — the hostname is the Compose service name (`postgres`), not `localhost`.
**Warning signs:** `Connection refused` in Flyway logs despite PostgreSQL container showing as healthy.

### Pitfall 3: n8n Encryption Key Loss

**What goes wrong:** After a container restart or volume wipe, n8n cannot decrypt stored credentials. All workflow connections are broken.
**Why it happens:** n8n auto-generates an encryption key on first start and stores it in `/home/node/.n8n/config`. If the volume is not persisted, it regenerates a new key on the next start.
**How to avoid:** (1) Mount a named volume at `/home/node/.n8n`. (2) Set `N8N_ENCRYPTION_KEY` as an explicit environment variable from `.env` — this overrides the auto-generated key and makes it persistent across volume wipes.
**Warning signs:** n8n shows "Error: Could not decrypt credentials" on workflow test.

### Pitfall 4: Docker UFW/iptables Bypass

**What goes wrong:** Exposing a container port with `ports: "5432:5432"` bypasses UFW firewall rules on Ubuntu. Any service binding to host port 5432 is reachable from the internet, even if UFW blocks 5432.
**Why it happens:** Docker modifies iptables directly, bypassing UFW chains.
**How to avoid:** The locked decision correctly does NOT expose storage ports on the host. Only expose ports that are intentionally public (n8n UI on 5678, Neo4j Browser on 7474/7687). Do not expose PostgreSQL 5432 or Qdrant 6333 in `ports` mapping.
**Warning signs:** `nmap` from external host shows storage ports open.

### Pitfall 5: Named Volume Data Directory Mismatch for PostgreSQL

**What goes wrong:** Mounting a volume to `/var/lib/postgresql` instead of `/var/lib/postgresql/data` results in data not persisting across container recreation.
**Why it happens:** The Dockerfile declares a volume at the `/data` subdirectory. A mount at the parent directory shadows but does not replace the declared volume.
**How to avoid:** Always mount to `/var/lib/postgresql/data` exactly.
**Warning signs:** After `docker compose down && docker compose up`, all tables are gone despite a named volume being present.

### Pitfall 6: Neo4j Memory on 8GB VPS

**What goes wrong:** Neo4j's default heap and page cache settings can consume 4-6GB on startup, leaving insufficient RAM for PostgreSQL, Qdrant, and n8n.
**Why it happens:** Neo4j's auto-tuning uses a percentage of available system RAM.
**How to avoid:** Explicitly cap Neo4j memory via environment variables:
```yaml
environment:
  NEO4J_server_memory_heap_initial__size: "512m"
  NEO4J_server_memory_heap_max__size: "1G"
  NEO4J_server_memory_pagecache_size: "512m"
```
**Warning signs:** Other containers OOM-killed shortly after Neo4j starts.

### Pitfall 7: Qdrant Bind Mount on macOS

**What goes wrong:** `./qdrant_data:/qdrant/storage` bind mount fails with "Incompatible file system" error on macOS.
**Why it happens:** Qdrant requires a POSIX-compatible file system. macOS APFS (even via Docker Desktop's VM layer) can trigger this.
**How to avoid:** Use named Docker volumes (`qdrant_storage:/qdrant/storage`) instead of bind mounts for Qdrant.
**Warning signs:** Qdrant container exits immediately with file system error in logs.

---

## Code Examples

Verified patterns from official sources:

### Full docker-compose.yml Structure

```yaml
# Source: Docker Compose official docs + n8n-hosting + Qdrant docs + Neo4j Operations Manual
name: stratum

networks:
  ingestion:
    driver: bridge
  reasoning:
    driver: bridge

volumes:
  postgres_data:
  neo4j_data:
  neo4j_logs:
  qdrant_storage:
  n8n_data:

services:
  # ─── STORAGE (both networks) ──────────────────────────────────
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - ingestion
      - reasoning
    profiles: ["storage", "ingestion", "reasoning"]
    # NOTE: No ports mapping — storage is internal only

  neo4j:
    image: neo4j:5.26.21
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: "512m"
      NEO4J_server_memory_heap_max__size: "1G"
      NEO4J_server_memory_pagecache_size: "512m"
      NEO4J_apoc_trigger_enabled: "true"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    ports:
      - "7474:7474"   # Neo4j Browser (admin UI — expose on host)
      - "7687:7687"   # Bolt protocol (admin UI — expose on host)
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider localhost:7474 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    networks:
      - ingestion
      - reasoning
    profiles: ["storage", "ingestion", "reasoning"]

  qdrant:
    image: qdrant/qdrant:v1.15.3
    restart: unless-stopped
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - ingestion
      - reasoning
    profiles: ["storage", "ingestion", "reasoning"]
    # NOTE: No ports mapping — internal only

  # ─── MIGRATIONS (one-shot, exits after completion) ────────────
  flyway:
    image: flyway/flyway:10
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./db/migrations:/flyway/sql
    environment:
      FLYWAY_URL: jdbc:postgresql://postgres:5432/${POSTGRES_DB}
      FLYWAY_USER: ${POSTGRES_USER}
      FLYWAY_PASSWORD: ${POSTGRES_PASSWORD}
    entrypoint: ["flyway", "migrate"]
    networks:
      - ingestion
    profiles: ["storage", "ingestion", "reasoning"]

  # ─── INGESTION (ingestion network only) ───────────────────────
  n8n:
    image: n8nio/n8n:1.78.0  # pin specific version
    restart: unless-stopped
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${N8N_DB_NAME}
      DB_POSTGRESDB_USER: ${N8N_DB_USER}
      DB_POSTGRESDB_PASSWORD: ${N8N_DB_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      GENERIC_TIMEZONE: Asia/Ho_Chi_Minh
      N8N_DIAGNOSTICS_ENABLED: "false"
    volumes:
      - n8n_data:/home/node/.n8n
    ports:
      - "5678:5678"   # n8n UI (expose on host)
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - ingestion     # n8n ONLY — cannot reach reasoning network
    profiles: ["ingestion"]
```

### PostgreSQL Migration: V1 Template

```sql
-- db/migrations/V1__initial_schema.sql
-- Source: Flyway naming convention

-- Required on every time-series table (DATA-07)
-- data_as_of: when the data was valid in the real world
-- ingested_at: when it was written to this database

CREATE TABLE pipeline_run_log (
    id             BIGSERIAL    PRIMARY KEY,
    pipeline_name  VARCHAR(255) NOT NULL,
    run_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    status         VARCHAR(50)  NOT NULL CHECK (status IN ('success', 'failure', 'partial')),
    rows_ingested  INTEGER,
    error_message  TEXT,
    data_as_of     TIMESTAMPTZ  NOT NULL,
    ingested_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

### VPS Provisioning Command Sequence

```bash
# Source: Docker official install docs for Ubuntu
# scripts/provision-vps.sh

# 1. Remove unofficial packages
sudo apt-get remove -y docker docker-engine docker.io containerd runc docker-compose

# 2. Install Docker's official APT packages
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 3. Add current user to docker group (avoids sudo for docker commands)
sudo usermod -aG docker $USER

# 4. Verify
docker compose version
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (standalone binary) | `docker compose` (plugin, V2) | 2022 | Use `docker compose` not `docker-compose`; compose plugin is now bundled with Docker Engine |
| Neo4j `apoc.trigger.add()` | `apoc.trigger.install()` from system db | Neo4j 5.0 (2022) | Must target system database; old API removed |
| Neo4j image `neo4j:latest` | `neo4j:5.26.21` then new `2026.x` versioning | 2025 | Neo4j moved to calendar versioning in 2025; `5.x` series remains stable; `latest` now points to 2026.x |
| Flyway Teams tier | Flyway Community (free) only | May 2025 | Teams tier discontinued; Community now fully free with enhanced capabilities |
| n8n SQLite backend | n8n PostgreSQL backend | n8n v1.0 (2023) | MySQL/MariaDB deprecated in v1.0; PostgreSQL is the only external DB option |

**Deprecated/outdated:**
- `docker-compose` V1 standalone binary: replaced by `docker compose` plugin. Commands are identical but the binary name changed.
- `apoc.trigger.add()`: removed in Neo4j 5.x; use `apoc.trigger.install()` targeting the system database.

---

## Open Questions

1. **Qdrant collection vector dimensions**
   - What we know: Qdrant requires specifying vector dimensions at collection creation time; it cannot be changed later without recreating the collection.
   - What's unclear: The embedding model for Phase 1 is not decided (Phase 1 only sets up the infrastructure; actual embeddings happen in later phases). This is Claude's discretion.
   - Recommendation: Create a placeholder collection with 1536 dimensions (matches OpenAI `text-embedding-3-small` and `text-embedding-ada-002`). If the model changes, recreate the collection and update the alias — the alias pattern exists precisely for this.

2. **Neo4j APOC trigger system database access in Docker Compose**
   - What we know: APOC 5.x triggers require `apoc.trigger.install()` called against the system database. The Neo4j Docker image starts with a single user database (`neo4j`) and the system database.
   - What's unclear: The exact mechanism for running multi-database Cypher init scripts against both system and user databases from Docker Compose startup.
   - Recommendation: Use a one-shot init container (similar to Flyway) that runs `cypher-shell -a neo4j://neo4j:7687 -u neo4j -p $PASSWORD -d system -f 01_triggers.cypher` after Neo4j healthcheck passes. This is the documented approach for neo4j init automation.

3. **n8n version pinning**
   - What we know: n8n releases frequently; pinning a specific version tag is required by the locked decision.
   - What's unclear: The exact latest stable n8n version as of Phase 1 build time.
   - Recommendation: At implementation time, check `hub.docker.com/r/n8nio/n8n/tags` for the latest stable tag. Use that specific version. Do not use `latest`.

4. **PostgreSQL separate database for n8n vs Stratum data**
   - What we know: n8n needs its own schema; Stratum time-series data goes in PostgreSQL too.
   - What's unclear: Whether they should be separate databases on the same PostgreSQL instance or separate schemas in the same database.
   - Recommendation: Separate databases within the same PostgreSQL container (`stratum` and `n8n_meta`). Use `POSTGRES_MULTIPLE_DATABASES` init script or two separate user accounts. This keeps n8n metadata and Stratum data completely isolated without running two PostgreSQL instances.

---

## Sources

### Primary (HIGH confidence)
- `/websites/neo4j_cypher-manual_25` (Context7) — constraints availability by edition, CREATE CONSTRAINT syntax
- `/websites/neo4j_operations-manual_current` (Context7) — Neo4j Docker Compose setup, environment variable mapping
- `/websites/qdrant_tech` (Context7) — collection creation, alias API, Docker volumes, API key configuration
- `/docker/compose` (Context7) — networks, profiles, health checks, depends_on
- [Neo4j Cypher Manual — Constraints](https://neo4j.com/docs/cypher-manual/current/constraints/) — confirmed Enterprise-only constraint types
- [APOC Core Installation Docs](https://neo4j.com/docs/apoc/current/installation/) — NEO4J_PLUGINS env var, Docker setup
- [Docker Install on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) — official APT install method
- [n8n Docker Docs](https://docs.n8n.io/hosting/installation/docker/) — PostgreSQL env vars, encryption key handling
- [Qdrant Configuration Docs](https://qdrant.tech/documentation/guides/configuration) — QDRANT__SERVICE__API_KEY, named volumes

### Secondary (MEDIUM confidence)
- WebSearch: "Neo4j Community Edition relationship property existence constraint 2025" → confirmed Enterprise-only from multiple sources including official docs
- WebSearch: "APOC Core Neo4j Community Edition 5.x Docker 2025" → verified `apoc.trigger.install()` API change, `NEO4J_PLUGINS` env var
- WebSearch: "n8n Docker Compose self-hosted PostgreSQL 2025" → confirmed `n8n-hosting` GitHub repo patterns
- WebSearch: "PostgreSQL migration tooling Flyway vs Liquibase vs golang-migrate 2025" → Flyway recommendation supported by multiple sources

### Tertiary (LOW confidence)
- Neo4j 5.x memory tuning values for 8GB RAM — from community patterns, not official sizing documentation. Validate against actual VPS memory usage during Phase 1.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all service choices are locked decisions; versions verified from Docker Hub tags
- Architecture: HIGH — Docker multi-network pattern verified from official Compose docs; health check patterns verified
- Neo4j constraint limitation: HIGH — confirmed by both Context7 (official Cypher Manual) and WebSearch from official Neo4j docs
- Pitfalls: MEDIUM — Docker UFW bypass and Neo4j memory patterns from community sources; others from official docs
- APOC trigger API (5.x): MEDIUM — verified from APOC docs that `apoc.trigger.install` is required but the exact system-db init scripting in Docker Compose is a LOW-confidence area that needs testing

**Research date:** 2026-03-03
**Valid until:** 2026-06-03 (90 days — Neo4j, Qdrant, n8n release frequently; re-verify version pins before implementation)
