---
phase: 12
slug: next-js-core-shell-and-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (unit) + Playwright (E2E) — greenfield, Wave 0 installs |
| **Config file** | `frontend/vitest.config.ts` + `frontend/playwright.config.ts` (Wave 0 creates) |
| **Quick run command** | `cd frontend && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd frontend && npx vitest run && npx playwright test` |
| **Estimated runtime** | ~15 seconds (unit ~5s, E2E ~10s) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run --reporter=verbose`
- **After every plan wave:** Run `cd frontend && npx vitest run && npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green + manual docker stats check
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 0 | INFR-01 | config | `grep "mem_limit: 512m" docker-compose.yml` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 0 | INFR-01 | config | `grep "standalone" frontend/next.config.ts` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 1 | DASH-01 | unit | `npx vitest run TierBadge.test` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 1 | DASH-02 | unit | `npx vitest run Sparkline.test` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 1 | DASH-03, DASH-04 | unit | `npx vitest run DashboardClient.test` | ❌ W0 | ⬜ pending |
| 12-03-02 | 03 | 1 | DASH-05 | unit | `npx vitest run EmptyState.test` | ❌ W0 | ⬜ pending |
| 12-04-01 | 04 | 2 | DASH-01 | integration | `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/` | N/A | ⬜ pending |
| 12-04-02 | 04 | 2 | INFR-01 | integration | `docker stats --no-stream stratum-frontend-1` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment and React Testing Library
- [ ] `frontend/src/test/setup.ts` — Global test setup (jest-dom matchers, cleanup)
- [ ] `frontend/playwright.config.ts` — Playwright config with baseURL, test credentials from env
- [ ] `frontend/tests/e2e/auth.spec.ts` — E2E stub: unauthenticated redirect, login flow
- [ ] `frontend/tests/e2e/dashboard.spec.ts` — E2E stub: dashboard load, card rendering
- [ ] `frontend/src/components/dashboard/__tests__/TierBadge.test.tsx` — Unit: tier badge color classes
- [ ] `frontend/src/components/dashboard/__tests__/Sparkline.test.tsx` — Unit: SVG polyline math
- [ ] `frontend/src/components/dashboard/__tests__/DashboardClient.test.tsx` — Unit: loading/error/empty states
- [ ] `frontend/src/components/dashboard/__tests__/EmptyState.test.tsx` — Unit: quick-add buttons

**Framework install (Wave 0 task):**
```bash
cd frontend
npm install --save-dev vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @playwright/test
npx playwright install chromium
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Authenticated user sees dashboard | DASH-01 | Requires live Supabase credentials | 1. Log in with test account 2. Verify dashboard loads with cards |
| Docker memory under load | INFR-01 | Requires browser + 30-ticker watchlist | 1. Open dashboard with full watchlist 2. Run `docker stats --no-stream` 3. Confirm < 512MiB |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
