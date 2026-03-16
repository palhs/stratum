# Phase 8: FastAPI Gateway and Docker Service - Research

**Researched:** 2026-03-16
**Domain:** FastAPI async service, SSE streaming, BackgroundTasks, Docker Compose profiles
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**API response format:**
- Minimal input: POST /reports/generate accepts `{"ticker": "VHM", "asset_type": "equity"}` — always generates both vi + en reports (no language parameter)
- No authentication in v2.0 — service is internal-only within Docker network
- GET /reports/{id} response format: Claude's discretion
- Error representation: Claude's discretion (standard HTTP codes expected)

**SSE streaming granularity:**
- SSE event detail level: Claude's discretion
- SSE scope (per-language vs job-level): Claude's discretion
- SSE access (always available vs opt-in): Claude's discretion
- On client disconnect: pipeline continues regardless — SSE is read-only observation; client can reconnect and poll /reports/{id} for final result

**Job lifecycle and cleanup:**
- Simple 4-state machine: pending → running → complete / failed
- Concurrent requests for same (ticker, asset_type): reject with 409 Conflict if pending/running job exists
- Failed jobs retryable: POST same params again is accepted (failed job doesn't block new submission)
- Job cleanup policy: Claude's discretion (v2.0 is manual usage, not high-volume)

**Docker service configuration:**
- Own Dockerfile in reasoning/ directory (not shared with sidecar — different dependencies)
- GEMINI_API_KEY via .env file (existing pattern — same file that has FRED_API_KEY and POSTGRES_PASSWORD)
- Expose port for dev: 8001:8000 (host:container)
- depends_on with health checks: postgres (healthy), neo4j (healthy), qdrant (healthy)
- mem_limit: 2GB
- profiles: ["reasoning"]
- Network: reasoning (existing Docker network)

### Claude's Discretion
- GET /reports/{id} response shape (JSON only vs envelope with markdown)
- Error response format (standard HTTP codes + detail vs structured envelope)
- SSE event granularity, scope, and access pattern
- Job cleanup/retention policy
- FastAPI project structure within reasoning/
- Uvicorn configuration (workers, host, port)
- Health endpoint response shape and store connectivity checks

### Deferred Ideas (OUT OF SCOPE)
- Live Gemini Vietnamese quality verification — deferred from Phase 7; will be naturally tested when the Docker service runs inside the network with real data
- `langgraph-checkpoint-postgres` and `psycopg[binary]` missing from requirements.txt — must be added in this phase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRVC-01 | FastAPI reasoning-engine service with `POST /reports/generate` endpoint (BackgroundTask) | BackgroundTasks.add_task() pattern confirmed via Context7; 202 response with JSONResponse(status_code=202); job created in report_jobs table before background task starts |
| SRVC-02 | `GET /reports/{id}` endpoint returns completed report | SQLAlchemy Core query on reports table; returns 200 + report JSON when complete, 202 + status when pending/running, 404 when not found |
| SRVC-03 | `GET /reports/stream/{id}` SSE endpoint for pipeline progress | sse-starlette EventSourceResponse confirmed; asyncio.Queue bridges background task → SSE generator; client disconnect via request.is_disconnected() — pipeline continues |
| SRVC-04 | `GET /health` endpoint for service monitoring | Existing sidecar pattern: HealthResponse(status, service) Pydantic model; can extend with store connectivity checks |
| SRVC-05 | reasoning-engine Docker service in docker-compose.yml on reasoning network with profiles: ["reasoning"] | Existing docker-compose.yml pattern: build context, mem_limit, depends_on with condition: service_healthy, ports 8001:8000, env_file .env |
</phase_requirements>

---

## Summary

Phase 8 wraps the Phase 7 LangGraph pipeline (`generate_report()`) in a FastAPI HTTP service. The core challenge is the async gap: `generate_report()` takes minutes to run, but `POST /reports/generate` must return HTTP 202 immediately. FastAPI's `BackgroundTasks.add_task()` handles this correctly — the background task executes after the response is sent and does not block the event loop for the client.

The second challenge is SSE streaming (SRVC-03). Since `generate_report()` is a single coroutine (not node-by-node observable), progress events must be emitted using a shared `asyncio.Queue` — the background task writes node-transition events to the queue, and the SSE generator reads from it. The `sse-starlette` library provides `EventSourceResponse` which is the standard FastAPI SSE solution: it handles `text/event-stream` media type, keepalive pings, and client disconnect detection.

The Docker integration is straightforward: follow the sidecar Dockerfile pattern (python:3.12-slim, curl for healthcheck, uvicorn CMD), update `docker-compose.yml` with the same patterns already used for data-sidecar but on the `reasoning` network with `profiles: ["reasoning"]` and `mem_limit: 2g`. Two critical requirements.txt additions before building: `langgraph-checkpoint-postgres` and `psycopg[binary]` (noted in CONTEXT.md deferred section).

**Primary recommendation:** Use FastAPI `BackgroundTasks` for async generation (not Celery, not asyncio.create_task directly). Use `sse-starlette` `EventSourceResponse` for SSE. Share state between background task and SSE via in-memory `asyncio.Queue` stored on `app.state`. Persist job state in the existing `report_jobs` PostgreSQL table.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115.0 | HTTP framework | Already used in sidecar; same version pinned |
| uvicorn | >=0.30.0 | ASGI server | Already used in sidecar; standard FastAPI runner |
| sse-starlette | >=2.1.0 | SSE EventSourceResponse | Production-grade SSE for FastAPI/Starlette; handles keepalive, disconnect, multi-loop |
| pydantic v2 | >=2.0.0 | Request/response models | Already project standard; BaseModel for all data models |
| sqlalchemy | >=2.0.0 | PostgreSQL job tracking + report retrieval | Already project standard; Core (not ORM) |
| psycopg2-binary | >=2.9.9 | Sync SQLAlchemy connection | Already in requirements.txt |
| psycopg[binary] | (latest) | Async psycopg3 for AsyncPostgresSaver | MUST ADD — missing from requirements.txt per CONTEXT.md |
| langgraph-checkpoint-postgres | (latest) | AsyncPostgresSaver for LangGraph | MUST ADD — missing from requirements.txt per CONTEXT.md |
| python-dotenv | >=1.0.0 | Load .env in local dev | Already in requirements.txt |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.27.0 | Async HTTP client for tests | TestClient uses it under the hood; already in sidecar |
| pytest-asyncio | >=0.24.0 | Async test support | Already in requirements.txt |
| anyio | (via fastapi) | async test runner | Required for AsyncClient-based tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | FastAPI StreamingResponse with text/event-stream | StreamingResponse works but requires manual SSE framing (data: ...\n\n), no keepalive, no disconnect handling; sse-starlette is strictly better |
| BackgroundTasks | asyncio.create_task() | create_task() works but loses FastAPI lifecycle management; BackgroundTasks is idiomatic and testable |
| BackgroundTasks | Celery/RQ | Celery requires Redis broker — unnecessary complexity for single-user v2.0 at low volume |
| In-memory asyncio.Queue for SSE | LangGraph streaming API | LangGraph has streaming support but it requires graph restructuring; asyncio.Queue is simpler and non-invasive to Phase 7 code |

**Installation:**
```bash
pip install sse-starlette>=2.1.0
# Add to reasoning/requirements.txt:
# sse-starlette>=2.1.0
# langgraph-checkpoint-postgres
# psycopg[binary]
```

---

## Architecture Patterns

### Recommended Project Structure
```
reasoning/
├── Dockerfile                  # NEW — Phase 8
├── requirements.txt            # Updated: add sse-starlette, langgraph-checkpoint-postgres, psycopg[binary]
├── pytest.ini                  # Existing
├── app/
│   ├── __init__.py             # Existing
│   ├── main.py                 # NEW — FastAPI app, lifespan, router registration
│   ├── dependencies.py         # NEW — lifespan-initialized shared resources (db_engine, neo4j_driver, qdrant_client)
│   ├── routers/
│   │   ├── __init__.py         # NEW
│   │   ├── health.py           # NEW — GET /health
│   │   └── reports.py          # NEW — POST /reports/generate, GET /reports/{id}, GET /reports/stream/{id}
│   ├── models/                 # Existing Phase 5/6 models
│   │   └── ...
│   ├── nodes/                  # Existing Phase 6 nodes
│   │   └── ...
│   └── pipeline/               # Existing Phase 7 pipeline
│       └── ...
└── tests/
    ├── conftest.py             # Existing + add TestClient fixture
    └── api/
        ├── __init__.py         # NEW
        ├── test_health.py      # NEW
        ├── test_reports.py     # NEW — POST /generate, GET /{id}
        └── test_stream.py      # NEW — SSE endpoint
```

### Pattern 1: FastAPI Lifespan with Shared Resources

The pipeline needs `db_engine`, `neo4j_driver`, and `qdrant_client` — expensive to create per-request. Use `lifespan` context manager to initialize once at startup and store on `app.state`.

**What:** Initialize all three store connections at app startup, close at shutdown.
**When to use:** Any resource that is expensive to create (DB connections, driver sessions).

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import create_engine
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    app.state.neo4j_driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"], auth=("neo4j", os.environ["NEO4J_PASSWORD"])
    )
    app.state.qdrant_client = QdrantClient(host=os.environ["QDRANT_HOST"], port=6333)
    app.state.job_queues: dict[int, asyncio.Queue] = {}  # job_id → SSE event queue
    yield
    # Shutdown
    app.state.db_engine.dispose()
    app.state.neo4j_driver.close()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: POST /reports/generate — 202 Accepted with BackgroundTasks

