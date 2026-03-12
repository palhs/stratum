"""
reasoning/app/retrieval/types.py — All retrieval return types as Pydantic models.
Phase 5 | Plan 01 | Requirement: RETR-04

All types used as return values from Phase 5 retriever functions (Plans 02-03).
Phase 6+ LangGraph nodes import these types directly for IDE autocomplete and
runtime validation.

Design decisions (locked):
- Pydantic v2 BaseModel (not dataclasses) for IDE autocomplete + validation
- All models have warnings: list[str] = [] field for freshness/data-quality warnings
- NoDataError is a plain Exception subclass (not a Pydantic model) — raise on empty retrieval
- All Optional fields default to None to accommodate sparse/missing data
"""

from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class NoDataError(Exception):
    """
    Raised when a retriever function returns no data for the requested query.
    Phase 6 nodes should catch NoDataError and handle gracefully (e.g., omit
    that data source from the report rather than failing the entire pipeline).
    """

    pass


# ---------------------------------------------------------------------------
# Retrieval return types
# ---------------------------------------------------------------------------


class RegimeAnalogue(BaseModel):
    """
    A historical regime analogue returned from the Neo4j regime analogue retriever.
    Represents a past economic period similar to the current regime.
    """

    source_regime: str
    analogue_id: str
    analogue_name: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    similarity_score: float
    dimensions_matched: list[str] = []
    narrative: Optional[str] = None
    warnings: list[str] = []


class DocumentChunk(BaseModel):
    """
    A document chunk returned from Qdrant hybrid search (macro_docs or earnings_docs).
    Represents a semantically relevant passage from an FOMC/SBV/earnings document.
    """

    id: str
    text: str
    score: float
    source: str
    lang: str = "en"
    metadata: dict[str, Any] = {}
    warnings: list[str] = []


class FundamentalsRow(BaseModel):
    """
    A stock fundamentals row from the stock_fundamentals PostgreSQL table.
    """

    symbol: str
    period_type: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    revenue_growth: Optional[float] = None
    net_margin: Optional[float] = None
    data_as_of: datetime
    warnings: list[str] = []


class StructureMarkerRow(BaseModel):
    """
    A price structure marker row from the structure_markers PostgreSQL table.
    Contains moving averages, drawdown metrics, and percentile ranks.
    """

    symbol: str
    asset_type: str
    resolution: str
    close: Optional[float] = None
    ma_10w: Optional[float] = None
    ma_20w: Optional[float] = None
    ma_50w: Optional[float] = None
    drawdown_from_ath: Optional[float] = None
    drawdown_from_52w_high: Optional[float] = None
    close_pct_rank: Optional[float] = None
    pe_pct_rank: Optional[float] = None
    data_as_of: datetime
    warnings: list[str] = []


class FredIndicatorRow(BaseModel):
    """
    A FRED macroeconomic indicator row from the fred_indicators PostgreSQL table.
    """

    series_id: str
    value: float
    frequency: str
    data_as_of: datetime
    warnings: list[str] = []


class GoldPriceRow(BaseModel):
    """
    A gold price row from the gold_price PostgreSQL table.
    """

    source: str
    price_usd: float
    data_as_of: datetime
    warnings: list[str] = []


class GoldEtfRow(BaseModel):
    """
    A gold ETF OHLCV row from the gold_etf_ohlcv PostgreSQL table.
    """

    ticker: str
    resolution: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
    data_as_of: datetime
    warnings: list[str] = []
