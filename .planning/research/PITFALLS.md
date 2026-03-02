# Pitfalls Research

**Domain:** AI-powered investment advisor platform — macro-fundamental analysis, Vietnamese retail investors
**Researched:** 2026-03-03
**Confidence:** MEDIUM (cross-verified across multiple sources; vnstock-specific data is LOW due to limited public post-mortems)

---

## Critical Pitfalls

### Pitfall 1: LLM Hallucinating Financial Numbers

**What goes wrong:**
The LLM fabricates specific financial figures — P/E ratios, earnings growth rates, price levels, index values — that sound authoritative but are drawn from training data, not the retrieved context. This is especially dangerous in multi-step reasoning chains (LangGraph) where a hallucinated number in step 2 becomes a "verified" input to step 3. Financial LLM hallucination rates average 2–14% depending on model and task; even a 2% rate on numbers an investor acts on is catastrophic.

**Why it happens:**
LLMs are trained to complete statistically likely sequences. When a financial number is not present in the retrieved context, the model fills in from training memory rather than saying "I don't have this data." The problem amplifies in agentic pipelines because each node trusts the output of the previous node without re-grounding against source data.

**How to avoid:**
- Every numerical claim in the final report must be traceable to a specific retrieved document, PostgreSQL record, or Neo4j node — not LLM output
- LangGraph nodes that produce numbers must cite their source as part of structured output (not natural language)
- Use Gemini structured output (JSON schema) so the pipeline fails noisily if a number cannot be grounded
- Add a "grounding check" node at the end of the reasoning chain that verifies all numbers in the narrative appear in the context passed to the LLM
- Never ask the LLM to recall historical figures from memory; always retrieve first, then ask the LLM to interpret

**Warning signs:**
- Report contains a specific number (PE ratio, EPS, price) that is not in any retrieved document
- LLM output contains hedge phrases like "approximately" or "historically around" on specific data points — this is the LLM drawing from training rather than retrieved context
- Numbers in the report differ slightly from the database values (model "rounded" a retrieved number in a way that changed its meaning)

**Phase to address:**
Data ingestion phase (grounding pipeline) and AI reasoning pipeline phase — both must treat this as a first-class constraint from day one, not a polish step.

---

### Pitfall 2: Stale Data Presented as Current

**What goes wrong:**
A monthly report is generated using data that was last refreshed weeks ago — either because an n8n scheduled job silently failed, a data source was rate-limited, or a free-tier API temporarily went down. The report uses stale OHLCV prices, old fundamental data, or lag-delayed macro indicators (World Gold Council data has 1–2 month publication lag by design) without flagging which values are current versus stale.

**Why it happens:**
n8n scheduled jobs fail silently without alerts unless explicitly configured. Free-tier APIs (vnstock, FRED, World Gold Council) have no SLA and can return errors or empty responses. When the downstream LangGraph pipeline runs, it reads whatever is in PostgreSQL — it has no way to know if that data is fresh unless staleness is explicitly encoded.

**How to avoid:**
- Every ingested data row must have an `ingested_at` timestamp AND a `data_as_of` field (the actual date the source published this data)
- LangGraph reads `data_as_of` before reasoning; if `data_as_of` exceeds a configurable freshness threshold, the node emits a warning that appears in the report
- n8n workflows must have error handlers that write a failure record to a `pipeline_run_log` table in PostgreSQL
- Report generation checks `pipeline_run_log` before proceeding; stale ingestion jobs cause the report to include explicit "DATA WARNING: X not refreshed since [date]" sections
- World Gold Council lag must be modeled as a property in Neo4j (source node has `typical_lag_days: 45`) so the reasoning pipeline knows not to treat this as "current" data

**Warning signs:**
- No `pipeline_run_log` table exists — jobs cannot report their own success/failure
- Reports contain the phrase "as of [date]" without that date being retrieved from the data layer
- An n8n run shows 0 new rows ingested but no error was raised

**Phase to address:**
Data ingestion pipeline phase — staleness tracking is infrastructure, not an afterthought.

---

### Pitfall 3: Macro Regime Misclassification as Overconfident Single Label

**What goes wrong:**
The platform forces every macro environment into a single label ("stagflation," "recovery," "expansion") even when the data produces a mixed signal — e.g., inflation falling but growth also decelerating, or Vietnam-specific conditions diverging from global regime. The AI presents this label confidently, and the downstream reasoning chain treats it as ground truth for all subsequent analysis. Users see "Current regime: Stagflation" with no indication this is a probabilistic classification with 55% confidence.

