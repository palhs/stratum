# Project Research Summary

**Project:** Stratum v2.0 — Analytical Reasoning Engine
**Domain:** AI-powered macro regime classification, multi-store RAG retrieval, and bilingual investment report generation layered over an operational v1.0 data ingestion platform
**Researched:** 2026-03-09
**Confidence:** HIGH (stack verified against PyPI and official docs; architecture confirmed against existing codebase; pitfalls cross-verified across official docs and community post-mortems)

---

## Executive Summary

Stratum v2.0 adds an AI analytical reasoning engine on top of a fully operational v1.0 data ingestion platform. The architecture is additive, not a rewrite: one new Docker service (`reasoning-engine`) joins an existing Docker Compose stack and attaches to the pre-existing `reasoning` network. The storage layer (PostgreSQL, Neo4j, Qdrant) is already dual-networked and requires no structural changes — only new data (Neo4j regime nodes, Qdrant document corpus) and two new Flyway migrations (V6 `reports`, V7 `report_jobs`). The recommended technical pattern is LangGraph (explicit StateGraph, not an autonomous agent) orchestrating LlamaIndex retrievers as deterministic Python functions, with Gemini 2.0/2.5 Flash as the LLM for structured analytical output. This is the dominant production pattern for analytical AI systems as of 2025–2026, with clear library boundaries: LangGraph owns orchestration, LlamaIndex owns retrieval, Gemini owns inference.

The platform's core intellectual property is macro regime classification with historical analogue matching — a capability absent from all Vietnamese retail investment platforms (Vietstock, CafeF) and from general-purpose platforms (Simply Wall St, Stockopedia). The pipeline runs five sequential LangGraph nodes (macro_regime → valuation → structure → entry_quality → compose_report), each producing Pydantic-validated structured output that feeds downstream nodes through explicit state. Bilingual output (Vietnamese primary, English secondary) is generated natively from structured data using Gemini — not by translating English output — with a mandatory Vietnamese financial term dictionary as a content prerequisite. The entry quality assessment intentionally outputs a qualitative tier (Favorable / Neutral / Cautious / Avoid), not a numeric score, to prevent false precision from propagating to investment decisions.

The dominant risk category is data integrity, not engineering complexity. Three independent failure modes can silently corrupt reports: LLM hallucination of financial numbers, stale data presented as current, and LangGraph state reducer misuse that silently corrupts intermediate analysis. All three require defensive patterns built into the architecture from the first node — a grounding check node, `data_as_of` freshness gates, and explicit `TypedDict` reducer annotations with unit tests per node. A second major risk is infrastructure: an 8GB VPS running 7+ Docker services requires explicit memory limits, VPS swap, and Neo4j JVM heap configuration before the reasoning service is added. Missing any of these produces OOM kills of random services rather than the reasoning engine that triggered the spike.

---

## Key Findings

### Recommended Stack

The v2.0 stack builds entirely on libraries that reached stable production quality in late 2025. LangGraph reached v1.0 stable GA in October 2025 (current: 1.0.10, Feb 27, 2026); `langchain-google-genai` v4.0.0 (February 2026) completed the mandatory migration from the deprecated `google-generativeai` SDK to `google-genai`; `llama-index-core` 0.14.15 (February 2026) provides the unified retrieval abstraction. These are not experimental choices — they are the officially recommended integration path per Google AI, Neo4j Labs, and Qdrant documentation as of March 2026.

