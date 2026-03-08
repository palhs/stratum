# Architecture Patterns

**Domain:** Analytical reasoning engine integration — LangGraph + LlamaIndex + Gemini over existing Docker Compose platform
**Researched:** 2026-03-09
**Confidence:** HIGH (existing codebase fully inspected; integration patterns verified against official docs)

---

## Context: What Already Exists (v1.0)

The v1.0 platform is fully operational. This document focuses exclusively on how v2.0 reasoning components integrate with it. Do not rebuild what exists.

**Existing Docker Compose services (7):**

| Service | Network | Role |
|---------|---------|------|
| `postgres` | ingestion + reasoning | Structured storage — OHLCV, fundamentals, structure markers, pipeline logs |
| `neo4j` | ingestion + reasoning | Graph storage — regime nodes, time period nodes, APOC triggers live |
| `qdrant` | ingestion + reasoning | Vector storage — 384-dim FastEmbed collections ready |
| `flyway` | ingestion | One-shot Flyway migration runner (V1–V5 applied) |
| `neo4j-init` | ingestion | One-shot constraints + APOC trigger installer |
| `qdrant-init` | ingestion | One-shot collection initializer |
| `n8n` | ingestion only | Cron orchestrator for all data ingestion |
| `data-sidecar` | ingestion only | FastAPI sidecar — vnstock, FRED, gold, structure marker computation |

**Key architectural constraint (locked):** `n8n` is on `ingestion` network only. Storage services (postgres, neo4j, qdrant) are on both `ingestion` and `reasoning` networks. New reasoning services join `reasoning` network only. n8n and reasoning services never communicate directly.

**Data already in storage:**

| Store | Contents |
|-------|----------|
| PostgreSQL | 9,411 OHLCV rows, 399 fundamentals, FRED macro series, gold data, 9,985 structure marker rows, pipeline run logs |
| Neo4j | Regime + TimePeriod constraints active; APOC triggers live; regime relationships empty (populated in v2.0) |
| Qdrant | 384-dim collections initialized; document corpus empty (populated in v2.0) |

---

## System Overview

```
+=====================================================================+
|  INGESTION NETWORK (existing — do not modify)                       |
|                                                                     |
|  n8n ──────────► data-sidecar (FastAPI)                            |
|                        │                                            |
|              ┌─────────┼──────────┐                                 |
|              ▼         ▼          ▼                                 |
+=====================================================================+
|  STORAGE LAYER (dual-network — existing services, new migrations)   |
|                                                                     |
|  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐            |
|  │ PostgreSQL  │  │    Neo4j     │  │     Qdrant      │            |
|  │ (port 5432) │  │ (port 7687) │  │   (port 6333)  │            |
|  │             │  │              │  │                 │            |
|  │ v2.0 adds:  │  │ v2.0 adds:   │  │ v2.0 adds:      │            |
|  │ reports     │  │ Regime nodes │  │ doc embeddings  │            |
|  │ report_jobs │  │ analogues    │  │ (Fed, SBV,      │            |
|  │             │  │ relationships│  │  earnings)      │            |
|  └─────────────┘  └──────────────┘  └─────────────────┘            |
+=====================================================================+
|  REASONING NETWORK (new in v2.0)                                    |
|                                                                     |
|  ┌──────────────────────────────────────────────────────────┐       |
|  │  reasoning-engine  (new Docker service)                  │       |
|  │                                                          │       |
|  │  FastAPI (reasoning gateway + SSE streaming)             │       |
|  │    └── POST /reports/generate   → trigger LangGraph      │       |
|  │    └── GET  /reports/{id}       → fetch stored report    │       |
|  │    └── GET  /reports/stream/{id} → SSE step events       │       |
|  │    └── GET  /health                                      │       |
|  │                                                          │       |
|  │  LangGraph StateGraph                                    │       |
|  │    ├── Node: macro_regime                                │       |
|  │    │     reads Neo4j via LlamaIndex PropertyGraphIndex   │       |
|  │    │     calls Gemini API (langchain-google-genai)       │       |
|  │    ├── Node: valuation                                   │       |
|  │    │     reads PostgreSQL directly (fundamentals, pct)   │       |
|  │    │     reads Qdrant via LlamaIndex QdrantVectorStore   │       |
|  │    │     calls Gemini API                                │       |
|  │    ├── Node: structure                                   │       |
|  │    │     reads PostgreSQL directly (structure_markers)   │       |
|  │    │     calls Gemini API                                │       |
|  │    ├── Node: entry_quality                               │       |
|  │    │     synthesizes all prior node outputs from state   │       |
|  │    │     calls Gemini API                                │       |
|  │    └── Node: compose_report                              │       |
|  │          assembles structured JSON report cards          │       |
|  │          generates Vietnamese + English narrative        │       |
|  │          calls Gemini API (two-pass: VN then EN)         │       |
|  │          writes completed report to PostgreSQL           │       |
|  │                                                          │       |
|  │  LlamaIndex (retrieval abstraction — called by nodes)    │       |
|  │    ├── Neo4jPropertyGraphIndex  → regime traversal       │       |
|  │    └── QdrantVectorStore        → hybrid dense+sparse    │       |
|  │                                                          │       |
|  │  PostgreSQLSaver (LangGraph checkpointer)                │       |
|  │    → checkpoint state to existing postgres service       │       |
|  └──────────────────────────────────────────────────────────┘       |
+=====================================================================+
```

