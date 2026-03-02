# Project Research Summary

**Project:** Stratum — Long-Term Investment Advisor Platform
**Domain:** AI-powered macro-fundamental investment research (Vietnamese market)
**Researched:** 2026-03-03
**Confidence:** MEDIUM-HIGH

## Executive Summary

Stratum is a structured AI reasoning platform that produces institutional-quality investment research reports for Vietnamese retail investors covering VN stocks and gold. The product is not a trading terminal or portfolio manager — it is a research advisor that answers "are conditions favorable for long-term entry?" through a layered analysis of macro regime, asset valuation, and higher time-frame price structure. Expert implementation of this type of platform uses a two-pipeline architecture with a hard storage boundary: a scheduled ingestion pipeline (n8n) that pre-computes all numeric metrics before writing to storage, and a separate reasoning pipeline (LangGraph + LlamaIndex) that reads from storage and produces explainable reports. The ingestion and reasoning pipelines share no runtime state and communicate exclusively through PostgreSQL, Neo4j, and Qdrant.

The recommended stack is well-validated and internally consistent. LangGraph 1.0 (stable as of Oct 2025) provides the explicit state machine needed for reproducible, auditable multi-step reasoning. LlamaIndex 0.14.15 wraps Qdrant and Neo4j retrieval in a unified interface. FastAPI with SSE streaming surfaces the reasoning pipeline to the frontend in real-time. The two gaps the founder's original stack did not address are: (1) a background task queue for long-running report generation (recommend `arq` on Redis, or LangGraph's built-in PostgreSQL checkpointer as an alternative), and (2) an embedding model for LlamaIndex + Qdrant (recommend FastEmbed for zero-cost local embedding). Both gaps have clean solutions that fit the existing architecture.

The dominant risks are not technical infrastructure risks — the stack is sound. The critical risks are data and reasoning quality risks: LLM hallucination of financial numbers, stale data silently entering reports, overconfident macro regime classification collapsing a probabilistic signal into a single label, and the entry quality score being interpreted as a buy/sell signal rather than a structured research summary. All four risks must be treated as first-class architectural constraints from the start of implementation, not as polish steps. The Vietnamese market data dependency on vnstock (an unofficial community library) is a known fragility that requires defensive error handling and version pinning from day one.

---

## Key Findings

### Recommended Stack

The stack spans four functional layers: AI reasoning (LangGraph 1.0.10 + google-genai 1.65.0 + Ollama), retrieval (LlamaIndex 0.14.15 with llama-index-vector-stores-qdrant and llama-index-graph-stores-neo4j), storage (PostgreSQL 17 + TimescaleDB optional, Neo4j Community 5.x, Qdrant 1.17.0), and ingestion/orchestration (n8n 2.9.4 + vnstock 3.4.2 + fredapi). The frontend is Next.js 16.1.6 with lightweight-charts 5.1.0 and Supabase self-hosted for auth. All services run in a single Docker Compose file on a VPS. The old `google-generativeai` package reached EOL November 2025 — the `google-genai` 1.65.0 SDK is mandatory.

**Core technologies:**
- **LangGraph 1.0.10:** Multi-step reasoning graph — the only framework with programmatic, auditable control over each reasoning step; required for explainability constraint
- **LlamaIndex 0.14.15:** Retrieval abstraction over Qdrant (semantic) and Neo4j (graph); called as a retrieval function inside LangGraph nodes, not as a reasoning orchestrator
- **google-genai 1.65.0:** Unified Gemini SDK (new GA package; old SDK is deprecated); supports Gemini 2.5 Flash and 3.1 Pro Preview
- **Qdrant 1.17.0:** Vector store for earnings transcripts, Fed minutes, macro reports; Relevance Feedback in v1.17 directly improves financial document retrieval
- **Neo4j Community 5.x:** Knowledge graph for macro regime relationships, historical analogues, asset correlations; supports Text2Cypher via LlamaIndex
- **PostgreSQL 17 + TimescaleDB:** Structured time-series, fundamentals, pre-computed structure markers, reports — TimescaleDB extension recommended from the start for OHLCV compression
- **n8n 2.9.4:** Pipeline orchestration with visual debugger — the right tool for single-operator self-hosted ingestion; communicates with reasoning layer only via storage, never direct API calls
- **vnstock 3.4.2:** Only maintained Python library for Vietnamese market data; must be version-pinned and wrapped with defensive error handling
- **arq (async Redis queue):** Gap fill for background task queue — FastAPI cannot hold HTTP connections open for 30–120 second report generation runs
- **FastEmbed (llama-index-embeddings-fastembed):** Gap fill for embedding model — zero-cost local quantized embedding, no GPU required, adequate for weekly/monthly ingestion cadence
- **langgraph-checkpoint-postgres:** Gap fill for LangGraph state persistence — required for explainability audit trail and interrupted run recovery

