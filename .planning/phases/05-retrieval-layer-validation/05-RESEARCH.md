# Phase 5: Retrieval Layer Validation - Research

**Researched:** 2026-03-12
**Domain:** Python retrieval layer — LlamaIndex (Neo4j CypherTemplateRetriever + Qdrant hybrid), direct SQLAlchemy PostgreSQL queries, pytest integration testing against live Docker services
**Confidence:** HIGH (core libraries verified via official docs and Context7; one MEDIUM-confidence item on LlamaIndex hybrid retriever behavior without full re-ingestion)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Freshness thresholds:**
- Source-specific thresholds matching each data source's natural update cadence (e.g., weekly data stale after ~10 days, monthly after ~45 days, quarterly after ~120 days — Claude determines exact values per source)
- Warning delivered in the return payload only — a `warnings` list in the result dict. Never raise exceptions for staleness, never block execution
- Freshness checked against `now()` — no caller-provided reference date (historical report generation is not a v2.0 requirement)
- Warnings state facts only: source name, staleness duration, and threshold. No suggested actions — keeps the retrieval layer generic

**Neo4j query patterns:**
- Hybrid retrieval: use pre-computed HAS_ANALOGUE edges as primary path, but also pass current FRED values so templates can enrich results with live comparison data
- Claude decides the number of Cypher templates based on Phase 6 success criteria and loaded graph structure
- Return typed dataclasses (Pydantic models or Python dataclasses) — downstream nodes get type safety and IDE autocomplete
- Include static LLM narrative from HAS_ANALOGUE edges in the return type — Phase 6 macro_regime node gets both quantitative data and pre-computed context in one retrieval call

**Qdrant hybrid tuning:**
- Collection-specific dense/sparse weights — macro_docs (FOMC/SBV policy documents) and earnings_docs (company financials) have different document characteristics warranting different weight tuning
- Fixed top-5 retrieval depth across all collections. Simple, predictable token budget for Gemini context window in Phase 6
- Language filtering on retrieval — retriever accepts a language param and filters on the 'lang' payload field. Only returns chunks in the requested language
- Claude decides the metadata filter pattern (whether retriever handles filtering internally or exposes filter params to callers)

**PostgreSQL query scope:**
- Five tables: stock_fundamentals, structure_markers, fred_indicators, gold_price, gold_etf_ohlcv (adds gold tables beyond ROADMAP RETR-03 minimum — valuation node needs gold context)
- Configurable time window with latest-only as default — queries accept an optional lookback period so valuation node can request last 4 quarters of fundamentals to show trend direction
- Claude decides async (psycopg3) vs sync SQLAlchemy based on LangGraph's execution model and the Phase 3 checkpoint setup

**Validation strategy:**
- Pytest assertions against live Docker services with Phase 4's seeded data — no mocks for retrieval quality validation
- Tests live in reasoning/tests/ (standard Python project layout within the reasoning-engine service)
- Freshness check validation uses reference date override — pass a fake 'now' to make real data appear stale, without modifying the database

**Module structure:**
- Shared freshness module: reasoning/app/retrieval/freshness.py with reusable check_freshness() logic imported by each retriever
- Shared types module: reasoning/app/retrieval/types.py with all return dataclasses (RegimeAnalogue, DocumentChunk, FundamentalsRow, etc.) — Phase 6 nodes import from one place
- Claude decides whether to scaffold the broader reasoning/ directory structure or create retrieval module only

**Error handling:**
- Claude decides retry strategy for transient failures (Neo4j down, Qdrant timeout) based on LangGraph checkpoint/retry semantics
- Raise a specific NoDataError exception when retrieval returns empty results — forces downstream reasoning nodes to acknowledge and handle missing data explicitly
- Structured logging at INFO level: every retrieval call logs query params, result count, elapsed time, and any warnings

**Embedding model:**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RETR-01 | LlamaIndex Neo4j retriever (CypherTemplateRetriever) validated against loaded regime graph data | Neo4jPropertyGraphStore + CypherTemplateRetriever pattern verified; structured_query for existing graphs confirmed; Pydantic param pattern documented |
| RETR-02 | LlamaIndex Qdrant retriever (hybrid dense+sparse) validated against document corpus | CRITICAL blocker discovered: existing collections use unnamed single vector; must add text-sparse config via update_collection + re-upsert BM25 vectors on all existing points |
| RETR-03 | PostgreSQL direct query patterns validated against fundamentals, structure_markers, and FRED indicator tables (+ gold tables per scope expansion) | SQLAlchemy Core patterns from sidecar fully reusable; sync psycopg2 correct choice for LangGraph nodes; 5-table scope confirmed |
| RETR-04 | Every retrieval function includes data_as_of freshness check and emits warnings when thresholds are exceeded | Shared freshness.py module pattern; reference date override for test validation; threshold values researched and recommended |
</phase_requirements>

---

## Summary

Phase 5 creates the `reasoning/app/retrieval/` module — the complete retrieval layer that Phase 6 LangGraph nodes will import. Three retrieval paths are validated independently: Neo4j graph traversal via LlamaIndex CypherTemplateRetriever, Qdrant hybrid dense+sparse search via QdrantVectorStore, and PostgreSQL direct queries via SQLAlchemy Core.

