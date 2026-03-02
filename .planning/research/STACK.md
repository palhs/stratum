# Technology Stack

**Project:** Stratum — Long-Term Investment Advisor Platform
**Researched:** 2026-03-03
**Scope:** Full-stack validation of founder's chosen tech with version-pinning and gap analysis

---

## Verdict

The founder's stack is well-chosen and internally consistent. Every major component has an official integration with the others, and the architecture boundary (storage decouples ingestion from reasoning) is a sound pattern. Two gaps exist: the stack needs explicit async task queue wiring for the background report generation pipeline, and TimescaleDB should be evaluated as a PostgreSQL extension for the time-series OHLCV data specifically.

---

## Recommended Stack

### AI Reasoning Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LangGraph | 1.0.10 | Multi-step AI reasoning chain control | Reached v1.0 stable Oct 2025; stateful graph execution with built-in node caching and deferred nodes for map-reduce patterns; `astream_events(v2)` integrates cleanly with FastAPI SSE streaming; the only framework with programmatic control over each reasoning step (not just prompt chaining) |
| google-genai | 1.65.0 | Gemini API SDK (primary LLM) | New unified GA SDK (since May 2025); old `google-generativeai` reached EOL Nov 2025 — must use this package; supports Gemini 2.5 Flash and Gemini 3.1 Pro Preview |
| Ollama | latest | Local LLM runtime (fallback/cost control) | Best DX for single-VPS deployment; "Docker for LLMs" — one command pull and run; appropriate for single-user v1 scale; production throughput limit is acceptable given weekly/monthly cadence; use vLLM only if moving to multi-user scale |

### RAG and Retrieval Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| llama-index-core | 0.14.15 | RAG orchestration, retrieval pipeline | Native integrations with both Qdrant and Neo4j in a single retrieval interface; `PropertyGraphStore` for Neo4j and `QdrantVectorStore` maintained as first-class integrations; Text2Cypher support for natural language graph queries |
| llama-index-vector-stores-qdrant | pinned to core version | Qdrant vector store connector | Official LlamaIndex integration package; do not use raw qdrant-client directly from LlamaIndex — use this wrapper |
| llama-index-graph-stores-neo4j | pinned to core version | Neo4j graph store connector | Official integration; supports both knowledge graph construction and `KnowledgeGraphQueryEngine` for regime queries |

### Storage Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 17.x | Fundamental financial data, computed price structure markers, user/watchlist data | Weekly/monthly cadence makes this sufficient — no streaming time-series pressure; TimescaleDB extension is **optional but recommended** for OHLCV partitioning if data grows past 2 years of history |
| TimescaleDB | 2.17.x (PostgreSQL extension) | Time-series optimization for OHLCV tables | Adds columnar compression (90%+) and continuous aggregates to standard PostgreSQL; zero migration cost — same SQL interface; install from the start on the OHLCV table even if not immediately needed |
| Neo4j | Community Edition 5.x / 2025.x | Knowledge graph: macro regime relationships, historical analogues, asset correlations | Python driver 6.1.0 required (do not install deprecated `neo4j-driver` package — use `neo4j`); LlamaIndex integration confirmed and actively maintained; supports Text2Cypher |
| Qdrant | 1.17.0 (server), qdrant-client 1.17.0 | Vector store: semantic retrieval over earnings transcripts, Fed minutes, macro reports | Confirmed Relevance Feedback feature in v1.17 improves financial document recall; self-hosted Docker image trivially runs on VPS; Python client matches server version |

### Ingestion and Orchestration Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| n8n | 2.9.4 (stable) | Pipeline orchestration: cron scheduling, data ingestion, retry logic, error alerting | Visual debugger is the primary reason over Airflow/Prefect — the founder is the operator; built-in HTTP request nodes cover FRED, World Gold Council endpoints without custom code; Python code nodes available for vnstock calls; communicates with AI layer only via PostgreSQL/Neo4j/Qdrant (never directly) |
| vnstock | 3.4.2 | Vietnamese stock market data (TCBS, SSI) | Only maintained Python library for VN market data; v3.4.2 (Feb 2026) has stock screener features; run from n8n Python code nodes; data lands in PostgreSQL |
| fredapi | latest (≥0.5.0) | FRED macroeconomic data ingestion | Simplest FRED client; returns pandas DataFrames; adequate for batch ingestion cadence; alternative: `pyfredapi` if async access needed (it covers all FRED endpoints) |