See `.planning/research/STACK.md` for full version pinning, installation commands, and alternatives considered.

### Expected Features

Macro regime classification is the root dependency for the entire platform. Valuation assessment, entry quality score, and historical analogues all require regime as their primary context layer. This means regime classification must be built and validated before any downstream feature is reliable.

**Must have (table stakes — v1 launch):**
- Watchlist management — entry point for report generation; infrastructure dependency for on-demand triggering
- Per-asset structured research report (card format) — core deliverable; nothing else matters without this
- Macro regime classification with historical analogues — intellectual core and root dependency for all analysis
- Asset valuation assessment relative to historical range and regime context — regime-relative valuation is the differentiated view
- Higher time-frame price structure analysis (weekly/monthly MAs, drawdown from ATH) — entry context layer
- AI-derived entry quality assessment with explicit reasoning chain — synthesis and primary output; must show sub-assessments per layer, not a single number
- Bilingual output (Vietnamese primary, English secondary) — Vietnamese-language native generation, not translation
- Explicit data freshness indicators and stale data handling — required given known data lag patterns (WGC 45-day lag, vnstock fragility)
- Mixed-signal and low-confidence regime representation — must be first-class output, not an edge case
- Explainable reasoning steps per analytical layer — each step must cite its data source and inputs
- On-demand report generation for new watchlist additions — users adding an asset cannot wait 30 days
- Report history archive per asset — baseline for any research platform

**Should have (competitive differentiation, add post-validation):**
- Email digest notification on report updates (weekly cadence-aligned, not price-triggered)
- PDF report export
- Improved chart rendering for price structure context in report cards

**Defer (v2+):**
- Additional asset classes (BTC, bonds, US stocks) — only after VN stocks + gold analysis is excellent
- Multi-user accounts, auth, billing — productization; single-user at launch
- Screener / asset discovery — requires large asset coverage first
- AI chat / Q&A over reports — explicitly an anti-feature; expands report depth instead

**Anti-features to explicitly exclude:**
- Real-time/intraday price data — contradicts the weekly/monthly analytical frame
- Portfolio holdings tracking and P&L — scope creep into brokerage-adjacent features
- Buy/sell trade signals — regulatory risk (Vietnam SSC); defeats probabilistic framing
- Short-term technical analysis (RSI, MACD) — different user persona than the platform serves

See `.planning/research/FEATURES.md` for full feature dependency graph and competitor analysis.

### Architecture Approach

The platform is a two-pipeline system separated at a hard storage boundary. n8n handles all ingestion and pre-computation, writing to PostgreSQL/Neo4j/Qdrant. LangGraph handles all reasoning, reading from storage via LlamaIndex retrievers. FastAPI is a thin async gateway that invokes LangGraph as a background task and streams step progress to the frontend via SSE. Next.js + Supabase Auth is the rendering layer. The storage boundary is the core architectural constraint: n8n and LangGraph share no runtime state, no direct API calls, no queue messages — only the storage layer.

