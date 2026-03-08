# Stack Research

**Domain:** AI analytical reasoning engine — multi-store RAG + LangGraph orchestration + bilingual report generation
**Researched:** 2026-03-09
**Confidence:** HIGH (all versions verified against PyPI and official sources as of March 2026)

---

## Scope: v2.0 Additions Only

This document covers only what is NEW for v2.0. The v1.0 stack (Docker Compose, PostgreSQL, Neo4j, Qdrant, n8n, FastAPI data-sidecar, SQLAlchemy, pytest) is validated and operational. Do not re-add any of the following:

| Already Installed (sidecar/requirements.txt) | Version |
|---|---|
| `sqlalchemy` | >=2.0.0 |
| `psycopg2-binary` | >=2.9.9 |
| `fastapi` | >=0.115.0 |
| `uvicorn` | >=0.30.0 |
| `pandas` | >=2.2.0 |
| `python-dotenv` | >=1.0.0 |
| `httpx` | >=0.27.0 |
| `pytest` | >=8.0.0 |
| `pytest-asyncio` | >=0.24.0 |

Docker Compose already defines and runs: `postgres:16-alpine`, `neo4j:5.26.21`, `qdrant/qdrant:v1.15.3`, `flyway:10`, dual networks (`ingestion` + `reasoning`). The `reasoning` network exists but has no service attached yet — v2.0 populates it.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `langgraph` | 1.0.10 | Multi-step reasoning graph orchestration | Reached v1.0 stable GA (Oct 2025); current latest is 1.0.10 (Feb 27, 2026). Provides explicit graph nodes — each reasoning step (macro regime classification, valuation, price structure, entry scoring) is a named node with visible inputs, outputs, and state. Cyclical graph support lets the LLM request additional data retrieval before proceeding. Required over LangChain chains because the reasoning pipeline has branching paths (mixed-signal handling, low-confidence regimes) that need graph-level control. |
| `langchain-google-genai` | >=4.0.0 | Gemini API integration for LangGraph nodes | v4.0.0 (released Feb 19, 2026) migrated from the deprecated `google-ai-generativelanguage` SDK to the new `google-genai` SDK. Provides `ChatGoogleGenerativeAI` — the correct class for attaching Gemini to LangGraph nodes with tool-calling and structured output. Use this rather than `google-genai` directly: it provides the `bind_tools()` and `.with_structured_output()` interfaces that LangGraph expects. Official Google + LangChain joint documentation confirms this as the canonical integration path. |
| `llama-index-core` | 0.14.15 | RAG retrieval framework over multi-store | LlamaIndex is the retrieval layer. Unifies access to PostgreSQL (SQL query engine), Neo4j (property graph + text-to-Cypher), and Qdrant (vector similarity) behind a single interface. LangGraph calls LlamaIndex retrievers as tools — this is the dominant production pattern as of 2025/2026. LlamaIndex handles document corpus ingestion, chunking, embedding, and retrieval; LangGraph orchestrates which retriever to call and when. Version 0.14.15 released Feb 18, 2026. |
| `llama-index-graph-stores-neo4j` | 0.5.1 | LlamaIndex → Neo4j property graph integration | Provides `Neo4jPropertyGraphStore` for LlamaIndex to query regime relationships, historical analogues, and asset correlations in Neo4j. Supports `TextToCypherRetriever` (natural language → Cypher) and `VectorContextRetriever` (vector + graph traversal). Required as a separate plugin package from `llama-index-core`. |
| `llama-index-vector-stores-qdrant` | 0.9.1 | LlamaIndex → Qdrant vector retrieval | Provides `QdrantVectorStore` for LlamaIndex to run semantic similarity queries over the manually curated document corpus (Fed minutes, SBV reports, VN earnings) in Qdrant. The existing Qdrant collection uses BAAI/bge-small-en-v1.5 at 384 dimensions — any new document ingestion must use the same model to avoid dimension mismatch. Version 0.9.1 released Jan 13, 2026. |
| `llama-index-llms-google-genai` | 0.3.0 | LlamaIndex → Gemini LLM for retrieval synthesis | Replaces the deprecated `llama-index-llms-gemini` (deprecated at v0.6.2). Provides `GoogleGenAI` LLM class for LlamaIndex's internal query synthesis — turning retrieved context into structured answers before returning results to LangGraph. Required so LlamaIndex can use Gemini for its synthesis steps independently of the LangGraph orchestration layer. Version 0.3.0 released Jul 30, 2025. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langgraph-checkpoint-postgres` | 3.0.4 | Persist LangGraph reasoning state across runs | Required in production. Stores LangGraph graph state as checkpoints in the existing PostgreSQL instance (separate schema from application data). Enables: resume interrupted reasoning chains, audit trail of each reasoning step (required by the explainability constraint in PROJECT.md), and human-review interrupt points. Version 3.0.4 released Jan 31, 2026. |
| `psycopg[binary]` | >=3.1.0 | psycopg3 driver for LangGraph checkpointing | `langgraph-checkpoint-postgres` requires psycopg3 specifically — it is incompatible with psycopg2. The existing sidecar uses `psycopg2-binary` for its ingestion work. Add psycopg3 only in the reasoning service requirements; do not replace or modify the sidecar. Both can coexist in the same Python environment if needed. |
| `llama-index-readers-database` | latest | SQL query engine for PostgreSQL structured data | Allows LlamaIndex to query PostgreSQL tables (OHLCV, fundamentals, structure markers) via SQLAlchemy. Used to pull structured quantitative data as context for regime classification and valuation assessment steps. Wraps the existing SQLAlchemy + psycopg2 connection pattern. |
| `qdrant-client` | >=1.7.0 | Qdrant Python driver | Required by `llama-index-vector-stores-qdrant`. Pin to a version compatible with the running `qdrant/qdrant:v1.15.3` server. The existing Qdrant server is v1.15.3 — `qdrant-client>=1.7.0` supports this server version. |
| `neo4j` | >=5.0.0 | Neo4j Python driver | Required by `llama-index-graph-stores-neo4j` and for direct Cypher queries in LangGraph nodes. Compatible with the running `neo4j:5.26.21` server. |
| `fastembed` | >=0.3.0 | FastEmbed for consistent embedding of new documents | The existing Qdrant collection was initialized with BAAI/bge-small-en-v1.5 at 384 dimensions (locked decision in PROJECT.md). Any new documents added to Qdrant for the v2.0 manually curated corpus must use the same model. Use `fastembed` directly for corpus document embedding during ingestion. |
| `jinja2` | >=3.1.0 | Report template rendering | Renders the JSON + Markdown report templates with dynamic data. Use Jinja2 to produce language-specific (Vietnamese/English) Markdown output from bilingual templates. Separates report presentation logic from LLM output. |
| `markdown` | >=3.5.0 | Markdown → HTML conversion (optional) | Converts Jinja2-rendered Markdown to HTML for any downstream rendering or preview. Use `markdown` (Python-Markdown) rather than `markdown2` — better CommonMark compliance and active maintenance. |
| `pydantic` | >=2.0.0 | Structured LLM output validation | For validating Gemini structured output (JSON report cards, entry quality scores). LangGraph state nodes should use Pydantic models to enforce schema. Already a transitive dependency but should be pinned explicitly in the reasoning service. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest-asyncio` | Async test support for LangGraph nodes | Already in sidecar requirements. The reasoning service needs it too — LangGraph nodes are async by default. Use `asyncio_mode = "auto"` in `pyproject.toml` or `pytest.ini`. |
| `langsmith` (optional) | LangGraph observability and step tracing | Provides time-travel debugging for LangGraph graph runs. Zero code changes required: set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` env vars to activate. Not required for v2.0 but worth knowing if debugging the reasoning chain becomes difficult. |

