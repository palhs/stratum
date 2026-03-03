"""
FRED macroeconomic indicator ingestion endpoints for the Stratum Data Sidecar.
Phase 2 | Plan 02 (updated Plan 04: pipeline logging)

Endpoints:
  POST /ingest/fred/indicators  — Fetch and upsert GDP, CPI, UNRATE, FEDFUNDS from FRED

Error mapping:
  503 — FRED_API_KEY not configured
  204 — No data returned for the given parameters
  500 — Unexpected internal error

Plan 04 additions:
  - log_pipeline_run() called on every run (success and failure)
  - duration_ms recorded via time.monotonic()
  - No anomaly detection for FRED endpoints (vnstock only)
"""

import logging
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import fred_service
from app.services.pipeline_log_service import log_pipeline_run

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class FredIngestRequest(BaseModel):
    start_date: date
    end_date: date
    series_ids: Optional[list[str]] = None  # Default: all configured series


class IngestResponse(BaseModel):
    status: str                         # "success" | "empty"
    rows_ingested: int
    data_as_of: Optional[str] = None    # ISO date string of most recent observation
    error_message: Optional[str] = None
    anomaly_detected: bool = False


# ---------------------------------------------------------------------------
# POST /ingest/fred/indicators
# ---------------------------------------------------------------------------

@router.post("/indicators", response_model=IngestResponse)
async def ingest_fred_indicators(
    request: FredIngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Fetch FRED macroeconomic indicators and upsert to fred_indicators.

    Default series: GDP (quarterly), CPIAUCSL (monthly), UNRATE (monthly), FEDFUNDS (monthly).
    Use series_ids to fetch a subset of the configured series.

    data_as_of = the FRED observation period date (the period the data covers),
    NOT the ingestion timestamp. GDP "2024-10-01" = Q4 2024 data.

    Historical backfill: pass start_date 10+ years ago for full history.
    Upsert is idempotent: re-running with the same date range produces no duplicates.

    Missing FRED_API_KEY: returns 503 with clear error message.
    Every run writes to pipeline_run_log (success or failure).
    """
    pipeline_name = "fred_indicators"
    start_time = time.monotonic()

    try:
        result = fred_service.fetch_and_upsert_fred_indicators(
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            series_ids=request.series_ids,
            db_session=db,
        )
    except EnvironmentError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.error("FRED API key missing: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "FRED_API_KEY is not configured. "
                "Obtain a free API key at https://fred.stlouisfed.org/docs/api/api_key.html "
                f"and set FRED_API_KEY in your environment. Error: {exc}"
            ),
        ) from exc
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        log_pipeline_run(
            db, pipeline_name, "failure", 0, str(request.end_date),
            error_message=str(exc), duration_ms=duration_ms,
        )
        logger.exception("Unexpected error during FRED indicators ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    rows_ingested = result["rows_ingested"]
    data_as_of = result.get("data_as_of") or str(request.end_date)

    if rows_ingested == 0:
        log_pipeline_run(
            db, pipeline_name, "partial", 0, data_as_of,
            error_message="No FRED indicator data returned for the given date range and series IDs",
            duration_ms=duration_ms,
        )
        raise HTTPException(
            status_code=204,
            detail="No FRED indicator data returned for the given date range and series IDs",
        )

    log_pipeline_run(
        db, pipeline_name, "success", rows_ingested, data_as_of,
        duration_ms=duration_ms,
    )

    return IngestResponse(
        status="success",
        rows_ingested=rows_ingested,
        data_as_of=result.get("data_as_of"),
    )
