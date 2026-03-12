# Roadmap: Stratum

## Overview

Stratum is built in phases following the hard dependency chain of its two-pipeline architecture. v1.0 delivered infrastructure and data ingestion (Phases 1-2). v2.0 builds the analytical reasoning engine on top, starting from infrastructure hardening (Phase 3) through knowledge graph population, retrieval validation, individual reasoning nodes, graph assembly with end-to-end report generation, the FastAPI gateway, and finally production hardening under realistic batch load (Phase 9). The dependency chain is strict and unidirectional: data must be in stores before retrieval can be validated; retrieval must be validated before reasoning nodes can be built; nodes must be individually validated before the graph can be assembled; the graph must produce a valid report before the API wrapper is worth building; and single-asset success must be stress-tested at batch scale before v2.0 is complete.

## Milestones

- ✅ **v1.0 Infrastructure and Data Ingestion** — Phases 1-2 (shipped 2026-03-09)
- 🚧 **v2.0 Analytical Reasoning Engine** — Phases 3-9 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Infrastructure and Data Ingestion (Phases 1-2) — SHIPPED 2026-03-09</summary>

- [x] **Phase 1: Infrastructure and Storage Foundation** (2/2 plans) — completed 2026-03-03
- [x] **Phase 2: Data Ingestion Pipeline** (5/5 plans) — completed 2026-03-08

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

### 🚧 v2.0 Analytical Reasoning Engine (In Progress)

**Milestone Goal:** Build the multi-step AI reasoning pipeline that transforms raw market data into actionable entry quality assessments with explainable, bilingual analysis.

- [x] **Phase 3: Infrastructure Hardening and Database Migrations** - Flyway migrations, memory limits, VPS swap, and checkpoint schema in place before any reasoning code is written (completed 2026-03-09)
- [x] **Phase 4: Knowledge Graph and Document Corpus Population** - Neo4j regime nodes with analogue relationships and Qdrant document collections populated with curated content (completed 2026-03-09)
- [ ] **Phase 5: Retrieval Layer Validation** - LlamaIndex retrievers confirmed working against real loaded data across all three stores before embedding in reasoning nodes
- [ ] **Phase 6: LangGraph Reasoning Nodes** - Five individual reasoning nodes built and validated in isolation with correct state schemas and Gemini structured output
- [ ] **Phase 7: Graph Assembly and End-to-End Report Generation** - StateGraph assembled and first complete bilingual report produced, grounded, and stored in PostgreSQL
- [ ] **Phase 8: FastAPI Gateway and Docker Service** - HTTP gateway exposing the validated reasoning pipeline with background execution and SSE streaming
- [ ] **Phase 9: Production Hardening and Batch Validation** - Batch behavior validated at 20-stock scale with memory baseline, spend alerts, and checkpoint cleanup

## Phase Details

### Phase 3: Infrastructure Hardening and Database Migrations
**Goal**: All infrastructure prerequisites are in place before any reasoning code is written — Flyway migrations create the reports and report_jobs tables, all Docker services have explicit memory limits, VPS swap is configured, Neo4j JVM heap is set, GEMINI_API_KEY is available, and the LangGraph checkpoint schema is initialized
**Depends on**: Phase 2
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. Running `flyway migrate` applies V6 and V7 cleanly — the `reports` table and `report_jobs` table exist in PostgreSQL with all columns and constraints visible via `\d reports` and `\d report_jobs`
  2. All existing Docker services in `docker-compose.yml` have explicit `mem_limit` values (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, data-sidecar 512MB) — `docker inspect` confirms limits on running containers. reasoning-engine `mem_limit: 2g` is set when the service is created in Phase 8.
  3. VPS swap is active at 4GB (`free -h` shows 4G swap) and Neo4j JVM heap is explicitly set in docker-compose.yml — Neo4j starts without defaulting to 25% of system RAM
  4. `GEMINI_API_KEY` is present in `.env.example` as a documented environment variable template — live API validation is a runtime verification item performed when the reasoning-engine service is deployed in Phase 8
  5. LangGraph checkpoint schema is initialized in PostgreSQL — the checkpoint tables created by `AsyncPostgresSaver.setup()` exist and are queryable
