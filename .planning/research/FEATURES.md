# Feature Research

**Domain:** Investment advisor product frontend — dashboard, watchlist, report browsing, auth, document ingestion, dictionary expansion
**Researched:** 2026-03-17
**Confidence:** MEDIUM-HIGH — Financial platform UX patterns are HIGH confidence (well-documented industry conventions); Supabase invite-only auth patterns are MEDIUM confidence (documented but with known quirks); FOMC automated ingestion is HIGH confidence (RSS feed verified); SBV automated ingestion is LOW confidence (no stable Vietnamese central bank feed confirmed); TradingView Lightweight Charts + Next.js integration is HIGH confidence (official examples exist).

---

## Scope Note

This file covers the **v3.0 milestone** only: adding a product frontend and user experience layer on top of the v2.0 analytical reasoning engine. Features already delivered in v1.0 and v2.0 are listed as **existing backend dependencies**, not as features to build.

---

## Existing Backend Available as Foundation

The following capabilities exist and feed v3.0 features directly:

| Capability | Backend Location | Notes |
|-----------|-----------------|-------|
| POST /reports/generate | FastAPI reasoning-engine | Triggers background report generation, returns job_id |
| GET /reports/{id} | FastAPI reasoning-engine | Returns full report JSON + markdown (bilingual) |
| GET /reports/stream/{id} | FastAPI reasoning-engine | SSE stream of pipeline progress events |
| GET /health | FastAPI reasoning-engine | Docker health monitoring |
| Reports table in PostgreSQL | PostgreSQL | Stores report_json, report_markdown, ticker, created_at, entry_quality tier |
| 4-tier entry quality labels | Analytical engine output | Favorable / Neutral / Cautious / Avoid |
| 162-term Vietnamese dictionary | In-process during report generation | Content asset, not a separate service |
| Pre-computed structure markers | PostgreSQL | MAs, drawdowns, OHLCV — available for charting |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users of any investment research platform assume exist. Missing any of these makes the product feel incomplete or broken.

| Feature | Why Expected | Complexity | Backend Dependency | Notes |
|---------|--------------|------------|-------------------|-------|
| Dashboard with watchlist cards | Any investment platform (Robinhood, Bloomberg, Vietstock) shows watched assets in a card list with summary status; it is the product's entry point | MEDIUM | GET /reports/{ticker} for latest report, PostgreSQL reports table for entry_quality tier and created_at | Cards must show: ticker symbol, entry quality tier badge (color-coded), last report date, sparkline of OHLCV; blank state for tickers with no reports yet |
| Sparkline chart on watchlist card | Robinhood, Bloomberg, Simply Wall St all use mini-charts for quick price context on list views; absent sparkline makes cards feel data-poor | LOW | OHLCV data in PostgreSQL (pre-computed weekly series) | TradingView Lightweight Charts line series; 52-week weekly close prices; no axis labels; hover tooltip optional |
| Report summary + full expand | Financial research platforms (FactSet, Simply Wall St) use progressive disclosure: summary → expand for full narrative; prevents information overload on first view | MEDIUM | GET /reports/{id} returns structured JSON with card sections | Summary view: entry quality tier, 3 sub-assessment badges, one-line verdict; Expand: full bilingual markdown rendered card by card |
| TradingView chart in report view | Interactive price chart with MA overlays is standard in any analytical platform targeting technical-aware users; absent chart forces users to open external tools | MEDIUM | OHLCV + MA data in PostgreSQL | TradingView Lightweight Charts (open-source, 45KB); show 50MA and 200MA as line series; weekly candles; zoom to 1Y/2Y/5Y/All; no real-time feed needed — static weekly data |
| Report history timeline per ticker | Every research platform with repeat coverage (Morningstar, MSCI) shows historical reports; users want to see how assessment changed over time | MEDIUM | PostgreSQL reports table with created_at + entry_quality per ticker | Vertical timeline or table: date, entry quality tier badge, one-line summary; click to open full historical report; assessment change indicators (upgrade/downgrade arrows) |
| Manual "Generate Report" trigger | On-demand generation is the core user action; users need a visible, accessible button to request a fresh report on a specific ticker | LOW | POST /reports/generate + GET /reports/stream/{id} SSE endpoint already exist | Button per ticker card; triggers POST, then opens SSE progress display; button disabled during active generation |
| SSE progress display | Any multi-step AI pipeline with >10s runtime needs visible progress; silent loading spinner creates anxiety and confusion about whether system is working | LOW | GET /reports/stream/{id} SSE already implemented in FastAPI | Progress log showing named nodes as they complete: "Macro regime classified", "Valuation assessed", "Structure interpreted", "Entry quality determined", "Report composed"; estimated time remaining optional |
| Watchlist management (add/remove) | Every watchlist product allows editing the watchlist; static or admin-only watchlists feel broken | LOW | New FastAPI endpoint or direct Supabase RLS table; PostgreSQL or Supabase watchlists table per user | Ticker search/autocomplete from VN30 list (bounded — only 30 stocks + gold); add to watchlist button; remove via long-press or edit mode; max ~30 items at current scale |
| Authentication (login/logout) | Any product with per-user state requires auth; without auth, watchlists cannot be persisted and the product cannot serve multiple invite users | MEDIUM | Supabase Auth (in stack); new users table or profiles table linked to Supabase user_id | Email + password login; magic link login as fallback; session persistence; logout clears local session |
| Empty/loading states | Dashboard without graceful empty states (no reports yet, loading, error) feels unfinished; this is a baseline UX expectation | LOW | None — pure frontend | Skeleton loaders on card list; "No reports yet — click Generate" on empty ticker card; error toast on failed generation |

