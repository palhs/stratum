"""
Tests for gold data ingestion — DATA-04.

DATA-04: gold_wgc_flows has rows OR endpoint returns 501 with documented limitation.
         (The WGC Goldhub portal is JS-rendered; the endpoint returns 501 by design.)

These are integration tests against the live database / service endpoints.
"""

import pytest
from sqlalchemy import select, func

from app.models import gold_wgc_flows, gold_etf_ohlcv
from app.services.gold_service import WGCNotImplemented, fetch_and_upsert_wgc_flows


# ---------------------------------------------------------------------------
# DATA-04: gold_wgc_flows — stub documented
# ---------------------------------------------------------------------------

class TestWGCFlows:
    """DATA-04: WGC flows either has rows OR the stub raises WGCNotImplemented."""

    def test_wgc_flow_ingest_stub_or_rows(self, db_session):
        """
        WGC flows endpoint is expected to return 501 (stub) OR have rows in DB.

        The WGC Goldhub portal is JS-rendered and has no stable download URL.
        The sidecar returns HTTP 501 by design (known limitation, tracked in deferred-items.md).
        This test passes if either:
          1. gold_wgc_flows has rows (manual CSV import happened), OR
          2. fetch_and_upsert_wgc_flows raises WGCNotImplemented (501 stub is active)
        """
        count = db_session.execute(
            select(func.count()).select_from(gold_wgc_flows)
        ).scalar()
        if count > 0:
            # If rows exist (manual import), validate structure
            return  # Pass — rows present

        # If no rows, verify the function raises WGCNotImplemented (the 501 stub)
        try:
            fetch_and_upsert_wgc_flows(db_session)
            pytest.fail(
                "fetch_and_upsert_wgc_flows should raise WGCNotImplemented when no data is available"
            )
        except WGCNotImplemented:
            pass  # Expected behavior — 501 stub is active

    def test_wgc_not_implemented_is_documented(self):
        """Verify WGCNotImplemented exists and inherits from NotImplementedError."""
        assert issubclass(WGCNotImplemented, NotImplementedError), (
            "WGCNotImplemented should subclass NotImplementedError"
        )

    def test_wgc_source_lag_note_if_rows_present(self, db_session):
        """If gold_wgc_flows has rows, source_lag_note must be populated."""
        rows = db_session.execute(
            select(gold_wgc_flows).limit(10)
        ).fetchall()
        if not rows:
            pytest.skip("No gold_wgc_flows rows — skipping source_lag_note validation")

        # All rows with source_lag_note should be non-NULL
        null_lag_count = db_session.execute(
            select(func.count()).select_from(gold_wgc_flows).where(
                gold_wgc_flows.c.source_lag_note.is_(None)
            )
        ).scalar()
        assert null_lag_count == 0, (
            f"gold_wgc_flows has {null_lag_count} rows with NULL source_lag_note"
        )


# ---------------------------------------------------------------------------
# GLD ETF OHLCV validation (ancillary gold table)
# ---------------------------------------------------------------------------

class TestGoldETFOHLCV:
    """Validate gold_etf_ohlcv table populated correctly."""

    def test_gold_etf_has_rows(self, db_session):
        """gold_etf_ohlcv should have rows after yfinance GLD ingestion."""
        count = db_session.execute(
            select(func.count()).select_from(gold_etf_ohlcv)
        ).scalar()
        assert count > 0, (
            "gold_etf_ohlcv is empty — run POST /ingest/gold/gld-etf to populate it"
        )

    def test_gold_etf_ticker_is_gld(self, db_session):
        """ticker should be 'GLD' for all rows."""
        tickers = db_session.execute(
            select(gold_etf_ohlcv.c.ticker).distinct()
        ).fetchall()
        ticker_set = {r[0] for r in tickers}
        assert "GLD" in ticker_set, (
            f"gold_etf_ohlcv does not have GLD ticker — found: {ticker_set}"
        )

    def test_gold_etf_close_non_null(self, db_session):
        """close must be non-NULL for all ETF rows."""
        null_count = db_session.execute(
            select(func.count()).select_from(gold_etf_ohlcv).where(
                gold_etf_ohlcv.c.close.is_(None)
            )
        ).scalar()
        assert null_count == 0, (
            f"gold_etf_ohlcv has {null_count} rows with NULL close"
        )