**Plans**: TBD

Plans:
- [x] 03-01: Flyway V6 and V7 migrations — reports and report_jobs tables
- [x] 03-02: Docker Compose memory limits, VPS swap, Neo4j JVM heap, and GEMINI_API_KEY configuration
- [x] 03-03: LangGraph checkpoint schema initialization and validation
- [x] 03-04: Documentation gap closure — ROADMAP.md and REQUIREMENTS.md Phase 3 scope alignment

### Phase 4: Knowledge Graph and Document Corpus Population
**Goal**: The Neo4j knowledge graph contains historical macro regime nodes covering 2008-2025 with HAS_ANALOGUE relationships carrying full similarity metadata, and Qdrant macro_docs and earnings_docs collections are populated with curated content — both are prerequisites for any retrieval or reasoning work
**Depends on**: Phase 3
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. Neo4j contains macro regime nodes spanning major economic periods from 2008-2025 — a Cypher query `MATCH (r:Regime) RETURN count(r)` returns a non-zero count and each node carries FRED series values for the period
  2. Neo4j `HAS_ANALOGUE` relationships exist between regime nodes, each carrying `similarity_score`, `dimensions_matched`, `period_start`, and `period_end` — a Cypher query traversing these relationships returns full relationship properties (not just node IDs)
  3. Qdrant `macro_docs` collection is populated — a similarity search for "Federal Reserve rate decision" returns relevant Fed FOMC minutes or SBV report chunks with scores above 0.7
  4. Qdrant `earnings_docs` collection is populated — a similarity search for a VN30 company ticker returns relevant earnings transcript chunks from that company's filings
**Plans**: 4 plans

Plans:
- [x] 04-01: Neo4j regime node seed data and Python seed script + Qdrant macro_docs/earnings_docs collection creation
- [x] 04-02: HAS_ANALOGUE relationship computation with cosine similarity and Gemini static narratives
- [x] 04-03: Qdrant macro_docs population — Fed FOMC minutes download and SBV report manifests
- [x] 04-04: Qdrant earnings_docs population — VN30 structured financials via vnstock API

### Phase 5: Retrieval Layer Validation
**Goal**: All three retrieval paths (Neo4j via LlamaIndex CypherTemplateRetriever, Qdrant via LlamaIndex hybrid dense+sparse, PostgreSQL via direct query) are independently validated against real loaded data with data freshness checks built into every retrieval function — before any retriever is embedded inside a LangGraph node
**Depends on**: Phase 4
**Requirements**: RETR-01, RETR-02, RETR-03, RETR-04
**Success Criteria** (what must be TRUE):
  1. A test call to the Neo4j CypherTemplateRetriever with a representative macro query returns regime analogue nodes with full `HAS_ANALOGUE` relationship properties — result includes `similarity_score`, `dimensions_matched`, `period_start`, `period_end` on every returned relationship
  2. A test call to the Qdrant hybrid retriever (dense + sparse) with a representative financial query returns more relevant results than dense-only search — validated by manual inspection of the top-5 results for at least three representative queries
  3. Direct PostgreSQL query functions for fundamentals, structure_markers, and fred_indicators tables return structured data matching the schema — each function is called with a real asset identifier and returns non-empty results
  4. Every retrieval function emits an explicit warning (logged and returned in the result payload) when `data_as_of` exceeds the freshness threshold — validated by running each retriever against a row with a deliberately stale `data_as_of` date and confirming the warning appears
**Plans**: 3 plans

Plans:
- [ ] 05-01: Scaffold reasoning/ module, shared types/freshness, Qdrant collection migration to named-vector hybrid config
- [ ] 05-02: Neo4j CypherTemplateRetriever and PostgreSQL direct query retrievers with integration tests
- [ ] 05-03: Qdrant hybrid dense+sparse retriever with language filtering and full retrieval layer validation