**Why it happens:**
Classification problems reward clean categories. Neo4j analogues are stored as discrete regime nodes. LLM prompts are written to produce a label. The system is designed around the happy path of a clean regime, not the common case of mixed signals.

**How to avoid:**
- Store regime classification as a distribution, not a point estimate: `{stagflation: 0.55, slowdown: 0.30, expansion: 0.15}` in the Neo4j regime node
- Require LangGraph regime classification node to produce a confidence score alongside the label
- If top regime confidence < 70%, the report explicitly surfaces "Mixed Signal Environment" and the two most likely analogues, not just the winner
- The PROJECT.md requirement for "Mixed-signal macro regime representation" must be implemented as a first-class output, not a fallback edge case
- Historical analogues in Neo4j must include "analogue_similarity_score" on the relationship so weak matches are distinguishable from strong matches

**Warning signs:**
- Neo4j regime relationships have no weight or confidence property
- The LangGraph regime node always outputs a single string, never a distribution
- No test cases for mixed-signal inputs exist in the test suite
- Report language contains "The current regime is X" without any confidence qualification

**Phase to address:**
AI reasoning pipeline phase (regime classification node design) and knowledge graph schema phase (regime relationships must carry confidence weights from inception).

---

### Pitfall 4: Entry Quality Score as a Single Authoritative Number

**What goes wrong:**
The "entry quality score" — which combines macro regime, valuation, and price structure — gets treated by users (and the report itself) as a precise, actionable signal: "Entry Score: 7.2 — Buy." Users anchor on the number rather than the reasoning behind it, and the platform effectively becomes an implicit buy/sell recommendation engine. This creates user harm (false confidence), regulatory exposure (unlicensed investment advice), and technical fragility (a small prompt change shifts scores unpredictably).

**Why it happens:**
Scores are legible. Users want a number. The platform is built to generate one. Without deliberate design constraints, the score becomes the product rather than a summary of structured reasoning.

**How to avoid:**
- Frame entry quality as a qualitative tier with narrative explanation, not a numeric score: "Favorable / Neutral / Cautious / Avoid" with the reasoning that produced it
- Every report section must show which of the three layers (macro, valuation, structure) drove the assessment — never collapse to a single number without the decomposition
- Report copy must use hedging language consistently: "suggests," "indicates conditions consistent with," "historically associated with" — never "buy," "sell," "entry point confirmed"
- Add a mandatory disclaimer section to every report that is substantive, not boilerplate: explain that this is macro-fundamental context, not a personal recommendation
- If numeric scoring is retained, require at minimum three sub-scores (one per layer) presented alongside the composite, so the composite cannot be read in isolation

**Warning signs:**
- Report copy contains the words "buy," "sell," "entry confirmed," or "target price"
- Users sharing reports interpret the score as a trading signal
- A single prompt controls the score and no sub-score decomposition exists

**Phase to address:**
Report design and AI reasoning pipeline phases — score semantics and report framing must be decided before implementation begins.

---

### Pitfall 5: vnstock as a Silent Single Point of Failure

**What goes wrong:**
vnstock is a community-maintained open-source library that wraps unofficial APIs from Vietnamese brokers (TCBS, VCI, SSI). These APIs are undocumented, not versioned, and have broken without notice when brokers deploy updates (the KRX system migration in May 2025 broke intraday data for VCI and MAS). When vnstock breaks, the entire Vietnamese stock data ingestion pipeline fails silently or returns empty results that pass validation.

**Why it happens:**
Free, open-source data wrappers for emerging markets are inherently fragile — the brokers do not consider third-party tools when they deploy backend changes. The project depends on a single library with no fallback.

**How to avoid:**
- Wrap all vnstock calls in explicit error handling that distinguishes between "API returned error," "API returned empty," and "API returned data but row count is anomalously low"
- Implement a "data quality check" step in n8n after every ingestion run: compare today's row count to 4-week moving average; alert if deviation > 50%
- Design the PostgreSQL schema so ingestion failures for individual stocks are row-level (one stock fails, others succeed) not job-level
- Pin the vnstock version in requirements.txt; do not auto-upgrade — upgrade is a deliberate decision after testing
- Monitor the vnstock GitHub repository for breaking change notices; subscribe to releases
- Accept that Vietnamese stock data may be unavailable for 1–3 days following broker infrastructure changes; document this in the platform's "data freshness" section

