# Stratum

## What This Is

A long-term investment advisor platform for Vietnamese retail investors that combines AI-powered macro regime analysis, valuation context, and price structure into grounded, bilingual research reports. The reasoning pipeline produces structured entry quality assessments answering: **what is worth holding** and **when is a reasonable time to enter**. Primary market is Vietnamese stocks and gold, with bilingual output (Vietnamese primary, English secondary).

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
- ✓ Macro regime classification with probability distribution and mixed-signal handling — v2.0
- ✓ Regime-relative valuation for VN equities and gold — v2.0
- ✓ Price structure interpretation from pre-computed markers — v2.0
- ✓ Qualitative entry quality tier (Favorable/Neutral/Cautious/Avoid) with 3 sub-assessments — v2.0
- ✓ Grounding check verifying numeric claims trace to database records — v2.0
- ✓ LangGraph StateGraph with PostgreSQL checkpointing — v2.0
- ✓ Conflicting signal handling ("strong thesis, weak structure") — v2.0
- ✓ Structured JSON report with card sections — v2.0
- ✓ Markdown report rendering — v2.0
- ✓ Bilingual generation (Vietnamese + English) with 162-term financial dictionary — v2.0
- ✓ DATA WARNING sections for stale data — v2.0
- ✓ Reports stored in PostgreSQL — v2.0
- ✓ FastAPI service with background task execution — v2.0
- ✓ SSE streaming for pipeline progress — v2.0
- ✓ Health endpoint for Docker monitoring — v2.0
- ✓ Docker-packaged reasoning-engine service — v2.0
- ✓ 20-stock batch validation with memory baseline — v2.0
- ✓ Gemini API spend alerts configured — v2.0
- ✓ Checkpoint cleanup job (TTL-based purge) — v2.0

## Current Milestone: v3.0 Product Frontend & User Experience

**Goal:** Make Stratum usable as a product — dashboard, watchlist, report browsing, auth, and automated document ingestion for a small group of invite-only users.

**Target features:**
- Dashboard with watchlist cards (entry quality tier, sparkline, last report date)
- Summary + expand report view with interactive TradingView chart (MAs, zoom)
- Report history timeline per ticker
- Manual "Generate Report" with SSE progress
- Supabase auth (invite-only, per-user watchlists)
- Watchlist management (add/remove tickers)
- Automated document ingestion pipelines (Fed minutes, SBV reports, earnings)
- Comprehensive Vietnamese financial terminology dictionary

### Active (v3.0)

- [ ] Dashboard with watchlist cards showing entry quality tier, sparkline chart, and last report date
- [ ] Summary + expand report view with interactive TradingView chart (MAs, zoom)
- [ ] Report history timeline per ticker with assessment change tracking
- [ ] Manual report generation trigger with SSE progress display
- [ ] Supabase authentication with invite-only user accounts
- [ ] Per-user watchlist management (add/remove tickers)
- [ ] Automated document ingestion pipelines (Fed minutes, SBV reports, earnings)
- [ ] Comprehensive Vietnamese financial terminology dictionary expansion

### Out of Scope

- Local LLM fallback via Ollama — Gemini API working, defer to v4.0
- OpenRouter integration for LLM cost optimization — defer to v4.0
- Real-time or intraday data — weekly/monthly cadence only
- Short-term technical analysis or trading signals — not a trading tool
- Holdings tracking, cost basis, or P&L — watchlist only at launch
- BTC, bonds, or other asset classes beyond VN stocks and gold — deferred post-launch
- US/global stock markets — VN-primary, global expansion later
- Mobile app — web-first
- Multi-user scale infrastructure — single user (self) at launch, productize later
- Single numeric entry quality score (e.g., 7.3/10) — qualitative tier is the correct output
- AI chat / Q&A over reports — unpredictable quality, cost risk
- Backtesting of entry quality — VN30 history too short for statistical significance

## Context

Shipped v2.0 with ~6,000 lines Python (app), ~8,500 lines Python (tests), ~2,200 lines scripts, ~400 lines SQL.

Tech stack operational: Docker Compose (8 services), PostgreSQL (Flyway V1-V7), Neo4j (17 regime nodes, HAS_ANALOGUE relationships), Qdrant (macro_docs + earnings_docs hybrid collections), FastAPI reasoning-engine with SSE streaming.

Pipeline architecture: prefetch (3-store retrieval) → 7-node LangGraph graph (macro_regime → valuation → structure → conflict → entry_quality → grounding_check → compose_report) → bilingual output → PostgreSQL storage. All labels deterministic; LLM generates narratives only.

