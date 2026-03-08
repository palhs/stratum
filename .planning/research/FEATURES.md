# Feature Research

**Domain:** Analytical reasoning engine — macro regime classification, asset valuation, price structure analysis, AI entry quality scoring, bilingual report generation
**Researched:** 2026-03-09
**Confidence:** MEDIUM-HIGH — Global institutional investment platform patterns are HIGH confidence (well-documented); AI-native entry quality scoring with LangGraph is MEDIUM confidence (nascent but growing precedent in 2025–2026); Vietnamese-language generation with Gemini is MEDIUM confidence (limited direct evidence but Gemini 2.5 supports Vietnamese natively).

---

## Scope Note

This file covers the v2.0 milestone features only: the analytical reasoning engine built on top of the v1.0 data ingestion platform. Features already delivered in v1.0 (OHLCV ingestion, FRED macro ingestion, pre-computed structure markers, pipeline run logging, anomaly detection, Docker infrastructure) are listed as **v1.0 dependencies**, not as features to build.

---

## v1.0 Data Available as Input

The following data exists in storage and feeds v2.0 features directly:

| Data | Storage Location | Cadence | Notes |
|------|-----------------|---------|-------|
| VN30 OHLCV (weekly/monthly) | PostgreSQL | Weekly | 9,411 rows; pre-computed MAs, drawdown from ATH, percentile ranks |
| VN30 fundamentals (P/E, P/B, EPS, ROE) | PostgreSQL | Monthly | 399 rows; validated through vnstock VCI source |
| FRED macro series (GDP, CPI, unemployment, Fed funds rate) | PostgreSQL | Monthly | Growth rates, level values, YoY change stored |
| Gold price (FRED spot) | PostgreSQL | Weekly/Monthly | USD spot price with data_as_of timestamp |
| GLD ETF flows | PostgreSQL | Monthly | Working; WGC central bank data is 501 stub |
| Pre-computed structure markers | PostgreSQL | Weekly | MAs (50/200), drawdown from ATH, 52-week percentile rank |
| Pipeline run log | PostgreSQL | Per run | Success/failure, row counts, anomaly flags |

**Gaps in v1.0 data that affect v2.0 features:**
- WGC central bank buying data: stub only — will require manual CSV import or skip for v2.0
- Historical regime nodes in Neo4j: empty — must be seeded before regime classification can function
- Document corpus (Fed minutes, SBV reports, VN earnings): not yet ingested into Qdrant

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the analytical reasoning engine must deliver. Missing any of these means the platform does not fulfill its stated purpose.

| Feature | Why Expected | Complexity | v1.0 Dependency | Notes |
|---------|--------------|------------|-----------------|-------|
| Retrieval layer over all three stores | Reasoning pipeline cannot access data without a retrieval abstraction; LangGraph nodes cannot query PostgreSQL, Neo4j, and Qdrant directly without a unified interface | MEDIUM | PostgreSQL (all tables), Neo4j (empty regime graph), Qdrant (empty collections) | LlamaIndex as retrieval-only layer; GraphRAGRetriever for Neo4j, HybridRetriever for Qdrant, SQLRetriever for PostgreSQL |
| Macro regime classification | The root dependency of the entire platform; valuation and entry quality both require regime context; without this the platform produces decontextualized data, not analysis | HIGH | FRED macro series, gold price, VN30 structure markers | Must output probability distribution, not a single label; mixed-signal handling required from day one; regime nodes in Neo4j must be seeded before this can run |
| Asset valuation assessment relative to historical range | Any investment analysis platform that shows a P/E ratio or price level is expected to contextualize it against history; without this, raw numbers are noise | MEDIUM | VN30 fundamentals (P/E, P/B), gold spot price, pre-computed percentile ranks | Historical percentile already pre-computed in v1.0 structure markers; regime-relative layer is the v2.0 addition |
| Higher time-frame price structure analysis | Long-term investors expect to see where price sits relative to moving averages and cycle extremes before making an entry decision; platform cannot answer "when to enter" without this | MEDIUM | Pre-computed MAs (50/200), drawdown from ATH, structure markers in PostgreSQL | v1.0 pre-computes these; v2.0 interprets them into narrative — not recomputation |
| AI-derived entry quality assessment | The platform's stated purpose is to answer "when is a reasonable time to enter"; without a synthesized assessment, users have three separate analyses but no actionable conclusion | HIGH | Depends on macro regime, valuation assessment, and price structure all running first | Must output qualitative tier (Favorable / Neutral / Cautious / Avoid) with three sub-assessments shown before composite; never a standalone number |
| Structured report output (JSON + Markdown) | Institutional research platforms (BlackRock, VinaCapital) produce structured deliverables; users of research-grade tools expect a formatted, navigable document — not raw LLM text | MEDIUM | Entry quality assessment output, all three analytical layers | Card format: macro regime card, valuation card, price structure card, entry quality card; JSON for programmatic use, Markdown for human reading |
| Bilingual output (Vietnamese + English) | Vietnamese retail investment platforms (Vietstock, CafeF) produce Vietnamese-language content; the primary user audience expects Vietnamese as the reading language | MEDIUM | Structured report output (must be stable before bilingual generation to avoid double maintenance) | Vietnamese is primary; English is secondary; generate both from same structured data, not translate one from the other |
| Graceful handling of missing and stale data | WGC data has a known 45-day publication lag; vnstock has known fragility; a platform that silently uses stale data or omits missing fields is worse than useless for investment decisions | LOW | Pipeline run log (data_as_of + ingested_at on every row), anomaly detection flags | Must emit explicit "DATA WARNING" sections in reports when freshness threshold is exceeded; not a nice-to-have |
| Explainable multi-step reasoning | CFA Institute research confirms that explainability is a table-stakes expectation for AI-assisted investment research; users who cannot see the reasoning chain cannot trust the conclusion | MEDIUM | All three analytical layers must produce intermediate outputs, not just a final answer | Each LangGraph node must output: data source cited, inputs used, intermediate conclusion reached; grounding check node must verify all numbers trace to retrieved records |
| Conflicting signal representation | When macro conditions are positive but price structure is weak (or vice versa), the platform must say so explicitly; papering over signal conflicts is a research quality failure | MEDIUM | Macro regime classification, valuation assessment, price structure — all three must be functional before conflicts can be surfaced | "Strong thesis, weak structure" output is a first-class report type, not an edge case to handle later |