---

## New vs Modified Components

### New Docker Service: `reasoning-engine`

**One new service.** No new database services are needed — the existing postgres, neo4j, and qdrant services are already on the `reasoning` network.

```yaml
# Addition to docker-compose.yml
reasoning-engine:
  build:
    context: ./reasoning
    dockerfile: Dockerfile
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
    NEO4J_URI: bolt://neo4j:7687
    NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    QDRANT_HOST: qdrant
    QDRANT_PORT: "6333"
    QDRANT_API_KEY: ${QDRANT_API_KEY}
    GEMINI_API_KEY: ${GEMINI_API_KEY}
    GEMINI_MODEL: ${GEMINI_MODEL:-gemini-2.0-flash}
  ports:
    - "8001:8000"   # Exposed on host for direct testing; not internal-only in v2.0
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 30s
  networks:
    - reasoning     # reasoning network only — cannot reach ingestion services
  profiles: ["reasoning"]
```

**Why one service, not separate LangGraph + FastAPI containers:** At single-user VPS scale, the reasoning-engine service runs FastAPI as the HTTP gateway and imports LangGraph inline. Splitting them would add container networking overhead with no benefit at this scale. LangGraph's state is persisted to PostgreSQL via `langgraph-checkpoint-postgres`, so it is stateless at the process level and survives restarts.

### New Flyway Migrations

Two new SQL migrations extend PostgreSQL for v2.0 reasoning outputs:

```
db/migrations/
├── V1__initial_schema.sql        (existing — pipeline_run_log)
├── V2__stock_data.sql            (existing — ohlcv, fundamentals)
├── V3__gold_data.sql             (existing — gold series)
├── V4__fred_indicators.sql       (existing — macro indicators)
├── V5__structure_markers.sql     (existing — computed markers)
├── V6__reports.sql               (NEW — report output storage)
└── V7__report_jobs.sql           (NEW — async job tracking)
```

V6 creates `reports` table: `id, asset_id, report_json, report_markdown_vn, report_markdown_en, regime_label, entry_quality_score, generated_at, data_as_of`.

V7 creates `report_jobs` table: `id, asset_id, status (queued/running/complete/failed), created_at, completed_at, error_message, report_id (FK to reports)`.

### New Neo4j Population (in v2.0 ingestion workflows)

Neo4j already has constraints and APOC triggers. v2.0 adds Cypher to populate regime analogue data via new n8n workflows. The schema is pre-wired — only data is missing.

Regime nodes: `(:Regime {id, label, start_date, end_date, description})`
TimePeriod nodes: `(:TimePeriod {id, period})`
Relationships: `(:Regime)-[:HAS_ANALOGUE {similarity_score}]->(:Regime)`, `(:Regime)-[:OCCURRED_DURING]->(:TimePeriod)`

### New Qdrant Document Corpus (manual load in v2.0)

Document collections for manually curated corpus (Fed minutes, SBV reports, VN earnings):
- Collection `macro_docs` — Fed minutes, SBV policy statements
- Collection `earnings_docs` — VN company earnings transcripts

Embeddings remain 384-dim FastEmbed (BAAI/bge-small-en-v1.5) — locked from v1.0. LlamaIndex uses `FastEmbedEmbedding` to match existing collection dimensions.

---

## Component Boundaries