**Critical discovery (RETR-02 blocker):** The existing Qdrant collections (`macro_docs_v1`, `earnings_docs_v1`) were initialized by `init-qdrant.sh` with a single unnamed dense vector (`"vectors": {"size": 384, "distance": "Cosine"}`). LlamaIndex's hybrid QdrantVectorStore requires collections with named vectors `text-dense` (384-dim Cosine) and `text-sparse` (sparse, no fixed size). The collections must be migrated before hybrid retrieval is possible. The migration strategy is: (1) `update_collection()` to add the `text-sparse` sparse vector config, (2) rename/update the existing unnamed dense vector to `text-dense`, (3) generate and upsert BM25 sparse vectors for all existing points. Alternatively, recreate collections with correct config and re-run Phase 4 seed scripts.

**Neo4j path is clean:** `CypherTemplateRetriever` works directly against a `Neo4jPropertyGraphStore` pointing at the externally-created graph. No `PropertyGraphIndex.from_documents()` needed — the store's `structured_query()` method executes raw Cypher, and `CypherTemplateRetriever` uses a Pydantic model to have the LLM fill template parameters.

**PostgreSQL path reuses sidecar patterns:** `sidecar/app/models.py` contains all SQLAlchemy Core Table definitions. The reasoning-engine should copy or import these; sync psycopg2 + SQLAlchemy is the correct choice because LangGraph nodes run synchronously by default and the project's established pattern (from Phase 3 checkpoint setup) uses psycopg2 for the sidecar.

**Primary recommendation:** Resolve the Qdrant collection naming blocker first (Wave 0 task), then implement the three retrieval modules in parallel (Neo4j, Qdrant, PostgreSQL), then add the shared freshness module and pytest suite against live Docker services.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| llama-index-graph-stores-neo4j | latest (>=0.3) | Neo4jPropertyGraphStore + CypherTemplateRetriever | Only LlamaIndex integration that works against externally-created Neo4j graphs |
| llama-index-vector-stores-qdrant | latest (>=0.3) | QdrantVectorStore with hybrid=True | Official LlamaIndex Qdrant integration; handles query embedding via FastEmbed transparently |
| llama-index-embeddings-fastembed | latest | FastEmbed bge-small-en-v1.5 dense embedding at query time | Matches Phase 4 seed model exactly; 384-dim |
| fastembed | >=0.3.0 | BM25 sparse vector generation for Qdrant | Already in seed-requirements.txt; provides `Qdrant/bm25` sparse model |
| qdrant-client | >=1.14.0,<1.17.0 | Low-level Qdrant operations (update_collection, scroll, upsert) | Pinned in seed-requirements.txt; use same range |
| neo4j | >=5.0 | Direct Neo4j driver for validation queries | Already in seed-requirements.txt |
| sqlalchemy | >=2.0.0 | PostgreSQL queries via Core Table definitions | Established project pattern; matches sidecar |
| psycopg2-binary | >=2.9.9 | Sync PostgreSQL driver | Established project pattern; compatible with sync LangGraph nodes |
| pydantic | v2 (bundled with llama-index) | CypherTemplateRetriever parameter models | Required for CypherTemplateRetriever Params class |
| pytest | >=8.0.0 | Test framework | Already in sidecar/requirements.txt |
| pytest-asyncio | >=0.24.0 | Async test support | Already in sidecar/requirements.txt |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| llama-index-core | >=0.11 | CypherTemplateRetriever, VectorStoreIndex base classes | Required as llama-index-graph-stores-neo4j dependency |
| python-dotenv | >=1.0.0 | Load env vars in test fixtures | All retrievers read env vars for service URLs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CypherTemplateRetriever | TextToCypherRetriever | TextToCypher lets LLM generate arbitrary Cypher — riskier for production, not recommended for externally-seeded graphs per CONTEXT.md specifics section |
| sync SQLAlchemy (psycopg2) | async psycopg3 | psycopg3 async is faster but adds complexity; LangGraph nodes are sync by default and psycopg2 is already the established project driver |
| LlamaIndex QdrantVectorStore | Direct qdrant-client hybrid query | Direct client gives more control over fusion weights but loses transparent embedding handling; LlamaIndex is preferred |

**Installation (reasoning/requirements.txt additions):**
```bash
pip install llama-index-graph-stores-neo4j \
            llama-index-vector-stores-qdrant \
            llama-index-embeddings-fastembed \
            fastembed>=0.3.0 \
            qdrant-client>=1.14.0 \
            neo4j>=5.0 \
            sqlalchemy>=2.0.0 \
            psycopg2-binary>=2.9.9
```

---

## Architecture Patterns

