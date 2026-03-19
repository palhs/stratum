# Phase 15: nginx and Docker Compose Integration - Research

**Researched:** 2026-03-19
**Domain:** nginx reverse proxy, Docker Compose override pattern, certbot TLS, SSE streaming
**Confidence:** HIGH

## Summary

This phase wires all frontend-tier services (frontend:3000, reasoning-engine:8000) behind a single
nginx reverse proxy using path-based routing. The work is purely infrastructure — no application
logic changes except removing exposed host ports from frontend and reasoning-engine and updating
`NEXT_PUBLIC_API_URL` to point to the nginx domain. Two separate nginx config files handle
local HTTP-only and production HTTPS+certbot scenarios, connected via Docker Compose's
override file pattern.

The critical technical challenge is SSE proxy configuration. nginx buffers responses by default;
without `proxy_buffering off` on the stream location block, the browser receives batched events
instead of a real-time stream. The `/api/reports/stream/*` location block requires a focused set
of directives distinct from the normal `/api/*` proxy behavior. The keepalive ping already
emitted by FastAPI every 15s (Phase 13) prevents the default 60s `proxy_read_timeout` from
closing idle SSE connections; the locked decision raises this to 600s on stream routes.

For production TLS, the industry-standard pattern is `certbot/certbot` Docker image running a
renewal loop (`certbot renew && sleep 12h`), sharing a `letsencrypt` volume with nginx. The
chicken-and-egg problem (nginx needs certs to start, but certbot needs nginx to validate the
domain) is solved by a two-phase bootstrap: first obtain certificates with a minimal HTTP-only
nginx config, then switch to the full HTTPS config.

**Primary recommendation:** Use `nginx:alpine` for the nginx service, `certbot/certbot` for TLS,
upstream blocks for both backend services (enables keepalive pool), and the Docker Compose
`docker-compose.override.yml` auto-merge for local vs. explicit `-f` flags for production.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single domain, path-based routing: `/` -> frontend:3000, `/api/*` -> reasoning-engine:8000
- Same-origin means no CORS headers needed
- n8n stays on separate port 5678 directly (admin tool, no nginx proxy)
- Neo4j Browser stays on port 7474/7687 directly (admin tool)
- Frontend and reasoning-engine host port mappings removed — only nginx exposes 80/443
- `NEXT_PUBLIC_API_URL` set to full domain URL (e.g., `https://stratum.example.com`) — absolute paths in config
- Local-first approach: HTTP only for local development, TLS for VPS deployment
- Two nginx config files: `nginx/local.conf` (HTTP, port 80) and `nginx/production.conf` (HTTPS + HTTP redirect + certbot)
- Docker Compose override pattern: `docker-compose.override.yml` for local config (auto-merged), production runs with `--file docker-compose.yml` only
- Certbot runs as a Docker container alongside nginx, shared volume for certificates
- Auto-renewal via certbot container timer/cron
- Domain DNS is a VPS prerequisite — not part of this phase's implementation
- SSE-specific directives applied only to `/api/reports/stream/*` location block (not all `/api/*`)
- Directives: `proxy_buffering off`, `X-Accel-Buffering: no`, chunked transfer encoding
- `proxy_read_timeout 600s` (10 minutes) on stream routes
- Other `/api/*` routes use normal buffered proxy behavior
- FastAPI keepalive pings already implemented (Phase 8/13)
- nginx image: `nginx:alpine` (~40MB, minimal)
- `mem_limit: 128m` for nginx container
- nginx joins reasoning network only (frontend + reasoning-engine)
- nginx profile: `["reasoning"]`
- nginx depends_on: frontend (healthy) + reasoning-engine (healthy)
- nginx health check: wget or curl to localhost:80

