"""
Stratum Data Sidecar — FastAPI application entry point.
Phase 2 | Plans 01, 02, 03

Internal service on the ingestion network.
n8n calls endpoints by service name: http://data-sidecar:8000/...
"""

import logging

from fastapi import FastAPI

from app.routers import fred, gold, health, markers, vnstock

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
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(vnstock.router, prefix="/ingest/vnstock", tags=["vnstock"])
app.include_router(gold.router, prefix="/ingest/gold", tags=["gold"])
app.include_router(fred.router, prefix="/ingest/fred", tags=["fred"])
app.include_router(markers.router, prefix="/compute", tags=["markers"])


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Sidecar ready")
