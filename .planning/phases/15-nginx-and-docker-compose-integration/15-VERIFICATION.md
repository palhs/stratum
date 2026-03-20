---
phase: 15-nginx-and-docker-compose-integration
verified: 2026-03-19T10:00:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "SSE events arrive unbuffered through nginx"
    expected: "curl -N -H 'Authorization: Bearer <token>' http://localhost/api/reports/stream/<job_id> emits events one-by-one as pipeline steps complete, not batched at end"
    why_human: "Requires running full stack with active pipeline; timing of event delivery cannot be verified statically"
  - test: "HTTP to HTTPS redirect on production domain"
    expected: "curl -I http://$DOMAIN returns HTTP 301 Location: https://$DOMAIN"
    why_human: "Requires VPS with real domain and certbot-issued TLS certificate"
  - test: "TLS certificate auto-renewal"
    expected: "docker compose logs certbot shows successful renewal within 24h of expiry"
    why_human: "Requires VPS with certbot and real domain; cannot simulate renewal cycle locally"
  - test: "All services healthy with full stack"
    expected: "docker compose --profile reasoning up -d; docker compose ps shows all services as healthy"
    why_human: "Requires running Docker environment with all service images built"
---

# Phase 15: nginx and Docker Compose Integration Verification Report

**Phase Goal:** Wire all frontend-tier services behind an nginx reverse proxy with path-based routing on a single domain
**Verified:** 2026-03-19T10:00:00Z
**Status:** human_needed — all automated checks passed; 4 items require running infrastructure
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                               | Status     | Evidence                                                                                                           |
|----|-------------------------------------------------------------------------------------|------------|--------------------------------------------------------------------------------------------------------------------|
| 1  | All HTTP traffic through nginx reaches frontend or reasoning-engine based on path   | VERIFIED   | local.conf and production.conf both define `location /` -> frontend_upstream, `location /api/` -> reasoning_upstream |
| 2  | SSE events from /api/reports/stream/* arrive unbuffered through nginx               | VERIFIED*  | Both configs have SSE location block with `proxy_buffering off`, `proxy_cache off`, `gzip off`, `proxy_read_timeout 600s`; *runtime delivery needs human test |
| 3  | Frontend and reasoning-engine are not directly accessible on host ports             | VERIFIED   | `grep "3000:3000\|8001:8000" docker-compose.yml` returns zero matches; tier headers updated to "No host port — accessed via nginx" |
| 4  | Local dev works with docker compose up (HTTP only, no certbot)                      | VERIFIED*  | docker-compose.override.yml mounts local.conf, exposes only port 80, certbot disabled with `restart: "no"`; *runtime needs human test |
| 5  | Production config serves HTTPS with certbot auto-renewal                            | VERIFIED*  | production.conf has `listen 443 ssl`, ssl_certificate directives, ACME challenge block, 301 redirect; certbot service has renewal loop; *requires VPS for runtime test |

**Score:** 5/5 truths verified (3 have runtime-only validation items flagged for human)

---

### Required Artifacts

| Artifact                    | Expected                                                             | Status     | Details                                                                                               |
|-----------------------------|----------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------------|
| `nginx/local.conf`          | HTTP-only nginx config with upstream blocks and SSE location         | VERIFIED   | 49 lines; upstream blocks, 3 location blocks, `proxy_buffering off` on SSE block, `keepalive 16`     |
| `nginx/production.conf`     | HTTPS nginx config with certbot ACME challenge and HTTP redirect     | VERIFIED   | 67 lines; 2 server blocks, ssl_certificate directives, ACME challenge location, 301 redirect          |
| `docker-compose.yml`        | nginx and certbot service definitions; no host ports on frontend/reasoning-engine | VERIFIED | nginx:alpine service at line 368, certbot service at line 394, volumes letsencrypt + certbot_webroot declared at lines 33-34, no 3000:3000 or 8001:8000 |
| `docker-compose.override.yml` | Local dev override mounting local.conf and exposing port 80        | VERIFIED   | 14 lines; mounts `local.conf:/etc/nginx/conf.d/default.conf:ro`, port 80 only, certbot no-op         |
| `.env.example`              | DOMAIN and CERTBOT_EMAIL env var documentation                       | VERIFIED   | Lines 63-65: `DOMAIN=stratum.example.com`, `CERTBOT_EMAIL=admin@example.com`, `NEXT_PUBLIC_API_URL=https://stratum.example.com` |

---

### Key Link Verification

| From                       | To                          | Via                        | Status   | Details                                                                                              |
|----------------------------|-----------------------------|----------------------------|----------|------------------------------------------------------------------------------------------------------|
| `nginx/local.conf`         | `frontend:3000`             | `upstream frontend_upstream` | WIRED  | Line 2: `server frontend:3000;` inside `upstream frontend_upstream` block                           |
| `nginx/local.conf`         | `reasoning-engine:8000`     | `upstream reasoning_upstream` | WIRED | Line 7: `server reasoning-engine:8000;` inside `upstream reasoning_upstream` block                  |
| `docker-compose.yml`       | `nginx/production.conf`     | volume mount               | WIRED    | Line 378: `./nginx/production.conf:/etc/nginx/conf.d/default.conf:ro`                               |
| `docker-compose.override.yml` | `nginx/local.conf`       | volume mount override      | WIRED    | Line 6: `./nginx/local.conf:/etc/nginx/conf.d/default.conf:ro` (overrides production.conf in base)  |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                        | Status    | Evidence                                                                                             |
|-------------|-------------|----------------------------------------------------|-----------|------------------------------------------------------------------------------------------------------|
| INFR-02     | 15-01-PLAN  | nginx reverse proxy with SSE buffering disabled for stream routes | SATISFIED | nginx installed as Docker service; `proxy_buffering off` on `/api/reports/stream/*`; no orphaned ports on frontend/reasoning-engine |

**Orphaned requirements check:** REQUIREMENTS.md maps INFR-02 to Phase 15. No other Phase 15 requirement IDs exist in REQUIREMENTS.md. Coverage is complete.

---

### Anti-Patterns Found

| File                      | Pattern              | Severity | Impact                                                                                                                    |
|---------------------------|----------------------|----------|---------------------------------------------------------------------------------------------------------------------------|
| `nginx/production.conf`   | `DOMAIN_PLACEHOLDER` | Info     | Intentional by design — documented in SUMMARY.md decisions section as "DOMAIN_PLACEHOLDER as literal string — deployer does a simple find-replace. Simpler than requiring NGINX_ENVSUBST_OUTPUT_DIR." Not a stub. |

No blocker or warning anti-patterns found. The `DOMAIN_PLACEHOLDER` literal is a deliberate deployment artifact documented in the plan and summary.

---

### Human Verification Required

#### 1. SSE Event Delivery Latency

**Test:** With full stack running, start a report generation and connect to the SSE stream:
```
curl -N -H "Authorization: Bearer <token>" http://localhost/api/reports/stream/<job_id>
```
**Expected:** Each pipeline step event (`node_start`, `node_complete`) arrives within 1-2 seconds of occurring, not batched at the end of the pipeline run.
**Why human:** Requires a running pipeline and visual timing verification. Static analysis of `proxy_buffering off` confirms the intent but cannot prove event delivery cadence.

#### 2. HTTP to HTTPS Redirect (Production)

**Test:** With a VPS deployment and real domain, run:
```
curl -I http://$DOMAIN
```
**Expected:** Response is `HTTP/1.1 301 Moved Permanently` with `Location: https://$DOMAIN/`
**Why human:** Requires VPS with a real domain name, nginx serving the production.conf with DOMAIN_PLACEHOLDER replaced, and DNS pointing to the server.

#### 3. TLS Certificate Auto-Renewal (Production)

**Test:** After initial certificate issue, check certbot logs:
```
docker compose logs certbot
```
**Expected:** Logs show `certbot renew` running every 12 hours; shows successful renewal when cert approaches expiry (< 30 days remaining).
**Why human:** Requires VPS with real certbot-issued certificate and elapsed time to observe renewal cycle.

#### 4. Full Stack Health Check (Local)

**Test:** Run `docker compose --profile reasoning up -d` and verify:
```
docker compose ps
```
**Expected:** All services (postgres, neo4j, qdrant, reasoning-engine, frontend, nginx) show status "healthy"; nginx health check (`wget http://localhost:80/`) passes after frontend and reasoning-engine are healthy.
**Why human:** Requires running Docker environment with built images and all services starting successfully.

---

### Gaps Summary

No gaps. All 5 observable truths are verified at the configuration level. All 5 artifacts exist, are substantive implementations (not stubs), and are fully wired. All 4 key links are confirmed present. INFR-02 is satisfied.

The 4 human verification items are runtime behaviors that cannot be verified through static code analysis. They do not represent gaps in the implementation — they are the expected validation steps for any infrastructure change that requires a running environment.

---

### Commit Verification

All commits documented in SUMMARY.md are confirmed present in git history:

| Commit   | Description                                                                              |
|----------|------------------------------------------------------------------------------------------|
| c3ebc13  | feat(15-01): create nginx config files for local and production                          |
| 65bcdad  | feat(15-01): wire nginx and certbot into Docker Compose, create override, update .env.example |
| ae32d66  | chore(15-01): update stale port comments in docker-compose.yml                           |

---

_Verified: 2026-03-19T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
