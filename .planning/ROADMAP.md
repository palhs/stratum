# Roadmap: Stratum

## Overview

Stratum is built in seven phases following the hard dependency chain of its two-pipeline architecture. Infrastructure and storage come first because every other component writes to or reads from it. Ingestion populates the stores with real data. Retrieval validation confirms LlamaIndex can execute the specific Cypher and hybrid search patterns before they are embedded inside a reasoning graph. The analytical reasoning nodes are then built and validated individually, followed by the synthesis layer that wires them into a complete bilingual report. The API layer exposes the working pipeline with streaming job progress. The frontend renders reports in the research-report aesthetic and delivers the user-facing platform. Phase 4 is the intellectual core and highest-risk phase — all four critical pitfalls (LLM hallucination, stale data, regime overconfidence, score framing) must be addressed here or in Phase 5 before the API or frontend are worth building.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure and Storage Foundation** - Docker Compose environment with all storage services running and schemas designed for correctness from day one
- [ ] **Phase 2: Data Ingestion Pipeline** - All external data sources flowing into storage with pre-computed markers, timestamps, and pipeline health monitoring
- [ ] **Phase 3: Retrieval Layer Validation** - LlamaIndex retrievers confirmed working against real loaded data before being embedded in reasoning nodes
- [ ] **Phase 4: Analytical Reasoning Nodes** - MacroRegimeClassifier, ValuationContextualizer, and StructureAnalyzer nodes producing validated sub-assessments
- [ ] **Phase 5: Synthesis, Reports, and Explainability** - EntryQualityScorer and ReportComposer completing the full reasoning chain with bilingual report output
- [ ] **Phase 6: API Layer and Platform** - FastAPI gateway exposing report generation and watchlist management with SSE streaming and LangGraph state persistence
- [ ] **Phase 7: Frontend** - Next.js report viewer delivering the research-report aesthetic with Supabase auth, structured report cards, and real-time pipeline progress

## Phase Details

### Phase 1: Infrastructure and Storage Foundation
**Goal**: All storage services are running on the VPS with schemas designed correctly from the start — no schema migrations required when data is loaded
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02
**Success Criteria** (what must be TRUE):
  1. All services (PostgreSQL, Neo4j, Qdrant, n8n, Supabase) start and pass health checks via a single `docker compose up` command
  2. PostgreSQL schema includes `data_as_of` and `ingested_at` on every time-series table and a `pipeline_run_log` table from the first migration
  3. Neo4j schema enforces that RESEMBLES relationships carry `similarity_score`, `dimensions_matched`, and `period` properties — no bare relationships exist
  4. Qdrant collections are created with named versions and the storage boundary is enforced (n8n and LangGraph containers have no network path to each other, only to storage)
  5. All services are reachable from the host at documented ports and Nginx reverse proxy is configured with SSE-compatible headers
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Docker Compose infrastructure stack with dual-network isolation, health checks, profiles, Makefile, and VPS provisioning
- [x] 01-02-PLAN.md — Storage schemas and initialization (PostgreSQL Flyway migration, Neo4j constraints + APOC triggers, Qdrant collection with alias versioning)

### Phase 2: Data Ingestion Pipeline
**Goal**: All external data sources are flowing into storage on schedule with pre-computed structure markers, full timestamp metadata, and automatic detection of pipeline failures and data anomalies
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09
**Success Criteria** (what must be TRUE):
  1. Vietnamese stock OHLCV and fundamental data (P/E, P/B, EPS) are loaded into PostgreSQL on a weekly/monthly cadence via vnstock, with version pinned and wrapped in error handling that distinguishes API errors from empty results
  2. Gold price data, ETF flow data, and central bank buying data from World Gold Council are in PostgreSQL with the 45-day publication lag modeled as a source property
  3. FRED macroeconomic indicators (GDP, inflation, unemployment, interest rates) are in PostgreSQL with correct `data_as_of` timestamps reflecting the period they cover, not the ingestion date
  4. Every row in every time-series table has both `data_as_of` and `ingested_at` populated — zero rows with NULL in either column
  5. Pre-computed structure markers (moving averages, drawdown from ATH, valuation percentiles) exist in PostgreSQL for all assets — LangGraph reads them, never computes them
  6. Every pipeline run writes a record to `pipeline_run_log` with success/failure status, and vnstock row-count anomalies (greater than 50% deviation from 4-week moving average) generate an alert
**Plans**: TBD

