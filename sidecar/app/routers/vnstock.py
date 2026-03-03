"""
vnstock ingestion endpoints for the Stratum Data Sidecar.
Phase 2 | Plan 01

Endpoints:
  POST /ingest/vnstock/ohlcv          — Fetch and upsert VN30 weekly OHLCV data
  POST /ingest/vnstock/fundamentals   — Fetch and upsert VN30 fundamental ratios

Error mapping:
  502 — vnstock API error (upstream failure)
  204 — No data returned for the given parameters
  500 — Unexpected internal error
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import vnstock_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    start_date: date
    end_date: date
    symbols: Optional[list[str]] = None
    resolution: str = "weekly"


class IngestResponse(BaseModel):
    status: str                         # "success" | "partial" | "empty"
    rows_ingested: int
    data_as_of: Optional[str] = None    # ISO date string of most recent row
    error_message: Optional[str] = None
    anomaly_detected: bool = False


# ---------------------------------------------------------------------------
# POST /ingest/vnstock/ohlcv
# ---------------------------------------------------------------------------

@router.post("/ohlcv", response_model=IngestResponse)
async def ingest_vnstock_ohlcv(
    request: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Fetch VN30 OHLCV bars from vnstock VCI source and upsert to stock_ohlcv.

    - If symbols is omitted, all current VN30 constituents are fetched (live, not hard-coded).
    - Upsert is idempotent: re-running with the same date range produces no duplicates.
    - data_as_of and ingested_at are populated on every row (DATA-07).
    """
    try:
        result = vnstock_service.fetch_and_upsert_ohlcv(
            symbols=request.symbols,
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            resolution=request.resolution,
            db_session=db,
        )
    except vnstock_service.VnstockAPIError as exc:
        logger.error("vnstock API error during OHLCV ingest: %s", exc)
        raise HTTPException(status_code=502, detail=f"vnstock API error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during OHLCV ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    if result["rows_ingested"] == 0:
        raise HTTPException(
            status_code=204,
            detail="No data returned for the given parameters",
        )

    return IngestResponse(
        status="success",
        rows_ingested=result["rows_ingested"],
        data_as_of=result.get("data_as_of"),
        anomaly_detected=result.get("anomaly_detected", False),
    )


# ---------------------------------------------------------------------------
# POST /ingest/vnstock/fundamentals
# ---------------------------------------------------------------------------

@router.post("/fundamentals", response_model=IngestResponse)
async def ingest_vnstock_fundamentals(
    request: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Fetch VN30 fundamental ratios from vnstock VCI source and upsert to stock_fundamentals.

    - If symbols is omitted, all current VN30 constituents are fetched (live, not hard-coded).
    - Upsert is idempotent: re-running with the same parameters produces no duplicates.
    - data_as_of and ingested_at are populated on every row (DATA-07).
    """
    try:
        result = vnstock_service.fetch_and_upsert_fundamentals(
            symbols=request.symbols,
            db_session=db,
        )
    except vnstock_service.VnstockAPIError as exc:
        logger.error("vnstock API error during fundamentals ingest: %s", exc)
        raise HTTPException(status_code=502, detail=f"vnstock API error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during fundamentals ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    if result["rows_ingested"] == 0:
        raise HTTPException(
            status_code=204,
            detail="No data returned for the given parameters",
        )

    return IngestResponse(
        status="success",
        rows_ingested=result["rows_ingested"],
        data_as_of=result.get("data_as_of"),
        anomaly_detected=result.get("anomaly_detected", False),
    )