### Differentiators (Competitive Advantage)

Features that distinguish Stratum from existing Vietnamese retail investment platforms and from generic AI financial tools.

| Feature | Value Proposition | Complexity | v1.0 Dependency | Notes |
|---------|-------------------|------------|-----------------|-------|
| Macro regime classification with historical analogues | No Vietnamese retail platform offers regime-aware analysis mapped to historical precedents; this is an institutional capability (BlackRock, Two Sigma use GMM/k-means/PCA for regime detection) delivered at retail scale | HIGH | FRED macro series (GDP, CPI, Fed funds rate, unemployment); Neo4j must be seeded with historical regime nodes before this is meaningful | Quantitative similarity for candidate analogues (k-means or cosine similarity over normalized FRED series); LLM interpretation for narrative; Neo4j RESEMBLES relationships carry similarity_score, dimensions_matched, period |
| Regime-relative valuation assessment | Most platforms show P/E vs a static historical average; regime-relative valuation asks "is this P/E reasonable given that we are in a late-cycle inflationary regime?"; this reframe is institutional-grade and unavailable in local Vietnamese platforms | MEDIUM | VN30 fundamentals (P/E, P/B), pre-computed percentile ranks; macro regime classification must run first | Gold valuation uses real yield (FRED TIPS rate) and ETF flow context; VN equity valuation uses P/E percentile relative to analogous historical periods from Neo4j regime graph |
| Mixed-signal and low-confidence regime representation | Institutional investment research (Macrobond, FactSet) explicitly models regime ambiguity; most consumer platforms present regimes as binary and clean; a platform that honestly represents partial matches is more trustworthy for sophisticated users | MEDIUM | Macro regime classification (probability distribution output required) | If top confidence below 70%, surface "Mixed Signal Environment" with two most likely analogues; Neo4j RESEMBLES relationships must carry confidence weights from inception |
| Vietnamese-native report generation | Existing Vietnamese platforms (Vietstock, CafeF) translate English financial concepts rather than generating Vietnamese-native analysis; Gemini 2.5 Flash supports Vietnamese natively with financial vocabulary | MEDIUM | Structured report output must be stable before Vietnamese generation begins; requires a curated Vietnamese financial term dictionary (content asset, not code) | Generate Vietnamese directly from structured data, not by translating English output; VAS (Vietnamese Accounting Standard) differs from IFRS — term mapping must account for this |
| Manually curated document corpus (Fed minutes, SBV reports, VN earnings) | Generic RAG systems retrieve from unstructured web content; a manually curated corpus of authoritative primary sources dramatically improves retrieval precision for macro context claims | MEDIUM | Qdrant collections (empty in v1.0, must be populated); FastEmbed embedding model | For v2.0: manual curation only; automated ingestion deferred to v3.0; corpus includes Fed FOMC minutes, State Bank of Vietnam reports, VN30 earnings transcripts |
| Asset-class cross-referencing (gold + VN stocks in same regime context) | Gold and Vietnamese equities respond differently to the same macro regime; a platform that explicitly covers both within the same analytical frame provides portfolio-level context unavailable in local platforms | MEDIUM | Gold price (FRED), GLD ETF flows, VN30 OHLCV — all in PostgreSQL; regime classification must span both asset classes | At launch: gold and VN stocks only; regime nodes in Neo4j must include period-level correlations between asset classes |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable for this milestone but create problems disproportionate to their benefit.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Single numeric entry quality score (e.g., 7.3/10) | Users want a number to act on; it feels precise and comparable | A single number without component breakdown is uninterpretable for investment decisions; it encourages "score = buy" reasoning that bypasses the analytical reasoning the platform exists to provide; it also creates false precision — AI reasoning over probabilistic inputs does not produce 7.3 vs 7.4 distinctions | Qualitative tier (Favorable / Neutral / Cautious / Avoid) with three sub-assessment cards shown first; tier label is the output of the synthesized assessment, not a standalone deliverable |
| AI chat / Q&A over reports | Popular expectation for AI products in 2026; "ask the report anything" is a common request | Unstructured chat creates unpredictable output quality and dramatically increases LLM cost non-linearly; harder to ensure explainability; may generate responses that appear to be specific investment advice; the structured report format already answers "why" questions better than open-ended chat | Expand report depth through additional analytical cards; if a question keeps arising about a specific aspect, add it as a structured section to the report template |
| Real-time regime updates (trigger on macro data change) | "Alert me when the regime changes" is a natural extension of regime classification | Regime classification is by definition a persistent-state signal computed on monthly or quarterly cadence; real-time monitoring creates false sensitivity to noise in macro releases; contradicts the weekly/monthly analytical frame; adds infrastructure complexity (streaming pipeline) with no analytical value | Weekly digest that includes a "regime unchanged / regime shifted" status line; regime changes are notable because they are infrequent |
| Per-asset portfolio context (how does this fit my holdings?) | Users who use the platform regularly will naturally want to see how an entry decision fits their existing positions | Moves the product from "research advisor" to "portfolio manager"; requires holdings data, cost basis, position sizing logic; fundamentally different product; compliance and regulatory exposure in Vietnam if holdings + advice combine | Watchlist-only at launch; Stratum answers "are conditions favorable for a long-term entry" not "should you rebalance today" |
| Backtesting of entry quality score | Power users will ask "would this have worked?" for any new scoring system | Extremely high complexity; requires clean historical data for all three layers (regime, valuation, structure) going back 10+ years for VN market (limited); can produce false confidence from overfitted backtests; the VN30 market history is too short for statistically meaningful backtesting of multi-layer signals | The historical analogues section IS the evidence layer — showing what happened in historically similar regimes is more honest than simulated P&L on a young market |
| Raw LLM output as report body | Fastest to implement; just prompt Gemini with all data and get a report | Ungrounded claims; numeric hallucination risk is severe in financial context; no intermediate outputs for explainability; impossible to audit; single monolithic prompt cannot handle mixed-signal and stale data edge cases cleanly | LangGraph StateGraph with five named nodes; each node produces a structured intermediate output that feeds the next; grounding check node at the end verifies all numbers trace to retrieved database records |