---

## Installation

New `reasoning/requirements.txt` for the new Docker service:

```bash
# Core reasoning orchestration
langgraph==1.0.10
langchain-google-genai>=4.0.0

# LlamaIndex multi-store retrieval
llama-index-core==0.14.15
llama-index-graph-stores-neo4j==0.5.1
llama-index-vector-stores-qdrant==0.9.1
llama-index-llms-google-genai==0.3.0
llama-index-readers-database

# LangGraph state persistence
langgraph-checkpoint-postgres==3.0.4
psycopg[binary]>=3.1.0

# Storage drivers
qdrant-client>=1.7.0
neo4j>=5.0.0
fastembed>=0.3.0

# Report generation
jinja2>=3.1.0
markdown>=3.5.0
pydantic>=2.0.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

Note: `sqlalchemy`, `psycopg2-binary`, `pandas`, `python-dotenv`, and `httpx` are already in the sidecar. The reasoning service may inherit or duplicate these — keep them separate per-service to maintain Docker layer independence.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `langchain-google-genai>=4.0.0` | `google-genai` directly | Only if not using LangGraph — direct SDK lacks `bind_tools()` and `.with_structured_output()` that LangGraph requires. |
| `langchain-google-genai>=4.0.0` | `google-generativeai` | Never — deprecated Nov 30, 2025. No new features, no Gemini 2.x support. |
| `llama-index-llms-google-genai` | `llama-index-llms-gemini` | Never — deprecated at v0.6.2. Migration to `google-genai` is mandatory. |
| `llama-index-core` for retrieval | LangChain retrievers | Only if already invested in LangChain ecosystem. LlamaIndex has native `Neo4jPropertyGraphStore` with text-to-Cypher and `QdrantVectorStore` with FastEmbed matching the existing collection. LangChain's Neo4j integration requires `langchain-neo4j` and lacks the same property graph retriever sophistication. |
| `langgraph-checkpoint-postgres` | `MemorySaver` (in-memory) | Only for local development and testing. `MemorySaver` loses all state on container restart — unacceptable for weekly/monthly production runs. |
| `psycopg[binary]` (psycopg3) | `psycopg2-binary` | psycopg2 is incompatible with `langgraph-checkpoint-postgres`. Must use psycopg3 for the checkpoint system specifically. |
| `jinja2` + `markdown` for reports | WeasyPrint (PDF generation) | Only when a PDF output is required — v3.0 when the frontend exists. WeasyPrint requires heavy system dependencies (Pango, Cairo, Fontconfig binaries). For v2.0 JSON + Markdown output, it is unnecessary overhead on a self-hosted VPS. |
| `jinja2` + `markdown` for reports | Raw LLM string output only | Never rely on raw strings alone. Gemini structured output → Pydantic validation → Jinja2 template rendering enforces the report JSON schema and produces consistent Markdown across runs without prompt-formatting drift. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` | Deprecated Nov 30, 2025. No new features. Does not support Gemini 2.x models including gemini-2.0-flash and gemini-2.5-flash. Official deprecation notice on GitHub. | `langchain-google-genai>=4.0.0` for LangGraph nodes; `llama-index-llms-google-genai` for LlamaIndex synthesis |
| `llama-index-llms-gemini` | Deprecated at v0.6.2. Official replacement exists and is actively maintained. | `llama-index-llms-google-genai==0.3.0` |
| `langchain` (core) as a direct dependency | LangGraph 1.x is standalone — it does not require the full `langchain` package for graph orchestration. Adding `langchain` directly pulls unnecessary weight. | `langgraph` + `langchain-google-genai` only (the latter has required LangChain interfaces as a transitive dep) |
| OpenAI embeddings (1536-dim) for new corpus documents | Would create a dimension mismatch with the existing Qdrant collection (384-dim BAAI/bge-small-en-v1.5). Changing embedding models would require re-embedding all existing vectors — a costly migration. | `fastembed` with `BAAI/bge-small-en-v1.5` — the same model used at Qdrant init |
| `pgvector` / `PGVectorStore` for retrieval | Qdrant already exists and is purpose-built for vector search. Adding pgvector would split vector retrieval across two backends (Qdrant and PostgreSQL) with no benefit. | `llama-index-vector-stores-qdrant` over the existing Qdrant service |
| WeasyPrint in v2.0 | Requires Pango, Cairo, Fontconfig system libraries — significant binary overhead for a self-hosted VPS. Report spec for v2.0 is JSON + Markdown, not PDF. | `jinja2` + `markdown` library; defer PDF to v3.0 when a frontend UI exists |
| CrewAI / AutoGen for orchestration | Less control over execution graph. LangGraph's explicit graph definition suits the structured 3-layer analysis (regime → valuation → price structure → entry score). CrewAI agents are less deterministic and harder to audit step-by-step. | `langgraph` |