Plans:
- [ ] 02-01: vnstock ingestion — OHLCV and fundamentals with version pinning and row-count anomaly detection
- [ ] 02-02: Gold and World Gold Council data ingestion with publication lag modeling
- [ ] 02-03: FRED macroeconomic indicator ingestion
- [ ] 02-04: Pre-computation of structure markers during ingestion
- [ ] 02-05: Pipeline run logging and health monitoring

### Phase 3: Retrieval Layer Validation
**Goal**: LlamaIndex retrievers are confirmed working against real data loaded in Phase 2, with custom Cypher templates validated against the Neo4j schema and hybrid search confirmed returning useful results from Qdrant — before these retrievers are embedded inside the reasoning graph
**Depends on**: Phase 2
**Requirements**: MACRO-04
**Success Criteria** (what must be TRUE):
  1. Neo4j RESEMBLES relationships in the loaded graph carry `similarity_score`, `dimensions_matched`, and `period` on every relationship — retrievable via the custom Cypher templates that Phase 4 nodes will use
  2. A test query against the Neo4j knowledge graph returns macro regime analogues with full relationship properties (not just node IDs) using LlamaIndex GraphRAGRetriever with registered custom Cypher templates
  3. A test query against Qdrant returns relevant financial documents via hybrid search (dense + sparse BM25) — not dense-only
  4. FastEmbed embedding model produces consistent vectors for the asset identifiers and regime terminology used in the Vietnamese market context
**Plans**: TBD

Plans:
- [ ] 03-01: LlamaIndex GraphRAGRetriever setup with custom Neo4j Cypher templates
- [ ] 03-02: LlamaIndex HybridRetriever setup for Qdrant with FastEmbed integration
- [ ] 03-03: Retrieval quality validation against loaded data

### Phase 4: Analytical Reasoning Nodes
**Goal**: The three analytical LangGraph nodes — MacroRegimeClassifier, ValuationContextualizer, and StructureAnalyzer — produce validated sub-assessments with correct handling of mixed signals, out-of-range values, and limited historical precedent
**Depends on**: Phase 3
**Requirements**: MACRO-01, MACRO-02, MACRO-03, MACRO-05, VAL-01, VAL-02, VAL-03, VAL-04, STRUC-01, STRUC-02, STRUC-03
**Success Criteria** (what must be TRUE):
  1. MacroRegimeClassifier outputs a probability distribution across candidate regimes (not a single label) and surfaces "Mixed Signal Environment" with multiple analogues when top confidence is below 70%
  2. MacroRegimeClassifier communicates explicitly when the current environment has limited historical precedent rather than forcing a low-confidence analogy
  3. ValuationContextualizer assesses each asset's valuation relative to its own historical range and contextualizes it within the current macro regime — regime-relative valuation, not raw percentile alone
  4. ValuationContextualizer handles historically unprecedented valuation levels with explicit communication ("this level has no direct historical precedent") rather than misleading out-of-range labels, and flags ETF flow vs physical demand divergence for gold when signals contradict
  5. StructureAnalyzer produces a price structure sub-assessment using pre-computed MA positioning, drawdown from ATH, and trend context, framed as entry timing context within a fundamental thesis — not as standalone trading signals
**Plans**: TBD

Plans:
- [ ] 04-01: LangGraph StateGraph skeleton and MacroRegimeClassifier node
- [ ] 04-02: Neo4j regime seed data curation and analogue relationship population
- [ ] 04-03: ValuationContextualizer node with regime-relative context and out-of-range handling
- [ ] 04-04: StructureAnalyzer node with pre-computed marker consumption
- [ ] 04-05: Mixed-signal and limited-precedent test cases

### Phase 5: Synthesis, Reports, and Explainability
**Goal**: EntryQualityScorer and ReportComposer complete the reasoning chain, producing a qualitative entry quality assessment with full reasoning decomposition and bilingual report output — with every numeric claim grounded to retrieved database records and conflicting signals handled explicitly
**Depends on**: Phase 4
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, AI-07, AI-08, RPT-01, RPT-02, RPT-03, RPT-05
**Success Criteria** (what must be TRUE):
  1. EntryQualityScorer produces a qualitative tier (Favorable / Neutral / Cautious / Avoid) with reasoning decomposition that shows all three sub-assessments (macro, valuation, structure) before the composite — never a numeric score alone
  2. Every numeric claim in a generated report is traceable to a specific retrieved database record — a grounding check node at the end of the chain fails noisily if any number cannot be attributed to a source
  3. Conflicting signals are surfaced explicitly with "strong thesis, weak structure — wait for structural confirmation" type language — not silently averaged away
  4. Report language uses probabilistic framing throughout ("suggests," "conditions consistent with") and contains no instances of "buy," "sell," or "entry confirmed"
  5. Reports are generated in both Vietnamese (primary) and English, with Vietnamese as native generation (not translation), using a consistent Vietnamese financial terminology dictionary
  6. If one reasoning step fails, the system completes the remaining steps and flags the missing component in the report rather than aborting — partial reports are better than no report
  7. LangGraph StateGraph uses named nodes (MacroRegimeClassifier, ValuationContextualizer, StructureAnalyzer, EntryQualityScorer, ReportComposer) and each step logs its input, data source, and output to the state
