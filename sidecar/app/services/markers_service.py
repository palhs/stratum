"""
Structure marker computation service for the Stratum Data Sidecar.
Phase 2 | Plan 03

Reads OHLCV and gold price data from PostgreSQL, computes pre-computed structure
markers (moving averages, drawdowns, valuation percentiles), and writes to the
structure_markers table.

LangGraph reasoning nodes READ pre-computed markers — they NEVER compute them.
This is a core project requirement (INFRA-02 storage boundary).

Computation strategy:
  - Full recompute on each run (VN30 scale: ~30 symbols × 260 weeks = ~7,800 rows < 5s)
  - Incremental adds complexity with no meaningful performance gain at this scale

Locked decisions:
  - MA windows: 10w, 20w, 50w
  - Drawdowns: BOTH full-history ATH and 52-week high
  - Valuation percentiles: 5-year rolling window for stocks, 10-year for gold
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import (
    gold_etf_ohlcv,
    gold_price,
    stock_fundamentals,
    stock_ohlcv,
    structure_markers,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Moving average windows (weeks)
_MA_10W_WINDOW = 10
_MA_20W_WINDOW = 20
_MA_50W_WINDOW = 50

# min_periods at ~80% of window
_MA_10W_MIN_PERIODS = 8
_MA_20W_MIN_PERIODS = 16
_MA_50W_MIN_PERIODS = 40

# Drawdown
_DRAWDOWN_52W_MIN_PERIODS = 26  # at least 6 months before computing 52w high

# Valuation percentile windows (bars at weekly resolution)
_STOCK_PCT_WINDOW = 260   # 5 years × 52 weeks
_STOCK_PCT_MIN_PERIODS = 52
_GOLD_PCT_WINDOW = 520    # 10 years × 52 weeks
_GOLD_PCT_MIN_PERIODS = 104

# Asset type labels
_ASSET_TYPE_STOCK = "stock"
_ASSET_TYPE_GOLD_SPOT = "gold_spot"
_ASSET_TYPE_GOLD_ETF = "gold_etf"


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_stock_ohlcv(db: Session) -> pd.DataFrame:
    """
    Load weekly VN30 stock OHLCV data from PostgreSQL.

    Returns DataFrame with columns: symbol, resolution, close, data_as_of
    """
    query = select(
        stock_ohlcv.c.symbol,
        stock_ohlcv.c.resolution,
        stock_ohlcv.c.close,
        stock_ohlcv.c.data_as_of,
    ).where(
        stock_ohlcv.c.resolution == "weekly"
    ).order_by(
        stock_ohlcv.c.symbol,
        stock_ohlcv.c.data_as_of,
    )
    result = db.execute(query)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["symbol", "resolution", "close", "data_as_of"])
    df = pd.DataFrame(rows, columns=["symbol", "resolution", "close", "data_as_of"])
    df["asset_type"] = _ASSET_TYPE_STOCK
    return df


def _load_gold_spot(db: Session) -> pd.DataFrame:
    """
    Load gold spot price data from PostgreSQL.

    Maps: price_usd -> close, adds symbol='XAU', resolution='weekly'.
    Note: gold_price stores daily/spot data; we treat it as weekly-compatible
    since it represents the gold spot price level.
    """
    query = select(
        gold_price.c.price_usd.label("close"),
        gold_price.c.data_as_of,
    ).order_by(
        gold_price.c.data_as_of,
    )
    result = db.execute(query)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["symbol", "resolution", "close", "data_as_of", "asset_type"])
    df = pd.DataFrame(rows, columns=["close", "data_as_of"])
    df["symbol"] = "XAU"
    df["resolution"] = "weekly"
    df["asset_type"] = _ASSET_TYPE_GOLD_SPOT
    return df[["symbol", "resolution", "close", "data_as_of", "asset_type"]]


def _load_gold_etf(db: Session) -> pd.DataFrame:
    """
    Load weekly gold ETF OHLCV data from PostgreSQL.

    Returns DataFrame with columns: symbol, resolution, close, data_as_of
    """
    query = select(
        gold_etf_ohlcv.c.ticker.label("symbol"),
        gold_etf_ohlcv.c.resolution,
        gold_etf_ohlcv.c.close,
        gold_etf_ohlcv.c.data_as_of,
    ).where(
        gold_etf_ohlcv.c.resolution == "weekly"
    ).order_by(
        gold_etf_ohlcv.c.ticker,
        gold_etf_ohlcv.c.data_as_of,
    )
    result = db.execute(query)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["symbol", "resolution", "close", "data_as_of", "asset_type"])
    df = pd.DataFrame(rows, columns=["symbol", "resolution", "close", "data_as_of"])
    df["asset_type"] = _ASSET_TYPE_GOLD_ETF
    return df


def _load_pe_ratios(db: Session) -> pd.DataFrame:
    """
    Load latest PE ratio per symbol from stock_fundamentals.

    Returns DataFrame with columns: symbol, pe_ratio (most recent annual entry).
    Used to compute pe_pct_rank for stocks.
    """
    # Get the most recent pe_ratio per symbol using a subquery approach
    query = text("""
        SELECT DISTINCT ON (symbol)
            symbol,
            pe_ratio,
            data_as_of
        FROM stock_fundamentals
        WHERE pe_ratio IS NOT NULL
        ORDER BY symbol, data_as_of DESC
    """)
    result = db.execute(query)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["symbol", "pe_ratio", "data_as_of"])
    return pd.DataFrame(rows, columns=["symbol", "pe_ratio", "data_as_of"])


def _load_all_pe_history(db: Session) -> pd.DataFrame:
    """
    Load full PE ratio history per symbol from stock_fundamentals.

    Returns DataFrame with columns: symbol, pe_ratio, data_as_of
    Used to compute pe_pct_rank rolling percentile.
    """
    query = select(
        stock_fundamentals.c.symbol,
        stock_fundamentals.c.pe_ratio,
        stock_fundamentals.c.data_as_of,
    ).where(
        stock_fundamentals.c.pe_ratio.isnot(None)
    ).order_by(
        stock_fundamentals.c.symbol,
        stock_fundamentals.c.data_as_of,
    )
    result = db.execute(query)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["symbol", "pe_ratio", "data_as_of"])
    return pd.DataFrame(rows, columns=["symbol", "pe_ratio", "data_as_of"])


# ---------------------------------------------------------------------------
# Marker computation
# ---------------------------------------------------------------------------

def _compute_markers_for_group(
    df_group: pd.DataFrame,
    asset_type: str,
    pe_history: Optional[pd.DataFrame] = None,
    symbol: Optional[str] = None,
) -> pd.DataFrame:
    """
    Compute all structure markers for a single (symbol, resolution) group.

    Args:
        df_group:   DataFrame sorted by data_as_of ASC with a 'close' column.
        asset_type: 'stock', 'gold_spot', or 'gold_etf'
        pe_history: Full PE ratio history for this symbol (stocks only), or None.
        symbol:     Symbol name (for logging).

    Returns:
        DataFrame with all marker columns added.
    """
    close = df_group["close"].astype(float)

    # -------------------------------------------------------------------------
    # a. Moving averages — 10w, 20w, 50w
    # -------------------------------------------------------------------------
    df_group = df_group.copy()
    df_group["ma_10w"] = close.rolling(_MA_10W_WINDOW, min_periods=_MA_10W_MIN_PERIODS).mean()
    df_group["ma_20w"] = close.rolling(_MA_20W_WINDOW, min_periods=_MA_20W_MIN_PERIODS).mean()
    df_group["ma_50w"] = close.rolling(_MA_50W_WINDOW, min_periods=_MA_50W_MIN_PERIODS).mean()

    # -------------------------------------------------------------------------
    # b. Full-history ATH drawdown
    # -------------------------------------------------------------------------
    ath = close.expanding().max()
    df_group["drawdown_from_ath"] = (close / ath) - 1.0

    # -------------------------------------------------------------------------
    # c. 52-week high drawdown
    # -------------------------------------------------------------------------
    high_52w = close.rolling(52, min_periods=_DRAWDOWN_52W_MIN_PERIODS).max()
    df_group["drawdown_from_52w_high"] = (close / high_52w) - 1.0

    # -------------------------------------------------------------------------
    # d. Valuation percentile (close price percentile rank)
    # -------------------------------------------------------------------------
    if asset_type == _ASSET_TYPE_STOCK:
        pct_window = _STOCK_PCT_WINDOW
        pct_min_periods = _STOCK_PCT_MIN_PERIODS
    else:
        # gold_spot and gold_etf use 10-year window
        pct_window = _GOLD_PCT_WINDOW
        pct_min_periods = _GOLD_PCT_MIN_PERIODS

    # Use pandas rolling rank (available in pandas >= 1.4) — faster than apply
    # rank(pct=True) returns percentile rank of the last value in the window
    try:
        df_group["close_pct_rank"] = close.rolling(pct_window, min_periods=pct_min_periods).rank(pct=True)
    except AttributeError:
        # Fallback for older pandas without rolling().rank()
        def _pct_rank(x: "np.ndarray") -> float:
            s = pd.Series(x)
            return float(s.rank(pct=True).iloc[-1])
        df_group["close_pct_rank"] = close.rolling(pct_window, min_periods=pct_min_periods).apply(
            _pct_rank, raw=True
        )

    # -------------------------------------------------------------------------
    # e. P/E percentile rank (stocks only)
    # -------------------------------------------------------------------------
    if asset_type == _ASSET_TYPE_STOCK and pe_history is not None and not pe_history.empty and symbol:
        # Get PE history for this symbol
        sym_pe = pe_history[pe_history["symbol"] == symbol][["pe_ratio", "data_as_of"]].copy()
        sym_pe = sym_pe.sort_values("data_as_of").drop_duplicates("data_as_of")
        sym_pe["pe_ratio"] = sym_pe["pe_ratio"].astype(float)

        if not sym_pe.empty:
            # Merge PE data with close data on data_as_of (annual PE vs weekly close)
            # For each weekly bar, find the most recent available annual PE
            # Strategy: merge_asof (forward-fill from most recent annual report)
            df_group = df_group.sort_values("data_as_of")
            sym_pe = sym_pe.sort_values("data_as_of")

            # Ensure datetime types are compatible for merge_asof
            df_group["data_as_of"] = pd.to_datetime(df_group["data_as_of"])
            sym_pe["data_as_of"] = pd.to_datetime(sym_pe["data_as_of"])

            merged = pd.merge_asof(
                df_group[["data_as_of"]].reset_index(drop=False),
                sym_pe[["data_as_of", "pe_ratio"]],
                on="data_as_of",
                direction="backward",
            )

            pe_series = merged.set_index("index")["pe_ratio"]
            pe_series = pe_series.reindex(df_group.index).astype(float)

            # Compute rolling percentile rank on the PE series aligned to weekly bars
            # Use 5-year window (260 bars) with min_periods=52
            try:
                df_group["pe_pct_rank"] = pe_series.rolling(
                    _STOCK_PCT_WINDOW, min_periods=_STOCK_PCT_MIN_PERIODS
                ).rank(pct=True)
            except AttributeError:
                def _pe_pct_rank(x: "np.ndarray") -> float:
                    s = pd.Series(x)
                    return float(s.rank(pct=True).iloc[-1])
                df_group["pe_pct_rank"] = pe_series.rolling(
                    _STOCK_PCT_WINDOW, min_periods=_STOCK_PCT_MIN_PERIODS
                ).apply(_pe_pct_rank, raw=True)
        else:
            df_group["pe_pct_rank"] = None
    else:
        # Gold and stocks with no PE history: pe_pct_rank = NULL
        df_group["pe_pct_rank"] = None

    return df_group


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_and_upsert_markers(
    db: Session,
    asset_types: Optional[list[str]] = None,
) -> dict:
    """
    Full recompute of structure markers for all (or selected) asset types.

    Reads source OHLCV/price data from PostgreSQL, computes rolling window
    indicators, and upserts to the structure_markers table.

    Args:
        db:           SQLAlchemy session.
        asset_types:  List of asset types to process. Defaults to all three:
                      ["stock", "gold_spot", "gold_etf"]

    Returns:
        dict with keys:
          - total_rows_written: int
          - breakdown: dict[str, int]  — rows per asset_type
          - null_counts: dict[str, int] — NULL count per marker column
    """
    if asset_types is None:
        asset_types = [_ASSET_TYPE_STOCK, _ASSET_TYPE_GOLD_SPOT, _ASSET_TYPE_GOLD_ETF]

    now_utc = datetime.now(tz=timezone.utc)
    all_frames: list[pd.DataFrame] = []
    breakdown: dict[str, int] = {}

    # -------------------------------------------------------------------------
    # Load PE history once (shared across all stock groups)
    # -------------------------------------------------------------------------
    pe_history: Optional[pd.DataFrame] = None
    if _ASSET_TYPE_STOCK in asset_types:
        pe_history = _load_all_pe_history(db)
        logger.info(
            "Loaded PE history: %d rows for %d symbols",
            len(pe_history),
            pe_history["symbol"].nunique() if not pe_history.empty else 0,
        )

    # -------------------------------------------------------------------------
    # Load and process each asset type
    # -------------------------------------------------------------------------
    source_frames: dict[str, pd.DataFrame] = {}

    if _ASSET_TYPE_STOCK in asset_types:
        source_frames[_ASSET_TYPE_STOCK] = _load_stock_ohlcv(db)
    if _ASSET_TYPE_GOLD_SPOT in asset_types:
        source_frames[_ASSET_TYPE_GOLD_SPOT] = _load_gold_spot(db)
    if _ASSET_TYPE_GOLD_ETF in asset_types:
        source_frames[_ASSET_TYPE_GOLD_ETF] = _load_gold_etf(db)

    for asset_type, df_source in source_frames.items():
        if df_source.empty:
            logger.info("No source data for asset_type=%s — skipping", asset_type)
            breakdown[asset_type] = 0
            continue

        logger.info(
            "Processing asset_type=%s: %d rows, %d symbols",
            asset_type,
            len(df_source),
            df_source["symbol"].nunique(),
        )

        computed_groups: list[pd.DataFrame] = []

        for (symbol, resolution), group in df_source.groupby(["symbol", "resolution"]):
            group = group.sort_values("data_as_of").reset_index(drop=True)

            try:
                group_with_markers = _compute_markers_for_group(
                    df_group=group,
                    asset_type=asset_type,
                    pe_history=pe_history if asset_type == _ASSET_TYPE_STOCK else None,
                    symbol=symbol if asset_type == _ASSET_TYPE_STOCK else None,
                )
            except Exception as exc:
                logger.error(
                    "Marker computation failed for symbol=%s asset_type=%s: %s",
                    symbol, asset_type, exc,
                )
                # Still write rows with NULL markers rather than skipping entirely
                group_with_markers = group.copy()
                for col in ["ma_10w", "ma_20w", "ma_50w", "drawdown_from_ath",
                            "drawdown_from_52w_high", "close_pct_rank", "pe_pct_rank"]:
                    group_with_markers[col] = None

            group_with_markers["asset_type"] = asset_type
            computed_groups.append(group_with_markers)

        if not computed_groups:
            breakdown[asset_type] = 0
            continue

        df_asset = pd.concat(computed_groups, ignore_index=True)

        # Add ingested_at timestamp
        df_asset["ingested_at"] = now_utc

        all_frames.append(df_asset)
        breakdown[asset_type] = len(df_asset)

    if not all_frames:
        logger.info("No markers to write — all source tables empty")
        return {
            "total_rows_written": 0,
            "breakdown": breakdown,
            "null_counts": {},
        }

    df_all = pd.concat(all_frames, ignore_index=True)

    # -------------------------------------------------------------------------
    # Log NULL counts as health metrics (before writing)
    # -------------------------------------------------------------------------
    marker_cols = ["ma_10w", "ma_20w", "ma_50w", "drawdown_from_ath",
                   "drawdown_from_52w_high", "close_pct_rank", "pe_pct_rank"]
    null_counts: dict[str, int] = {}
    for col in marker_cols:
        if col in df_all.columns:
            n_null = int(df_all[col].isna().sum())
            null_counts[col] = n_null
            if n_null > 0:
                logger.info(
                    "NULL count for %s: %d/%d (%.1f%%) — expected for early-history rows",
                    col, n_null, len(df_all), 100 * n_null / len(df_all),
                )

    # -------------------------------------------------------------------------
    # Build upsert rows
    # -------------------------------------------------------------------------
    db_cols = [
        "symbol", "asset_type", "resolution", "close",
        "ma_10w", "ma_20w", "ma_50w",
        "drawdown_from_ath", "drawdown_from_52w_high",
        "close_pct_rank", "pe_pct_rank",
        "data_as_of", "ingested_at",
    ]

    # Convert NaN/NaT to None for PostgreSQL NULL handling
    for col in db_cols:
        if col in df_all.columns:
            df_all[col] = df_all[col].where(df_all[col].notna(), other=None)

    rows_to_write = df_all[[c for c in db_cols if c in df_all.columns]].to_dict(orient="records")

    # -------------------------------------------------------------------------
    # Upsert to structure_markers
    # -------------------------------------------------------------------------
    stmt = pg_insert(structure_markers).values(rows_to_write)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "resolution", "data_as_of"],
        set_={
            "asset_type": stmt.excluded.asset_type,
            "close": stmt.excluded.close,
            "ma_10w": stmt.excluded.ma_10w,
            "ma_20w": stmt.excluded.ma_20w,
            "ma_50w": stmt.excluded.ma_50w,
            "drawdown_from_ath": stmt.excluded.drawdown_from_ath,
            "drawdown_from_52w_high": stmt.excluded.drawdown_from_52w_high,
            "close_pct_rank": stmt.excluded.close_pct_rank,
            "pe_pct_rank": stmt.excluded.pe_pct_rank,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db.execute(stmt)
    db.commit()

    total = len(rows_to_write)
    logger.info(
        "structure_markers upsert complete: %d rows written, breakdown: %s",
        total, breakdown,
    )

    return {
        "total_rows_written": total,
        "breakdown": breakdown,
        "null_counts": null_counts,
    }
