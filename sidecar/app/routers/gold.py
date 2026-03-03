"""
Gold data ingestion endpoints for the Stratum Data Sidecar.
Phase 2 | Plan 02

Endpoints:
  POST /ingest/gold/fred-price   — Fetch and upsert FRED GOLDAMGBD228NLBM gold price
  POST /ingest/gold/gld-etf      — Fetch and upsert GLD ETF weekly OHLCV via yfinance
  POST /ingest/gold/wgc-flows    — WGC ETF flow ingestion (returns 501 — known limitation)

Error mapping:
  502 — Upstream API error (FRED / yfinance failure)
  204 — No data returned for the given parameters
  501 — Not Implemented (WGC flows — JS-rendered portal)
  503 — Service unavailable (missing FRED_API_KEY)
  500 — Unexpected internal error
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import gold_service
from app.services.gold_service import WGCNotImplemented

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class GoldIngestRequest(BaseModel):
    start_date: date
    end_date: date
    resolution: str = "weekly"


class IngestResponse(BaseModel):
    status: str                         # "success" | "partial" | "empty" | "not_implemented"
    rows_ingested: int
    data_as_of: Optional[str] = None    # ISO date string of most recent row
    error_message: Optional[str] = None
    anomaly_detected: bool = False


# ---------------------------------------------------------------------------
# POST /ingest/gold/fred-price
# ---------------------------------------------------------------------------

@router.post("/fred-price", response_model=IngestResponse)
async def ingest_gold_fred_price(
    request: GoldIngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Fetch LBMA gold PM fix from FRED series GOLDAMGBD228NLBM and upsert to gold_price.

    data_as_of = the FRED observation date (the day the price was fixed), NOT ingestion time.
    Historical backfill: pass start_date 10 years ago to ingest the full history.
    Upsert is idempotent: re-running with the same date range produces no duplicates.
    """
    try:
        result = gold_service.fetch_and_upsert_gold_fred_price(
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            db_session=db,
        )
    except EnvironmentError as exc:
        logger.error("FRED API key missing: %s", exc)
        raise HTTPException(status_code=503, detail=f"FRED_API_KEY not configured: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during FRED gold price ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    if result["rows_ingested"] == 0:
        raise HTTPException(
            status_code=204,
            detail="No gold price data returned for the given date range",
        )

    return IngestResponse(
        status="success",
        rows_ingested=result["rows_ingested"],
        data_as_of=result.get("data_as_of"),
    )


# ---------------------------------------------------------------------------
# POST /ingest/gold/gld-etf
# ---------------------------------------------------------------------------

@router.post("/gld-etf", response_model=IngestResponse)
async def ingest_gold_gld_etf(
    request: GoldIngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Fetch GLD ETF OHLCV from yfinance and upsert to gold_etf_ohlcv.

    resolution defaults to "weekly" (yfinance "1wk").
    data_as_of = the bar's week-start date normalized to midnight UTC.
    Historical backfill: pass start_date 10 years ago for full history.
    Upsert is idempotent: re-running produces no duplicates.
    """
    try:
        result = gold_service.fetch_and_upsert_gld_etf(
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            resolution=request.resolution,
            db_session=db,
        )
    except Exception as exc:
        logger.exception("Unexpected error during GLD ETF ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    if result["rows_ingested"] == 0:
        raise HTTPException(
            status_code=204,
            detail="No GLD ETF data returned for the given date range",
        )

    return IngestResponse(
        status="success",
        rows_ingested=result["rows_ingested"],
        data_as_of=result.get("data_as_of"),
    )


# ---------------------------------------------------------------------------
# POST /ingest/gold/wgc-flows
# ---------------------------------------------------------------------------

@router.post("/wgc-flows", response_model=IngestResponse)
async def ingest_gold_wgc_flows(
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    WGC ETF flow and central bank gold buying ingestion — NOT IMPLEMENTED.

    The World Gold Council Goldhub portal is JavaScript-rendered and does not
    expose a stable direct-download URL. This endpoint returns 501 until a
    reliable ingestion method is available.

    Known limitation: import WGC data manually via CSV upload.
    See deferred-items.md for details.
    """
    try:
        gold_service.fetch_and_upsert_wgc_flows(db_session=db)
        # Should not reach here — stub always raises
        return IngestResponse(status="success", rows_ingested=0)
    except WGCNotImplemented as exc:
        logger.info("WGC flows endpoint called — returning 501 (known limitation): %s", exc)
        raise HTTPException(
            status_code=501,
            detail=(
                "WGC Goldhub scraping is not implemented. "
                "The portal is JavaScript-rendered and does not expose a stable download URL. "
                "Import WGC data manually via CSV upload."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during WGC flows ingest")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