**Major components:**
1. **n8n Ingestion Pipeline** — fetches from external APIs (vnstock, FRED, World Gold Council), transforms, pre-computes all derived metrics (MAs, drawdown, valuation percentiles), and writes to all three stores. Never calls LangGraph or FastAPI.
2. **Storage Layer (PostgreSQL + Neo4j + Qdrant)** — the only interface between ingestion and reasoning. PostgreSQL stores structured time-series, fundamentals, pre-computed markers, completed reports, and job status. Neo4j stores macro regime graph with historical analogues and weighted RESEMBLES relationships. Qdrant stores semantic vectors over unstructured documents.
3. **LangGraph Reasoning Pipeline** — explicit StateGraph (not a freeform agent) with five nodes: MacroRegimeClassifier, ValuationContextualizer, StructureAnalyzer, EntryQualityScorer, ReportComposer. Calls LlamaIndex retrievers as tool functions. Outputs bilingual structured report to PostgreSQL. State is persisted via langgraph-checkpoint-postgres.
4. **LlamaIndex Retrieval Layer** — retrieval abstraction only; not a reasoning orchestrator. GraphRAGRetriever for Neo4j, HybridRetriever (dense + sparse) for Qdrant. Called by LangGraph nodes, not the other way around.
5. **FastAPI API Layer** — async gateway; invokes LangGraph as BackgroundTask; streams reasoning step progress as SSE; validates Supabase JWTs locally; writes job status to PostgreSQL. Contains no business logic.
6. **Next.js + Supabase Frontend** — thin rendering layer; consumes FastAPI endpoints; uses SSE for real-time step progress; renders structured report cards with lightweight-charts for price context.

See `.planning/research/ARCHITECTURE.md` for full data flow diagrams, anti-patterns, and build order dependencies.

### Critical Pitfalls

1. **LLM hallucinating financial numbers** — Every numeric claim in a report must be traceable to a retrieved database record, not LLM output. Use Gemini structured JSON output so the pipeline fails noisily when a number cannot be grounded. Add a grounding-check node at the end of the reasoning chain. Never ask the LLM to recall historical figures from memory. Recovery cost if discovered post-publication: HIGH.

2. **Stale data presented as current** — Every ingested row needs both `ingested_at` (when fetched) and `data_as_of` (the period the data covers). n8n must write to a `pipeline_run_log` table on every run. LangGraph reads `data_as_of` before reasoning and emits "DATA WARNING" sections when freshness threshold is exceeded. World Gold Council's 45-day publication lag must be modeled as a property in Neo4j, not treated as a current data point.

3. **Macro regime classification as overconfident single label** — Regime classification must output a probability distribution, not a string. If top confidence is below 70%, the report must surface "Mixed Signal Environment" with two likely analogues rather than forcing a single label. Neo4j `RESEMBLES` relationships must carry `similarity_score`, `dimensions_matched`, and `period` properties from inception — retrofitting this is a full graph rebuild.

4. **Entry quality score as an authoritative buy/sell signal** — The entry quality output must be a qualitative tier with reasoning decomposition (Favorable/Neutral/Cautious/Avoid), not a numeric score. Every report must show three sub-assessments (macro, valuation, structure) before any composite. Report copy must use probabilistic language ("suggests," "conditions consistent with") and must never contain "buy," "sell," or "entry confirmed."

5. **vnstock as a silent single point of failure** — vnstock wraps unofficial broker APIs that break without notice (KRX migration May 2025 is documented). All vnstock calls must distinguish between API error, empty result, and anomalously low row count. Implement row-count anomaly detection in n8n (compare to 4-week moving average; alert on >50% deviation). Pin the version in requirements.txt. Accept 1–3 day data outages following broker infrastructure changes.

See `.planning/research/PITFALLS.md` for full pitfall details, integration gotchas, performance traps, and security mistakes.

---

## Implications for Roadmap

Based on research, the architecture has clear build-order dependencies that directly constrain phase structure. Each layer depends on the one below it being stable. Six phases are implied.