### Differentiators (Competitive Advantage)

Features that distinguish Stratum from existing Vietnamese investment platforms and from generic AI financial tools at the UX layer.

| Feature | Value Proposition | Complexity | Backend Dependency | Notes |
|---------|-------------------|------------|-------------------|-------|
| Entry quality tier badge as primary signal | Vietstock and CafeF show price data and news; no Vietnamese platform surfaces a synthesized entry quality tier front-and-center on the watchlist card; this is the analytical engine's output made visible | LOW | entry_quality field in PostgreSQL reports table | Color-coded badge: Favorable (green), Neutral (yellow/amber), Cautious (orange), Avoid (red); displayed as the most prominent element on the card, not buried in the report |
| Assessment change tracking across history | Morningstar and FactSet track rating upgrades/downgrades; no Vietnamese retail platform does this; showing "Cautious → Neutral (this week)" in the report timeline is a differentiator for users who monitor regime shifts | MEDIUM | Multiple reports per ticker in PostgreSQL with created_at; requires comparison logic | Compute delta between consecutive entry_quality values; render as "upgrade arrow" (green) or "downgrade arrow" (red) in timeline; highlight when tier changes |
| Bilingual toggle on full report | No Vietnamese investment platform offers side-by-side or toggle bilingual report viewing; English version is valuable for users who prefer reading analytical terms in English | LOW | Both report_markdown (vi) and report_markdown_en (en) stored in PostgreSQL | Language toggle button (VI / EN) at top of report view; switches rendered markdown; default to Vietnamese; remembers user preference via localStorage |
| Invite-only access with pre-seeded watchlists | Exclusive early-user access creates trust signal; pre-seeded watchlists for invited users (e.g., VN30 top 10 by market cap) reduce time-to-value on first login | MEDIUM | Supabase Auth admin.inviteUserByEmail(); per-user watchlists table; seed script for initial watchlist entries | Supabase invite flow: admin calls inviteUserByEmail() from server; user clicks invite link, sets password; signup disabled in Supabase dashboard; watchlist seeded on first login via trigger or onboarding step |
| Automated FOMC minutes ingestion | Most platforms rely on manual document curation; automating FOMC minutes ingestion keeps the macro context fresh without admin burden; Federal Reserve publishes an RSS feed and consistent URL pattern for minutes | MEDIUM | n8n (existing orchestrator); Qdrant macro_docs collection (existing); FastEmbed embedding model (existing); Fed RSS feed at federalreserve.gov/feeds/feeds.htm | n8n cron job: poll Fed RSS feed → detect new minutes release → download PDF → extract text → chunk → embed (FastEmbed 384-dim) → upsert into Qdrant macro_docs; FOMC meets 8x/year; minutes released ~3 weeks after meeting |
| Automated SBV report ingestion (where available) | State Bank of Vietnam publishes monetary policy reports; automating ingestion keeps Vietnamese macro context current | HIGH | n8n (existing); Qdrant macro_docs collection; SBV website structure is unstable — no confirmed RSS feed | SBV does not publish a stable RSS or structured API; automated ingestion requires scraping sbv.gov.vn which is fragile; consider n8n HTTP Request node + CSS selector scraping as starting point; may require manual fallback; flag as LOW confidence until tested |
| Dictionary expansion for earnings-season terminology | Earnings season produces specialized Vietnamese financial vocabulary (KQKD, EBITDA transliteration, sector-specific terms) that the 162-term base dictionary does not cover; expanding the dictionary improves report readability for non-financial users | MEDIUM | In-process during report generation; Vietnamese financial term dictionary is a content asset loaded by the bilingual ReportComposer node | Content work: identify gaps by reviewing generated reports for missing or inconsistent term translations; target +80–120 terms covering earnings vocabulary, sector-specific terms, and VAS-to-IFRS mapping |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem natural extensions of the product but create disproportionate problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time price feed on dashboard | "Show me the current price" is the first thing users ask for; feels like a dashboard gap | Requires a live data subscription (vnstock has rate limits; no free real-time VN stock feed exists); contradicts the weekly/monthly analytical cadence; creates expectation mismatch between live price and weekly report data; the platform answers "should I enter" not "what is the price right now" | Show last_close_price from the most recent OHLCV row with an explicit "as of [date]" label; link to Vietstock/CafeF for live price lookup |
| Portfolio P&L tracking (cost basis, returns) | Natural extension after watching stocks and reading reports | Requires holdings data input (privacy risk), cost basis calculation, multi-transaction history; fundamentally different product scope; opens compliance questions in VN financial regulations if advice + holdings combine | Watchlist only at launch; Stratum answers "conditions for entry" not "how is my position performing" |
| Push notifications for regime changes | "Alert me when the macro regime changes" is the natural evolution of regime monitoring | Regime classification runs on weekly/monthly cadence; push infrastructure (FCM, APNs, or email delivery service) adds ops complexity; false urgency from incremental regime shifts contradicts the long-term analytical frame | Weekly digest email (or scheduled n8n notification) with "regime unchanged / regime shifted" status; use n8n's built-in email alerting which is already operational |
| AI chat / Q&A over reports | "Ask the report a question" is the common AI product expectation in 2026 | Uncontrolled LLM responses over financial reports create liability; cost scales non-linearly; harder to ensure grounding; may contradict structured report findings; investment advice regulations in Vietnam require controlled, auditable outputs | Deep report expand view with all analytical reasoning visible; if a question recurs, add it as a structured card to the report template |
| PDF export of reports | "Save and share my report" is a common user request | PDF generation (Puppeteer, wkhtmltopdf, react-pdf) adds a dependency; PDF styling is a separate implementation concern; bilingual PDF layout is complex; reports are structured markdown — already printable via browser print | Browser print CSS (print stylesheet) for the report view; this handles 90% of the export use case without a PDF library |
| User-submitted tickers beyond VN30 + gold | "Can I add US stocks or crypto?" | Data ingestion for non-VN30 tickers requires new vnstock integration work; US stocks require a different data source entirely; gold is already covered; expands scope dramatically before product is validated with the primary audience | Hard-code the supported ticker universe to VN30 + XAU; ticker search autocomplete shows only supported tickers; display a clear "VN30 + gold only in v3.0" message |
| Social features (share watchlist, follow other users) | Sharing investment ideas is common on retail platforms (Stocktwits, CafeF community) | Requires user profiles, social graph, content moderation, notification infrastructure; adds complexity 10x beyond the core product; Vietnamese investment community platforms (CafeF) already exist for this | Focus on single-user analytical depth; defer social features until product-market fit is established for the core advisory function |

