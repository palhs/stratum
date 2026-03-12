"""
reasoning/app/retrieval/freshness.py — Shared freshness check logic.
Phase 5 | Plan 01 | Requirement: RETR-04

check_freshness() validates whether source data is within an acceptable staleness
threshold. Returns a list of warning strings — empty list = fresh, non-empty = stale.

Design decisions (locked):
- Never raises exceptions — always returns result + warnings list
- Warnings state facts only: source name, staleness duration, threshold (no action hints)
- Handles timezone-naive datetimes by attaching UTC (prevents comparison errors)
- now_override parameter enables deterministic testing without mocking
"""

from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Freshness threshold constants (days)
# ---------------------------------------------------------------------------

FRESHNESS_THRESHOLDS: dict[str, int] = {
    "fred_indicators": 10,        # Weekly FRED updates
    "stock_fundamentals": 120,    # Quarterly reporting
    "structure_markers": 10,      # Weekly computation
    "gold_price": 10,             # Weekly updates
    "gold_etf_ohlcv": 10,         # Weekly updates
    "qdrant_macro_docs": 45,      # Monthly policy docs
    "qdrant_earnings_docs": 120,  # Quarterly earnings
}


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def check_freshness(
    data_as_of: datetime,
    threshold_days: int,
    source_name: str,
    now_override: Optional[datetime] = None,
) -> list[str]:
    """
    Check if source data is fresh relative to the threshold.

    Args:
        data_as_of:      The timestamp of the most recent data point.
        threshold_days:  Maximum acceptable age in days.
        source_name:     Human-readable source identifier for warning messages.
        now_override:    Override current time for deterministic testing. If None,
                         uses datetime.now(UTC).

    Returns:
        Empty list if data is fresh (age <= threshold_days).
        List with one warning string if data is stale (age > threshold_days).
        Warning format: "STALE DATA: {source_name} data_as_of={date} is {age} days old
        (threshold: {threshold} days)"
    """
    # Determine "now"
    now: datetime = now_override if now_override is not None else datetime.now(timezone.utc)

    # Ensure now is timezone-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Ensure data_as_of is timezone-aware (Pitfall 5: naive datetimes)
    if data_as_of.tzinfo is None:
        data_as_of = data_as_of.replace(tzinfo=timezone.utc)

    age_days = (now - data_as_of).days

    if age_days <= threshold_days:
        return []

    warning = (
        f"STALE DATA: {source_name} data_as_of={data_as_of.date()} "
        f"is {age_days} days old (threshold: {threshold_days} days)"
    )
    return [warning]