### Phase 6: LangGraph Reasoning Nodes
**Goal**: Five LangGraph nodes (structure, valuation, macro_regime, entry_quality, grounding_check) and one special-case handler (conflicting_signals) are built and validated individually with mock state — each produces Pydantic-validated structured output, consumes only what the next node needs, and handles edge cases (mixed signals, missing data, conflicting sub-assessments) explicitly
**Depends on**: Phase 5
**Requirements**: REAS-01, REAS-02, REAS-03, REAS-04, REAS-05, REAS-07
**Success Criteria** (what must be TRUE):
  1. The macro_regime node outputs a probability distribution over regime types — when the top confidence is below 70%, the output explicitly labels the result "Mixed Signal Environment" and surfaces the two most likely analogues rather than forcing a single-label answer
  2. The valuation node produces regime-relative assessments for VN equities (P/E, P/B vs historical analogues from Neo4j) and gold (real yield context, ETF flow) — the output cites the specific retrieved analogue and period used for comparison
  3. The structure node interprets pre-computed v1.0 markers (MAs, drawdown from ATH, percentile) into a price structure narrative without recomputing any values — the node reads only from PostgreSQL structure_markers and produces narrative output referencing those stored values
  4. The entry_quality node outputs a qualitative tier (Favorable / Neutral / Cautious / Avoid) with all three sub-assessments (macro, valuation, structure) explicitly present in the output before the composite tier — no numeric score is produced
  5. The grounding_check node verifies that every numeric claim in intermediate node outputs traces to a specific retrieved database record ID — it raises an explicit error (not a warning) if any number cannot be attributed to a source
  6. When sub-assessments disagree (e.g., strong macro thesis but weak price structure), the conflicting signal handler produces an explicit "strong thesis, weak structure" output type — the disagreement is surfaced in the node output, not silently averaged
**Plans**: TBD

Plans:
- [ ] 06-01: ReportState TypedDict with documented reducers and structure node implementation
- [ ] 06-02: Valuation node with regime-relative context and PostgreSQL + Qdrant retrieval integration
- [ ] 06-03: Macro regime classification node with probability distribution and mixed-signal handling
- [ ] 06-04: Entry quality assessment node with qualitative tier and conflicting signal handler
- [ ] 06-05: Grounding check node with numeric claim attribution validation

### Phase 7: Graph Assembly and End-to-End Report Generation
**Goal**: The LangGraph StateGraph assembles all validated nodes into a complete pipeline with PostgreSQL checkpointing, produces a first end-to-end bilingual report for a single test asset, stores it in the PostgreSQL reports table, and the report passes grounding check, data freshness validation, and Vietnamese term consistency review
**Depends on**: Phase 6
**Requirements**: REAS-06, REPT-01, REPT-02, REPT-03, REPT-04, REPT-05
**Success Criteria** (what must be TRUE):
  1. The LangGraph StateGraph definition assembles all nodes with explicit linear edges, an explicit TypedDict state schema with all reducers documented, and PostgreSQL AsyncPostgresSaver checkpointing — the graph definition can be imported and instantiated without errors
  2. A complete pipeline run for a single VN30 test asset produces a JSON report with four structured card sections (macro regime, valuation, structure, entry quality) — each section has the required fields and passes Pydantic schema validation
  3. The same pipeline run produces a Markdown report with human-readable narrative — the narrative uses probabilistic framing throughout and contains no instances of "buy," "sell," or "entry confirmed"
  4. The report is generated in both Vietnamese (primary) and English — the Vietnamese output uses the financial term dictionary throughout, and the bilingual generation is from structured data (not translation of English output)
  5. When `data_as_of` for any data source exceeds its freshness threshold, the report includes an explicit "DATA WARNING" section naming the specific data source and the staleness duration — reports with the WGC gold data gap explicitly flag it
  6. The completed report is written to the PostgreSQL `reports` table with full JSON payload and metadata — a `SELECT` query against `reports` returns the stored record with correct `report_id`, `asset_id`, `generated_at`, and `report_json` fields
**Plans**: TBD

Plans:
- [ ] 07-01: LangGraph StateGraph assembly with AsyncPostgresSaver checkpointing
- [ ] 07-02: JSON structured report output and Pydantic schema validation
- [ ] 07-03: Markdown report rendering and bilingual generation with Vietnamese term dictionary
- [ ] 07-04: Data freshness flag integration and DATA WARNING section generation
- [ ] 07-05: PostgreSQL report storage and end-to-end pipeline integration test

