"""
reasoning/app/retrieval/postgres_retriever.py — PostgreSQL direct query retrievers.
Phase 5 | Plan 02 | Requirement: RETR-03

Direct query functions for all 5 Phase 2 PostgreSQL tables:
  - stock_fundamentals  → get_fundamentals()
  - structure_markers   → get_structure_markers()
  - fred_indicators     → get_fred_indicators()
  - gold_price          → get_gold_price()
  - gold_etf_ohlcv      → get_gold_etf()

Design decisions (locked):
- Sync SQLAlchemy Core with psycopg2-binary (NOT async psycopg3 — Pitfall 4)
- Module-level engine + connection factory (same pattern as sidecar/app/db.py)
- Each function accepts optional `engine` parameter for test injection
- pool_size=3 (read-only retrieval, lighter than sidecar's 5)
- All functions call check_freshness() and populate warnings field on returned rows
- All functions accept now_override for deterministic testing
- NoDataError raised when no rows returned for the requested symbol/series
- INFO logging per call: function name, params, row count, elapsed_ms, warning count
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine

from reasoning.app.models.tables import (
    fred_indicators,
    gold_etf_ohlcv,
    gold_price,
    stock_fundamentals,
    structure_markers,
)
from reasoning.app.retrieval.freshness import FRESHNESS_THRESHOLDS, check_freshness
from reasoning.app.retrieval.types import (
    FredIndicatorRow,
    FundamentalsRow,
    GoldEtfRow,
    GoldPriceRow,
    NoDataError,
    StructureMarkerRow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level engine (lazy init — created on first use if not injected)
# ---------------------------------------------------------------------------

_default_engine: Optional[Engine] = None


def _get_engine() -> Engine:
    """
    Return the module-level default engine, creating it on first call.

    Reads DATABASE_URL from environment.
    Default: postgresql://stratum:changeme@postgres:5432/stratum
    """
    global _default_engine
    if _default_engine is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://stratum:changeme@postgres:5432/stratum",
        )
        _default_engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=3,
        )
    return _default_engine


# ---------------------------------------------------------------------------
# get_fundamentals()
# ---------------------------------------------------------------------------


def get_fundamentals(
    symbol: str,
    lookback_quarters: int = 1,
    now_override: Optional[datetime] = None,
    engine: Optional[Engine] = None,
) -> List[FundamentalsRow]:
    """
    Retrieve stock fundamentals rows for a given symbol.

    Args:
        symbol:            Ticker symbol (e.g. "VNM").
        lookback_quarters: Number of most recent quarters to return. Default 1.
        now_override:      Override current time for freshness check (testing).
        engine:            Optional SQLAlchemy engine for test injection.

    Returns:
        List[FundamentalsRow]: Fundamentals rows ordered by data_as_of DESC.
        Each row includes a warnings field (empty = fresh, non-empty = stale).

    Raises:
        NoDataError: If no rows found for the given symbol.
    """
    t0 = time.monotonic()
    eng = engine or _get_engine()

    stmt = (
        select(stock_fundamentals)
        .where(stock_fundamentals.c.symbol == symbol)
        .order_by(stock_fundamentals.c.data_as_of.desc())
        .limit(lookback_quarters)
    )

    with eng.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    threshold = FRESHNESS_THRESHOLDS["stock_fundamentals"]

    if not rows:
        logger.info(
            "get_fundamentals | symbol=%s | rows=0 | elapsed_ms=%d",
            symbol, elapsed_ms,
        )
        raise NoDataError(f"No fundamentals data found for symbol: {symbol}")

    results = []
    warning_count = 0
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold, "stock_fundamentals", now_override
        )
        warning_count += len(warnings)
        results.append(
            FundamentalsRow(
                symbol=row.symbol,
                period_type=row.period_type,
                pe_ratio=float(row.pe_ratio) if row.pe_ratio is not None else None,
                pb_ratio=float(row.pb_ratio) if row.pb_ratio is not None else None,
                eps=float(row.eps) if row.eps is not None else None,
                market_cap=float(row.market_cap) if row.market_cap is not None else None,
                roe=float(row.roe) if row.roe is not None else None,
                roa=float(row.roa) if row.roa is not None else None,
                revenue_growth=float(row.revenue_growth) if row.revenue_growth is not None else None,
                net_margin=float(row.net_margin) if row.net_margin is not None else None,
                data_as_of=row.data_as_of,
                warnings=warnings,
            )
        )

    logger.info(
        "get_fundamentals | symbol=%s | rows=%d | warnings=%d | elapsed_ms=%d",
        symbol, len(results), warning_count, elapsed_ms,
    )
    return results


# ---------------------------------------------------------------------------
# get_structure_markers()
# ---------------------------------------------------------------------------


def get_structure_markers(
    symbol: str,
    now_override: Optional[datetime] = None,
    engine: Optional[Engine] = None,
) -> List[StructureMarkerRow]:
    """
    Retrieve the most recent price structure markers for a given symbol.

    Args:
        symbol:       Ticker symbol (e.g. "VNM").
        now_override: Override current time for freshness check (testing).
        engine:       Optional SQLAlchemy engine for test injection.

    Returns:
        List[StructureMarkerRow]: Most recent structure marker rows.
        Each row includes a warnings field (empty = fresh, non-empty = stale).

    Raises:
        NoDataError: If no rows found for the given symbol.
    """
    t0 = time.monotonic()
    eng = engine or _get_engine()

    stmt = (
        select(structure_markers)
        .where(structure_markers.c.symbol == symbol)
        .order_by(structure_markers.c.data_as_of.desc())
        .limit(1)
    )

    with eng.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    threshold = FRESHNESS_THRESHOLDS["structure_markers"]

    if not rows:
        logger.info(
            "get_structure_markers | symbol=%s | rows=0 | elapsed_ms=%d",
            symbol, elapsed_ms,
        )
        raise NoDataError(f"No structure markers found for symbol: {symbol}")

    results = []
    warning_count = 0
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold, "structure_markers", now_override
        )
        warning_count += len(warnings)
        results.append(
            StructureMarkerRow(
                symbol=row.symbol,
                asset_type=row.asset_type,
                resolution=row.resolution,
                close=float(row.close) if row.close is not None else None,
                ma_10w=float(row.ma_10w) if row.ma_10w is not None else None,
                ma_20w=float(row.ma_20w) if row.ma_20w is not None else None,
                ma_50w=float(row.ma_50w) if row.ma_50w is not None else None,
                drawdown_from_ath=float(row.drawdown_from_ath) if row.drawdown_from_ath is not None else None,
                drawdown_from_52w_high=float(row.drawdown_from_52w_high) if row.drawdown_from_52w_high is not None else None,
                close_pct_rank=float(row.close_pct_rank) if row.close_pct_rank is not None else None,
                pe_pct_rank=float(row.pe_pct_rank) if row.pe_pct_rank is not None else None,
                data_as_of=row.data_as_of,
                warnings=warnings,
            )
        )

    logger.info(
        "get_structure_markers | symbol=%s | rows=%d | warnings=%d | elapsed_ms=%d",
        symbol, len(results), warning_count, elapsed_ms,
    )
    return results


# ---------------------------------------------------------------------------
# get_fred_indicators()
# ---------------------------------------------------------------------------


def get_fred_indicators(
    series_ids: List[str],
    lookback_days: int = 90,
    now_override: Optional[datetime] = None,
    engine: Optional[Engine] = None,
) -> List[FredIndicatorRow]:
    """
    Retrieve FRED macroeconomic indicator rows for the given series IDs.

    Args:
        series_ids:   List of FRED series IDs (e.g. ["FEDFUNDS", "UNRATE"]).
        lookback_days: Include only rows where data_as_of >= (now - lookback_days).
        now_override: Override current time for freshness check and lookback calc.
        engine:       Optional SQLAlchemy engine for test injection.

    Returns:
        List[FredIndicatorRow]: Indicator rows ordered by data_as_of DESC.
        Each row includes a warnings field (empty = fresh, non-empty = stale).

    Raises:
        NoDataError: If no rows found for any of the requested series IDs.
    """
    t0 = time.monotonic()
    eng = engine or _get_engine()

    # Compute lookback cutoff
    now = now_override if now_override is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    stmt = (
        select(fred_indicators)
        .where(fred_indicators.c.series_id.in_(series_ids))
        .where(fred_indicators.c.data_as_of >= cutoff)
        .order_by(fred_indicators.c.data_as_of.desc())
    )

    with eng.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    threshold = FRESHNESS_THRESHOLDS["fred_indicators"]

    if not rows:
        logger.info(
            "get_fred_indicators | series=%s | rows=0 | elapsed_ms=%d",
            series_ids, elapsed_ms,
        )
        raise NoDataError(
            f"No FRED indicator data found for series: {series_ids} "
            f"within last {lookback_days} days"
        )

    results = []
    warning_count = 0
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold, "fred_indicators", now_override
        )
        warning_count += len(warnings)
        results.append(
            FredIndicatorRow(
                series_id=row.series_id,
                value=float(row.value),
                frequency=row.frequency,
                data_as_of=row.data_as_of,
                warnings=warnings,
            )
        )

    logger.info(
        "get_fred_indicators | series=%s | rows=%d | warnings=%d | elapsed_ms=%d",
        series_ids, len(results), warning_count, elapsed_ms,
    )
    return results


# ---------------------------------------------------------------------------
# get_gold_price()
# ---------------------------------------------------------------------------


def get_gold_price(
    lookback_days: int = 7,
    now_override: Optional[datetime] = None,
    engine: Optional[Engine] = None,
) -> List[GoldPriceRow]:
    """
    Retrieve the most recent gold price rows.

    Args:
        lookback_days: Number of most recent days' rows to return.
        now_override:  Override current time for freshness check (testing).
        engine:        Optional SQLAlchemy engine for test injection.

    Returns:
        List[GoldPriceRow]: Gold price rows ordered by data_as_of DESC.
        Each row includes a warnings field (empty = fresh, non-empty = stale).

    Raises:
        NoDataError: If no rows found in the gold_price table.
    """
    t0 = time.monotonic()
    eng = engine or _get_engine()

    stmt = (
        select(gold_price)
        .order_by(gold_price.c.data_as_of.desc())
        .limit(lookback_days)
    )

    with eng.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    threshold = FRESHNESS_THRESHOLDS["gold_price"]

    if not rows:
        logger.info(
            "get_gold_price | rows=0 | elapsed_ms=%d", elapsed_ms,
        )
        raise NoDataError("No gold price data found in gold_price table")

    results = []
    warning_count = 0
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold, "gold_price", now_override
        )
        warning_count += len(warnings)
        results.append(
            GoldPriceRow(
                source=row.source,
                price_usd=float(row.price_usd),
                data_as_of=row.data_as_of,
                warnings=warnings,
            )
        )

    logger.info(
        "get_gold_price | rows=%d | warnings=%d | elapsed_ms=%d",
        len(results), warning_count, elapsed_ms,
    )
    return results


# ---------------------------------------------------------------------------
# get_gold_etf()
# ---------------------------------------------------------------------------


def get_gold_etf(
    ticker: str = "GLD",
    lookback_days: int = 7,
    now_override: Optional[datetime] = None,
    engine: Optional[Engine] = None,
) -> List[GoldEtfRow]:
    """
    Retrieve gold ETF OHLCV rows for a given ticker.

    Args:
        ticker:        ETF ticker symbol (e.g. "GLD"). Default "GLD".
        lookback_days: Number of most recent rows to return.
        now_override:  Override current time for freshness check (testing).
        engine:        Optional SQLAlchemy engine for test injection.

    Returns:
        List[GoldEtfRow]: Gold ETF rows ordered by data_as_of DESC.
        Each row includes a warnings field (empty = fresh, non-empty = stale).

    Raises:
        NoDataError: If no rows found for the given ticker.
    """
    t0 = time.monotonic()
    eng = engine or _get_engine()

    stmt = (
        select(gold_etf_ohlcv)
        .where(gold_etf_ohlcv.c.ticker == ticker)
        .order_by(gold_etf_ohlcv.c.data_as_of.desc())
        .limit(lookback_days)
    )

    with eng.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    threshold = FRESHNESS_THRESHOLDS["gold_etf_ohlcv"]

    if not rows:
        logger.info(
            "get_gold_etf | ticker=%s | rows=0 | elapsed_ms=%d",
            ticker, elapsed_ms,
        )
        raise NoDataError(f"No gold ETF data found for ticker: {ticker}")

    results = []
    warning_count = 0
    for row in rows:
        warnings = check_freshness(
            row.data_as_of, threshold, "gold_etf_ohlcv", now_override
        )
        warning_count += len(warnings)
        results.append(
            GoldEtfRow(
                ticker=row.ticker,
                resolution=row.resolution,
                open=float(row.open) if row.open is not None else None,
                high=float(row.high) if row.high is not None else None,
                low=float(row.low) if row.low is not None else None,
                close=float(row.close),
                volume=int(row.volume) if row.volume is not None else None,
                data_as_of=row.data_as_of,
                warnings=warnings,
            )
        )

    logger.info(
        "get_gold_etf | ticker=%s | rows=%d | warnings=%d | elapsed_ms=%d",
        ticker, len(results), warning_count, elapsed_ms,
    )
    return results
