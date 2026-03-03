"""
Gold data fetching and ingestion service.
Phase 2 | Plan 02

Fetches gold spot price (FRED GOLDAMGBD228NLBM), GLD ETF OHLCV (yfinance),
and World Gold Council ETF flows (stub — JS-rendered, returns 501).

CRITICAL data_as_of semantics:
  - FRED gold price: The FRED `date` field IS the observation date (market session
    date when the London PM fix was set). This is ALWAYS different from ingested_at.
  - GLD ETF: The yfinance bar date is the week-start of that candle. Normalized to
    midnight UTC and stored as data_as_of.
  - WGC flows: Currently a stub (see module-level note below).

WGC note:
  The World Gold Council Goldhub portal (gold.org/goldhub/data/...) is JavaScript-
  rendered and does not expose a stable direct-download URL. Playwright automation
  is not included in this build to avoid bloating the sidecar container with Chromium.
  The /ingest/gold/wgc-flows endpoint returns HTTP 501 with a documented limitation
  message. WGC data can be manually imported via CSV upload when needed.
  This is a known limitation tracked in deferred-items.md.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf
from fredapi import Fred
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import gold_etf_ohlcv, gold_price

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FRED gold spot price ingestion — GOLDAMGBD228NLBM
# ---------------------------------------------------------------------------

def fetch_and_upsert_gold_fred_price(
    start_date: str,
    end_date: str,
    db_session: Session,
) -> dict:
    """
    Fetch LBMA gold PM fix from FRED series GOLDAMGBD228NLBM and upsert to gold_price.

    CRITICAL: The FRED observation date (e.g. "2024-01-15") is the day the London
    Bullion Market Association fixed the price. This is stored as data_as_of.
    ingested_at is set to NOW() — these are ALWAYS different values.

    Args:
        start_date: ISO date string (YYYY-MM-DD). Use 10-years-ago for backfill.
        end_date:   ISO date string (YYYY-MM-DD).
        db_session: SQLAlchemy session.

    Returns:
        dict with keys: rows_ingested (int), data_as_of (str | None)
    """
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        raise EnvironmentError("FRED_API_KEY environment variable is not set")

    fred = Fred(api_key=api_key)
    series = fred.get_series(
        "GOLDAMGBD228NLBM",
        observation_start=start_date,
        observation_end=end_date,
    )

    if series is None or series.empty:
        logger.info("FRED GOLDAMGBD228NLBM: no data returned for [%s, %s]", start_date, end_date)
        return {"rows_ingested": 0, "data_as_of": None}

    # Drop NaN — FRED returns NaN for non-trading days (weekends, holidays)
    series = series.dropna()

    if series.empty:
        logger.info("FRED GOLDAMGBD228NLBM: all values NaN after dropna for [%s, %s]", start_date, end_date)
        return {"rows_ingested": 0, "data_as_of": None}

    ingested_at = datetime.now(tz=timezone.utc)
    rows: list[dict] = []
    for obs_date, price_val in series.items():
        # obs_date is a pandas Timestamp — the observation date from FRED
        # This IS the data_as_of (not the ingestion time)
        if pd.isnull(obs_date) or pd.isnull(price_val):
            continue
        ts = pd.Timestamp(obs_date)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        rows.append({
            "source": "FRED_GOLDAMGBD228NLBM",
            "price_usd": float(price_val),
            "data_as_of": ts.to_pydatetime(),
            "ingested_at": ingested_at,
        })

    if not rows:
        return {"rows_ingested": 0, "data_as_of": None}

    logger.debug(
        "FRED GOLDAMGBD228NLBM: data_as_of range %s to %s (%d rows)",
        min(r["data_as_of"] for r in rows),
        max(r["data_as_of"] for r in rows),
        len(rows),
    )

    stmt = pg_insert(gold_price).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "data_as_of"],
        set_={
            "price_usd": stmt.excluded.price_usd,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db_session.execute(stmt)
    db_session.commit()

    latest_data_as_of = max(r["data_as_of"] for r in rows)
    return {
        "rows_ingested": len(rows),
        "data_as_of": latest_data_as_of.isoformat(),
    }


# ---------------------------------------------------------------------------
# GLD ETF weekly OHLCV ingestion via yfinance
# ---------------------------------------------------------------------------

def fetch_and_upsert_gld_etf(
    start_date: str,
    end_date: str,
    resolution: str,
    db_session: Session,
) -> dict:
    """
    Fetch GLD ETF weekly OHLCV from yfinance and upsert to gold_etf_ohlcv.

    Args:
        start_date: ISO date string (YYYY-MM-DD). Use 10-years-ago for backfill.
        end_date:   ISO date string (YYYY-MM-DD).
        resolution: "weekly" (maps to yfinance "1wk") or "monthly" (maps to "1mo").
        db_session: SQLAlchemy session.

    Returns:
        dict with keys: rows_ingested (int), data_as_of (str | None)
    """
    interval_map = {"weekly": "1wk", "monthly": "1mo", "daily": "1d"}
    interval = interval_map.get(resolution, "1wk")

    ticker_obj = yf.Ticker("GLD")
    df = ticker_obj.history(
        start=start_date,
        end=end_date,
        interval=interval,
        auto_adjust=True,
    )

    if df is None or df.empty:
        logger.info("yfinance GLD: no data returned for [%s, %s] interval=%s", start_date, end_date, interval)
        return {"rows_ingested": 0, "data_as_of": None}

    # yfinance returns lowercase column names after auto_adjust
    df.columns = [c.lower() for c in df.columns]

    # The index is the bar date — normalize to midnight UTC
    df = df.reset_index()
    date_col = df.columns[0]  # "Date" or "Datetime"
    df = df.rename(columns={date_col: "data_as_of"})

    # Normalize data_as_of to midnight UTC
    df["data_as_of"] = pd.to_datetime(df["data_as_of"])
    if df["data_as_of"].dt.tz is not None:
        df["data_as_of"] = df["data_as_of"].dt.tz_convert("UTC").dt.normalize()
    else:
        df["data_as_of"] = df["data_as_of"].dt.normalize().dt.tz_localize("UTC")

    # Remove rows without a close price
    df = df[df["close"].notna()].copy()

    if df.empty:
        return {"rows_ingested": 0, "data_as_of": None}

    ingested_at = datetime.now(tz=timezone.utc)
    df["ticker"] = "GLD"
    df["resolution"] = resolution
    df["ingested_at"] = ingested_at

    # Select DB columns
    db_cols = ["ticker", "resolution", "open", "high", "low", "close", "volume",
               "data_as_of", "ingested_at"]
    df = df[[c for c in db_cols if c in df.columns]]

    # Cast volume to int where possible (yfinance sometimes returns float)
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0).astype("int64")

    rows = df.to_dict(orient="records")

    logger.debug(
        "yfinance GLD: data_as_of range %s to %s (%d rows)",
        min(r["data_as_of"] for r in rows),
        max(r["data_as_of"] for r in rows),
        len(rows),
    )

    stmt = pg_insert(gold_etf_ohlcv).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "resolution", "data_as_of"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db_session.execute(stmt)
    db_session.commit()

    latest_data_as_of = max(r["data_as_of"] for r in rows)
    ts = latest_data_as_of
    if hasattr(ts, "isoformat"):
        data_as_of_str = ts.isoformat()
    else:
        data_as_of_str = str(ts)

    return {
        "rows_ingested": len(rows),
        "data_as_of": data_as_of_str,
    }


# ---------------------------------------------------------------------------
# WGC ETF flows — stub (JS-rendered portal, no stable download URL)
# ---------------------------------------------------------------------------

class WGCNotImplemented(NotImplementedError):
    """
    Raised when WGC scraping is requested.

    The World Gold Council Goldhub portal is JavaScript-rendered and does not
    expose a stable direct-download endpoint. WGC data should be manually
    imported via CSV upload. This is a known limitation.
    """


def fetch_and_upsert_wgc_flows(db_session: Session) -> dict:  # noqa: ARG001
    """
    Stub: World Gold Council ETF flow ingestion is not implemented.

    The WGC Goldhub portal (gold.org/goldhub/data/gold-etf-holdings-and-flows)
    is JavaScript-rendered and does not provide a stable direct-download URL.
    Playwright automation was evaluated but excluded to avoid bloating the sidecar
    container with a Chromium dependency.

    Known limitation: WGC data must be manually imported via CSV upload.
    Tracked in deferred-items.md.
    """
    raise WGCNotImplemented(
        "WGC Goldhub scraping is not implemented: the portal is JavaScript-rendered "
        "and does not expose a stable download URL. "
        "Import WGC data manually via CSV upload."
    )
