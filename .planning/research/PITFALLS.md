# Pitfalls Research

**Domain:** Adding LLM-powered analytical reasoning to an existing financial data platform — macro regime classification, RAG retrieval, bilingual report generation, constrained VPS deployment
**Researched:** 2026-03-09
**Confidence:** MEDIUM-HIGH (v1.0 pitfalls retained from HIGH-confidence sources; v2.0 additions cross-verified across LangChain/LlamaIndex official docs, Google AI docs, and community post-mortems)

---

## Critical Pitfalls

### Pitfall 1: LangGraph State Bloat Causes Gemini Context Overflow and VPS OOM

**What goes wrong:**
Each LangGraph node appends retrieved documents, intermediate analysis, and structured outputs to the shared state. By the time the report generation node runs, the state object contains tens of thousands of tokens of accumulated context from regime classification, valuation retrieval, and price structure analysis. This triggers two failure modes simultaneously: (1) the assembled context exceeds Gemini's context window or token budget, causing a 429/400 error mid-pipeline, and (2) the VPS runs out of heap memory because LangGraph serializes the entire state object to the PostgresSaver checkpointer at every super-step. On an 8GB VPS running PostgreSQL, Neo4j, Qdrant, and the LangGraph service concurrently, a 50MB state checkpoint is the difference between a successful run and an OOM-killed container.

**Why it happens:**
LangGraph's immutable state versioning creates a new state snapshot at each step. Without explicit pruning, all intermediate data accumulates. Early development does not surface this because test cases use small synthetic datasets; production runs with full 20-stock VN30 batch analysis and multiple retrieved documents expose it. Developers naturally put everything "useful" in state to avoid re-fetching.

**How to avoid:**
- Define a strict `TypedDict` state schema with no unbounded list or dict fields — every field has a fixed type and purpose
- Each node outputs only what the *next* node needs; raw retrieved documents are dropped from state after the node that used them completes
- Keep retrieved document chunks in a separate context payload passed as a function argument, not embedded in LangGraph state
- Set a hard token budget check before every Gemini call: count tokens in the assembled context; if > 80% of the model's context window, the node raises a structured error (`CONTEXT_TOO_LARGE`) and truncates lowest-relevance documents
- Use `PostgresSaver` for the checkpointer (not `InMemorySaver`) but store only compact state objects — never raw document text in checkpoints
- Test the full pipeline with a realistic 20-stock batch (not a 3-stock toy example) during the reasoning pipeline phase before adding any new nodes

**Warning signs:**
- `TypedDict` state has a field typed as `context: dict`, `documents: list[Any]`, or `retrieved: list[str]` with no length bound
- No token count is checked before calling the Gemini API
- Pipeline passes on 3-stock test data but times out or crashes on 20-stock production runs
- Docker logs show OOM-killed for the LangGraph service container during batch report generation

**Phase to address:**
AI reasoning pipeline — state schema design must enforce size constraints from the first implementation, before any retrieval nodes are connected.

---

### Pitfall 2: LlamaIndex Cannot Use Most Retrievers Against the Existing Neo4j Graph

**What goes wrong:**
LlamaIndex's built-in retrievers — `VectorContextRetriever`, `LLMSynonymRetriever`, and auto-generated embedding-based graph traversal — depend on LlamaIndex-specific metadata properties that LlamaIndex inserts when *it* creates the graph. The Stratum Neo4j graph was created by the v1.0 ingestion pipeline (n8n + APOC triggers), not by LlamaIndex. None of the LlamaIndex-expected node properties exist. When the retrieval layer is added, developers assume the fancy retrievers will "just work" against the existing graph and discover during integration testing that they return nothing or crash.

**Why it happens:**
The LlamaIndex documentation covers the happy path of LlamaIndex creating and querying its own graph. The "externally created graph" warning is buried in a single caveat: "If your graph was created outside of LlamaIndex, the most useful retrievers will be Text-to-Cypher or Cypher templates." Developers do not read this far before starting implementation.

**How to avoid:**
- Accept from day one that the Stratum Neo4j graph will only support `TextToCypherRetriever` and `CypherTemplateRetriever` from LlamaIndex — do not attempt to use other built-in retrievers
- Use `CypherTemplateRetriever` for all known, structured retrieval patterns (e.g., "find regimes that RESEMBLE the current period with similarity > 0.7") — templates are safer than free-form Text-to-Cypher for financial queries
- Use `TextToCypherRetriever` only for exploratory queries where the exact pattern is not known in advance; validate generated Cypher against the schema before execution
- Write all Cypher query templates explicitly before building the retrieval layer — do not rely on LlamaIndex to generate correct Cypher against a domain-specific schema
- Test each Cypher template against the actual Neo4j instance with representative data before wiring into LangGraph
- The `SimplePropertyGraphStore` does not support Cypher at all — never confuse it with the `Neo4jPropertyGraphStore`

**Warning signs:**
- LlamaIndex `VectorContextRetriever` or `LLMSynonymRetriever` is configured against the Stratum Neo4j graph
- Retrieval queries return empty results even when matching nodes exist in Neo4j
- Cypher queries generated by LlamaIndex produce full graph scans (`MATCH (n) WHERE ...` without relationship traversal)
- Integration test for Neo4j retrieval was skipped because "it works against the test schema"

**Phase to address:**
Retrieval layer phase — establish which LlamaIndex retrievers are compatible with externally-created graphs before writing any retrieval code. Write Cypher templates before connecting to LangGraph.

---

### Pitfall 3: LangGraph Reducer Misuse Causes Silent State Corruption

**What goes wrong:**
LangGraph reducers define how state updates merge when multiple nodes write to the same field. The default behavior for `TypedDict` fields without an explicit reducer is replacement (last write wins). When a developer adds `add_messages`-style reducers to fields that should be replaced (e.g., `current_regime_label`) or uses plain replacement for fields that should accumulate (e.g., `retrieved_analogues`), state values become silently wrong. The regime label from step 2 overwrites the correct label from step 4, or analogue lists from parallel retrieval branches only contain results from whichever branch finished last.

