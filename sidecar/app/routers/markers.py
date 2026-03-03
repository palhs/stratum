"""
Structure marker computation endpoint for the Stratum Data Sidecar.
Phase 2 | Plan 03

Endpoint:
  POST /compute/structure-markers  — Compute and upsert all structure markers

Called by n8n AFTER data ingestion endpoints complete (Plan 04 wires this into
the n8n workflow). Depends on fresh OHLCV and fundamental data in PostgreSQL.

LangGraph reasoning nodes READ pre-computed markers — they NEVER compute them.
This endpoint populates the structure_markers table for all assets.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import markers_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class ComputeMarkersRequest(BaseModel):
    """
    Request body for POST /compute/structure-markers.

    asset_types: Optional list of asset types to process.
    If omitted, all three asset types are computed.
    Valid values: "stock", "gold_spot", "gold_etf"
    """
    asset_types: list[str] | None = None


class ComputeMarkersResponse(BaseModel):
    """
    Response for POST /compute/structure-markers.

    status:             "success" | "empty" (source tables have no data)
    total_rows_written: Total rows upserted to structure_markers
    breakdown:          Rows written per asset_type (e.g. {"stock": 7800, "gold_spot": 520})
    null_counts:        NULL count per marker column — health metric showing
                        how many rows have insufficient history for computation
    warning:            Optional warning message when source tables are empty
    """
    status: str
    total_rows_written: int
    breakdown: dict[str, int]
    null_counts: dict[str, int]
    warning: str | None = None


# ---------------------------------------------------------------------------
# POST /compute/structure-markers
# ---------------------------------------------------------------------------

@router.post("/structure-markers", response_model=ComputeMarkersResponse)
async def compute_structure_markers(
    request: ComputeMarkersRequest,
    db: Session = Depends(get_db),
) -> ComputeMarkersResponse:
    """
    Compute and upsert pre-computed structure markers for all assets.

    Reads OHLCV and gold price data from PostgreSQL, computes:
      - Moving averages: 10w, 20w, 50w
      - Drawdowns: full-history ATH and 52-week high (both computed)
      - Valuation percentile rank: 5y window for stocks, 10y for gold
      - P/E percentile rank: stocks only (NULL for gold)

    Full recompute strategy — idempotent via ON CONFLICT DO UPDATE.

    If source tables are empty (data not yet loaded), returns 200 with
    total_rows_written=0 and a warning message. This is not an error —
    source data may not have been ingested yet.
    """
    asset_types = request.asset_types
    if asset_types is not None:
        # Validate asset_type values
        valid_types = {"stock", "gold_spot", "gold_etf"}
        invalid = set(asset_types) - valid_types
        if invalid:
            logger.warning(
                "compute_structure_markers: unknown asset_types %s — proceeding with valid subset",
                invalid,
            )
            asset_types = [t for t in asset_types if t in valid_types]
        if not asset_types:
            return ComputeMarkersResponse(
                status="empty",
                total_rows_written=0,
                breakdown={},
                null_counts={},
                warning="No valid asset_types provided. Valid values: stock, gold_spot, gold_etf",
            )

    try:
        result = markers_service.compute_and_upsert_markers(
            db=db,
            asset_types=asset_types,
        )
    except Exception as exc:
        logger.exception("Unexpected error during structure marker computation")
        # Propagate as a 500 — do NOT swallow silently
        raise

    total = result["total_rows_written"]
    breakdown = result["breakdown"]
    null_counts = result["null_counts"]

    if total == 0:
        logger.warning(
            "compute_structure_markers: 0 rows written — source tables may be empty"
        )
        return ComputeMarkersResponse(
            status="empty",
            total_rows_written=0,
            breakdown=breakdown,
            null_counts=null_counts,
            warning=(
                "No rows written. Source tables (stock_ohlcv, gold_price, gold_etf_ohlcv) "
                "may not have data yet. Run ingestion endpoints first."
            ),
        )

    logger.info(
        "compute_structure_markers: wrote %d rows — breakdown: %s",
        total, breakdown,
    )
    return ComputeMarkersResponse(
        status="success",
        total_rows_written=total,
        breakdown=breakdown,
        null_counts=null_counts,
    )
