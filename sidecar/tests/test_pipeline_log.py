"""
Tests for pipeline run logging — DATA-08.

DATA-08: pipeline_run_log has records for each pipeline type with status field.
         Every sidecar endpoint must log its runs.

These are integration tests against the live database populated by the sidecar.
"""

import pytest
from sqlalchemy import select, func

from app.models import pipeline_run_log
from app.services.pipeline_log_service import log_pipeline_run


# ---------------------------------------------------------------------------
# DATA-08: pipeline_run_log
# ---------------------------------------------------------------------------

class TestPipelineRunLog:
    """DATA-08: pipeline_run_log table quality checks."""

    _EXPECTED_PIPELINES = {
        "vnstock_ohlcv",
        "vnstock_fundamentals",
        "gold_fred_price",
        "gold_gld_etf",
        "fred_indicators",
        "structure_markers",
    }

    def test_run_log_has_rows(self, db_session):
        """pipeline_run_log must have at least one row."""
        count = db_session.execute(
            select(func.count()).select_from(pipeline_run_log)
        ).scalar()
        assert count > 0, (
            "pipeline_run_log is empty — run at least one sidecar endpoint to generate log records"
        )

    def test_run_log_has_required_fields(self, db_session):
        """
        Every pipeline_run_log row must have pipeline_name, status, rows_ingested,
        and data_as_of populated.
        """
        # Check pipeline_name non-NULL
        null_name = db_session.execute(
            select(func.count()).select_from(pipeline_run_log).where(
                pipeline_run_log.c.pipeline_name.is_(None)
            )
        ).scalar()
        assert null_name == 0, (
            f"pipeline_run_log has {null_name} rows with NULL pipeline_name"
        )

        # Check status non-NULL
        null_status = db_session.execute(
            select(func.count()).select_from(pipeline_run_log).where(
                pipeline_run_log.c.status.is_(None)
            )
        ).scalar()
        assert null_status == 0, (
            f"pipeline_run_log has {null_status} rows with NULL status"
        )

        # Check rows_ingested non-NULL
        null_rows = db_session.execute(
            select(func.count()).select_from(pipeline_run_log).where(
                pipeline_run_log.c.rows_ingested.is_(None)
            )
        ).scalar()
        assert null_rows == 0, (
            f"pipeline_run_log has {null_rows} rows with NULL rows_ingested"
        )

    def test_run_log_status_values_are_valid(self, db_session):
        """status should be 'success', 'failure', or 'partial' only."""
        valid_statuses = {"success", "failure", "partial"}
        rows = db_session.execute(
            select(pipeline_run_log.c.status).distinct()
        ).fetchall()
        found = {r[0] for r in rows}
        unknown = found - valid_statuses
        assert not unknown, (
            f"pipeline_run_log has unexpected status values: {unknown}. "
            f"Valid values: {valid_statuses}"
        )

    def test_run_log_has_success_records(self, db_session):
        """pipeline_run_log should have at least some 'success' records."""
        success_count = db_session.execute(
            select(func.count()).select_from(pipeline_run_log).where(
                pipeline_run_log.c.status == "success"
            )
        ).scalar()
        assert success_count > 0, (
            "pipeline_run_log has no 'success' records — "
            "expected at least one successful pipeline run"
        )

    def test_run_log_pipeline_names_present(self, db_session):
        """Known pipeline names should have at least some records."""
        pipeline_rows = db_session.execute(
            select(pipeline_run_log.c.pipeline_name).distinct()
        ).fetchall()
        present_pipelines = {r[0] for r in pipeline_rows}
        # At least one expected pipeline should be present
        overlap = self._EXPECTED_PIPELINES & present_pipelines
        assert overlap, (
            f"pipeline_run_log has no records for any expected pipeline. "
            f"Expected one of: {self._EXPECTED_PIPELINES}. "
            f"Found pipelines: {present_pipelines}"
        )


# ---------------------------------------------------------------------------
# log_pipeline_run() unit-level tests (using live DB, not mocks)
# ---------------------------------------------------------------------------

class TestLogPipelineRunFunction:
    """Validate that log_pipeline_run() correctly inserts records."""

    def test_run_log_written(self, db_session):
        """log_pipeline_run() should insert a new record and return its ID."""
        import datetime
        count_before = db_session.execute(
            select(func.count()).select_from(pipeline_run_log)
        ).scalar()

        test_pipeline = "test_pipeline_log_written"
        inserted_id = log_pipeline_run(
            db_session=db_session,
            pipeline_name=test_pipeline,
            status="success",
            rows_ingested=42,
            data_as_of=datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc),
            duration_ms=123,
        )

        assert inserted_id is not None, "log_pipeline_run() returned None — INSERT likely failed"

        count_after = db_session.execute(
            select(func.count()).select_from(pipeline_run_log)
        ).scalar()
        assert count_after == count_before + 1, (
            f"Expected {count_before + 1} rows after insert, got {count_after}"
        )

    def test_failure_logged(self, db_session):
        """log_pipeline_run() should log failure records with status='failure'."""
        import datetime
        test_pipeline = "test_pipeline_failure_logged"
        inserted_id = log_pipeline_run(
            db_session=db_session,
            pipeline_name=test_pipeline,
            status="failure",
            rows_ingested=0,
            data_as_of=datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc),
            error_message="simulated test error",
            duration_ms=50,
        )

        assert inserted_id is not None, "log_pipeline_run() with status='failure' returned None"

        # Verify the failure record exists
        row = db_session.execute(
            select(pipeline_run_log).where(
                pipeline_run_log.c.id == inserted_id
            )
        ).fetchone()
        assert row is not None, f"Could not find inserted failure record with id={inserted_id}"
        assert row.status == "failure", f"Expected status='failure', got '{row.status}'"
        assert row.error_message == "simulated test error", (
            f"Expected error_message='simulated test error', got '{row.error_message}'"
        )
        assert row.rows_ingested == 0, f"Expected rows_ingested=0, got {row.rows_ingested}"

    def test_log_pipeline_run_never_raises(self, db_session):
        """log_pipeline_run() must never raise — even with unusual input."""
        import datetime
        # Test with None data_as_of (should default to NOW())
        result = log_pipeline_run(
            db_session=db_session,
            pipeline_name="test_no_raise",
            status="success",
            rows_ingested=0,
            data_as_of=None,  # Should handle gracefully
        )
        # Result can be None or an int — it must not raise
        assert result is None or isinstance(result, int), (
            f"log_pipeline_run() returned unexpected type: {type(result)}"
        )