Known limitations: WGC Goldhub returns 501 (JS-rendered). SBV document corpus requires manual PDF curation. AI Studio spend cap only (no tiered Cloud Billing alerts). All LLM calls currently use gemini-2.5-pro via direct API.

## Constraints

- **Deployment**: Self-hosted VPS — minimal infrastructure cost
- **Architecture**: Storage layer (PostgreSQL, Neo4j, Qdrant) is the hard boundary between ingestion (n8n) and reasoning (LangGraph) — they never communicate directly
- **Data cadence**: Weekly and monthly only — no real-time feeds
- **Reasoning**: All AI analysis must be explainable step-by-step — labels computed deterministically in Python, LLM generates narratives
- **Computation**: Pre-computed structure markers calculated during ingestion, stored in PostgreSQL — LangGraph reads, never computes
- **Report style**: Research report aesthetic — narrative-first, conclusion-first ordering
- **Language**: Vietnamese primary, English secondary — accessible to retail investors
- **Budget**: Free-tier data sources, self-hosted, Gemini API with spend cap

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Pipeline orchestration | n8n | Cron, retry, visual debugging, error alerting built-in |
| AI reasoning | LangGraph | Multi-step chain control with PostgreSQL checkpointing |
| RAG & retrieval | LlamaIndex | Native Qdrant + Neo4j integration in single retrieval layer |
| LLM | Gemini 2.5 Pro (via API) | Structured output + native Vietnamese; OpenRouter migration planned |
| Structured storage | PostgreSQL | Fundamental data, reports, report jobs, LangGraph checkpoints |
| Knowledge graph | Neo4j | Macro regime nodes, HAS_ANALOGUE relationships |
| Vector store | Qdrant | Hybrid dense+sparse search over FOMC/SBV/earnings docs |
| Backend | FastAPI | Async-native, BackgroundTask execution, SSE streaming |
| Auth & user data | Supabase (v3.0) | Auth out of the box |
| Frontend | Next.js (v3.0) | SSR, report-style UI |
| Charting | TradingView Lightweight Charts (v3.0) | Open source, embeddable |
| VN stock data | vnstock 3.4.2 | Open-source Python library for Vietnamese market data |

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| VN stocks as primary market | Founder's expertise and first-user market | ✓ Good — 30 VN30 tickers supported |
| Qualitative tier over numeric score | AI reasons through layers qualitatively; numeric score encourages "score = buy" | ✓ Good — 4-tier system works well |
| Bilingual reports (VN + EN) | Primary audience Vietnamese, English for broader reach | ✓ Good — 162-term dictionary + Gemini rewrite |
| Self-hosted VPS over cloud managed | Cost control, single-user scale | ✓ Good — all services within 2GB mem_limit |
| Free-tier data sources at launch | Validate analysis quality before investing in premium data | ✓ Good — vnstock + FRED sufficient for v2.0 |
| n8n/LangGraph separation at storage boundary | Keep ingestion decoupled from reasoning | ✓ Good — enforced via Docker dual-network isolation |
| Deterministic labels, LLM for narrative only | Reliable classification; LLM augments, doesn't decide | ✓ Good — grounding check validates all claims |
| Gemini API only for v2.0 | Simplify reasoning pipeline; validate quality first | ✓ Good — OpenRouter migration planned for cost optimization |
| Manual document corpus for v2.0 | Validate reasoning quality with curated docs | ✓ Good — FOMC automated, SBV manual |
| Split v2.0 (engine) / v3.0 (UI) | Ship analytical quality first; frontend follows | ✓ Good — engine fully validated |
| Both-layer regime classification | Quantitative similarity for candidates, LLM for interpretation | ✓ Good — mixed-signal handling works at 70% threshold |
| SQLAlchemy Core over ORM | Required for pg_insert().on_conflict_do_update() upsert pattern | ✓ Good — clean upsert across all services |
| FastEmbed 384-dim over OpenAI 1536-dim | Memory-efficient for 8GB VPS | ✓ Good — locked for Qdrant collections |
| AsyncPostgresSaver for checkpointing | LangGraph Platform TTL not available self-hosted; custom cleanup job needed | ✓ Good — TTL cleanup implemented |
| AI Studio spend cap (not Cloud Billing) | Simpler setup; hard-stop protection sufficient for dev | ⚠️ Revisit — upgrade to Cloud Billing for tiered alerts in production |
| WGC 501 stub (no Playwright) | Goldhub JS-rendered, no stable API | ⚠️ Revisit — manual CSV import needed |

---
*Last updated: 2026-03-17 after v3.0 milestone start*
