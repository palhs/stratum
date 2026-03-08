"""
vnstock data fetching and transformation service.
Phase 2 | Plan 01

Fetches Vietnamese stock market data from the vnstock VCI source and upserts
it into the Stratum PostgreSQL database.

CRITICAL anti-patterns avoided here:
  - NOT using `vnstock3` package name (renamed to `vnstock` in Jan 2025)
  - NOT using TCBS source for financial ratios (broken as of 2025 — VCI only)
  - NOT hard-coding VN30 symbols — fetched live via Listing.symbols_by_group()
  - NOT creating separate tables per resolution — single stock_ohlcv table

Authentication:
  - If VNSTOCK_API_KEY env var is set, calls vnstock.set_token() for Community tier (60 req/min)
  - If unset, logs a warning and proceeds with guest tier (20 req/min)
"""

import logging
import os
import time
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from vnstock import Listing, Vnstock

from app.models import stock_fundamentals, stock_ohlcv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level authentication
# ---------------------------------------------------------------------------

_VNSTOCK_API_KEY = os.environ.get("VNSTOCK_API_KEY", "")

if _VNSTOCK_API_KEY:
    try:
        # Community tier: 60 req/min (vs 20 req/min guest)
        import vnstock as _vnstock_module
        if hasattr(_vnstock_module, "change_api_key"):
            # vnstock >=3.4.0 renamed set_token → change_api_key
            _vnstock_module.change_api_key(_VNSTOCK_API_KEY)
            logger.info("vnstock: authenticated with Community tier API key")
        elif hasattr(_vnstock_module, "set_token"):
            _vnstock_module.set_token(_VNSTOCK_API_KEY)
            logger.info("vnstock: authenticated with Community tier API key")
        else:
            logger.warning(
                "vnstock: no authentication method available in this version — "
                "proceeding with guest tier (20 req/min)"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("vnstock: failed to set API token: %s — proceeding as guest", exc)
else:
    logger.warning(
        "VNSTOCK_API_KEY not set — proceeding with guest tier (20 req/min). "
        "Set VNSTOCK_API_KEY for Community tier (60 req/min)."
    )


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class VnstockAPIError(Exception):
    """Raised when vnstock API calls fail (upstream error)."""


# ---------------------------------------------------------------------------
# VN30 symbol list
# ---------------------------------------------------------------------------

def get_vn30_symbols() -> list[str]:
    """
    Return the current VN30 constituent symbols from VCI listing.

    NEVER hard-coded — always fetched live from vnstock.
    """
    try:
        symbols_df = Listing(source="vci").symbols_by_group(group="VN30")
        if isinstance(symbols_df, pd.DataFrame):
            # The column name varies by vnstock version; try common names
            for col in ("symbol", "ticker", "code"):
                if col in symbols_df.columns:
                    return symbols_df[col].tolist()
            # Fall back to first column
            return symbols_df.iloc[:, 0].tolist()
        # Some versions return a list directly
        return list(symbols_df)
    except Exception as exc:
        raise VnstockAPIError(f"Failed to fetch VN30 symbols: {exc}") from exc


# ---------------------------------------------------------------------------
# OHLCV ingestion
# ---------------------------------------------------------------------------

# vnstock column name → stock_ohlcv column name
_OHLCV_COLUMN_MAP = {
    "time": "data_as_of",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}


def fetch_and_upsert_ohlcv(
    symbols: Optional[list[str]],
    start_date: str,
    end_date: str,
    resolution: str,
    db_session: Session,
) -> dict:
    """
    Fetch weekly/monthly OHLCV bars for the given symbols and upsert to stock_ohlcv.

    Args:
        symbols:    List of ticker symbols. If None, fetches all VN30 constituents.
        start_date: ISO date string (YYYY-MM-DD). Use 5-year-ago date for backfill.
        end_date:   ISO date string (YYYY-MM-DD).
        resolution: "weekly" or "monthly".
        db_session: SQLAlchemy session.

    Returns:
        dict with keys: rows_ingested (int), data_as_of (str | None), anomaly_detected (bool)
    """
    if symbols is None:
        symbols = get_vn30_symbols()

    # vnstock interval codes
    interval_map = {"weekly": "1W", "monthly": "1M"}
    interval = interval_map.get(resolution, "1W")

    all_rows: list[dict] = []
    failed_symbols: list[str] = []

    for sym in symbols:
        try:
            df = (
                Vnstock()
                .stock(symbol=sym, source="VCI")
                .quote.history(start=start_date, end=end_date, interval=interval)
            )
        except Exception as exc:
            logger.warning("OHLCV fetch failed for %s: %s", sym, exc)
            failed_symbols.append(sym)
            continue

        if df is None or df.empty:
            logger.debug("No OHLCV data returned for %s in [%s, %s]", sym, start_date, end_date)
            continue

        # Rename columns to match DB schema
        df = df.rename(columns={k: v for k, v in _OHLCV_COLUMN_MAP.items() if k in df.columns})

        # Ensure we have all required columns; skip rows with missing close
        if "data_as_of" not in df.columns:
            logger.warning("OHLCV data for %s has no time/data_as_of column — skipping", sym)
            continue

        df = df[df["close"].notna()].copy()

        # Add metadata columns
        df["symbol"] = sym
        df["resolution"] = resolution
        df["ingested_at"] = pd.Timestamp.now(tz="UTC")

        # Ensure data_as_of is timezone-aware UTC
        if not pd.api.types.is_datetime64_any_dtype(df["data_as_of"]):
            df["data_as_of"] = pd.to_datetime(df["data_as_of"])
        if df["data_as_of"].dt.tz is None:
            df["data_as_of"] = df["data_as_of"].dt.tz_localize("UTC")

        # Select only DB columns
        db_cols = ["symbol", "resolution", "open", "high", "low", "close", "volume",
                   "data_as_of", "ingested_at"]
        df = df[[c for c in db_cols if c in df.columns]]

        all_rows.extend(df.to_dict(orient="records"))

    if not all_rows:
        return {"rows_ingested": 0, "data_as_of": None, "anomaly_detected": False}

    # Upsert — ON CONFLICT (symbol, resolution, data_as_of) DO UPDATE
    stmt = pg_insert(stock_ohlcv).values(all_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "resolution", "data_as_of"],
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

    # Most recent data_as_of for the response
    latest_data_as_of = max(
        (r["data_as_of"] for r in all_rows if r.get("data_as_of") is not None),
        default=None,
    )
    data_as_of_str = latest_data_as_of.isoformat() if latest_data_as_of else None

    anomaly = bool(failed_symbols)
    if anomaly:
        logger.warning("OHLCV ingest: %d symbols failed: %s", len(failed_symbols), failed_symbols)

    return {
        "rows_ingested": len(all_rows),
        "data_as_of": data_as_of_str,
        "anomaly_detected": anomaly,
    }


# ---------------------------------------------------------------------------
# Fundamentals ingestion
# ---------------------------------------------------------------------------

# vnstock financial ratio column name → stock_fundamentals column name
# vnstock VCI returns MultiIndex columns; the second level (display name) is mapped here.
# The first level is the Vietnamese category name (ignored — we use the second level).
_FUNDAMENTALS_COLUMN_MAP = {
    # VCI MultiIndex second-level column names (lang="en")
    "P/E": "pe_ratio",
    "P/B": "pb_ratio",
    "EPS (VND)": "eps",
    "Market Capital (Bn. VND)": "market_cap",
    "ROE (%)": "roe",
    "ROA (%)": "roa",
    "Net Profit Margin (%)": "net_margin",
    # Alternative English column names seen in some vnstock versions
    "priceToEarning": "pe_ratio",
    "priceToBook": "pb_ratio",
    "earningPerShare": "eps",
    "marketCap": "market_cap",
    "roe": "roe",
    "roa": "roa",
    "revenueGrowth": "revenue_growth",
    "netProfitMargin": "net_margin",
    "pe": "pe_ratio",
    "pb": "pb_ratio",
    "eps": "eps",
    "market_cap": "market_cap",
    "ROE": "roe",
    "ROA": "roa",
    "revenue_growth": "revenue_growth",
    "net_margin": "net_margin",
}


def fetch_and_upsert_fundamentals(
    symbols: Optional[list[str]],
    db_session: Session,
) -> dict:
    """
    Fetch annual fundamental ratios for the given symbols and upsert to stock_fundamentals.

    Args:
        symbols:    List of ticker symbols. If None, fetches all VN30 constituents.
        db_session: SQLAlchemy session.

    Returns:
        dict with keys: rows_ingested (int), data_as_of (str | None), anomaly_detected (bool)
    """
    if symbols is None:
        symbols = get_vn30_symbols()

    all_rows: list[dict] = []
    failed_symbols: list[str] = []

    for sym in symbols:
        try:
            df = (
                Vnstock()
                .stock(symbol=sym, source="VCI")
                .finance.ratio(period="year", lang="en", dropna=True)
            )
        except SystemExit as exc:
            # vnstock rate limit handler calls sys.exit() — catch it to avoid crashing
            # the container. Treat as a rate limit error and skip remaining symbols.
            logger.warning(
                "Fundamentals fetch for %s: vnstock rate limit exit (SystemExit) — "
                "stopping symbol loop to avoid container crash: %s",
                sym, exc,
            )
            failed_symbols.append(sym)
            break  # Cannot continue — rate limited for this minute
        except Exception as exc:
            logger.warning("Fundamentals fetch failed for %s: %s", sym, exc)
            failed_symbols.append(sym)
            continue

        # Small delay between symbols to avoid rate limit (60 req/min community tier)
        # 1.5s delay = ~40 symbols/min max, well within 60/min limit
        time.sleep(1.5)

        if df is None or df.empty:
            logger.debug("No fundamentals data returned for %s", sym)
            continue

        # Flatten MultiIndex columns if present (vnstock VCI returns them)
        # Strategy: use the second level (display name) as the column key for mapping.
        # This correctly maps "P/E", "ROE (%)", etc. from the VCI MultiIndex.
        # The period column ("yearReport") lives in the "Meta" first-level group,
        # so we check both the raw second-level name and fallback full-join.
        if isinstance(df.columns, pd.MultiIndex):
            # Preserve second-level names for column mapping; fall back to full join
            # for columns without a meaningful second level
            new_cols = []
            for col in df.columns:
                second_level = str(col[-1]).strip()
                if second_level:
                    new_cols.append(second_level)
                else:
                    new_cols.append("_".join(str(c) for c in col).strip("_"))
            df.columns = new_cols

        # Identify the date/period column
        period_col = None
        for candidate in ("yearReport", "year", "period", "reportDate", "date", "ticker"):
            if candidate in df.columns:
                period_col = candidate
                break
        if period_col is None and not df.empty:
            # Use index as period if it looks like dates
            if hasattr(df.index, "dtype") and pd.api.types.is_datetime64_any_dtype(df.index):
                df = df.reset_index()
                period_col = df.columns[0]

        # Build rows
        for _, row in df.iterrows():
            record: dict = {
                "symbol": sym,
                "period_type": "year",
                "ingested_at": pd.Timestamp.now(tz="UTC"),
            }

            # Map financial columns
            for src_col, dst_col in _FUNDAMENTALS_COLUMN_MAP.items():
                if src_col in row.index and pd.notna(row[src_col]):
                    record[dst_col] = row[src_col]

            # Resolve data_as_of from the period column
            if period_col and period_col in row.index and pd.notna(row[period_col]):
                raw_period = row[period_col]
                try:
                    if isinstance(raw_period, (int, float)):
                        # Year integer like 2023 → end of that year
                        ts = pd.Timestamp(year=int(raw_period), month=12, day=31, tz="UTC")
                    else:
                        ts = pd.Timestamp(str(raw_period))
                        if ts.tzinfo is None:
                            ts = ts.tz_localize("UTC")
                    record["data_as_of"] = ts
                except Exception:  # noqa: BLE001
                    logger.debug("Could not parse period value '%s' for %s", raw_period, sym)
                    continue
            else:
                # Skip rows where we cannot determine data_as_of (DATA-07 requires non-NULL)
                logger.debug("No period column found for %s row — skipping", sym)
                continue

            all_rows.append(record)

    if not all_rows:
        return {"rows_ingested": 0, "data_as_of": None, "anomaly_detected": False}

    # Upsert — ON CONFLICT (symbol, period_type, data_as_of) DO UPDATE
    stmt = pg_insert(stock_fundamentals).values(all_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "period_type", "data_as_of"],
        set_={
            "pe_ratio": stmt.excluded.pe_ratio,
            "pb_ratio": stmt.excluded.pb_ratio,
            "eps": stmt.excluded.eps,
            "market_cap": stmt.excluded.market_cap,
            "roe": stmt.excluded.roe,
            "roa": stmt.excluded.roa,
            "revenue_growth": stmt.excluded.revenue_growth,
            "net_margin": stmt.excluded.net_margin,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db_session.execute(stmt)
    db_session.commit()

    latest_data_as_of = max(
        (r["data_as_of"] for r in all_rows if r.get("data_as_of") is not None),
        default=None,
    )
    data_as_of_str = latest_data_as_of.isoformat() if latest_data_as_of else None

    anomaly = bool(failed_symbols)
    if anomaly:
        logger.warning(
            "Fundamentals ingest: %d symbols failed: %s", len(failed_symbols), failed_symbols
        )

    return {
        "rows_ingested": len(all_rows),
        "data_as_of": data_as_of_str,
        "anomaly_detected": anomaly,
    }