### Claude's Discretion
- Exact nginx.conf structure (server blocks, upstream definitions)
- Certbot Docker service configuration details
- docker-compose.override.yml structure for local development
- nginx logging configuration
- Whether to use nginx upstream blocks or direct proxy_pass
- gzip compression settings
- Static asset caching headers (if any)
- Exact health check implementation for nginx

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFR-02 | nginx reverse proxy with SSE buffering disabled for stream routes | SSE location block directives documented; certbot TLS pattern verified; Docker Compose service definition patterns identified |
</phase_requirements>

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| nginx:alpine | alpine (current) | Reverse proxy, TLS termination | Official image, ~40MB, ships with wget for health checks |
| certbot/certbot | latest | Let's Encrypt certificate acquisition and renewal | Official EFF image, webroot plugin supports nginx integration |

### Supporting
| Library/Tool | Version | Purpose | When to Use |
|---|---|---|---|
| docker compose override | built-in | Local vs production config separation | Auto-merged for local dev, explicit `-f` for production |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| certbot/certbot Docker container | nginx-certbot combined image (JonasAlfredsson) | Combined image is simpler but less composable; separate containers align with existing project pattern |
| upstream blocks | direct proxy_pass | Direct proxy_pass opens a new TCP connection per request; upstream blocks with keepalive pool reuse connections — prefer upstream blocks |
| docker-compose.override.yml | separate docker-compose.local.yml | override.yml is auto-merged on `docker compose up` without flags — zero cognitive overhead for developers |

**Installation:** No npm packages needed. Docker images pulled automatically on `docker compose up`.

## Architecture Patterns

### Recommended Project Structure
```
nginx/
├── local.conf          # HTTP only (port 80), for docker-compose.override.yml
└── production.conf     # HTTPS (port 443) + HTTP redirect + certbot ACME challenge

docker-compose.override.yml   # Local dev: mounts local.conf, no certbot service
docker-compose.yml             # Base: nginx service definition (certbot added in production)
```

### Pattern 1: nginx Upstream Blocks with Keepalive Pool

**What:** Define named upstream blocks for each backend; use `keepalive N` to maintain persistent
connections to backends rather than creating a new TCP connection per request.

**When to use:** Always — for both `frontend` and `reasoning-engine` upstreams. Particularly
important for the SSE stream endpoint where connection overhead compounds.

**Example:**
```nginx
# Source: nginx.org/en/docs/http/ngx_http_upstream_module.html
upstream frontend_upstream {
    server frontend:3000;
    keepalive 16;
}

upstream reasoning_upstream {
    server reasoning-engine:8000;
    keepalive 16;
}
```

### Pattern 2: SSE-Specific Location Block

**What:** Dedicated location block for `/api/reports/stream/` with buffering disabled. Normal
`/api/` routes retain default buffered proxy behavior for better throughput.

**When to use:** Only on the stream route — applying `proxy_buffering off` globally harms
throughput on normal API requests.

**Example:**
```nginx
# Source: nginx.org/en/docs/http/ngx_http_proxy_module.html + oneuptime.com/blog SSE guide
location ~ ^/api/reports/stream/ {
    proxy_pass http://reasoning_upstream;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_set_header Host $host;

    # SSE: disable all buffering
    proxy_buffering off;
    proxy_cache off;
    gzip off;

    # Upstream response header also tells nginx to skip buffering
    # (belt-and-suspenders: proxy_buffering off already sufficient in nginx)
    add_header X-Accel-Buffering no;

    # 10-minute timeout — covers 2-5 min pipeline + generous headroom
    # FastAPI already emits keepalive pings every 15s (Phase 13)
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}

location /api/ {
    proxy_pass http://reasoning_upstream;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Pattern 3: Docker Compose Override File for Local vs Production

**What:** `docker-compose.override.yml` is automatically merged by `docker compose up` when present.
Production deployment explicitly excludes it with `docker compose -f docker-compose.yml up -d`.

**When to use:** Local development uses override for HTTP-only nginx config (no certbot). Production
switches to the full HTTPS config via explicit `-f` flag.

**Local override example:**
```yaml
# docker-compose.override.yml — auto-merged for local dev, excluded in production
services:
  nginx:
    ports:
      - "80:80"
    volumes:
      - ./nginx/local.conf:/etc/nginx/conf.d/default.conf:ro
