"""
Tests for FRED data ingestion — DATA-03 and DATA-05.

DATA-03: gold_price has rows with data_as_of = FRED observation date
         (spread across years, NOT clustered on today/ingestion date).
DATA-05: fred_indicators has rows for GDP, CPIAUCSL, UNRATE, FEDFUNDS
         with data_as_of spanning observation periods across years.

These are integration tests against the live database populated by the sidecar.

NOTE: These tests require FRED_API_KEY to be set in the environment and the
POST /ingest/gold/fred-price and POST /ingest/fred/indicators endpoints to
have been run. Tests will skip if FRED_API_KEY is not set (auth gate).
"""

import datetime
import os

import pytest
from sqlalchemy import select, func

from app.models import fred_indicators, gold_price


# ---------------------------------------------------------------------------
# Skip marker: FRED tests require FRED_API_KEY
# ---------------------------------------------------------------------------

_FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
_requires_fred = pytest.mark.skipif(
    not _FRED_API_KEY,
    reason="FRED_API_KEY not set — FRED/gold tests skipped (auth gate). "
    "Set FRED_API_KEY in environment and run ingest endpoints to validate DATA-03/DATA-05."
)


# ---------------------------------------------------------------------------
# DATA-03: gold_price — FRED observation dates
# ---------------------------------------------------------------------------

@_requires_fred
class TestGoldPriceFREDDates:
    """DATA-03: gold_price.data_as_of must be FRED observation dates, not ingestion dates."""

    def test_gold_price_has_rows(self, db_session):
        """gold_price must have at least one row."""
        count = db_session.execute(
            select(func.count()).select_from(gold_price)
        ).scalar()
        assert count > 0, (
            "gold_price is empty — run POST /ingest/gold/fred-price to populate it"
        )

    def test_gold_price_data_as_of_is_historical(self, db_session):
        """
        gold_price.data_as_of must span years, not all be today.

        The FRED gold price (GOLDAMGBD228NLBM) goes back decades. A 10-year
        backfill will give thousands of rows with data_as_of spread across years.
        The minimum data_as_of should be at least 5 years before today.
        """
        min_date = db_session.execute(
            select(func.min(gold_price.c.data_as_of))
        ).scalar()
        assert min_date is not None, "gold_price has NULL min(data_as_of)"

        # data_as_of should reach back at least 5 years
        five_years_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5 * 365)
        assert min_date < five_years_ago, (
            f"gold_price min(data_as_of) is {min_date} — expected dates at least 5 years ago. "
            "This suggests data_as_of was set to NOW() instead of the FRED observation date."
        )

    def test_gold_price_has_many_distinct_dates(self, db_session):
        """gold_price should have many distinct data_as_of values (daily gold prices)."""
        distinct_count = db_session.execute(
            select(func.count(gold_price.c.data_as_of.distinct()))
        ).scalar()
        # A 5-year daily series has ~1,300 trading days; a 10-year has ~2,600
        assert distinct_count >= 100, (
            f"gold_price has only {distinct_count} distinct data_as_of values — "
            "expected 100+ from a multi-year FRED backfill"
        )

    def test_gold_price_source_is_fred(self, db_session):
        """source column should contain FRED reference."""
        rows = db_session.execute(
            select(gold_price.c.source).distinct()
        ).fetchall()
        sources = {r[0] for r in rows}
        fred_sources = {s for s in sources if "FRED" in s.upper()}
        assert fred_sources, (
            f"gold_price has no FRED-sourced rows — found sources: {sources}"
        )


# ---------------------------------------------------------------------------
# DATA-05: fred_indicators — observation period dates + all series
# ---------------------------------------------------------------------------

@_requires_fred
class TestFREDIndicators:
    """DATA-05: fred_indicators must have all series with historical observation dates."""

    _EXPECTED_SERIES = {"GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS"}

    def test_fred_indicators_has_rows(self, db_session):
        """fred_indicators must have at least one row."""
        count = db_session.execute(
            select(func.count()).select_from(fred_indicators)
        ).scalar()
        assert count > 0, (
            "fred_indicators is empty — run POST /ingest/fred/indicators to populate it"
        )

    def test_fred_all_series_present(self, db_session):
        """GDP, CPIAUCSL, UNRATE, and FEDFUNDS must all have records."""
        series_rows = db_session.execute(
            select(fred_indicators.c.series_id).distinct()
        ).fetchall()
        present_series = {r[0] for r in series_rows}
        missing = self._EXPECTED_SERIES - present_series
        assert not missing, (
            f"fred_indicators is missing these required series: {missing}. "
            f"Present series: {present_series}"
        )

    def test_fred_data_as_of_spans_years(self, db_session):
        """
        fred_indicators.data_as_of must span years of observation periods.

        FRED data is historical — a backfill of GDP/CPI/etc goes back to the 1940s.
        Even with a 10-year backfill window, data_as_of should span at least 5 years.
        """
        min_date = db_session.execute(
            select(func.min(fred_indicators.c.data_as_of))
        ).scalar()
        max_date = db_session.execute(
            select(func.max(fred_indicators.c.data_as_of))
        ).scalar()
        assert min_date is not None, "fred_indicators has NULL min(data_as_of)"
        assert max_date is not None, "fred_indicators has NULL max(data_as_of)"

        # Span should be at least 5 years
        span_days = (max_date - min_date).days
        assert span_days >= 5 * 365, (
            f"fred_indicators data_as_of spans only {span_days} days "
            f"(from {min_date} to {max_date}). "
            "Expected at least 5 years of FRED observation periods. "
            "This suggests data_as_of was set to NOW() instead of the FRED observation date."
        )

    def test_fred_data_as_of_not_clustered_on_today(self, db_session):
        """
        Verify fred_indicators.data_as_of is NOT clustered near today's date.

        The most common anti-pattern is setting data_as_of = now() for all FRED rows.
        If >90% of rows have data_as_of within 7 days of today, that's a bug.
        """
        total = db_session.execute(
            select(func.count()).select_from(fred_indicators)
        ).scalar()
        assert total > 0, "fred_indicators is empty"

        seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        rows_near_today = db_session.execute(
            select(func.count()).select_from(fred_indicators).where(
                fred_indicators.c.data_as_of >= seven_days_ago
            )
        ).scalar()

        # Should be a small fraction of total (recent observations, not all)
        pct_near_today = rows_near_today / total if total > 0 else 1.0
        assert pct_near_today < 0.1, (
            f"{pct_near_today:.1%} of fred_indicators rows have data_as_of within 7 days of today "
            f"({rows_near_today}/{total} rows). "
            "This strongly suggests data_as_of is being set to NOW() instead of the FRED observation date."
        )

    def test_fred_frequency_correct(self, db_session):
        """frequency column should match expected values per series."""
        expected_frequencies = {
            "GDP": "quarterly",
            "CPIAUCSL": "monthly",
            "UNRATE": "monthly",
            "FEDFUNDS": "monthly",
        }
        for series_id, expected_freq in expected_frequencies.items():
            rows = db_session.execute(
                select(fred_indicators.c.frequency).where(
                    fred_indicators.c.series_id == series_id
                ).distinct()
            ).fetchall()
            if not rows:
                continue  # Series not present — tested separately
            freqs = {r[0] for r in rows}
            assert expected_freq in freqs, (
                f"fred_indicators series_id={series_id} has frequency={freqs}, "
                f"expected '{expected_freq}'"
            )
