---
phase: 03-infrastructure-hardening-and-database-migrations
plan: "02"
subsystem: infra
tags: [docker, memory-limits, neo4j, jvm-tuning, gemini, environment]

# Dependency graph
requires:
  - phase: 03-infrastructure-hardening-and-database-migrations
    provides: dual-network docker-compose structure from 03-01

provides:
  - Docker memory ceilings on all 5 long-running services (postgres 512m, neo4j 2g, qdrant 1g, n8n 512m, data-sidecar 512m)
  - Neo4j JVM heap tuned with initial=max=1G eliminating GC pause spikes
  - GEMINI_API_KEY documented in .env.example for Phase 6+ reasoning pipeline
  - VPS swap setup instructions documented as host prerequisite comments

affects:
  - 06-reasoning-pipeline
  - 08-fastapi-service
  - 03-03

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mem_limit on service level (not deploy.resources) for non-Swarm deployments"
    - "Neo4j heap initial=max to prevent GC growth pauses"

key-files:
  created: []
  modified:
    - docker-compose.yml
    - .env.example

key-decisions:
  - "mem_limit via legacy key (not deploy.resources) — project uses non-Swarm Docker deployment"
  - "Neo4j initial heap set to 1G (matches max) to eliminate GC heap-growth pauses per Neo4j recommendation"
  - "Init services (flyway, neo4j-init, qdrant-init) excluded from mem_limit — one-shot services that exit immediately"
  - "GEMINI_API_KEY added to .env.example only in Phase 3; docker-compose env block deferred to Phase 8 when reasoning-engine service is added"
  - "VPS swap documented as comment block in docker-compose.yml — host-level operation not automatable from Docker"

patterns-established:
  - "Memory budget pattern: storage (postgres 512m, qdrant 1g, neo4j 2g) + ingestion (n8n 512m, sidecar 512m) = 4.5GB total ceiling"
  - "JVM tuning documented inline with budget arithmetic comments"

requirements-completed: [INFRA-03, INFRA-04, INFRA-05]

# Metrics
duration: 10min
completed: 2026-03-09
---

# Phase 3 Plan 02: Memory Limits and JVM Tuning Summary

**Docker mem_limit added to all 5 long-running services and Neo4j JVM heap tuned to initial=max=1G, with GEMINI_API_KEY and VPS swap instructions documented**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-09T00:00:00Z
- **Completed:** 2026-03-09T00:10:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added explicit `mem_limit` to all 5 long-running services: postgres (512m), neo4j (2g), qdrant (1g), n8n (512m), data-sidecar (512m) — prevents OOM kills under v2.0 reasoning workload
- Tuned Neo4j JVM heap: initial changed from 512m to 1G (matching max), eliminating GC heap-growth pauses; total JVM footprint 1.5GB comfortably within 2g container limit
- Added GEMINI_API_KEY to .env.example with SDK auto-detection note and key source URL (Phase 3+ prerequisite for reasoning pipeline)
- Documented VPS 4GB swap prerequisite (INFRA-04) as an idempotent comment block in docker-compose.yml with exact host commands

## Task Commits

Each task was committed atomically:

1. **Task 1: Add mem_limit to all Docker services and tune Neo4j JVM heap** - `5bdb6a3` (feat)
2. **Task 2: Add GEMINI_API_KEY to environment template** - `9207eab` (feat)

## Files Created/Modified

- `docker-compose.yml` - Added `mem_limit` to postgres/neo4j/qdrant/n8n/data-sidecar; changed Neo4j heap_initial from 512m to 1G; added VPS swap prerequisite comment block
- `.env.example` - Added GEMINI_API_KEY section between FRED and Telegram sections with documentation

## Decisions Made

- Used legacy `mem_limit` key (not `deploy.resources`) because this project uses non-Swarm Docker — `deploy.resources` is only honored by Docker Swarm
- Excluded one-shot init services (flyway, neo4j-init, qdrant-init) from `mem_limit` — they exit immediately after running and adding limits risks migration failures on large schemas
- GEMINI_API_KEY added to `.env.example` only in Phase 3; the docker-compose service environment block is deferred to Phase 8 when the reasoning-engine service is created
- VPS swap documented as host-level comment — cannot be configured from inside Docker containers

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**VPS host configuration required before production deployment:**

Run once on the VPS host (not inside Docker):
```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```
Verify: `free -h` should show 4G swap.

**Environment variable:**
- Add `GEMINI_API_KEY=<your-key>` to `.env.local` / `.env.production`
- Get key: https://aistudio.google.com/app/apikey

## Next Phase Readiness

- Memory ceilings enforced — stack will not OOM-kill under Phase 6 reasoning workload
- GEMINI_API_KEY documented — users know where to obtain it before Phase 6 work begins
- VPS swap instructions available in docker-compose.yml for operators
- Ready for 03-03 (next plan in Phase 3)

---
*Phase: 03-infrastructure-hardening-and-database-migrations*
*Completed: 2026-03-09*