### Phase 1: Infrastructure and Storage Foundation
**Rationale:** All other components depend on the storage layer being accessible and the schema being correct. Neo4j schema is particularly irreversible — designing it incorrectly before data is loaded requires a full graph rebuild. This phase establishes the non-negotiable base.
**Delivers:** VPS running Docker Compose with all storage services; PostgreSQL schema with `data_as_of`, `ingested_at`, and `pipeline_run_log` from the start; Neo4j schema with full relationship properties (RESEMBLES with similarity_score, dimensions_matched, period); Qdrant collections versioned; Supabase auth configured; Nginx reverse proxy with SSE headers.
**Addresses:** Watchlist management schema; report archive schema; job status table.
**Avoids:** Neo4j schema mismatch pitfall (design retrieval queries first, work backward to schema); stale data pitfall (add staleness columns to the first migration, not as an afterthought).
**Research flag:** Standard patterns — Docker Compose, PostgreSQL, Supabase self-hosted all have official documentation. Neo4j schema design for analogue retrieval is the one non-standard element; may benefit from targeted research during planning.

### Phase 2: Data Ingestion Pipeline (n8n)
**Rationale:** LangGraph cannot reason without data. The storage layer must be populated with realistic data before the reasoning pipeline can be tested end-to-end. Pre-computation of all structure markers (MAs, drawdown, valuation percentiles) happens here — not in the reasoning pipeline.
**Delivers:** Fully populated storage layer: vnstock → PostgreSQL OHLCV + fundamentals (weekly/monthly); FRED → PostgreSQL macro series; World Gold Council → PostgreSQL gold data; document embedding → Qdrant; regime relationships → Neo4j. All data rows include `data_as_of` and `ingested_at`. Pipeline run log writes success/failure on every execution. Row-count anomaly detection alerts on empty-but-successful runs.
**Addresses:** Data ingestion (VN stocks, gold, macro) P1 features; data freshness indicators; stale data handling.
**Avoids:** vnstock silent failure pitfall (version pinned, row-count checks); stale data pitfall (pipeline_run_log from day one); n8n type precision gotcha (typed PostgreSQL inserts, not JSON passthrough).
**Research flag:** vnstock-specific n8n integration patterns are sparse; may benefit from a focused research spike. FRED and WGC ingestion are straightforward HTTP.

### Phase 3: Retrieval Layer Validation (LlamaIndex)
**Rationale:** Retrieval must be verified independently before being embedded in LangGraph nodes. Retrieval bugs are extremely difficult to debug from inside a multi-node reasoning graph. This phase validates that LlamaIndex can execute the specific Cypher patterns needed for analogue retrieval and that Qdrant hybrid search returns useful financial documents before wiring them into reasoning.
**Delivers:** Validated LlamaIndex GraphRAGRetriever for Neo4j with custom Cypher templates (not auto-generated queries); validated HybridRetriever (dense + sparse BM25) for Qdrant; FastEmbed embedding model integrated; retrieval quality confirmed with test queries against real loaded data.
**Addresses:** Historical analogues retrieval quality; semantic retrieval over earnings transcripts and macro documents.
**Avoids:** LlamaIndex auto-generated Cypher causing full graph scans (write Cypher templates first); Qdrant dense-only retrieval missing financial identifiers (hybrid search mandatory for financial documents).
**Research flag:** Targeted research may be needed on LlamaIndex + Neo4j custom Cypher query registration patterns. This is an integration detail with sparse documentation beyond official examples.

### Phase 4: AI Reasoning Pipeline (LangGraph)
**Rationale:** Cannot build reasoning nodes without verified data (Phase 2) and verified retrieval (Phase 3). This is the intellectual core of the platform and the highest-risk phase from a quality perspective. All four critical pitfalls (hallucination, overconfident regime, score framing, state growth) must be addressed here.
**Delivers:** Working LangGraph StateGraph with five named nodes (MacroRegimeClassifier, ValuationContextualizer, StructureAnalyzer, EntryQualityScorer, ReportComposer); regime classification outputs probability distribution with mixed-signal handling; entry quality outputs qualitative tier with three sub-assessments; every numeric claim is grounded to a retrieved source; bilingual report generation (Vietnamese primary); LangGraph state TypedDict with strict size constraints and pruning; langgraph-checkpoint-postgres for audit trail; test cases for mixed-signal inputs.
**Addresses:** Macro regime classification + analogues; asset valuation assessment; price structure analysis; entry quality assessment; explainable reasoning chain; mixed-signal representation; bilingual output — all P1 features.
**Avoids:** LLM hallucination pitfall (grounding check node, structured JSON output); regime overconfidence pitfall (distribution output, confidence threshold); entry quality framing pitfall (qualitative tiers, no numeric-only score); LangGraph state growth pitfall (TypedDict constraints, token budget checks); anti-pattern of single monolithic LLM prompt.
**Research flag:** HIGH priority for phase research — this phase involves the most novel integrations (LangGraph + LlamaIndex + Gemini structured output for financial analysis) and has the highest failure cost. Recommend `/gsd:research-phase` before detailed planning.

