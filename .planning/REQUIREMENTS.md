# Requirements: Stratum

**Defined:** 2026-03-09
**Core Value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.

## v2.0 Requirements

Requirements for v2.0 Analytical Reasoning Engine. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: Flyway V6 migration creates `reports` table for storing generated report JSON and metadata
- [x] **INFRA-02**: Flyway V7 migration creates `report_jobs` table for tracking pipeline run status
- [x] **INFRA-03**: Docker Compose has explicit `mem_limit` on all existing services (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, data-sidecar 512MB); reasoning-engine 2GB deferred to Phase 8 when service is created
- [x] **INFRA-04**: VPS swap configured at 4GB and Neo4j JVM heap explicitly set
- [x] **INFRA-05**: `GEMINI_API_KEY` added to environment configuration
- [x] **INFRA-06**: LangGraph checkpoint database schema initialized (psycopg3-based PostgresSaver)

### Data Population

- [ ] **DATA-01**: Neo4j seeded with historical macro regime nodes covering major economic periods (2008-2025) with FRED series values
- [ ] **DATA-02**: Neo4j regime nodes connected via `HAS_ANALOGUE` relationships carrying `similarity_score`, `dimensions_matched`, `period_start`, `period_end`
- [ ] **DATA-03**: Qdrant `macro_docs` collection populated with curated Fed FOMC minutes and SBV reports
- [ ] **DATA-04**: Qdrant `earnings_docs` collection populated with curated VN30 company earnings transcripts

### Retrieval

- [ ] **RETR-01**: LlamaIndex Neo4j retriever (CypherTemplateRetriever) validated against loaded regime graph data
- [ ] **RETR-02**: LlamaIndex Qdrant retriever (hybrid dense+sparse) validated against document corpus
- [ ] **RETR-03**: PostgreSQL direct query patterns validated against fundamentals, structure_markers, and FRED indicator tables
- [ ] **RETR-04**: Every retrieval function includes `data_as_of` freshness check and emits warnings when thresholds are exceeded

### Reasoning

- [ ] **REAS-01**: Macro regime classification node outputs probability distribution over regime types with mixed-signal handling (top confidence < 70% surfaces "Mixed Signal Environment")
- [ ] **REAS-02**: Valuation assessment node produces regime-relative valuation for VN equities (P/E, P/B vs historical analogues) and gold (real yield, ETF flow context)
- [ ] **REAS-03**: Price structure node interprets pre-computed v1.0 markers (MAs, drawdown, percentile) into narrative without recomputation
- [ ] **REAS-04**: Entry quality assessment node outputs qualitative tier (Favorable / Neutral / Cautious / Avoid) with three visible sub-assessments (macro, valuation, structure)
- [ ] **REAS-05**: Grounding check node verifies every numeric claim in report output traces to a specific retrieved database record
- [ ] **REAS-06**: LangGraph StateGraph assembles all nodes with explicit TypedDict state, documented reducers, and PostgreSQL checkpointing
- [ ] **REAS-07**: Conflicting signal handling produces explicit "strong thesis, weak structure" report type when sub-assessments disagree

### Reports

- [ ] **REPT-01**: Report output in structured JSON format with card sections (macro regime, valuation, structure, entry quality)
- [ ] **REPT-02**: Report output rendered as Markdown with human-readable narrative
- [ ] **REPT-03**: Bilingual generation (Vietnamese primary, English secondary) from structured data using Gemini native Vietnamese
- [ ] **REPT-04**: Reports include explicit "DATA WARNING" sections when `data_as_of` exceeds freshness thresholds
- [ ] **REPT-05**: Reports stored in PostgreSQL `reports` table with full JSON and metadata

### Service

