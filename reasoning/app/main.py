"""
Stratum Reasoning Engine — FastAPI application entry point.

Starts with lifespan context manager that initializes:
  - PostgreSQL engine (SQLAlchemy)
  - Neo4j driver
  - Qdrant client
  - SSE job queues

Routers registered:
  - health:   GET /health
  - reports:  POST /reports/generate, GET /reports/{job_id}
"""
import logging

from fastapi import FastAPI

from app.dependencies import lifespan
from app.routers import health, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stratum Reasoning Engine",
    lifespan=lifespan,
)

# Health router (no prefix — /health)
app.include_router(health.router)

# Reports router — prefix /reports; stream endpoint (Plan 03) will be added before /{job_id}
app.include_router(reports.router, prefix="/reports", tags=["reports"])

logger.info("Stratum Reasoning Engine configured.")
