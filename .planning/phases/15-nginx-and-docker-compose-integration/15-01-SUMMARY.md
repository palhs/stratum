---
phase: 15-nginx-and-docker-compose-integration
plan: "01"
subsystem: infrastructure
tags: [nginx, docker-compose, certbot, tls, sse, reverse-proxy]
dependency_graph:
  requires: []
  provides: [nginx-reverse-proxy, certbot-tls, sse-buffering-disabled, single-domain-routing]
  affects: [frontend, reasoning-engine, docker-compose]
tech_stack:
  added: [nginx:alpine, certbot/certbot:latest]
  patterns: [upstream-keepalive-blocks, docker-compose-override, sse-location-block, certbot-webroot-renewal]
key_files:
  created:
    - nginx/local.conf
    - nginx/production.conf
    - docker-compose.override.yml
  modified:
    - docker-compose.yml
    - .env.example
    - .gitignore
key_decisions:
  - "docker-compose.override.yml committed to git (contains no secrets; RESEARCH.md guidance followed)"
  - "DOMAIN_PLACEHOLDER literal string in production.conf — deployer replaces with actual domain (simpler than envsubst templating)"
  - ".gitignore updated to unblock docker-compose.override.yml from being tracked"
  - "Stale port comments (3000:3000, 8001:8000) in service tier headers updated to reflect nginx-only access"
metrics:
  duration: "~8 min"
  completed_date: "2026-03-19"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
---

# Phase 15 Plan 01: nginx and Docker Compose Integration Summary

nginx reverse proxy with SSE buffering disabled, certbot TLS, Docker Compose override pattern for local/production split, and host ports removed from frontend and reasoning-engine.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create nginx config files for local and production | c3ebc13 | nginx/local.conf, nginx/production.conf |
| 2 | Wire nginx and certbot into Docker Compose, create override, update .env.example | 65bcdad, ae32d66 | docker-compose.yml, docker-compose.override.yml, .env.example, .gitignore |

## What Was Built

### nginx/local.conf
HTTP-only config for local development. Two upstream blocks (`frontend_upstream`, `reasoning_upstream`) with `keepalive 16` for connection pooling. Three location blocks:
- `~ ^/api/reports/stream/` — SSE-specific: `proxy_buffering off`, `proxy_cache off`, `gzip off`, `X-Accel-Buffering: no`, `proxy_read_timeout 600s`
- `/api/` — Normal buffered proxy to reasoning-engine with X-Forwarded headers
- `/` — Frontend fallback with keepalive connection reuse

### nginx/production.conf
HTTPS config with `DOMAIN_PLACEHOLDER` literal (deployer replaces with actual domain). Two server blocks:
- Port 80: ACME challenge (`/.well-known/acme-challenge/ -> /var/www/certbot`), HTTP-to-HTTPS 301 redirect for all other traffic
- Port 443 SSL: Identical proxy routing as local.conf with `ssl_certificate` directives pointing to letsencrypt volume paths

### docker-compose.yml changes
- `volumes:` block: added `letsencrypt:` and `certbot_webroot:` named volumes
- `frontend` service: removed `ports: - "3000:3000"`, updated `NEXT_PUBLIC_API_URL` to `${NEXT_PUBLIC_API_URL:-}` (empty default = same-origin via nginx)
- `reasoning-engine` service: removed `ports: - "8001:8000"`
- Added `nginx` service: `nginx:alpine`, `mem_limit: 128m`, `depends_on` frontend+reasoning-engine healthy, production.conf volume mount, ports 80+443, `reasoning` network, `reasoning` profile
- Added `certbot` service: `certbot/certbot:latest`, renewal loop (`while true; do certbot renew && sleep 12h; done`), shared letsencrypt volumes, `reasoning` profile

### docker-compose.override.yml
Auto-merged by `docker compose up` for local development. Overrides nginx volumes to mount `local.conf` instead of `production.conf`. Overrides certbot entrypoint to `echo` no-op with `restart: "no"`.

### .env.example
Added Phase 11 Supabase vars (SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_JWKS_URL), deprecated VPS_HOST comment, and Phase 15 vars: `DOMAIN=stratum.example.com`, `CERTBOT_EMAIL=admin@example.com`, `NEXT_PUBLIC_API_URL=https://stratum.example.com`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] docker-compose.override.yml was gitignored**
- **Found during:** Task 2 commit
- **Issue:** `.gitignore` contained `docker-compose.override.yml` entry, preventing the file from being tracked. RESEARCH.md explicitly states "Commit docker-compose.override.yml to git. It's safe — it contains no secrets."
- **Fix:** Commented out the gitignore entry and added an explanatory note
- **Files modified:** `.gitignore`
- **Commit:** 65bcdad

**2. [Rule 1 - Bug] Stale port comments in docker-compose.yml tier headers**
- **Found during:** Task 2 verification — comments still referenced `Port: 3000:3000` and `Port: 8001:8000` after ports were removed
- **Fix:** Updated tier header comments to read "No host port — accessed via nginx on port 80/443"
- **Files modified:** `docker-compose.yml`
- **Commit:** ae32d66

## Decisions Made

1. **DOMAIN_PLACEHOLDER as literal string** — production.conf uses `DOMAIN_PLACEHOLDER` rather than nginx envsubst templating. Deployer does a simple find-replace. Simpler than requiring `NGINX_ENVSUBST_OUTPUT_DIR` entrypoint override.

2. **docker-compose.override.yml committed** — overrides file contains no secrets (only local dev config). Following RESEARCH.md Pitfall 5 guidance to prevent local dev breakage for future contributors.

3. **NEXT_PUBLIC_API_URL defaults to empty string** — `${NEXT_PUBLIC_API_URL:-}` means local dev uses same-origin fetch (api.ts falls back to `''`), production .env sets full domain URL. No change needed to frontend code.

## Self-Check: PASSED

Files exist:
- nginx/local.conf: FOUND
- nginx/production.conf: FOUND
- docker-compose.override.yml: FOUND

Commits exist:
- c3ebc13: FOUND
- 65bcdad: FOUND
- ae32d66: FOUND

Key acceptance criteria:
- proxy_buffering off in nginx/local.conf: PASS
- ssl_certificate in nginx/production.conf: PASS
- nginx: and certbot: in docker-compose.yml: PASS
- No 3000:3000 in docker-compose.yml: PASS
- No 8001:8000 in docker-compose.yml: PASS
- local.conf in docker-compose.override.yml: PASS
- DOMAIN= in .env.example: PASS
- CERTBOT_EMAIL= in .env.example: PASS
