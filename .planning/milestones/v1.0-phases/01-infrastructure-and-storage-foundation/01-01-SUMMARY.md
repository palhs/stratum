---
phase: 01-infrastructure-and-storage-foundation
plan: 01
subsystem: infrastructure
tags: [docker-compose, networking, postgres, neo4j, qdrant, n8n, flyway, makefile, devops]
dependency_graph:
  requires: []
  provides:
    - docker-compose stack with all storage services
    - dual-network isolation (ingestion/reasoning)
    - environment template (.env.example)
    - developer Makefile
    - VPS provisioning script
  affects:
    - 01-02: schema initialization runs inside this compose stack
    - Phase 2: n8n ingestion workflows use this compose environment
    - Phase 6: FastAPI/LangGraph will join the reasoning network
tech_stack:
  added:
    - postgres:16-alpine
    - neo4j:5.26.21 (Community Edition)
    - qdrant/qdrant:v1.15.3
    - n8nio/n8n:1.78.0
    - flyway/flyway:10
    - curlimages/curl:latest (qdrant-init)
  patterns:
    - Docker multi-network isolation (ingestion + reasoning bridge networks)
    - Docker Compose profiles for selective service startup
    - Named volumes only (no bind mounts for persistent data)
    - Health checks with service_healthy conditions on all depends_on
    - One-shot init containers for Flyway and Qdrant initialization
key_files:
  created:
    - docker-compose.yml
    - .env.example
    - .env.local
    - Makefile
    - scripts/provision-vps.sh
    - scripts/init-qdrant.sh
    - .gitignore
  modified: []
decisions:
  - "Named volumes for all persistent data — no bind mounts (avoids Qdrant APFS/POSIX issue on macOS, and is locked decision)"
  - "n8n on ingestion network only — no reasoning network membership (INFRA-02 enforcement)"
  - "postgres and qdrant ports NOT exposed on host — only Neo4j Browser (7474/7687) and n8n UI (5678) exposed"
  - "NEO4J_server_memory_pagecache_size capped at 512m to prevent OOM on 8GB VPS"
  - "N8N_ENCRYPTION_KEY as explicit env var — overrides auto-generated key, persists across volume wipes"
  - "Qdrant collections initialized with 1536 dimensions (OpenAI text-embedding-3-small compatible) with alias versioning"
  - "scripts/init-qdrant.sh creates 3 versioned collections (macro, valuation, structure) with stable aliases"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_created: 7
  files_modified: 0
  completed_date: "2026-03-03"
---

# Phase 1 Plan 1: Docker Compose Infrastructure Stack Summary

**One-liner:** Complete Docker Compose stack with 7 services, dual ingestion/reasoning network isolation, Docker Compose profiles for selective startup, and VPS provisioning via Docker's official APT repository.

## What Was Built

### docker-compose.yml

The core infrastructure file implementing the INFRA-01 and INFRA-02 requirements:

- **7 services** across 3 tiers: storage (postgres, neo4j, qdrant), migration/init (flyway, neo4j-init, qdrant-init), and ingestion (n8n)
- **2 Docker bridge networks**: `ingestion` and `reasoning` — storage services join both; n8n joins ingestion only
- **5 named volumes**: postgres_data, neo4j_data, neo4j_logs, qdrant_storage, n8n_data
- **Health checks** on postgres (`pg_isready`), neo4j (`wget localhost:7474`), qdrant (`curl /healthz`)
- **Docker Compose profiles** enable `storage`, `ingestion`, and `reasoning` selective startup
- **No host port exposure** for postgres (5432) or qdrant (6333) — locked security decision

Network topology enforces INFRA-02: n8n and the future LangGraph/FastAPI containers share no network. Storage services are the only bridge.

### Environment files

- `.env.example` — committed template with all 9 required variables and generation hints
- `.env.local` — gitignored local dev values including a generated N8N_ENCRYPTION_KEY
- `.gitignore` — excludes `.env.local`, `.env.production`, `.env.staging`, `.env`; `.env.example` committed

### Makefile

Developer ergonomics for 9 targets: `help` (default), `up`, `up-storage`, `up-ingestion`, `down`, `reset-db`, `migrate`, `logs`, `ps`, `health`.

The `reset-db` target includes a 5-second countdown warning before destroying volumes.

### scripts/provision-vps.sh

One-time Ubuntu VPS Docker installation using Docker's official APT repository. Uses `set -euo pipefail`, removes the unofficial `docker.io` package, installs `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`, adds user to docker group. Executable (`chmod +x`).

### scripts/init-qdrant.sh

One-shot Qdrant collection initialization script run by the `qdrant-init` compose service. Creates 3 versioned collections (`macro_embeddings_v1`, `valuation_embeddings_v1`, `structure_embeddings_v1`) with 1536 dimensions (Cosine distance) and stable aliases (`macro_embeddings`, etc.) for zero-downtime collection versioning.

## Deviations from Plan

### Auto-added Functionality (Rule 2)

**1. [Rule 2 - Missing] Added scripts/init-qdrant.sh**
- **Found during:** Task 1 execution
- **Issue:** docker-compose.yml references `./scripts/init-qdrant.sh:ro` in qdrant-init service volume mount, but the plan only described the service without specifying script creation as a separate task
- **Fix:** Created `scripts/init-qdrant.sh` with full Qdrant collection initialization — 3 versioned collections matching the alias-versioning pattern from RESEARCH.md (Pattern 7)
- **Files modified:** `scripts/init-qdrant.sh` (new)
- **Commit:** 98d0875

## Success Criteria Verification

| Criterion | Status |
|-----------|--------|
| 7 Docker Compose services defined | PASS |
| 2 networks (ingestion, reasoning) | PASS |
| Storage services on both networks | PASS |
| n8n on ingestion only (INFRA-02) | PASS |
| postgres/qdrant ports NOT exposed on host | PASS |
| neo4j 7474/7687 + n8n 5678 exposed on host | PASS |
| Health checks on postgres, neo4j, qdrant | PASS |
| Docker Compose profiles: storage, ingestion, reasoning | PASS |
| Named volumes only (no bind mounts) | PASS |
| .env.example with all required variables | PASS |
| .env.local gitignored, .env.example committed | PASS |
| Makefile with up, down, reset-db, migrate, help | PASS |
| VPS provisioning script uses docker-ce (not docker.io) | PASS |
| set -euo pipefail in provision script | PASS |

## Self-Check: PASSED

Files verified:
- docker-compose.yml: EXISTS
- .env.example: EXISTS
- Makefile: EXISTS
- scripts/provision-vps.sh: EXISTS
- scripts/init-qdrant.sh: EXISTS
- .gitignore: EXISTS

Commits verified:
- 4697420: feat(01-01): create Docker Compose stack
- 98d0875: feat(01-01): create environment files, Makefile, provisioning script, and .gitignore