**Warning signs:**
- vnstock version is unpinned (`vnstock>=3.0.0` instead of `vnstock==3.2.0`)
- Ingestion job returns 0 rows with exit code 0 (success reported on empty result)
- No anomaly detection on row count after ingestion

**Phase to address:**
Data ingestion pipeline phase — defensive error handling and data quality checks are non-negotiable before connecting to reasoning pipeline.

---

### Pitfall 6: Neo4j Graph Schema Designed for the First Use Case, Not the Analogue Retrieval Use Case

**What goes wrong:**
The Neo4j schema is designed during early implementation with macro regime nodes connected to current conditions. Later, when historical analogue retrieval is added ("this environment resembles 2015-2016 because X"), the schema requires a rewrite because regime similarity relationships were not designed to carry confidence scores, date ranges, or multi-dimensional similarity vectors. LlamaIndex Neo4j retrieval queries break when the schema changes mid-project.

**Why it happens:**
Graph databases are schema-flexible, which tempts early shortcuts. Nodes and relationships are added without thinking through the query patterns that LlamaIndex will use to retrieve analogues. Relationship properties are added as afterthoughts rather than first-class design.

**How to avoid:**
- Design the full Neo4j schema before writing any code — including all relationship types (`RESEMBLES`, `PRECEDES`, `CORRELATES_WITH`) and their required properties (confidence, similarity_score, date_range, source)
- Write the LlamaIndex retrieval queries first (what Cypher will you run to find historical analogues?) and work backward to the schema that supports them
- Use `RESEMBLES` relationships with properties: `similarity_score: float`, `dimensions: list[str]` (which macro indicators drove the similarity), `period_start: date`, `period_end: date`
- Never store blob data in Neo4j — store it in PostgreSQL and use Neo4j nodes to hold the reference key
- Test with 5 years of historical analogues before building the reasoning pipeline, not after

**Warning signs:**
- Neo4j relationship nodes have no properties (bare `RESEMBLES` edges with no weights)
- LlamaIndex queries against Neo4j are using `MATCH (n:Regime)` without traversing relationships
- Schema was designed in one session and has never been reviewed against actual retrieval patterns

**Phase to address:**
Knowledge graph design phase (must precede both ingestion and reasoning pipeline phases).

---

### Pitfall 7: LangGraph State Growing Unboundedly Across Reasoning Steps

**What goes wrong:**
Each LangGraph node appends to the shared state — retrieved documents, intermediate analysis, structured outputs. By the time the report generation node runs, the state object contains tens of thousands of tokens of accumulated context. This causes: (1) context window overflow when passed to Gemini, (2) memory spikes on the VPS, (3) slow inference because the model processes irrelevant context from early pipeline steps.

**Why it happens:**
LangGraph's immutable state versioning creates a new state object at each step. Without explicit state pruning, all intermediate data accumulates. Early development doesn't hit this problem because test data is small; production runs with full document retrieval expose it.

**How to avoid:**
- Define explicit state pruning at each node: nodes output only what the next node needs, and previous-step raw context is dropped
- Use TypedDict with strict field definitions — no catch-all `dict` fields that accumulate arbitrary data
- Keep retrieved documents in a separate context object that is passed by reference, not embedded in the LangGraph state
- Set a hard token budget for each node's input: if the assembled context exceeds 80% of the Gemini context window, the pipeline raises an error before inference (not after)
- Test the full pipeline with realistic data volumes (not toy examples) during the reasoning pipeline phase

**Warning signs:**
- LangGraph state TypedDict has a field like `context: dict` or `documents: list[Any]`
- No token count is checked before calling Gemini
- Pipeline passes on toy data but times out or errors on real data

