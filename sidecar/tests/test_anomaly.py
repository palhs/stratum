"""
Tests for anomaly detection — DATA-09.

DATA-09: check_row_count_anomaly() returns True for >50% deviation,
         False for normal counts, False for insufficient history,
         and NEVER raises an exception.

These tests use the live database for the "real" behavior tests, and
create controlled data for edge case tests.
"""

import datetime
import uuid
import pytest
from sqlalchemy import select, func

from app.models import pipeline_run_log
from app.services.anomaly_service import check_row_count_anomaly
from app.services.pipeline_log_service import log_pipeline_run


# ---------------------------------------------------------------------------
# Helper: seed pipeline_run_log with known row counts
# ---------------------------------------------------------------------------

def _unique_pipeline(prefix: str) -> str:
    """Generate a unique pipeline name to prevent cross-run data collisions."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _seed_run_log(db_session, pipeline_name: str, row_counts: list[int]) -> None:
    """Insert test records into pipeline_run_log with given row counts."""
    base_time = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    for i, count in enumerate(row_counts):
        run_at = base_time + datetime.timedelta(days=i)
        db_session.execute(
            pipeline_run_log.insert().values(
                pipeline_name=pipeline_name,
                run_at=run_at,
                status="success",
                rows_ingested=count,
                data_as_of=run_at,
                ingested_at=run_at,
                duration_ms=100,
            )
        )
    db_session.commit()


# ---------------------------------------------------------------------------
# DATA-09: anomaly detection tests
# ---------------------------------------------------------------------------

class TestAnomalyDetection:
    """DATA-09: check_row_count_anomaly() behavior tests."""

    def test_row_count_deviation_high(self, db_session):
        """
        check_row_count_anomaly() must return True for >50% deviation.

        Seed 4 runs with row_count=100. Then check with new_row_count=200
        which is a 100% deviation (above the 50% threshold).
        """
        pipeline = _unique_pipeline("test_anomaly_high")
        _seed_run_log(db_session, pipeline, [100, 100, 100, 100])

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=200)
        assert result is True, (
            f"Expected True (anomaly) for 100% deviation from avg=100, new=200, got {result}"
        )

    def test_row_count_deviation_low(self, db_session):
        """
        check_row_count_anomaly() must return True for very low count (>50% below avg).

        Seed 4 runs with row_count=100. Then check with new_row_count=10
        which is a 90% below average deviation.
        """
        pipeline = _unique_pipeline("test_anomaly_low")
        _seed_run_log(db_session, pipeline, [100, 100, 100, 100])

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=10)
        assert result is True, (
            f"Expected True (anomaly) for 90% deviation below avg=100, new=10, got {result}"
        )

    def test_row_count_deviation_normal(self, db_session):
        """
        check_row_count_anomaly() must return False for normal counts (<=50% deviation).

        Seed 4 runs with row_count=100. Then check with new_row_count=110
        which is only a 10% deviation (below the 50% threshold).
        """
        pipeline = _unique_pipeline("test_anomaly_normal")
        _seed_run_log(db_session, pipeline, [100, 100, 100, 100])

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=110)
        assert result is False, (
            f"Expected False (normal) for 10% deviation from avg=100, new=110, got {result}"
        )

    def test_row_count_deviation_exactly_at_threshold(self, db_session):
        """
        check_row_count_anomaly() must return False for EXACTLY 50% deviation.

        The threshold check is >0.50, NOT >=0.50. Exactly 50% should not trigger.
        """
        pipeline = _unique_pipeline("test_anomaly_threshold")
        _seed_run_log(db_session, pipeline, [100, 100, 100, 100])

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=150)
        assert result is False, (
            f"Expected False for exactly 50% deviation (threshold is >50%), got {result}"
        )

    def test_row_count_insufficient_history(self, db_session):
        """
        check_row_count_anomaly() must return False when < 4 historical runs exist.

        With only 3 prior runs, the check should be skipped and return False.
        """
        pipeline = _unique_pipeline("test_anomaly_insuf")
        _seed_run_log(db_session, pipeline, [100, 100, 100])  # Only 3 runs

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=999)
        assert result is False, (
            f"Expected False for insufficient history (3 runs < 4 required), got {result}"
        )

    def test_row_count_zero_history(self, db_session):
        """check_row_count_anomaly() must return False when no history exists."""
        pipeline = "test_anomaly_zero_history_unique_xyz"
        # No seed — no records for this pipeline

        result = check_row_count_anomaly(db_session, pipeline, new_row_count=100)
        assert result is False, (
            f"Expected False for zero history, got {result}"
        )

    def test_anomaly_does_not_raise(self, db_session):
        """
        check_row_count_anomaly() must NEVER raise an exception.

        Test with various edge case inputs that might cause errors.
        """
        # Test with extreme values
        try:
            check_row_count_anomaly(db_session, "nonexistent_pipeline_xyz123", 0)
            check_row_count_anomaly(db_session, "nonexistent_pipeline_xyz123", -1)
            check_row_count_anomaly(db_session, "nonexistent_pipeline_xyz123", 10_000_000)
            check_row_count_anomaly(db_session, "", 100)
        except Exception as exc:
            pytest.fail(
                f"check_row_count_anomaly() raised an exception: {type(exc).__name__}: {exc}. "
                "The function must never raise — it should return False on any error."
            )

    def test_anomaly_returns_bool(self, db_session):
        """check_row_count_anomaly() must always return a bool."""
        result = check_row_count_anomaly(db_session, "nonexistent_pipeline_bool_check", 100)
        assert isinstance(result, bool), (
            f"check_row_count_anomaly() returned {type(result).__name__} instead of bool"
        )
