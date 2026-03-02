# Feature Research

**Domain:** Long-term investment advisor platform (Vietnamese market, macro-fundamental analysis)
**Researched:** 2026-03-03
**Confidence:** MEDIUM — Global investment platform patterns are HIGH confidence (well-documented); Vietnamese market-specific expectations are MEDIUM confidence (fewer authoritative sources); novel AI-driven analysis features are LOW-MEDIUM confidence (nascent space with limited direct precedent)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Watchlist management | Every investment platform has watchlists; users expect to add/remove assets and organize their coverage universe | LOW | Watchlist only (no holdings) per PROJECT.md — do not conflate with portfolio tracking |
| Per-asset research report | Users open a platform expecting to read structured analysis of a specific asset | MEDIUM | Core deliverable of the platform; must exist before anything else matters |
| Valuation context (vs historical range) | Any fundamental tool shows where current price or metric sits relative to history | MEDIUM | P/E vs 10-year range, price-to-book, gold price vs purchasing-power baseline — relative not absolute |
| Bilingual output (Vietnamese + English) | Vietstock, VietstockFinance, and major Vietnamese financial portals all provide two-language versions; the primary user audience expects Vietnamese-language content | MEDIUM | Vietnamese is primary; English for broader reach. Report generation must produce both. |
| Explicit data freshness indicators | In data-lagged environments (World Gold Council publishes 1–2 months late; FRED data varies), users must know whether what they are reading reflects current reality | LOW | Flag stale data explicitly in reports — not a nice-to-have given known data lag issues |
| Conflict disclosure in analysis | When signals disagree (macro positive, price structure weak), users expect the platform to say so rather than paper over it | LOW | "Strong thesis, weak structure" outputs are expected transparency, not edge case handling |
| On-demand report generation for new watchlist additions | Users adding a new asset expect to get analysis immediately, not wait for the next scheduled run | MEDIUM | Monthly cadence for existing watchlist; on-demand for new additions |
| Explainable reasoning steps | Institutional-quality research (BlackRock, VinaCapital, sell-side reports) shows its work — users of research-grade tools expect to see the reasoning chain, not just a conclusion | MEDIUM | Each analysis step must show its data source, inputs, and output clearly |
| Report history / archive | Users return to prior reports to track how analysis has evolved — this is baseline for any research platform | LOW | Simple append-only archive per asset; no versioning complexity needed at launch |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Macro regime classification with historical analogues | No Vietnamese retail investment platform offers regime-aware analysis mapped to historical precedents; this is an institutional capability democratized for retail | HIGH | The regime → analogues → current asset performance chain is the core intellectual property of this platform. Vietstock offers no equivalent. |
| AI-derived entry quality score | Synthesizes macro regime, valuation position, and price structure into a single actionable signal — something no existing Vietnamese retail platform provides | HIGH | Must be explainable: a score without a reasoning chain is not acceptable. Score is output of multi-step LangGraph chain, not a formula. |
| Higher time-frame price structure analysis (weekly/monthly) | Addresses the most costly retail investor mistake: being fundamentally right but entering at a structurally dangerous price level. No local Vietnamese platform provides this at a long-term orientation. | MEDIUM | Weekly/monthly MA positioning, drawdown from ATH, trend context. Pre-computed in n8n. Not trading signals — explicitly entry context. |
| Mixed-signal and low-confidence regime representation | Most platforms pretend regimes are clean and signals are clear. A platform that honestly represents partial matches and mixed signals is meaningfully more trustworthy for sophisticated users. | MEDIUM | This is both a technical challenge (handling ambiguity in the knowledge graph) and a UX challenge (displaying uncertainty without alarming users) |
| Asset-class cross-referencing (gold + VN stocks) | Gold and Vietnamese equities are both affected by macro regimes but in different ways; a platform that explicitly covers both and their relationship provides portfolio-level context no local competitor does | MEDIUM | At launch: gold and VN stocks only. Dependency: regime classification must span both asset classes. |
| Gold fundamental analysis (ETF flows, central bank buying, real yield) | Gold is widely owned by Vietnamese retail investors but rarely analyzed with institutional-grade fundamentals in local Vietnamese-language resources | MEDIUM | World Gold Council data has 1–2 month lag and central bank figures are revised; the platform must handle this gracefully and flag it |
| Vietnamese stock fundamental analysis via vnstock | vnstock provides open-source access to Vietnamese market data not available through global platforms; wrapping this in institutional-quality analysis is unique | MEDIUM | vnstock data quality varies by metric; pipeline must validate and flag missing fields |
| Structured card report format | Research-grade narrative format (not trading terminal UI) is unusual in local Vietnamese retail platforms, which tend toward data tables and technical charts | MEDIUM | Cards per analytical layer: macro regime card, valuation card, price structure card, entry quality card. Visual hierarchy matters. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time or intraday price data | "Why isn't my price live?" is the most common user complaint on any investment platform | Contradicts the long-term, weekly/monthly analytical frame; real-time data creates pressure to act on short-term noise, which defeats the platform's purpose; adds infrastructure cost and complexity that provides no analytical value for the use case | Display last weekly/monthly close with explicit timestamp; label it clearly. Educate in report copy that entry decisions are made on weekly closes, not ticks. |
| Portfolio holdings tracking and P&L | Users who love a platform want to log their positions and see returns | Scope creep into brokerage-adjacent features; compliance risk if positions + advice combine; fundamentally changes the product from "research advisor" to "portfolio manager" with different legal and UX implications in Vietnam | Watchlist only. If user wants to track holdings, they have a broker for that. Stratum answers "should I enter" not "how am I doing". |
| Buy/sell trade signals | "Should I buy now?" naturally leads to "tell me exactly when to buy" | Crosses from investment education/research into regulated financial advice territory in Vietnam (Ủy ban Chứng khoán Nhà nước regulatory risk); also defeats the macro-fundamental framing which is inherently probabilistic, not actionable-to-the-day | Entry quality score with explicit framing: "conditions are favorable / unfavorable / mixed for long-term entry" — not "buy today at 12:30pm" |
| Social features (sharing, comments, community) | Users want to discuss analysis and share reports | Dramatically expands moderation burden; creates regulatory exposure if shared analysis constitutes investment advice; diverts development from core analysis quality | Reports can be exported/shared externally by the user; platform itself stays single-user research tool |
| Price alerts and push notifications | "Alert me when stock X crosses Y" is requested on every investment platform | Implies real-time monitoring infrastructure; creates urgency that conflicts with the weekly/monthly cadence thesis; trains users to react to price, not analysis | Weekly digest email/notification summarizing which watchlist assets have updated reports — cadence-aligned, not price-triggered |
| Backtesting / strategy simulator | Power users want to test whether the entry quality score would have worked historically | Extremely high complexity; requires clean historical regime + valuation + price structure data going back many years; can produce false confidence if backtests are overfitted | Show historical analogues as evidence rather than simulated P&L. The research reports IS the evidence of what happened in similar regimes. |
| AI chat / Q&A over reports | "Ask the platform anything" is a popular AI feature expectation in 2025–2026 | Unstructured chat creates unpredictable output quality; increases LLM cost non-linearly; harder to ensure explainability; may generate responses that appear to be financial advice | Structured report cards with explicit reasoning sections answer "why" questions better than chat; expand report depth instead of adding chat |
| Short-term technical trading signals | Technical analysis tools (RSI, MACD, short-term patterns) are requested by any platform touching charts | Completely contradicts the long-term, macro-fundamental positioning; adds a different user persona (trader vs long-term investor) who will compete for product attention | Explicitly exclude short-term TA. Use only weekly/monthly MAs and drawdown from ATH as structural context. Label these as "price structure context" not "technical analysis". |

