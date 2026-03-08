# Stratum

## What This Is

A long-term investment advisor platform for Vietnamese retail investors who want institutional-quality macro-fundamental analysis delivered in plain language. The platform analyzes macroeconomic regimes, asset valuations, and higher time-frame price structure to produce structured research reports that answer two questions: **what is worth holding** and **when is a reasonable time to enter**. Primary market is Vietnamese stocks and gold, with bilingual report output (Vietnamese and English).

## Core Value

Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.

## Requirements

### Validated

- ✓ Vietnamese stock OHLCV data ingestion via vnstock — v1.0
- ✓ Vietnamese stock fundamental data ingestion via vnstock — v1.0
- ✓ Gold price data ingestion from FRED — v1.0
- ✓ Gold ETF flow and central bank buying data ingestion (WGC 501 stub, GLD ETF working) — v1.0
- ✓ FRED macroeconomic indicator ingestion (GDP, CPI, unemployment, rates) — v1.0
- ✓ Pre-computed structure markers (MAs, drawdowns, percentiles) — v1.0
- ✓ Timestamp convention (data_as_of + ingested_at) on every row — v1.0
- ✓ Pipeline run logging with success/failure status — v1.0
- ✓ Row-count anomaly detection for vnstock — v1.0
- ✓ Docker Compose infrastructure on self-hosted VPS — v1.0
- ✓ Storage layer as hard boundary between n8n and LangGraph — v1.0

### Active (v2.0)

- [ ] Macro regime classification against historical analogues (quantitative similarity + LLM interpretation)
- [ ] Asset valuation assessment relative to historical range and current regime
- [ ] Higher time-frame price structure analysis (weekly/monthly) for entry timing context
- [ ] AI-derived entry quality score combining all three layers
- [ ] Plain-language narrative reports in structured card format (JSON + Markdown output)
- [ ] Bilingual report generation (Vietnamese and English)
- [ ] Graceful handling of missing/stale data with explicit flagging in reports
- [ ] Mixed-signal macro regime representation (partial matches, low-confidence analogues)
- [ ] Conflicting signal handling — "strong thesis, weak structure" outputs
- [ ] Explainable multi-step reasoning — each step has clear input, data source, and output
- [ ] Retrieval layer: LlamaIndex over PostgreSQL + Neo4j + Qdrant (manually curated document corpus)
- [ ] Document corpus: Fed minutes, SBV reports, VN company earnings (manually curated for v2.0)

### Deferred (v3.0)

- [ ] User watchlist management
- [ ] Monthly report generation cadence with on-demand capability for new watchlist additions
- [ ] API layer (FastAPI endpoints for frontend)
- [ ] Frontend (Next.js report UI with TradingView charts)
- [ ] Automated document ingestion pipelines (Fed, SBV, earnings)
- [ ] Local LLM fallback (Ollama)

### Out of Scope

- Real-time or intraday data — weekly/monthly cadence only
- Short-term technical analysis or trading signals — not a trading tool
- Holdings tracking, cost basis, or P&L — watchlist only at launch
- BTC, bonds, or other asset classes beyond VN stocks and gold — deferred post-launch
- US/global stock markets — VN-primary, global expansion later
- Mobile app — web-first
- Multi-user scale infrastructure — single user (self) at launch, productize later

## Current Milestone: v2.0 Analytical Reasoning Engine

**Goal:** Build the multi-step AI reasoning pipeline that transforms raw market data into actionable entry quality assessments with explainable analysis.

**Target features:**
- Retrieval layer (LlamaIndex) over all three storage backends
- Macro regime classification: quantitative similarity search → LLM interpretation
- Asset valuation assessment relative to historical range and current regime
- HTF price structure analysis for entry timing context
- AI-derived entry quality score combining all three layers
- Bilingual report generation (JSON + Markdown) via Gemini API
- Manually curated document corpus (Fed minutes, SBV reports, VN earnings)

## Context

Shipped v1.0 with 3,801 lines of Python, 317 lines of SQL, 216 lines of Docker Compose.

Tech stack operational: Docker Compose (7 services), PostgreSQL (Flyway V1-V5), Neo4j (constraints + APOC triggers), Qdrant (384-dim FastEmbed), n8n (weekly/monthly workflows), FastAPI data-sidecar.

Data flowing: VN30 stocks (9,411 OHLCV rows, 399 fundamentals), gold (FRED spot + GLD ETF), FRED macro indicators (GDP, CPI, unemployment, rates), structure markers (9,985 rows).

Known limitations: WGC Goldhub is JS-rendered — no automated ingestion, returns 501. Telegram alerts not yet wired (env vars not injected into n8n container).

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
| LLM (v2.0) | Gemini API | Gemini only for v2.0; local LLM fallback deferred to v3.0 |
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
| n8n/LangGraph separation at storage boundary | Keep ingestion pipeline decoupled from AI reasoning — each layer focused | ✓ Good — enforced via Docker dual-network isolation |
| Report quality as v1 success metric over UI/scale | One excellent report proves the concept; polish and users follow | — Pending |
| VCI source exclusively for vnstock | TCBS source broken as of 2025 | ✓ Good — VCI stable through v1.0 |
| VN30 symbols fetched dynamically | Never hard-coded; uses Listing.symbols_by_group() | ✓ Good — adapts to VN30 composition changes |
| SQLAlchemy Core over ORM declarative | Required for pg_insert().on_conflict_do_update() upsert pattern | ✓ Good — clean upsert across all services |
| FastEmbed 384-dim over OpenAI 1536-dim | Memory-efficient for 8GB VPS; BAAI/bge-small-en-v1.5 | ✓ Good — locked for Qdrant collections |
| Full recompute for structure markers | At VN30 scale (~7,800 rows) < 5s; incremental adds complexity with no gain | ✓ Good — simplicity preserved |
| WGC 501 stub (no Playwright) | Goldhub JS-rendered, no stable API; Chromium too heavy for sidecar | ⚠️ Revisit — manual CSV import needed |
| vnstock pinned to 3.4.2 | 3.2.3 → 3.4.2 breaking change; version locked | ✓ Good — prevents silent breakage |
| n8n pinned to 2.10.2 | 1.78.0 workflow JSON format incompatible | ✓ Good — stable import format |

| Gemini API only for v2.0 | Simplify reasoning pipeline; validate quality before adding fallback complexity | — Pending |
| Manual document corpus for v2.0 | Validate reasoning quality with curated docs before automating ingestion | — Pending |
| Split v2.0 (engine) / v3.0 (UI) | Ship analytical quality first; frontend delivery layer follows | — Pending |
| Both-layer regime classification | Quantitative similarity for candidate analogues, LLM for interpretation and narration | — Pending |

---
*Last updated: 2026-03-09 after v2.0 milestone start*
