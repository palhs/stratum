"""
Tickers router — chart data endpoints for the Stratum Reasoning Engine.

Endpoints:
  GET /tickers/{symbol}/ohlcv — returns OHLCV candlestick data with MA50/MA200
    computed via SQLAlchemy window functions (no Python-side calculation).

Protected by the require_auth dependency (Supabase JWT).
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import MetaData, Table, func, select

from reasoning.app.auth import require_auth
from reasoning.app.schemas import OHLCVPoint, OHLCVResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Gold ETF tickers — route to gold_etf_ohlcv table (uses 'ticker' column)
# All other symbols route to stock_ohlcv (uses 'symbol' column)
GOLD_TICKERS = {"GLD", "IAU", "SGOL"}


def _to_float(value) -> float | None:
    """Convert Decimal, float, or None to float (or None)."""
    if value is None:
        return None
    return float(value)


def _to_int_volume(value) -> int | None:
    """Convert volume to int (or None)."""
    if value is None:
        return None
    return int(value)


def _query_ohlcv(db_engine, symbol: str) -> list[dict]:
    """Query OHLCV data with MA50 and MA200 computed as window functions.

    Routes to gold_etf_ohlcv for GOLD_TICKERS, otherwise to stock_ohlcv.
    Returns rows for the past 52 weeks, weekly resolution, ordered by date ascending.
    """
    symbol = symbol.upper()
    is_gold = symbol in GOLD_TICKERS

    table_name = "gold_etf_ohlcv" if is_gold else "stock_ohlcv"
    metadata = MetaData()
    tbl = Table(table_name, metadata, autoload_with=db_engine)

    # Column used to filter by symbol differs per table
    sym_col = tbl.c.ticker if is_gold else tbl.c.symbol

    cutoff = datetime.now(timezone.utc) - timedelta(weeks=52)

    # Window spec: ordered by date, rolling window for moving averages
    ma50_window = func.avg(tbl.c.close).over(
        partition_by=sym_col,
        order_by=tbl.c.data_as_of,
        rows=(-49, 0),
    ).label("ma50")

    ma200_window = func.avg(tbl.c.close).over(
        partition_by=sym_col,
        order_by=tbl.c.data_as_of,
        rows=(-199, 0),
    ).label("ma200")

    stmt = (
        select(
            tbl.c.data_as_of,
            tbl.c.open,
            tbl.c.high,
            tbl.c.low,
            tbl.c.close,
            tbl.c.volume,
            ma50_window,
            ma200_window,
        )
        .where(sym_col == symbol)
        .where(tbl.c.resolution == "weekly")
        .where(tbl.c.data_as_of >= cutoff)
        .order_by(tbl.c.data_as_of.asc())
    )

    results = []
    with db_engine.connect() as conn:
        for row in conn.execute(stmt):
            data_as_of = row.data_as_of
            # Ensure timezone-aware datetime for consistent timestamp conversion
            if hasattr(data_as_of, "timestamp"):
                unix_ts = int(data_as_of.timestamp())
            else:
                # date object — convert to midnight UTC
                unix_ts = int(
                    datetime(data_as_of.year, data_as_of.month, data_as_of.day, tzinfo=timezone.utc).timestamp()
                )

            results.append(
                {
                    "time": unix_ts,
                    "open": _to_float(row.open),
                    "high": _to_float(row.high),
                    "low": _to_float(row.low),
                    "close": _to_float(row.close),
                    "volume": _to_int_volume(row.volume),
                    "ma50": _to_float(row.ma50),
                    "ma200": _to_float(row.ma200),
                }
            )

    return results


@router.get("/{symbol}/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str,
    request: Request,
    _: dict = Depends(require_auth),
) -> OHLCVResponse:
    """Return OHLCV candlestick data with rolling MA50/MA200 for the given symbol.

    Time values are Unix timestamps (seconds since epoch) for TradingView Lightweight Charts.
    """
    db_engine = request.app.state.db_engine
    data = _query_ohlcv(db_engine, symbol)
    return OHLCVResponse(symbol=symbol.upper(), data=data)