```

**Production** runs with `docker compose -f docker-compose.yml up -d` which excludes the override,
so the base `docker-compose.yml` must include the certbot service and production config volume mount.

### Pattern 4: Certbot Docker Container with Webroot Renewal Loop

**What:** Certbot container shares a volume with nginx for ACME HTTP-01 challenges
(`/var/www/certbot`) and certificate storage (`/etc/letsencrypt`). Renewal runs in a
`while true` loop every 12 hours.

**When to use:** Production only — included in `docker-compose.yml` base but only activated
when the letsencrypt volume has certificates (after bootstrap).

**Certbot service example:**
```yaml
certbot:
  image: certbot/certbot:latest
  restart: unless-stopped
  volumes:
    - letsencrypt:/etc/letsencrypt:rw
    - certbot_webroot:/var/www/certbot:rw
  entrypoint: ["/bin/sh", "-c"]
  command:
    - "while true; do certbot renew --webroot --webroot-path /var/www/certbot/ --quiet && sleep 12h; done"
  profiles: ["reasoning"]
```

**Bootstrap (one-time on VPS, before docker compose up):**
```bash
# 1. Start nginx with HTTP-only config first
docker compose -f docker-compose.yml up -d nginx

# 2. Obtain initial certificate
docker compose -f docker-compose.yml run --rm certbot \
  certbot certonly --webroot --webroot-path /var/www/certbot \
  --email $CERTBOT_EMAIL --agree-tos --no-eff-email \
  -d $DOMAIN

