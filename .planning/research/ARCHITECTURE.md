# Architecture Patterns

**Domain:** Long-term investment advisor platform (macro-fundamental analysis, AI reasoning pipeline)
**Researched:** 2026-03-03
**Confidence:** MEDIUM-HIGH

---

## Recommended Architecture

The platform is a **two-pipeline system** separated at a hard storage boundary. Ingestion (n8n) and reasoning (LangGraph/LlamaIndex) are fully decoupled — they share only persistent storage, never runtime state or direct API calls. FastAPI surfaces reasoning pipeline output to the frontend. The frontend (Next.js + Supabase) is a thin rendering layer.

```
+----------------------------------------------------------+
|  INGESTION PIPELINE  (n8n)                               |
|                                                          |
|  Data Sources                 Storage Writers            |
|  vnstock ─────────────────►  PostgreSQL (OHLCV, fundamentals)
|  FRED / Simfin ───────────►  PostgreSQL (macro series)   |
|  World Gold Council ──────►  PostgreSQL (gold data)      |
|  Earnings transcripts ────►  Qdrant (vector embeddings)  |
|  Fed minutes ─────────────►  Qdrant (vector embeddings)  |
|  Macro relationships ─────►  Neo4j (regime graph)        |
|                                                          |
|  Pre-computation (in n8n before write):                  |
|  - Moving averages (20, 50, 200 week/month)              |
|  - Drawdown from ATH                                     |
|  - Valuation percentile rank vs historical range         |
|  - Structure markers written to PostgreSQL               |
+----------------------------------------------------------+
                        |
              STORAGE BOUNDARY (read-only to reasoning)
                        |
+----------------------------------------------------------+
|  STORAGE LAYER                                           |
|                                                          |
|  PostgreSQL ── structured time-series, fundamentals,     |
|               pre-computed structure markers             |
|  Neo4j      ── macro regime graph, historical analogues, |
|               asset correlations, relationship traversal |
|  Qdrant     ── semantic vectors (transcripts, minutes,   |
|               narrative macro documents)                 |
+----------------------------------------------------------+
                        |
              STORAGE BOUNDARY (read-only from ingestion)
                        |
+----------------------------------------------------------+
|  REASONING PIPELINE  (LangGraph + LlamaIndex)            |
|                                                          |
|  LangGraph StateGraph                                    |
|  ├── Node: MacroRegimeClassifier                         |
|  │   └── reads Neo4j via LlamaIndex graph retriever      |
|  │   └── outputs: regime label + confidence + analogues  |
|  ├── Node: ValuationContextualizer                       |
|  │   └── reads PostgreSQL (fundamentals, percentiles)    |
|  │   └── reads Qdrant via LlamaIndex RAG (analyst docs)  |
|  │   └── outputs: valuation assessment vs regime         |
|  ├── Node: StructureAnalyzer                             |
|  │   └── reads PostgreSQL (pre-computed structure markers)|
|  │   └── outputs: price structure quality assessment     |
|  ├── Node: EntryQualityScorer                            |
|  │   └── receives outputs from all 3 above nodes         |
|  │   └── synthesizes multi-layer reasoning               |
|  │   └── outputs: entry quality score + explanation      |
|  └── Node: ReportComposer                                |
|      └── assembles full research report in card format   |
|      └── generates bilingual (VN + EN) output            |
|      └── writes report to PostgreSQL (reports table)     |
|                                                          |
|  LlamaIndex (retrieval layer called by LangGraph nodes)  |
|  ├── GraphRAGRetriever → Neo4j                           |
|  └── HybridRetriever   → Qdrant (dense + sparse)         |
+----------------------------------------------------------+
                        |
+----------------------------------------------------------+
|  API LAYER  (FastAPI)                                    |
|                                                          |
|  POST /reports/generate  — triggers LangGraph pipeline   |
|  GET  /reports/{id}      — fetch stored report           |
|  GET  /reports/stream    — SSE stream for pipeline steps |
|  GET  /watchlist         — user watchlist CRUD           |
|  POST /watchlist         — add asset to watchlist        |
|                                                          |
|  JWT validation via Supabase public key                  |
|  Long-running jobs: FastAPI BackgroundTasks + job table  |
+----------------------------------------------------------+
                        |
+----------------------------------------------------------+
|  FRONTEND  (Next.js + Supabase Auth)                     |
|                                                          |
|  Auth: Supabase (@supabase/ssr) → JWT passed to FastAPI  |
|  Pages: Report viewer, Watchlist manager, Report history |
|  Charts: TradingView Lightweight Charts (OHLCV overlay)  |
|  SSE consumer: streams reasoning step progress           |
+----------------------------------------------------------+
```

