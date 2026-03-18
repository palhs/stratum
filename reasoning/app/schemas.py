"""
Shared Pydantic v2 response schemas for the Stratum Reasoning Engine API.

Used by:
  - GET /tickers/{symbol}/ohlcv  → OHLCVPoint, OHLCVResponse
  - GET /tickers/{symbol}/reports → ReportHistoryItem, ReportHistoryResponse (Phase 10-02)
  - GET /watchlist → WatchlistItem, WatchlistResponse (Phase 11-02)
  - PUT /watchlist → WatchlistUpdate (Phase 11-02)
"""
from typing import Optional

from pydantic import BaseModel


class OHLCVPoint(BaseModel):
    """Single OHLCV candlestick with optional moving averages.

    time is a Unix timestamp (seconds since epoch) — the format expected by
    TradingView Lightweight Charts.
    """

    time: int  # Unix timestamp (seconds since epoch)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
    ma50: Optional[float] = None
    ma200: Optional[float] = None


class OHLCVResponse(BaseModel):
    """Top-level response for the OHLCV chart endpoint."""

    symbol: str
    data: list[OHLCVPoint]


class ReportHistoryItem(BaseModel):
    """Summary of one historical analysis report."""

    report_id: int
    generated_at: str  # ISO 8601 datetime string
    tier: str  # "Favorable" | "Neutral" | "Cautious" | "Avoid"
    verdict: str  # one-line narrative summary


class ReportHistoryResponse(BaseModel):
    """Paginated report history for a symbol."""

    symbol: str
    page: int
    per_page: int
    total: int
    items: list[ReportHistoryItem]


class WatchlistItem(BaseModel):
    """Single ticker in a user's watchlist."""

    symbol: str
    name: str
    asset_type: str  # "equity" | "gold_etf"


class WatchlistResponse(BaseModel):
    """User's full watchlist."""

    tickers: list[WatchlistItem]


class WatchlistUpdate(BaseModel):
    """Payload for PUT /watchlist — full list replacement."""

    tickers: list[str]  # list of symbol strings
