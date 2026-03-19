---
phase: 14
slug: report-view-tradingview-chart-and-history
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.0 + @testing-library/react 16.3.2 |
| **Config file** | `frontend/vitest.config.ts` |
| **Quick run command** | `cd frontend && npm test` |
| **Full suite command** | `cd frontend && npm test` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test`
- **After every plan wave:** Run `cd frontend && npm test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | RVEW-01 | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/ReportSummaryCard.test.tsx` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 0 | RVEW-02 | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/ReportPageClient.test.tsx` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 0 | RVEW-03 | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/BilingualToggle.test.tsx` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 0 | RVEW-04 | unit (mock) | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/TradingViewChart.test.tsx` | ❌ W0 | ⬜ pending |
| 14-01-05 | 01 | 0 | RHST-01 | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/HistoryTimeline.test.tsx` | ❌ W0 | ⬜ pending |
| 14-01-06 | 01 | 0 | RHST-02 | unit | included in HistoryTimeline test | ❌ W0 | ⬜ pending |
| 14-01-07 | 01 | 0 | RHST-03 | unit | included in ReportPageClient test | ❌ W0 | ⬜ pending |
| 14-01-08 | 01 | 0 | RHST-04 | unit | `cd frontend && npm test -- --reporter=verbose src/components/report/__tests__/HistoryTimeline.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/report/__tests__/ReportSummaryCard.test.tsx` — stubs for RVEW-01
- [ ] `frontend/src/components/report/__tests__/BilingualToggle.test.tsx` — stubs for RVEW-03
- [ ] `frontend/src/components/report/__tests__/TradingViewChart.test.tsx` — stubs for RVEW-04 (mock lightweight-charts via vi.mock)
- [ ] `frontend/src/components/report/__tests__/ReportPageClient.test.tsx` — stubs for RVEW-02, RHST-03
- [ ] `frontend/src/components/report/__tests__/HistoryTimeline.test.tsx` — stubs for RHST-01, RHST-02, RHST-04
- [ ] `reasoning/tests/test_reports_by_id.py` — stubs for new GET /reports/by-report-id/{report_id} endpoint

**Test mocking notes:**
- `lightweight-charts` must be mocked: `vi.mock('lightweight-charts', () => ({ createChart: vi.fn(() => ({ ... })), ... }))`
- `localStorage` is available in jsdom — no mock needed
- `next/dynamic` must be mocked: `vi.mock('next/dynamic', () => ({ default: (fn: () => Promise<unknown>) => fn }))`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TradingView chart is visually zoomable | RVEW-04 | Visual interaction cannot be unit-tested | Load report page, verify chart renders candles, drag to zoom |
| Language toggle visual state | RVEW-03 | Visual toggle state | Toggle between VI/EN, verify content switches and persists after page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
