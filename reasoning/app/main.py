"""
Stratum Reasoning Engine — FastAPI application entry point.

Starts with lifespan context manager that initializes:
  - PostgreSQL engine (SQLAlchemy)
  - Neo4j driver
  - Qdrant client
  - SSE job queues

Routers registered:
  - health:     GET /health
  - reports:    POST /reports/generate [auth], GET /reports/by-ticker/{symbol} [auth],
                GET /reports/stream/{job_id}, GET /reports/{job_id}
  - tickers:    GET /tickers/{symbol}/ohlcv [auth]
  - watchlist:  GET /watchlist [auth], PUT /watchlist [auth]
"""
import logging

from fastapi import FastAPI

from reasoning.app.dependencies import lifespan
from reasoning.app.routers import health, reports, tickers, watchlist

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

# Tickers router — prefix /tickers; requires Supabase JWT auth
app.include_router(tickers.router, prefix="/tickers", tags=["tickers"])

# Watchlist router — prefix /watchlist; requires Supabase JWT auth
app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])

logger.info("Stratum Reasoning Engine configured.")