### Phase 5: API Layer (FastAPI)
**Rationale:** FastAPI is a thin gateway. It cannot be built until the pipeline it invokes (Phase 4) is functional. Building API shapes before the pipeline is stable causes wasted iteration as endpoint signatures change.
**Delivers:** POST /reports/generate with BackgroundTask + job_id response; GET /reports/stream/{job_id} SSE endpoint for step progress; GET /reports/{id} for stored report retrieval; watchlist CRUD endpoints; Supabase JWT verification middleware (local verification against public key, not per-request Supabase API calls); arq Redis queue integration for production-grade background task handling.
**Addresses:** On-demand report generation; watchlist management API; SSE step-progress streaming.
**Avoids:** FastAPI holding HTTP connections open during 30–120 second pipeline runs (BackgroundTask + arq); in-memory report storage anti-pattern (all reports written to PostgreSQL, retrieved by query).
**Research flag:** Standard patterns — FastAPI BackgroundTasks, SSE streaming with LangGraph, Supabase JWT verification are all well-documented. Skip phase research.

### Phase 6: Frontend (Next.js)
**Rationale:** Frontend has no value until all backend layers are functional. Building the UI before API shapes are stable causes double work. Build last to minimize wasted iteration.
**Delivers:** Supabase Auth integration (SSR with @supabase/ssr); watchlist management UI; report viewer with structured card layout (macro regime card, valuation card, price structure card, entry quality card); SSE step-progress UI showing reasoning pipeline execution in real-time; lightweight-charts 5.1.0 integration for weekly/monthly OHLCV with structure markers; report history list per asset; Vietnamese as primary display language; bilingual term glossary sidebar for financial terms; data freshness indicators in report UI.
**Addresses:** Structured card report format; bilingual UX; data freshness display; on-demand generation feedback (visible trigger, not silent background job); report history archive.
**Avoids:** UX pitfalls — entry quality as headline number without component breakdown (sub-assessments are primary display); bilingual inconsistency (term mapping dictionary used by Gemini generation must be validated in UI); "N/A without explanation" for missing data (specific messages per data unavailability reason).
**Research flag:** lightweight-charts v5 multi-pane integration and Next.js 16 App Router with Supabase SSR are well-documented. Skip phase research unless specific chart integration patterns prove complex during planning.

### Phase Ordering Rationale

