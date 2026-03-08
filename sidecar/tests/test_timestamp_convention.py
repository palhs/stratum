"""
Tests for timestamp convention — DATA-07.

DATA-07: Zero rows in ANY Phase 2 table with NULL data_as_of or NULL ingested_at.

This is the most critical data quality requirement. Any NULL timestamp indicates
a bug in the ingestion pipeline where we failed to set the observation date or
ingestion timestamp.

These are integration tests against the live database.
"""

import os
import pytest
from sqlalchemy import select, func

from app.models import (
    stock_ohlcv,
    stock_fundamentals,
    gold_price,
    gold_etf_ohlcv,
    gold_wgc_flows,
    fred_indicators,
    structure_markers,
)

_FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


# ---------------------------------------------------------------------------
# DATA-07: Zero NULL timestamps in all Phase 2 tables
# ---------------------------------------------------------------------------

class TestTimestampConvention:
    """DATA-07: All Phase 2 tables must have zero NULL data_as_of or ingested_at."""

    def _assert_no_null_timestamps(self, db_session, table, table_name: str):
        """
        Helper: assert no rows have NULL data_as_of OR NULL ingested_at.

        Uses a single query counting violating rows:
          SELECT COUNT(*) FROM {table} WHERE data_as_of IS NULL OR ingested_at IS NULL
        """
        count = db_session.execute(
            select(func.count()).select_from(table).where(
                table.c.data_as_of.is_(None) | table.c.ingested_at.is_(None)
            )
        ).scalar()
        assert count == 0, (
            f"{table_name}: found {count} rows with NULL data_as_of OR NULL ingested_at. "
            "DATA-07 requires zero NULL timestamps in all Phase 2 tables."
        )

    def test_stock_ohlcv_no_null_timestamps(self, db_session):
        """stock_ohlcv: zero NULL data_as_of or ingested_at."""
        self._assert_no_null_timestamps(db_session, stock_ohlcv, "stock_ohlcv")

    def test_stock_fundamentals_no_null_timestamps(self, db_session):
        """stock_fundamentals: zero NULL data_as_of or ingested_at."""
        self._assert_no_null_timestamps(db_session, stock_fundamentals, "stock_fundamentals")

    def test_gold_price_no_null_timestamps(self, db_session):
        """gold_price: zero NULL data_as_of or ingested_at (requires FRED_API_KEY)."""
        count = db_session.execute(select(func.count()).select_from(gold_price)).scalar()
        if count == 0:
            if not _FRED_API_KEY:
                pytest.skip("gold_price is empty — FRED_API_KEY not set (auth gate)")
        self._assert_no_null_timestamps(db_session, gold_price, "gold_price")

    def test_gold_etf_ohlcv_no_null_timestamps(self, db_session):
        """gold_etf_ohlcv: zero NULL data_as_of or ingested_at."""
        self._assert_no_null_timestamps(db_session, gold_etf_ohlcv, "gold_etf_ohlcv")

    def test_gold_wgc_flows_no_null_timestamps(self, db_session):
        """gold_wgc_flows: zero NULL data_as_of or ingested_at (if any rows exist)."""
        count = db_session.execute(
            select(func.count()).select_from(gold_wgc_flows)
        ).scalar()
        if count == 0:
            pytest.skip("gold_wgc_flows is empty (WGC stub active) — skipping timestamp check")
        self._assert_no_null_timestamps(db_session, gold_wgc_flows, "gold_wgc_flows")

    def test_fred_indicators_no_null_timestamps(self, db_session):
        """fred_indicators: zero NULL data_as_of or ingested_at (requires FRED_API_KEY)."""
        count = db_session.execute(select(func.count()).select_from(fred_indicators)).scalar()
        if count == 0:
            if not _FRED_API_KEY:
                pytest.skip("fred_indicators is empty — FRED_API_KEY not set (auth gate)")
        self._assert_no_null_timestamps(db_session, fred_indicators, "fred_indicators")

    def test_structure_markers_no_null_timestamps(self, db_session):
        """structure_markers: zero NULL data_as_of or ingested_at."""
        self._assert_no_null_timestamps(db_session, structure_markers, "structure_markers")

    def test_all_tables_have_rows(self, db_session):
        """
        Comprehensive check: all Phase 2 tables (except wgc_flows and FRED-gated tables) must have rows.

        This confirms the end-to-end pipeline actually ran and produced data.
        If a table is empty, the NULL timestamp tests above would trivially pass
        but data was never ingested.

        Note: gold_price and fred_indicators require FRED_API_KEY. If FRED_API_KEY is not
        set, these tables may be empty and are excluded from this check (auth gate behavior).
        """
        # Core tables that must always have rows (no external API key needed)
        required_tables = [
            (stock_ohlcv, "stock_ohlcv"),
            (stock_fundamentals, "stock_fundamentals"),
            (gold_etf_ohlcv, "gold_etf_ohlcv"),
            (structure_markers, "structure_markers"),
        ]

        # FRED-dependent tables — only required if FRED_API_KEY is set
        if _FRED_API_KEY:
            required_tables.extend([
                (gold_price, "gold_price"),
                (fred_indicators, "fred_indicators"),
            ])

        empty_tables = []
        for table, table_name in required_tables:
            count = db_session.execute(
                select(func.count()).select_from(table)
            ).scalar()
            if count == 0:
                empty_tables.append(table_name)

        assert not empty_tables, (
            f"The following Phase 2 tables are empty: {empty_tables}. "
            "Run the full ingestion pipeline before running this test suite."
        )