| Component | Responsibility | Reads From | Writes To | Does NOT |
|-----------|---------------|------------|-----------|----------|
| n8n (existing) | Fetch, transform, pre-compute, store | External APIs | PostgreSQL, Neo4j, Qdrant | Talk to reasoning-engine |
| data-sidecar (existing) | Data ingestion endpoints for n8n | External APIs, PostgreSQL | PostgreSQL | Talk to reasoning-engine |
| PostgreSQL | Structured storage — OHLCV, fundamentals, structure markers, reports, jobs | — | — | Compute anything |
| Neo4j | Graph storage — regime nodes, analogue relationships | — | — | Compute anything |
| Qdrant | Vector index — document embeddings | — | — | Compute anything |
| LlamaIndex (inside reasoning-engine) | Retrieval abstraction over Neo4j and Qdrant | Neo4j (Cypher), Qdrant (vector search) | — | Call LLM, orchestrate reasoning, write to storage |
| LangGraph (inside reasoning-engine) | Multi-step reasoning state machine | Via LlamaIndex, directly from PostgreSQL | PostgreSQL (reports, report_jobs only) | Fetch external APIs, compute structure markers |
| FastAPI (inside reasoning-engine) | HTTP gateway, async job management, SSE streaming | PostgreSQL (job status, reports), LangGraph (invoke) | PostgreSQL (job status) | Contain business logic |
| Gemini API (external) | LLM inference for all reasoning nodes | Prompt + context assembled by LangGraph nodes | — | Retrieve data, write to storage |

---

## Data Flow: Storage → Retrieval → Reasoning → Output

### Flow 1: Macro Regime Classification

```
LangGraph node: macro_regime
  │
  ├── [RETRIEVAL] LlamaIndex Neo4jPropertyGraphIndex
  │     cypher: MATCH (r:Regime)-[:HAS_ANALOGUE]->(analogue:Regime)
  │             WHERE r conditions match current macro indicators
  │             RETURN r, analogue, similarity_score
  │     current macro indicators sourced from PostgreSQL fred_indicators table
  │     returns: list of historical regime analogues with similarity scores
  │
  ├── [REASONING] Gemini API call
  │     prompt: current macro indicator snapshot + analogue list
  │     output: {regime_label, confidence (0-1), analogue_summary, key_drivers}
  │     structured output via langchain-google-genai with_structured_output()
  │
  └── state["regime"] = {label, confidence, analogues, drivers}
      → passes to valuation node via LangGraph state
```

### Flow 2: Asset Valuation Assessment

```
LangGraph node: valuation
  │
  ├── [RETRIEVAL] PostgreSQL direct query
  │     SELECT pe_ratio, pb_ratio, ps_ratio, roe, dividend_yield
  │     FROM fundamentals
  │     WHERE symbol = {asset_id} ORDER BY data_as_of DESC LIMIT 1
  │     JOIN structure_markers ON symbol WHERE pe_pct_rank, close_pct_rank
  │     returns: current fundamentals + percentile ranks
  │
  ├── [RETRIEVAL] LlamaIndex QdrantVectorStore hybrid search
  │     query: "valuation analysis {regime_label} {asset_sector}"
  │     enable_hybrid=True, sparse_top_k=5, similarity_top_k=3
  │     collection: earnings_docs (company earnings) + macro_docs (analyst context)
  │     returns: relevant document chunks (earnings excerpts, macro context)
  │
  ├── [REASONING] Gemini API call
  │     prompt: fundamentals snapshot + percentile ranks + regime (from state) + doc chunks
  │     output: {valuation_verdict, historical_context, regime_adjustment, narrative}
  │     structured output via with_structured_output()
  │
  └── state["valuation"] = {verdict, context, narrative}
      → passes to structure node via LangGraph state
```

### Flow 3: Price Structure Analysis

```
LangGraph node: structure
  │
  ├── [RETRIEVAL] PostgreSQL direct query
  │     SELECT close, ma_10w, ma_20w, ma_50w,
  │            drawdown_from_ath, drawdown_from_52w_high,
  │            close_pct_rank, data_as_of
  │     FROM structure_markers
  │     WHERE symbol = {asset_id} AND resolution = 'weekly'
  │     ORDER BY data_as_of DESC LIMIT 52  -- last year of weekly markers
  │     returns: pre-computed structure marker series (no computation here)
  │
  ├── [REASONING] Gemini API call
  │     prompt: structure marker series + regime (from state)
  │     output: {trend_quality, ma_alignment, drawdown_context, support_proximity, structure_verdict}
  │     structured output via with_structured_output()
  │
  └── state["structure"] = {trend_quality, ma_alignment, drawdown_context, verdict}
      → passes to entry_quality node via LangGraph state
```

### Flow 4: Entry Quality Scoring

```
LangGraph node: entry_quality
  │
  ├── [NO RETRIEVAL] reads only from LangGraph state
  │     state["regime"]    — macro regime output
  │     state["valuation"] — valuation assessment output
  │     state["structure"] — price structure output
  │
  ├── [REASONING] Gemini API call
  │     prompt: all three prior outputs assembled into synthesis prompt
  │     task: synthesize multi-layer reasoning into entry quality assessment
  │     output: {entry_quality_score (1-10), score_rationale, risk_factors,
  │              thesis_strength, structure_quality, conflicting_signals}
  │     structured output via with_structured_output()
  │
  └── state["entry_quality"] = {score, rationale, risk_factors, conflicts}
      → passes to compose_report node via LangGraph state
```