- [ ] **SRVC-01**: FastAPI reasoning-engine service with `POST /reports/generate` endpoint (BackgroundTask)
- [ ] **SRVC-02**: `GET /reports/{id}` endpoint returns completed report
- [ ] **SRVC-03**: `GET /reports/stream/{id}` SSE endpoint for pipeline progress
- [ ] **SRVC-04**: `GET /health` endpoint for service monitoring
- [ ] **SRVC-05**: reasoning-engine Docker service added to `docker-compose.yml` on `reasoning` network with `profiles: ["reasoning"]`
- [ ] **SRVC-06**: Batch report generation validated against 20-stock workload with memory baseline
- [ ] **SRVC-07**: Gemini API spend alerts configured with tiered thresholds
- [ ] **SRVC-08**: Checkpoint cleanup job implemented (TTL-based purge)

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### v3.0 — User-Facing Delivery

- **WATCH-01**: User can manage a stock watchlist
- **WATCH-02**: User can trigger on-demand report generation for new watchlist additions
- **FRONT-01**: Next.js frontend renders report cards with TradingView charts
- **FRONT-02**: User can browse report history
- **AUTH-01**: Supabase authentication with user accounts
- **INGEST-01**: Automated document ingestion pipelines (Fed minutes, SBV reports, earnings)
- **LLM-01**: Local LLM fallback via Ollama for cost/privacy flexibility
- **TERM-01**: Comprehensive Vietnamese financial terminology dictionary

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Single numeric entry quality score (e.g., 7.3/10) | Anti-feature: encourages "score = buy" reasoning, bypasses the analytical chain; qualitative tier is the correct output |
| AI chat / Q&A over reports | Unpredictable output quality, increases LLM cost non-linearly, may generate apparent investment advice |
| Real-time regime updates | Regime classification is monthly/quarterly cadence; real-time adds noise, not value |
| Per-asset portfolio context | Moves product from research advisor to portfolio manager; different product entirely |
| Backtesting of entry quality | VN30 market history too short for statistically meaningful backtesting of multi-layer signals |
| PDF export | v3.0 frontend concern; JSON + Markdown sufficient for v2.0 |
| Real-time or intraday data | Weekly/monthly cadence only |
| Mobile app | Web-first |
| Multi-user scale | Single user at launch |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 3 | Complete |
| INFRA-02 | Phase 3 | Complete |
| INFRA-03 | Phase 3 | Complete |
| INFRA-04 | Phase 3 | Complete |
| INFRA-05 | Phase 3 | Complete |
| INFRA-06 | Phase 3 | Complete |
| DATA-01 | Phase 4 | Pending |
| DATA-02 | Phase 4 | Pending |
| DATA-03 | Phase 4 | Pending |
| DATA-04 | Phase 4 | Pending |
| RETR-01 | Phase 5 | Pending |
| RETR-02 | Phase 5 | Pending |
| RETR-03 | Phase 5 | Pending |
| RETR-04 | Phase 5 | Pending |
| REAS-01 | Phase 6 | Pending |
| REAS-02 | Phase 6 | Pending |
| REAS-03 | Phase 6 | Pending |
| REAS-04 | Phase 6 | Pending |
| REAS-05 | Phase 6 | Pending |
| REAS-07 | Phase 6 | Pending |
| REAS-06 | Phase 7 | Pending |
| REPT-01 | Phase 7 | Pending |
| REPT-02 | Phase 7 | Pending |
| REPT-03 | Phase 7 | Pending |
| REPT-04 | Phase 7 | Pending |
| REPT-05 | Phase 7 | Pending |
| SRVC-01 | Phase 8 | Pending |
| SRVC-02 | Phase 8 | Pending |
| SRVC-03 | Phase 8 | Pending |
| SRVC-04 | Phase 8 | Pending |
| SRVC-05 | Phase 8 | Pending |
| SRVC-06 | Phase 9 | Pending |
| SRVC-07 | Phase 9 | Pending |
| SRVC-08 | Phase 9 | Pending |

**Coverage:**
- v2.0 requirements: 34 total (note: prior traceability section incorrectly stated 30; actual count is 34)
- Mapped to phases: 34
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 — traceability populated after roadmap creation (Phases 3-9)*
