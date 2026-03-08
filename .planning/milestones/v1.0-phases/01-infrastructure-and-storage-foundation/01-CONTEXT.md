# Phase 1: Infrastructure and Storage Foundation - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Docker Compose environment with all storage services (PostgreSQL, Neo4j, Qdrant) and n8n running with correct schemas from day one. Network boundary enforced between ingestion and reasoning pipelines at the Docker network level. Supabase is cloud-hosted (auth only). No Nginx reverse proxy yet — direct port access over HTTP.

</domain>

<decisions>
## Implementation Decisions

### VPS and Hosting
- Own Ubuntu server, dedicated to Stratum
- 8GB RAM initially, scalable to 16GB if performance requires it
- IP-only access (no domain yet) — HTTP only, SSL deferred until domain is ready
- Docker and Docker Compose need to be installed as part of Phase 1 provisioning
- Deployment via git pull on VPS — no CI/CD pipeline for now
- No Nginx reverse proxy in Phase 1 — services expose ports directly on host

### Service Versions and Editions
- Neo4j Community Edition (free, sufficient for single-user)
- PostgreSQL 16, Neo4j 5.x, Qdrant latest stable — all pinned to specific versions in compose file
- Supabase Cloud free tier for auth/user management (not self-hosted — saves ~6 containers worth of RAM)
- n8n self-hosted in Docker Compose stack (needs direct access to storage services)
- Named Docker volumes for all persistent data (not bind mounts)
- No container resource limits — let Docker manage dynamically on 8GB
- Secrets managed via .env files (gitignored), not Docker secrets

### Network Boundary Enforcement
- Strict Docker network separation: two networks — `ingestion` (n8n + storage services) and `reasoning` (LangGraph/FastAPI + storage services)
- Storage services (PostgreSQL, Neo4j, Qdrant) attached to both networks — they are the only bridge
- n8n and LangGraph containers physically cannot reach each other
- Only admin UIs exposed on host: n8n UI (5678), Neo4j Browser (7474/7687), FastAPI (8000)
- Storage ports (PostgreSQL 5432, Qdrant 6333) internal only — not exposed on host
- Access control via built-in service auth (n8n auth, Neo4j auth) — no firewall rules

### Local Dev Workflow
- Develop locally on Mac with Docker Compose, deploy to VPS via git pull
- Single `docker-compose.yml` with environment-specific `.env` files (`.env.local`, `.env.production`)
- Docker Compose profiles for selective service startup: `storage` (PG, Neo4j, Qdrant), `ingestion` (n8n), `reasoning` (LangGraph, FastAPI)
- Makefile for common operations: `make up`, `make down`, `make reset-db`, `make migrate`

### Claude's Discretion
- Exact PostgreSQL table naming conventions and migration tooling
- Neo4j constraint creation approach (Cypher scripts vs application-managed)
- Qdrant collection configuration (vector dimensions, distance metric)
- Docker Compose health check implementation details
- Makefile target specifics beyond the standard operations

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for infrastructure setup.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — Phase 1 establishes the foundational patterns

### Integration Points
- Supabase Cloud project needs to be created and API keys added to .env
- VPS SSH access required for Docker installation and initial deployment

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-infrastructure-and-storage-foundation*
*Context gathered: 2026-03-03*
