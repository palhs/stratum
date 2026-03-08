"""
Tests for vnstock data ingestion — DATA-01 and DATA-02.

DATA-01: stock_ohlcv has rows with correct symbol, resolution, OHLCV columns,
         data_as_of (non-NULL), ingested_at (non-NULL).
DATA-02: stock_fundamentals has rows with PE, PB, EPS, market_cap, ROE, ROA
         columns populated.

These are integration tests against the live database populated by the sidecar.
"""

import pytest
from sqlalchemy import select, func, text

from app.models import stock_ohlcv, stock_fundamentals
from app.services.vnstock_service import get_vn30_symbols


# ---------------------------------------------------------------------------
# DATA-01: stock_ohlcv
# ---------------------------------------------------------------------------

class TestStockOHLCV:
    """DATA-01: stock_ohlcv table quality checks."""

    def test_ohlcv_has_rows(self, db_session):
        """stock_ohlcv must have at least one row after ingestion."""
        count = db_session.execute(
            select(func.count()).select_from(stock_ohlcv)
        ).scalar()
        assert count > 0, (
            "stock_ohlcv is empty — run POST /ingest/vnstock/ohlcv to populate it"
        )

    def test_ohlcv_has_resolution_column(self, db_session):
        """resolution must be 'weekly' or 'monthly' — never NULL or an unknown value."""
        valid_resolutions = {"weekly", "monthly"}
        rows = db_session.execute(
            select(stock_ohlcv.c.resolution).distinct()
        ).fetchall()
        assert rows, "No rows in stock_ohlcv"
        found_resolutions = {r[0] for r in rows}
        unknown = found_resolutions - valid_resolutions
        assert not unknown, (
            f"stock_ohlcv has unexpected resolution values: {unknown}"
        )

    def test_ohlcv_close_non_null(self, db_session):
        """close must be non-NULL for all rows (it is a NOT NULL column)."""
        null_close_count = db_session.execute(
            select(func.count()).select_from(stock_ohlcv).where(
                stock_ohlcv.c.close.is_(None)
            )
        ).scalar()
        assert null_close_count == 0, (
            f"stock_ohlcv has {null_close_count} rows with NULL close"
        )

    def test_ohlcv_symbol_non_null(self, db_session):
        """symbol must be non-NULL for all rows."""
        null_count = db_session.execute(
            select(func.count()).select_from(stock_ohlcv).where(
                stock_ohlcv.c.symbol.is_(None)
            )
        ).scalar()
        assert null_count == 0, (
            f"stock_ohlcv has {null_count} rows with NULL symbol"
        )

    def test_ohlcv_has_multiple_symbols(self, db_session):
        """stock_ohlcv should contain data for multiple VN30 symbols (not just 1)."""
        distinct_symbols = db_session.execute(
            select(func.count(stock_ohlcv.c.symbol.distinct()))
        ).scalar()
        assert distinct_symbols >= 5, (
            f"stock_ohlcv only has data for {distinct_symbols} symbols — "
            "expected at least 5 VN30 constituents"
        )

    def test_ohlcv_data_as_of_is_historical(self, db_session):
        """data_as_of values should be historical dates, not all the same day."""
        distinct_dates = db_session.execute(
            select(func.count(stock_ohlcv.c.data_as_of.distinct()))
        ).scalar()
        assert distinct_dates >= 10, (
            f"stock_ohlcv has only {distinct_dates} distinct data_as_of dates — "
            "expected multiple weeks/months of history"
        )


# ---------------------------------------------------------------------------
# DATA-02: stock_fundamentals
# ---------------------------------------------------------------------------

class TestStockFundamentals:
    """DATA-02: stock_fundamentals table quality checks."""

    def test_fundamentals_has_rows(self, db_session):
        """stock_fundamentals must have at least one row after ingestion."""
        count = db_session.execute(
            select(func.count()).select_from(stock_fundamentals)
        ).scalar()
        assert count > 0, (
            "stock_fundamentals is empty — run POST /ingest/vnstock/fundamentals to populate it"
        )

    def test_fundamentals_pe_populated(self, db_session):
        """At least some rows should have pe_ratio populated."""
        pe_count = db_session.execute(
            select(func.count()).select_from(stock_fundamentals).where(
                stock_fundamentals.c.pe_ratio.isnot(None)
            )
        ).scalar()
        assert pe_count > 0, (
            "stock_fundamentals has no rows with pe_ratio — expected VN30 PE data"
        )

    def test_fundamentals_pb_populated(self, db_session):
        """At least some rows should have pb_ratio populated."""
        pb_count = db_session.execute(
            select(func.count()).select_from(stock_fundamentals).where(
                stock_fundamentals.c.pb_ratio.isnot(None)
            )
        ).scalar()
        assert pb_count > 0, (
            "stock_fundamentals has no rows with pb_ratio — expected VN30 PB data"
        )

    def test_fundamentals_has_multiple_symbols(self, db_session):
        """Fundamentals should cover multiple VN30 symbols."""
        distinct_symbols = db_session.execute(
            select(func.count(stock_fundamentals.c.symbol.distinct()))
        ).scalar()
        assert distinct_symbols >= 5, (
            f"stock_fundamentals only has data for {distinct_symbols} symbols"
        )

    def test_fundamentals_period_type_is_year(self, db_session):
        """period_type should be 'year' for annual fundamentals."""
        rows = db_session.execute(
            select(stock_fundamentals.c.period_type).distinct()
        ).fetchall()
        period_types = {r[0] for r in rows}
        assert "year" in period_types, (
            f"stock_fundamentals does not have any 'year' period_type rows — found: {period_types}"
        )


# ---------------------------------------------------------------------------
# VN30 symbol list (live fetch)
# ---------------------------------------------------------------------------

class TestVN30Symbols:
    """Test that get_vn30_symbols() returns a live, non-empty list."""

    def test_vn30_symbols_dynamic(self):
        """get_vn30_symbols() must return a non-empty list from VCI."""
        symbols = get_vn30_symbols()
        assert isinstance(symbols, list), "get_vn30_symbols() must return a list"
        assert len(symbols) >= 20, (
            f"get_vn30_symbols() returned only {len(symbols)} symbols — "
            "VN30 should have 30 constituents"
        )
        # Symbols should be non-empty strings
        for sym in symbols:
            assert isinstance(sym, str) and len(sym) > 0, (
                f"Invalid symbol in VN30 list: {sym!r}"
            )
