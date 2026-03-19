# Phase 15: nginx and Docker Compose Integration - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire all services through an nginx reverse proxy with path-based routing on a single domain. Local-first: HTTP-only nginx config for Docker Compose development. Production-ready: TLS via certbot Docker container, SSE buffering disabled for stream routes, host ports removed from frontend and reasoning-engine. The system is deployable with `docker compose up -d`.

</domain>

<decisions>
## Implementation Decisions

### Routing topology
- Single domain, path-based routing: `/` -> frontend:3000, `/api/*` -> reasoning-engine:8000
- Same-origin means no CORS headers needed — browser sees one domain for everything
- n8n stays on separate port 5678 directly (admin tool, no nginx proxy)
- Neo4j Browser stays on port 7474/7687 directly (admin tool)
- Frontend and reasoning-engine host port mappings removed — only nginx exposes 80/443
- `NEXT_PUBLIC_API_URL` set to full domain URL (e.g., `https://stratum.example.com`) — absolute paths in config

### TLS and domain setup
- Local-first approach: HTTP only for local development, TLS for VPS deployment
- Two nginx config files: `nginx/local.conf` (HTTP, port 80) and `nginx/production.conf` (HTTPS + HTTP redirect + certbot)
- Docker Compose override pattern: `docker-compose.override.yml` for local config (auto-merged), production runs with `--file docker-compose.yml` only
- Certbot runs as a Docker container alongside nginx, shared volume for certificates
- Auto-renewal via certbot container timer/cron
- Domain DNS is a VPS prerequisite — not part of this phase's implementation

### SSE proxy config
- SSE-specific directives applied only to `/api/reports/stream/*` location block (not all `/api/*`)
- Directives: `proxy_buffering off`, `X-Accel-Buffering: no`, chunked transfer encoding
- `proxy_read_timeout 600s` (10 minutes) on stream routes — generous buffer above 2-5 min pipeline runtime
- Other `/api/*` routes use normal buffered proxy behavior
- FastAPI keepalive pings already implemented (Phase 8/13) — prevent premature nginx timeout

### Service wiring
- nginx image: `nginx:alpine` (~40MB, minimal)
- `mem_limit: 128m` for nginx container
- nginx joins reasoning network only (frontend + reasoning-engine)
- nginx profile: `["reasoning"]` — same as frontend and reasoning-engine
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Docker infrastructure
- `docker-compose.yml` — Current 10-service Docker Compose with dual-network isolation, profiles, health checks
- `.env.example` — Environment variable template (needs domain/TLS vars added)
- `scripts/provision-vps.sh` — VPS provisioning script (may need certbot/nginx additions)

### Frontend API routing
- `frontend/src/lib/api.ts` — `NEXT_PUBLIC_API_URL` base URL usage, fetchAPI helper
- `frontend/src/components/dashboard/DashboardClient.tsx` — EventSource SSE connection using `NEXT_PUBLIC_API_URL`
- `frontend/next.config.ts` — Current standalone output config (no rewrites needed with nginx)

### Backend SSE
- `reasoning/app/routers/reports.py` — SSE stream endpoint at GET /reports/stream/{job_id}, ping keepalive

### Prior phase context
- `.planning/phases/08-fastapi-gateway-and-docker-service/08-CONTEXT.md` — Docker service config decisions (port 8001, mem_limit 2g, reasoning network)
- `.planning/phases/13-report-generation-with-sse-progress/13-CONTEXT.md` — SSE streaming architecture, EventSource connection pattern

### Requirements
- `.planning/REQUIREMENTS.md` section "Infrastructure" — INFR-02 (nginx reverse proxy with SSE buffering disabled)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml`: Well-structured with profiles (storage, ingestion, reasoning), dual networks, health checks on all services — nginx service follows established patterns
- `scripts/provision-vps.sh`: Existing VPS setup script — can be extended for certbot/domain prep
- `.env.example`: Existing env template — extend with DOMAIN, CERTBOT_EMAIL vars

### Established Patterns
- Docker: `mem_limit` via legacy key, named volumes, `restart: unless-stopped`, health checks on all long-running services
- Profiles: `["reasoning"]` for all frontend-tier services
- Networks: `reasoning` for frontend/API, `ingestion` for n8n/sidecar, storage services join both
- Internal-only services have no host port mapping (postgres, qdrant, data-sidecar)

### Integration Points
- Remove `ports` from frontend and reasoning-engine services in docker-compose.yml
- Add nginx service to docker-compose.yml on reasoning network
- Add `NEXT_PUBLIC_API_URL` with full domain URL in .env (replacing VPS_HOST:8001 pattern)
- Create `nginx/` directory with local.conf and production.conf
- Create `docker-compose.override.yml` for local development (mounts local.conf, exposes port 80)
- Production compose excludes override (mounts production.conf, exposes 80+443, adds certbot service)

</code_context>

<specifics>
## Specific Ideas

- Local-first means `docker compose up` just works on a dev machine — no domain, no TLS, no certbot required
- Production deployment is a separate step: configure domain DNS, run certbot init, then `docker compose -f docker-compose.yml up -d`
- The override pattern is standard Docker Compose — developers familiar with Docker will recognize it immediately

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-nginx-and-docker-compose-integration*
*Context gathered: 2026-03-19*