**Why it happens:**
Reducer semantics are not obvious, especially when nodes run in parallel branches. The difference between "last write wins" and "accumulate via reducer" is not enforced at the type level — both compile and run without error; the wrong one just produces incorrect financial analysis silently.

**How to avoid:**
- Document the expected reducer for every `TypedDict` field in a comment alongside its definition — "REPLACE" or "ACCUMULATE" — and match the annotation accordingly
- Use `Annotated[list, operator.add]` for any field that multiple nodes contribute to (e.g., analogue lists from parallel retrieval branches)
- Use the `Overwrite` type annotation for fields that should always be replaced, never accumulated
- Write unit tests for each node that assert the state shape after the node runs — not just that the node completes without error
- Never use a catch-all `dict` or `list[Any]` field as a temporary accumulator between nodes — design explicit typed fields for each stage's output

**Warning signs:**
- State `TypedDict` has fields with no `Annotated` type annotation (relying on implicit replacement semantics)
- Parallel retrieval branches write to the same list field without a reducer
- Integration tests only check the final report output, not intermediate state after each node
- A bug report where "regime classification is correct in isolation but wrong in the full pipeline" — classic reducer contamination

**Phase to address:**
AI reasoning pipeline — reducer design must be explicit and tested before any parallel node branches are added.

---

### Pitfall 4: Gemini Free Tier Is Not a Viable Production Backend (Post-December 2025)

**What goes wrong:**
The Gemini free tier was previously a reasonable option for low-volume production use. After the December 7, 2025 quota changes, free tier RPM for most models dropped to 5 RPM with tighter daily request limits, making it insufficient for a weekly batch report generation job that analyzes 20+ VN30 stocks. A batch run generating reports for all 30 VN30 stocks plus gold will hit 429 rate-limit errors mid-batch with no graceful degradation — the pipeline fails partway through, leaving a partial set of reports.

**Why it happens:**
The quota change was not widely announced. Developers who benchmarked on the free tier before December 2025 have working rate-limit logic that no longer matches the actual limits. Batch jobs do not naturally spread requests over time; they fire as fast as the upstream pipeline produces inputs.

**How to avoid:**
- Use Gemini Tier 1 paid (150-300 RPM) for any production workload with more than a handful of documents
- Implement exponential backoff with jitter for all Gemini API calls — never raw retry on 429
- Add a configurable inter-request delay between LangGraph nodes that call Gemini (e.g., 2 seconds minimum for Tier 1, 12 seconds for free tier) — make this delay a config value, not hardcoded
- Implement Gemini context caching for static content (system prompt, macro framework documents, glossary) — cached tokens cost 10% of base input price and the minimum threshold is 1,024 tokens for 2.5 Flash
- Set Gemini API spend alerts at $5, $10, and $25/month thresholds in Google Cloud console before running any production batch
- Structure batch jobs to process one stock completely before starting the next, not all stocks simultaneously — this naturally throttles API usage and allows graceful partial completion

**Warning signs:**
- Gemini API calls have no retry logic or only immediate retry (no backoff)
- Batch report generation fires all Gemini calls in rapid succession without inter-request delay
- No API spend alert is configured
- Context caching is not used for the system prompt or reference documents that are identical across all stock reports
- The pipeline has no mechanism to resume from partial completion after a rate-limit failure

**Phase to address:**
AI reasoning pipeline — rate-limit handling, backoff, and context caching must be designed before the first batch test against the Gemini API.

---

### Pitfall 5: Vietnamese Financial Terminology Produces Inconsistent Bilingual Output

**What goes wrong:**
Gemini generates Vietnamese financial text that uses different translations for the same English term across reports — "lãi suất cơ bản," "lãi suất tham chiếu," and "lãi suất chính sách" may all be used for "policy rate" within the same batch. More critically, Vietnamese-specific market terms (VNINDEX, HNX, VN30, HoSE, NĐT cá nhân) may be transliterated inconsistently or replaced with generic descriptions. Financial NER (Named Entity Recognition) in Vietnamese is under-researched relative to English, and general-purpose LLMs have not been trained on Vietnamese financial corpora at sufficient depth for consistent domain terminology.

**Why it happens:**
Vietnamese is a tonal, low-resource language for financial NLP. LLMs generate the statistically most likely Vietnamese text, but without a grounding term dictionary, "most likely" varies by context. There is no standard Vietnamese financial terminology authority equivalent to the CFA Institute's English glossary. Each Gemini call independently generates translations without reference to previous calls.

**How to avoid:**
- Build and maintain a Vietnamese financial term dictionary as a project artifact (`glossary/vn_financial_terms.json`) — this is a known gap from v1.0 that must be resolved before bilingual generation can be validated
- Include the relevant term dictionary as part of the Gemini system prompt for every report generation call — not the full glossary, but the terms relevant to the report type (macro terms for regime sections, valuation terms for fundamental sections)
- Use Gemini structured output with explicit string enums for high-stakes labels (regime names, entry quality tiers) so the model selects from a controlled Vietnamese vocabulary, not free generation
- After generating each report, run a term-consistency check: extract all occurrences of key financial terms and verify they match the approved glossary entries
- Store the glossary in Neo4j as `Term` nodes with `english_label` and `vietnamese_label` properties, queryable as part of the report generation context

**Warning signs:**
- No Vietnamese financial term dictionary exists as a project artifact
- Vietnamese report sections generated from different Gemini calls use different translations for "P/E ratio," "earnings growth," or "macro regime"
- Term consistency check is manual (spot-checked by a human) rather than automated
- The Gemini system prompt for bilingual generation does not include a terminology reference

**Phase to address:**
Bilingual report generation phase — the Vietnamese term dictionary must be built and included in prompts before any bilingual output is generated; consistency checks must be automated before the first report is reviewed.

---

### Pitfall 6: LangGraph Checkpointer Writes Stall the VPS During Batch Generation