---

## Feature Dependencies

```
[Macro regime classification]
    └──required by──> [Asset valuation assessment (regime-relative)]
    └──required by──> [Entry quality score]
    └──required by──> [Historical analogues display]

[Asset valuation assessment]
    └──required by──> [Entry quality score]
    └──required by──> [Per-asset research report]

[Higher time-frame price structure]
    └──required by──> [Entry quality score]
    └──required by──> [Per-asset research report]

[Entry quality score]
    └──required by──> [Per-asset research report (complete)]

[Data ingestion — VN stocks (vnstock)]
    └──required by──> [Asset valuation assessment (VN stocks)]
    └──required by──> [Higher time-frame price structure (VN stocks)]

[Data ingestion — Gold (World Gold Council, ETF flows)]
    └──required by──> [Asset valuation assessment (gold)]
    └──required by──> [Gold fundamental analysis card]

[Data ingestion — Macro (FRED)]
    └──required by──> [Macro regime classification]

[Per-asset research report]
    └──required by──> [Bilingual output]
    └──required by──> [Report history / archive]

[Watchlist management]
    └──enables──> [On-demand report generation]
    └──enables──> [Report history per asset]

[Explainable reasoning steps]
    └──enhances──> [Entry quality score (score without chain = not acceptable)]
    └──enhances──> [Mixed-signal representation]
```