### Backend API Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.135.1 | HTTP API, LangGraph invocation endpoint, SSE streaming | Async-native; `StreamingResponse` + `astream_events(v2)` from LangGraph is the standard pattern for streaming reasoning steps to the frontend; requires Python ≥3.10, recommend 3.12 for production |
| Pydantic | 2.12.5 | Request/response validation, data models | Required by FastAPI 0.135.1; v2 is 5–50x faster than v1 due to Rust core rewrite; `BaseModel` for all LangGraph state definitions |
| SQLAlchemy | 2.x (async) | PostgreSQL ORM | Use `AsyncSession` + `asyncpg` driver; single engine per process, short-lived session per request; do not mix sync and async patterns |
| asyncpg | ≥0.30.0 | Async PostgreSQL driver | SQLAlchemy's recommended async backend for PostgreSQL; significantly higher throughput than `psycopg2` under concurrent load |
| Alembic | ≥1.14.0 | Database schema migrations | Run migrations in lifespan startup (before first request); configure with `-t async` template for async SQLAlchemy compatibility |
| neo4j (Python driver) | 6.1.0 | Direct Neo4j access from FastAPI where LlamaIndex is not in the path | Install `neo4j` package (not deprecated `neo4j-driver`); supports async sessions |

### Auth and User Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Supabase | self-hosted via Docker Compose | Auth, user session management, UUID user ID generation | Auth works identically in self-hosted vs managed; UUID user IDs mirror into PostgreSQL and Neo4j for cross-store user scoping; self-hosted is appropriate for single-user v1 — no MAU billing surprises; config via files not UI in self-hosted mode |

### Frontend Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Next.js | 16.1.6 | SSR frontend, research report UI | App Router is now the standard; Turbopack stable by default; React Compiler stable in v16; SSR suits report-style pages (server-rendered HTML for long narrative content); requires Node.js ≥20.9 |
| lightweight-charts | 5.1.0 | Financial chart rendering | v5 added multi-pane support (needed for price + volume + indicator separation); 35kB base bundle; open source Apache 2.0; renders weekly/monthly OHLCV natively; integrates with Next.js client components via `use client` directive |
| React | 19.2 | UI framework (bundled with Next.js 16) | Next.js 16 uses React 19.2 canary features; do not install React separately — use the version pinned by Next.js |
| Tailwind CSS | 4.x | Styling | Pairs with Next.js App Router; report-style aesthetic is well-served by utility classes; v4 removes config file requirement for most use cases |

### Infrastructure and Deployment

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker Compose | v2.x | Service orchestration on VPS | Runs all services (n8n, PostgreSQL, Neo4j, Qdrant, Supabase stack, FastAPI, Next.js) in a single compose file; the only viable self-hosted orchestration approach at single-user scale |
| Nginx | latest stable | Reverse proxy, SSL termination | Routes `/api/*` to FastAPI, `/` to Next.js; handles SSE keep-alive headers (`X-Accel-Buffering: no`); required for SSE to work through a proxy |
| PostgreSQL 17 | included in Docker Compose | (see Storage) | — |

---

## Gaps Identified

### Gap 1: Background Task Queue (Critical)

n8n handles scheduled ingestion, but the on-demand report generation path (user adds to watchlist → trigger reasoning pipeline → return report) needs a background task queue so FastAPI doesn't hold the HTTP connection open for a multi-minute LangGraph execution.

**Recommendation:** Use `arq` (Async Redis Queue) as the background task system.
- Designed for asyncio from the ground up — natural fit for FastAPI
- ~7x faster than RQ, ~40x faster for I/O-bound jobs compared to blocking queues
- Redis as broker (one additional container in Docker Compose)
- Pattern: FastAPI endpoint enqueues job → returns `job_id` → frontend polls or receives SSE push when done