### Flow 5: Bilingual Report Composition

```
LangGraph node: compose_report
  │
  ├── [NO RETRIEVAL] reads only from LangGraph state
  │     all four prior node outputs
  │
  ├── [REASONING] Gemini API call — Pass 1 (Vietnamese)
  │     prompt: all state outputs + "generate Vietnamese investor narrative"
  │     output: structured report cards in Vietnamese markdown
  │
  ├── [REASONING] Gemini API call — Pass 2 (English)
  │     prompt: all state outputs + "generate English investor narrative"
  │     output: structured report cards in English markdown
  │
  ├── [ASSEMBLY] assemble final report JSON
  │     {
  │       asset_id, generated_at, data_as_of,
  │       regime: {label, confidence, analogues, drivers},
  │       valuation: {verdict, context, narrative},
  │       structure: {trend_quality, ma_alignment, verdict},
  │       entry_quality: {score, rationale, risk_factors, conflicts},
  │       report_markdown_vn: "...",
  │       report_markdown_en: "..."
  │     }
  │
  ├── [WRITE] PostgreSQL INSERT
  │     INSERT INTO reports (...) VALUES (...)
  │     UPDATE report_jobs SET status='complete', report_id=... WHERE id=...
  │
  └── state["report_id"] = new report UUID
      LangGraph graph terminates → FastAPI BackgroundTask completes
```

### Flow 6: Full Report Generation Request Lifecycle

```
Trigger: HTTP POST /reports/generate {asset_id}
  │
  ├── FastAPI: INSERT INTO report_jobs (asset_id, status='queued')
  │            return {job_id, status: "queued"}
  │
  ├── FastAPI BackgroundTask: run_report_pipeline(job_id, asset_id)
  │     │
  │     ├── UPDATE report_jobs SET status='running'
  │     │
  │     ├── PostgreSaver checkpointer connects to postgres
  │     │   thread_id = job_id (unique per report run)
  │     │
  │     ├── LangGraph graph.invoke({asset_id}, config={thread_id})
  │     │     → macro_regime node (Flow 1)
  │     │     → valuation node   (Flow 2)
  │     │     → structure node   (Flow 3)
  │     │     → entry_quality node (Flow 4)
  │     │     → compose_report node (Flow 5)
  │     │
  │     └── UPDATE report_jobs SET status='complete', report_id=...
  │
  └── Parallel: GET /reports/stream/{job_id}
        FastAPI SSE stream — LangGraph emits events per node completion
        Frontend consumes SSE: "macro_regime_complete", "valuation_complete", etc.
```

---

## Recommended Project Structure

```
reasoning/                       # New Docker context — reasoning-engine service
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app — /reports/generate, /reports/{id}, /reports/stream/{id}
│   ├── db.py                    # PostgreSQL connection (SQLAlchemy Core, reuses sidecar pattern)
│   ├── models.py                # Pydantic schemas — ReportRequest, ReportJob, Report
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py             # ReportState TypedDict — all node outputs
│   │   ├── graph.py             # LangGraph StateGraph definition + compilation
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── macro_regime.py  # MacroRegime node — Neo4j retrieval + Gemini call
│   │       ├── valuation.py     # Valuation node — PostgreSQL + Qdrant retrieval + Gemini call
│   │       ├── structure.py     # Structure node — PostgreSQL retrieval + Gemini call
│   │       ├── entry_quality.py # EntryQuality node — state synthesis + Gemini call
│   │       └── compose_report.py # Report node — bilingual generation + PostgreSQL write
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── neo4j_retriever.py   # LlamaIndex Neo4jPropertyGraphIndex wrapper
│   │   └── qdrant_retriever.py  # LlamaIndex QdrantVectorStore hybrid retriever
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py            # GET /health
│   │   └── reports.py           # POST /generate, GET /{id}, GET /stream/{id}
│   └── services/
│       ├── __init__.py
│       ├── pipeline_service.py  # BackgroundTask runner — invokes LangGraph graph
│       └── report_service.py    # PostgreSQL read/write for reports + jobs
│
db/migrations/
├── ...existing V1-V5...
├── V6__reports.sql              # New: reports table
└── V7__report_jobs.sql          # New: report_jobs table
```

**Structure rationale:**
- `graph/nodes/` — one file per LangGraph node keeps reasoning logic isolated and independently testable
- `retrieval/` — LlamaIndex retriever wrappers are separate from node logic; nodes call retriever functions, not LlamaIndex internals directly
- `services/` — mirrors data-sidecar pattern for consistency; pipeline_service owns the BackgroundTask lifecycle
- Mirrors `sidecar/app/` structure so the codebase stays consistent between the two Python services