---

## Component Boundaries

| Component | Responsibility | Reads From | Writes To | Does NOT |
|-----------|---------------|------------|-----------|----------|
| n8n Ingestion | Fetch, schedule, transform, pre-compute, store | External APIs (vnstock, FRED, WGC) | PostgreSQL, Neo4j, Qdrant | Talk to LangGraph, FastAPI, or frontend |
| PostgreSQL | Structured time-series, fundamentals, pre-computed markers, reports | — | — | Compute anything |
| Neo4j | Macro regime graph, analogues, asset correlations | — | — | Compute anything |
| Qdrant | Semantic vector index over unstructured documents | — | — | Compute anything |
| LlamaIndex | Retrieval abstraction over Qdrant (RAG) and Neo4j (graph) | Qdrant, Neo4j | — | Reason, schedule, or write to storage |
| LangGraph | Multi-step reasoning graph, state machine, report composition | Via LlamaIndex, directly from PostgreSQL | PostgreSQL (reports table only) | Fetch from external APIs, compute structure markers |
| FastAPI | Async HTTP gateway, job management, SSE streaming | PostgreSQL (reports), LangGraph (trigger) | PostgreSQL (job status) | Contain business logic |
| Supabase | Auth, JWT issuance | — | User records | Touch investment data |
| Next.js | Report rendering, watchlist UI, SSE consumer | FastAPI API | — | Talk to database directly |

---

## Data Flow

### Flow 1: Scheduled Data Ingestion (n8n cron, weekly/monthly)

```
External API (vnstock / FRED / WGC)
  → n8n HTTP node: fetch raw data
  → n8n Code node: transform + normalize
  → n8n Code node: pre-compute structure markers (MAs, drawdown, valuation percentile)
  → n8n PostgreSQL node: upsert time-series rows
  → (if document type) n8n Embedding node: embed text
  → n8n Qdrant node: upsert vector documents
  → (if relationship type) n8n Cypher template: MERGE nodes/relationships
  → n8n Neo4j HTTP node: execute Cypher
```

**Key rule:** All computations (moving averages, drawdown from ATH, percentile rank) happen inside n8n Code nodes before the write. Nothing is computed by LangGraph at reasoning time.

---

### Flow 2: Report Generation (user triggers or monthly cron)

```
User (Next.js) → POST /reports/generate {asset_id, user_id}
  → FastAPI: validate JWT via Supabase, create job record in PostgreSQL
  → FastAPI BackgroundTask: invoke LangGraph graph
    → LangGraph: MacroRegimeClassifier node
        → LlamaIndex GraphRetriever → Neo4j Cypher traversal
        → returns regime label, confidence, analogue list
    → LangGraph: ValuationContextualizer node
        → PostgreSQL query: fundamentals, percentile markers
        → LlamaIndex HybridRetriever → Qdrant dense+sparse search
        → returns valuation assessment with regime context
    → LangGraph: StructureAnalyzer node
        → PostgreSQL query: pre-computed MA markers, drawdown, ATH distance
        → returns structure quality (trend, support proximity, risk level)
    → LangGraph: EntryQualityScorer node
        → receives all three outputs via LangGraph State
        → LLM synthesizes multi-layer reasoning + produces score + explanation
    → LangGraph: ReportComposer node
        → assembles structured report cards (macro, valuation, structure, entry quality)
        → generates bilingual (VN + EN) narrative
        → writes completed report to PostgreSQL reports table
    → FastAPI: update job status to complete, return report_id
  → FastAPI SSE stream: emits step-completion events to frontend during execution
User (Next.js) → GET /reports/{id} → render report
```

---

### Flow 3: SSE Step Streaming (during report generation)

```
LangGraph node emits: stream_writer("macro_regime_complete", {regime, confidence})
  → FastAPI astream_events() loop
  → SSE chunk to Next.js client
  → Frontend renders step progress card in real-time
```

This allows the UI to show "Analyzing macro regime... done. Assessing valuation..." while the pipeline runs (which may take 30–120 seconds for a full report).

---

## Patterns to Follow

### Pattern 1: Storage-Boundary Isolation

**What:** n8n and LangGraph share no runtime connection. The only interface between them is the storage layer: PostgreSQL, Neo4j, Qdrant. n8n writes. LangGraph reads.

**When:** Always. This is a hard architectural constraint (from PROJECT.md).

**Why:** Prevents tight coupling between the ingestion schedule and the reasoning schedule. Ingestion can fail, retry, or be modified without affecting in-progress reasoning runs. Reasoning can be triggered independently of ingestion cadence.

