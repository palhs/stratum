# Phase 4: Knowledge Graph and Document Corpus Population - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Populate Neo4j with historical macro regime nodes (2008-2025) carrying FRED series values and VN macro properties, connect them via HAS_ANALOGUE relationships with quantitative similarity scores and static LLM-generated narratives, populate Qdrant macro_docs collection with curated Fed FOMC minutes and SBV reports, and populate Qdrant earnings_docs collection with VN30 company earnings transcripts. This phase is pure data population — no retrieval logic, no reasoning nodes, no API endpoints.

</domain>

<decisions>
## Implementation Decisions

### Regime period definitions
- Hybrid approach: hand-defined era names and date boundaries, populated with FRED series values for each period
- Detailed granularity: ~15-20 regime nodes, breaking major eras into sub-phases (e.g., GFC split into 'credit crisis' + 'QE1 response', rate hike cycle into 'initial hikes' + 'terminal rate plateau')
- FRED dimensions: match exactly what's already in the fred_indicators table from v1.0 ingestion — no gaps between stored data and regime references
- Include VN-specific macro properties alongside US FRED data: SBV reference rate, VN CPI, VND/USD on each regime node (requires manual data curation since VN macro isn't in FRED)

### Document corpus sourcing
- Fed FOMC: key turning points only (~10-15 docs) — major policy shifts: rate cuts during GFC, QE announcements, taper tantrum, rate hike starts/pauses, COVID response, 2022-2023 tightening
- SBV: rate decisions + monetary policy reports (~20-30 docs) — SBV refinancing/discount rate changes with policy statements, plus quarterly/annual monetary policy reports
- VN30 earnings: latest 4 quarters per company (~120 docs) — all 30 VN30 companies, most recent year of earnings transcripts
- Language note: SBV and VN earnings docs may be in Vietnamese — embedding model handles this or documents need translation consideration

### Analogue similarity design
- FRED metric distance + Gemini narrative scoring (both-layer approach per PROJECT.md decision)
- Threshold-based connectivity: only create HAS_ANALOGUE relationships for top 3-5 analogues per regime (not fully connected graph)
- Use HAS_ANALOGUE relationship type (roadmap spec), not RESEMBLES (existing v1.0 type stays for backwards compatibility)
- HAS_ANALOGUE carries: similarity_score, dimensions_matched, period_start, period_end (richer schema than RESEMBLES)
- Both static narrative + runtime interpretation: Phase 4 generates a static narrative summary per analogue pair (stored as property on HAS_ANALOGUE edge), Phase 6 macro_regime node uses both static narrative and live Gemini interpretation in query context

### Claude's Discretion
- Document chunking strategy — optimal approach based on document types and FastEmbed 384-dim model characteristics
- Exact regime period boundaries and names within the 2008-2025 range
- VN macro data sourcing approach (manual CSV, web scraping, or hardcoded values)
- Similarity threshold value for HAS_ANALOGUE relationship creation
- Whether to update APOC trigger for HAS_ANALOGUE or handle validation in application layer

</decisions>

<specifics>
## Specific Ideas

- Regime nodes should carry enough FRED data that the macro_regime reasoning node in Phase 6 can compare "current conditions" against historical analogues quantitatively
- Static LLM narratives on HAS_ANALOGUE edges serve as pre-computed context — reduces Gemini API calls during report generation while still allowing runtime interpretation for query-aware analysis
- VN macro properties on regime nodes enable the reasoning pipeline to ground VN-specific analysis in historical context, not just US macro
- Earnings corpus covers all VN30 (not just top 10) because the batch validation in Phase 9 tests 20-stock workloads — corpus must support that scale

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `neo4j/init/01_constraints.cypher`: Regime.id and TimePeriod.id uniqueness constraints already in place
- `neo4j/init/02_apoc_triggers.cypher`: RESEMBLES trigger pattern can inform HAS_ANALOGUE validation
- `scripts/init-qdrant.sh`: Collection creation via curl HTTP API — macro_embeddings_v1 (384-dim Cosine) with alias pattern established
- `sidecar/app/db.py`: SQLAlchemy Core database connection pattern for reading fred_indicators

### Established Patterns
- One-shot Docker init services: flyway, neo4j-init, qdrant-init, langgraph-init — all follow depends_on + service_healthy + no restart
- Qdrant alias versioning: versioned collection (macro_embeddings_v1) + stable alias (macro_embeddings)
- Neo4j cypher-shell execution: neo4j-init runs .cypher files via cypher-shell against bolt://neo4j:7687
- FastEmbed 384-dim (BAAI/bge-small-en-v1.5) locked for all Qdrant collections

### Integration Points
- Neo4j bolt://neo4j:7687 on both ingestion and reasoning networks
- Qdrant HTTP API at qdrant:6333 with QDRANT_API_KEY
- PostgreSQL fred_indicators table: source of FRED dimension values for regime nodes
- New Qdrant collections (macro_docs, earnings_docs) need creation in init-qdrant.sh or separate init script
- Seed scripts (Cypher for Neo4j, Python for Qdrant) need a runner mechanism — either extend existing init services or new seed services

</code_context>

<deferred>
## Deferred Ideas

- Vietnamese financial term dictionary — Phase 6 prerequisite, content asset not code. Noted in STATE.md pending todos but out of Phase 4 scope.
- Automated document ingestion pipelines — explicitly deferred to v3.0 (INGEST-01 in REQUIREMENTS.md future section)

</deferred>

---

*Phase: 04-knowledge-graph-and-document-corpus-population*
*Context gathered: 2026-03-09*