---

## Architectural Patterns

### Pattern 1: Storage-Boundary Isolation (inherited from v1.0, unchanged)

**What:** n8n and reasoning-engine share no runtime connection. The only interface is the storage layer. n8n writes. reasoning-engine reads (except for reports and report_jobs which it writes).

**When:** Always. This is a hard constraint. `n8n` is on `ingestion` network. `reasoning-engine` is on `reasoning` network. They cannot reach each other by Docker network topology.

**Why:** Decouples ingestion schedule from reasoning schedule. If n8n pipeline fails overnight, an in-progress or queued report is not affected. If reasoning-engine crashes, ingestion continues uninterrupted.

---

### Pattern 2: LangGraph as Explicit State Machine (not a freeform agent)

**What:** A `StateGraph` with five fixed named nodes and explicit edges. Nodes do not autonomously decide to call tools. Each node has a defined input (from state), defined retrieval operations, a defined LLM call, and a defined output (written back to state).

**When:** Always. No `create_react_agent`, no autonomous tool selection.

**Why:** The platform's core value is explainable, reproducible reasoning. A freeform agent produces non-deterministic reasoning paths. The StateGraph guarantees the same five-step structure for every report.

```python
from langgraph.graph import StateGraph, END
from app.graph.state import ReportState
from app.graph.nodes import macro_regime, valuation, structure, entry_quality, compose_report

graph = StateGraph(ReportState)
graph.add_node("macro_regime", macro_regime.run)
graph.add_node("valuation", valuation.run)
graph.add_node("structure", structure.run)
graph.add_node("entry_quality", entry_quality.run)
graph.add_node("compose_report", compose_report.run)

graph.set_entry_point("macro_regime")
graph.add_edge("macro_regime", "valuation")
graph.add_edge("valuation", "structure")
graph.add_edge("structure", "entry_quality")
graph.add_edge("entry_quality", "compose_report")
graph.add_edge("compose_report", END)

compiled = graph.compile(checkpointer=PostgresSaver.from_conn_string(DATABASE_URL))
```

---

### Pattern 3: LlamaIndex as Retrieval Function (not an orchestrator)

**What:** LlamaIndex is called as a Python function inside LangGraph nodes. It does not orchestrate, does not call LLMs for synthesis, and does not produce report content.

**When:** In `macro_regime.py` (Neo4j PropertyGraph retrieval) and `valuation.py` (Qdrant hybrid retrieval).

**Why:** LlamaIndex and LangGraph have overlapping orchestration capabilities. Using LlamaIndex as an orchestrator creates conflicting control flow. Clean division: LangGraph owns orchestration, LlamaIndex owns retrieval.

```python
# retrieval/neo4j_retriever.py
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core import PropertyGraphIndex

def retrieve_regime_analogues(current_indicators: dict) -> list[dict]:
    graph_store = Neo4jPropertyGraphStore(
        username="neo4j",
        password=NEO4J_PASSWORD,
        url=NEO4J_URI,
    )
    # Use LlamaIndex as a thin Cypher execution wrapper
    # LangGraph node passes result to Gemini for interpretation
    ...

# retrieval/qdrant_retriever.py
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever

def retrieve_analyst_context(query: str, collection: str) -> list[str]:
    vector_store = QdrantVectorStore(
        collection_name=collection,
        client=qdrant_client,
        enable_hybrid=True,
        batch_size=20,
    )
    ...
```

---

### Pattern 4: Gemini via langchain-google-genai with Structured Output

**What:** All LLM calls use `ChatGoogleGenerativeAI` from `langchain-google-genai`. Each node uses `.with_structured_output(NodeOutputSchema)` to enforce JSON structure on LLM responses.

**When:** Every node that calls Gemini API (macro_regime, valuation, structure, entry_quality, compose_report).

**Why:** Structured output prevents fragile string parsing. Pydantic schemas validate node outputs before they enter state. Failures surface as validation errors with specific field context, not opaque string parse failures.

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