**Alternative:** Use LangGraph's own persistence (PostgreSQL checkpointer) combined with a polling endpoint if Redis overhead is unwanted. This avoids an additional service.

### Gap 2: Embedding Model (Important)

LlamaIndex + Qdrant requires an embedding model to encode documents for semantic search. The stack doesn't specify one.

**Recommendation:** Use `llama-index-embeddings-gemini` for the Gemini embedding API, or `llama-index-embeddings-fastembed` for local embedding via FastEmbed (runs in-process, no GPU required, uses quantized models like `BAAI/bge-small-en-v1.5`).

For v1, FastEmbed is preferred: zero cost, no additional API dependency, fast enough for weekly/monthly ingestion cadence.

### Gap 3: LangGraph State Persistence / Checkpointing

LangGraph 1.0 has built-in PostgreSQL checkpointing (`langgraph-checkpoint-postgres`). This should be explicitly added to enable:
- Resume interrupted reasoning chains
- Audit trail of each reasoning step (required by the explainability constraint)
- Human-in-the-loop review points if needed

**Recommendation:** Add `langgraph-checkpoint-postgres` to the stack and use the same PostgreSQL instance (different schema) as the checkpointer.

### Gap 4: n8n → FastAPI Trigger Integration

n8n's scheduled pipeline produces ingested data in the storage layer. The monthly report generation job should be triggered by n8n (via HTTP request node to FastAPI endpoint) after ingestion completes, not on a separate cron. This ensures reports always use the freshest ingested data. Confirm this pattern is implemented explicitly in the architecture — it is not automatic.

---

## Alternatives Considered

| Category | Recommended | Alternative Considered | Why Not |
|----------|-------------|----------------------|---------|
| LLM Orchestration | LangGraph 1.0 | n8n AI nodes | n8n AI nodes don't provide programmatic step-by-step control needed for explainable multi-layer reasoning; LangGraph is the right tool for reasoning, n8n for ingestion — use both |
| LLM Orchestration | LangGraph 1.0 | CrewAI / AutoGen | Less control over execution graph; LangGraph's explicit graph definition suits the structured 3-layer analysis (macro → valuation → price structure) |
| Vector Store | Qdrant | pgvector (PostgreSQL extension) | pgvector works but has lower retrieval quality at scale and fewer ANN algorithm choices; Qdrant's Relevance Feedback in v1.17 is directly useful for financial document retrieval refinement |
| Knowledge Graph | Neo4j | ArangoDB / Dgraph | LlamaIndex and LangChain both have first-class Neo4j integrations; ArangoDB has no equivalent maintained Python/LlamaIndex integration |
| Pipeline Orchestration | n8n | Apache Airflow | Airflow requires more infrastructure (executor, scheduler, webserver separately); n8n's visual debugger better fits single-operator self-hosted model |
| Pipeline Orchestration | n8n | Prefect / Dagster | Both are Python-only and require SDK-defined DAGs; n8n's HTTP request nodes eliminate boilerplate for external API ingestion tasks |
| Frontend | Next.js 16 | Remix / Nuxt | Next.js has the broadest React ecosystem; App Router's server components fit report-style SSR; TradingView charts integrate cleanly with React |
| Backend | FastAPI | Django REST Framework | FastAPI's async-native design is required for non-blocking LangGraph execution; Django async support exists but is bolted on |
| Auth | Supabase self-hosted | Keycloak / Auth0 | Supabase auth is simpler to operate and the JWT/UUID output integrates directly with PostgreSQL RLS and Neo4j; overkill features of Keycloak not needed |
| Local LLM | Ollama | vLLM | vLLM is production-grade for multi-user concurrent inference; at single-user v1 scale, Ollama's simplicity wins; revisit if moving to multi-tenant |
| Background Tasks | arq | Celery | Celery is sync-first with async bolted on; arq is async-native and fits the FastAPI stack without impedance mismatch |