---

## Feature Dependencies

```
[Supabase Auth — invite-only setup]
    └──required by──> [Per-user watchlist management]
    └──required by──> [Report history (user-scoped access)]
    └──required by──> [Dashboard (authenticated route)]

[Per-user watchlist management]
    └──required by──> [Dashboard watchlist cards]
    └──required by──> [Entry quality badge display]
    └──required by──> [Sparkline chart on card]

[Dashboard watchlist cards]
    └──requires──> [GET /reports/{ticker} — latest report per ticker]
    └──requires──> [OHLCV data in PostgreSQL — for sparkline]

[Manual "Generate Report" trigger]
    └──requires──> [POST /reports/generate — existing FastAPI endpoint]
    └──requires──> [SSE progress display — connects to existing GET /reports/stream/{id}]

[SSE progress display]
    └──requires──> [GET /reports/stream/{id} — already implemented]

[Report summary + expand view]
    └──requires──> [GET /reports/{id} — returns structured JSON]
    └──enhances──> [Report history timeline — expand any historical report]

[Report history timeline]
    └──requires──> [Multiple reports per ticker in PostgreSQL]
    └──enhances──> [Assessment change tracking — computed from consecutive entries]

[TradingView chart in report view]
    └──requires──> [OHLCV + MA data in PostgreSQL — fetched via new GET /tickers/{symbol}/ohlcv endpoint]

[Bilingual toggle]
    └──requires──> [Both report_markdown (vi) and report_markdown_en (en) in PostgreSQL]

[Automated FOMC minutes ingestion]
    └──requires──> [n8n cron job (new workflow)]
    └──requires──> [Qdrant macro_docs collection (existing, populated in v2.0)]
    └──enhances──> [Report macro context depth]

[Automated SBV report ingestion]
    └──requires──> [n8n HTTP scraping workflow (new, fragile)]
    └──requires──> [Qdrant macro_docs collection (existing)]
    └──blocks on──> [SBV website stability investigation]

[Dictionary expansion]
    └──requires──> [162-term base dictionary (existing content asset)]
    └──enhances──> [Bilingual report quality — incremental improvement]
    └──does not block──> [Any v3.0 frontend feature]
```