### Recommended Project Structure
```
reasoning/
├── app/
│   ├── retrieval/
│   │   ├── __init__.py          # Public API: exports all retriever functions
│   │   ├── freshness.py         # check_freshness(data_as_of, threshold_days, source_name, now_override=None)
│   │   ├── types.py             # RegimeAnalogue, DocumentChunk, FundamentalsRow, StructureMarkerRow, FredIndicatorRow, GoldPriceRow, GoldEtfRow
│   │   ├── neo4j_retriever.py   # get_regime_analogues(query_text, limit=5) -> list[RegimeAnalogue]
│   │   ├── qdrant_retriever.py  # search_macro_docs(query, lang, top_k=5) -> list[DocumentChunk]
│   │   │                        # search_earnings_docs(query, ticker, lang, top_k=5) -> list[DocumentChunk]
│   │   └── postgres_retriever.py # get_fundamentals(symbol, lookback_quarters=1) -> list[FundamentalsRow]
│   │                              # get_structure_markers(symbol) -> list[StructureMarkerRow]
│   │                              # get_fred_indicators(series_ids, lookback_days=90) -> list[FredIndicatorRow]
│   │                              # get_gold_price(lookback_days=7) -> list[GoldPriceRow]
│   │                              # get_gold_etf(ticker, lookback_days=7) -> list[GoldEtfRow]
│   └── models/
│       └── tables.py            # Copy of sidecar/app/models.py — SQLAlchemy Core Table definitions
└── tests/
    ├── conftest.py              # Fixtures: neo4j_driver, qdrant_client, db_engine (all live Docker)
    ├── test_neo4j_retriever.py  # Tests for RETR-01
    ├── test_qdrant_retriever.py # Tests for RETR-02
    ├── test_postgres_retriever.py # Tests for RETR-03
    └── test_freshness.py        # Tests for RETR-04 (uses now_override parameter)
```

### Pattern 1: CypherTemplateRetriever Against Externally-Created Graph
**What:** Connect `Neo4jPropertyGraphStore` to the existing bolt://neo4j:7687 graph (not built by LlamaIndex). Use `CypherTemplateRetriever` with a Pydantic model for the LLM to fill template parameters.
**When to use:** All Neo4j retrieval in this phase.
**Example:**
```python
# Source: https://neo4j.com/blog/developer/property-graph-index-llamaindex/
# Source: https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import CypherTemplateRetriever
from llama_index.core.bridge.pydantic import BaseModel, Field

graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password=os.environ["NEO4J_PASSWORD"],
    url="bolt://neo4j:7687",
)

class RegimeParams(BaseModel):
    """Parameters for regime analogue lookup."""
    regime_keywords: list[str] = Field(
        description="Keywords describing the current macro regime (e.g., ['high inflation', 'rate hike', 'recession risk'])"
    )

REGIME_ANALOGUE_CYPHER = """
MATCH (r:Regime)-[rel:HAS_ANALOGUE]->(analogue:Regime)
WHERE any(kw IN $regime_keywords WHERE toLower(r.name) CONTAINS toLower(kw)
       OR toLower(r.notes) CONTAINS toLower(kw))
RETURN r.id AS source_regime,
       analogue.id AS analogue_id,
       analogue.name AS analogue_name,
       analogue.period_start AS period_start,
       analogue.period_end AS period_end,
       rel.similarity_score AS similarity_score,
       rel.dimensions_matched AS dimensions_matched,
       rel.narrative AS narrative
ORDER BY rel.similarity_score DESC
LIMIT 5
"""

retriever = CypherTemplateRetriever(
    graph_store,
    RegimeParams,
    REGIME_ANALOGUE_CYPHER,
    llm=llm,  # Gemini model
)

nodes = retriever.retrieve("high inflation environment with aggressive Fed tightening")
```

**Alternative — direct structured_query (no LLM, for deterministic tests):**
```python
# Use graph_store.structured_query() directly when parameters are already extracted
results = graph_store.structured_query(
    "MATCH (r:Regime)-[rel:HAS_ANALOGUE]->(a:Regime) RETURN r, rel, a LIMIT 5"
)
```

### Pattern 2: Qdrant Hybrid Search via QdrantVectorStore
**What:** LlamaIndex QdrantVectorStore with `enable_hybrid=True` and `fastembed_sparse_model="Qdrant/bm25"`. Collections MUST have named vectors `text-dense` (384-dim Cosine) and `text-sparse` (sparse, Dot).
**When to use:** All Qdrant document retrieval. NOTE: Requires collection migration first (see Wave 0 Gaps).
**Example:**
```python
# Source: https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(host="qdrant", port=6333, api_key=os.environ["QDRANT_API_KEY"], https=False)

vector_store = QdrantVectorStore(
    "macro_docs_v1",
    client=client,
    enable_hybrid=True,
    fastembed_sparse_model="Qdrant/bm25",
    batch_size=20,
)

# Attach to existing collection (no re-ingestion)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    embed_model=FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5"),
)

# Language-filtered hybrid query
retriever = index.as_retriever(
    similarity_top_k=5,
    sparse_top_k=10,  # 10 from each vector type, fused to top 5
    vector_store_query_mode="hybrid",
)

# Apply language filter using Qdrant filters
from llama_index.core.vector_stores.types import MetadataFilters, MetadataFilter, FilterOperator
nodes = retriever.retrieve(
    "Federal Reserve quantitative easing inflation",
    # Language filter passed through vector_store_kwargs
)
```