---

## Installation Reference

### Python Environment (Backend, n8n Python nodes, LangGraph service)

```bash
# Core backend
pip install fastapi==0.135.1 uvicorn[standard] pydantic==2.12.5

# Database drivers
pip install sqlalchemy asyncpg alembic
pip install neo4j==6.1.0
pip install qdrant-client==1.17.0

# AI / RAG
pip install langgraph==1.0.10
pip install langgraph-checkpoint-postgres
pip install llama-index-core==0.14.15
pip install llama-index-vector-stores-qdrant
pip install llama-index-graph-stores-neo4j
pip install llama-index-embeddings-fastembed

# LLM SDKs
pip install google-genai==1.65.0

# Data ingestion
pip install vnstock==3.4.2
pip install fredapi

# Background tasks
pip install arq redis

# Utilities
pip install httpx pandas python-dotenv
```

### Node.js Environment (Frontend)

```bash
# New project (includes Next.js 16, React 19)
npx create-next-app@latest stratum-frontend

# Financial charts
npm install lightweight-charts@5.1.0

# Supabase auth client
npm install @supabase/supabase-js @supabase/ssr

# Styling
npm install tailwindcss@^4 @tailwindcss/typography
```

---

## Python Version Constraint

All components require Python >=3.10. Recommend Python 3.12 for production:
- Supported by LangGraph 1.0.10, llama-index-core 0.14.15, FastAPI 0.135.1, qdrant-client 1.17.0, neo4j 6.1.0, vnstock 3.4.2
- Python 3.13 support exists across the stack but is newer — 3.12 has broader tested compatibility

---

## Sources

- LangGraph PyPI: https://pypi.org/project/langgraph/ — version 1.0.10 confirmed (HIGH confidence)
- LlamaIndex Core PyPI: https://pypi.org/project/llama-index-core/ — version 0.14.15 confirmed (HIGH confidence)
- FastAPI PyPI: https://pypi.org/project/fastapi/ — version 0.135.1 confirmed (HIGH confidence)
- Qdrant client PyPI: https://pypi.org/project/qdrant-client/ — version 1.17.0 confirmed (HIGH confidence)
- Qdrant server GitHub releases: https://github.com/qdrant/qdrant/releases — v1.17.0 confirmed (HIGH confidence)
- Neo4j Python driver PyPI: https://pypi.org/project/neo4j/ — version 6.1.0 confirmed (HIGH confidence)
- vnstock PyPI: https://pypi.org/project/vnstock/ — version 3.4.2 confirmed (HIGH confidence)
- google-genai PyPI: https://pypi.org/project/google-genai/ — version 1.65.0 confirmed (HIGH confidence)
- Pydantic PyPI: https://pypi.org/project/pydantic/ — version 2.12.5 confirmed (HIGH confidence)
- Next.js 16.1.6: https://nextjs.org/blog/next-16-1 (MEDIUM confidence — inferred from search, not direct PyPI)
- lightweight-charts v5.1.0: https://www.npmjs.com/package/lightweight-charts (MEDIUM confidence — search result)
- n8n 2.9.4: https://github.com/n8n-io/n8n/releases (MEDIUM confidence — search result)
- LlamaIndex + Neo4j integration: https://neo4j.com/labs/genai-ecosystem/llamaindex/ (HIGH confidence — official Neo4j labs page)
- GraphRAG with Qdrant + Neo4j: https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/ (HIGH confidence — official Qdrant docs)
- LangGraph + FastAPI SSE streaming: https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn (MEDIUM confidence)
- Supabase self-hosting: https://supabase.com/docs/guides/self-hosting (HIGH confidence — official docs)
- arq vs Celery: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications (MEDIUM confidence)
- TimescaleDB PostgreSQL compatibility: https://github.com/timescale/timescaledb (MEDIUM confidence)
- google-generativeai EOL: https://github.com/google-gemini/deprecated-generative-ai-python (HIGH confidence — official deprecation notice)