---

## Feature Dependencies

```
[v1.0: FRED macro data in PostgreSQL]
    └──required by──> [Macro regime classification]

[v1.0: Gold price in PostgreSQL]
    └──required by──> [Macro regime classification]
    └──required by──> [Gold valuation assessment]

[v1.0: VN30 fundamentals in PostgreSQL]
    └──required by──> [VN equity valuation assessment]

[v1.0: Pre-computed structure markers in PostgreSQL]
    └──required by──> [Price structure analysis (v2.0 interprets, not recomputes)]

[Neo4j regime graph — seeded with historical nodes]
    └──required by──> [Macro regime classification (analogue retrieval)]
    └──required by──> [Regime-relative valuation assessment]

[Qdrant corpus — populated with curated documents]
    └──required by──> [Macro context retrieval in reasoning nodes]
    └──enables──> [Narrative grounding in report]

[Retrieval layer (LlamaIndex)]
    └──required by──> [All LangGraph reasoning nodes]

[Macro regime classification]
    └──required by──> [Regime-relative valuation assessment]
    └──required by──> [Entry quality assessment]
    └──required by──> [Historical analogues display]

[Regime-relative valuation assessment]
    └──required by──> [Entry quality assessment]
    └──required by──> [Structured report output — valuation card]

[Price structure analysis]
    └──required by──> [Entry quality assessment]
    └──required by──> [Structured report output — structure card]

[Entry quality assessment]
    └──required by──> [Structured report output — entry quality card]
    └──required by──> [Conflicting signal representation]

[Structured report output (JSON + Markdown)]
    └──required by──> [Bilingual output (Vietnamese + English)]

[Vietnamese financial term dictionary]
    └──required by──> [Bilingual output — quality Vietnamese generation]

[Bilingual output]
    └──required by──> [Report storage in PostgreSQL]
    └──required by──> [Report history archive]
```

