# =============================================================================
# Stratum Data Sidecar — Python 3.12 FastAPI container
# Phase 2 | Plan 01
# =============================================================================
# Internal service only — no host port mapping.
# n8n calls data-sidecar:8000 on the ingestion network.
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Healthcheck: verify the FastAPI /health endpoint responds
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=30s \
    CMD curl -sf http://localhost:8000/health || exit 1

# Run uvicorn (binding to all interfaces so Docker can reach it)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
