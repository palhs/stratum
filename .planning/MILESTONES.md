# Project Milestones: Stratum

## v2.0 Analytical Reasoning Engine (Shipped: 2026-03-17)

**Delivered:** Multi-step AI reasoning pipeline that transforms raw market data into grounded, bilingual entry quality assessments — served via FastAPI with background execution, SSE streaming, and Docker deployment.

**Phases completed:** 3-9 (+ 8.1 gap closure) — 8 phases, 28 plans

**Key accomplishments:**
- 7-node LangGraph StateGraph pipeline (macro regime, valuation, structure, conflict detection, entry quality, grounding check, report composition) with PostgreSQL checkpointing
- Neo4j knowledge graph: 17 macro regime nodes (2008-2025) with cosine-similarity HAS_ANALOGUE relationships and Gemini-generated narratives
- Triple-store hybrid retrieval: Neo4j CypherTemplateRetriever, Qdrant dense+sparse hybrid search, PostgreSQL direct queries — all with data freshness monitoring
- Bilingual report generation: Vietnamese primary (162-term financial dictionary + Gemini narrative rewrite) and English secondary, with DATA WARNING sections for stale data
- FastAPI reasoning-engine service: POST /reports/generate (202 + BackgroundTask), GET /reports/{id}, GET /reports/stream/{id} SSE, GET /health — Docker packaged with mem_limit 2g
- Production tooling: 20-stock batch validation script, Gemini spend cap (AI Studio), TTL-based checkpoint cleanup job

**Stats:**
- ~6,000 lines Python (app) + ~8,500 lines Python (tests) + ~2,200 lines scripts + ~400 lines SQL
- 8 phases, 28 plans, 182 commits
- 9 days from start to ship (2026-03-09 → 2026-03-17)
- 34/34 requirements satisfied, 0 gaps

**Git range:** `feat(03-01)` → `docs(09-03)`

**Known tech debt (accepted):**
- `get_all_analogues()` exported but uncalled by pipeline — dormant fallback
- SBV document corpus requires manual PDF placement (FOMC automated)
- AI Studio spend cap only — hard-stop protection, no tiered early warnings
- All LLM calls use gemini-2.5-pro — OpenRouter migration planned for cost optimization

---

## v1.0 Infrastructure and Data Ingestion (Shipped: 2026-03-09)

**Delivered:** Complete Docker infrastructure with dual-network isolation and automated data ingestion pipeline for Vietnamese stocks, gold, and macroeconomic indicators.

**Phases completed:** 1-2 (7 plans total)

**Key accomplishments:**
- Docker Compose stack with 7 services, dual ingestion/reasoning network isolation, profiles for selective startup, and VPS provisioning
- Storage schemas: PostgreSQL Flyway migrations (V1-V5), Neo4j constraints + APOC triggers, Qdrant 384-dim FastEmbed collections with alias versioning
- FastAPI data-sidecar with vnstock VN30 OHLCV (9,411 rows) and fundamentals (399 rows) ingestion
- Gold (FRED spot price + GLD ETF via yfinance) and FRED macroeconomic indicator ingestion (GDP, CPI, unemployment, rates)
- Pre-computed structure markers: moving averages, ATH/52w drawdowns, percentile rank (9,985 rows)
- Pipeline monitoring: run logging, row-count anomaly detection, n8n weekly/monthly workflows with Telegram error handler
- pytest suite: 46 pass, 13 skip (FRED auth gate by design), 0 fail — validating all 9 DATA requirements

**Stats:**
- 80 files created/modified
- 3,801 lines Python, 317 lines SQL, 216 lines Docker Compose
- 2 phases, 7 plans, 44 commits
- 6 days from start to ship (2026-03-03 → 2026-03-09)

**Git range:** `feat(01-01)` → `feat(02-05)`

**Known tech debt (accepted):**
- Telegram env vars not injected into n8n container (alerts silently fail)
- WGC monthly retry does not short-circuit on 501 (~21 min wasted/month)
- FRED_API_KEY requires manual .env.local setup

**What's next:** Next milestone will cover Phases 3-7 — retrieval validation, analytical reasoning nodes, synthesis/reports, API layer, and frontend.

---