**Phase to address:**
AI reasoning pipeline phase — state schema design must enforce size constraints from the first implementation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Prompts as hardcoded strings in Python | Faster iteration early | Cannot version, test, or A/B compare; a single prompt change breaks reports unpredictably | Never — store prompts in config files from day one |
| Single LangGraph chain for all assets (stocks + gold) | Less code initially | Gold and Vietnamese stocks have fundamentally different data shapes and analogue histories; a unified chain produces worse analysis for both | Never — design separate reasoning paths per asset class |
| Skip staleness timestamps on ingested rows | Simpler schema early | Cannot detect stale data at report time; users receive outdated analysis without warning | Never — add `data_as_of` and `ingested_at` from the first migration |
| Use LLM to compute structure markers (MAs, drawdown) | No pre-computation needed | Slower, more expensive, less reproducible; contradicts the explicit architectural constraint | Never — pre-compute in n8n per PROJECT.md constraints |
| Pin vnstock to "latest" | Always use newest features | Breaking changes silently corrupt ingestion; version pinning is free | Never — always pin to a tested version |
| Skip Qdrant payload filtering (retrieve all, filter in Python) | Simpler retrieval code | Retrieval becomes slower and less precise as document count grows; irrelevant documents pollute LLM context | Acceptable only in prototype phase with < 100 documents |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| vnstock | Call directly from LangGraph reasoning pipeline | All vnstock calls go through n8n ingestion only; LangGraph reads pre-computed data from PostgreSQL — this is an explicit architectural constraint |
| FRED API | Assume all series have consistent update cadences | FRED series have wildly different update frequencies (daily, weekly, monthly, quarterly, annual); model each series' `expected_update_frequency` in the ingestion config |
| World Gold Council data | Treat publication date as data date | WGC publishes with 1–2 month lag; `data_as_of` must reflect the period the data covers, not when WGC published it — otherwise the pipeline treats 6-week-old gold flows as current |
| Gemini API | Pass all reasoning context in a single prompt | Use context caching for static documents (Fed minutes, macro reports) to reduce cost 90%; only dynamic data goes in the live prompt |
| Neo4j + LlamaIndex | Let LlamaIndex auto-generate Cypher queries | Auto-generated Cypher often produces full graph scans; write specific Cypher query templates for each retrieval pattern and register them as LlamaIndex query tools |
| Qdrant | Embed documents once and never re-embed | Chunk strategy changes require full re-embedding; design the ingestion pipeline to support re-embedding with a `--reindex` flag from the start |
| Supabase auth | Use Supabase user UUIDs only in the auth layer | Mirror user UUIDs into PostgreSQL and Neo4j user nodes at account creation; downstream analysis pipelines reference PostgreSQL user records, not Supabase directly |
| n8n + PostgreSQL | Use n8n's built-in JSON output for all data | n8n JSON can lose type precision (dates as strings, floats as strings); use typed PostgreSQL inserts with explicit column types, not `INSERT INTO ... SELECT * FROM JSON` patterns |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Retrieving full historical OHLCV from PostgreSQL for every report | Report generation takes minutes; LLM context bloated with raw data | Pre-compute all structure markers (MAs, drawdown from ATH) during ingestion; LangGraph reads computed columns, not raw OHLCV | Single user with 20+ watchlist items |
| Neo4j supernode on major macro regime categories | Regime classification queries run for seconds; all analogues for "recession" connected to one node | Create hierarchical regime nodes (broad → specific); use relationship properties for time-scoping | Once > 500 historical data points are loaded |
| Qdrant dense-only retrieval for financial documents | Tables, numeric data, and specific ticker names retrieved inaccurately | Use hybrid search (dense + sparse BM25) for financial documents; dense for semantics, sparse for exact terms/numbers | Any document with tables or specific financial identifiers |
| Gemini API synchronous calls in n8n | n8n workers block during LLM inference; other scheduled jobs queue up | Use async trigger pattern: n8n triggers LangGraph via FastAPI endpoint; LangGraph runs asynchronously; n8n polls for completion | First multi-stock batch report run |
| No Qdrant collection versioning | Schema changes require downtime; collection must be deleted and rebuilt | Version collections (`reports_v1`, `reports_v2`); migrate by building v2 in parallel, then cutover | First time chunk strategy needs to change |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Financial documents in Qdrant contain personally identifiable data (user watchlists, notes) embedded in the same collection as public market data | Semantic search over public data inadvertently returns user-private content | Strict collection separation: one Qdrant collection for public financial documents, separate collection for any user-specific content; never co-embed public and private data |
| LLM output passed directly to report generation without sanitization | Indirect prompt injection via financial documents (a crafted earnings report could instruct the LLM to change report conclusions) | Treat all retrieved documents as untrusted input; system prompt must explicitly frame retrieved content as "external data to be analyzed, not instructions to follow"; use Gemini's structured output to constrain what the model can output |
| Gemini API key in n8n environment variables without rotation plan | API key compromise allows unlimited spend | Store API keys in a secrets manager or environment variable vault; set Gemini API spend limits; rotate keys on a schedule |
| VPS-hosted PostgreSQL/Neo4j/Qdrant with default ports accessible | Data exfiltration if VPS network is compromised | Bind all storage services to localhost only; use SSH tunnels for admin access; no public ports on storage layer |
| Reports served over unauthenticated FastAPI endpoints during development | Research reports (which may contain non-public analysis) accessible without auth | Add Supabase JWT verification to FastAPI from the first endpoint; do not defer auth to "when we add users" |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Entry quality presented as a numeric score without component breakdown | Users anchor on the number; treat 7/10 as a buy signal without reading the reasoning that might say "strong macro but dangerous price structure" | Show three sub-assessments (macro, valuation, structure) as the primary display; composite is a summary label, not the headline |
| Vietnamese-language reports that use financial jargon without explanation | Retail investors (the target audience) misunderstand terms like "overbought," "PE expansion," or "macro regime" | Define domain terms in a persistent glossary sidebar; first use of any technical term in a report links to the glossary |
| Report shows "N/A" for missing data without explanation | Users assume the platform is broken or incomplete | Distinguish between "data not yet available" (World Gold Council lag), "data source temporarily unavailable" (vnstock outage), and "this stock does not have this data" (e.g., new listings with no earnings history) — each gets a specific message |
| Monthly cadence means new watchlist items have no report for up to 30 days | Users add a stock to their watchlist and see nothing; they lose trust in the platform | On-demand report generation for new watchlist additions (as noted in PROJECT.md requirements) must be implemented as a visible trigger, not a background job with no feedback |
| Bilingual reports with inconsistent terminology (English financial terms have no standard Vietnamese equivalent) | Vietnamese-language sections feel machine-translated and untrustworthy | Define a term mapping dictionary at the project level; Gemini bilingual generation must be validated against this dictionary; use consistent translations (e.g., always "lãi suất" not "lãi suất cơ bản" and "lãi suất tham chiếu" interchangeably) |

