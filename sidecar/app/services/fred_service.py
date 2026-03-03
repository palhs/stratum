"""
FRED macroeconomic indicator fetching and ingestion service.
Phase 2 | Plan 02

Fetches GDP, CPI, unemployment rate, and federal funds rate from the FRED API
and upserts to fred_indicators.

CRITICAL data_as_of semantics:
  The FRED observation date is the PERIOD the data covers — NOT the API call date.

  Examples:
    GDP    date="2024-10-01" → Q4 2024 (quarter starting Oct 1)
    UNRATE date="2024-12-01" → December 2024
    CPI    date="2024-12-01" → December 2024

  data_as_of must store these observation period dates. ingested_at = NOW().
  The warning sign of this bug: all fred_indicators rows have data_as_of
  clustered around Sunday night (the scheduled run time) instead of spread
  across years. A DEBUG log line after each fetch shows the actual date range
  to make this verifiable.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fredapi import Fred
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import fred_indicators

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FRED series configuration
# ---------------------------------------------------------------------------

FRED_SERIES: dict[str, dict[str, str]] = {
    "GDP": {"frequency": "quarterly", "description": "US GDP"},
    "CPIAUCSL": {"frequency": "monthly", "description": "US CPI (Consumer Price Index)"},
    "UNRATE": {"frequency": "monthly", "description": "US Unemployment Rate"},
    "FEDFUNDS": {"frequency": "monthly", "description": "Federal Funds Effective Rate"},
}


# ---------------------------------------------------------------------------
# FRED macroeconomic indicator ingestion
# ---------------------------------------------------------------------------

def fetch_and_upsert_fred_indicators(
    start_date: str,
    end_date: str,
    series_ids: Optional[list[str]],
    db_session: Session,
) -> dict:
    """
    Fetch FRED macroeconomic indicators and upsert to fred_indicators.

    CRITICAL: The FRED observation date = the period the data covers.
    For GDP date="2024-10-01" = Q4 2024. For UNRATE date="2024-12-01" = Dec 2024.
    This is stored as data_as_of (NOT the API call timestamp).

    Args:
        start_date: ISO date string (YYYY-MM-DD). Use 10+ years ago for backfill.
        end_date:   ISO date string (YYYY-MM-DD).
        series_ids: Optional list of FRED series IDs to fetch. If None, fetches
                    all series in FRED_SERIES (GDP, CPIAUCSL, UNRATE, FEDFUNDS).
        db_session: SQLAlchemy session.

    Returns:
        dict with keys: rows_ingested (int), data_as_of (str | None)
    """
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        raise EnvironmentError("FRED_API_KEY environment variable is not set")

    fred = Fred(api_key=api_key)

    # Default to all configured series
    if series_ids is None:
        series_ids = list(FRED_SERIES.keys())

    ingested_at = datetime.now(tz=timezone.utc)
    all_rows: list[dict] = []

    for series_id in series_ids:
        series_config = FRED_SERIES.get(series_id, {"frequency": "unknown", "description": series_id})
        frequency = series_config["frequency"]

        try:
            series = fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date,
            )
        except Exception as exc:
            logger.warning("FRED series %s fetch failed: %s", series_id, exc)
            continue

        if series is None or series.empty:
            logger.info("FRED %s: no data returned for [%s, %s]", series_id, start_date, end_date)
            continue

        # Drop NaN — FRED uses "." (represented as NaN by fredapi) for missing observations
        series = series.dropna()

        if series.empty:
            logger.info("FRED %s: all values NaN after dropna for [%s, %s]", series_id, start_date, end_date)
            continue

        rows: list[dict] = []
        for obs_date, value in series.items():
            if pd.isnull(obs_date) or pd.isnull(value):
                continue
            ts = pd.Timestamp(obs_date)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            rows.append({
                "series_id": series_id,
                "value": float(value),
                "frequency": frequency,
                "data_as_of": ts.to_pydatetime(),
                "ingested_at": ingested_at,
            })

        if not rows:
            continue

        # DEBUG log showing data_as_of range — makes it verifiable that observation
        # dates are spread across years, NOT clustered around ingestion time
        logger.debug(
            "FRED %s: data_as_of range %s to %s (%d rows)",
            series_id,
            min(r["data_as_of"] for r in rows),
            max(r["data_as_of"] for r in rows),
            len(rows),
        )

        all_rows.extend(rows)

    if not all_rows:
        return {"rows_ingested": 0, "data_as_of": None}

    # Upsert — ON CONFLICT (series_id, data_as_of) DO UPDATE
    stmt = pg_insert(fred_indicators).values(all_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["series_id", "data_as_of"],
        set_={
            "value": stmt.excluded.value,
            "frequency": stmt.excluded.frequency,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db_session.execute(stmt)
    db_session.commit()

    latest_data_as_of = max(r["data_as_of"] for r in all_rows)
    return {
        "rows_ingested": len(all_rows),
        "data_as_of": latest_data_as_of.isoformat(),
    }