- **Storage before ingestion:** Schema errors discovered after data is loaded require migrations or full rebuilds, especially in Neo4j. Design schema against retrieval query patterns first.
- **Ingestion before reasoning:** LangGraph nodes cannot be tested or debugged without realistic data. Toy data hides state growth bugs and retrieval quality issues that surface with real volumes.
- **Retrieval validation before reasoning integration:** Embedding a broken retriever inside a 5-node reasoning graph makes root-cause analysis near-impossible. Validate retrieval in isolation.
- **Reasoning before API:** API endpoint shapes depend on the data structures LangGraph produces (report schema, job status, streaming events). Building API before these are stable causes rework.
- **API before frontend:** Frontend cannot function without API endpoints. Frontend built last ensures all API contracts are stable before UI iteration begins.
- **Phase 4 (Reasoning) is the highest-risk phase:** It involves the most novel integrations, all four critical pitfalls originate here or materialize here, and the output quality directly determines whether the product's core value proposition is realized.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (AI Reasoning Pipeline):** Novel LangGraph + LlamaIndex + Gemini integration for structured financial analysis; mixed-signal regime classification design; grounding check implementation patterns; bilingual generation quality. Recommend `/gsd:research-phase` before this phase is planned in detail.
- **Phase 2 (Ingestion Pipeline) — vnstock specifically:** vnstock n8n integration patterns and row-count anomaly detection implementation are sparsely documented. Worth a targeted spike to confirm the specific n8n Python code node patterns needed.
- **Phase 3 (Retrieval Validation) — Neo4j custom Cypher in LlamaIndex:** Registering custom Cypher templates as LlamaIndex query tools rather than using auto-generated Cypher is not covered in official quick-start docs. Needs targeted research before implementation.

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1 (Infrastructure):** Docker Compose, PostgreSQL, Supabase self-hosted, Nginx are fully documented. Neo4j schema design is the only novel element but is addressable with schema planning, not research.
- **Phase 5 (API Layer):** FastAPI BackgroundTasks, SSE streaming, JWT verification, arq integration are all well-documented with high-confidence sources.
- **Phase 6 (Frontend):** Next.js 16 App Router + Supabase SSR + lightweight-charts v5 are well-documented. Standard patterns apply.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core packages (LangGraph, LlamaIndex, FastAPI, Qdrant, Neo4j driver, vnstock, google-genai) all confirmed on PyPI with exact version numbers. Frontend versions (Next.js 16.1.6, lightweight-charts 5.1.0) are MEDIUM — confirmed via search, not direct npm registry reads. |
| Features | MEDIUM | Global investment platform feature patterns are HIGH confidence. Vietnamese market-specific expectations are MEDIUM (fewer authoritative Vietnamese-language sources). AI-driven analysis features are LOW-MEDIUM — novel space with limited direct precedent but CFA Institute and academic sources validate the explainability requirement. |
| Architecture | MEDIUM-HIGH | Core patterns (storage boundary isolation, LangGraph state machine, LlamaIndex as retrieval-only, FastAPI BackgroundTask for long-running jobs) confirmed across multiple official documentation sources and academic references. Supabase + Next.js + FastAPI JWT pattern has only one non-official source — treat as MEDIUM. |
| Pitfalls | MEDIUM | Financial LLM hallucination research is HIGH confidence (peer-reviewed sources). vnstock fragility is HIGH confidence (official vnstock docs confirm KRX breakage). Neo4j schema pitfalls are HIGH confidence (official Neo4j blog). LangGraph state memory leak is HIGH confidence (official GitHub issue). Domain-specific pitfalls (regime overconfidence, score framing) are MEDIUM based on institutional investment platform analogues. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **arq vs. LangGraph PostgreSQL checkpointer for background tasks:** Both are viable. arq adds a Redis dependency (one more container); the LangGraph checkpointer avoids this but adds complexity to the polling/notification pattern. Decision should be made at Phase 5 planning with a concrete implementation spike. If Redis is acceptable, arq is cleaner. If minimizing container count matters, use LangGraph's native checkpointer with a polling endpoint.

- **Ollama model selection for local fallback:** The stack specifies Ollama as the local LLM runtime but does not identify a specific model. For a single-VPS deployment with the report generation workload (Vietnamese language, financial analysis, bilingual generation), model selection requires a brief evaluation against available Ollama models and VPS RAM constraints before Phase 4 begins.

- **Vietnamese financial terminology mapping:** Bilingual report generation requires a consistent Vietnamese financial term dictionary. This dictionary does not exist yet and must be authored before Phase 4 (ReportComposer node) and Phase 6 (glossary sidebar) can be implemented. It is a content asset, not a technical one, but it blocks quality bilingual generation.

- **World Gold Council data ingestion method:** The WGC data has known 45-day publication lag and requires modeling this lag in Neo4j as a source property. The specific WGC API endpoint structure and authentication requirements are not confirmed in the research. Validate before Phase 2 planning.