### Dependency Notes

- **Auth must be the first feature built.** Watchlist management, per-user state, and authenticated routes all depend on Supabase Auth being configured. Without auth, there is no user_id to scope watchlist records to.

- **Supabase invite-only requires explicit configuration.** In Supabase dashboard, "Allow new users to sign up" must be disabled; user creation must happen exclusively via `auth.admin.inviteUserByEmail()` called from a trusted server context using the `service_role` key. There is a known issue where invite flows can fail when signups are disabled — the documented workaround is to ensure the Site URL points to a password-set page, not a login page.

- **New FastAPI endpoint needed for OHLCV data.** The TradingView chart requires OHLCV + MA data for a given ticker in a time-series format. The current FastAPI service exposes report endpoints only. A new `GET /tickers/{symbol}/ohlcv` endpoint reading from PostgreSQL is needed.

- **SSE progress display requires no new backend work.** The existing `GET /reports/stream/{id}` endpoint is already implemented. The v3.0 work is purely frontend: consume the SSE stream in Next.js and render named progress steps.

- **Dictionary expansion does not block frontend.** It is a content work stream that can run in parallel with frontend development and ships as an incremental improvement to report quality within any phase.

- **FOMC ingestion can ship independently of frontend.** The n8n workflow is self-contained: it writes to Qdrant and does not affect the frontend at all. It can be built and tested in parallel with any frontend phase.

- **SBV automated ingestion is high-risk.** The SBV website (sbv.gov.vn) does not publish a structured RSS feed or API. Automated ingestion requires CSS-selector scraping, which is fragile to layout changes. This should be prototyped before committing to it as a v3.0 deliverable; manual PDF upload via n8n file trigger is the safe fallback.

---

## MVP Definition

### v3.0 Launch: Product Frontend

Minimum viable product for v3.0 — what's needed to make Stratum usable as a product for a small group of invite-only users.

- [ ] Supabase Auth configured: signup disabled, invite-only via admin API — without this, per-user state is impossible
- [ ] Per-user watchlist management (add/remove from VN30 + gold universe) — without this, the dashboard has nothing to show
- [ ] Dashboard with watchlist cards (entry quality tier badge, last report date, sparkline) — the product's entry point
- [ ] Manual "Generate Report" trigger with SSE progress display — the core user action
- [ ] Report summary + full expand view with bilingual toggle — how users consume the analytical output
- [ ] TradingView chart in report view (weekly OHLCV + 50MA + 200MA) — contextualizes the price structure analysis
- [ ] Report history timeline per ticker (date, tier badge, assessment change indicator) — enables monitoring regime shifts over time
- [ ] New FastAPI GET /tickers/{symbol}/ohlcv endpoint — required for TradingView chart data

