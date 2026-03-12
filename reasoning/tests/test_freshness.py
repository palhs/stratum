"""
reasoning/tests/test_freshness.py — Unit tests for check_freshness().
Phase 5 | Plan 01 | Requirement: RETR-04

Tests freshness logic without any live Docker service dependency.
All tests use now_override for deterministic, timezone-safe assertions.
"""

from datetime import datetime, timedelta, timezone

import pytest

from reasoning.app.retrieval.freshness import check_freshness, FRESHNESS_THRESHOLDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
NOW_FIXED = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fresh data tests
# ---------------------------------------------------------------------------


def test_fresh_data_returns_empty_warnings():
    """Data within threshold returns empty warnings list."""
    data_as_of = NOW_FIXED - timedelta(days=5)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert warnings == []


def test_data_exactly_at_threshold_is_fresh():
    """Data exactly at threshold age (equal) is considered fresh."""
    data_as_of = NOW_FIXED - timedelta(days=10)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="gold_price",
        now_override=NOW_FIXED,
    )
    assert warnings == []


def test_very_recent_data_is_fresh():
    """Data from yesterday is always fresh."""
    data_as_of = NOW_FIXED - timedelta(days=1)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="structure_markers",
        now_override=NOW_FIXED,
    )
    assert warnings == []


# ---------------------------------------------------------------------------
# Stale data tests
# ---------------------------------------------------------------------------


def test_stale_data_returns_warning():
    """Data beyond threshold returns a non-empty warnings list."""
    data_as_of = NOW_FIXED - timedelta(days=15)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert len(warnings) == 1


def test_stale_warning_contains_source_name():
    """Stale warning includes the source name."""
    data_as_of = NOW_FIXED - timedelta(days=20)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert "fred_indicators" in warnings[0]


def test_stale_warning_contains_stale_data_prefix():
    """Stale warning starts with 'STALE DATA:' prefix."""
    data_as_of = NOW_FIXED - timedelta(days=20)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert warnings[0].startswith("STALE DATA:")


def test_stale_warning_contains_threshold():
    """Stale warning includes the threshold value."""
    data_as_of = NOW_FIXED - timedelta(days=20)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert "10 days" in warnings[0]


def test_stale_warning_contains_age():
    """Stale warning includes the actual age in days."""
    data_as_of = NOW_FIXED - timedelta(days=20)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert "20 days" in warnings[0]


def test_stale_warning_contains_data_as_of_date():
    """Stale warning includes the data_as_of date."""
    data_as_of = NOW_FIXED - timedelta(days=20)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="fred_indicators",
        now_override=NOW_FIXED,
    )
    assert str(data_as_of.date()) in warnings[0]


# ---------------------------------------------------------------------------
# Timezone handling tests
# ---------------------------------------------------------------------------


def test_timezone_naive_data_as_of_handled():
    """Timezone-naive data_as_of is handled correctly (Pitfall 5)."""
    # Naive datetime — should not raise, should compare as UTC
    data_as_of_naive = datetime(2025, 12, 1, 0, 0, 0)  # no tzinfo
    warnings = check_freshness(
        data_as_of=data_as_of_naive,
        threshold_days=10,
        source_name="gold_price",
        now_override=NOW_FIXED,
    )
    # 45 days ago from NOW_FIXED → stale
    assert len(warnings) == 1


def test_timezone_aware_data_as_of_handled():
    """Timezone-aware data_as_of works correctly."""
    data_as_of = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="gold_price",
        now_override=NOW_FIXED,
    )
    # 5 days old, threshold 10 → fresh
    assert warnings == []


def test_timezone_naive_now_override_handled():
    """Timezone-naive now_override is handled correctly."""
    now_naive = datetime(2026, 1, 15, 12, 0, 0)  # no tzinfo
    data_as_of = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
    # Should not raise TypeError
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="gold_price",
        now_override=now_naive,
    )
    assert warnings == []


# ---------------------------------------------------------------------------
# now_override tests
# ---------------------------------------------------------------------------


def test_now_override_makes_fresh_data_appear_stale():
    """now_override far in the future makes current data appear stale."""
    data_as_of = datetime.now(tz=UTC)  # real current time (fresh)
    future_now = datetime.now(tz=UTC) + timedelta(days=200)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="qdrant_macro_docs",
        now_override=future_now,
    )
    # 200 days old with 10-day threshold → stale
    assert len(warnings) == 1
    assert "STALE DATA:" in warnings[0]


def test_now_override_none_uses_real_time():
    """When now_override is None, real current time is used (no error)."""
    data_as_of = datetime.now(tz=UTC)
    # Should not raise, and fresh data should be fresh right now
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=365,
        source_name="stock_fundamentals",
        now_override=None,
    )
    assert warnings == []


# ---------------------------------------------------------------------------
# FRESHNESS_THRESHOLDS constants tests
# ---------------------------------------------------------------------------


def test_freshness_thresholds_contains_all_sources():
    """All 7 expected source keys exist in FRESHNESS_THRESHOLDS."""
    expected_sources = [
        "fred_indicators",
        "stock_fundamentals",
        "structure_markers",
        "gold_price",
        "gold_etf_ohlcv",
        "qdrant_macro_docs",
        "qdrant_earnings_docs",
    ]
    for source in expected_sources:
        assert source in FRESHNESS_THRESHOLDS, f"Missing threshold for: {source}"


def test_freshness_thresholds_values_are_positive():
    """All threshold values are positive integers."""
    for source, days in FRESHNESS_THRESHOLDS.items():
        assert isinstance(days, int), f"{source} threshold is not int"
        assert days > 0, f"{source} threshold is not positive"


def test_fred_indicators_threshold():
    """fred_indicators threshold is 10 days (weekly data)."""
    assert FRESHNESS_THRESHOLDS["fred_indicators"] == 10


def test_stock_fundamentals_threshold():
    """stock_fundamentals threshold is 120 days (quarterly data)."""
    assert FRESHNESS_THRESHOLDS["stock_fundamentals"] == 120


def test_qdrant_macro_docs_threshold():
    """qdrant_macro_docs threshold is 45 days (monthly policy docs)."""
    assert FRESHNESS_THRESHOLDS["qdrant_macro_docs"] == 45


def test_qdrant_earnings_docs_threshold():
    """qdrant_earnings_docs threshold is 120 days (quarterly earnings)."""
    assert FRESHNESS_THRESHOLDS["qdrant_earnings_docs"] == 120


# ---------------------------------------------------------------------------
# Edge case: just-past threshold
# ---------------------------------------------------------------------------


def test_one_day_past_threshold_is_stale():
    """Data one day past threshold is stale."""
    data_as_of = NOW_FIXED - timedelta(days=11)
    warnings = check_freshness(
        data_as_of=data_as_of,
        threshold_days=10,
        source_name="structure_markers",
        now_override=NOW_FIXED,
    )
    assert len(warnings) == 1