- **Neo4j initial regime graph seed data:** The reasoning pipeline depends on Neo4j being populated with historical macro regime nodes, analogue relationships, and period metadata. Where this seed data comes from (manual curation, automated historical ingestion, or a one-time import) is not fully resolved. This is a Phase 2 concern that needs an explicit plan.

---

## Sources

### Primary (HIGH confidence)
- LangGraph PyPI — version 1.0.10 confirmed: https://pypi.org/project/langgraph/
- LlamaIndex Core PyPI — version 0.14.15 confirmed: https://pypi.org/project/llama-index-core/
- FastAPI PyPI — version 0.135.1 confirmed: https://pypi.org/project/fastapi/
- Qdrant client PyPI — version 1.17.0 confirmed: https://pypi.org/project/qdrant-client/
- Neo4j Python driver PyPI — version 6.1.0 confirmed: https://pypi.org/project/neo4j/
- vnstock PyPI — version 3.4.2 confirmed; KRX breakage documented: https://pypi.org/project/vnstock/
- google-genai PyPI — version 1.65.0 confirmed; old SDK EOL official: https://pypi.org/project/google-genai/
- LlamaIndex + Neo4j integration — official Neo4j Labs: https://neo4j.com/labs/genai-ecosystem/llamaindex/
- Qdrant hybrid search + LlamaIndex — official LlamaIndex docs: https://docs.llamaindex.ai/en/stable/examples/vector_stores/qdrant_hybrid/
- langgraph-checkpoint-postgres — PyPI: https://pypi.org/project/langgraph-checkpoint-postgres/
- Supabase self-hosting — official docs: https://supabase.com/docs/guides/self-hosting
- Supabase Auth with Next.js SSR — official docs: https://supabase.com/docs/guides/auth/server-side/nextjs
- google-generativeai EOL — official deprecation notice: https://github.com/google-gemini/deprecated-generative-ai-python
- LLM hallucination in finance — peer-reviewed: https://arxiv.org/abs/2311.15548
- Neo4j worst practices — official Neo4j blog: https://neo4j.com/blog/cypher-and-gql/dark-side-neo4j-worst-practices/
- LangGraph memory leak — official GitHub issue: https://github.com/langchain-ai/langgraph/issues/3898
- OWASP LLM prompt injection — official: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- CFA Institute Explainable AI in Finance: https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance
- Gemini API pricing and context caching — official Google docs: https://ai.google.dev/gemini-api/docs/pricing
- vnstock breaking changes — official docs: https://vnstocks.com/docs/vnstock-insider-api/lich-su-phien-ban

### Secondary (MEDIUM confidence)
- LangGraph + FastAPI SSE streaming guide 2025-26: https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn
- n8n + LangGraph separation pattern: https://www.samirsaci.com/build-an-ai-agent-for-strategic-budget-planning-with-langgraph-and-n8n/
- GraphRAG with Qdrant + Neo4j — official Qdrant docs: https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/
- Mastering LangGraph state management 2025: https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025
- Multi-Agent RAG for investment advisory — academic: https://www.researchgate.net/publication/390816837
- arq vs Celery comparison: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
- FactSet macro regime framework: https://insight.factset.com/mapping-asset-returns-to-economic-regimes-a-practical-investors-guide
- World Gold Council ETF flow data — official source: https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows
- Vietstock platform features — official: https://en.vietstock.vn/about-us.htm
- Simply Wall St features — official: https://simplywall.st/
- Vietnam emerging market context — FTSE Russell official: https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse
- BlackRock ML for macro investing: https://www.blackrock.com/institutions/en-us/insights/machine-learning-macro-investing

### Tertiary (LOW confidence)
- Investment platform features survey — aggregator: https://visualping.io/blog/investment-research-tools
- Vietnam retail investor behavior — peer-reviewed survey (2018): https://pmc.ncbi.nlm.nih.gov/articles/PMC6140283/
- Are AI trading signals reliable 2024–2025: https://www.moneymarketinsights.com/p/are-ai-trading-signals-reliable-data-from-2024-2025

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*