**Plans**: TBD

Plans:
- [ ] 05-01: EntryQualityScorer node with qualitative tier output and sub-assessment decomposition
- [ ] 05-02: Grounding check node — numeric claim attribution validation
- [ ] 05-03: ReportComposer node — bilingual structured report generation
- [ ] 05-04: Vietnamese financial terminology dictionary and bilingual generation quality validation
- [ ] 05-05: Partial-failure handling and conflicting signal output
- [ ] 05-06: langgraph-checkpoint-postgres integration and end-to-end reasoning pipeline test

### Phase 6: API Layer and Platform
**Goal**: FastAPI exposes the reasoning pipeline with background task execution, SSE streaming of step progress, and watchlist CRUD — with LangGraph state persisted for audit and recovery, and the monthly report cadence and on-demand generation triggered correctly
**Depends on**: Phase 5
**Requirements**: INFRA-03, INFRA-04, USER-01, USER-02, USER-03
**Success Criteria** (what must be TRUE):
  1. POST /reports/generate returns a job_id immediately and executes report generation as a background task — the HTTP connection is never held open for the full 30–120 second pipeline run
  2. GET /reports/stream/{job_id} streams SSE events showing reasoning step progress (MacroRegimeClassifier running, ValuationContextualizer complete, etc.) in real time
  3. User can add and remove assets from their watchlist via CRUD endpoints, and adding a new asset triggers immediate on-demand report generation using the latest available data
  4. Monthly report generation runs automatically for all watchlist assets via scheduled execution — no manual trigger required
  5. LangGraph state is persisted via langgraph-checkpoint-postgres — an interrupted report generation run can be inspected for audit and the state is recoverable
**Plans**: TBD

Plans:
- [ ] 06-01: FastAPI application setup with Supabase JWT verification middleware
- [ ] 06-02: Report generation endpoint with BackgroundTask and job status polling
- [ ] 06-03: SSE streaming endpoint for reasoning step progress
- [ ] 06-04: Watchlist CRUD endpoints and on-demand report trigger
- [ ] 06-05: Monthly report cadence scheduler and langgraph-checkpoint-postgres integration

### Phase 7: Frontend
**Goal**: The Next.js application delivers the research-report aesthetic with structured report cards, real-time pipeline progress, price structure charts, Supabase authentication, and the watchlist management UI — making the platform usable end-to-end by the first user
**Depends on**: Phase 6
**Requirements**: RPT-04, USER-04
**Success Criteria** (what must be TRUE):
  1. User can log in via Supabase auth and access their watchlist — unauthenticated users cannot access any report or watchlist data
  2. Report view presents four structured cards (macro regime, valuation, price structure, entry quality) with the three sub-assessments visible before the composite entry quality tier — the entry quality tier is never the headline
  3. Reports feel like research documents, not trading terminals: narrative text is primary, lightweight-charts OHLCV with structure markers support the story, no candlestick-heavy trading UI elements
  4. SSE step-progress UI shows the reasoning pipeline executing in real time — user sees which node is running and which have completed, giving clear feedback during the 30–120 second generation window
  5. Data freshness is visible in the report UI for each data source, and missing data components display specific unavailability messages rather than generic "N/A"
**Plans**: TBD

Plans:
- [ ] 07-01: Supabase SSR auth integration and protected routing
- [ ] 07-02: Watchlist management UI
- [ ] 07-03: Report card layout and structured report viewer
- [ ] 07-04: SSE pipeline progress UI
- [ ] 07-05: lightweight-charts integration for price structure context
- [ ] 07-06: Bilingual UI, Vietnamese term glossary sidebar, and data freshness indicators

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure and Storage Foundation | 2/2 | Complete | 2026-03-03 |
| 2. Data Ingestion Pipeline | 1/5 | In Progress|  |
| 3. Retrieval Layer Validation | 0/3 | Not started | - |
| 4. Analytical Reasoning Nodes | 0/5 | Not started | - |
| 5. Synthesis, Reports, and Explainability | 0/6 | Not started | - |
| 6. API Layer and Platform | 0/5 | Not started | - |
| 7. Frontend | 0/6 | Not started | - |
