"""
reasoning/tests/test_postgres_retriever.py — Integration tests for PostgreSQL retrievers.
Phase 5 | Plan 02 | Requirement: RETR-03

Tests run against the live PostgreSQL Docker service with Phase 2 ingested data.
No mocks — locked decision.

Environment:
  DATABASE_URL is read from environment (docker exec provides the connection)
  Tests that require the db_engine fixture will be skipped if PostgreSQL unavailable.

Note: fred_indicators and gold_price tables may be empty (data ingestion not yet run
for all sources). Tests for these tables use pytest.skip when no data is available.
"""

import os
from datetime import datetime, timezone, timedelta

import pytest
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_engine():
    """
    Session-scoped PostgreSQL engine fixture for retriever tests.
    Creates engine directly (not via conftest.py) using DATABASE_URL from env.
    """
    from sqlalchemy import create_engine, text

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stratum:stratum_password@postgres:5432/stratum"
    )

    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=3,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available at DATABASE_URL: {exc}")

    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Tests for get_fundamentals()
# ---------------------------------------------------------------------------


class TestGetFundamentals:
    """Tests for get_fundamentals() — stock_fundamentals table."""

    def test_returns_list_for_valid_symbol(self, pg_engine):
        """get_fundamentals() returns a non-empty list for a known symbol."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals
        from reasoning.app.retrieval.types import FundamentalsRow

        results = get_fundamentals("VNM", engine=pg_engine)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, FundamentalsRow) for r in results)

    def test_row_has_all_required_fields(self, pg_engine):
        """Each FundamentalsRow has symbol, period_type, data_as_of, and warnings."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals

        results = get_fundamentals("VNM", engine=pg_engine)
        assert len(results) > 0

        for row in results:
            assert row.symbol == "VNM"
            assert row.period_type is not None
            assert row.data_as_of is not None
            assert isinstance(row.warnings, list)

    def test_lookback_quarters_limits_results(self, pg_engine):
        """lookback_quarters parameter limits the number of rows returned."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals

        results_1 = get_fundamentals("VNM", lookback_quarters=1, engine=pg_engine)
        results_4 = get_fundamentals("VNM", lookback_quarters=4, engine=pg_engine)

        assert len(results_1) <= 1
        assert len(results_4) <= 4
        # More quarters = more results (assuming VNM has multi-quarter data)
        assert len(results_4) >= len(results_1)

    def test_raises_no_data_error_for_nonexistent_symbol(self, pg_engine):
        """get_fundamentals() raises NoDataError for a symbol not in the DB."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals
        from reasoning.app.retrieval.types import NoDataError

        with pytest.raises(NoDataError):
            get_fundamentals("NONEXISTENT_SYMBOL_XYZ", engine=pg_engine)

    def test_fresh_data_has_empty_warnings(self, pg_engine):
        """Fresh data (now_override = data_as_of + 1 day) has empty warnings."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals

        results = get_fundamentals("VNM", lookback_quarters=1, engine=pg_engine)
        assert len(results) > 0

        # Use now_override = data_as_of + 1 day (data is fresh)
        fresh_override = results[0].data_as_of + timedelta(days=1)
        fresh_results = get_fundamentals(
            "VNM",
            lookback_quarters=1,
            now_override=fresh_override,
            engine=pg_engine,
        )
        assert len(fresh_results) > 0
        assert fresh_results[0].warnings == [], (
            f"Expected no warnings for fresh data, got: {fresh_results[0].warnings}"
        )

    def test_stale_data_has_warnings(self, pg_engine):
        """Stale data (now_override = data_as_of + 200 days) has populated warnings."""
        from reasoning.app.retrieval.postgres_retriever import get_fundamentals

        results = get_fundamentals("VNM", lookback_quarters=1, engine=pg_engine)
        assert len(results) > 0

        # Use now_override 200 days after data_as_of (threshold is 120 days for fundamentals)
        stale_override = results[0].data_as_of + timedelta(days=200)
        stale_results = get_fundamentals(
            "VNM",
            lookback_quarters=1,
            now_override=stale_override,
            engine=pg_engine,
        )
        assert len(stale_results) > 0
        assert len(stale_results[0].warnings) > 0, (
            "Expected staleness warning for data 200 days old (threshold: 120 days)"
        )


# ---------------------------------------------------------------------------
# Tests for get_structure_markers()
# ---------------------------------------------------------------------------


class TestGetStructureMarkers:
    """Tests for get_structure_markers() — structure_markers table."""

    def test_returns_list_for_valid_symbol(self, pg_engine):
        """get_structure_markers() returns a non-empty list for a known symbol."""
        from reasoning.app.retrieval.postgres_retriever import get_structure_markers
        from reasoning.app.retrieval.types import StructureMarkerRow

        results = get_structure_markers("VNM", engine=pg_engine)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, StructureMarkerRow) for r in results)

    def test_row_has_required_fields(self, pg_engine):
        """Each StructureMarkerRow has symbol, asset_type, resolution, data_as_of."""
        from reasoning.app.retrieval.postgres_retriever import get_structure_markers

        results = get_structure_markers("VNM", engine=pg_engine)
        assert len(results) > 0

        row = results[0]
        assert row.symbol == "VNM"
        assert row.asset_type is not None
        assert row.resolution is not None
        assert row.data_as_of is not None
        assert isinstance(row.warnings, list)

    def test_raises_no_data_error_for_nonexistent_symbol(self, pg_engine):
        """get_structure_markers() raises NoDataError for unknown symbol."""
        from reasoning.app.retrieval.postgres_retriever import get_structure_markers
        from reasoning.app.retrieval.types import NoDataError

        with pytest.raises(NoDataError):
            get_structure_markers("NONEXISTENT_SYMBOL_XYZ", engine=pg_engine)


# ---------------------------------------------------------------------------
# Tests for get_fred_indicators()
# ---------------------------------------------------------------------------


class TestGetFredIndicators:
    """Tests for get_fred_indicators() — fred_indicators table."""

    def test_raises_no_data_error_when_table_empty_or_no_series(self, pg_engine):
        """get_fred_indicators() raises NoDataError for unknown series."""
        from reasoning.app.retrieval.postgres_retriever import get_fred_indicators
        from reasoning.app.retrieval.types import NoDataError

        with pytest.raises(NoDataError):
            get_fred_indicators(
                series_ids=["NONEXISTENT_SERIES_XYZ"],
                engine=pg_engine,
            )

    def test_returns_list_type(self, pg_engine):
        """get_fred_indicators() with valid series returns list (possibly empty if no data)."""
        from reasoning.app.retrieval.postgres_retriever import get_fred_indicators
        from reasoning.app.retrieval.types import NoDataError, FredIndicatorRow

        try:
            results = get_fred_indicators(
                series_ids=["FEDFUNDS"],
                engine=pg_engine,
            )
            assert isinstance(results, list)
            if results:
                assert all(isinstance(r, FredIndicatorRow) for r in results)
        except NoDataError:
            # fred_indicators table may be empty (FRED ingestion not yet run)
            pytest.skip("FEDFUNDS data not available in fred_indicators — FRED ingestion needed")


# ---------------------------------------------------------------------------
# Tests for get_gold_price()
# ---------------------------------------------------------------------------


class TestGetGoldPrice:
    """Tests for get_gold_price() — gold_price table."""

    def test_raises_no_data_error_when_empty(self, pg_engine):
        """get_gold_price() raises NoDataError when gold_price table is empty."""
        from sqlalchemy import text
        from reasoning.app.retrieval.postgres_retriever import get_gold_price
        from reasoning.app.retrieval.types import NoDataError

        # Check if gold_price has data
        with pg_engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) FROM gold_price")).fetchone()
            count = row[0]

        if count == 0:
            with pytest.raises(NoDataError):
                get_gold_price(engine=pg_engine)
        else:
            from reasoning.app.retrieval.types import GoldPriceRow
            results = get_gold_price(engine=pg_engine)
            assert isinstance(results, list)
            assert all(isinstance(r, GoldPriceRow) for r in results)

    def test_accepts_lookback_days_parameter(self, pg_engine):
        """get_gold_price() accepts lookback_days parameter without error."""
        from reasoning.app.retrieval.postgres_retriever import get_gold_price
        from reasoning.app.retrieval.types import NoDataError

        try:
            results = get_gold_price(lookback_days=30, engine=pg_engine)
            assert isinstance(results, list)
        except NoDataError:
            pass  # Expected when gold_price is empty


# ---------------------------------------------------------------------------
# Tests for get_gold_etf()
# ---------------------------------------------------------------------------


class TestGetGoldEtf:
    """Tests for get_gold_etf() — gold_etf_ohlcv table."""

    def test_returns_list_for_gld(self, pg_engine):
        """get_gold_etf() returns a non-empty list for GLD ticker."""
        from reasoning.app.retrieval.postgres_retriever import get_gold_etf
        from reasoning.app.retrieval.types import GoldEtfRow

        results = get_gold_etf("GLD", lookback_days=30, engine=pg_engine)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, GoldEtfRow) for r in results)

    def test_row_has_required_fields(self, pg_engine):
        """Each GoldEtfRow has ticker, resolution, close, data_as_of, warnings."""
        from reasoning.app.retrieval.postgres_retriever import get_gold_etf

        results = get_gold_etf("GLD", lookback_days=30, engine=pg_engine)
        assert len(results) > 0

        row = results[0]
        assert row.ticker == "GLD"
        assert row.resolution is not None
        assert row.close is not None
        assert row.data_as_of is not None
        assert isinstance(row.warnings, list)

    def test_raises_no_data_error_for_nonexistent_ticker(self, pg_engine):
        """get_gold_etf() raises NoDataError for unknown ticker."""
        from reasoning.app.retrieval.postgres_retriever import get_gold_etf
        from reasoning.app.retrieval.types import NoDataError

        with pytest.raises(NoDataError):
            get_gold_etf("NONEXISTENT_TICKER_XYZ", engine=pg_engine)

    def test_stale_data_has_warnings(self, pg_engine):
        """Stale GLD data (200 days past threshold) has warnings populated."""
        from reasoning.app.retrieval.postgres_retriever import get_gold_etf

        # Get the most recent GLD row
        results = get_gold_etf("GLD", lookback_days=7, engine=pg_engine)
        assert len(results) > 0

        # 200 days after data_as_of (threshold is 10 days for gold_etf_ohlcv)
        stale_override = results[0].data_as_of + timedelta(days=200)
        stale_results = get_gold_etf(
            "GLD",
            lookback_days=7,
            now_override=stale_override,
            engine=pg_engine,
        )
        assert len(stale_results) > 0
        assert len(stale_results[0].warnings) > 0, (
            "Expected staleness warning for data 200 days old (threshold: 10 days)"
        )
