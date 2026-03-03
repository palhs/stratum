"""
Stratum Data Sidecar — FastAPI application entry point.
Phase 2 | Plan 01

Internal service on the ingestion network.
n8n calls endpoints by service name: http://data-sidecar:8000/...
"""

import logging

from fastapi import FastAPI

from app.routers import health, vnstock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stratum Data Sidecar",
    description="Internal data ingestion sidecar for the Stratum platform.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Router registration
# Additional routers (gold, fred, wgc, markers) will be added in later plans.
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(vnstock.router, prefix="/ingest/vnstock", tags=["vnstock"])


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Sidecar ready")