---

## Stack Patterns by Variant

**For a LangGraph node that needs structured quantitative data (regime metrics, valuation ratios, price structure markers):**
- Use `llama-index-readers-database` SQL query engine → existing SQLAlchemy → PostgreSQL
- Return Pydantic-validated dict to LangGraph state
- Because: Structure markers and fundamentals are pre-computed and stored in PostgreSQL during ingestion (PROJECT.md constraint: LangGraph reads them, never computes on the fly)

**For a LangGraph node that needs historical analogue matching (macro regime similarity search):**
- Use `llama-index-graph-stores-neo4j` with `TextToCypherRetriever`
- Because: Neo4j stores regime relationships and historical analogues with APOC triggers maintaining graph consistency; text-to-Cypher lets Gemini query the graph without hardcoded Cypher templates that would break with schema changes

**For a LangGraph node that needs document context (Fed minutes, SBV reports, VN earnings):**
- Use `llama-index-vector-stores-qdrant` with `QdrantVectorStore`
- Embed query using `fastembed` BAAI/bge-small-en-v1.5 before querying (must match collection embedding model)
- Because: The existing 384-dim Qdrant collection holds the manually curated document corpus; same embedding model is mandatory

**For bilingual report generation (Vietnamese + English):**
- Use Gemini structured output → Pydantic model with `vi_text` / `en_text` fields per report card
- Then render each language variant through a Jinja2 template
- Output: `report_{ticker}_{date}_vi.md` + `report_{ticker}_{date}_en.md` + `report_{ticker}_{date}.json`
- Because: Single Gemini call with structured output produces both languages atomically; Pydantic enforces schema; Jinja2 separates presentation from data; raw LLM string output alone produces inconsistent formatting across runs

