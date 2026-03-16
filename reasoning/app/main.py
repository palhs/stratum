"""
Stratum Reasoning Engine — FastAPI application entry point.

Starts with lifespan context manager that initializes:
  - PostgreSQL engine (SQLAlchemy)
  - Neo4j driver
  - Qdrant client
  - SSE job queues

Routers registered:
  - health: GET /health
"""
import logging

from fastapi import FastAPI

from app.dependencies import lifespan
from app.routers import health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stratum Reasoning Engine",
    lifespan=lifespan,
)

app.include_router(health.router)

logger.info("Stratum Reasoning Engine configured.")