**Example:**
```
# Wrong: LangGraph calling n8n API or triggering a fetch
# Wrong: n8n calling LangGraph to pass raw data

# Correct:
# n8n writes OHLCV row to PostgreSQL with pre-computed markers
# LangGraph reads that row from PostgreSQL when generating report
```

---

### Pattern 2: Pre-Computation at Ingestion Time

**What:** All derived values (moving averages, drawdown from ATH, valuation percentile ranks) are computed during the n8n ingestion step before writing to storage.

**When:** Any time a metric is derivable from raw data and used by the reasoning pipeline.

**Why:** Eliminates latency and compute overhead at report generation time. Report generation should be reading + reasoning, not computing. Also isolates mathematical errors to the ingestion layer where they are easier to debug and retrigger.

**Example:**
```python
# n8n Code node (pre-write computation)
ma_20w = compute_moving_average(prices, window=20)
drawdown_from_ath = (current_price - ath) / ath
valuation_percentile = percentile_rank(current_pe, historical_pe_series)

# Write all of these alongside the raw row
row = {
    "date": date,
    "close": current_price,
    "ma_20w": ma_20w,
    "drawdown_from_ath": drawdown_from_ath,
    "valuation_percentile_pe": valuation_percentile
}
```

---

### Pattern 3: LangGraph as Explicit State Machine (Not a Freeform Agent)

**What:** LangGraph graph is a defined StateGraph with named nodes and explicit edges. Nodes do not autonomously decide to call tools — each node has a specific function and defined outputs that flow to specific next nodes.

**When:** Always. Avoid "ReAct" or fully autonomous tool-calling agents for the core reasoning pipeline.

**Why:** This platform's core value is explainable multi-step reasoning. A freeform agent that decides which tools to call produces non-reproducible, hard-to-audit reasoning paths. A defined state machine guarantees the same reasoning structure every time, with every step producing a traceable output.

**Example state machine nodes:**
```python
graph = StateGraph(ReportState)
graph.add_node("macro_regime", classify_macro_regime)
graph.add_node("valuation", assess_valuation)
graph.add_node("structure", analyze_price_structure)
graph.add_node("entry_quality", score_entry_quality)
graph.add_node("compose_report", compose_bilingual_report)

graph.add_edge("macro_regime", "valuation")
graph.add_edge("valuation", "structure")
graph.add_edge("structure", "entry_quality")
graph.add_edge("entry_quality", "compose_report")
graph.add_edge("compose_report", END)
```

---

### Pattern 4: LlamaIndex as Retrieval Abstraction Only

**What:** LlamaIndex is used exclusively as a retrieval layer — it does not orchestrate reasoning, does not call LLMs for synthesis, and does not produce report content. LangGraph calls LlamaIndex retrievers as tool functions within nodes.

**When:** Whenever a LangGraph node needs to retrieve from Qdrant (semantic) or Neo4j (graph traversal).

**Why:** LlamaIndex and LangGraph have overlapping capabilities. Using LlamaIndex as an orchestrator creates conflicting control flow. The clean division: LangGraph owns reasoning orchestration, LlamaIndex owns retrieval.

**Example:**
```python
# In a LangGraph node — LlamaIndex is a retrieval function, not an orchestrator
def classify_macro_regime(state: ReportState) -> ReportState:
    # Graph retrieval via LlamaIndex
    regime_context = graph_retriever.retrieve(
        f"macro regime analogues for {state['current_macro_conditions']}"
    )
    # Reasoning via LLM (called directly or via LangChain)
    regime_result = llm.invoke(REGIME_PROMPT.format(context=regime_context))
    state["regime"] = regime_result
    return state
```

---

### Pattern 5: FastAPI BackgroundTask for Long-Running Pipeline

**What:** Report generation is invoked as a FastAPI BackgroundTask. The HTTP endpoint immediately returns a job ID. The frontend polls or subscribes to SSE for progress.

**When:** For any operation taking more than ~2 seconds (report generation takes 30–120 seconds).

**Why:** FastAPI's synchronous request-response model is incompatible with LangGraph pipeline durations. BackgroundTask decouples HTTP response from pipeline completion.

```python
@app.post("/reports/generate")
async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
    job_id = create_job_record(db, request)
    background_tasks.add_task(run_report_pipeline, job_id, request)
    return {"job_id": job_id, "status": "queued"}

@app.get("/reports/stream/{job_id}")
async def stream_progress(job_id: str):
    return StreamingResponse(
        report_event_stream(job_id),
        media_type="text/event-stream"
    )
```

---