**What goes wrong:**
LangGraph writes a checkpoint to PostgreSQL at every super-step. In a pipeline that generates reports for 30 stocks × 5 nodes per pipeline = 150 checkpoint writes per batch run. Each checkpoint serializes the full state object to the `checkpoints` table in PostgreSQL. If the state object is large (see Pitfall 1) and PostgreSQL is the same instance used by n8n for workflow data, checkpoint writes compete with ingestion jobs, n8n UI queries, and report storage writes — causing query latency spikes across all services and potentially stalling the VPS under load.

**Why it happens:**
LangGraph's PostgreSQL checkpointer uses the same connection pool and database as the rest of the application unless explicitly configured otherwise. The `langgraph-checkpoint-postgres` package creates its own table schema in whatever database it is connected to. Developers use the application's main PostgreSQL database for convenience.

**How to avoid:**
- Create a dedicated PostgreSQL database for LangGraph checkpoints, separate from the main application database — use the same PostgreSQL instance but a different `langgraph_checkpoints` database to isolate connection pools
- Set aggressive TTLs on checkpoints: for weekly/monthly analysis that runs batch and completes, checkpoint history beyond 24 hours has no operational value — add a cleanup job that purges old checkpoints
- Configure LangGraph to use `AsyncPostgresSaver` (async checkpointer) so checkpoint writes do not block the node execution thread
- Size the state object to be small (see Pitfall 1) — a 1KB state checkpoint has negligible impact; a 10MB state checkpoint blocks PostgreSQL connections
- Monitor checkpoint table size weekly; add a `docker exec` alert if the `langgraph_checkpoints` database grows beyond 500MB

**Warning signs:**
- LangGraph checkpoints are stored in the same PostgreSQL database as n8n workflow data and application tables
- PostgreSQL response time increases noticeably during batch report generation
- No checkpoint cleanup job exists; the `checkpoints` table grows unboundedly
- `AsyncPostgresSaver` is not used — synchronous checkpoint writes block the pipeline thread

**Phase to address:**
Infrastructure phase (Docker Compose service design) — database isolation must be configured before the LangGraph service is added to the stack.

---

### Pitfall 7: LLM Hallucinating Financial Numbers in Multi-Step Reasoning Chain

**What goes wrong:**
The LLM fabricates specific financial figures — P/E ratios, earnings growth rates, price levels, index values — that sound authoritative but are drawn from training data, not the retrieved context. In a multi-step LangGraph pipeline, a hallucinated number in step 2 (regime classification) becomes "verified" input to step 3 (valuation assessment) and step 4 (report generation). Financial LLM hallucination rates average 10-20% on complex reasoning tasks; even a 5% rate on numbers an investor acts on is dangerous. GPT-4 Turbo with retrieval on FinanceBench hallucinated on 81% of financial calculation questions.

**Why it happens:**
LLMs complete statistically likely sequences. When a financial number is not present in the retrieved context, the model fills in from training memory rather than refusing. The problem amplifies in agentic pipelines because each node trusts the output of the previous node without re-grounding against source data. Gemini's structured JSON output mode constrains the *format* but not the *factual accuracy* of field values.

**How to avoid:**
- Every numerical claim in the final report must be traceable to a specific retrieved document, PostgreSQL record, or Neo4j node — not LLM inference
- LangGraph nodes that produce numbers must cite their source as a structured output field (e.g., `"pe_ratio": 18.5, "pe_ratio_source": "postgresql:fundamentals:VIC:2025-Q3"`) alongside the value
- Use Gemini structured output with JSON schema that includes source citation fields for every numeric value; a report that cannot cite its numbers fails schema validation and triggers a pipeline error
- Add a grounding check node at the end of the reasoning chain that verifies all numbers in the narrative appear in the context passed to the LLM; numbers present in the report but absent from retrieved context fail the check
- Never ask Gemini to recall historical figures from training memory; retrieve first, then ask the LLM to interpret the retrieved values

**Warning signs:**
- Report contains a specific number (P/E ratio, EPS, price) not present in any retrieved document or database record
- LLM output contains hedge phrases like "approximately" or "historically around" on specific numeric data points — the LLM is drawing from training, not context
- Numbers in the report differ slightly from database values (model "rounded" in a way that changed meaning)
- Structured output schema does not include source citation fields alongside numeric values

**Phase to address:**
AI reasoning pipeline design phase and report validation phase — grounding enforcement must be built into the pipeline from the first node, not added as a post-processing check.

---

### Pitfall 8: Stale Data Presented as Current in Reports

**What goes wrong:**
A weekly report is generated using data last refreshed days ago — because an n8n scheduled job silently failed, a data source was rate-limited, or a free-tier API (vnstock, FRED) temporarily returned errors. The LangGraph pipeline reads whatever is in PostgreSQL with no knowledge of freshness. The World Gold Council data has a 45-day publication lag by design; vnstock may return stale data during broker infrastructure changes. Reports go out with outdated OHLCV prices or macro indicators without flagging which values are stale.

**Why it happens:**
n8n scheduled jobs report success even when they retrieve 0 new rows, unless explicitly coded to fail on empty results. LangGraph has no inherent data freshness awareness — it reads rows as they exist. The `data_as_of` timestamps established in v1.0 exist in the database but the reasoning pipeline must be coded to read and act on them.

**How to avoid:**
- Every LangGraph node that reads from PostgreSQL must also read the `data_as_of` timestamp for the data it fetches and compare it against a configurable freshness threshold
- If `data_as_of` exceeds the freshness threshold, the node emits a warning that propagates to the final report as an explicit "DATA WARNING: [field] not refreshed since [date]" section
- Check the `pipeline_run_log` table (established in v1.0) at the start of every report generation run; if any required ingestion job has not run successfully within its expected cadence, abort report generation with an explicit error rather than silently using stale data
- World Gold Council data must have `data_as_of` reflecting the coverage period (45 days behind), not the fetch date — the reasoning pipeline must account for this lag in its freshness logic
- vnstock data during broker infrastructure changes may be stale for 1-3 days; the pipeline must surface this explicitly in reports