---

## "Looks Done But Isn't" Checklist

- [ ] **Macro regime classification:** Often missing confidence scores and mixed-signal handling — verify the output type is a distribution, not a string
- [ ] **Historical analogue retrieval:** Often returns the closest match by cosine similarity without checking if the match is actually meaningful — verify analogues have a minimum similarity threshold and that the report surfaces similarity score and the specific dimensions that matched
- [ ] **Entry quality score:** Often missing component breakdown — verify each report shows macro, valuation, and structure sub-assessments independently before the composite
- [ ] **Stale data handling:** Often "works in development" where data is always fresh — verify by running report generation 48 hours after intentionally stopping the ingestion job; report must flag stale data, not silently use it
- [ ] **Bilingual reports:** Vietnamese translation often degrades on financial tables and structured data — verify tables render correctly in both languages and financial terms are consistently translated
- [ ] **Conflicting signal output:** Reports for "strong thesis, weak structure" cases often suppress the conflict — verify the report explicitly names the conflict, not just the winning signal
- [ ] **World Gold Council lag:** Often implemented as "pull latest available" without encoding the 45-day publication lag — verify `data_as_of` for gold flow data reflects the actual coverage period, not the fetch date
- [ ] **Neo4j analogue confidence:** Often relationships are unweighted ("RESEMBLES" with no score) — verify every `RESEMBLES` relationship has `similarity_score`, `dimensions_matched`, and `period` properties

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LLM hallucinated numbers discovered in published reports | HIGH | Identify all reports in the affected date range; re-run with grounding enforcement; add a schema-level grounding check node to the pipeline before re-deploying |
| vnstock breaking change causes stale data for multiple days | MEDIUM | Fall back to last known-good data with explicit staleness flag in reports; pin vnstock to the last working version; monitor GitHub for a patch |
| Neo4j schema incompatible with analogue retrieval requirements | HIGH | Schema migration in Neo4j requires re-creating relationships; plan for a full graph rebuild; this is why schema must be correct before data is loaded |
| LangGraph state growth causing OOM on VPS | MEDIUM | Restart pipeline; add state pruning to the offending nodes; consider upgrading VPS RAM as short-term mitigation |
| Gemini API cost spike from uncached large contexts | LOW | Enable context caching immediately; audit which documents are being re-sent vs. cached; set API spend alerts |
| Report generated using wrong regime classification (misclassification discovered post-publication) | MEDIUM | Add confidence threshold check that blocks report generation if regime confidence < threshold; regenerate affected reports with corrected classification |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LLM hallucinating financial numbers | AI reasoning pipeline design | Every numeric claim in a test report is traceable to a specific database record or retrieved document |
| Stale data presented as current | Data ingestion pipeline | Running report generation 48h after stopping ingestion produces visible staleness warnings, not silent use of stale data |
| Macro regime misclassification as overconfident label | Knowledge graph schema + AI reasoning pipeline | Regime classification node outputs a probability distribution; mixed-signal test cases produce "Mixed Signal" reports, not forced single-label classification |
| Entry quality as authoritative number | Report design phase (pre-implementation) | No report contains the words "buy," "sell," or "confirmed entry"; all reports show three sub-assessments before any composite |
| vnstock as silent single point of failure | Data ingestion pipeline | Anomaly detection on row count catches empty-but-successful ingestion runs; version is pinned in requirements.txt |
| Neo4j schema mismatch with retrieval patterns | Knowledge graph schema phase (before ingestion) | LlamaIndex retrieval test queries return correctly-structured analogues with similarity scores and period metadata |
| LangGraph state growing unboundedly | AI reasoning pipeline design | Pipeline test with 20-stock batch does not exceed 80% of Gemini context window; state TypedDict has no unbounded list fields |
| Conflicting signals suppressed in reports | AI reasoning pipeline + report design | Test cases with explicitly conflicting signals (high macro confidence, low structure confidence) produce reports that name the conflict |

