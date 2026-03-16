---
phase: 08-fastapi-gateway-and-docker-service
plan: 01
subsystem: api
tags: [fastapi, uvicorn, docker, sse-starlette, langgraph-checkpoint-postgres, psycopg, sqlalchemy, neo4j, qdrant]

# Dependency graph
requires:
  - phase: 07-graph-assembly-and-end-to-end-report-generation
    provides: generate_report() async entry point and pipeline infrastructure that reasoning-engine wraps
provides:
  - FastAPI app skeleton (app/main.py) with lifespan and health router
  - Lifespan context manager (app/dependencies.py) initializing db_engine, neo4j_driver, qdrant_client, db_uri, job_queues on app.state
  - GET /health endpoint returning {"status": "ok", "service": "reasoning-engine"}
  - reasoning/Dockerfile following sidecar pattern with 60s start-period
  - reasoning-engine service in docker-compose.yml with mem_limit 2g, profiles [reasoning], port 8001:8000
  - Updated requirements.txt with fastapi, uvicorn, sse-starlette, httpx, langgraph-checkpoint-postgres, psycopg[binary]
affects:
  - 08-02 (report generation endpoint — imports app.dependencies.lifespan and app.state resources)
  - 08-03 (SSE streaming — uses app.state.job_queues established here)

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.115.0
    - uvicorn>=0.30.0
    - sse-starlette>=2.1.0
    - httpx>=0.27.0
    - langgraph-checkpoint-postgres
    - psycopg[binary]
  patterns:
    - FastAPI lifespan asynccontextmanager for resource initialization (not deprecated @app.on_event)
    - Isolated TestClient fixture with minimal app (no lifespan) for health endpoint unit tests
    - app.state for shared resources (db_engine, neo4j_driver, qdrant_client, db_uri, job_queues)

key-files:
  created:
    - reasoning/app/main.py
    - reasoning/app/dependencies.py
    - reasoning/app/routers/__init__.py
    - reasoning/app/routers/health.py
    - reasoning/tests/api/__init__.py
    - reasoning/tests/api/test_health.py
    - reasoning/Dockerfile
  modified:
    - reasoning/requirements.txt
    - docker-compose.yml

key-decisions:
  - "lifespan asynccontextmanager pattern used (not deprecated @app.on_event('startup')) — FastAPI best practice"
  - "Test app for health endpoint is minimal FastAPI with no lifespan — avoids real DB connections; health router has no app.state dependencies"
  - "Dockerfile start-period=60s (vs sidecar 30s) — reasoning-engine loads heavier dependencies (LlamaIndex, LangGraph, Neo4j)"
  - "GEMINI_API_KEY env var in reasoning-engine service — deferred from Phase 3, now delivered with service creation"
  - "psycopg[binary] and langgraph-checkpoint-postgres added — required for AsyncPostgresSaver used in run_graph()"

patterns-established:
  - "Health router has no app.state deps — enables isolated unit testing without DB connections"
  - "app.state.job_queues: dict[int, asyncio.Queue] = {} initialized at startup — ready for SSE in Plan 03"

requirements-completed: [SRVC-04, SRVC-05]

# Metrics
duration: ~15min
completed: 2026-03-16
---

# Phase 8 Plan 01: FastAPI App Skeleton, Health Endpoint, Dockerfile, and Docker Compose Service Summary

**FastAPI reasoning-engine service skeleton with GET /health, lifespan-based resource initialization (db_engine, neo4j_driver, qdrant_client, job_queues on app.state), Dockerfile, and docker-compose.yml service definition with mem_limit 2g on reasoning network**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-16T09:00:00Z
- **Completed:** 2026-03-16T09:15:41Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- FastAPI app skeleton with lifespan context manager initializing all shared resources (db_engine, neo4j_driver, qdrant_client, db_uri, job_queues) on app.state — foundation for Plans 02 and 03
- GET /health endpoint tested with 2 passing unit tests using isolated TestClient (no DB connections)
- Docker packaging: reasoning/Dockerfile following sidecar pattern with 60s start-period; docker-compose.yml reasoning-engine service with all locked config (mem_limit 2g, profiles [reasoning], port 8001:8000, GEMINI_API_KEY env)

## Task Commits

Each task was committed atomically:

1. **Task 1: FastAPI app skeleton with lifespan, health endpoint, and tests** - `ff1ea97` (feat)
2. **Task 2: Dockerfile, requirements.txt updates, and docker-compose.yml service definition** - `47264b3` (feat)

## Files Created/Modified

- `reasoning/app/main.py` - FastAPI app with title, lifespan, and health router registration
- `reasoning/app/dependencies.py` - lifespan asynccontextmanager: creates db_engine, neo4j_driver, qdrant_client, db_uri, job_queues on app.state; disposes on shutdown
- `reasoning/app/routers/__init__.py` - empty package init
- `reasoning/app/routers/health.py` - GET /health → HealthResponse(status="ok", service="reasoning-engine") with Pydantic response model
- `reasoning/tests/api/__init__.py` - empty package init
- `reasoning/tests/api/test_health.py` - 2 tests: test_health_returns_200 and test_health_response_shape; minimal test app with no lifespan
- `reasoning/Dockerfile` - python:3.12-slim, curl healthcheck --start-period=60s, uvicorn CMD
- `reasoning/requirements.txt` - added fastapi, uvicorn, sse-starlette, httpx, langgraph-checkpoint-postgres, psycopg[binary]
- `docker-compose.yml` - added reasoning-engine service: mem_limit 2g, profiles [reasoning], port 8001:8000, depends_on postgres/neo4j/qdrant healthy, full environment block including GEMINI_API_KEY

## Decisions Made

- Used `lifespan` asynccontextmanager (not deprecated `@app.on_event`) — FastAPI best practice for resource lifecycle
- Test isolation via minimal FastAPI app (no lifespan) in test_health.py — health endpoint has no app.state deps, so no mock/override needed
- `start-period=60s` in Dockerfile and docker-compose healthcheck — reasoning-engine loads heavier ML dependencies than sidecar (30s)
- `GEMINI_API_KEY` delivered in this plan's docker-compose service — deferred from Phase 3 when the reasoning-engine service didn't exist yet

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing `ModuleNotFoundError: No module named 'reasoning'` in nodes/pipeline/freshness tests — these use `reasoning.app.*` import paths and are a pre-existing issue in the venv unrelated to this plan's changes. API tests (tests/api/) pass correctly.

## User Setup Required

None - no external service configuration required. GEMINI_API_KEY must be in .env (existing project pattern already established).

## Next Phase Readiness

- FastAPI app skeleton is ready for Plan 02 (POST /reports/generate endpoint) — app.state has all resources initialized
- app.state.job_queues dict is initialized and ready for Plan 03 (SSE streaming)
- reasoning-engine Docker service definition is complete — Plans 02/03 only need to add routers

---
*Phase: 08-fastapi-gateway-and-docker-service*
*Completed: 2026-03-16*