**Warning signs:**
- LangGraph retrieval nodes do not read `data_as_of` from fetched rows
- No check of `pipeline_run_log` before initiating report generation
- Reports contain "as of [date]" without that date being retrieved from the data layer
- An n8n run shows 0 new rows ingested but pipeline_run_log records it as success

**Phase to address:**
Retrieval layer phase — freshness checks must be built into every retrieval node before connecting them to the reasoning chain.

---

### Pitfall 9: Macro Regime Misclassification as Overconfident Single Label

**What goes wrong:**
The platform forces every macro environment into a single label ("stagflation," "recovery," "expansion") even when data produces mixed signals — inflation falling while growth also decelerates, or Vietnam-specific conditions diverging from global regime. The AI presents this label confidently, and all downstream reasoning treats it as ground truth. Users see "Current regime: Stagflation" with no indication this is a probabilistic classification with 55% confidence.

**Why it happens:**
Classification tasks reward clean categories. Neo4j analogue nodes are stored as discrete regime types. LLM prompts are written to produce a label. The system is designed around the happy path of a clean regime, not the common case of mixed signals.

**How to avoid:**
- Store regime classification as a distribution in Neo4j, not a point estimate: `{stagflation: 0.55, slowdown: 0.30, expansion: 0.15}`
- Require the LangGraph regime classification node to produce a confidence score alongside the label as part of its structured output
- If top regime confidence < 70%, the report explicitly surfaces "Mixed Signal Environment" and the two most likely analogues — this is a first-class output defined in PROJECT.md requirements, not a fallback edge case
- Historical analogues in Neo4j must include `analogue_similarity_score` on `RESEMBLES` relationships so weak matches are distinguishable from strong matches
- Test the regime classification node with explicitly mixed-signal inputs (e.g., rising inflation + falling growth) before connecting it to the valuation node

**Warning signs:**
- Neo4j `RESEMBLES` relationships have no weight or confidence property
- The LangGraph regime node always outputs a single string label, never a probability distribution
- No test cases for mixed-signal macro inputs exist in the test suite
- Report language uses "The current regime is X" without any confidence qualification

**Phase to address:**
Knowledge graph schema phase (regime relationship properties) and AI reasoning pipeline phase (regime classification node must output distributions).

---

### Pitfall 10: Neo4j Schema Designed Before Retrieval Query Patterns Are Known

**What goes wrong:**
The Neo4j schema is designed during early implementation with macro regime nodes connected to current conditions. Later, when historical analogue retrieval is added ("this environment resembles 2015-2016 because X"), the schema requires a rewrite because `RESEMBLES` relationships do not carry confidence scores, date ranges, or multi-dimensional similarity vectors. LlamaIndex retrieval queries break when the schema changes mid-project. Rebuilding the graph mid-milestone is a high-cost operation.

**Why it happens:**
Graph databases are schema-flexible, which tempts early shortcuts. Relationship properties are added as afterthoughts rather than first-class design decisions. The retrieval query pattern ("find regimes where similarity_score > 0.7 across these three macro dimensions") is designed after the storage schema, not before it.

**How to avoid:**
- Write the LlamaIndex/Cypher retrieval queries *first* — what Cypher will you run to find historical analogues? — and work backward to the schema that supports those queries
- Use `RESEMBLES` relationships with required properties from inception: `similarity_score: float`, `dimensions_matched: list[str]`, `period_start: date`, `period_end: date`, `source: string`
- Never add a relationship type to Neo4j without defining all its required properties; bare unweighted relationships are schema debt
- Test with at least 5 years of historical analogues loaded before building any reasoning nodes that depend on analogue retrieval
- Store blob data (document text, raw reports) in PostgreSQL with a reference key in Neo4j — never embed large text in Neo4j nodes

**Warning signs:**
- Neo4j `RESEMBLES` relationships have no properties (bare edges with no weights or metadata)
- LlamaIndex queries use `MATCH (n:Regime)` without traversing relationships
- Schema was designed in one session and never validated against actual retrieval query patterns
- The graph was populated with data before the retrieval layer was defined

**Phase to address:**
Knowledge graph schema phase — must precede both data loading and reasoning pipeline phases; schema and retrieval queries must be co-designed.

---

### Pitfall 11: Text-to-Cypher Generates Invalid Queries Against Domain-Specific Schema

**What goes wrong:**
LlamaIndex's `TextToCypherRetriever` generates Cypher queries by asking the LLM to interpret the schema and produce valid Cypher. For general schemas, this works reasonably well. For the Stratum domain-specific schema (custom regime labels, Vietnamese stock identifiers, multi-dimensional similarity relationships), the generated Cypher is frequently wrong: it references non-existent node labels, misidentifies relationship directions, generates full graph scans, or uses property names that do not match the schema. The Stratum Neo4j schema with APOC triggers and custom constraints adds additional complexity that confuses auto-generated Cypher. This was benchmarked in the Neo4j Text2Cypher 2024 dataset and confirmed to have accuracy issues with domain-specific schemas.

**Why it happens:**
LLMs generating Cypher learn from public Neo4j schemas. The Stratum schema is domain-specific and not represented in training data. Text-to-Cypher accuracy degrades on schemas with multi-labeled nodes (which Neo4j schema generation methods particularly struggle with) and on relationship types with many required properties.

**How to avoid:**
- Prefer `CypherTemplateRetriever` over `TextToCypherRetriever` for all production retrieval paths — templates are parameterized but safe
- If `TextToCypherRetriever` is used, validate the generated Cypher using an iterative planner pattern: generate → validate against schema → re-generate if invalid → maximum 3 iterations before falling back to template
- Create a schema documentation string (formatted for the LLM) that lists every node label, relationship type, and property with types — include this in the Text-to-Cypher prompt explicitly
- Never allow un-validated LLM-generated Cypher to execute against the production Neo4j instance; use a read-only Neo4j user for all LlamaIndex retrieval queries
- Log every generated Cypher query during the first 4 weeks of production operation for post-hoc review