---

## Sources

- [6 Mistakes to Avoid When Using AI for Financial Advisors](https://aldeninvestmentgroup.com/blog/6-mistakes-to-avoid-when-using-ai-for-financial-advisors/) — MEDIUM confidence
- [Key Risks of AI in Financial Reporting and Consolidation](https://mondialsoftware.com/key-risks-of-ai-in-financial-reporting-and-consolidation/) — MEDIUM confidence
- [LLM Hallucinations: What Are the Implications for Financial Institutions? | BizTech Magazine](https://biztechmagazine.com/article/2025/08/llm-hallucinations-what-are-implications-financial-institutions) — MEDIUM confidence
- [Deficiency of Large Language Models in Finance: An Empirical Examination of Hallucination](https://arxiv.org/abs/2311.15548) — HIGH confidence (peer-reviewed)
- [Why your AI agent keeps hallucinating financial data (and how to fix it)](https://dev.to/valyuai/why-your-ai-agent-keeps-hallucinating-financial-data-and-how-to-fix-it-180d) — MEDIUM confidence
- [Welcome to the Dark Side: Neo4j Worst Practices](https://neo4j.com/blog/cypher-and-gql/dark-side-neo4j-worst-practices/) — HIGH confidence (official Neo4j blog)
- [Mastering LangGraph State Management in 2025](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025) — MEDIUM confidence
- [Memory Leak in LangGraph · Issue #3898](https://github.com/langchain-ai/langgraph/issues/3898) — HIGH confidence (official GitHub issue)
- [LLM01:2025 Prompt Injection - OWASP Gen AI Security Project](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — HIGH confidence (official OWASP)
- [Are AI Trading Signals Reliable? Data From 2024–2025](https://www.moneymarketinsights.com/p/are-ai-trading-signals-reliable-data-from-2024-2025) — LOW confidence (single source)
- [How Machine Learning is Enhancing Macro Investing | BlackRock](https://www.blackrock.com/institutions/en-us/insights/machine-learning-macro-investing) — HIGH confidence (institutional source)
- [Major Compliance Risks Advisors Face When Using AI Tools | Kitces](https://www.kitces.com/blog/artificial-intelligence-ai-tools-regulation-compliance-regulatory-ria-chatgpt-records-client-data-risk/) — MEDIUM confidence
- [vnstock GitHub issues — data reliability patterns](https://github.com/thinh-vu/vnstock/issues) — HIGH confidence (primary source)
- [vnstock breaking changes — KRX system May 2025](https://vnstocks.com/docs/vnstock-insider-api/lich-su-phien-ban) — HIGH confidence (official docs)
- [Building a Production-Grade RAG Document Ingestion Pipeline with LlamaIndex and Qdrant](https://medium.com/@iamarunbrahma/building-a-production-grade-rag-document-ingestion-pipeline-with-llamaindex-and-qdrant-08f4ea1c03c1) — MEDIUM confidence
- [Gemini API pricing and context caching](https://ai.google.dev/gemini-api/docs/pricing) — HIGH confidence (official Google docs)
- [Investor Overconfidence in the AI Era](https://jsom.org.pk/index.php/Research/article/view/391) — MEDIUM confidence (academic journal)

---
*Pitfalls research for: AI-powered long-term investment advisor platform (Stratum) — Vietnamese retail investors*
*Researched: 2026-03-03*