**Core technologies:**
- `langgraph==1.0.10`: Explicit StateGraph orchestration — five named nodes with deterministic linear edges. Required over autonomous agent frameworks because the analytical sequence (macro → valuation → structure → entry quality) must be fixed and auditable for every report.
- `langchain-google-genai>=4.0.0`: Gemini integration for LangGraph nodes. Provides `bind_tools()` and `.with_structured_output()` that LangGraph requires. The `google-generativeai` package it replaces was deprecated November 30, 2025 and does not support Gemini 2.x.
- `llama-index-core==0.14.15`: RAG retrieval abstraction over all three stores. Called as a Python function from LangGraph nodes — never as an orchestrator. Manages Neo4j property graph traversal, Qdrant hybrid vector search, and PostgreSQL SQL queries behind a unified interface.
- `llama-index-graph-stores-neo4j==0.5.1`: Neo4j integration for LlamaIndex. Supports `TextToCypherRetriever` and `CypherTemplateRetriever` — the only two retrievers compatible with externally-created graphs (Stratum's Neo4j was built by n8n, not LlamaIndex).
- `llama-index-vector-stores-qdrant==0.9.1`: Qdrant hybrid dense+sparse retrieval for the curated document corpus.
- `langgraph-checkpoint-postgres==3.0.4`: PostgreSQL-backed LangGraph state persistence for audit trail and interrupted run recovery. Requires psycopg3 (`psycopg[binary]>=3.1.0`) specifically — psycopg2 is incompatible.
- `fastembed>=0.3.0` with `BAAI/bge-small-en-v1.5` (384-dim): Locked from v1.0 Qdrant collection initialization. Changing the embedding model requires re-embedding all existing vectors — treat as immutable.
- `jinja2>=3.1.0` + `pydantic>=2.0.0`: Structured output validation and bilingual report template rendering. Raw LLM string output as a report body is explicitly an anti-feature.

**Critical version constraints:**
- `langgraph==1.0.10` requires Python >=3.10. The reasoning service Dockerfile must use `python:3.12-slim`.
- `langchain-google-genai>=4.0.0` and `llama-index-llms-google-genai==0.3.0` replace deprecated packages that must not be used under any circumstance.
- Gemini temperature must be 0.1–0.3 for analytical nodes — temperature 0.0 degrades reasoning quality on Gemini 2.0+ per Google official documentation.

See `.planning/research/STACK.md` for full `requirements.txt` and Docker Compose service definition.

### Expected Features

The v2.0 feature scope is constrained by a strict dependency chain. No feature can be built before its upstream dependencies are complete and validated. All 12 P1 features must be present for the first valid report to be produced.

**Must have — table stakes (P1, all required for first valid report):**
- Retrieval layer (LlamaIndex) validated independently over all three stores — blocks all reasoning nodes
- Neo4j regime graph seeded with historical macro regime nodes — blocks regime classification
- Qdrant document corpus populated (Fed minutes, SBV reports, VN earnings) — required for narrative grounding
- Macro regime classification with probability distribution output and mixed-signal handling — root dependency for everything downstream
- Regime-relative valuation assessment for VN equities (P/E, P/B vs historical analogues) and gold (real yield, ETF flow)
- Price structure interpretation node (reads pre-computed v1.0 markers, produces narrative — zero recomputation in the reasoning layer)
- Entry quality assessment with qualitative tier (Favorable / Neutral / Cautious / Avoid) and three visible sub-assessments (macro, valuation, structure)
- Grounding check node verifying all report numbers trace to retrieved database records — non-negotiable, prevents hallucination from propagating
- Structured report output in JSON + Markdown card format (macro regime, valuation, structure, entry quality cards)
- Vietnamese financial term dictionary (content artifact, not code — prerequisite for bilingual output quality)
- Bilingual generation (Vietnamese primary, English secondary) from structured data, not translation
- Explicit data freshness flags and "DATA WARNING" sections when `data_as_of` exceeds freshness thresholds
- Conflicting signal representation ("strong thesis, weak structure") as a first-class report type

**Should have — after first report validates (P2):**
- LangGraph checkpoint persistence for audit trail and interrupted run recovery
- Additional VN30 assets beyond initial 2–3 stock test set
- Automated Neo4j regime graph update on new FRED data ingestion

**Defer — out of scope for v2.0:**
- FastAPI API layer (report structure must stabilize before API shapes are designed)
- Frontend / Next.js UI — reports are JSON + Markdown files stored in PostgreSQL
- On-demand report generation via API — requires stable API layer
- PDF export (WeasyPrint system dependencies are overhead for a JSON + Markdown milestone)
- AI chat / Q&A over reports (unstructured chat creates unpredictable quality and cost)
- Real-time regime updates (regime classification is monthly cadence; real-time adds noise, not value)
- Per-asset portfolio context (moves the product toward portfolio management, out of scope)

See `.planning/research/FEATURES.md` for full dependency graph and competitor analysis table.

### Architecture Approach

The v2.0 architecture is a single new Docker service (`reasoning-engine`) joining the pre-existing `reasoning` network. No new database services are required — existing PostgreSQL, Neo4j, and Qdrant services are already dual-networked. The service co-locates FastAPI (HTTP gateway) and LangGraph (reasoning pipeline) in one container — appropriate for single-user VPS scale. The component boundary is strict and topologically enforced: n8n (ingestion network only) and reasoning-engine (reasoning network only) cannot communicate; the only interface between them is the shared storage layer. n8n writes data; reasoning-engine reads data and writes only to `reports` and `report_jobs`.

**Major components:**
1. `reasoning-engine` (new Docker service) — FastAPI gateway + LangGraph StateGraph + LlamaIndex retrievers; `python:3.12-slim`; `reasoning` network only; no host port mapping in production
2. LangGraph StateGraph — five named nodes with linear edges and PostgreSQL checkpointing; explicit state machine with deterministic execution path, not an autonomous agent
3. LlamaIndex retrieval layer — `Neo4jPropertyGraphStore` (Cypher template retrieval of regime analogues), `QdrantVectorStore` (hybrid dense+sparse document retrieval); called as Python functions from nodes, never as orchestrators
4. Gemini API (external) — invoked via `ChatGoogleGenerativeAI.with_structured_output(PydanticSchema)` from every reasoning node; all output enforced as Pydantic-validated structured JSON
5. PostgreSQL `reports` and `report_jobs` tables (new Flyway V6 and V7) — all report state persists here; FastAPI is fully stateless
6. Neo4j — populated with `Regime` nodes, `TimePeriod` nodes, and `HAS_ANALOGUE` relationships (carrying `similarity_score`, `dimensions_matched`, `period_start`, `period_end`) for analogue retrieval
7. Qdrant — populated with `macro_docs` and `earnings_docs` collections using BAAI/bge-small-en-v1.5 (384-dim, locked from v1.0)

See `.planning/research/ARCHITECTURE.md` for complete data flow diagrams, 7-phase build order, project directory structure, and all architectural anti-patterns.

### Critical Pitfalls

The research identified 13 pitfalls. The top 6 require architectural decisions before the first line of reasoning code is written:

1. **LangGraph state bloat causes Gemini context overflow and VPS OOM** — Each node must output only what the next node needs; raw retrieved documents must not live in LangGraph state; every Gemini call needs a token budget check before invocation; use compact `TypedDict` state schema from day one. Test with a realistic 20-stock batch before adding nodes, not a 3-stock toy example.

2. **LlamaIndex cannot use most retrievers against the existing Neo4j graph** — Only `CypherTemplateRetriever` and `TextToCypherRetriever` are compatible with externally-created graphs. Write all Cypher templates explicitly before building the retrieval layer. Never attempt `VectorContextRetriever` or `LLMSynonymRetriever` against the Stratum Neo4j instance.

3. **LLM hallucination of financial numbers propagates silently through the multi-step chain** — Every numeric claim must cite a specific database record ID in structured output. A grounding check node must verify every number in the narrative appears in retrieved context verbatim. JSON schema compliance does not prevent semantic hallucination — two separate validation steps are required.

4. **LangGraph reducer misuse causes silent state corruption** — Document the expected reducer (REPLACE or ACCUMULATE) for every `TypedDict` field. Use `Annotated[list, operator.add]` for accumulating fields; `Overwrite` for replacement fields. Write unit tests for node state shape after each node runs, not just that nodes complete without error.

5. **VPS memory exhaustion during concurrent service operation** — Set explicit `mem_limit` in Docker Compose for every service before adding the reasoning-engine (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, reasoning-engine 2GB). Configure 4GB VPS swap. Set Neo4j JVM heap explicitly — Neo4j defaults consume 25% of system RAM (2GB on an 8GB VPS).

6. **Macro regime misclassification as overconfident single label** — Regime classification must output a probability distribution, not a point estimate. If top confidence < 70%, the report explicitly surfaces "Mixed Signal Environment" with two most likely analogues. Neo4j `HAS_ANALOGUE` relationships must carry `similarity_score` from inception — retrofitting is a full graph rebuild.

Additional pitfalls: Gemini free tier is not viable for production batch workloads post-December 2025 (use Tier 1 paid with exponential backoff and configurable inter-request delay); Vietnamese financial terminology inconsistency requires a `glossary/vn_financial_terms.json` artifact included in every bilingual generation prompt; LangGraph checkpoint writes should use `AsyncPostgresSaver` in a separate database to avoid I/O contention; stale data freshness checks must be built into every retrieval node (read `data_as_of`, compare to threshold, emit explicit DATA WARNING).

See `.planning/research/PITFALLS.md` for all 13 pitfalls with phase assignments and warning signs.

---

## Implications for Roadmap

The build order is strictly constrained by data and retrieval dependencies. Reasoning nodes cannot be tested without real data in the stores. Report generation cannot be validated without validated reasoning nodes. The architecture research provides an explicit 7-phase build order that the roadmap should follow directly.

### Phase 1: Infrastructure Hardening and Database Migrations

**Rationale:** The reasoning-engine service will fail to start if PostgreSQL tables and memory limits are not in place first. This phase has no code risk — only configuration and SQL. Do it before any reasoning code is written.
**Delivers:** Flyway V6 (`reports` table) and V7 (`report_jobs` table); Docker memory limits and VPS swap configured; PostgreSQL checkpoint database schema initialized; Neo4j JVM heap explicitly set; `GEMINI_API_KEY` added to `.env`.
**Addresses:** Pitfall 5 (VPS OOM prevention), Pitfall 6 (checkpoint I/O isolation), Pitfall 1 (memory headroom required before state bloat can be validated)
**Avoids:** Debugging OOM kills instead of reasoning logic when the first reasoning service is added.

### Phase 2: Knowledge Graph and Document Corpus Population

**Rationale:** Neo4j regime graph and Qdrant document corpus are content prerequisites, not code tasks. Regime classification cannot produce meaningful output against an empty graph. Retrieval quality must be validated before being embedded in LangGraph nodes.
**Delivers:** Historical macro regime nodes in Neo4j with `HAS_ANALOGUE` relationships carrying `similarity_score`, `dimensions_matched`, `period_start`, `period_end`; `macro_docs` and `earnings_docs` collections in Qdrant populated with Fed minutes, SBV reports, VN earnings using BAAI/bge-small-en-v1.5 (384-dim); Vietnamese financial term dictionary (`glossary/vn_financial_terms.json`).
**Addresses:** Pitfall 10 (Neo4j schema must be designed from retrieval query patterns, not the other way around), Pitfall 9 (regime nodes must carry confidence weights from inception), Pitfall 5 (Vietnamese terminology dictionary prerequisite for bilingual quality)
**Content note:** Write the Cypher retrieval queries first, then design the Neo4j schema to support them. The `HAS_ANALOGUE` relationship property set must be final before any data is loaded.

### Phase 3: Retrieval Layer Validation

**Rationale:** LlamaIndex retrievers must be independently tested against real data before being embedded in LangGraph nodes. Bugs inside a 5-node reasoning graph are extremely difficult to root-cause.
**Delivers:** `reasoning/app/retrieval/neo4j_retriever.py` (CypherTemplateRetriever wrappers validated against loaded regime data); `reasoning/app/retrieval/qdrant_retriever.py` (hybrid dense+sparse validated against document corpus); PostgreSQL direct query patterns confirmed against fundamentals, structure_markers, fred_indicators tables; `data_as_of` freshness checks built into every retrieval function.
**Addresses:** Pitfall 2 (LlamaIndex retriever compatibility with externally-created graphs), Pitfall 11 (CypherTemplateRetriever preferred over TextToCypherRetriever for production paths), Pitfall 8 (freshness checks must be in retrieval layer, not as post-processing)
**Validation gate:** Each retriever must return relevant content against representative queries before Phase 4 begins.

### Phase 4: LangGraph Reasoning Nodes (one at a time, bottom-up)

**Rationale:** Build and validate each node in isolation before wiring into the graph. Start with the node with fewest dependencies (`structure` — PostgreSQL only, no LLM retrieval) to establish node patterns before adding LlamaIndex and Gemini complexity.
**Delivers:** Five independently tested LangGraph nodes: `structure.py` (PostgreSQL direct, Gemini interpretation), `valuation.py` (PostgreSQL + Qdrant + Gemini), `macro_regime.py` (Neo4j + Gemini, probability distribution output), `entry_quality.py` (state synthesis + Gemini, qualitative tier output), `compose_report.py` (bilingual generation + PostgreSQL write); grounding check node; `ReportState` TypedDict with all reducer annotations documented; Vietnamese term dictionary integrated into compose_report prompt.
**Addresses:** Pitfall 1 (strict state schema, token budget checks before every Gemini call), Pitfall 3 (explicit reducer annotations, unit tests for state shape), Pitfall 4 (Gemini Tier 1 rate-limit handling with exponential backoff from first node), Pitfall 7 (grounding check node, source citation IDs in structured output), Pitfall 9 (regime node outputs probability distribution, not point estimate)
**Node build order within phase:** structure → valuation → macro_regime → entry_quality → compose_report

### Phase 5: LangGraph Graph Assembly and End-to-End Validation

**Rationale:** Assemble the StateGraph only after all five nodes are independently verified. The first end-to-end run is an integration test, not a production run.
**Delivers:** `reasoning/app/graph/graph.py` (StateGraph with five nodes, linear edges, AsyncPostgresSaver checkpointer in separate database); `reasoning/app/graph/state.py` (ReportState TypedDict finalized); one complete report for a single test asset written to PostgreSQL `reports` table and validated against the founder's analytical standard.
**Addresses:** Pitfall 6 (AsyncPostgresSaver in isolated checkpoint database), Pitfall 13 (semantic grounding check separate from JSON schema validation)
**Validation gate:** Report must pass grounding check (all numbers traceable to retrieved records), data freshness check, and Vietnamese term consistency check before Phase 6 begins.

### Phase 6: FastAPI Gateway and Docker Service

**Rationale:** FastAPI is a thin HTTP wrapper over the validated LangGraph pipeline. It cannot be built meaningfully before the pipeline is functional. This is the final engineering delivery of the v2.0 milestone.
**Delivers:** `reasoning/app/main.py` with `POST /reports/generate` (BackgroundTask), `GET /reports/{id}`, `GET /reports/stream/{id}` (SSE), `GET /health`; `reasoning/Dockerfile`; reasoning-engine added to `docker-compose.yml` with `profiles: ["reasoning"]`; end-to-end test of HTTP trigger → LangGraph pipeline → PostgreSQL report storage.
**Addresses:** Pattern 6 (FastAPI BackgroundTask for long-running pipeline), Anti-Pattern 4 (stateless FastAPI — no in-memory report state), Anti-Pattern 5 (LangGraph runs inside FastAPI container as a library, not as a separate server)

### Phase 7: Production Hardening and Batch Validation

**Rationale:** Single-asset end-to-end success does not validate batch behavior. Critical pitfalls around state bloat, OOM, and rate limits only surface at realistic batch scale.
**Delivers:** Batch report generation validated against realistic 20-stock workload; Docker memory stats baselined; Gemini API spend alerts configured ($5/$10/$25/month thresholds); checkpoint cleanup job implemented (TTL-based purge beyond 24 hours); n8n ingestion and batch report scheduling coordinated to prevent concurrent memory spikes; `data_as_of` freshness logic validated with real-world WGC 45-day lag.
**Addresses:** Pitfall 1 (full batch test, not toy example), Pitfall 4 (Tier 1 Gemini rate limits validated in production conditions), Pitfall 12 (memory budget validated under production load), Pitfall 8 (freshness logic validated with known lag patterns)

### Phase Ordering Rationale

- **Infrastructure before code (Phase 1 first):** A missing migration or missing memory limit is harder to debug when mixed with reasoning failures. Isolate infrastructure concerns.
- **Data before retrieval, retrieval before reasoning (Phases 2–4):** The dependency chain is strict and unidirectional. Skipping any step means the next phase cannot be meaningfully tested.
- **Nodes before graph, graph before gateway (Phases 4–6):** Integration bugs in a 5-node graph are expensive to isolate. Test each node with mock state before wiring them together.
- **Batch validation last (Phase 7):** Single-asset success is necessary but not sufficient for production readiness. The critical pitfalls (OOM, rate limits, state bloat) only manifest at scale.

### Research Flags

Phases likely needing per-phase deeper research during planning:

- **Phase 2 (Knowledge Graph Population):** Historical macro regime schema design and `HAS_ANALOGUE` relationship property definitions require query-first design. Research which macro periods (2008–2025) are representable from FRED data alone vs. requiring supplemental sources. Research Vietnamese financial market history coverage for Neo4j seeding.
- **Phase 4 (LangGraph Nodes):** Gemini context caching implementation (minimum 1,024 tokens for 2.5 Flash) needs validation against the specific model version in use. The interplay between `.with_structured_output()` and Gemini's function calling activation (December 2025 known behavior) needs validation before building all five nodes.

Phases with standard patterns (research phase can be skipped):

- **Phase 1 (Infrastructure):** Standard Docker Compose configuration and Flyway migration patterns. Well-documented. No research needed.
- **Phase 3 (Retrieval Layer):** LlamaIndex Neo4j and Qdrant integration patterns are well-documented in official sources. Cypher template patterns for this schema are the only unknown and can be resolved during implementation.
- **Phase 6 (FastAPI Gateway):** Standard FastAPI BackgroundTask + SSE patterns. Mirrors existing data-sidecar structure in the codebase.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI as of March 2026. Deprecation notices confirmed via official GitHub and PyPI. Google AI official docs confirm LangGraph + langchain-google-genai as the canonical integration path. |
| Features | MEDIUM-HIGH | Table stakes and anti-features are HIGH confidence (CFA Institute, institutional platform patterns). AI-native entry quality scoring with LangGraph is MEDIUM (nascent but growing 2025–2026 precedent). Vietnamese-language generation with Gemini is MEDIUM (Gemini supports Vietnamese natively; financial domain consistency depends on term dictionary quality). |
| Architecture | HIGH | Existing codebase fully inspected at the time of research. Build order derived from actual v1.0 service topology and Docker network constraints. All integration patterns verified against official Neo4j Labs, Qdrant, and LangChain documentation. |
| Pitfalls | MEDIUM-HIGH | LangGraph-specific pitfalls (state bloat, reducer misuse) cross-verified across official docs and community post-mortems. Financial hallucination rates cited from FinanceBench benchmark. VPS infrastructure pitfalls derived from actual v1.0 service memory footprints. |

**Overall confidence:** HIGH for infrastructure and stack decisions. MEDIUM for regime classification accuracy and Vietnamese output quality — both depend on content assets (regime graph data quality, term dictionary scope) not yet created.

### Gaps to Address

- **Neo4j historical regime data coverage:** The quality of regime classification is entirely dependent on the historical analogue dataset loaded into Neo4j. An explicit plan for which macro periods (2008–2025) to seed and from which data sources must be resolved before Phase 2 begins. This is a content gap, not a code gap.

- **WGC central bank buying data:** The v1.0 WGC stub cannot be resolved without a paid WGC data subscription or a manual CSV import process. Gold valuation must function without this data for v2.0 launch, flagging it as a known gap in reports. Not a blocker, but must be explicitly handled in the stale data warning logic.

- **Gemini model selection (2.0-flash vs 2.5-flash):** The cost-quality tradeoff for the specific prompt patterns in this pipeline has not been benchmarked. Should be validated during Phase 4 node development with both models before committing to production configuration.

- **Vietnamese term dictionary scope:** The `glossary/vn_financial_terms.json` artifact is identified as a prerequisite but its scope — how many terms, which VAS vs. IFRS distinctions matter for this domain — has not been defined. Needs an authoring session before Phase 4 `compose_report` node is built.

---

## Sources

### Primary (HIGH confidence)

- [LangGraph PyPI](https://pypi.org/project/langgraph/) — v1.0.10 stable, Feb 27, 2026; StateGraph patterns
- [langchain-google-genai PyPI](https://pypi.org/project/langchain-google-genai/) — v4.0.0 SDK migration; structured output; bind_tools interface
- [llama-index-core PyPI](https://pypi.org/project/llama-index-core/) — v0.14.15, Feb 18, 2026; multi-store retrieval
- [llama-index-graph-stores-neo4j PyPI](https://pypi.org/project/llama-index-graph-stores-neo4j/) — v0.5.1; TextToCypherRetriever and CypherTemplateRetriever
- [llama-index-vector-stores-qdrant PyPI](https://pypi.org/project/llama-index-vector-stores-qdrant/) — v0.9.1, Jan 13, 2026
- [langgraph-checkpoint-postgres PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) — v3.0.4; psycopg3 requirement confirmed
- [Google AI for Developers — LangGraph + Gemini example](https://ai.google.dev/gemini-api/docs/langgraph-example) — canonical integration pattern; official Google documentation
- [Google GenAI SDK libraries overview](https://ai.google.dev/gemini-api/docs/libraries) — `google-generativeai` deprecation confirmed
- [google-generativeai deprecated GitHub](https://github.com/google-gemini/deprecated-generative-ai-python) — deprecated Nov 30, 2025
- [Neo4j Labs — LlamaIndex integration](https://neo4j.com/labs/genai-ecosystem/llamaindex/) — TextToCypherRetriever patterns; externally-created graph caveat
- [Qdrant — GraphRAG with Neo4j](https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/) — hybrid retrieval over graph + vector stores
- [LlamaIndex — Qdrant hybrid search docs](https://docs.llamaindex.ai/en/stable/examples/vector_stores/qdrant_hybrid/) — enable_hybrid, sparse_top_k patterns
- [CFA Institute — Explainable AI in Finance (2025)](https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance) — explainability as table-stakes expectation for investment research

### Secondary (MEDIUM confidence)

- [ZenML — LlamaIndex vs LangGraph](https://www.zenml.io/blog/llamaindex-vs-langgraph) — LlamaIndex for retrieval + LangGraph for orchestration as dominant production pattern
- [FactSet — Asset returns to economic regimes](https://insight.factset.com/mapping-asset-returns-to-economic-regimes-a-practical-investors-guide) — institutional regime classification frameworks
- [Two Sigma — Machine learning approach to regime modeling](https://www.twosigma.com/articles/a-machine-learning-approach-to-regime-modeling/) — quantitative regime modeling at institutional scale
- [AlphaArchitect — K-means macro regime clustering](https://alphaarchitect.com/clustering-macroeconomic-regimes/) — k-means over FRED series for regime detection
- [AWS — LangGraph financial analysis agent](https://aws.amazon.com/blogs/machine-learning/build-an-intelligent-financial-analysis-agent-with-langgraph-and-strands-agents/) — production LangGraph financial analysis patterns
- [LangGraph GitHub discussions — PostgreSQL checkpointer](https://github.com/langchain-ai/langgraph/discussions/3691) — PostgresSaver.setup() autocommit requirement; community-verified
- [Zestminds — FastAPI + LangGraph production pattern](https://www.zestminds.com/blog/build-ai-workflows-fastapi-langgraph/) — verified against official patterns
- [llama-index-llms-gemini PyPI deprecation notice](https://pypi.org/project/llama-index-llms-gemini/) — deprecated at v0.6.2; replaced by llama-index-llms-google-genai
- [LLM Pro Finance Suite (2025 preprint)](https://arxiv.org/html/2511.08621v1) — multilingual financial LLM capabilities including Vietnamese

---

*Research completed: 2026-03-09*
*Ready for roadmap: yes*