**Warning signs:**
- `TextToCypherRetriever` is used for structured regime analogue queries without validation
- Generated Cypher contains `MATCH (n)` without a label or `WHERE` clause (full graph scan)
- Retrieval returns empty results even when matching nodes exist — common symptom of wrong node labels
- The Neo4j user used by LlamaIndex has write permissions

**Phase to address:**
Retrieval layer phase — Cypher template library must be built and tested before Text-to-Cypher is enabled for any retrieval path.

---

### Pitfall 12: VPS Memory Exhaustion During Concurrent Service Operation

**What goes wrong:**
The v1.0 stack already runs 7 Docker services (PostgreSQL, Neo4j, Qdrant, n8n, FastAPI sidecar, and supporting services) on an 8GB VPS. Adding LangGraph as a new service with its own Python process, plus context-loading for financial document retrieval, pushes total resident memory over the VPS limit. The Linux OOM killer terminates a random service — often Neo4j, which has no built-in crash recovery — rather than the LangGraph service that caused the spike. The VPS operates without swap, so memory exhaustion is immediate rather than degraded.

**Why it happens:**
Each service is individually sized within acceptable limits; the problem is the *sum*. Neo4j has a large default JVM heap. Qdrant loads the BAAI/bge-small-en-v1.5 model into memory. LangGraph loads Python dependencies for LlamaIndex, LangGraph, and the Gemini SDK. During a batch report generation, all services are simultaneously active. Without per-container memory limits in Docker Compose, there is no ceiling on any individual service.

**How to avoid:**
- Set explicit `mem_limit` constraints in Docker Compose for every service: Neo4j (2GB max), Qdrant (1GB max), PostgreSQL (512MB max), n8n (512MB max), FastAPI sidecar (256MB max), LangGraph service (2GB max) — total budgeted: 6.3GB, leaving 1.7GB for the host OS and buffer
- Configure swap (4GB minimum) on the VPS host before adding the LangGraph service — this prevents instant OOM kills and gives time for graceful degradation
- Set Neo4j JVM heap explicitly in the `docker-compose.yml` env: `NEO4J_dbms_memory_heap_initial_size=512m` and `NEO4J_dbms_memory_heap_max_size=1g` — Neo4j defaults consume 25% of system RAM, which is 2GB on an 8GB VPS
- Qdrant: set `QDRANT__STORAGE__ON_DISK_PAYLOAD=true` to reduce memory footprint by storing payload on disk rather than RAM
- Schedule LangGraph batch report generation during off-peak hours (e.g., 02:00 on Sunday) when n8n ingestion jobs are not running concurrently
- Monitor memory usage with `docker stats` during the first 3 batch runs; establish a baseline before adding more stocks to the watchlist

**Warning signs:**
- No `mem_limit` or `mem_reservation` set on any Docker Compose service
- No swap configured on the VPS host (`swapon --show` returns empty)
- Neo4j `dbms.memory.heap.max_size` is not explicitly configured (defaults to 25% of RAM)
- LangGraph batch generation and n8n ingestion workflows run concurrently without scheduling coordination
- `docker stats` shows any service consistently above 80% of available RAM during normal operation

**Phase to address:**
Infrastructure phase (Docker Compose configuration) — memory budgets and swap must be configured before the LangGraph service is added to the stack; do not defer to "fix if it breaks."

---

### Pitfall 13: JSON Structured Output Schema Compliance Does Not Prevent Financial Hallucination

**What goes wrong:**
Developers use Gemini's `responseMimeType: "application/json"` with a strict `responseSchema` to enforce structured output. The pipeline validates JSON schema compliance and assumes schema compliance equals factual accuracy. In reality, Gemini can produce a perfectly valid JSON object (`{"pe_ratio": 18.5, "source": "company fundamentals"}`) where `18.5` is hallucinated and `"company fundamentals"` is a generic string that maps to no specific record. Schema compliance rate approaches 100% with grammar-constrained generation; hallucination rate on financial numeric fields remains 10-20%. The LangGraph grounding check node never runs because the JSON schema passed validation.

**Why it happens:**
JSON schema validation catches structural errors, not semantic ones. LLMs generate schema-compliant JSON by filling in required fields — including numeric fields — with plausible values whether or not those values are grounded in retrieved context. The `source` field in structured output is only as reliable as the source citation enforcement built into the prompt.

**How to avoid:**
- JSON schema validation is necessary but not sufficient — add a semantic grounding check as a separate LangGraph node after report generation
- The grounding check node receives both the generated report JSON and the complete retrieved context; it verifies each numeric value in the report appears verbatim (or within rounding tolerance) in the retrieved context
- Use explicit source citation IDs in the schema (e.g., `"pe_ratio_source_id": "pg:fundamentals:VIC:row_id_42"`) not free-text source descriptions — validate that the source ID exists in the database before the report is accepted
- As a December 2025 Gemini bug: JSON mode may only activate when Function Calling is enabled in some configurations — test structured output behavior explicitly with the target Gemini model version before building the pipeline
- Never use `json_mode` (which suggests JSON formatting) when you need schema validation — use `responseSchema` with an explicit Pydantic or JSON Schema object

**Warning signs:**
- The pipeline has a JSON schema validation step but no semantic grounding check
- Source citations in structured output are free-text strings (`"source": "company data"`) not database record IDs
- Numeric values in reports are never cross-checked against the retrieved context that was passed to the LLM
- Testing only verifies JSON structure validity, not numeric accuracy

**Phase to address:**
AI reasoning pipeline design phase — grounding enforcement must be built in before the first report is generated; JSON schema validation alone is not an acceptable substitute.

---

### Pitfall 14: Entry Quality Score Becomes an Implicit Buy/Sell Signal

**What goes wrong:**
The AI-derived entry quality assessment — which combines macro regime, valuation, and price structure — is presented as a score or tier that users interpret as a buy/sell signal: "Favorable entry conditions" becomes "buy now." The platform crosses into unlicensed investment advice territory. Users anchor on the composite assessment rather than the underlying reasoning, losing the explainability benefit that the multi-step chain was designed to produce.

**Why it happens:**
Legible assessments are desirable. Users want an answer. The platform generates one. Without deliberate design constraints on language and framing, the score becomes the product rather than a summary of structured reasoning.

