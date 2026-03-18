---
phase: 13
slug: report-generation-with-sse-progress
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), vitest (frontend) |
| **Config file** | reasoning/pyproject.toml, frontend/vitest.config.ts |
| **Quick run command** | `cd reasoning && python -m pytest tests/api/ -x -q` / `cd frontend && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd reasoning && python -m pytest tests/ -x -q` / `cd frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds (backend) + ~15 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run quick run command for the affected layer (backend or frontend)
- **After every plan wave:** Run full suite for both layers
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | RGEN-02 | unit | `cd reasoning && python -m pytest tests/api/test_stream.py -x -q` | TBD | ⬜ pending |
| 13-01-02 | 01 | 1 | RGEN-02 | integration | `cd reasoning && python -m pytest tests/api/test_stream.py -x -q` | TBD | ⬜ pending |
| 13-02-01 | 02 | 1 | RGEN-01 | unit | `cd frontend && npx vitest run` | TBD | ⬜ pending |
| 13-02-02 | 02 | 1 | RGEN-02 | unit | `cd frontend && npx vitest run` | TBD | ⬜ pending |
| 13-02-03 | 02 | 1 | RGEN-03 | unit | `cd frontend && npx vitest run` | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — pytest and vitest already configured from Phases 10-12.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE events appear in real time in browser | RGEN-02 | Requires live LangGraph pipeline + browser EventSource | Trigger generation on a ticker card, observe 7 steps progressing in sequence |
| EventSource closes on navigate away | RGEN-03 | Requires browser navigation event | Start generation, navigate to another page, verify no 404 reconnect attempts in network tab |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
