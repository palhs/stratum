# Phase 4: Knowledge Graph and Document Corpus Population - Research

**Researched:** 2026-03-09
**Domain:** Neo4j Cypher seeding, Qdrant vector collection population, FastEmbed, document chunking, multilingual embedding, FRED data modeling
**Confidence:** HIGH (Neo4j/Qdrant APIs verified via Context7), MEDIUM (document sourcing verified via WebSearch), LOW (VN-specific data sourcing — no canonical single source)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Regime period definitions:**
- Hybrid approach: hand-defined era names and date boundaries, populated with FRED series values for each period
- Detailed granularity: ~15-20 regime nodes, breaking major eras into sub-phases (e.g., GFC split into 'credit crisis' + 'QE1 response', rate hike cycle into 'initial hikes' + 'terminal rate plateau')
- FRED dimensions: match exactly what's already in the fred_indicators table from v1.0 ingestion — no gaps between stored data and regime references
- Include VN-specific macro properties alongside US FRED data: SBV reference rate, VN CPI, VND/USD on each regime node (requires manual data curation since VN macro isn't in FRED)

**Document corpus sourcing:**
- Fed FOMC: key turning points only (~10-15 docs) — major policy shifts: rate cuts during GFC, QE announcements, taper tantrum, rate hike starts/pauses, COVID response, 2022-2023 tightening
- SBV: rate decisions + monetary policy reports (~20-30 docs) — SBV refinancing/discount rate changes with policy statements, plus quarterly/annual monetary policy reports
- VN30 earnings: latest 4 quarters per company (~120 docs) — all 30 VN30 companies, most recent year of earnings transcripts
- Language note: SBV and VN earnings docs may be in Vietnamese — embedding model handles this or documents need translation consideration

**Analogue similarity design:**
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

### Deferred Ideas (OUT OF SCOPE)

- Vietnamese financial term dictionary — Phase 6 prerequisite, content asset not code. Noted in STATE.md pending todos but out of Phase 4 scope.
- Automated document ingestion pipelines — explicitly deferred to v3.0 (INGEST-01 in REQUIREMENTS.md future section)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Neo4j seeded with historical macro regime nodes covering major economic periods (2008-2025) with FRED series values | Cypher UNWIND+MERGE pattern for bulk node creation; FRED series (GDP, CPIAUCSL, UNRATE, FEDFUNDS) already in fred_indicators table |
| DATA-02 | Neo4j regime nodes connected via HAS_ANALOGUE relationships carrying similarity_score, dimensions_matched, period_start, period_end | Existing RESEMBLES trigger as pattern; new APOC trigger or app-layer validation; cosine similarity via numpy/scipy on FRED vectors |
| DATA-03 | Qdrant macro_docs collection populated with curated Fed FOMC minutes and SBV reports | Fed minutes freely available as PDFs from federalreserve.gov; SBV reports from sbv.gov.vn; chunking strategy defined below |
| DATA-04 | Qdrant earnings_docs collection populated with curated VN30 company earnings transcripts | HOSE disclosure portal (hsx.vn); annual reports + quarterly financial statements; no formal earnings call transcripts in VN market |
</phase_requirements>

---

## Summary

Phase 4 is a pure data population phase with no runtime API logic. It has three distinct technical tracks: (1) Neo4j graph seeding — defining ~15-20 historical macro regime nodes with FRED dimensions and VN macro properties, computing pairwise cosine similarity, and creating HAS_ANALOGUE relationships with static Gemini-generated narratives; (2) Qdrant macro_docs population — downloading ~30-45 curated FOMC and SBV documents, chunking them, and embedding with FastEmbed; (3) Qdrant earnings_docs population — collecting VN30 quarterly financial reports, chunking, and embedding.

The most important planning decision surfaced by research: **BAAI/bge-small-en-v1.5 (384-dim, locked in v1.0) is an English-only model**. Vietnamese text in SBV reports and VN earnings documents will produce degraded embeddings. The CONTEXT.md acknowledges "embedding model handles this or documents need translation consideration" — this must be resolved before Plan 03/04 are written. The recommended path is English-language documents where possible (FOMC always in English, SBV has English portal, earnings summaries translated) with clear flagging of quality limitations for Vietnamese-only content.

The runner mechanism for seed scripts is the critical integration question. The project has an established one-shot Docker init service pattern (flyway, neo4j-init, qdrant-init). Phase 4 must either add new seed init services or extend existing ones. The Neo4j Cypher seed and Qdrant Python embedding scripts both need a container runner that can access the respective services on the ingestion network.

**Primary recommendation:** Implement Neo4j regime seeding as a new Cypher file executed by neo4j-init service; implement Qdrant population as a new Python seed script in a new one-shot Docker service that uses fastembed+qdrant-client, running after qdrant-init completes.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| neo4j (Python driver) | 5.x | Execute Cypher seed scripts from Python | Official driver; project already targets Neo4j 5.26.21 |
| qdrant-client | latest (1.x) | Create collections, upsert points | Project already uses qdrant:v1.15.3; official Python client |
| fastembed | latest | Generate 384-dim embeddings (BAAI/bge-small-en-v1.5) | Project locked to FastEmbed for all Qdrant collections |
| numpy | latest | Cosine similarity computation for regime analogue scoring | Standard; already in ecosystem via pandas/fastembed |
| scipy | latest | scipy.spatial.distance.cdist for pairwise similarity matrix | More efficient than manual numpy for O(n²) regime pairs |
| pypdf2 / pdfplumber | latest | PDF text extraction for FOMC minutes and financial reports | FOMC minutes and SBV reports are PDFs |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-generativeai | latest | Gemini API for static analogue narrative generation | Generating per-pair narrative summary stored on HAS_ANALOGUE edge |
| langchain-text-splitters | latest | RecursiveCharacterTextSplitter for document chunking | Chunking FOMC/SBV/earnings docs before embedding |
| sqlalchemy | 2.x | Read fred_indicators from PostgreSQL for regime FRED values | Already in sidecar — reuse for seed script DB access |
| psycopg2-binary | 2.9.x | PostgreSQL connection | Already in sidecar requirements |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy cosine distance | sklearn.metrics.pairwise.cosine_similarity | scipy slightly faster for pairwise; sklearn cleaner API — either works |
| pypdf2 | pdfplumber | pdfplumber handles complex layouts better (tables, multi-column); pypdf2 lighter weight for plain-text PDFs |
| fastembed (English only) | BAAI/bge-m3 (1024-dim, multilingual) | bge-m3 is correct for Vietnamese but breaks 384-dim collection schema locked in v1.0; must translate VN docs to English or accept quality limitation |
| Cypher file via neo4j-init | Python neo4j driver in seed service | Cypher file is simpler for pure seeding; Python driver needed if similarity computation logic precedes Cypher execution |

**Installation (seed service requirements.txt additions):**
```bash
pip install fastembed qdrant-client neo4j scipy pdfplumber langchain-text-splitters google-generativeai
```

---

## Architecture Patterns

### Recommended Project Structure

```
neo4j/
└── seed/
    ├── 03_regime_nodes.cypher      # Regime node MERGE statements (DATA-01)
    └── 04_analogue_relationships.cypher  # HAS_ANALOGUE MERGE statements (DATA-02)

scripts/
├── seed-neo4j-analogues.py        # Computes similarity, calls Gemini, writes 04_*.cypher or executes directly
├── seed-qdrant-macro-docs.py      # Embeds FOMC + SBV docs → macro_docs_v1 collection (DATA-03)
└── seed-qdrant-earnings-docs.py   # Embeds VN30 earnings docs → earnings_docs_v1 collection (DATA-04)

data/
├── fomc/                          # Downloaded FOMC PDF minutes
├── sbv/                           # Downloaded SBV policy statements
└── earnings/                      # VN30 quarterly reports (PDFs or extracted text)
```

### Pattern 1: Neo4j Regime Node Seeding via UNWIND+MERGE

**What:** Pass a list of regime maps as a parameter and bulk-MERGE nodes idempotently.
**When to use:** Static seed data where all regime definitions are known at script time.

```python
# Source: Context7 /neo4j/neo4j-python-driver
from neo4j import GraphDatabase

REGIME_BATCH = [
    {
        "id": "gfc_credit_crisis_2007_2009",
        "name": "GFC — Credit Crisis",
        "period_start": "2007-08-01",
        "period_end": "2009-03-01",
        "gdp_avg": -2.1,
        "cpi_avg": 2.8,
        "unrate_avg": 7.2,
        "fedfunds_avg": 1.5,
        "sbv_rate_avg": 8.5,
        "vn_cpi_avg": 22.0,
        "vnd_usd_avg": 16800.0,
        "regime_type": "contraction",
        "notes": "GFC credit freeze, Bear Stearns/Lehman collapse, TARP"
    },
    # ... ~14-19 more regimes
]

def seed_regime_nodes(tx, batch):
    tx.run("""
        UNWIND $batch AS row
        MERGE (r:Regime {id: row.id})
        ON CREATE SET r += row
        ON MATCH  SET r += row
        RETURN count(r) AS seeded
    """, batch=batch)

driver = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", password))
with driver.session(database="neo4j") as session:
    session.execute_write(seed_regime_nodes, REGIME_BATCH)
```

### Pattern 2: HAS_ANALOGUE Relationship Seeding

**What:** Compute pairwise cosine similarity on FRED dimension vectors, call Gemini for narrative, MERGE relationships.
**When to use:** After all regime nodes are present; requires Python computation layer before Cypher execution.

```python
# Source: Context7 /neo4j/neo4j-python-driver + scipy docs
import numpy as np
from scipy.spatial.distance import cdist

# Build FRED feature vectors from regime data
# Dimensions: [gdp_avg, cpi_avg, unrate_avg, fedfunds_avg]
regime_ids = [r["id"] for r in REGIME_BATCH]
vectors = np.array([
    [r["gdp_avg"], r["cpi_avg"], r["unrate_avg"], r["fedfunds_avg"]]
    for r in REGIME_BATCH
])

# Normalize each dimension to [0,1] range before cosine similarity
# (prevents fedfunds dominating due to scale differences)
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
vectors_norm = scaler.fit_transform(vectors)

# Pairwise cosine similarity matrix
sim_matrix = 1 - cdist(vectors_norm, vectors_norm, metric='cosine')

# Build relationship batch: top-3 analogues per regime (excluding self)
SIMILARITY_THRESHOLD = 0.80  # Claude's discretion — start here
analogue_batch = []
for i, src_id in enumerate(regime_ids):
    scores = [(j, sim_matrix[i][j]) for j in range(len(regime_ids)) if i != j]
    scores.sort(key=lambda x: x[1], reverse=True)
    top_n = [s for s in scores[:5] if s[1] >= SIMILARITY_THRESHOLD]
    for j, score in top_n:
        analogue_batch.append({
            "from_id": src_id,
            "to_id": regime_ids[j],
            "similarity_score": float(score),
            "dimensions_matched": ["gdp", "cpi", "unrate", "fedfunds"],
            "period_start": REGIME_BATCH[i]["period_start"],
            "period_end": REGIME_BATCH[i]["period_end"],
            "narrative": ""  # filled by Gemini call below
        })

# Gemini narrative (static pre-computation)
# Generate narrative for each pair before Cypher write

def seed_analogues(tx, batch):
    tx.run("""
        UNWIND $batch AS row
        MATCH (src:Regime {id: row.from_id})
        MATCH (tgt:Regime {id: row.to_id})
        MERGE (src)-[rel:HAS_ANALOGUE]->(tgt)
        ON CREATE SET rel.similarity_score   = row.similarity_score,
                      rel.dimensions_matched = row.dimensions_matched,
                      rel.period_start       = row.period_start,
                      rel.period_end         = row.period_end,
                      rel.narrative          = row.narrative
        ON MATCH  SET rel.similarity_score   = row.similarity_score,
                      rel.dimensions_matched = row.dimensions_matched,
                      rel.period_start       = row.period_start,
                      rel.period_end         = row.period_end,
                      rel.narrative          = row.narrative
    """, batch=batch)
```

### Pattern 3: Qdrant Collection Creation + Embedding Upsert

**What:** Create versioned collections with aliases, chunk documents, embed with FastEmbed, upsert PointStructs.
**When to use:** Populating macro_docs and earnings_docs collections.

```python
# Source: Context7 /qdrant/qdrant-client + /qdrant/fastembed
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from fastembed import TextEmbedding
import uuid

client = QdrantClient(host="qdrant", port=6333, api_key=QDRANT_API_KEY)

# Create versioned collection + alias (mirrors existing init-qdrant.sh pattern)
client.create_collection(
    collection_name="macro_docs_v1",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
client.update_collection_aliases(change_aliases_operations=[
    {"create_alias": {"collection_name": "macro_docs_v1", "alias_name": "macro_docs"}}
])

# Embed and upsert chunks
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

def upsert_doc_chunks(client, collection_name, chunks, metadata_list):
    """chunks: list[str], metadata_list: list[dict] same length"""
    embeddings = list(embedding_model.embed(chunks, batch_size=64))
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={**metadata, "text": chunk}
        )
        for chunk, embedding, metadata in zip(chunks, embeddings, metadata_list)
    ]
    client.upload_points(
        collection_name=collection_name,
        points=points,
        batch_size=64,
        wait=True,
    )
```

### Pattern 4: Document Chunking for Financial PDFs

**What:** Recursive character splitting at 512 tokens with 10-15% overlap (~50-75 tokens).
**When to use:** All three document types (FOMC, SBV, earnings).

```python
# Source: WebSearch (arxiv 2402.05131, NVIDIA benchmark, Weaviate guide)
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pdfplumber

def extract_and_chunk_pdf(pdf_path: str, chunk_size: int = 512, chunk_overlap: int = 64) -> list[str]:
    """
    Extract text from PDF and split into overlapping chunks.
    chunk_size=512 tokens (~2048 chars); overlap=64 tokens (~12% — within 10-20% best-practice range).
    For FOMC minutes: section-level split is preferable if document has clear headings.
    """
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2048,      # ~512 tokens for bge-small (4 chars/token approx)
        chunk_overlap=256,    # ~12% overlap — preserves cross-boundary context
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    return splitter.split_text(full_text)
```

### Anti-Patterns to Avoid

- **Do not MERGE nodes inside a loop without UNWIND**: Creates individual transactions per node; extremely slow for 15-20 nodes (not critical at this scale but sets a bad precedent). Use UNWIND $batch.
- **Do not use `SET r = row` on relationships**: This replaces ALL properties. Use `SET r += row` (merge operator) to preserve any existing properties while updating.
- **Do not skip normalization before cosine similarity**: FRED series have wildly different scales (FEDFUNDS: 0-20%, UNRATE: 3-15%, GDP: -10% to +5%). Without scaling, high-magnitude dimensions dominate the similarity score. Use MinMaxScaler or StandardScaler before computing cosine similarity.
- **Do not create HAS_ANALOGUE as fully connected graph**: N×(N-1) = ~300 relationships for 15-20 nodes is manageable, but the query patterns in Phase 5 (CypherTemplateRetriever) work best with sparse graphs. Top-3-to-5 analogues per node, threshold-filtered.
- **Do not embed Vietnamese text with bge-small-en-v1.5**: This model is English-only. Vietnamese content produces degraded embeddings. Translate or use English-language versions of SBV/earnings documents.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cosine similarity matrix | Manual nested loops | scipy.cdist or sklearn.cosine_similarity | scipy/sklearn use optimized BLAS; hand-rolled is 10-100x slower and prone to normalization bugs |
| PDF text extraction | Custom PDF parser | pdfplumber | Handles multi-column layouts, tables, headers; FOMC minutes have complex formatting |
| Document chunking | Character index splitting | langchain RecursiveCharacterTextSplitter | Respects semantic boundaries (paragraphs, sentences) before falling back to character splitting |
| Embedding generation | Calling HuggingFace API | fastembed (local ONNX) | Project locked to fastembed; avoids API costs, runs offline, same model as collection was initialized for |
| Qdrant batch upload | Single-point upsert loop | client.upload_points() with batch_size | Automatic batching, retry logic, parallel upload built in |

**Key insight:** The similarity computation and Gemini narrative generation are the only truly custom logic in this phase. Everything else is plumbing that well-established libraries handle correctly.

---

## Common Pitfalls

### Pitfall 1: FRED Data Availability vs. Regime Period Coverage

**What goes wrong:** Some FRED series have gaps or infrequent updates. GDP is quarterly; if a regime period is defined as < 1 quarter, there may be no GDP observation in that window. The `fred_indicators` table stores one row per (series_id, data_as_of) — regime period averages must aggregate multiple rows.
**Why it happens:** FRED series have native frequencies (quarterly for GDP, monthly for CPI/UNRATE/FEDFUNDS). Period boundaries don't align with observation dates.
**How to avoid:** When computing FRED dimension averages for a regime period, query `fred_indicators WHERE series_id = X AND data_as_of BETWEEN period_start AND period_end`. If the window returns 0 rows for GDP, expand window to nearest quarterly boundary. Document missing coverage explicitly in regime node `notes` property.
**Warning signs:** Regime node has NULL for gdp_avg but non-NULL for other dimensions — always check for partial FRED coverage.

### Pitfall 2: Embedding Model Language Mismatch

**What goes wrong:** SBV documents in Vietnamese and VN earnings reports in Vietnamese produce low-quality embeddings from BAAI/bge-small-en-v1.5 (English-only model). Similarity searches in Phase 5 return poor results for Vietnamese-language queries.
**Why it happens:** bge-small-en-v1.5 was trained on English text only. Its name includes `-en-`. It was locked at v1.0 for all Qdrant collections (384-dim, Cosine). Switching to bge-m3 (multilingual, 1024-dim) would require recreating all collections.
**How to avoid:** Prioritize English-language document sources. SBV maintains an English portal at sbv.gov.vn/en. For VN earnings — annual reports for large VN30 companies (VIC, VHM, VCB, BID, HPG, etc.) are often published with English summaries or translated by brokers. For purely Vietnamese content, pre-translate key sections to English before embedding.
**Warning signs:** Similarity searches for Vietnamese company names return scores < 0.5 across the board.

### Pitfall 3: HAS_ANALOGUE APOC Trigger Not Installed for New Relationship Type

**What goes wrong:** The existing APOC trigger in `02_apoc_triggers.cypher` enforces properties only on `RESEMBLES` relationships. HAS_ANALOGUE relationships can be created without required properties — no validation at write time.
**Why it happens:** RESEMBLES and HAS_ANALOGUE are different relationship types. The existing trigger does not cover HAS_ANALOGUE.
**How to avoid:** Either (a) add a new APOC trigger for HAS_ANALOGUE in a `05_has_analogue_trigger.cypher` file run by neo4j-init, or (b) enforce required properties at the Python seed script layer with explicit validation before Cypher execution. Option (b) is simpler for Phase 4 since seeding is done once from a controlled script. Document the decision.
**Warning signs:** `MATCH ()-[r:HAS_ANALOGUE]->() WHERE r.similarity_score IS NULL RETURN count(r)` returns non-zero.

### Pitfall 4: Qdrant Collection Already Exists

**What goes wrong:** If the seed script is re-run, `client.create_collection()` raises an exception because macro_docs_v1 already exists.
**Why it happens:** Qdrant create_collection is not idempotent by default.
**How to avoid:** Check for collection existence before creation (as in the existing `init-qdrant.sh` pattern using HTTP status code check). Use:
```python
existing = [c.name for c in client.get_collections().collections]
if "macro_docs_v1" not in existing:
    client.create_collection(...)
```
**Warning signs:** Seed script fails on second run with "collection already exists" error.

### Pitfall 5: VN30 Earnings "Transcripts" Don't Exist in Vietnam

**What goes wrong:** Planning assumes earnings call transcripts similar to US companies (10-K, S&P 500 call transcripts on Seeking Alpha, etc.). Vietnamese listed companies do not hold earnings calls — this is not a standard practice on HOSE.
**Why it happens:** Western RAG pipelines commonly use earnings transcripts. VN market operates differently.
**How to avoid:** Source the following VN-equivalent documents instead — (1) annual reports (báo cáo thường niên) from HOSE disclosure portal (hsx.vn), (2) quarterly financial statements (báo cáo tài chính quý), (3) AGM materials if available. These are the closest equivalents to earnings transcripts in the VN market. Language will primarily be Vietnamese — apply translation strategy from Pitfall 2.
**Warning signs:** "Earnings transcripts" folder is empty because team searched for non-existent document type.

### Pitfall 6: Gemini API Calls for Static Narrative Generation Hit Rate Limits

**What goes wrong:** Generating analogue narratives for ~20-50 regime pairs sequentially via Gemini API produces rate limit errors or is slow.
**Why it happens:** Gemini API has requests-per-minute limits. Phase 4 is a one-time batch operation but the calls can pile up.
**How to avoid:** Add a small delay between Gemini calls (e.g., `time.sleep(1)`), implement retry with exponential backoff, or generate narratives in parallel batches respecting RPM limits. Cache all generated narratives to a local JSON file so the seed script can skip API calls on re-run.
**Warning signs:** Seed script fails partway through narrative generation with 429 errors.

---

## Code Examples

Verified patterns from official sources:

### Bulk MERGE with UNWIND (Neo4j — idempotent seed)
```python
# Source: Context7 /neo4j/neo4j-python-driver
def seed_regimes(tx, batch):
    tx.run("""
        UNWIND $batch AS row
        MERGE (r:Regime {id: row.id})
        ON CREATE SET r += row
        ON MATCH  SET r += row
    """, batch=batch)

with driver.session(database="neo4j") as session:
    session.execute_write(seed_regimes, REGIME_BATCH)
```

### Query fred_indicators for Regime Period Average
```python
# Source: existing sidecar/app/db.py SQLAlchemy pattern
from sqlalchemy import text

def get_fred_avg_for_period(session, series_id: str, period_start: str, period_end: str) -> float | None:
    result = session.execute(text("""
        SELECT AVG(value) as avg_val
        FROM fred_indicators
        WHERE series_id = :series_id
          AND data_as_of >= :start
          AND data_as_of <= :end
    """), {"series_id": series_id, "start": period_start, "end": period_end})
    row = result.fetchone()
    return float(row.avg_val) if row and row.avg_val is not None else None
```

### Qdrant Collection + Alias Creation (idempotent)
```python
# Source: Context7 /qdrant/qdrant-client
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="qdrant", port=6333, api_key=QDRANT_API_KEY)

existing = {c.name for c in client.get_collections().collections}
if "macro_docs_v1" not in existing:
    client.create_collection(
        collection_name="macro_docs_v1",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    client.update_collection_aliases(change_aliases_operations=[
        {"create_alias": {"collection_name": "macro_docs_v1", "alias_name": "macro_docs"}}
    ])
```

### FastEmbed Batch Embedding
```python
# Source: Context7 /qdrant/fastembed
from fastembed import TextEmbedding

model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

chunks = ["Federal Reserve raises rates by 75bps...", "SBV adjusts refinancing rate..."]
embeddings = list(model.embed(chunks, batch_size=64))
# Returns list of numpy arrays, each shape (384,)
```

### Pairwise Cosine Similarity Matrix (normalized)
```python
# Source: WebSearch (scikit-learn docs, scipy docs)
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.preprocessing import MinMaxScaler

feature_matrix = np.array([
    [gdp_avg, cpi_avg, unrate_avg, fedfunds_avg]
    for regime in regimes
])

scaler = MinMaxScaler()
normalized = scaler.fit_transform(feature_matrix)
sim_matrix = 1 - cdist(normalized, normalized, metric='cosine')
# sim_matrix[i][j] = cosine similarity between regime i and regime j
# Diagonal = 1.0 (self-similarity), values range 0..1
```

### FOMC Minutes Suggested URL Pattern
```
# Source: federalreserve.gov (verified via WebSearch)
# Pattern: https://www.federalreserve.gov/monetarypolicy/files/fomcminutes{YYYYMMDD}.pdf
# Example: https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20081029.pdf
# Historical: federalreserve.gov/monetarypolicy/fomc_historical.htm (2008-2014)
# Recent: federalreserve.gov/monetarypolicy/fomccalendars.htm (2015+)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| apoc.trigger.add() | apoc.trigger.install() | Neo4j 5.x / APOC 5.x | Existing project already uses install() correctly |
| Single collection | Versioned collection + stable alias | v1.0 established | Alias pattern in init-qdrant.sh already established — extend for macro_docs, earnings_docs |
| Full-document embedding | Chunked embedding with overlap | Industry standard by 2023 | Required for FOMC minutes (10-30 pages) — full doc exceeds model context |
| English-only models (bge-small-en) | Multilingual models (bge-m3, multilingual-e5-large) | 2024 | Project is locked to bge-small-en-v1.5 at 384-dim; multilingual upgrade would require collection recreation — out of scope for Phase 4 |

**Deprecated/outdated:**
- `apoc.trigger.add`: Replaced by `apoc.trigger.install` in APOC 5.x — project already uses correct version
- Fully-connected analogue graphs: Superseded by threshold-filtered sparse graphs for better retrieval performance

---

## Open Questions

1. **VN Macro Data Sourcing for Regime Nodes**
   - What we know: SBV reference rate, VN CPI, VND/USD are required on regime nodes per CONTEXT.md locked decisions. These are NOT in FRED. SBV portal (sbv.gov.vn/en) has policy announcements but no machine-readable historical time series back to 2008.
   - What's unclear: Is there a reliable free API or downloadable dataset for SBV reference rate history 2008-2025? Alternative: World Bank API has Vietnam CPI and USD/VND. IMF eLibrary has Vietnam data. vnstock may have VND/USD exchange rate history.
   - Recommendation: For Plan 01 (regime node schema), define VN macro properties as nullable with explicit fallback logic. Source from World Bank API (free, reliable), vnstock exchange rate data, or manual CSV curation. Document exact sources per value.

2. **VN30 Earnings Document Language and Translation Strategy**
   - What we know: VN30 companies publish annual reports and quarterly statements on HOSE (hsx.vn). Many are in Vietnamese only. US-style earnings call transcripts do not exist in Vietnam.
   - What's unclear: What percentage of VN30 annual reports have English versions? Large caps (VIC, VCB, BID, HPG, MWG) likely have English reports for international investor relations. Mid-cap VN30 members may not.
   - Recommendation: Plan 04 (earnings_docs) should scope to English-available annual reports first, supplement with machine-translated quarterly summaries for Vietnamese-only companies. Mark translated content with payload metadata flag `{"lang": "vi-translated"}`.

3. **Similarity Threshold for HAS_ANALOGUE**
   - What we know: CONTEXT.md specifies "top 3-5 analogues per regime." Threshold is Claude's discretion.
   - What's unclear: What cosine similarity score constitutes a meaningful macro analogue? With only 4 FRED dimensions (GDP, CPI, UNRATE, FEDFUNDS), the feature space is low-dimensional — scores will cluster higher than expected.
   - Recommendation: Start at 0.80 as initial threshold. After computing the full similarity matrix, examine the distribution. If >10 analogues per regime exceed 0.80, raise to 0.85. If <2 analogues exceed 0.80, lower to 0.75. Add Gemini narrative scoring as a second gate (Phase 4 CONTEXT.md: "both-layer approach") — only keep pairs where Gemini confirms meaningful historical parallel.

4. **APOC Trigger for HAS_ANALOGUE: Add or Skip?**
   - What we know: Existing APOC trigger covers RESEMBLES only. CONTEXT.md says "Claude's discretion" on whether to update trigger or handle validation in app layer.
   - What's unclear: Is runtime enforcement via APOC trigger worth the complexity for a one-shot seed operation?
   - Recommendation: Handle validation in the Python seed script (assert all required properties are present before writing). Add a comment in `02_apoc_triggers.cypher` noting that HAS_ANALOGUE validation is application-layer enforced. Do NOT add a second APOC trigger — operational complexity outweighs benefit for seeded-only data.

5. **One-shot Docker Service vs. Manual Script for Seed Operations**
   - What we know: Project has established one-shot init pattern (flyway, neo4j-init, qdrant-init). These run at `docker compose up`. Phase 4 seed scripts are heavier (Gemini API calls, PDF parsing) — not appropriate for every compose up.
   - What's unclear: Should seed scripts be one-shot Docker services (runs on compose up) or manually-triggered scripts?
   - Recommendation: Seed scripts should be manually triggered (not auto-run on compose up). Add a Makefile target `make seed-graph` and `make seed-docs`. Scripts should be idempotent (MERGE for Neo4j, collection existence check for Qdrant). Document in README that seeding is a one-time manual operation after Phase 3 infra is running.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/neo4j/neo4j-python-driver` — session.execute_write, UNWIND+MERGE, relationship property patterns
- Context7 `/websites/neo4j_cypher-manual_25` — MERGE with map parameters, UNWIND list parameter examples
- Context7 `/qdrant/qdrant-client` — upsert points, upload_points, collection creation
- Context7 `/qdrant/fastembed` — TextEmbedding, BAAI/bge-small-en-v1.5, batch_size, multilingual models
- Context7 `/websites/neo4j_apoc_current` — apoc.trigger.install patterns
- Context7 `/websites/qdrant_tech` — create collection with sparse vectors, payload indexing

### Secondary (MEDIUM confidence)
- [federalreserve.gov — FOMC minutes download](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) — confirmed free PDF access, verified URL pattern
- [FRASER / St. Louis Fed — historical FOMC](https://fraser.stlouisfed.org/title/federal-open-market-committee-meeting-minutes-transcripts-documents-677) — historical materials pre-2015
- [sbv.gov.vn/en — SBV English portal](https://www.sbv.gov.vn/en/) — English-language monetary policy reports confirmed available
- [HOSE disclosure portal — hsx.vn](https://www.hsx.vn) — Vietnamese listed company annual reports
- [WebSearch — VN30 earnings practices](https://the-shiv.com/vietnam-vn30-index-stocks/) — confirmed no earnings call transcripts in VN market
- [arxiv 2402.05131 — Financial Report Chunking](https://arxiv.org/abs/2402.05131) — 1024 token, 15% overlap benchmark for financial PDFs
- [scikit-learn cosine_similarity](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html) — verified API

### Tertiary (LOW confidence)
- [BAAI/bge-small-en-v1.5 HuggingFace](https://huggingface.co/BAAI/bge-small-en-v1.5) — English-only limitation confirmed via HuggingFace model card (WebSearch, not Context7)
- [BGE-M3 multilingual model](https://huggingface.co/BAAI/bge-m3) — 1024-dim, 100+ languages including Vietnamese (WebSearch)
- World Bank API for VN macro data — not directly verified, listed as sourcing option

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Neo4j driver, qdrant-client, fastembed all verified via Context7 official docs
- Architecture: HIGH — patterns directly derived from existing project code + verified library APIs
- Pitfalls: MEDIUM-HIGH — English-only embedding limitation is HIGH confidence (verified multiple sources); VN earnings transcript gap is MEDIUM (verified via market research); FRED data gaps are MEDIUM (derived from schema knowledge, not empirically tested against live data)
- Document sourcing: MEDIUM — FOMC access is HIGH confidence; SBV and VN earnings are MEDIUM (portals confirmed, but content coverage/format requires hands-on verification)

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable APIs; FOMC/SBV sourcing is stable; VN market practices unlikely to change)