**What:** Create job record (status=pending), return 202 + job_id immediately, run pipeline as background task.
**When to use:** Any operation that takes longer than ~1s to complete.

```python
# Source: https://fastapi.tiangolo.com/tutorial/background-tasks/
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi import status

@router.post("/reports/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    req: Request,
) -> JSONResponse:
    # 1. Check for duplicate pending/running jobs → 409
    # 2. INSERT report_jobs (status=pending) → get job_id
    # 3. background_tasks.add_task(run_pipeline, job_id, ...)
    # 4. Return {"job_id": job_id, "status": "pending"}
    background_tasks.add_task(run_pipeline, job_id, ticker, asset_type, app_state)
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "pending"}
    )
```

**Critical detail:** `BackgroundTasks.add_task()` executes the task AFTER the response is sent. The task runs in the same event loop as FastAPI. For CPU-bound work this could block; for I/O-bound async work (Gemini API, DB queries) it is appropriate and efficient.

### Pattern 3: SSE via asyncio.Queue Bridge

The core problem: `generate_report()` is a monolithic coroutine — it does not yield mid-execution. SSE requires a way to receive events during execution. The solution is an `asyncio.Queue` bridge:

1. At job creation, allocate `queue = asyncio.Queue()` and store as `app.state.job_queues[job_id]`
2. Background task writes `{"node": "macro_regime", "status": "complete", "ts": ...}` dicts to the queue as each node finishes
3. The SSE generator reads from the queue and yields SSE events
4. Pipeline continues running even if SSE client disconnects — queue simply fills up (bounded by number of nodes: 7 events max)