**How to avoid:**
- Frame entry quality as a qualitative tier with narrative explanation, never a numeric score: "Favorable / Neutral / Cautious / Avoid" with the reasoning decomposition that produced it
- Every report section must show which of the three layers (macro, valuation, structure) drove the assessment — never collapse to a composite label without the decomposition
- Report copy must use hedging language consistently: "suggests," "indicates conditions consistent with," "historically associated with" — never "buy," "sell," "entry point confirmed"
- Add a mandatory disclaimer to every report that is substantive, not boilerplate: explain this is macro-fundamental context, not a personal recommendation
- Add a validation check in the report generation node: scan the output text for prohibited words ("buy," "sell," "confirmed," "guaranteed") and fail if found

**Warning signs:**
- Report copy contains "buy," "sell," "entry confirmed," or "target price"
- A single composite label is the headline element of the report with no decomposition visible above the fold
- Users in testing interpret the entry quality tier as a trading signal without reading the underlying reasoning

**Phase to address:**
Report design phase — entry quality semantics and prohibited language must be decided before implementation begins; add automated text scanning to the report validation node.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Prompts as hardcoded strings in Python | Faster early iteration | Cannot version, test, or compare; a single prompt change breaks reports unpredictably; no diff history for prompt evolution | Never — store prompts in versioned config files from day one |
| Single LangGraph chain for all assets (stocks + gold) | Less code initially | Gold and VN stocks have fundamentally different data shapes and analogue histories; a unified chain produces worse analysis for both | Never — design separate reasoning paths per asset class |
| Skip staleness check in retrieval nodes | Simpler retrieval code | LangGraph reads stale data silently; users receive outdated analysis without warning | Never — freshness check is one line of code per node |
| InMemorySaver as LangGraph checkpointer | No PostgreSQL dependency | State lost on service restart; no fault tolerance; no time-travel debugging | Acceptable only during local development, never in production |
| Use LLM to compute structure markers (MAs, drawdown) | No pre-computation needed | Slower, more expensive, less reproducible; violates explicit architectural constraint in PROJECT.md | Never — pre-compute in n8n per project constraints |
| Free-text source citations in structured output | Simpler schema design | Cannot programmatically verify grounding; hallucinated sources look identical to real ones | Never — use database record IDs as citation keys |
| Skip per-container memory limits in Docker Compose | Less upfront configuration | Any service can consume all available RAM; OOM killer terminates random services including databases | Never — set limits before adding the LangGraph service |
| Text-to-Cypher for all Neo4j retrieval without templates | Flexible queries without pre-writing Cypher | Generated Cypher is frequently wrong on domain-specific schemas; invalid queries execute against production database | Acceptable only for exploratory development, never for production retrieval paths |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LlamaIndex + externally-created Neo4j graph | Use `VectorContextRetriever` or `LLMSynonymRetriever` expecting they work on any Neo4j graph | Only `TextToCypherRetriever` and `CypherTemplateRetriever` work on graphs not created by LlamaIndex; accept this constraint from day one |
| LangGraph + PostgreSQL checkpointer | Use the same PostgreSQL database as n8n and application tables | Create a dedicated `langgraph_checkpoints` PostgreSQL database; checkpoint writes must not compete with n8n workflow data |
| Gemini API structured output | Use `json_mode` or `responseMimeType` alone expecting schema enforcement | Use `responseSchema` with explicit Pydantic model or JSON Schema; add semantic grounding check as a separate validation step |
| Gemini API rate limits | Assume free tier is sufficient for 30-stock batch generation after December 2025 | Use Tier 1 paid (150 RPM minimum); implement exponential backoff with jitter; configure inter-request delay |
| Gemini context caching | Cache frequently-changing content (current price data) | Cache only stable content: system prompt, macro framework documents, terminology glossary; never cache data that changes weekly |
| Qdrant + LlamaIndex | Embed documents once and never re-embed | Chunk strategy changes require full re-embedding; design the ingestion pipeline to support `--reindex` flag; version Qdrant collections |
| Neo4j Text-to-Cypher | Allow LLM-generated Cypher to execute without validation | Validate generated Cypher against schema before execution; use a read-only Neo4j user for all LlamaIndex retrieval |
| Vietnamese bilingual generation | Send Gemini a bilingual report request without a terminology glossary | Include relevant term dictionary entries in the system prompt; use enum types for high-stakes labels to constrain Vietnamese vocabulary |
| Docker Compose + LangGraph service | Add LangGraph service to the existing stack without memory limits | Set `mem_limit` on every service before adding LangGraph; configure swap on VPS host; schedule batch jobs during off-peak hours |
| LangGraph + n8n | Have n8n call LangGraph synchronously and wait for inference completion | Use async trigger pattern: n8n fires FastAPI endpoint; LangGraph runs async; n8n polls for completion via a run status endpoint |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| LangGraph state contains raw retrieved documents | Pipeline OOM on VPS during batch generation; Gemini context overflow errors | Pass documents as function arguments to nodes; keep only summaries/IDs in state | First batch run with full 20-stock VN30 list |
| Neo4j schema introspection on large graph | LlamaIndex Text-to-Cypher hangs for minutes before executing | Pre-provide schema string to LlamaIndex; disable auto-introspection; use explicit schema documentation in prompts | Once graph exceeds ~10K nodes |
| Gemini calls without context caching for repeated static content | API costs 10x higher than necessary; token budget consumed by repeated system prompt | Enable implicit caching; use explicit caching for system prompts exceeding 1,024 tokens | From the first production batch run |
| Synchronous Gemini API calls in a batch loop | Batch of 30 stocks takes 30× single-stock time; rate limits hit mid-batch | Implement async Gemini calls; add configurable inter-request delay; process stocks sequentially with backoff | First batch run that hits RPM limits |
| Qdrant dense-only retrieval for financial documents | Tables, numeric data, and ticker names retrieved inaccurately | Use hybrid search (dense + BM25 sparse) for financial documents | Any query that includes specific financial identifiers or numbers |
| Full OHLCV retrieval from PostgreSQL for every report | Report generation slow; LLM context bloated with raw data | Pre-compute structure markers during n8n ingestion; LangGraph reads computed columns only | Single-user with 20+ watchlist items |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Neo4j user used by LlamaIndex has write permissions | LLM-generated Cypher injection could modify graph data | Create a read-only Neo4j user for all LlamaIndex/LangGraph retrieval queries; write access only via FastAPI sidecar |
| Financial documents in Qdrant co-embedded with user-private content | Semantic search over public documents inadvertently returns user notes | Strict collection separation: one collection for public market documents, separate collection for user-specific content |
| LLM output passed to report generation without sanitization | Prompt injection via crafted financial documents changes report conclusions | Treat all retrieved documents as untrusted input; structured output schema constrains what the model can output; system prompt explicitly frames retrieved content as data to analyze, not instructions |
| Gemini API key stored in Docker Compose environment without spend limit | API key compromise allows unlimited spend with no alert | Store API keys in a secrets manager; set Gemini API spend alerts at $5/$10/$25 thresholds; rotate keys on a schedule |
| VPS PostgreSQL/Neo4j/Qdrant ports accessible on public interfaces | Data exfiltration if VPS network is compromised | Bind all storage services to localhost only; use SSH tunnels for admin access |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Entry quality presented as composite label without decomposition | Users anchor on "Favorable" without reading macro/valuation/structure sub-assessments | Show three sub-assessments as primary display; composite label is a summary, not the headline |
| Vietnamese reports use different translations for the same term | Retail investors lose trust; reports feel machine-translated | Build and enforce Vietnamese term dictionary; automated term-consistency check after generation |
| Report shows "N/A" for missing data without explanation | Users assume platform is broken | Distinguish between "data not available" (WGC lag), "source temporarily unavailable" (vnstock outage), and "this stock lacks this data" — each gets a specific message |
| Mixed-signal macro regime displays only the top label | Users miss that regime classification has low confidence | Surface confidence score alongside regime label; "Mixed Signal Environment" is a first-class report type |
| Bilingual reports with inconsistent financial terminology | Vietnamese-language sections appear untrustworthy | Maintain approved glossary; validate all generated text against glossary before report acceptance |
| Conflicting signals (strong macro, weak structure) suppressed | User receives misleading "Favorable" assessment hiding structural risk | Conflicting signal reports are a required output type; "strong thesis, weak structure" must be named explicitly |