**Collection migration (Wave 0 required task):**
```python
# Source: https://qdrant.tech/documentation/concepts/collections/
# Step 1: Add sparse vector config to existing collection
client.update_collection(
    collection_name="macro_docs_v1",
    sparse_vectors_config={"text-sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)}
)

# Step 2: Rename existing unnamed dense vector to "text-dense"
# NOTE: Qdrant does NOT support renaming vectors on existing collections.
# The existing unnamed vector config is stored under "" (empty string key).
# LlamaIndex QdrantVectorStore looks for "text-dense" specifically.
# SOLUTION: Recreate collections with correct config + re-run Phase 4 seed scripts.
# This is the recommended approach over partial migration.
```

### Pattern 3: PostgreSQL Direct Query (SQLAlchemy Core, Sync)
**What:** Reuse SQLAlchemy Core Table definitions from sidecar. Sync psycopg2 engine. Accept optional lookback_days/lookback_quarters parameter; default to latest row.
**When to use:** All PostgreSQL retrieval (fundamentals, structure_markers, fred_indicators, gold_price, gold_etf_ohlcv).
**Example:**
```python
# Source: sidecar/app/models.py and sidecar/app/db.py (established project pattern)
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker
from reasoning.app.models.tables import stock_fundamentals  # copied from sidecar

engine = create_engine(
    os.environ.get("DATABASE_URL", "postgresql://stratum:changeme@postgres:5432/stratum"),
    pool_pre_ping=True,
    pool_size=3,
)

def get_fundamentals(symbol: str, lookback_quarters: int = 1) -> list[FundamentalsRow]:
    with SessionLocal() as session:
        stmt = (
            select(stock_fundamentals)
            .where(stock_fundamentals.c.symbol == symbol)
            .order_by(desc(stock_fundamentals.c.data_as_of))
            .limit(lookback_quarters)
        )
        rows = session.execute(stmt).fetchall()
    if not rows:
        raise NoDataError(f"No fundamentals found for symbol={symbol!r}")
    results = []
    for row in rows:
        warnings = check_freshness(row.data_as_of, threshold_days=120, source_name=f"stock_fundamentals:{symbol}")
        results.append(FundamentalsRow(**row._mapping, warnings=warnings))
    return results
```

### Pattern 4: Shared Freshness Check
**What:** Single `check_freshness()` function in `freshness.py` that accepts `data_as_of`, threshold in days, source name, and optional `now_override` for testing.
**When to use:** Called by every retrieval function after fetching rows. Returns a list of warning strings (empty list = fresh).
**Example:**
```python
# reasoning/app/retrieval/freshness.py
from datetime import datetime, timedelta, timezone
from typing import Optional

def check_freshness(
    data_as_of: datetime,
    threshold_days: int,
    source_name: str,
    now_override: Optional[datetime] = None,
) -> list[str]:
    """
    Returns list of warning strings. Empty list means data is fresh.
    Never raises — callers always get a result + warnings.
    """
    now = now_override or datetime.now(timezone.utc)
    if data_as_of.tzinfo is None:
        data_as_of = data_as_of.replace(tzinfo=timezone.utc)
    age_days = (now - data_as_of).days
    if age_days > threshold_days:
        return [
            f"STALE DATA: {source_name} data_as_of={data_as_of.date()} "
            f"is {age_days} days old (threshold: {threshold_days} days)"
        ]
    return []
```