**Implementation approach:** Wrap `run_graph()` with a callback that posts to the queue. Since `run_graph()` uses `compiled.ainvoke()`, use LangGraph's streaming capability or instrument with a simple wrapper.

**LangGraph `astream_events` approach (preferred):** LangGraph compiled graphs expose `astream_events()` which yields `{"event": "on_chain_start/end", "name": "node_name", ...}` events. This is the non-invasive way to get node transitions without restructuring `graph.py`.

```python
# Instrument the background task to emit SSE events:
async def run_pipeline_with_events(job_id: int, queue: asyncio.Queue, ...):
    # Update job status → running
    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        compiled = build_graph().compile(checkpointer=checkpointer)
        async for event in compiled.astream_events(state, config=config, version="v2"):
            if event["event"] in ("on_chain_start", "on_chain_end"):
                node_name = event.get("name", "")
                await queue.put({"node": node_name, "status": event["event"], "ts": ...})
    # Update job status → completed; put sentinel None to close SSE
    await queue.put(None)
```

**SSE generator reading from queue:**
```python
# Source: https://context7.com/sysid/sse-starlette/llms.txt
from sse_starlette import EventSourceResponse

async def event_generator(request: Request, queue: asyncio.Queue):
    try:
        while True:
            if await request.is_disconnected():
                break  # Pipeline continues; SSE stream closes cleanly
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keepalive"}
                continue
            if event is None:  # Sentinel: pipeline complete
                break
            yield {"event": "node_transition", "data": json.dumps(event)}
    except asyncio.CancelledError:
        raise

@router.get("/reports/stream/{job_id}")
async def stream_report(job_id: int, request: Request):
    queue = request.app.state.job_queues.get(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job not found or already completed")
    return EventSourceResponse(event_generator(request, queue))
```

