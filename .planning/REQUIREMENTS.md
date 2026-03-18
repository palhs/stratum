# Requirements: Stratum

**Defined:** 2026-03-18
**Core Value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.

## v3.0 Requirements

Requirements for v3.0 Product Frontend & User Experience. Each maps to roadmap phases.

### Authentication

- [x] **AUTH-01**: User can log in with email and password via Supabase
- [x] **AUTH-02**: User session persists across browser refresh via HTTP-only cookies
- [ ] **AUTH-03**: Admin can invite new users via Supabase admin API (signup disabled)
- [x] **AUTH-04**: User data is isolated per account (watchlists, report access)
- [x] **AUTH-05**: Invited user receives pre-seeded watchlist on first login

### Watchlist

- [x] **WTCH-01**: User can add tickers from VN30 + gold universe to their watchlist
- [x] **WTCH-02**: User can remove tickers from their watchlist
- [x] **WTCH-03**: Watchlist is persisted per user across sessions

### Dashboard

- [ ] **DASH-01**: User sees watchlist as cards on dashboard landing page
- [ ] **DASH-02**: Each card shows entry quality tier badge (color-coded Favorable/Neutral/Cautious/Avoid)
- [ ] **DASH-03**: Each card shows sparkline price chart (52-week weekly close)
- [ ] **DASH-04**: Each card shows last report date
- [ ] **DASH-05**: Dashboard shows appropriate empty/loading/error states

### Report Generation

- [ ] **RGEN-01**: User can trigger report generation via button on ticker card
- [ ] **RGEN-02**: User sees real-time SSE progress showing named pipeline steps
- [ ] **RGEN-03**: Generate button is disabled during active generation

### Report View

- [ ] **RVEW-01**: User sees report summary card (tier, sub-assessments, one-line verdict)
- [ ] **RVEW-02**: User can expand summary to full bilingual markdown report
- [ ] **RVEW-03**: User can toggle between Vietnamese and English report versions
- [ ] **RVEW-04**: Report view includes interactive TradingView chart (weekly OHLCV + 50MA + 200MA, zoomable)

### Report History

- [ ] **RHST-01**: User can view timeline of past reports per ticker
- [ ] **RHST-02**: Timeline shows date and entry quality tier badge per report
- [ ] **RHST-03**: User can open any historical report from the timeline
- [ ] **RHST-04**: Timeline shows assessment change indicators (upgrade/downgrade arrows)

### Document Ingestion

- [ ] **DING-01**: FOMC minutes are automatically ingested via n8n cron when new releases detected
- [ ] **DING-02**: SBV reports can be ingested via n8n manual trigger (file upload fallback)
- [ ] **DING-03**: Ingested documents are chunked, embedded, and upserted into Qdrant with deduplication

### Dictionary

- [ ] **DICT-01**: Vietnamese financial dictionary expanded by 80-120 terms covering earnings vocabulary and sector-specific terms

### Infrastructure

- [ ] **INFR-01**: Next.js frontend runs as Docker service with mem_limit on VPS
- [ ] **INFR-02**: nginx reverse proxy with SSE buffering disabled for stream routes
- [x] **INFR-03**: FastAPI reasoning-engine validates Supabase JWT on protected endpoints
- [x] **INFR-04**: New GET /tickers/{symbol}/ohlcv endpoint serves chart data
- [x] **INFR-05**: New GET /reports/by-ticker/{symbol} endpoint serves report history

## Future Requirements

Deferred to v4.0+.

### LLM Cost Optimization

- **LLM-01**: OpenRouter integration for multi-model routing and cost optimization
- **LLM-02**: Local LLM fallback via Ollama for non-critical generation tasks

### Extended Coverage

- **EXT-01**: Support tickers beyond VN30 + gold universe
- **EXT-02**: Automated SBV website scraping (if sbv.gov.vn stabilizes)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time price feed | Contradicts weekly/monthly analytical cadence; creates expectation mismatch |
| Portfolio P&L / holdings tracking | Different product scope; opens compliance questions |
| Push notifications | Weekly cadence doesn't warrant push infra; n8n email digest is sufficient |
| AI chat / Q&A over reports | Uncontrolled LLM responses over financial data; liability risk |
| PDF export | Browser print CSS handles 90% of the use case |
| Public signup | Invite-only for v3.0; validate product before opening access |
| Social features | 10x complexity for unvalidated need; CafeF already serves this |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 11 | Complete |
| AUTH-02 | Phase 11 | Complete |
| AUTH-03 | Phase 11 | Pending |
| AUTH-04 | Phase 11 | Complete |
| AUTH-05 | Phase 11 | Complete |
| WTCH-01 | Phase 11 | Complete |
| WTCH-02 | Phase 11 | Complete |
| WTCH-03 | Phase 11 | Complete |
| DASH-01 | Phase 12 | Pending |
| DASH-02 | Phase 12 | Pending |
| DASH-03 | Phase 12 | Pending |
| DASH-04 | Phase 12 | Pending |
| DASH-05 | Phase 12 | Pending |
| RGEN-01 | Phase 13 | Pending |
| RGEN-02 | Phase 13 | Pending |
| RGEN-03 | Phase 13 | Pending |
| RVEW-01 | Phase 14 | Pending |
| RVEW-02 | Phase 14 | Pending |
| RVEW-03 | Phase 14 | Pending |
| RVEW-04 | Phase 14 | Pending |
| RHST-01 | Phase 14 | Pending |
| RHST-02 | Phase 14 | Pending |
| RHST-03 | Phase 14 | Pending |
| RHST-04 | Phase 14 | Pending |
| DING-01 | Phase 16 | Pending |
| DING-02 | Phase 16 | Pending |
| DING-03 | Phase 16 | Pending |
| DICT-01 | Phase 16 | Pending |
| INFR-01 | Phase 12 | Pending |
| INFR-02 | Phase 15 | Pending |
| INFR-03 | Phase 10 | Complete |
| INFR-04 | Phase 10 | Complete |
| INFR-05 | Phase 10 | Complete |

**Coverage:**
- v3.0 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after v3.0 roadmap creation — all 33 requirements mapped*
