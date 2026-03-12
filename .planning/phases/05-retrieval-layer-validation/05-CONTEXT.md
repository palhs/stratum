# Phase 5: Retrieval Layer Validation - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate all three retrieval paths (Neo4j CypherTemplateRetriever, Qdrant hybrid dense+sparse, PostgreSQL direct query) independently against real loaded data from Phase 4, with data freshness checks built into every retrieval function. This phase produces the `reasoning/app/retrieval/` module that Phase 6 reasoning nodes will import. No reasoning logic, no LangGraph nodes, no API endpoints — pure retrieval validation.

</domain>

<decisions>
## Implementation Decisions

### Freshness thresholds
- Source-specific thresholds matching each data source's natural update cadence (e.g., weekly data stale after ~10 days, monthly after ~45 days, quarterly after ~120 days — Claude determines exact values per source)
- Warning delivered in the return payload only — a `warnings` list in the result dict. Never raise exceptions for staleness, never block execution
- Freshness checked against `now()` — no caller-provided reference date (historical report generation is not a v2.0 requirement)
- Warnings state facts only: source name, staleness duration, and threshold. No suggested actions — keeps the retrieval layer generic

### Neo4j query patterns
- Hybrid retrieval: use pre-computed HAS_ANALOGUE edges as primary path, but also pass current FRED values so templates can enrich results with live comparison data
- Claude decides the number of Cypher templates based on Phase 6 success criteria and loaded graph structure
- Return typed dataclasses (Pydantic models or Python dataclasses) — downstream nodes get type safety and IDE autocomplete
- Include static LLM narrative from HAS_ANALOGUE edges in the return type — Phase 6 macro_regime node gets both quantitative data and pre-computed context in one retrieval call

### Qdrant hybrid tuning
- Collection-specific dense/sparse weights — macro_docs (FOMC/SBV policy documents) and earnings_docs (company financials) have different document characteristics warranting different weight tuning
- Fixed top-5 retrieval depth across all collections. Simple, predictable token budget for Gemini context window in Phase 6
- Language filtering on retrieval — retriever accepts a language param and filters on the 'lang' payload field. Only returns chunks in the requested language
- Claude decides the metadata filter pattern (whether retriever handles filtering internally or exposes filter params to callers)

### PostgreSQL query scope
- Five tables: stock_fundamentals, structure_markers, fred_indicators, gold_price, gold_etf_ohlcv (adds gold tables beyond ROADMAP RETR-03 minimum — valuation node needs gold context)
- Configurable time window with latest-only as default — queries accept an optional lookback period so valuation node can request last 4 quarters of fundamentals to show trend direction
- Claude decides async (psycopg3) vs sync SQLAlchemy based on LangGraph's execution model and the Phase 3 checkpoint setup
- Claude decides whether to copy SQLAlchemy table definitions or create a shared package

### Validation strategy
- Pytest assertions against live Docker services with Phase 4's seeded data — no mocks for retrieval quality validation
- Tests live in reasoning/tests/ (standard Python project layout within the reasoning-engine service)
- Freshness check validation uses reference date override — pass a fake 'now' to make real data appear stale, without modifying the database

### Module structure
- Shared freshness module: reasoning/app/retrieval/freshness.py with reusable check_freshness() logic imported by each retriever
- Shared types module: reasoning/app/retrieval/types.py with all return dataclasses (RegimeAnalogue, DocumentChunk, FundamentalsRow, etc.) — Phase 6 nodes import from one place
- Claude decides whether to scaffold the broader reasoning/ directory structure or create retrieval module only

### Error handling
- Claude decides retry strategy for transient failures (Neo4j down, Qdrant timeout) based on LangGraph checkpoint/retry semantics
- Raise a specific NoDataError exception when retrieval returns empty results — forces downstream reasoning nodes to acknowledge and handle missing data explicitly
- Structured logging at INFO level: every retrieval call logs query params, result count, elapsed time, and any warnings

### Embedding model
- Use LlamaIndex's built-in embedding integration with FastEmbed bge-small-en-v1.5 — LlamaIndex QdrantVectorStore handles query embedding transparently
- Sparse (BM25) component configuration for hybrid search needs research — technical details of Qdrant/LlamaIndex hybrid search to be determined during Phase 5 research

### Claude's Discretion
- Exact freshness threshold values per data source
- Number and content of Neo4j Cypher templates
- Qdrant metadata filter pattern (internal vs caller-exposed)
- Async vs sync PostgreSQL connection approach
- Table definition sharing strategy (copy vs shared package)
- Retry strategy for transient retrieval failures
- Broader reasoning/ directory scaffolding scope
- Dense/sparse weight values per Qdrant collection

</decisions>

<specifics>
## Specific Ideas

- Retrieval must be validated independently before embedding in LangGraph nodes — bugs inside a 5-node reasoning graph are extremely hard to root-cause (research PITFALLS.md)
- Only CypherTemplateRetriever and TextToCypherRetriever work against the externally-created Neo4j graph — never attempt VectorContextRetriever or LLMSynonymRetriever (research PITFALLS.md)
- Gold tables (gold_price, gold_etf_ohlcv) added to PostgreSQL scope because the valuation node needs gold context alongside VN equities — the product covers both asset classes
- Language filtering is important because FastEmbed bge-small-en-v1.5 produces degraded embeddings for Vietnamese text (Phase 4 flagged this) — returning Vietnamese chunks when English was requested would pollute the reasoning context

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sidecar/app/models.py`: SQLAlchemy Core Table() definitions for all 8 PostgreSQL tables — reasoning-engine needs to reference these schemas
- `sidecar/app/db.py`: SQLAlchemy engine + session pattern (sync, psycopg2) — reasoning-engine will need its own connection but the pattern is established
- `neo4j/init/01_constraints.cypher`: Regime.id and TimePeriod.id uniqueness constraints — Cypher templates should reference these
- `scripts/seed-neo4j-analogues.py`: Shows the HAS_ANALOGUE relationship schema (similarity_score, dimensions_matched, period_start, period_end, narrative)
- `scripts/seed-qdrant-macro-docs.py` / `scripts/seed-qdrant-earnings-docs.py`: Show FastEmbed embedding + Qdrant point structure with payload fields (lang, ticker, source, etc.)

### Established Patterns
- data_as_of + ingested_at timestamp convention on every table row — freshness checks compare data_as_of against thresholds
- FastEmbed 384-dim (BAAI/bge-small-en-v1.5) locked for all Qdrant collections — query embedding must use the same model
- Deterministic uuid5 point IDs in Qdrant — can be used for deduplication awareness in retrieval
- SQLAlchemy Core (not ORM declarative) for all table operations — upsert pattern via pg_insert().on_conflict_do_update()

### Integration Points
- Neo4j bolt://neo4j:7687 — reasoning-engine connects on the reasoning Docker network
- Qdrant HTTP API at qdrant:6333 with QDRANT_API_KEY from environment
- PostgreSQL at postgres:5432/stratum — reasoning-engine reads from same database as sidecar (different connection, same schema)
- Phase 3 checkpoint schema lives in 'langgraph' schema within the stratum database — retrieval queries use the default public schema
- Phase 4 seeded data: ~15-20 regime nodes, HAS_ANALOGUE relationships, macro_docs_v1 collection, earnings_docs_v1 collection

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-retrieval-layer-validation*
*Context gathered: 2026-03-12*
