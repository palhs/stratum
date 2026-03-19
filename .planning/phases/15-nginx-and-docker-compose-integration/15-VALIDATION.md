---
phase: 15
slug: nginx-and-docker-compose-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, reasoning/tests/) + shell smoke tests |
| **Config file** | reasoning/pyproject.toml (existing) |
| **Quick run command** | `bash scripts/smoke-test-nginx.sh` |
| **Full suite command** | `docker compose exec reasoning-engine pytest tests/ -q && bash scripts/smoke-test-nginx.sh` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose ps` (verify services healthy)
- **After every plan wave:** Run `bash scripts/smoke-test-nginx.sh`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | INFR-02 | config | `nginx -t` (config syntax check) | N/A | ⬜ pending |
| 15-01-02 | 01 | 1 | INFR-02 | smoke | `curl -sf http://localhost/api/health` | ❌ W0 | ⬜ pending |
| 15-01-03 | 01 | 1 | INFR-02 | smoke | `curl -sf http://localhost/` (frontend) | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 1 | INFR-02 | smoke | `curl -sf http://localhost/api/watchlist` returns 401 | ❌ W0 | ⬜ pending |
| 15-01-05 | 01 | 1 | INFR-02 | manual | `curl -N http://localhost/api/reports/stream/<id>` real-time events | manual-only | ⬜ pending |
| 15-01-06 | 01 | 1 | INFR-02 | smoke | `docker compose ps` all services healthy | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/smoke-test-nginx.sh` — curl smoke tests: 401 on unauth API, 200 on health, 200 on frontend root
- [ ] Smoke test covers: nginx config syntax check, proxy routing, auth passthrough

*Existing infrastructure (pytest) covers reasoning-engine unit/integration tests. Wave 0 adds nginx-specific smoke tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE events arrive real-time through nginx | INFR-02 | Requires running pipeline + visual timing verification | `curl -N -H "Authorization: Bearer <token>" http://localhost/api/reports/stream/<job_id>` — events must arrive one-by-one, not batched |
| HTTP→HTTPS redirect on production | INFR-02 | Requires VPS with TLS certs + real domain | `curl -I http://$DOMAIN` returns 301 to https:// |
| TLS certificate valid and auto-renewing | INFR-02 | Requires VPS with certbot + real domain | `docker compose logs certbot` shows successful renewal |
| All 10 Docker services healthy | INFR-02 | Requires full stack running | `docker compose ps` shows all services with status "healthy" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