### Add After First Users Validate (v3.x)

Features to add once the core product is live and invite users are engaged:

- [ ] Automated FOMC minutes ingestion via n8n — trigger: macro context depth in reports is insufficient or manual curation becomes burdensome
- [ ] Dictionary expansion (+80–120 terms) — trigger: users report terminology confusion in Vietnamese reports
- [ ] Assessment change email digest — trigger: users ask for notifications when their watched tickers change tier

### Future Consideration (v4.0+)

Features to defer until product-market fit is established:

- [ ] Automated SBV ingestion — defer until sbv.gov.vn scraping is validated as stable; manual upload is sufficient for v3.0
- [ ] Browser print CSS for report export — low effort but not blocking; add after core is validated
- [ ] Additional ticker universe beyond VN30 + gold — defer until VN30 coverage is validated
- [ ] OpenRouter LLM cost optimization — already listed in PROJECT.md as v4.0 scope

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Supabase Auth (invite-only) | HIGH — gates all per-user features | MEDIUM | P1 |
| Per-user watchlist management | HIGH — gates dashboard content | LOW | P1 |
| Dashboard with watchlist cards | HIGH — product entry point | MEDIUM | P1 |
| Manual report trigger + SSE progress | HIGH — core user action | LOW (backend exists) | P1 |
| Report summary + expand view | HIGH — core report consumption | MEDIUM | P1 |
| TradingView chart in report view | HIGH — contextualizes analysis | MEDIUM | P1 |
| New GET /tickers/{symbol}/ohlcv endpoint | HIGH — required by chart | LOW | P1 |
| Report history timeline | HIGH — enables trend monitoring | MEDIUM | P1 |
| Bilingual toggle | MEDIUM — differentiator for EN readers | LOW | P2 |
| Assessment change indicators | MEDIUM — differentiator | LOW (computed from existing data) | P2 |
| Automated FOMC ingestion | MEDIUM — keeps macro context fresh | MEDIUM | P2 |
| Dictionary expansion | MEDIUM — report quality improvement | LOW (content work) | P2 |
| Automated SBV ingestion | MEDIUM — VN macro context | HIGH (scraping risk) | P3 |
| Assessment change email digest | LOW — nice-to-have at small scale | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v3.0 launch
- P2: Should have, add after core is working
- P3: Nice to have, v3.x or v4.0

---

## Competitor Feature Analysis

### How Existing Platforms Handle Each v3.0 Feature Area

| Feature | Vietstock / CafeF | Simply Wall St | Bloomberg Terminal | Stratum v3.0 approach |
|---------|-------------------|----------------|-------------------|----------------------|
| Dashboard watchlist | Price-focused card grid; no entry quality synthesis | Snowflake score card with 5 dimensions | Full-screen watchlist with all market data columns | Entry quality tier as primary signal; sparkline + last report date as secondary; minimal data density for analytical clarity |
| Report history timeline | CafeF news archive by ticker (not analytical reports) | Not present | Research report history per ticker (institutional) | Vertical timeline per ticker: entry quality tier per date; assessment change delta (upgrade/downgrade); click-to-expand full historical report |
| Interactive chart | Full technical analysis charting suite (daily/intraday) | Static price chart with fair value marker | Full Bloomberg charting | Weekly OHLCV + 50MA + 200MA only; TradingView Lightweight Charts; no intraday, no indicator overlays — matches analytical cadence |
| Auth / access control | Open registration | Free tier + paid subscription | License-based institutional access | Invite-only via Supabase admin invite flow; per-user watchlists via RLS; signup disabled |
| Report generation | Automated daily price/fundamental data pulls | Automated (data provider feeds) | Automated (Bloomberg data infrastructure) | Manual user-triggered via button; SSE progress display showing named LangGraph nodes; weekly cadence is appropriate for long-term analysis |
| Document corpus freshness | Aggregated news feeds (automated) | Not applicable | Automated Bloomberg data and news feeds | FOMC automated (n8n RSS); SBV manual/semi-automated; earnings corpus manual curation for v3.0 |
| Bilingual support | Vietnamese only | English only | English only; terminal has some language settings | Language toggle: Vietnamese (default) / English; both generated natively by analytical engine — not translated |
| On-demand generation | Not present — data refreshes automatically | Not present — refreshes on schedule | Not present — live data | Explicit "Generate Report" button per ticker; user controls when analysis runs; prevents unnecessary Gemini API spend |