### Dependency Notes

- **Neo4j regime graph must be seeded before classification runs.** The v1.0 Neo4j instance has constraints and APOC triggers but no regime data. Seeding historical macro regime nodes (with period metadata, FRED series values, and asset class correlations) is a prerequisite for any regime classification to be meaningful. This is a content curation task, not a code task.

- **Retrieval layer validation must precede reasoning integration.** LlamaIndex retrievers (GraphRAGRetriever for Neo4j, HybridRetriever for Qdrant, SQLRetriever for PostgreSQL) must be tested independently against real data before being embedded in LangGraph nodes. Bugs inside a 5-node reasoning graph are extremely difficult to root-cause.

- **Macro regime classification is the root dependency for everything downstream.** Valuation assessment (regime-relative context), entry quality assessment (macro sub-score), and analogues display all require regime to be functional and validated before they can be built reliably. Build and validate regime classification before adding valuation or entry quality nodes.

- **Bilingual output depends on stable report structure.** Generating Vietnamese and English from the same structured data requires the report structure (cards, fields, terminology) to be finalized. Building bilingual before structure is stable causes double maintenance burden on every structural change.

- **Vietnamese financial term dictionary is a content prerequisite, not a code task.** Gemini generates Vietnamese natively but financial terminology (định giá tương đối, cấu trúc giá, chế độ vĩ mô) requires consistent mapping that must be authored before the ReportComposer node is built. This is a blocker for bilingual output quality.

- **WGC central bank data gap does not block v2.0 launch.** Gold valuation can function with FRED gold spot price, GLD ETF flows, and real yield (FRED TIPS). WGC central bank buying is supplementary context. The 501 stub in v1.0 should be flagged as a known data gap in reports, not treated as a blocker.

---

## MVP Definition

### v2.0 Launch: Analytical Reasoning Engine

Minimum viable product for the v2.0 milestone — what's needed to produce one complete, explainable, bilingual report that meets the founder's stated analytical standard.

- [ ] Retrieval layer (LlamaIndex) validated over all three stores — without this, no reasoning node can access data
- [ ] Neo4j regime graph seeded with historical macro periods — without this, regime classification has nothing to match against
- [ ] Qdrant document corpus populated with manually curated documents — without this, macro narrative lacks grounding
- [ ] Macro regime classification with probability distribution output and mixed-signal handling — root dependency for all downstream features
- [ ] Regime-relative valuation assessment for VN equities (P/E, P/B vs historical analogues) and gold (real yield, ETF flow context)
- [ ] Price structure interpretation node (reads pre-computed v1.0 markers, produces narrative) — do not recompute what v1.0 already computes
- [ ] Entry quality assessment with qualitative tier and three visible sub-assessments (macro, valuation, structure)
- [ ] Grounding check node verifying all report numbers trace to retrieved database records — not optional, blocks hallucination
- [ ] Structured report output in JSON + Markdown (card format: macro regime card, valuation card, structure card, entry quality card)
- [ ] Bilingual generation (Vietnamese primary, English secondary) using Vietnamese financial term dictionary
- [ ] Explicit data freshness flags and "DATA WARNING" sections when data_as_of exceeds freshness threshold
- [ ] Conflicting signal handling producing "strong thesis, weak structure" report type explicitly

### Add After First Report Validates (v2.x)

Features to add once the first end-to-end report is validated against the founder's analytical standard:

- [ ] LangGraph checkpoint persistence (langgraph-checkpoint-postgres) for audit trail and interrupted run recovery — trigger: first time a pipeline run needs to be debugged or resumed
- [ ] Additional VN30 assets (beyond initial test set of 2–3 stocks) — trigger: first report quality confirmed
- [ ] Automated Neo4j regime graph update on new FRED data ingestion — trigger: manual seeding workflow becomes burdensome
- [ ] Enhanced Qdrant corpus (additional SBV reports, VN earnings) — trigger: report narrative lacks macro context depth

### Defer to v3.0

Features out of scope for v2.0 analytical engine — belong to the UI/productization milestone:

- [ ] FastAPI API layer — v2.0 reports run as Python scripts or n8n-triggered jobs; API shapes cannot be stable until report structure is finalized
- [ ] Frontend (Next.js) — no user-facing UI in v2.0; reports are JSON + Markdown files written to PostgreSQL
- [ ] Watchlist management UI — single-asset manual triggering is sufficient for v2.0 validation
- [ ] On-demand report generation via API — requires FastAPI layer; defer to v3.0
- [ ] Report history archive UI — data is stored in PostgreSQL; UI is a v3.0 concern
- [ ] PDF export — v3.0 frontend concern

---

## Feature Prioritization Matrix

### v2.0 Scope Only

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Retrieval layer (LlamaIndex over 3 stores) | HIGH — blocks everything | MEDIUM | P1 |
| Neo4j regime graph seeding | HIGH — blocks classification | LOW (content curation) | P1 |
| Qdrant corpus population | MEDIUM — improves narrative grounding | LOW (content curation) | P1 |
| Macro regime classification | HIGH — root dependency | HIGH | P1 |
| Grounding check node | HIGH — prevents hallucination | LOW | P1 |
| Stale data flags in reports | HIGH — prevents presenting misleading data | LOW | P1 |
| Conflicting signal handling | HIGH — prevents false confidence | MEDIUM | P1 |
| Regime-relative valuation assessment | HIGH | MEDIUM | P1 |
| Price structure interpretation node | HIGH | LOW (reads pre-computed data) | P1 |
| Entry quality assessment (qualitative tier) | HIGH | MEDIUM | P1 |
| Structured report output (JSON + Markdown) | HIGH | MEDIUM | P1 |
| Vietnamese financial term dictionary | HIGH — blocks bilingual quality | LOW (content, not code) | P1 |
| Bilingual generation (VN + EN) | HIGH | MEDIUM | P1 |
| Mixed-signal representation | HIGH | MEDIUM | P1 |
| LangGraph checkpoint persistence | MEDIUM | LOW | P2 |
| Additional VN30 assets | MEDIUM | LOW | P2 |
| Automated regime graph updates | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v2.0 launch
- P2: Should have, add after first report validates
- P3: Nice to have, v2.x or v3.0

---

## Competitor Feature Analysis

### How Existing Platforms Handle Each v2.0 Feature

| Feature | Vietstock / CafeF | Simply Wall St | Stockopedia | Stratum v2.0 approach |
|---------|-------------------|----------------|-------------|----------------------|
| Macro regime classification | Not present — news commentary, not regime analysis | Not present | Not present | Core intellectual property — quantitative similarity over FRED series + LLM interpretation of matched analogues |
| Historical analogues | Not present | Not present | Not present | Neo4j RESEMBLES relationships with similarity_score, dimensions_matched, period; surfaces 2–3 analogues with narrative per matched period |
| Valuation vs historical range | Basic P/E data shown; no historical percentile | DCF-based fair value (global stocks) | StockRanks value score | Pre-computed percentile rank (v1.0); regime-relative context added in v2.0 |
| Price structure analysis | Technical analysis (daily/intraday focus, short-term TA) | Not present | Momentum score | Weekly/monthly MA positioning and drawdown from ATH; explicitly framed as entry context, not trading signal |
| Entry quality score | Not present | "Snowflake" score (5 dimensions, no macro layer) | StockRanks composite (value + quality + momentum) | Qualitative tier with three visible sub-assessments; AI-derived through multi-step LangGraph reasoning, not formula |
| Explainability | Not applicable (data portal) | Methodology page; no per-report reasoning | Factor definitions; no per-report chain | Every LangGraph node outputs data source, inputs used, intermediate conclusion; grounding check verifies numbers |
| Mixed-signal representation | Not applicable | Not applicable | Not applicable | First-class output type; probability distribution for regime; confidence level on every report section |
| Vietnamese-language output | Yes (primary) | No | No | Vietnamese generated natively (not translated); curated financial term dictionary; VAS accounting context |
| Gold fundamental analysis | Price data only | Not present | Not present | Real yield (FRED TIPS), ETF flows (GLD), macro regime framing; WGC central bank data flagged as lagged |
| Bilingual output | Vietnamese only (no structured bilingual) | English only | English only | Both Vietnamese and English from same structured data; not translation |
| Stale data disclosure | Not present | Not present | Not present | Explicit "DATA WARNING" sections; data_as_of shown on every data point cited in report |