---

## Docker Compose Integration

The reasoning service belongs in the `reasoning` Docker network profile. The `reasoning` network already exists in `docker-compose.yml` and `postgres`, `neo4j`, and `qdrant` are already members of it. Suggested new service addition:

```yaml
  reasoning:
    build:
      context: ./reasoning
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      NEO4J_URL: bolt://neo4j:7687
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    networks:
      - reasoning    # reasoning network ONLY — cannot reach n8n (INFRA-02 enforcement)
    profiles: ["reasoning"]
```

Key integration points:
- `GEMINI_API_KEY` is a new env var — must be added to `.env` on the VPS
- Storage service names (`postgres`, `neo4j`, `qdrant`) resolve identically inside the reasoning network — same hostnames the sidecar uses
- Flyway already joins both networks via the `storage` profile; any new PostgreSQL tables needed for checkpoint storage (V6+ migrations) use the existing Flyway pipeline
- The `reasoning` service intentionally has no host port mapping — it is invoked by triggers (n8n HTTP request → FastAPI reasoning endpoint), not exposed directly

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `langgraph==1.0.10` | Python >=3.10 | LangGraph 1.x requires Python >=3.10. The reasoning service Dockerfile must use `python:3.12-slim` or similar — NOT the same base as the sidecar if sidecar is on 3.9. |
| `llama-index-core==0.14.15` | Python >=3.9, <4.0 | Compatible with Python 3.10+ used for the reasoning service |
| `llama-index-vector-stores-qdrant==0.9.1` | `qdrant-client>=1.7.0` | Pin qdrant-client to a version that supports `qdrant/qdrant:v1.15.3` server — `>=1.7.0` satisfies this |
| `llama-index-graph-stores-neo4j==0.5.1` | `neo4j>=5.0.0` | Compatible with running `neo4j:5.26.21` server |
| `langchain-google-genai>=4.0.0` | Pulls `google-genai` transitively | Do not pin `google-genai` separately — let `langchain-google-genai` manage the SDK version to avoid conflicts |
| `langgraph-checkpoint-postgres==3.0.4` | `psycopg[binary]>=3.1.0` | Requires psycopg3. Cannot substitute psycopg2. Both psycopg2 and psycopg3 can coexist in one Python environment |
| `fastembed>=0.3.0` | BAAI/bge-small-en-v1.5 (384-dim) | Must use the same model as the existing Qdrant collection. Changing the model requires re-embedding all existing vectors — treat this as immutable |