class MacroRegimeOutput(BaseModel):
    regime_label: str
    confidence: float          # 0.0 to 1.0
    analogue_summary: str
    key_drivers: list[str]
    mixed_signals: list[str]   # conflicting indicators, if any

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,        # "gemini-2.0-flash" default
    temperature=0.2,           # Low temperature for analytical consistency
    google_api_key=GEMINI_API_KEY,
)
structured_llm = llm.with_structured_output(MacroRegimeOutput)
result: MacroRegimeOutput = structured_llm.invoke(prompt)
```

**Note:** Temperature 0.0 causes degraded reasoning on Gemini 2.0+. Use 0.1–0.3 for analytical tasks (not 0.0). [HIGH confidence — Google official docs warn about this.]

---

### Pattern 5: PostgreSQL Checkpointer for LangGraph State Persistence

**What:** `PostgresSaver` from `langgraph-checkpoint-postgres` writes LangGraph checkpoint state to the existing `postgres` service. Each report run uses `thread_id = job_id`.

**When:** Always — the reasoning-engine container is stateless; all state persists to PostgreSQL.

**Why:** If the reasoning-engine container restarts mid-run (VPS reboot, OOM), the checkpoint allows the run to resume from the last completed node rather than restarting. Also provides a full audit trail of intermediate reasoning state per report.

```python
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg

# On startup — create checkpoint tables if not present
with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
    saver = PostgresSaver(conn)
    saver.setup()  # Creates langgraph_checkpoint_* tables — idempotent

# Per report run
with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
    compiled_graph = graph.compile(checkpointer=checkpointer)
    result = compiled_graph.invoke(
        {"asset_id": asset_id},
        config={"configurable": {"thread_id": job_id}}
    )
```

**Caution:** `PostgresSaver.setup()` must be called with `autocommit=True`. The checkpoint tables (`langgraph_checkpoints`, `langgraph_checkpoint_blobs`, `langgraph_checkpoint_writes`) are created in the same PostgreSQL database. Add these to a V8 migration if you want Flyway to own the schema, OR let `setup()` handle it on first run.

---

### Pattern 6: FastAPI BackgroundTask for Long-Running Pipeline

**What:** `POST /reports/generate` returns immediately with a `job_id`. The LangGraph pipeline runs in a `BackgroundTask`. The client polls `GET /reports/stream/{job_id}` via SSE for step-completion events.

**When:** Always — report generation takes 30–120 seconds. FastAPI cannot block the HTTP response for that duration.

**Why:** Single-user VPS scale. BackgroundTask is sufficient. No need for Celery/Redis at this scale. PostgreSQL `report_jobs` table provides persistence — job status survives process restart (unlike in-memory queues).

```python
@app.post("/reports/generate")
async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks, db=Depends(get_db)):
    job_id = create_job_record(db, request.asset_id)
    background_tasks.add_task(run_report_pipeline, job_id, request.asset_id)
    return {"job_id": job_id, "status": "queued"}

@app.get("/reports/stream/{job_id}")
async def stream_report_progress(job_id: str):
    return StreamingResponse(
        report_event_stream(job_id),
        media_type="text/event-stream"
    )
```

---

## Integration Points: Existing Services

| Existing Service | How reasoning-engine connects | What it reads/writes |
|-----------------|-------------------------------|---------------------|
| `postgres` | SQLAlchemy Core (direct query) + PostgresSaver (checkpointer) | Reads: fundamentals, structure_markers, fred_indicators. Writes: reports, report_jobs, langgraph checkpoints |
| `neo4j` | LlamaIndex `Neo4jPropertyGraphStore` via bolt://neo4j:7687 | Reads: Regime nodes, TimePeriod nodes, HAS_ANALOGUE relationships |
| `qdrant` | LlamaIndex `QdrantVectorStore` via qdrant:6333 with API key | Reads: macro_docs, earnings_docs vector collections |
| `n8n` | No direct connection — storage boundary enforced by network | None |
| `data-sidecar` | No direct connection — ingestion network only | None |

---

## Build Order (v2.0 Phase Dependencies)

The dependency chain is strict. Each phase requires the prior to be complete and verified.

```
Phase 1: Database Migrations (V6, V7)
  └── Add V6__reports.sql and V7__report_jobs.sql
  └── Run Flyway migrate against existing postgres
  WHY FIRST: reasoning-engine service startup will fail if tables don't exist.
             Do this before writing a single line of reasoning-engine code.

Phase 2: Neo4j Regime Data Population
  └── Write n8n workflow or manual Cypher to populate:
      Regime nodes (historical macro regimes)
      TimePeriod nodes
      HAS_ANALOGUE relationships with similarity_score
  WHY SECOND: MacroRegime node cannot retrieve analogues from an empty graph.
              Retrieval quality must be validated independently before wiring into LangGraph.

Phase 3: Qdrant Document Corpus Load
  └── Manually embed and upsert Fed minutes, SBV reports, VN earnings into:
      macro_docs collection (existing)
      earnings_docs collection (existing)
  └── Use BAAI/bge-small-en-v1.5 FastEmbed — 384-dim, locked from v1.0
  WHY THIRD: Valuation node cannot retrieve analyst context without document corpus.
             Test retrieval quality with direct LlamaIndex queries before LangGraph wiring.

