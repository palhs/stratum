# Stratum

## What This Is

A long-term investment advisor platform for Vietnamese retail investors who want institutional-quality macro-fundamental analysis delivered in plain language. The platform analyzes macroeconomic regimes, asset valuations, and higher time-frame price structure to produce structured research reports that answer two questions: **what is worth holding** and **when is a reasonable time to enter**. Primary market is Vietnamese stocks and gold, with bilingual report output (Vietnamese and English).

## Core Value

Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Macro regime classification against historical analogues
- [ ] Asset valuation assessment relative to historical range and current regime
- [ ] Higher time-frame price structure analysis (weekly/monthly) for entry timing context
- [ ] AI-derived entry quality score combining all three layers
- [ ] Plain-language narrative reports in structured card format
- [ ] Bilingual report generation (Vietnamese and English)
- [ ] Vietnamese stock data ingestion via vnstock
- [ ] Gold fundamental data ingestion (World Gold Council, ETF flows)
- [ ] Macroeconomic data ingestion (FRED)
- [ ] User watchlist management
- [ ] Monthly report generation cadence with on-demand capability for new watchlist additions
- [ ] Graceful handling of missing/stale data with explicit flagging in reports
- [ ] Mixed-signal macro regime representation (partial matches, low-confidence analogues)
- [ ] Conflicting signal handling — "strong thesis, weak structure" outputs
- [ ] Explainable multi-step reasoning — each step has clear input, data source, and output

### Out of Scope

- Real-time or intraday data — weekly/monthly cadence only
- Short-term technical analysis or trading signals — not a trading tool
- Holdings tracking, cost basis, or P&L — watchlist only at launch
- BTC, bonds, or other asset classes beyond VN stocks and gold — deferred post-launch
- US/global stock markets — VN-primary, global expansion later
- Mobile app — web-first
- Multi-user scale infrastructure — single user (self) at launch, productize later

## Context

- The founder is both the domain expert and first user — currently performs this macro-fundamental analysis manually and wants to automate and eventually productize the process
- Vietnamese stock market data comes from vnstock (https://github.com/thinh-vu/vnstock.git), an open-source Python library
- All external data sources are free tier at launch (FRED, Simfin, World Gold Council, vnstock)
- Gold data from World Gold Council has significant publication lag (1–2 months) — reasoning pipeline must account for this
- Central bank gold buying data is often revised after initial publication
- Some macro environments produce mixed signals that don't fit clean regime labels
- Asset valuations can reach historically unprecedented levels — system must handle out-of-range values
- v1 success is defined by report quality matching the founder's manual analytical standard, not by UI polish or user scale

## Constraints

- **Deployment**: Self-hosted VPS — minimal infrastructure cost
- **Architecture**: Storage layer (PostgreSQL, Neo4j, Qdrant) is the hard boundary between ingestion (n8n) and reasoning (LangGraph) — they never communicate directly
- **Data cadence**: Weekly and monthly only — no real-time feeds
- **Reasoning**: All AI analysis must be explainable step-by-step — no black-box single-prompt analysis
- **Computation**: Pre-computed structure markers (MAs, drawdown from ATH) calculated during ingestion by n8n, stored in PostgreSQL — LangGraph reads them, never computes on the fly
- **Report style**: Research report aesthetic, not trading terminal — narrative-first, charts support the story
- **Language**: User-facing content accessible to retail investors — no jargon-heavy output
- **Budget**: Free-tier data sources, self-hosted — keep costs minimal at launch

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Pipeline orchestration | n8n | Cron, retry, visual debugging, error alerting built-in |
| AI reasoning | LangGraph | Multi-step chain control, programmatic agent behavior |
| RAG & retrieval | LlamaIndex | Native Qdrant + Neo4j integration in single retrieval layer |
| LLM | Gemini API / local LLM | Gemini for quality, local LLM for cost/privacy flexibility |
| Structured storage | PostgreSQL | Fundamental data + weekly/monthly OHLCV — sufficient at this cadence |
| Knowledge graph | Neo4j | Macro regime relationships, historical analogues, asset correlations |
| Vector store | Qdrant | Semantic retrieval over earnings transcripts, Fed minutes, macro reports |
| Backend | FastAPI | Async-native, suits variable-time reasoning pipeline |
| Auth & user data | Supabase | Auth out of the box, UUID user IDs mirror into PostgreSQL/Neo4j |
| Frontend | Next.js | SSR, report-style UI |
| Charting | TradingView Lightweight Charts | Open source, embeddable, production-grade |
| VN stock data | vnstock | Open-source Python library for Vietnamese market data |

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| VN stocks as primary market | Founder's expertise and first-user market | — Pending |
| AI-derived entry quality score (not formula-based) | AI reasons through layers qualitatively with explanation, rather than encoding a fixed weighting formula | — Pending |
| Bilingual reports (VN + EN) | Primary audience is Vietnamese investors, English for broader reach | — Pending |
| Self-hosted VPS over cloud managed | Cost control at launch, single-user scale doesn't need managed services | — Pending |
| Free-tier data sources at launch | Validate analysis quality before investing in premium data | — Pending |
| n8n/LangGraph separation at storage boundary | Keep ingestion pipeline decoupled from AI reasoning — each layer focused | — Pending |
| Report quality as v1 success metric over UI/scale | One excellent report proves the concept; polish and users follow | — Pending |

---
*Last updated: 2026-03-03 after initialization*