---

## Complexity Notes per Feature

For roadmap phase planning:

**LOW implementation complexity (existing data, straightforward interpretation):**
- Price structure interpretation node — v1.0 pre-computes all markers; v2.0 only interprets them into narrative
- Grounding check node — structural validation of LangGraph output against retrieved records
- Stale data flags — read data_as_of from PostgreSQL, compare to freshness threshold, emit warning section
- Vietnamese financial term dictionary — content work, no code complexity
- Neo4j regime graph seeding — data curation and Cypher import, no new code required

**MEDIUM implementation complexity (new reasoning logic, well-understood patterns):**
- Retrieval layer (LlamaIndex) — integration work; GraphRAGRetriever, HybridRetriever, SQLRetriever each need independent validation
- Regime-relative valuation assessment — requires macro regime classification output as input; the valuation percentile is already computed
- Entry quality assessment — aggregation of three sub-assessments into qualitative tier
- Structured report output (JSON + Markdown) — schema design and template engineering
- Bilingual generation — Gemini structured output with term dictionary; not translation, direct generation
- Conflicting signal handling — conditional logic in LangGraph routing based on sub-assessment disagreement

**HIGH implementation complexity (novel integration, highest risk):**
- Macro regime classification — quantitative similarity over time-series FRED data; Neo4j analogue retrieval; LLM interpretation of matched periods; probability distribution output; mixed-signal edge cases; seeded graph data required; most critical pitfalls originate here
- Full LangGraph StateGraph (all five nodes together) — each node is medium complexity individually; integration of all five with state passing, error handling, and conditional routing across real data is HIGH complexity overall

---

## Sources

- FactSet macro regime framework: https://insight.factset.com/mapping-asset-returns-to-economic-regimes-a-practical-investors-guide (MEDIUM confidence)
- Macrosynergy regime classification research: https://macrosynergy.com/research/classifying-market-regimes/ (MEDIUM confidence)
- Two Sigma machine learning regime modeling: https://www.twosigma.com/articles/a-machine-learning-approach-to-regime-modeling/ (MEDIUM confidence)
- AlphaArchitect k-means macro regime clustering: https://alphaarchitect.com/clustering-macroeconomic-regimes/ (MEDIUM confidence)
- Tactical asset allocation with FRED-MD regime detection: https://arxiv.org/html/2503.11499v2 (MEDIUM confidence — recent preprint)
- CFA Institute Explainable AI in Finance: https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance (HIGH confidence — CFA Institute official)
- AWS blog: LangGraph + Strands Agents financial analysis: https://aws.amazon.com/blogs/machine-learning/build-an-intelligent-financial-analysis-agent-with-langgraph-and-strands-agents/ (MEDIUM confidence)
- Neo4j + LlamaIndex integration: https://neo4j.com/labs/genai-ecosystem/llamaindex/ (HIGH confidence — official Neo4j Labs)
- Qdrant + Neo4j GraphRAG: https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/ (HIGH confidence — official Qdrant docs)
- LLM Pro Finance Suite (multilingual financial LLMs): https://arxiv.org/html/2511.08621v1 (MEDIUM confidence — academic preprint)
- Macrobond gold valuation outlier 2025: https://www.macrobond.com/resources/macro-trends/gold-beyond-geopolitical-hedge-and-valuation-outlier (MEDIUM confidence)
- World Gold Council gold outlook 2025: https://www.gold.org/goldhub/research/gold-outlook-2025 (HIGH confidence — official WGC)
- Advisor Perspectives CAPE/P/E10 historical percentile analysis: https://www.advisorperspectives.com/dshort/updates/2026/01/06/pe10-market-valuation-december-2025 (MEDIUM confidence)
- Simply Wall St features: https://simplywall.st/ (HIGH confidence — official)
- Stockopedia StockRanks: https://www.stockopedia.com/ (HIGH confidence — official)
- Vietstock platform: https://en.vietstock.vn/about-us.htm (MEDIUM confidence — official)

---
*Feature research for: Analytical reasoning engine — Stratum v2.0 milestone*
*Researched: 2026-03-09*