---

## "Looks Done But Isn't" Checklist

- [ ] **LangGraph state schema:** Often missing size constraints — verify every `TypedDict` field has a fixed type with no unbounded lists; run the pipeline with 20 stocks and measure peak state size
- [ ] **Neo4j retrieval compatibility:** Often assumes all LlamaIndex retrievers work — verify `VectorContextRetriever` is not used against the externally-created Stratum graph; only `CypherTemplateRetriever` and `TextToCypherRetriever` are configured
- [ ] **Gemini rate limit handling:** Often only has `try/except` on API calls — verify exponential backoff with jitter is implemented; verify inter-request delay is configurable; verify batch resumes from partial completion after 429 error
- [ ] **Vietnamese term consistency:** Often "works" in demo with manually-reviewed output — verify automated term-consistency check runs after every report generation and catches inconsistent translations
- [ ] **Grounding check node:** Often present but only validates JSON schema, not semantic accuracy — verify the grounding check node cross-references each numeric value against the specific database record or document that sourced it
- [ ] **Docker memory limits:** Often undiscovered until VPS crashes — verify `mem_limit` is set on every Docker Compose service; verify swap is configured on VPS host; run `docker stats` during a 30-stock batch and confirm no service exceeds its budget
- [ ] **LangGraph checkpointer isolation:** Often uses main application database — verify LangGraph checkpoints write to a dedicated `langgraph_checkpoints` database, not the same database as n8n or application data
- [ ] **Macro regime confidence:** Often generates a single label — verify the regime classification node output includes a probability distribution; verify mixed-signal inputs produce "Mixed Signal" reports
- [ ] **Neo4j RESEMBLES relationship properties:** Often bare edges with no weights — verify every `RESEMBLES` relationship has `similarity_score`, `dimensions_matched`, `period_start`, and `period_end` properties before any reasoning node reads analogue data

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LangGraph state OOM causes VPS crash | MEDIUM | Restart all Docker services; add `mem_limit` to Docker Compose; reduce state object size; add swap to VPS host |
| LLM hallucinated numbers discovered in published reports | HIGH | Identify all reports in the affected date range; add grounding check node; re-run affected reports with grounding enforcement; version-stamp reports with pipeline revision |
| Neo4j schema incompatible with retrieval patterns | HIGH | Schema migration requires full graph rebuild; stop all ingestion jobs; redesign schema with retrieval queries; re-load historical data; validate retrieval before resuming |
| Gemini API cost spike from uncached large contexts | LOW | Enable context caching immediately; audit which documents are re-sent vs. cached; set API spend alerts |
| Text-to-Cypher generates invalid Cypher in production | MEDIUM | Switch affected retrieval paths to `CypherTemplateRetriever`; add Cypher validation before execution; add read-only Neo4j user constraint |
| Vietnamese term inconsistency discovered across reports | MEDIUM | Build glossary retrospectively; add term-consistency automation; re-generate affected reports with glossary in system prompt |
| LangGraph checkpoints bloating main application database | MEDIUM | Migrate checkpoint table to dedicated database; add cleanup job for old checkpoints; resize PostgreSQL allocation |
| Gemini JSON mode fails to produce structured output (Dec 2025 bug) | LOW | Switch to `responseSchema` with explicit schema object; test that structured output activates correctly for the specific model version in use |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LangGraph state bloat / VPS OOM | Infrastructure (Docker Compose) + AI reasoning pipeline design | Run 20-stock batch; measure peak state size and VPS memory; no OOM events |
| LlamaIndex incompatibility with externally-created Neo4j graph | Retrieval layer phase | Only `CypherTemplateRetriever` and `TextToCypherRetriever` configured; retrieval returns correct results against v1.0 graph |
| LangGraph reducer misuse causes silent state corruption | AI reasoning pipeline design | Unit tests assert state shape after every node; parallel branches verified with mixed-input tests |
| Gemini free tier rate limits (post-December 2025) | AI reasoning pipeline design | Exponential backoff implemented; 30-stock batch completes without 429 failures; spend alerts configured |
| Vietnamese financial terminology inconsistency | Bilingual report generation phase | Automated term-consistency check passes on 10-report sample; no term has multiple Vietnamese translations within a batch |
| LangGraph checkpointer database contention | Infrastructure (Docker Compose) | LangGraph checkpoints in dedicated database; no PostgreSQL latency increase during batch generation |
| LLM hallucinating financial numbers | AI reasoning pipeline design + grounding check node | Every numeric value in test reports traced to a specific database record or retrieved document |
| Stale data presented as current | Retrieval layer phase | Report generated 48h after stopping ingestion shows explicit DATA WARNING sections, not silent use of stale data |
| Macro regime overconfident single label | Knowledge graph schema + AI reasoning pipeline | Mixed-signal test inputs produce probability distributions and "Mixed Signal" reports |
| Neo4j schema mismatch with retrieval patterns | Knowledge graph schema phase (before data loading) | Cypher retrieval queries return correctly-structured analogues with all required relationship properties |
| Text-to-Cypher invalid Cypher on domain schema | Retrieval layer phase | All production retrieval paths use `CypherTemplateRetriever`; Text-to-Cypher validated before execution |
| JSON schema compliance without semantic grounding | AI reasoning pipeline design | Grounding check node rejects reports where numeric values are not traceable to source records |
| Entry quality score as buy/sell signal | Report design phase (pre-implementation) | Automated text scan finds no prohibited words; three sub-assessments visible before composite label |
| VPS memory exhaustion under concurrent load | Infrastructure (Docker Compose) | `mem_limit` set on every service; swap configured; 30-stock batch completes without OOM events |