### Pattern 6: Supabase JWT Verification in FastAPI (Not Session Passthrough)

**What:** Next.js sends the Supabase JWT access token in the Authorization header. FastAPI verifies it against the Supabase public JWT key. FastAPI never calls Supabase Auth API for every request — it verifies locally.

**When:** Every authenticated FastAPI endpoint.

**Why:** Supabase Auth is the source of truth. FastAPI must verify JWTs but does not manage sessions. The Supabase user UUID extracted from the JWT is used as the foreign key in PostgreSQL and Neo4j user-scoped records.

```python
# FastAPI JWT dependency
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    return payload["sub"]  # Supabase UUID
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: LangGraph Computing Raw Metrics

**What:** LangGraph nodes computing moving averages, drawdown, or percentile ranks from raw OHLCV data.

**Why bad:** Increases report generation latency, duplicates logic that should live in n8n, makes reasoning nodes harder to test (need to seed raw data rather than pre-computed values). Violates the pre-computation constraint from PROJECT.md.

**Instead:** n8n pre-computes all numeric metrics before writing to PostgreSQL. LangGraph only reads the pre-computed columns.

---

### Anti-Pattern 2: LlamaIndex as Reasoning Orchestrator

**What:** Using LlamaIndex's QueryEngine or AgentRunner as the top-level reasoning loop, with LangGraph demoted to a subcomponent or not used.

**Why bad:** LlamaIndex's reasoning abstractions are optimized for document Q&A, not multi-step structured analysis. The report requires a specific sequence of reasoning steps (regime → valuation → structure → entry quality) with explicit state passing between steps. LlamaIndex QueryEngine is opaque about what reasoning steps were taken, which violates the explainability requirement.

**Instead:** LangGraph is the orchestrator. LlamaIndex is called as a retrieval function inside LangGraph nodes.

---

### Anti-Pattern 3: n8n Calling LangGraph Directly to Pass Raw Data

**What:** n8n workflow fetches data and makes an HTTP call to FastAPI/LangGraph to pass raw data for processing in the same ingestion run.

**Why bad:** Couples ingestion timing to reasoning availability. If LangGraph API is down during ingestion, data is lost. Creates a synchronous dependency where n8n must wait for reasoning completion. Defeats the purpose of the storage boundary.

**Instead:** n8n writes to storage. Reasoning is triggered separately (by user request or a separate cron) and reads from storage.

---

### Anti-Pattern 4: Single Monolithic LLM Prompt for Full Report

**What:** One large LLM prompt that receives all data (macro, valuation, structure) and produces the full report in a single call.

**Why bad:** No intermediate steps to inspect or debug. Cannot attribute which part of the analysis is based on which data source. Violates the explainability requirement. Large context windows increase cost and reduce precision. Cannot partially rerun a failed step.

**Instead:** LangGraph StateGraph with distinct nodes, each responsible for one reasoning layer. Each node's output is stored in state and is inspectable.

---

### Anti-Pattern 5: FastAPI Storing Large Report Content In-Memory

**What:** Keeping generated report content in FastAPI process memory, accessed via an in-memory dict keyed by job_id.

**Why bad:** Single-instance state does not survive process restart. Cannot scale to multiple workers. Memory leak risk for long-running process on a VPS.

**Instead:** Write completed reports to PostgreSQL reports table. FastAPI retrieves reports via database query, not in-memory state.

---

## Build Order (Phase Dependencies)

The architecture has clear build-order dependencies. Each layer depends on the one below it being stable.

```
Phase 1: Storage Foundation
  └─ PostgreSQL schema (OHLCV, fundamentals, structure markers, reports, jobs)
  └─ Neo4j schema (regime nodes, analogue relationships)
  └─ Qdrant collections (transcripts, macro docs)
  └─ Docker Compose (all three databases + n8n + FastAPI on VPS)
  └─ Supabase project (auth, user table)
  WHY FIRST: All other components depend on these being accessible.

Phase 2: Ingestion Pipeline (n8n)
  └─ Depends on: Phase 1 (storage)
  └─ vnstock → PostgreSQL OHLCV
  └─ FRED → PostgreSQL macro series
  └─ World Gold Council → PostgreSQL gold data
  └─ Pre-computation nodes (MA, drawdown, percentile)
  └─ Document embedding → Qdrant
  └─ Regime relationship population → Neo4j
  WHY SECOND: LangGraph cannot reason without data. Must have populated storage
              before reasoning pipeline is tested end-to-end.

