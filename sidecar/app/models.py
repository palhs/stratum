"""
SQLAlchemy Table models for all Phase 2 tables.
Phase 2 | Plan 01

Uses Core Table() definitions (not ORM declarative models) because
we use INSERT ON CONFLICT DO UPDATE (upsert) statements directly.

All table definitions MUST exactly match their Flyway migration counterparts:
  V1: pipeline_run_log
  V2: stock_ohlcv, stock_fundamentals
  V3: gold_price, gold_etf_ohlcv, gold_wgc_flows
  V4: fred_indicators
  V5: structure_markers
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    MetaData,
    Numeric,
    Table,
    Text,
    DateTime,
    String,
    Integer,
)

metadata = MetaData()

# =============================================================================
# V1 — pipeline_run_log
# =============================================================================
pipeline_run_log = Table(
    "pipeline_run_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("pipeline_name", String(255), nullable=False),
    Column("run_at", DateTime(timezone=True), nullable=False),
    Column("status", String(50), nullable=False),
    Column("rows_ingested", Integer),
    Column("error_message", Text),
    Column("duration_ms", Integer),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V2 — stock_ohlcv
# =============================================================================
stock_ohlcv = Table(
    "stock_ohlcv",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(20), nullable=False),
    Column("resolution", String(10), nullable=False),
    Column("open", Numeric(18, 4)),
    Column("high", Numeric(18, 4)),
    Column("low", Numeric(18, 4)),
    Column("close", Numeric(18, 4), nullable=False),
    Column("volume", BigInteger),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V2 — stock_fundamentals
# =============================================================================
stock_fundamentals = Table(
    "stock_fundamentals",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(20), nullable=False),
    Column("period_type", String(10), nullable=False),
    Column("pe_ratio", Numeric(12, 4)),
    Column("pb_ratio", Numeric(12, 4)),
    Column("eps", Numeric(12, 4)),
    Column("market_cap", Numeric(24, 2)),
    Column("roe", Numeric(10, 4)),
    Column("roa", Numeric(10, 4)),
    Column("revenue_growth", Numeric(10, 4)),
    Column("net_margin", Numeric(10, 4)),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V3 — gold_price
# =============================================================================
gold_price = Table(
    "gold_price",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("source", String(50), nullable=False),
    Column("price_usd", Numeric(12, 4), nullable=False),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V3 — gold_etf_ohlcv
# =============================================================================
gold_etf_ohlcv = Table(
    "gold_etf_ohlcv",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("ticker", String(10), nullable=False),
    Column("resolution", String(10), nullable=False),
    Column("open", Numeric(12, 4)),
    Column("high", Numeric(12, 4)),
    Column("low", Numeric(12, 4)),
    Column("close", Numeric(12, 4), nullable=False),
    Column("volume", BigInteger),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V3 — gold_wgc_flows
# =============================================================================
gold_wgc_flows = Table(
    "gold_wgc_flows",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("period_end", Date, nullable=False),
    Column("region", String(100)),
    Column("fund_name", String(255)),
    Column("holdings_tonnes", Numeric(12, 4)),
    Column("flows_usd_millions", Numeric(14, 4)),
    Column("central_bank_net_tonnes", Numeric(12, 4)),
    Column("source_lag_note", Text),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V4 — fred_indicators
# =============================================================================
fred_indicators = Table(
    "fred_indicators",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("series_id", String(50), nullable=False),
    Column("value", Numeric(20, 6), nullable=False),
    Column("frequency", String(10), nullable=False),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# V5 — structure_markers
# =============================================================================
structure_markers = Table(
    "structure_markers",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(20), nullable=False),
    Column("asset_type", String(20), nullable=False),
    Column("resolution", String(10), nullable=False),
    Column("close", Numeric(18, 4)),
    Column("ma_10w", Numeric(18, 4)),
    Column("ma_20w", Numeric(18, 4)),
    Column("ma_50w", Numeric(18, 4)),
    Column("drawdown_from_ath", Numeric(8, 6)),
    Column("drawdown_from_52w_high", Numeric(8, 6)),
    Column("close_pct_rank", Numeric(6, 4)),
    Column("pe_pct_rank", Numeric(6, 4)),
    Column("data_as_of", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
)