---

## Complexity Notes per Feature

For roadmap phase planning:

**LOW implementation complexity (backend exists, frontend plumbing):**
- Manual report trigger + SSE progress display — POST and stream endpoints already implemented; frontend consumes existing API
- Bilingual toggle — both language variants already in PostgreSQL; toggle is a React state change
- Sparkline on watchlist card — OHLCV data in PostgreSQL; TradingView Lightweight Charts line series
- Assessment change indicators — compute delta between consecutive reports in same query; render arrow icon
- Watchlist add/remove — bounded ticker universe (VN30 + gold = ~31 items); simple Supabase RLS table
- Dictionary expansion — content work; no code changes required, only dictionary file updates

**MEDIUM implementation complexity (new patterns, well-understood):**
- Dashboard with watchlist cards — fetching latest report per ticker for N tickers; aggregate query optimization needed to avoid N+1 queries
- Report summary + expand view — rendering structured JSON report cards; markdown rendering for full view; React accordion or drawer pattern
- TradingView chart in report view — Next.js dynamic import (SSR-safe); custom data adapter feeding OHLCV from API; MA series overlay
- Report history timeline — query multiple reports per ticker ordered by created_at; render timeline component; click-to-expand historical reports
- Supabase Auth invite-only — configuration + admin API call from server; RLS policies for watchlists table; session handling in Next.js middleware
- Automated FOMC ingestion — n8n workflow: HTTP Request → PDF extraction → text chunking → FastEmbed → Qdrant upsert; deduplication by document date

**HIGH implementation complexity (fragile dependencies, novel integration):**
- New GET /tickers/{symbol}/ohlcv FastAPI endpoint — reads from PostgreSQL, returns time-series JSON; simple to build but must be added to the reasoning-engine FastAPI service and Docker image
- Automated SBV ingestion — sbv.gov.vn has no RSS feed; scraping requires CSS selector maintenance; PDF extraction from Vietnamese government PDFs is fragile; treat as experimental until validated

---

## Sources

- Supabase Auth invite-only pattern (sign up disabled): https://github.com/orgs/supabase/discussions/4296 (MEDIUM confidence — community discussion, known limitation documented)
- Supabase auth.admin.inviteUserByEmail() API: https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail (HIGH confidence — official docs)
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security (HIGH confidence — official docs)
- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/docs (HIGH confidence — official docs)
- TradingView + Next.js integration examples: https://github.com/tradingview/charting-library-examples (HIGH confidence — official repo)
- Federal Reserve RSS feeds (FOMC minutes): https://www.federalreserve.gov/feeds/feeds.htm (HIGH confidence — official)
- FOMC meeting calendar and minutes release schedule: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (HIGH confidence — official; minutes released ~3 weeks after meeting)
- n8n Qdrant Vector Store node: https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoreqdrant/ (HIGH confidence — official n8n docs)
- n8n PDF → Qdrant RAG workflow template: https://n8n.io/workflows/4400-build-a-pdf-document-rag-system-with-mistral-ocr-qdrant-and-gemini-ai/ (MEDIUM confidence — community template, validated pattern)
- FastAPI SSE implementation: https://fastapi.tiangolo.com/tutorial/server-sent-events/ (HIGH confidence — official FastAPI docs)
- SSE + Next.js progress tracking: https://medium.com/@ruslanfg/long-running-nextjs-requests-eff158e75c1d (MEDIUM confidence — community article)
- Robinhood watchlist card + sparkline design: https://robinhood.com/us/en/support/articles/watchlist-and-cards/ (HIGH confidence — official)
- Consumer Financial Protection Bureau Vietnamese financial glossary: https://files.consumerfinance.gov/f/documents/cfpb_adult-fin-ed_vietnamese-style-guide-glossary.pdf (HIGH confidence — official CFPB, March 2024)
- Simply Wall St portfolio tracker features: https://simplywall.st/ (HIGH confidence — official)

---
*Feature research for: Stratum v3.0 — Product Frontend and User Experience*
*Researched: 2026-03-17*