### Dependency Notes

- **Macro regime classification is the root dependency**: Valuation assessment, entry quality score, and analogues all require regime as their primary context layer. Regime classification must be built and validated before any downstream feature is reliable.
- **Entry quality score requires all three upstream layers**: Macro regime, valuation, and price structure must all be functional before the score can be computed. The score is the synthesis, not an independent feature.
- **Bilingual output depends on report structure being stable**: Generate Vietnamese and English from the same structured data/template. Building bilingual before report structure is stable creates double maintenance burden.
- **On-demand generation depends on watchlist**: You can't generate a report for an asset that isn't being tracked. Watchlist is infrastructure for report triggering.
- **Gold and VN stocks share the regime layer but diverge at valuation**: Macro regime classification spans both. Valuation logic differs per asset class and must be built separately.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept (report quality matching founder's manual analytical standard).

- [ ] Data ingestion: VN stocks via vnstock (weekly/monthly OHLCV + fundamentals) — without this, there is no analysis
- [ ] Data ingestion: Gold (price, ETF flows, central bank data) — gold is half the launch asset universe
- [ ] Data ingestion: Macro data via FRED — required for regime classification
- [ ] Macro regime classification with historical analogues — the intellectual core; everything else depends on it
- [ ] Asset valuation assessment relative to historical range and regime — regime-relative valuation is the differentiated view
- [ ] Higher time-frame price structure analysis (weekly/monthly MAs, drawdown from ATH) — entry context layer
- [ ] AI-derived entry quality score with explicit reasoning chain — the synthesis and primary output
- [ ] Structured card report in Vietnamese and English — the user-facing deliverable
- [ ] Watchlist management — add/remove assets, trigger report generation
- [ ] Monthly report generation cadence + on-demand for new watchlist additions
- [ ] Data freshness flags and explicit stale data handling in reports
- [ ] Mixed-signal and low-confidence representation in reports
- [ ] Report history archive per asset

### Add After Validation (v1.x)

Features to add once core analysis quality is confirmed.

- [ ] Email digest notification on report updates — trigger: users find themselves manually checking for new reports
- [ ] Report export (PDF) — trigger: users want to share/store reports outside the platform
- [ ] Additional VN stock fundamental metrics (valuation ratios not in vnstock base) — trigger: gaps identified in v1 report quality
- [ ] Improved chart rendering for price structure context — trigger: cards feel text-heavy without visual support

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Additional asset classes (BTC, bonds, US stocks) — per PROJECT.md out of scope; add only after VN stocks + gold analysis is excellent
- [ ] Multi-user accounts and authentication — single-user at launch; productization requires auth, permissions, billing
- [ ] Screener / asset discovery — "find assets that match this regime profile" — valuable but requires large asset coverage first
- [ ] Watchlist sharing / report export to external users — productization feature; single-user tool doesn't need it
- [ ] Mobile web optimization — web-first; mobile can follow if usage patterns demand it

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Data ingestion (VN stocks, gold, macro) | HIGH | MEDIUM | P1 |
| Macro regime classification + analogues | HIGH | HIGH | P1 |
| Asset valuation assessment | HIGH | MEDIUM | P1 |
| Higher time-frame price structure | HIGH | MEDIUM | P1 |
| AI entry quality score | HIGH | HIGH | P1 |
| Structured card report (bilingual) | HIGH | MEDIUM | P1 |
| Watchlist management | HIGH | LOW | P1 |
| Monthly + on-demand report cadence | HIGH | LOW | P1 |
| Data freshness / stale data flags | HIGH | LOW | P1 |
| Mixed-signal representation | MEDIUM | MEDIUM | P1 |
| Explainable reasoning chain | HIGH | MEDIUM | P1 |
| Report history archive | MEDIUM | LOW | P2 |
| Email digest on updates | MEDIUM | LOW | P2 |
| PDF export | LOW | LOW | P2 |
| Additional asset classes | HIGH | HIGH | P3 |
| Multi-user / auth | MEDIUM | HIGH | P3 |
| Screener / discovery | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Vietstock / VietstockFinance | Simply Wall St (global analog) | Stratum approach |
|---------|------------------------------|-------------------------------|-----------------|
| Macro regime classification | Not present — news and market commentary, not regime analysis | Not present | Core differentiator — regime is the organizing frame for all analysis |
| Historical analogues | Not present | Not present | Core differentiator — current regime mapped to historical precedents |
| Asset valuation vs historical range | Basic P/E data present; no regime-relative context | DCF-based fair value (global stocks only) | Regime-relative valuation: where does this asset sit given the macro backdrop? |
| Higher time-frame price structure | Technical analysis (daily/intraday focus) | Not present | Weekly/monthly only; explicitly framed as entry context not trading signals |
| Entry quality score | Not present | "Snowflake" score (valuation, health, dividends, growth) — no macro layer | AI-derived multi-layer synthesis with explicit reasoning chain |
| Vietnamese language | Yes | No | Yes — primary language; report generation must be native Vietnamese not translated |
| Gold analysis | Gold price data only | Not present | Fundamental: ETF flows, central bank buying, real yield context, macro regime framing |
| Explainability | Not applicable (data portal, not AI advisor) | Partial — methodology page but no per-report reasoning | Full: every step in analysis chain shows its inputs, data source, and output |
| Mixed-signal disclosure | Not applicable | Not applicable | Explicit: reports show confidence level and flag when signals conflict |
| Watchlist | Yes | Yes | Yes — watchlist is the entry point for report generation |
| Portfolio tracking | Yes (holdings, P&L) | Yes (portfolio management) | Deliberately excluded — watchlist only |
| Real-time data | Yes | Yes | Deliberately excluded — weekly/monthly cadence only |

---

## Sources

- Vietstock platform features: https://en.vietstock.vn/about-us.htm (MEDIUM confidence — official source)
- Simply Wall St features: https://simplywall.st/ (HIGH confidence — official source)
- FactSet macro regime framework: https://insight.factset.com/mapping-asset-returns-to-economic-regimes-a-practical-investors-guide (MEDIUM confidence)
- World Gold Council ETF flow data: https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows (HIGH confidence — official source)
- Koyfin platform comparison: https://www.koyfin.com/blog/best-platform-investment-research-portfolio-analytics-client-proposals/ (MEDIUM confidence)
- Investment research platform features survey: https://visualping.io/blog/investment-research-tools (LOW confidence — aggregator)
- Vietnam retail investor behavior: https://pmc.ncbi.nlm.nih.gov/articles/PMC6140283/ (MEDIUM confidence — peer-reviewed survey)
- Vietnam emerging market upgrade context: https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse (MEDIUM confidence — FTSE Russell official)
- CFA Institute Explainable AI in Finance: https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance (HIGH confidence — CFA Institute official)

---
*Feature research for: Long-term investment advisor platform — Vietnamese market, macro-fundamental analysis*
*Researched: 2026-03-03*