### Pattern 4: Dockerfile — Follow Sidecar Pattern

The sidecar Dockerfile is the established project pattern. The reasoning Dockerfile is identical in structure but uses the reasoning `requirements.txt`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini .
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=60s \
    CMD curl -sf http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Note:** `start_period: 60s` (vs sidecar's 30s) — reasoning-engine loads heavier dependencies (LlamaIndex, LangGraph, Neo4j driver) at startup.

### Pattern 5: docker-compose.yml reasoning-engine Service

Follow existing service patterns exactly. Key elements:

```yaml
reasoning-engine:
  build:
    context: ./reasoning
    dockerfile: Dockerfile
  mem_limit: 2g
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
    neo4j:
      condition: service_healthy
    qdrant:
      condition: service_healthy
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    DATABASE_URI: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    NEO4J_URI: bolt://neo4j:7687
    NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    QDRANT_HOST: qdrant
    QDRANT_PORT: "6333"
    QDRANT_API_KEY: ${QDRANT_API_KEY}
    GEMINI_API_KEY: ${GEMINI_API_KEY}
  healthcheck:
    test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 60s
  ports:
    - "8001:8000"
  networks:
    - reasoning
  profiles: ["reasoning"]
```

**Note:** `mem_limit: 2g` uses the legacy Docker key — this is the locked project decision from Phase 3 (not `deploy.resources`).

### Anti-Patterns to Avoid

- **Using `@app.on_event("startup")` instead of `lifespan`:** Deprecated in modern FastAPI. The lifespan pattern (asynccontextmanager) is the recommended approach and allows resource sharing via `app.state`.
- **Creating DB connections per-request:** Never create `sqlalchemy.create_engine()` or `GraphDatabase.driver()` inside a path operation function. These are expensive; create once in lifespan.
- **Using `asyncio.create_task()` directly for background work:** Loses FastAPI's lifecycle management; task may escape test isolation. BackgroundTasks is the correct FastAPI idiom.
- **Blocking the event loop in the background task:** `generate_report()` is async and uses `await`, so it does not block. But any sync I/O inside the background task (e.g., synchronous psycopg2 calls) would block. The existing `write_report()` uses synchronous SQLAlchemy Core — this is fine since it runs in the background task after the response is already sent.
- **Route ordering: `/reports/stream/{id}` vs `/reports/{id}`:** FastAPI matches routes top-to-bottom. Register `/reports/stream/{id}` BEFORE `/reports/{id}` in the router to prevent `stream` being interpreted as a `{id}` path parameter.
- **SSE without keepalive:** Without periodic pings, proxies (nginx, AWS ALB) close idle SSE connections after 60s. Use `ping=15` in EventSourceResponse or manual keepalive yields.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE framing | Manual `data: ...\n\n` string building | `sse-starlette` EventSourceResponse | Handles CRLF, keepalive pings, disconnect, media type headers correctly |
| Async test client | Custom HTTP test harness | FastAPI TestClient / httpx AsyncClient | Already used in sidecar; TestClient runs synchronously; AsyncClient via ASGITransport for async tests |
| Job ID generation | UUID or random string | PostgreSQL BIGSERIAL (existing `report_jobs.job_id`) | Schema already has BIGSERIAL primary key — use it; no client-generated IDs needed |
| Duplicate job detection | Timestamp comparison | SQL query: `WHERE asset_id=X AND status IN ('pending','running')` | `idx_report_jobs_asset_status` index already exists for this exact query pattern |

**Key insight:** All the hard parts already exist. The `report_jobs` table, indexes, and 4-state machine are in V7 migration. The `generate_report()` entry point is in `reasoning/app/pipeline/__init__.py`. Phase 8 is pure integration: wire HTTP → jobs table → pipeline → SSE.

---

## Common Pitfalls

### Pitfall 1: asyncio.Queue Not Shared Between BackgroundTask and SSE Handler

**What goes wrong:** Background task writes to a queue object; SSE handler looks up a different queue object (or None) from `app.state.job_queues`. No events are emitted.

**Why it happens:** The queue must be created before the background task starts, stored keyed by `job_id`, and retrieved by `job_id` in the SSE endpoint. If the queue is created inside the background task function itself, the SSE endpoint cannot access it.

**How to avoid:** Create `queue = asyncio.Queue()` in the POST `/reports/generate` handler, store `app.state.job_queues[job_id] = queue`, then pass the queue to the background task.

**Warning signs:** SSE endpoint returns 404 for existing jobs; SSE stream opens but emits no events.

### Pitfall 2: Event Loop Issues with asyncio.Queue in BackgroundTasks

**What goes wrong:** `asyncio.Queue` created in one event loop, awaited in another → `RuntimeError: Future belongs to a different event loop`.

**Why it happens:** FastAPI/uvicorn runs a single event loop in the main thread. BackgroundTasks execute in the same event loop. As long as the queue is created in the same request-response cycle (not at module level), there is no issue.

**How to avoid:** Always create the queue within the async path operation handler (not at module initialization). Use `asyncio.get_event_loop()` sparingly — prefer `asyncio.Queue()` created at request time.

### Pitfall 3: Route Order — /reports/stream/{id} Must Come Before /reports/{id}

**What goes wrong:** GET `/reports/stream/123` matches route `/reports/{id}` with `id="stream"` → 404 or validation error.

**Why it happens:** FastAPI registers routes in the order `include_router()` processes them. If `/reports/{id}` is registered first, the literal path `stream` is consumed as the `id` parameter.

**How to avoid:** In `reports.py`, define the stream endpoint function/decorator before the `/{id}` endpoint. FastAPI matches routes in definition order.

**Warning signs:** Curl to `/reports/stream/1` returns 422 Unprocessable Entity with "value is not a valid integer" for `id`.

### Pitfall 4: Missing psycopg[binary] and langgraph-checkpoint-postgres

**What goes wrong:** `reasoning-engine` container fails to start with `ModuleNotFoundError: No module named 'psycopg'` or `langgraph_checkpoint_postgres`.

**Why it happens:** These were identified as missing from `requirements.txt` in the CONTEXT.md deferred section. They are needed for `AsyncPostgresSaver.from_conn_string()` inside `run_graph()`.

**How to avoid:** Add both to `reasoning/requirements.txt` before building the Docker image. Verify with `pip install -r requirements.txt` in CI or local build.

**Warning signs:** Container starts but pipeline calls fail immediately; `ImportError` in logs.

### Pitfall 5: BackgroundTasks Runs Sync Functions Synchronously

**What goes wrong:** If a sync (non-async) function is passed to `background_tasks.add_task()`, FastAPI runs it directly in the event loop thread, potentially blocking all other requests during the ~3-5 minute pipeline run.

**Why it happens:** FastAPI distinguishes between sync and async background functions. Sync functions run in the event loop; they are not automatically sent to a thread pool.

**How to avoid:** The pipeline entry point `generate_report()` is already `async def` — pass it directly to `add_task()`. This is the correct pattern. If any sub-operation is sync-only and slow, wrap with `asyncio.to_thread()`.

**Warning signs:** FastAPI becomes unresponsive to other requests during pipeline execution.

### Pitfall 6: SSE Queue Memory Leak After Job Completion

**What goes wrong:** `app.state.job_queues` grows unbounded — every completed job leaves an `asyncio.Queue` in memory.

**Why it happens:** Queue is added on job creation but never removed after job completion.

**How to avoid (Claude's Discretion — simple policy):** Remove queue from `app.state.job_queues` after the SSE generator exits (using a try/finally block in `event_generator`). For jobs with no SSE subscriber, clean up in the background task itself after posting the sentinel None event. Given v2.0 is manual usage (not high-volume), a simple cleanup is sufficient.

---

## Code Examples

Verified patterns from official sources:

### POST /reports/generate — Full Pattern
```python
# Source: https://fastapi.tiangolo.com/tutorial/background-tasks/ (verified via Context7)
import asyncio
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi import status
from pydantic import BaseModel

router = APIRouter()

class GenerateRequest(BaseModel):
    ticker: str
    asset_type: str

@router.post("/reports/generate", status_code=202)
async def generate_report_endpoint(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> JSONResponse:
    # Check for duplicate active job
    existing_job_id = _find_active_job(request.app.state.db_engine, body.ticker, body.asset_type)
    if existing_job_id:
        raise HTTPException(status_code=409, detail=f"Job {existing_job_id} already pending/running")

    # Create job record
    job_id = _create_job(request.app.state.db_engine, asset_id=f"{body.ticker}:{body.asset_type}")

    # Create SSE event queue
    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.job_queues[job_id] = queue

    # Schedule background pipeline
    background_tasks.add_task(
        _run_pipeline,
        job_id=job_id,
        ticker=body.ticker,
        asset_type=body.asset_type,
        db_engine=request.app.state.db_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        qdrant_client=request.app.state.qdrant_client,
        queue=queue,
    )

    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})
```

### GET /reports/stream/{job_id} — SSE Pattern
```python
# Source: https://context7.com/sysid/sse-starlette/llms.txt (verified via Context7)
import json
from sse_starlette import EventSourceResponse
from starlette.requests import Request

@router.get("/reports/stream/{job_id}")
async def stream_report_events(job_id: int, request: Request):
    queue = request.app.state.job_queues.get(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job not found or stream already closed")

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break  # Client left; pipeline keeps running
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keepalive"}
                    continue
                if event is None:  # Sentinel: pipeline finished
                    yield {"event": "complete", "data": json.dumps({"job_id": job_id})}
                    break
                yield {"event": "node_transition", "data": json.dumps(event)}
        except asyncio.CancelledError:
            raise
        finally:
            request.app.state.job_queues.pop(job_id, None)

    return EventSourceResponse(event_generator(), ping=15)
```

### Lifespan with app.state
```python
# Source: https://fastapi.tiangolo.com/advanced/events/ (verified via Context7)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=5)
    app.state.neo4j_driver = GraphDatabase.driver(...)
    app.state.qdrant_client = QdrantClient(...)
    app.state.job_queues: dict[int, asyncio.Queue] = {}
    yield
    app.state.db_engine.dispose()
    app.state.neo4j_driver.close()

app = FastAPI(lifespan=lifespan)
```

### FastAPI TestClient for background tasks
```python
# Source: https://fastapi.tiangolo.com/tutorial/testing/ (verified via Context7)
# TestClient executes background tasks synchronously during test — no async needed
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

def test_generate_returns_202(mock_pipeline):
    with TestClient(app) as client:
        response = client.post("/reports/generate", json={"ticker": "VHM", "asset_type": "equity"})
    assert response.status_code == 202
    assert "job_id" in response.json()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` asynccontextmanager | FastAPI 0.95+ | Deprecated event handlers; lifespan is the recommended pattern |
| Global variables for shared state | `app.state` dict | FastAPI 0.95+ | Thread-safe, testable, per-app isolation |
| Manual SSE framing with StreamingResponse | `sse-starlette` EventSourceResponse | Ongoing | Handles all SSE edge cases; no hand-rolling needed |
| Celery for background tasks in FastAPI | BackgroundTasks (for simple cases) | FastAPI design | Celery is for distributed/retryable work; BackgroundTasks for in-process fire-and-forget |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Still works but deprecated. Lifespan is correct pattern.
- `asyncio.get_event_loop().create_task()`: Deprecated in Python 3.10+. Use `asyncio.create_task()` or BackgroundTasks.

---

## Open Questions

1. **LangGraph astream_events compatibility with AsyncPostgresSaver**
   - What we know: LangGraph compiled graphs support `.astream_events(version="v2")` which yields node-level events. The existing `run_graph()` uses `compiled.ainvoke()`.
   - What's unclear: Whether `astream_events` works identically with `AsyncPostgresSaver` checkpointer in the exact version of `langgraph` pinned (`>=0.2.0`). The API stabilized around 0.2.x.
   - Recommendation: If `astream_events` has any version issues, fall back to wrapping the existing `run_graph()` call and posting manual events to the queue before/after each node via a custom approach (patch node functions to wrap with queue.put). This is slightly invasive but isolated to the background task runner.

2. **asyncio.Queue and TestClient behavior**
   - What we know: TestClient executes background tasks synchronously (inline with the test). SSE streams need to be tested differently.
   - What's unclear: How to test SSE endpoints without a live server — the SSE generator is async and queue-based.
   - Recommendation: For SSE tests, use `httpx.AsyncClient` with `ASGITransport` and `@pytest.mark.anyio`, or mock the queue and test the generator function directly. Keep SSE tests as "integration" markers.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `reasoning/pytest.ini` (exists; `asyncio_mode = auto`, `integration` marker registered) |
| Quick run command | `cd reasoning && python -m pytest tests/api/ -x -q` |
| Full suite command | `cd reasoning && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRVC-01 | POST /reports/generate returns 202 + job_id, creates job in DB, dispatches background task | unit (mocked pipeline) | `pytest tests/api/test_reports.py::test_generate_returns_202 -x` | ❌ Wave 0 |
| SRVC-01 | 409 Conflict when pending/running job exists for same (ticker, asset_type) | unit | `pytest tests/api/test_reports.py::test_generate_409_conflict -x` | ❌ Wave 0 |
| SRVC-01 | Failed job retry accepted (POST same params when job is failed) | unit | `pytest tests/api/test_reports.py::test_generate_retry_failed -x` | ❌ Wave 0 |
| SRVC-02 | GET /reports/{id} returns 200 + report JSON when job completed | unit (mocked DB) | `pytest tests/api/test_reports.py::test_get_report_completed -x` | ❌ Wave 0 |
| SRVC-02 | GET /reports/{id} returns 202 + status when job pending/running | unit | `pytest tests/api/test_reports.py::test_get_report_pending -x` | ❌ Wave 0 |
| SRVC-02 | GET /reports/{id} returns 404 when job_id not found | unit | `pytest tests/api/test_reports.py::test_get_report_not_found -x` | ❌ Wave 0 |
| SRVC-03 | GET /reports/stream/{id} emits SSE events and closes on sentinel | unit (mock queue) | `pytest tests/api/test_stream.py::test_sse_stream_emits_events -x` | ❌ Wave 0 |
| SRVC-03 | GET /reports/stream/{id} returns 404 for unknown job_id | unit | `pytest tests/api/test_stream.py::test_sse_stream_404 -x` | ❌ Wave 0 |
| SRVC-04 | GET /health returns 200 with status=ok | unit | `pytest tests/api/test_health.py::test_health_ok -x` | ❌ Wave 0 |
| SRVC-05 | Docker service starts and /health returns 200 | integration (Docker) | `pytest tests/api/test_health.py::test_health_docker -m integration -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd reasoning && python -m pytest tests/api/ -x -q`
- **Per wave merge:** `cd reasoning && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `reasoning/tests/api/__init__.py` — package init
- [ ] `reasoning/tests/api/test_health.py` — covers SRVC-04
- [ ] `reasoning/tests/api/test_reports.py` — covers SRVC-01, SRVC-02
- [ ] `reasoning/tests/api/test_stream.py` — covers SRVC-03
- [ ] `reasoning/app/routers/__init__.py` — package init
- [ ] `reasoning/app/main.py` — FastAPI app entry point
- [ ] `reasoning/app/dependencies.py` — shared resource initialization
- [ ] `reasoning/app/routers/health.py` — health endpoint
- [ ] `reasoning/app/routers/reports.py` — all report endpoints
- [ ] `reasoning/Dockerfile` — container packaging

---

## Sources

### Primary (HIGH confidence)
- `/websites/fastapi_tiangolo` (Context7) — BackgroundTasks, lifespan, StreamingResponse, JSONResponse status codes, TestClient
- `/sysid/sse-starlette` (Context7) — EventSourceResponse, disconnect detection, keepalive ping, send_timeout
- `sidecar/Dockerfile` (project file) — Dockerfile pattern for Python FastAPI service
- `docker-compose.yml` (project file) — service patterns: mem_limit, depends_on conditions, profiles, env_file
- `db/migrations/V7__report_jobs.sql` (project file) — report_jobs table schema, indexes, state machine
- `reasoning/app/pipeline/__init__.py` (project file) — generate_report() signature and parameters
- `reasoning/app/pipeline/graph.py` (project file) — run_graph(), node names, LangGraph compilation

### Secondary (MEDIUM confidence)
- Context7 FastAPI docs on lifespan startup/shutdown patterns — verified via official fastapi.tiangolo.com docs
- sse-starlette README patterns for custom ping and error handling

### Tertiary (LOW confidence)
- LangGraph `astream_events` API compatibility with AsyncPostgresSaver at `>=0.2.0` — not verified against specific version; flagged as open question

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries already in project (FastAPI, SQLAlchemy, pydantic v2) or well-documented (sse-starlette via Context7)
- Architecture: HIGH — Patterns verified via Context7 official docs; project structure follows existing sidecar/reasoning conventions
- Pitfalls: HIGH for known pitfalls (route ordering, queue scope, missing deps); MEDIUM for LangGraph astream_events compatibility

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (30 days — stable libraries; FastAPI and sse-starlette do not change rapidly)