### Phase 8: FastAPI Gateway and Docker Service
**Goal**: A FastAPI reasoning-engine service wraps the validated LangGraph pipeline with a background-task report generation endpoint, a report retrieval endpoint, an SSE progress streaming endpoint, and a health endpoint — packaged as a Docker service on the reasoning network with the `reasoning` profile
**Depends on**: Phase 7
**Requirements**: SRVC-01, SRVC-02, SRVC-03, SRVC-04, SRVC-05
**Success Criteria** (what must be TRUE):
  1. A POST to `/reports/generate` returns a `job_id` immediately (HTTP 202) and runs report generation as a background task — the HTTP connection is not held open for the full pipeline run duration
  2. A GET to `/reports/{id}` returns the completed report JSON when generation is finished, and returns a pending status response when the job is still running
  3. A GET to `/reports/stream/{id}` establishes an SSE connection that emits events for each node transition (node name, status, timestamp) as the pipeline executes — the stream closes cleanly when the pipeline completes
  4. A GET to `/health` returns a 200 response with service status — the health check is callable from within the Docker network without authentication
  5. The reasoning-engine is defined in `docker-compose.yml` on the `reasoning` network with `profiles: ["reasoning"]` and explicit `mem_limit` — `docker compose --profile reasoning up` starts the service cleanly and it connects to PostgreSQL, Neo4j, and Qdrant without errors
**Plans**: TBD

Plans:
- [ ] 08-01: FastAPI application skeleton with health endpoint and Dockerfile
- [ ] 08-02: Report generation endpoint with BackgroundTask and job status tracking
- [ ] 08-03: SSE streaming endpoint for reasoning node progress
- [ ] 08-04: Docker Compose reasoning-engine service definition and end-to-end HTTP trigger test

### Phase 9: Production Hardening and Batch Validation
**Goal**: The v2.0 system is validated under realistic production conditions — a 20-stock batch workload completes within memory limits, Gemini API spend alerts are configured and testable, and a checkpoint cleanup job prevents unbounded PostgreSQL growth
**Depends on**: Phase 8
**Requirements**: SRVC-06, SRVC-07, SRVC-08
**Success Criteria** (what must be TRUE):
  1. A batch run generating reports for 20 VN30 stocks completes without OOM kills to any Docker service — `docker stats` during the run shows all services staying within their configured `mem_limit` values
  2. Gemini API spend alerts are configured with tiered thresholds — a test alert fires correctly at the configured threshold and the configuration is documented in the project
  3. The checkpoint cleanup job runs against the PostgreSQL checkpoint tables and removes records older than the configured TTL — a test run with synthetic old records confirms deletion and the job does not affect records newer than the TTL
**Plans**: TBD

Plans:
- [ ] 09-01: Batch report generation test against 20-stock workload with memory baseline
- [ ] 09-02: Gemini API spend alert configuration with tiered thresholds
- [ ] 09-03: Checkpoint cleanup job implementation with TTL-based purge

## Progress

**Execution Order:**
Phases execute in numeric order: 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure and Storage Foundation | v1.0 | 2/2 | Complete | 2026-03-03 |
| 2. Data Ingestion Pipeline | v1.0 | 5/5 | Complete | 2026-03-08 |
| 3. Infrastructure Hardening and Database Migrations | v2.0 | 4/4 | Complete | 2026-03-09 |
| 4. Knowledge Graph and Document Corpus Population | 4/4 | Complete   | 2026-03-09 | - |
| 5. Retrieval Layer Validation | 2/3 | In Progress|  | - |
| 6. LangGraph Reasoning Nodes | v2.0 | 0/5 | Not started | - |
| 7. Graph Assembly and End-to-End Report Generation | v2.0 | 0/5 | Not started | - |
| 8. FastAPI Gateway and Docker Service | v2.0 | 0/4 | Not started | - |
| 9. Production Hardening and Batch Validation | v2.0 | 0/3 | Not started | - |