# 3. Switch nginx to HTTPS config and restart
docker compose -f docker-compose.yml up -d
```

### Pattern 5: HTTP to HTTPS Redirect in nginx

**What:** Port 80 server block returns 301 redirect to HTTPS for all traffic except ACME challenges.

**Example:**
```nginx
# nginx/production.conf — HTTP server block
server {
    listen 80;
    server_name $DOMAIN;

    # ACME challenge for certbot renewal (port 80 must serve .well-known/)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
```

### Anti-Patterns to Avoid
- **Applying `proxy_buffering off` globally:** Harms throughput on normal JSON API responses. Apply only to the stream location block.
- **Using `proxy_pass http://frontend:3000` directly (no upstream block):** Creates a new TCP connection per request. Use upstream blocks with keepalive.
- **Putting certbot bootstrap inside docker-compose:** The chicken-and-egg problem (nginx needs certs to start HTTPS, certbot needs nginx for HTTP challenge) requires a manual bootstrap sequence. Do not try to automate this in Compose startup.
- **Setting `chunked_transfer_encoding off` on SSE:** FastAPI/Starlette uses chunked encoding to send SSE frames. Disabling this breaks the stream. The `proxy_buffering off` directive is the correct lever.
- **`NEXT_PUBLIC_API_URL` with trailing slash:** `api.ts` concatenates paths like `/watchlist` directly — `https://domain.com/` + `/watchlist` would create double-slash. Ensure URL has no trailing slash.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| TLS certificate management | Custom cert generation scripts | certbot/certbot Docker image | Let's Encrypt rate limits, renewal timing, OCSP stapling, cert chain management are all handled |
| SSE proxy buffering detection | Custom nginx module or middleware | `proxy_buffering off` + `proxy_read_timeout` directives | nginx natively supports this; no custom code needed |
| nginx config templating for env vars | Custom bash substitution | nginx `$DOMAIN` env via `envsubst` in entrypoint or hard-coded domain in config files | Project uses two explicit config files (local.conf / production.conf) — simpler than templating |

**Key insight:** All the complexity in this phase is nginx config directives and Docker Compose
file structure — not application code. The risk is configuration mistakes, not missing libraries.

## Common Pitfalls

### Pitfall 1: SSE Events Buffered Despite `proxy_buffering off`
**What goes wrong:** Browser receives a burst of events at pipeline completion instead of
real-time progress updates. curl -N appears to work but EventSource in browser does not.
**Why it happens:** nginx may apply gzip compression which re-buffers the stream even when
`proxy_buffering off` is set. Also, FastAPI's ASGI server (uvicorn) must be flushing responses
immediately — sse-starlette handles this correctly.
**How to avoid:** Add `gzip off` inside the SSE location block explicitly. Verify with
`curl -N http://localhost/api/reports/stream/<id>` and confirm events arrive one-by-one.
**Warning signs:** `curl -N` shows events but browser EventSource batches them; check for
a gzip module applying to the stream route.

### Pitfall 2: nginx Starts Before Upstream Services Are Healthy
**What goes wrong:** nginx starts, immediately tries to resolve `frontend` and `reasoning-engine`
hostnames, fails, and enters a crash loop (502 on all routes).
**Why it happens:** nginx resolves upstream hostnames at startup time by default.
**How to avoid:** The `depends_on: {condition: service_healthy}` in the nginx service definition
(already locked in CONTEXT.md) ensures nginx waits for healthy upstreams. Additionally, nginx
resolves names via Docker's internal DNS at runtime when using `upstream` blocks, so transient
failures recover.
**Warning signs:** `docker compose logs nginx` shows "host not found in upstream" at startup.

### Pitfall 3: Certbot Renewal Fails After Initial Bootstrap
**What goes wrong:** Certificates expire after 90 days; certbot renewal fails silently.
**Why it happens:** The nginx config for port 80 must serve `/.well-known/acme-challenge/`
from the shared webroot volume even after switching to HTTPS. If the production.conf port 80
block does not include this location, renewal HTTP-01 challenge fails.
**How to avoid:** Always include `location /.well-known/acme-challenge/ { root /var/www/certbot; }`
in the HTTP server block of `production.conf`.
**Warning signs:** `docker compose logs certbot` shows "Challenge failed" or "Forbidden" errors.

### Pitfall 4: `NEXT_PUBLIC_API_URL` Still Points to Direct Port After Phase 15
**What goes wrong:** SSE EventSource in DashboardClient.tsx connects to
`http://VPS_HOST:8001/reports/stream/...` directly (bypassing nginx) — TLS not enforced,
JWT exposed over HTTP.
**Why it happens:** `NEXT_PUBLIC_API_URL` is baked into the Next.js build at build time.
The value in `.env` must be updated to `https://stratum.example.com` before `docker compose build`.
**How to avoid:** Update `.env` and `.env.example` with `NEXT_PUBLIC_API_URL=https://$DOMAIN`
(no port, no trailing slash). Rebuild frontend container after changing this value.
**Warning signs:** Browser DevTools Network tab shows EventSource connecting to port 8001.

### Pitfall 5: Port Removal from Frontend/Reasoning-Engine Breaks Local Dev Without Override
**What goes wrong:** After removing `ports:` from frontend and reasoning-engine in `docker-compose.yml`,
developers running `docker compose up` without the override can't access services directly.
**Why it happens:** The override file adds nginx + exposes port 80 for local dev, but if
docker-compose.override.yml is gitignored or missing, local dev breaks.
**How to avoid:** Commit `docker-compose.override.yml` to git. It's safe — it contains no secrets,
only service configuration adjustments for local development.
**Warning signs:** `curl http://localhost:3000` fails after removing ports from base compose file.

### Pitfall 6: mem_limit with Legacy Key
**What goes wrong:** Docker Compose emits deprecation warnings if `mem_limit` format is incorrect.
**Why it happens:** The project uses the legacy `mem_limit: 128m` key (confirmed in existing
compose file for all other services). This is already established project convention.
**How to avoid:** Follow existing pattern — `mem_limit: 128m` on the nginx service.

## Code Examples

Verified patterns from official sources and existing project code:

### nginx/local.conf — Local HTTP-Only Config
```nginx
# Source: nginx.org official docs + project decisions (CONTEXT.md)
upstream frontend_upstream {
    server frontend:3000;
    keepalive 16;
}

upstream reasoning_upstream {
    server reasoning-engine:8000;
    keepalive 16;
}

server {
    listen 80;
    server_name _;

    # SSE stream route — buffering disabled
    location ~ ^/api/reports/stream/ {
        proxy_pass http://reasoning_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        gzip off;
        add_header X-Accel-Buffering no;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # All other /api/* routes — normal buffered proxy
    location /api/ {
        proxy_pass http://reasoning_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend — all other routes
    location / {
        proxy_pass http://frontend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### nginx/production.conf — HTTPS + HTTP Redirect
```nginx
# Source: Let's Encrypt certbot patterns + nginx.org official docs
upstream frontend_upstream {
    server frontend:3000;
    keepalive 16;
}

upstream reasoning_upstream {
    server reasoning-engine:8000;
    keepalive 16;
}

# HTTP: ACME challenge + redirect
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl;
    server_name DOMAIN_PLACEHOLDER;

    ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;

    # SSE stream route — buffering disabled
    location ~ ^/api/reports/stream/ {
        proxy_pass http://reasoning_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        gzip off;
        add_header X-Accel-Buffering no;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # All other /api/* routes
    location /api/ {
        proxy_pass http://reasoning_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://frontend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### docker-compose.yml nginx service addition (base)
```yaml
# Source: existing project patterns (docker-compose.yml) + CONTEXT.md locked decisions
  nginx:
    image: nginx:alpine
    mem_limit: 128m
    restart: unless-stopped
    depends_on:
      frontend:
        condition: service_healthy
      reasoning-engine:
        condition: service_healthy
    volumes:
      - ./nginx/production.conf:/etc/nginx/conf.d/default.conf:ro
      - letsencrypt:/etc/letsencrypt:ro
      - certbot_webroot:/var/www/certbot:ro
    ports:
      - "80:80"
      - "443:443"
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:80 || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 20s
    networks:
      - reasoning
    profiles: ["reasoning"]

  certbot:
    image: certbot/certbot:latest
    restart: unless-stopped
    volumes:
      - letsencrypt:/etc/letsencrypt:rw
      - certbot_webroot:/var/www/certbot:rw
    entrypoint: ["/bin/sh", "-c"]
    command:
      - "while true; do certbot renew --webroot --webroot-path /var/www/certbot/ --quiet && sleep 12h; done"
    profiles: ["reasoning"]
```

### docker-compose.override.yml (local dev, auto-merged)
```yaml
# Source: Docker Compose override pattern (docs.docker.com/compose/how-tos/production/)
services:
  nginx:
    volumes:
      - ./nginx/local.conf:/etc/nginx/conf.d/default.conf:ro
    ports:
      - "80:80"
    # Override: no letsencrypt volume, no certbot, HTTP only

  certbot:
    # Disable certbot in local dev by overriding entrypoint to no-op
    entrypoint: ["echo", "certbot disabled in local dev"]
    restart: "no"
```

### .env.example additions
```bash
# nginx/TLS (Phase 15)
DOMAIN=stratum.example.com
CERTBOT_EMAIL=admin@example.com
NEXT_PUBLIC_API_URL=https://stratum.example.com
```

### Verifying SSE end-to-end through nginx
```bash
# Source: curl manual, verified pattern for SSE testing
# Test local (HTTP):
curl -N -H "Authorization: Bearer <token>" http://localhost/api/reports/stream/<job_id>

# Test production (HTTPS):
curl -N -H "Authorization: Bearer <token>" https://stratum.example.com/api/reports/stream/<job_id>

# Events should arrive one-by-one in real time, not as a single batch
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| docker-compose (v1, separate binary) | `docker compose` plugin (v2) | 2022 | No `docker-compose` command; all Compose operations via `docker compose` |
| Manual cert renewal cron on host | certbot Docker container renewal loop | 2019+ | No host cron dependency; renewal is containerized and portable |
| nginx proxy_pass direct to hostname | upstream blocks with keepalive | Stable nginx feature | TCP connection reuse; matters less at low traffic but establishes correct pattern |

**Deprecated/outdated:**
- `docker-compose.yml` v2/v3 format schema keys: project uses current compose spec (no `version:` key in compose file — confirmed by inspecting existing docker-compose.yml which has no `version:` key).
- Host-level certbot (apt install certbot): works but creates host dependency; Docker container approach is portable.

## Open Questions

1. **DOMAIN substitution in production.conf**
   - What we know: CONTEXT.md says `NEXT_PUBLIC_API_URL=https://stratum.example.com`; the actual domain is a VPS deployment decision
   - What's unclear: Whether the production.conf should use a literal domain string or use nginx's `$DOMAIN` env substitution via `envsubst`
   - Recommendation: Use literal `DOMAIN_PLACEHOLDER` string in production.conf template and document that the deployer must replace it, OR pass via `NGINX_ENVSUBST_OUTPUT_DIR` with nginx official image's built-in envsubst support. The simpler approach is to use the `DOMAIN` env var with nginx's `envsubst` entrypoint — `nginx:alpine` supports this natively.

2. **certbot disable strategy in local dev override**
   - What we know: certbot should not run locally; docker-compose.override.yml must suppress it
   - What's unclear: Best way to disable a service in override without removing it (profiles can't be overridden)
   - Recommendation: Override the certbot entrypoint to a no-op (`echo`) and set `restart: "no"` — keeps the service defined but harmless locally. Alternatively, certbot service could use a dedicated `production` profile and only be activated in production.

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest (existing, reasoning/tests/) |
| Config file | reasoning/pytest.ini or pyproject.toml (existing) |
| Quick run command | `docker compose exec reasoning-engine pytest tests/api/ -x -q` |
| Full suite command | `docker compose exec reasoning-engine pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| INFR-02 | nginx reverse proxy running on port 80/443 | smoke | `curl -sf http://localhost/api/health` | Wave 0 |
| INFR-02 | SSE events not buffered through nginx | smoke | `curl -N http://localhost/api/reports/stream/<id>` (manual verify real-time) | manual-only |
| INFR-02 | HTTP redirects to HTTPS on production | smoke | `curl -I http://$DOMAIN` returns 301 | manual-only (needs VPS) |
| INFR-02 | Unauthenticated /api/* returns 401 not 502 | smoke | `curl -sf http://localhost/api/watchlist` returns HTTP 401 | Wave 0 |
| INFR-02 | All 10 services pass health checks | smoke | `docker compose ps` shows all services healthy | manual-only |

### Sampling Rate
- **Per task commit:** `docker compose ps` (verify services start cleanly)
- **Per wave merge:** `curl` smoke tests against running nginx
- **Phase gate:** All 10 services healthy + SSE verified end-to-end before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scripts/smoke-test-nginx.sh` — basic curl checks against nginx (401 on unauth, 200 on health, 200 on frontend root) — covers INFR-02

## Sources

### Primary (HIGH confidence)
- nginx.org/en/docs/http/ngx_http_proxy_module.html — proxy_buffering, proxy_read_timeout official documentation
- nginx.org/en/docs/http/ngx_http_upstream_module.html — upstream blocks, keepalive directive
- docs.docker.com/compose/how-tos/production/ — Docker Compose override file pattern for production

### Secondary (MEDIUM confidence)
- oneuptime.com/blog/post/2025-12-16-server-sent-events-nginx/view — SSE nginx configuration (2025, verified against nginx official docs)
- ecostack.dev/posts/nginx-lets-encrypt-certificate-https-docker-compose/ — certbot/certbot Docker renewal loop pattern
- blog.jarrousse.org (2022) — Two-phase certbot bootstrap pattern (chicken-and-egg TLS problem)

### Tertiary (LOW confidence)
- Various community sources on certbot renewal loop timing (12h interval) — consistent across multiple sources, treat as confirmed MEDIUM

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — nginx:alpine and certbot/certbot are official images; directives verified against nginx.org
- Architecture: HIGH — Docker Compose override pattern is official Docker documentation; SSE directives verified against nginx official module docs
- Pitfalls: MEDIUM-HIGH — SSE buffering pitfall verified against nginx docs; certbot renewal pitfall from multiple community sources consistent with official certbot docs

**Research date:** 2026-03-19
**Valid until:** 2026-06-19 (stable infra domain; nginx and certbot change slowly)
