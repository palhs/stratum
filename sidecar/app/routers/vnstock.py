"""
vnstock ingestion endpoints for the Stratum Data Sidecar.
Phase 2 | Plan 01 (updated Plan 04: pipeline logging + anomaly detection)

Endpoints:
  POST /ingest/vnstock/ohlcv          — Fetch and upsert VN30 weekly OHLCV data
  POST /ingest/vnstock/fundamentals   — Fetch and upsert VN30 fundamental ratios

Error mapping:
  502 — vnstock API error (upstream failure)
  204 — No data returned for the given parameters
  500 — Unexpected internal error

Plan 04 additions:
  - log_pipeline_run() called on every run (success and failure)
  - check_row_count_anomaly() called for vnstock endpoints only
  - duration_ms recorded via time.monotonic()
"""

import logging
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import vnstock_service
from app.services.pipeline_log_service import log_pipeline_run
from app.services.anomaly_service import check_row_count_anomaly

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
    - Every run writes to pipeline_run_log (success or failure).
    - Anomaly detection runs after successful ingestion (alert-only, never blocks).
    """
    pipeline_name = "vnstock_ohlcv"
    start_time = time.monotonic()

    try:
        result = vnstock_service.fetch_and_upsert_ohlcv(
            symbols=request.symbols,
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            resolution=request.resolution,
            db_session=db,
        )
    except vnstock_service.VnstockAPIError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.error("vnstock API error during OHLCV ingest: %s", exc)
        raise HTTPException(status_code=502, detail=f"vnstock API error: {exc}") from exc
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.exception("Unexpected error during OHLCV ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    rows_ingested = result["rows_ingested"]
    data_as_of = result.get("data_as_of") or str(request.end_date)

    if rows_ingested == 0:
        log_pipeline_run(
            db, pipeline_name, "partial", 0, data_as_of,
            error_message="No data returned for the given parameters",
            duration_ms=duration_ms,
        )
        raise HTTPException(
            status_code=204,
            detail="No data returned for the given parameters",
        )

    # Anomaly detection — alert-only, never blocks
    anomaly_detected = check_row_count_anomaly(db, pipeline_name, rows_ingested)

    log_pipeline_run(
        db, pipeline_name, "success", rows_ingested, data_as_of,
        duration_ms=duration_ms,
    )

    return IngestResponse(
        status="success",
        rows_ingested=rows_ingested,
        data_as_of=result.get("data_as_of"),
        anomaly_detected=anomaly_detected,
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
    - Every run writes to pipeline_run_log (success or failure).
    - Anomaly detection runs after successful ingestion (alert-only, never blocks).
    """
    pipeline_name = "vnstock_fundamentals"
    start_time = time.monotonic()

    try:
        result = vnstock_service.fetch_and_upsert_fundamentals(
            symbols=request.symbols,
            db_session=db,
        )
    except vnstock_service.VnstockAPIError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.error("vnstock API error during fundamentals ingest: %s", exc)
        raise HTTPException(status_code=502, detail=f"vnstock API error: {exc}") from exc
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.exception("Unexpected error during fundamentals ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    rows_ingested = result["rows_ingested"]
    data_as_of = result.get("data_as_of") or str(request.end_date)

    if rows_ingested == 0:
        log_pipeline_run(
            db, pipeline_name, "partial", 0, data_as_of,
            error_message="No data returned for the given parameters",
            duration_ms=duration_ms,
        )
        raise HTTPException(
            status_code=204,
            detail="No data returned for the given parameters",
        )

    # Anomaly detection — alert-only, never blocks
    anomaly_detected = check_row_count_anomaly(db, pipeline_name, rows_ingested)

    log_pipeline_run(
        db, pipeline_name, "success", rows_ingested, data_as_of,
        duration_ms=duration_ms,
    )

    return IngestResponse(
        status="success",
        rows_ingested=rows_ingested,
        data_as_of=result.get("data_as_of"),
        anomaly_detected=anomaly_detected,
    )