Phase 4: Retrieval Layer (LlamaIndex wrappers)
  └── Build reasoning/app/retrieval/neo4j_retriever.py — test with manual queries
  └── Build reasoning/app/retrieval/qdrant_retriever.py — test hybrid search quality
  WHY FOURTH: Retrieval bugs are hard to isolate inside a running LangGraph graph.
              Verify retrieval returns relevant content before embedding in nodes.

Phase 5: LangGraph Nodes (one at a time, bottom-up)
  └── structure.py  — PostgreSQL-only, no LLM retrieval, simplest node, test first
  └── valuation.py  — PostgreSQL + Qdrant retrieval + Gemini call
  └── macro_regime.py — Neo4j retrieval + Gemini call
  └── entry_quality.py — state synthesis + Gemini call, no retrieval
  └── compose_report.py — bilingual generation + PostgreSQL write
  WHY THIS ORDER: Start with the node that has fewest dependencies (structure).
                  Test each node in isolation with mock state before wiring into graph.

Phase 6: LangGraph Graph Assembly
  └── Assemble state.py (ReportState TypedDict)
  └── Assemble graph.py (StateGraph with all five nodes)
  └── Wire PostgresSaver checkpointer
  └── End-to-end test: single asset, full pipeline, inspect PostgreSQL reports table
  WHY SIXTH: Only assemble the graph after each node is independently verified.

Phase 7: FastAPI reasoning-engine Service
  └── Implement /reports/generate (BackgroundTask wrapper over LangGraph)
  └── Implement /reports/{id} (read from PostgreSQL reports table)
  └── Implement /reports/stream/{id} (SSE via LangGraph astream_events)
  └── Implement /health
  └── Build Dockerfile + add reasoning-engine to docker-compose.yml
  WHY LAST IN THIS MILESTONE: FastAPI is a thin gateway. Cannot build endpoints
                              without the LangGraph pipeline being functional.
                              v2.0 milestone ends here. Frontend is v3.0.
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Computing Metrics Inside LangGraph Nodes

**What people do:** Pull raw OHLCV rows inside a LangGraph node and compute moving averages, drawdown, or percentile ranks during report generation.

**Why it's wrong:** Adds 5–30 seconds of computation per node, duplicates logic that already lives in the data-sidecar, and makes nodes dependent on raw data rather than pre-computed outputs. Violates the pre-computation constraint.

**Do this instead:** The `structure` node reads from `structure_markers` table — everything is pre-computed. `SELECT ma_20w, drawdown_from_ath, close_pct_rank FROM structure_markers WHERE symbol = ? ORDER BY data_as_of DESC LIMIT 52`. Zero computation in the node.

---

### Anti-Pattern 2: Single Monolithic LLM Prompt for Full Report

**What people do:** One large Gemini call receiving all data (macro indicators, fundamentals, structure markers, document chunks) and asked to produce the full report.

**Why it's wrong:** No intermediate state to inspect. Cannot attribute which conclusion derives from which source. Violates explainability requirement. Large context degrades Gemini output quality. Cannot partially resume from a checkpoint.

**Do this instead:** Five distinct nodes, each with a scoped prompt. Each node's output is stored in `ReportState` and is a fully inspectable dict. The checkpointer saves state after each node completes.

---

### Anti-Pattern 3: Using LlamaIndex QueryEngine for Reasoning

**What people do:** Use LlamaIndex `QueryEngine` or `RouterQueryEngine` as the top-level reasoning loop, routing questions to different backends based on query type.

**Why it's wrong:** LlamaIndex routing is designed for document Q&A, not structured multi-step analysis with explicit state. The RouterQueryEngine does not guarantee the macro → valuation → structure → entry_quality sequence. Makes the reasoning path non-deterministic and non-inspectable.

**Do this instead:** LangGraph defines the sequence. LlamaIndex is called as a Python function within nodes. The retrieval result is a list of strings that the node assembles into a prompt. LlamaIndex does not call the LLM.

---

### Anti-Pattern 4: In-Memory Report State in FastAPI

**What people do:** Store generated report content in a FastAPI global dict keyed by `job_id`, accessed by the GET endpoint.

**Why it's wrong:** State lost on process restart (VPS reboots). Cannot serve report after container redeploy. Memory leak risk on a long-running VPS process.

**Do this instead:** Write completed reports to PostgreSQL `reports` table in the `compose_report` node. `GET /reports/{id}` queries the database. FastAPI is stateless.

---

### Anti-Pattern 5: Separate LangGraph Server Container

**What people do:** Run LangGraph as a separate container (using `langchain/langgraph-api` Docker image) alongside a FastAPI container, connecting them over HTTP.