Phase 3: Retrieval Layer (LlamaIndex)
  └─ Depends on: Phase 1 (populated Qdrant + Neo4j)
  └─ Qdrant hybrid retriever (dense + sparse)
  └─ Neo4j graph retriever (Cypher-based)
  └─ Retrieval quality validation (test queries before wiring into LangGraph)
  WHY THIRD: Retrieval must be verified independently before being embedded
             into LangGraph nodes. Retrieval bugs are hard to debug from inside
             a multi-node reasoning graph.

Phase 4: Reasoning Pipeline (LangGraph)
  └─ Depends on: Phase 2 (populated storage), Phase 3 (retrieval verified)
  └─ MacroRegimeClassifier node
  └─ ValuationContextualizer node
  └─ StructureAnalyzer node
  └─ EntryQualityScorer node
  └─ ReportComposer node (bilingual output)
  └─ PostgreSQL checkpointer for LangGraph state persistence
  WHY FOURTH: Cannot build reasoning nodes without verified data and retrieval.

Phase 5: API Layer (FastAPI)
  └─ Depends on: Phase 4 (working LangGraph graph)
  └─ Report generation endpoint with BackgroundTask
  └─ SSE streaming endpoint
  └─ Report retrieval endpoints
  └─ Watchlist CRUD endpoints
  └─ Supabase JWT verification middleware
  WHY FIFTH: FastAPI is a thin gateway. Cannot build endpoints without the
             pipeline they invoke being functional.

Phase 6: Frontend (Next.js)
  └─ Depends on: Phase 5 (FastAPI endpoints working)
  └─ Supabase Auth integration (SSR)
  └─ Report rendering (card layout)
  └─ SSE step-progress UI
  └─ Watchlist management UI
  └─ TradingView Lightweight Charts integration
  WHY LAST: Frontend has no value until all backend layers function. Build
            late to avoid wasted UI iteration on unstable API shapes.
```

---

## Scalability Considerations

This platform is explicitly single-user at launch (PROJECT.md: "single user (self) at launch"). Scalability considerations are noted for future productization, not immediate implementation.

| Concern | Single User (now) | Multi-User (later) |
|---------|-------------------|--------------------|
| Report generation concurrency | FastAPI BackgroundTask sufficient | Add Celery/Redis task queue |
| Database isolation | One PostgreSQL schema | Schema-per-tenant or row-level Supabase RLS |
| LangGraph state | PostgreSQL checkpointer with single thread_id per report | thread_id includes user_id for isolation |
| n8n pipeline | Single cron workflow per data source | Add asset-scoped workflow parameterization |
| API authentication | Supabase JWT (already multi-user capable) | No change needed |
| Report storage | PostgreSQL reports table | Add CDN for rendered report assets |

---

## Sources

- [LangGraph Production Patterns (LangChain official)](https://docs.langchain.com/oss/python/langgraph/persistence) — MEDIUM confidence (official docs)
- [LangGraph + FastAPI SSE Streaming Guide 2025-26](https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn) — MEDIUM confidence (verified with official patterns)
- [n8n + LangGraph Separation Pattern (Samir Saci)](https://www.samirsaci.com/build-an-ai-agent-for-strategic-budget-planning-with-langgraph-and-n8n/) — MEDIUM confidence (verified against architecture)
- [LlamaIndex + Neo4j Integration (Neo4j Labs)](https://neo4j.com/labs/genai-ecosystem/llamaindex/) — HIGH confidence (official Neo4j documentation)
- [Qdrant Hybrid Search with LlamaIndex (official docs)](https://docs.llamaindex.ai/en/stable/examples/vector_stores/qdrant_hybrid/) — HIGH confidence (official LlamaIndex docs)
- [langgraph-checkpoint-postgres (PyPI)](https://pypi.org/project/langgraph-checkpoint-postgres/) — HIGH confidence (official package)
- [Supabase Auth with Next.js SSR (official docs)](https://supabase.com/docs/guides/auth/server-side/nextjs) — HIGH confidence (official Supabase docs)
- [Supabase + Next.js + FastAPI JWT pattern](https://medium.com/@ojasskapre/implementing-supabase-authentication-with-next-js-and-fastapi-5656881f449b) — LOW confidence (single source, not official)
- [Investment Platform Independence Architecture](https://blog.joshsoftware.com/2025/12/31/why-independence-matters-more-than-scale-in-investment-software-architecture/) — MEDIUM confidence (domain-specific validation)
- [Multi-Agent RAG for Investment Advisory (ResearchGate)](https://www.researchgate.net/publication/390816837_Transforming_Investment_Advisory_with_Multi-Agent_RAG_Architectures_A_Design_Science_Approach) — MEDIUM confidence (academic, validates pattern)