---

## Sources

- [LangGraph State Machines: Managing Complex Agent Task Flows in Production](https://dev.to/jamesli/langgraph-state-machines-managing-complex-agent-task-flows-in-production-36f4) — MEDIUM confidence
- [Mastering LangGraph Checkpointing: Best Practices for 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025) — MEDIUM confidence
- [LangGraph Persistence Guide: Checkpointers and State](https://fast.io/resources/langgraph-persistence/) — MEDIUM confidence
- [`langgraph dev` Ignores Checkpointer Configuration — GitHub Issue #5790](https://github.com/langchain-ai/langgraph/issues/5790) — HIGH confidence (official issue tracker)
- [LangGraph Persistence — Official LangChain Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — HIGH confidence
- [Neo4j Property Graph Index — LlamaIndex Official Docs](https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/) — HIGH confidence
- [LlamaIndex Neo4j Graph Integration](https://markaicode.com/llamaindex-neo4j-graph-integration/) — MEDIUM confidence
- [Building Knowledge Graph Agents With LlamaIndex Workflows](https://neo4j.com/blog/knowledge-graph/knowledge-graph-agents-llamaindex/) — HIGH confidence (official Neo4j blog)
- [Gemini API Rate Limits — Official Google AI Docs](https://ai.google.dev/gemini-api/docs/rate-limits) — HIGH confidence
- [Gemini API Pricing — Official Google AI Docs](https://ai.google.dev/gemini-api/docs/pricing) — HIGH confidence
- [Gemini API Context Caching — Official Google AI Docs](https://ai.google.dev/gemini-api/docs/caching) — HIGH confidence
- [Gemini Structured Output JSON Mode — Community Report Dec 2025](https://discuss.ai.google.dev/t/gemini-responds-with-structured-json-like-output-only-when-function-calling-is-enabled/112993) — MEDIUM confidence (community forum)
- [Gemini API Pricing and Quotas 2026](https://www.aifreeapi.com/en/posts/gemini-api-pricing-and-quotas) — MEDIUM confidence
- [FAITH: Assessing Intrinsic Tabular Hallucinations in Finance](https://arxiv.org/html/2508.05201) — HIGH confidence (peer-reviewed)
- [LLM Structured Output Benchmarks are Riddled with Mistakes](https://cleanlab.ai/blog/structured-output-benchmark/) — MEDIUM confidence
- [Reliable Structured Output from Local LLMs: JSON Extraction Without Hallucination](https://markaicode.com/ollama-structured-output-pipeline/) — MEDIUM confidence
- [Challenges When Developing NLP for Vietnamese](https://www.1stopasia.com/blog/challenges-developing-nlp-for-vietnamese/) — MEDIUM confidence
- [Best Open Source LLM for Vietnamese in 2026](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Vietnamese) — LOW confidence (single source)
- [Docker CPU and Memory Limits in Docker Compose](https://docker.recipes/docs/resource-limits) — HIGH confidence (official documentation)
- [Mitigating LLM Hallucination in the Banking Domain](https://dspace.mit.edu/bitstream/handle/1721.1/162944/sert-dsert-meng-eecs-2025-thesis.pdf) — HIGH confidence (MIT thesis)
- [RAG in 2025: Enterprise Guide](https://datanucleus.dev/rag-and-agentic-ai/what-is-rag-enterprise-guide-2025) — MEDIUM confidence
- [Welcome to the Dark Side: Neo4j Worst Practices](https://neo4j.com/blog/cypher-and-gql/dark-side-neo4j-worst-practices/) — HIGH confidence (official Neo4j blog)
- [Memory Leak in LangGraph — GitHub Issue #3898](https://github.com/langchain-ai/langgraph/issues/3898) — HIGH confidence (official issue tracker)
- [LLM01:2025 Prompt Injection — OWASP Gen AI Security Project](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — HIGH confidence (official OWASP)

---
*Pitfalls research for: Adding LLM-powered analytical reasoning layer to Stratum financial data platform (v2.0 milestone)*
*Researched: 2026-03-09*