**Why it's wrong:** The `langchain/langgraph-api` server is designed for the LangGraph Cloud platform subscription. At single-user VPS scale, it adds networking overhead, requires licensing consideration, and duplicates the FastAPI layer. The official pattern for self-hosted is FastAPI importing LangGraph as a Python library.

**Do this instead:** FastAPI and LangGraph run in the same `reasoning-engine` container. FastAPI invokes the compiled LangGraph graph directly via `graph.invoke()` or `graph.astream_events()`. State persists to PostgreSQL via `PostgresSaver`, so the process is effectively stateless.

---

## Scaling Considerations

This platform is single-user at launch. These notes are for future reference only — do not implement prematurely.

| Concern | Single User (v2.0) | Multi-User (v3.0+) |
|---------|-------------------|--------------------|
| Report generation concurrency | FastAPI BackgroundTask — one report at a time is fine | Add Celery + Redis task queue; multiple reasoning-engine workers |
| LangGraph state isolation | `thread_id = job_id` — each report has unique thread | `thread_id = f"{user_id}_{job_id}"` for multi-user isolation |
| Database connection pooling | SQLAlchemy `create_engine` with pool_size=5 sufficient | Increase pool_size; consider PgBouncer proxy |
| Gemini API rate limits | 15 calls per report × single user = trivial | Add per-user rate limiting; consider Gemini Pro tier |
| Neo4j memory | 512MB heap / 512MB pagecache (existing config) | Sufficient through ~10K regime analogue nodes |
| Qdrant | 384-dim, manual corpus = small; memory sufficient | No change needed until corpus exceeds ~100K documents |

---

## Requirements Summary

```
# reasoning/requirements.txt (new)
langgraph>=0.3.0
langgraph-checkpoint-postgres>=3.0.0
langchain-google-genai>=2.1.0
langchain-core>=0.3.0
llama-index-core>=0.12.0
llama-index-graph-stores-neo4j>=0.3.0
llama-index-vector-stores-qdrant>=0.3.0
llama-index-embeddings-fastembed>=0.3.0
fastapi>=0.115.0
uvicorn>=0.30.0
sqlalchemy>=2.0.0
psycopg[binary,pool]>=3.2.0
psycopg2-binary>=2.9.9   # for existing SQLAlchemy patterns
qdrant-client>=1.9.0
neo4j>=5.20.0
python-dotenv>=1.0.0
pydantic>=2.0.0
httpx>=0.27.0
```

**Key version note:** `psycopg[binary,pool]` (psycopg3) is required for `PostgresSaver`. The existing `data-sidecar` uses `psycopg2-binary` (psycopg2). Both can coexist. The reasoning-engine uses psycopg3 for the checkpointer and can use psycopg2 for direct SQLAlchemy queries if the existing db.py pattern is copied.

---

## Sources

- [LangGraph StateGraph Official Docs — LangChain](https://docs.langchain.com/oss/python/langgraph/add-memory) — HIGH confidence (official)
- [langgraph-checkpoint-postgres PyPI v3.0.2](https://pypi.org/project/langgraph-checkpoint-postgres/) — HIGH confidence (official package)
- [Gemini + LangGraph Official Example (Google AI, Feb 2026)](https://ai.google.dev/gemini-api/docs/langgraph-example) — HIGH confidence (Google official)
- [langchain-google-genai Reference](https://reference.langchain.com/python/integrations/langchain_google_genai/) — HIGH confidence (LangChain official)
- [LlamaIndex Neo4j PropertyGraph Integration (Neo4j Labs)](https://neo4j.com/labs/genai-ecosystem/llamaindex/) — HIGH confidence (official Neo4j)
- [LlamaIndex QdrantVectorStore Hybrid Search (official docs)](https://docs.llamaindex.ai/en/stable/examples/vector_stores/qdrant_hybrid/) — HIGH confidence (official LlamaIndex)
- [GraphRAG with Qdrant and Neo4j (Qdrant official)](https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/) — HIGH confidence (official Qdrant)
- [LlamaIndex + Qdrant Integration Guide (Qdrant official)](https://qdrant.tech/documentation/frameworks/llama-index/) — HIGH confidence (official Qdrant)
- [FastAPI + LangGraph Production Pattern (Zestminds, 2025)](https://www.zestminds.com/blog/build-ai-workflows-fastapi-langgraph/) — MEDIUM confidence (verified against official patterns)
- [PostgreSQL Checkpointer + Docker Compose (LangGraph discussion #3691)](https://github.com/langchain-ai/langgraph/discussions/3691) — MEDIUM confidence (community, verified against official checkpointer docs)

---

*Architecture research for: Stratum v2.0 — Analytical Reasoning Engine*
*Researched: 2026-03-09*