---

## Sources

- [langgraph PyPI](https://pypi.org/project/langgraph/) — version 1.0.10, Feb 27, 2026. HIGH confidence.
- [google-genai PyPI](https://pypi.org/project/google-genai/) — version 1.66.0, Mar 4, 2026. HIGH confidence.
- [langchain-google-genai PyPI](https://pypi.org/project/langchain-google-genai/) — v4.0.0 SDK migration confirmed, last release Feb 19, 2026. HIGH confidence.
- [llama-index-core PyPI](https://pypi.org/project/llama-index-core/) — version 0.14.15, Feb 18, 2026. HIGH confidence.
- [llama-index-graph-stores-neo4j PyPI](https://pypi.org/project/llama-index-graph-stores-neo4j/) — version 0.5.1. HIGH confidence.
- [llama-index-vector-stores-qdrant PyPI](https://pypi.org/project/llama-index-vector-stores-qdrant/) — version 0.9.1, Jan 13, 2026. HIGH confidence.
- [llama-index-llms-google-genai PyPI](https://pypi.org/project/llama-index-llms-google-genai/) — version 0.3.0, deprecates `llama-index-llms-gemini`. HIGH confidence.
- [llama-index-llms-gemini PyPI deprecation notice](https://pypi.org/project/llama-index-llms-gemini/) — confirmed deprecated at v0.6.2. HIGH confidence.
- [langgraph-checkpoint-postgres PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) — version 3.0.4, Jan 31, 2026. HIGH confidence.
- [google-generativeai deprecated GitHub](https://github.com/google-gemini/deprecated-generative-ai-python) — deprecated Nov 30, 2025. HIGH confidence.
- [LangGraph + Gemini ReAct agent — Google AI for Developers](https://ai.google.dev/gemini-api/docs/langgraph-example) — official Google documentation confirming LangGraph + langchain-google-genai as the canonical integration path. HIGH confidence.
- [LlamaIndex Neo4j property graph docs](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/) — TextToCypherRetriever and VectorContextRetriever confirmed. HIGH confidence.
- [LlamaIndex + LangGraph integration pattern — ZenML](https://www.zenml.io/blog/llamaindex-vs-langgraph) — LlamaIndex for retrieval + LangGraph for orchestration is the dominant production pattern. MEDIUM confidence (non-official, consistent with multiple sources).
- [Google GenAI SDK libraries overview](https://ai.google.dev/gemini-api/docs/libraries) — confirms `google-genai` as the recommended SDK, `google-generativeai` deprecated. HIGH confidence.

---

*Stack research for: Stratum v2.0 Analytical Reasoning Engine — new capabilities only*
*Researched: 2026-03-09*
