# Stratum — Deployment Guide

## Environments

| Environment | Frontend + Reasoning | Infrastructure | nginx config | Command |
|-------------|---------------------|----------------|--------------|---------|
| **Dev** (daily) | Native on Mac (hot reload) | Docker | `nginx/dev.conf` | `make dev` |
| **Integration** | Docker (built images) | Docker | `nginx/local.conf` | `make up-integration` |
| **Production** | Docker | Docker + TLS | `nginx/production.conf` | See VPS section |

## Local Development (Mac)

Services run natively for instant hot reload. Storage and nginx run in Docker.

### Prerequisites

- Docker Desktop for Mac
- Node.js 20+ (for frontend)
- Python 3.12 with venv (for reasoning-engine)
- `.env.local` configured (copy from `.env.example`)

### First-time setup

```bash
# Install frontend dependencies
cd frontend && npm install && cd ..

# Create reasoning venv (if not exists)
cd reasoning && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
```

### Daily workflow

```bash
# Terminal 1: Start storage + nginx
make dev

# Terminal 2: Frontend with hot reload
make dev-frontend

# Terminal 3: Reasoning engine with auto-reload
make dev-reasoning
```

### Access points

| URL | What |
|-----|------|
| `http://localhost` | Full app through nginx (same as production routing) |
| `http://localhost:3000` | Frontend directly (skip nginx) |
| `http://localhost:8000` | Reasoning API directly (skip nginx) |
| `http://localhost:8000/docs` | FastAPI Swagger UI |
| `http://localhost:7474` | Neo4j Browser |
| `http://localhost:5678` | n8n UI (requires `make up-ingestion`) |

### How it works

- Storage runs via Docker Compose (`make dev-storage` / `--profile storage`)
- nginx runs as a standalone Docker container (`make dev-nginx`) using `nginx/dev.conf`
  - Proxies to `host.docker.internal` which resolves to your Mac from inside Docker
  - No dependency on frontend/reasoning-engine containers
- `docker-compose.override.yml` auto-applies and stubs out frontend/reasoning-engine/nginx
  so `docker-buildx` is not required for storage-only workflows
- Frontend and reasoning-engine run natively with hot reload

### Useful commands

```bash
make ps             # Check running services
make health         # Health status of all services
make logs           # Stream all logs
make down           # Stop everything (storage + nginx)
make dev-storage    # Restart just databases
make dev-nginx-stop # Stop just the nginx proxy
```

## Integration Testing

Full stack in Docker — validates nginx routing, SSE streaming, and service discovery.

```bash
# Requires docker-buildx plugin
make up-integration
```

This builds frontend and reasoning-engine images and starts everything with `nginx/local.conf` (Docker internal DNS names). Use this to verify the production-like setup before deploying.

### Verify

```bash
# Routing
curl http://localhost/              # Frontend
curl http://localhost/api/v1/health # Reasoning API through nginx

# SSE streaming (replace with a real report ID)
curl -N http://localhost/api/reports/stream/{report-id}
```

## VPS Production Deployment

### Prerequisites

- VPS with 4GB+ RAM and 4GB swap configured (see `docker-compose.yml` header)
- Domain pointed at VPS IP (A record)
- Docker + Docker Compose installed on VPS

### Initial setup

```bash
# 1. Clone repo on VPS
git clone <repo-url> /opt/stratum && cd /opt/stratum

# 2. Remove dev override (not needed on VPS)
rm -f docker-compose.override.yml

# 3. Create production env
cp .env.example .env.production

# Edit .env.production:
#   - Set real passwords for POSTGRES_PASSWORD, NEO4J_PASSWORD, QDRANT_API_KEY, N8N_ENCRYPTION_KEY
#   - Set SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_JWKS_URL
#   - Set GEMINI_API_KEY
#   - Set DOMAIN=yourdomain.com
#   - Set CERTBOT_EMAIL=admin@yourdomain.com
#   - Set NEXT_PUBLIC_API_URL=https://yourdomain.com

# 4. Replace domain placeholder in nginx production config
sed -i "s/DOMAIN_PLACEHOLDER/yourdomain.com/g" nginx/production.conf

# 5. First boot — get TLS certificate
#    Start nginx on HTTP first (certbot needs port 80 for ACME challenge)
#    Temporarily comment out the HTTPS server block in production.conf,
#    then run:
docker compose --env-file .env.production --profile reasoning up -d

# 6. Issue certificate
docker compose --env-file .env.production run --rm certbot certonly \
  --webroot --webroot-path /var/www/certbot/ \
  -d yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos --no-eff-email

# 7. Restore the HTTPS server block in production.conf, then restart nginx
docker compose --env-file .env.production restart nginx
```

### Ongoing operations

```bash
# Start all services
docker compose --env-file .env.production --profile storage --profile ingestion --profile reasoning up -d

# View logs
docker compose --env-file .env.production logs -f nginx

# Update deployment
git pull
docker compose --env-file .env.production --profile reasoning up -d --build

# Certificate auto-renewal is handled by the certbot container (checks every 12h)
# To manually test renewal:
docker compose --env-file .env.production run --rm certbot renew --dry-run
```

### Verify production

```bash
# HTTPS and redirect
curl -I http://yourdomain.com        # Should 301 → https://
curl https://yourdomain.com          # Should return frontend

# API routing
curl https://yourdomain.com/api/v1/health

# TLS certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com < /dev/null 2>/dev/null | openssl x509 -noout -dates
```

## nginx Configuration Reference

| File | Upstreams | TLS | Used by |
|------|-----------|-----|---------|
| `nginx/dev.conf` | `host.docker.internal:3000/8000` | No | `make dev` (Mac native) |
| `nginx/local.conf` | `frontend:3000`, `reasoning-engine:8000` | No | `make up-integration` (all Docker) |
| `nginx/production.conf` | `frontend:3000`, `reasoning-engine:8000` | Yes | VPS with real domain |

All three configs share identical routing rules:
- `/ → frontend` (catch-all)
- `/api/* → reasoning-engine` (buffered proxy)
- `/api/reports/stream/* → reasoning-engine` (SSE, unbuffered, 600s timeout)