**Freshness threshold recommendations (Claude's discretion — these are the recommended values):**
| Source | Table | Threshold Days | Cadence |
|--------|-------|---------------|---------|
| fred_indicators | fred_indicators | 10 | Weekly FRED updates |
| stock_fundamentals | stock_fundamentals | 120 | Quarterly reporting |
| structure_markers | structure_markers | 10 | Weekly computation |
| gold_price | gold_price | 10 | Weekly updates |
| gold_etf_ohlcv | gold_etf_ohlcv | 10 | Weekly updates |
| qdrant_macro_docs | Qdrant payload.document_date | 45 | Monthly policy docs |
| qdrant_earnings_docs | Qdrant payload.document_date | 120 | Quarterly earnings |
| neo4j_analogues | HAS_ANALOGUE edges (no data_as_of) | N/A — not freshness-checked, narrative is static |

### Anti-Patterns to Avoid
- **Using VectorContextRetriever or LLMSynonymRetriever against the Neo4j graph:** These rely on LlamaIndex-internal node properties (embedding vectors stored in Neo4j node properties) that were NOT set during Phase 4 seeding. Only CypherTemplateRetriever and TextToCypherRetriever work against externally-seeded graphs.
- **Raising exceptions on stale data:** Per locked decision, freshness warnings are informational. Raise only NoDataError (empty result), never StaleDataError.
- **Querying Qdrant collections without language filter:** bge-small-en-v1.5 produces degraded embeddings for Vietnamese text. Always filter `lang == "en"` unless explicitly handling mixed-language results.
- **Attempting to use unnamed vector in LlamaIndex hybrid mode:** The existing collections have an unnamed default vector. LlamaIndex requires `text-dense` as the named dense vector. This will silently fail or error without migration.
- **Copying async psycopg3 pattern from LangGraph PostgresSaver:** The checkpoint saver uses async psycopg3 for the `langgraph` schema. Retrieval queries use sync psycopg2 against the `public` schema. These are separate concerns with separate drivers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dense query embedding at retrieval time | Custom FastEmbed call wrapping QdrantClient | LlamaIndex QdrantVectorStore with FastEmbedEmbedding | QdrantVectorStore handles embed-query-fuse pipeline transparently |
| BM25 sparse query vector generation | Custom tokenizer + IDF computation | FastEmbed `Qdrant/bm25` via `fastembed_sparse_model` param | Matches the BM25 model used at index time; IDF state is stored in Qdrant collection |
| Cypher parameter extraction from natural language | Custom regex/NLP extractor | CypherTemplateRetriever + Pydantic model + LLM | LLM fills structured Pydantic params; template prevents hallucinated queries |
| Score fusion across dense/sparse results | Custom RRF or weighted sum | LlamaIndex QdrantVectorStore Relative Score Fusion (default) | Battle-tested; configurable via `alpha` parameter |
| Result deduplication across retrieval calls | Custom dedup logic | Deterministic uuid5 point IDs in Qdrant (from Phase 4 seed) | Point IDs are already deterministic; dedup by ID if needed |

**Key insight:** The retrieval layer's value is correct wiring of existing systems (LlamaIndex, Qdrant, Neo4j), not building new retrieval algorithms. All the hard problems (embedding, BM25, score fusion, Cypher parameterization) have off-the-shelf solutions in the locked stack.

---

## Common Pitfalls

### Pitfall 1: Qdrant Collection Named Vector Mismatch
**What goes wrong:** LlamaIndex QdrantVectorStore with `enable_hybrid=True` silently fails or throws a vector-not-found error because existing collections use unnamed single-vector config (`"vectors": {"size": 384}`) instead of named configs (`"text-dense"` + `"text-sparse"`).
**Why it happens:** `init-qdrant.sh` created collections with the simple unnamed vector format. LlamaIndex hybrid mode hardcodes `dense_vector_name="text-dense"` and `sparse_vector_name="text-sparse"`.
**How to avoid:** Wave 0 must recreate collections with the correct named vector config AND re-run Phase 4 seed scripts to populate both dense (`text-dense`) and sparse (`text-sparse`) vectors. Use `update_collection()` only for the sparse config addition — but the dense vector rename is not possible without recreation.
**Warning signs:** `KeyError: 'text-dense'` or `VectorNameNotFound` error on first hybrid query.

### Pitfall 2: CypherTemplateRetriever LLM Hallucinating Node Labels
**What goes wrong:** The LLM fills the Pydantic params with values that don't match actual node properties (e.g., `names: ["Recession 2008"]` when nodes use `id: "gfc_2008_2009"`), returning empty results.
**Why it happens:** The LLM doesn't know the actual node ID format used in the graph.
**How to avoid:** (1) Include graph schema hints in the Pydantic Field `description`. (2) Supplement CypherTemplateRetriever with a `graph_store.structured_query()` fallback that searches by FRED dimension ranges rather than by name. (3) Always validate retrieval with deterministic tests using `structured_query()` before testing with LLM-parameterized calls.
**Warning signs:** retriever.retrieve() returns zero nodes despite Phase 4 data being present.

### Pitfall 3: Stale BM25 IDF State After Re-seeding
**What goes wrong:** If macro_docs_v1 is deleted and recreated with sparse vector config, then re-seeded in batches, the IDF modifier in the sparse index recalculates on each batch. Early batches have inflated IDF weights; later batches have more accurate weights.
**Why it happens:** Qdrant BM25 IDF is computed incrementally as points are inserted. Small collections have unstable IDF.
**How to avoid:** Seed all documents in a single batch upload (or use the seed script's existing batch pattern), then run validation queries. Don't test hybrid retrieval quality until full corpus is loaded.
**Warning signs:** BM25 results heavily favor terms that only appear in early-uploaded documents.

### Pitfall 4: Async/Sync Driver Mismatch
**What goes wrong:** Using `psycopg3`/`asyncpg` in the retrieval module that will be called from sync LangGraph nodes causes `RuntimeError: This event loop is already running` or `SynchronousDatabaseDriver` errors.
**Why it happens:** LangGraph nodes are synchronous Python functions by default. Async database drivers require an event loop; calling them from sync code requires `asyncio.run()` which fails inside an existing event loop.
**How to avoid:** Use sync SQLAlchemy with psycopg2-binary for all retrieval in Phase 5. The async psycopg3 pattern used by LangGraph's PostgresSaver (for checkpointing in the `langgraph` schema) is a separate connection used only by the graph framework — retrieval modules are independent.
**Warning signs:** `RuntimeError: This event loop is already running` during Phase 6 integration.

### Pitfall 5: Freshness Check on Timezone-Naive Datetimes
**What goes wrong:** `datetime.now(timezone.utc) - data_as_of` raises `TypeError: can't subtract offset-naive and offset-aware datetimes` because PostgreSQL returns timezone-naive datetimes when the column doesn't store TZ info.
**Why it happens:** SQLAlchemy returns Python `datetime` objects. `DateTime(timezone=True)` columns in the schema *do* store TZ, but SQLAlchemy may still return naive datetimes depending on driver behavior.
**How to avoid:** Always normalize `data_as_of` in `check_freshness()` — if `.tzinfo is None`, attach UTC. Example already shown in Pattern 4 above.
**Warning signs:** `TypeError` in freshness check on first real data row.

### Pitfall 6: Neo4j Graph Store Requires PropertyGraphIndex Wrapper (Partially True)
**What goes wrong:** Documentation examples show `CypherTemplateRetriever(index.property_graph_store, ...)` (using an index). Attempting to call it without `PropertyGraphIndex` setup raises an AttributeError.
**Why it happens:** `CypherTemplateRetriever` accepts a `property_graph_store` directly — the `index.property_graph_store` is just one way to get it. You can pass `Neo4jPropertyGraphStore(...)` directly.
**How to avoid:** Instantiate `Neo4jPropertyGraphStore` directly and pass it as the first argument to `CypherTemplateRetriever`. No `PropertyGraphIndex.from_documents()` or `from_existing()` needed. Validate with `graph_store.structured_query("MATCH (n:Regime) RETURN count(n)")` before wiring CypherTemplateRetriever.
**Warning signs:** Confusion from documentation examples that always show the index — check the constructor signature directly.

---

## Code Examples

### Neo4j: Direct structured_query validation
```python
# Source: LlamaIndex official docs, neo4j.com/labs/genai-ecosystem/llamaindex/
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password=os.environ["NEO4J_PASSWORD"],
    url=os.environ.get("NEO4J_URI", "bolt://neo4j:7687"),
)

# Validate graph has HAS_ANALOGUE relationships with all required properties
results = graph_store.structured_query("""
    MATCH (src:Regime)-[rel:HAS_ANALOGUE]->(tgt:Regime)
    RETURN src.id AS source_id,
           tgt.id AS target_id,
           rel.similarity_score AS similarity_score,
           rel.dimensions_matched AS dimensions_matched,
           rel.period_start AS period_start,
           rel.period_end AS period_end,
           rel.narrative AS narrative
    LIMIT 5
""")
assert len(results) > 0, "No HAS_ANALOGUE relationships found"
for row in results:
    assert row["similarity_score"] is not None
    assert row["period_start"] is not None
```

### Qdrant: Collection migration — add sparse vector config + re-seed
```python
# Source: https://qdrant.tech/documentation/concepts/collections/
from qdrant_client import QdrantClient, models

client = QdrantClient(host="qdrant", port=6333, api_key=os.environ["QDRANT_API_KEY"], https=False)

# Step 1: Add sparse vector config to existing collection
# This adds text-sparse without destroying existing dense vectors
client.update_collection(
    collection_name="macro_docs_v1",
    sparse_vectors_config={
        "text-sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
    }
)

# NOTE: The existing unnamed dense vector cannot be renamed to "text-dense"
# via update_collection. Full recreation is required.
# Recommended: delete + recreate + re-run seed-qdrant-macro-docs.py
# with updated collection creation that uses named vectors.
```

### Qdrant: Hybrid search with language filter
```python
# Source: https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/
from qdrant_client.models import Filter, FieldCondition, MatchValue
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex

vector_store = QdrantVectorStore(
    "macro_docs_v1",
    client=client,
    enable_hybrid=True,
    fastembed_sparse_model="Qdrant/bm25",
    batch_size=20,
)
index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    embed_model=FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5"),
)
retriever = index.as_retriever(
    similarity_top_k=5,
    sparse_top_k=10,
    vector_store_query_mode="hybrid",
)

# Language filter (English only for bge-small-en-v1.5 quality)
from llama_index.core.vector_stores.types import MetadataFilters, MetadataFilter
nodes = retriever.retrieve(
    "Federal Reserve quantitative easing impact on inflation expectations",
    # Note: metadata_filters may need to be set on retriever init, not per-query
    # Claude's discretion: test both approaches and use whichever QdrantVectorStore supports
)
```

### PostgreSQL: Fundamentals with lookback + freshness check
```python
# Based on: sidecar/app/models.py and sidecar/app/db.py
from sqlalchemy import select, desc, create_engine
from sqlalchemy.orm import sessionmaker
from reasoning.app.models.tables import stock_fundamentals
from reasoning.app.retrieval.freshness import check_freshness
from reasoning.app.retrieval.types import FundamentalsRow, NoDataError

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3)
SessionLocal = sessionmaker(bind=engine)

def get_fundamentals(
    symbol: str,
    lookback_quarters: int = 1,
    now_override=None
) -> list[FundamentalsRow]:
    with SessionLocal() as session:
        stmt = (
            select(stock_fundamentals)
            .where(stock_fundamentals.c.symbol == symbol)
            .order_by(desc(stock_fundamentals.c.data_as_of))
            .limit(lookback_quarters)
        )
        rows = session.execute(stmt).fetchall()
    if not rows:
        raise NoDataError(f"No fundamentals for symbol={symbol!r}")
    results = []
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold_days=120,
            source_name=f"stock_fundamentals:{symbol}",
            now_override=now_override,
        )
        results.append(FundamentalsRow(**row._mapping, warnings=warnings))
    return results
```

### Pytest: Freshness check validation via now_override
```python
# Tests for RETR-04 — validate warning appears without modifying database
from datetime import datetime, timedelta, timezone

def test_freshness_warning_appears(db_session):
    """Confirms freshness warning emitted when data_as_of is deliberately stale."""
    # Use a real row but pass a future 'now' to make it appear stale
    future_now = datetime.now(timezone.utc) + timedelta(days=200)
    rows = get_fundamentals("VNM", lookback_quarters=1, now_override=future_now)
    assert len(rows) > 0
    assert len(rows[0].warnings) > 0
    assert "STALE DATA" in rows[0].warnings[0]
    assert "stock_fundamentals:VNM" in rows[0].warnings[0]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| KnowledgeGraphIndex (triple-store) | PropertyGraphIndex + Neo4jPropertyGraphStore | LlamaIndex v0.10+ | Property graph allows node labels, relationship types, and arbitrary properties — essential for HAS_ANALOGUE traversal |
| LlamaIndex VectorStoreIndex dense-only Qdrant | QdrantVectorStore with enable_hybrid=True + fastembed_sparse_model | LlamaIndex 0.10.x | Native hybrid support; no custom fusion code needed |
| Qdrant unnamed single vector config | Named vectors (text-dense, text-sparse) | Qdrant 1.8+ | Required for hybrid collections; breaks backward compat with unnamed vector collections when using LlamaIndex |
| psycopg2 only for all Python Postgres | psycopg3 for async (LangGraph checkpoint), psycopg2 for sync (retrieval) | 2023-2024 | LangGraph's PostgresSaver requires psycopg3; retrieval modules can stay on psycopg2 |
| BM42 (Qdrant's in-house sparse model) | Qdrant/bm25 via FastEmbed | 2024 | BM25 is more predictable for financial document keyword matching than BM42 |

**Deprecated/outdated:**
- `llama_index.core.retrievers.KnowledgeGraphRAGRetriever`: Replaced by PropertyGraphIndex retrievers. Do not use.
- `QdrantVectorStore(collection_name="...")` without named vectors for hybrid: Works for dense-only, breaks for hybrid. Phase 4 collections must be migrated.
- `google-generativeai` Python SDK: Deprecated — project already migrated to `google-genai>=1.0.0` (commit e01a362). Retrieval layer should use `google-genai` if Gemini is needed for CypherTemplateRetriever LLM calls.

---

## Open Questions

1. **Can LlamaIndex QdrantVectorStore read from a collection with both unnamed default vectors AND named text-sparse, or does the dense vector strictly require the name `text-dense`?**
   - What we know: Source code documentation says `dense_vector_name` defaults to `"text-dense"`. The collection was created with `"vectors": {"size": 384}` (unnamed default vector, not named).
   - What's unclear: Whether `dense_vector_name=""` (empty string for unnamed vector) is a valid workaround, or if recreation is mandatory.
   - Recommendation: Test `QdrantVectorStore(..., dense_vector_name="", sparse_vector_name="text-sparse")` first. If that fails, recreate collections — this is the safer path and re-running Phase 4 seed scripts is low-cost since they're idempotent.
   - Confidence: LOW on workaround viability — official docs emphasize named vectors for hybrid.

2. **How does LlamaIndex QdrantVectorStore pass per-query metadata filters (e.g., lang="en") in hybrid mode?**
   - What we know: `MetadataFilters` can be set at retriever initialization. `QdrantVectorStore` accepts `qdrant_filters` as a constructor parameter. Per-query filter via `retriever.retrieve()` kwargs may not be supported.
   - What's unclear: Whether the language filter should be set at retriever init (fixed per retriever instance) or per-query.
   - Recommendation: Create separate retriever instances per language (one for `lang="en"`, potentially one for `lang="vi"` in future). This maps naturally to the decision to have separate retrievers for macro_docs and earnings_docs with different alpha weights.
   - Confidence: MEDIUM — constructor-level filter approach is common pattern.

3. **Should the broader reasoning/ service directory be scaffolded in Phase 5 or only the retrieval module?**
   - What we know: Phase 8 creates the FastAPI reasoning-engine service. Phase 6 creates LangGraph nodes that import from retrieval/.
   - What's unclear: Whether Phase 5 should pre-scaffold the full service directory (app/, Dockerfile, requirements.txt) to avoid Phase 6 restructuring, or keep it minimal (just retrieval/).
   - Recommendation: Scaffold the full `reasoning/` service directory skeleton in Phase 5 (without FastAPI routes). This makes Phase 6 import paths stable and avoids reorganization. Cost: ~1 extra task.
   - Confidence: HIGH on recommendation — pre-scaffolding is low-risk and prevents tech debt.

---

## Validation Architecture

> `workflow.nyquist_validation` key not present in `.planning/config.json` (config has `research`, `plan_check`, `verifier` but no `nyquist_validation`). The CONTEXT.md locked decision specifies "Pytest assertions against live Docker services." Validation architecture section included as it is directly mandated by RETR-04 and the validation strategy decision.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | reasoning/pytest.ini (Wave 0 gap — does not exist yet) |
| Quick run command | `pytest reasoning/tests/test_freshness.py -x` |
| Full suite command | `pytest reasoning/tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETR-01 | CypherTemplateRetriever returns regime analogues with all 5 required properties (similarity_score, dimensions_matched, period_start, period_end, narrative) | integration (live Neo4j) | `pytest reasoning/tests/test_neo4j_retriever.py -x` | Wave 0 gap |
| RETR-02 | Hybrid Qdrant search returns more relevant results than dense-only for 3 representative queries | integration (live Qdrant) + manual inspection | `pytest reasoning/tests/test_qdrant_retriever.py -x` | Wave 0 gap |
| RETR-03 | Direct PostgreSQL query functions for all 5 tables return non-empty structured results for real asset identifiers | integration (live Postgres) | `pytest reasoning/tests/test_postgres_retriever.py -x` | Wave 0 gap |
| RETR-04 | Every retrieval function emits STALE DATA warning when now_override makes data appear stale | integration (live services, now_override param) | `pytest reasoning/tests/test_freshness.py -x` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** Quick test for the module being implemented (e.g., `pytest reasoning/tests/test_neo4j_retriever.py -x`)
- **Per wave merge:** `pytest reasoning/tests/ -v`
- **Phase gate:** Full suite green before phase close

### Wave 0 Gaps
- [ ] `reasoning/pytest.ini` — test discovery config (asyncio_mode=auto, testpaths=tests)
- [ ] `reasoning/tests/conftest.py` — shared fixtures: `neo4j_graph_store`, `qdrant_client`, `db_engine`, `db_session`
- [ ] `reasoning/tests/test_neo4j_retriever.py` — covers RETR-01
- [ ] `reasoning/tests/test_qdrant_retriever.py` — covers RETR-02
- [ ] `reasoning/tests/test_postgres_retriever.py` — covers RETR-03
- [ ] `reasoning/tests/test_freshness.py` — covers RETR-04
- [ ] Qdrant collection migration — add `text-sparse` to collections AND recreate with named `text-dense` (required before any Qdrant test can run)
- [ ] `reasoning/requirements.txt` — llama-index-graph-stores-neo4j, llama-index-vector-stores-qdrant, llama-index-embeddings-fastembed, psycopg2-binary, sqlalchemy

---

## Sources

### Primary (HIGH confidence)
- https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/ — CypherTemplateRetriever, Neo4jPropertyGraphStore, PropertyGraphIndex patterns
- https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/ — QdrantVectorStore hybrid setup, text-dense/text-sparse requirements, alpha parameter, fusion strategies
- https://qdrant.tech/documentation/concepts/collections/ — update_collection() for sparse vectors, named vector requirements, collection creation
- https://qdrant.tech/documentation/concepts/hybrid-queries/ — RRF fusion, Prefetch + FusionQuery patterns
- https://qdrant.tech/documentation/beginner-tutorials/hybrid-search-fastembed/ — FastEmbed BM25 + dense hybrid end-to-end example
- `sidecar/app/models.py` — SQLAlchemy Core Table definitions for all 8 tables (project ground truth)
- `sidecar/app/db.py` — Established sync psycopg2 + SQLAlchemy connection pattern
- `scripts/init-qdrant.sh` — Confirmed collections use unnamed single-vector config (source of RETR-02 migration requirement)
- `scripts/seed-neo4j-analogues.py` — Confirmed HAS_ANALOGUE schema: similarity_score, dimensions_matched, period_start, period_end, narrative

### Secondary (MEDIUM confidence)
- https://neo4j.com/blog/developer/property-graph-index-llamaindex/ — CypherTemplateRetriever with Pydantic BaseModel Params pattern (April 2025, verified against official LlamaIndex docs)
- https://developers.llamaindex.ai/python/framework/integrations/vector_stores/qdrant_hybrid_rag_multitenant_sharding/ — Advanced hybrid with per-tenant filters (multi-tenancy pattern confirms filter approach)
- LangGraph PostgresSaver uses psycopg3 async (verified via langgraph GitHub issues) — confirms sync psycopg2 is the correct choice for retrieval modules

### Tertiary (LOW confidence)
- LlamaIndex QdrantVectorStore accepts `dense_vector_name=""` for unnamed default vector — NOT verified; needs empirical testing (open question #1)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified via official docs and existing project usage
- Architecture: HIGH — module structure follows established sidecar patterns + LlamaIndex conventions
- Pitfalls: HIGH — Qdrant named vector mismatch is verified by reading init-qdrant.sh + LlamaIndex source docs; others verified via official docs
- Qdrant hybrid collection workaround: LOW — needs empirical test

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (LlamaIndex and Qdrant move fast; re-verify hybrid API if >30 days)
