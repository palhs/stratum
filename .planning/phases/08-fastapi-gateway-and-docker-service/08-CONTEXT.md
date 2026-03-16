# Phase 8: FastAPI Gateway and Docker Service - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

FastAPI reasoning-engine service wrapping the Phase 7 LangGraph pipeline with: async report generation endpoint (POST /reports/generate → 202 + job_id), report retrieval (GET /reports/{id}), SSE progress streaming (GET /reports/stream/{id}), and health endpoint (GET /health). Packaged as a Docker service on the reasoning network with `profiles: ["reasoning"]`. No UI, no batch processing (Phase 9), no public-facing deployment.

</domain>

<decisions>
## Implementation Decisions

### API response format
- Minimal input: POST /reports/generate accepts `{"ticker": "VHM", "asset_type": "equity"}` — always generates both vi + en reports (no language parameter)
- No authentication in v2.0 — service is internal-only within Docker network
- GET /reports/{id} response format: Claude's discretion
- Error representation: Claude's discretion (standard HTTP codes expected)

### SSE streaming granularity
- SSE event detail level: Claude's discretion
- SSE scope (per-language vs job-level): Claude's discretion
- SSE access (always available vs opt-in): Claude's discretion
- On client disconnect: pipeline continues regardless — SSE is read-only observation; client can reconnect and poll /reports/{id} for final result

### Job lifecycle and cleanup
- Simple 4-state machine: pending → running → complete / failed
- Concurrent requests for same (ticker, asset_type): reject with 409 Conflict if pending/running job exists
- Failed jobs retryable: POST same params again is accepted (failed job doesn't block new submission)
- Job cleanup policy: Claude's discretion (v2.0 is manual usage, not high-volume)

### Docker service configuration
- Own Dockerfile in reasoning/ directory (not shared with sidecar — different dependencies)
- GEMINI_API_KEY via .env file (existing pattern — same file that has FRED_API_KEY and POSTGRES_PASSWORD)
- Expose port for dev: 8001:8000 (host:container) — allows curl/testing from host machine
- depends_on with health checks: postgres (healthy), neo4j (healthy), qdrant (healthy) — service waits for all stores
- mem_limit: 2GB (deferred from Phase 3 decision)
- profiles: ["reasoning"] (from roadmap)
- Network: reasoning (existing Docker network)

### Claude's Discretion
- GET /reports/{id} response shape (JSON only vs envelope with markdown)
- Error response format (standard HTTP codes + detail vs structured envelope)
- SSE event granularity, scope, and access pattern
- Job cleanup/retention policy
- FastAPI project structure within reasoning/
- Uvicorn configuration (workers, host, port)
- Health endpoint response shape and store connectivity checks

</decisions>

<specifics>
## Specific Ideas

- The 409 Conflict on duplicate jobs protects against wasted Gemini API calls — important since gemini-2.5-pro is more expensive than flash
- Port 8001 exposure is for dev convenience — the sidecar likely uses 8000, so reasoning gets 8001
- Pipeline continues on SSE disconnect because the background task (generate_report) is already committed — cancellation would add complexity with orphaned LangGraph checkpoint state
- Failed job retry via re-POST (not a retry endpoint) keeps the API surface minimal

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/pipeline/__init__.py`: `generate_report(ticker, asset_type)` — the pipeline entry point (async, returns `(vi_id, en_id)`)
- `reasoning/app/pipeline/graph.py`: `build_graph()`, `run_graph(state, thread_id, db_uri)` — StateGraph with AsyncPostgresSaver
- `reasoning/app/pipeline/prefetch.py`: `prefetch(ticker, asset_type)` — populates ReportState from all 3 stores
- `reasoning/app/pipeline/storage.py`: `write_report(report_output, asset_id, language, db_uri)` — INSERT into reports table
- `db/migrations/V7__report_jobs.sql`: report_jobs table already exists with job_id, status, asset_id, created_at, updated_at, report_id (nullable FK)
- `sidecar/Dockerfile`: Reference pattern for Python service Docker packaging

### Established Patterns
- SQLAlchemy Core (not ORM) for all PostgreSQL operations
- Pydantic v2 BaseModel for all data models
- `warnings: list[str] = []` propagation pattern
- `.env` file for secrets, docker-compose `env_file` or `${VAR}` interpolation
- `mem_limit` via legacy Docker key (not deploy.resources)
- Health checks on all existing services (postgres, neo4j, qdrant)

### Integration Points
- Pipeline entry: `generate_report(ticker, asset_type)` from `reasoning.app.pipeline`
- Report storage: `reports` table (report_id, asset_id, language, report_json, report_markdown)
- Job tracking: `report_jobs` table (job_id, status, asset_id, report_id FK)
- Docker network: `reasoning` — connects to postgres, neo4j, qdrant
- `langgraph` PostgreSQL schema with checkpoint tables (created during Phase 7 verification)
- `langgraph-checkpoint-postgres` and `psycopg[binary]` need to be in requirements.txt

</code_context>

<deferred>
## Deferred Ideas

- Live Gemini Vietnamese quality verification — deferred from Phase 7; will be naturally tested when the Docker service runs inside the network with real data
- `langgraph-checkpoint-postgres` and `psycopg[binary]` missing from requirements.txt — must be added in this phase

</deferred>

---

*Phase: 08-fastapi-gateway-and-docker-service*
*Context gathered: 2026-03-16*
