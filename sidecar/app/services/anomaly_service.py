"""
Row-count anomaly detection service for the Stratum Data Sidecar.
Phase 2 | Plan 04

Used by vnstock endpoints ONLY to detect unusual row count changes.
Anomaly detection is ALERT-ONLY — it NEVER blocks data ingestion (locked decision).

Algorithm:
  1. Query the 4 most recent successful runs for the given pipeline from pipeline_run_log.
  2. Compute the average rows_ingested from those 4 runs.
  3. If abs(new_row_count - average) / average > 0.50, return True (anomaly flagged).
  4. If fewer than 4 prior successful runs exist (or average == 0), skip check — return False.

This module NEVER raises exceptions. All errors are caught internally.
"""

import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import pipeline_run_log

logger = logging.getLogger(__name__)

# Deviation threshold: flag if new count is >50% above or below the 4-run average
_ANOMALY_THRESHOLD = 0.50

# Minimum number of prior successful runs required before checking
_MIN_HISTORY_RUNS = 4


def check_row_count_anomaly(
    db_session: Session,
    pipeline_name: str,
    new_row_count: int,
) -> bool:
    """
    Check whether new_row_count deviates >50% from the 4-run moving average.

    This function NEVER raises an exception — any failure returns False so that
    ingestion is never blocked by monitoring logic.

    Args:
        db_session:     SQLAlchemy session.
        pipeline_name:  The same pipeline_name used in log_pipeline_run().
        new_row_count:  The rows_ingested value from the current run.

    Returns:
        True  — anomaly detected (>50% deviation from 4-run average).
        False — no anomaly, insufficient history, or any internal error.
    """
    try:
        # Query the 4 most recent successful runs for this pipeline
        stmt = (
            select(pipeline_run_log.c.rows_ingested)
            .where(pipeline_run_log.c.pipeline_name == pipeline_name)
            .where(pipeline_run_log.c.status == "success")
            .order_by(pipeline_run_log.c.run_at.desc())
            .limit(_MIN_HISTORY_RUNS)
        )
        rows = db_session.execute(stmt).fetchall()

        if len(rows) < _MIN_HISTORY_RUNS:
            logger.debug(
                "anomaly_service: insufficient history for %s (%d runs, need %d) — skipping check",
                pipeline_name,
                len(rows),
                _MIN_HISTORY_RUNS,
            )
            return False

        prior_counts = [r[0] for r in rows if r[0] is not None]
        if not prior_counts:
            logger.debug(
                "anomaly_service: no non-null rows_ingested in history for %s — skipping check",
                pipeline_name,
            )
            return False

        average = sum(prior_counts) / len(prior_counts)

        if average == 0:
            logger.debug(
                "anomaly_service: average rows_ingested is 0 for %s — skipping check",
                pipeline_name,
            )
            return False

        deviation = abs(new_row_count - average) / average

        if deviation > _ANOMALY_THRESHOLD:
            logger.warning(
                "anomaly_service: ROW COUNT ANOMALY detected for %s — "
                "new=%d, 4-run avg=%.1f, deviation=%.1f%% (threshold=%.0f%%)",
                pipeline_name,
                new_row_count,
                average,
                deviation * 100,
                _ANOMALY_THRESHOLD * 100,
            )
            return True

        logger.debug(
            "anomaly_service: %s row count OK — new=%d, 4-run avg=%.1f, deviation=%.1f%%",
            pipeline_name,
            new_row_count,
            average,
            deviation * 100,
        )
        return False

    except Exception as exc:  # noqa: BLE001
        # CRITICAL: Never let monitoring logic break ingestion
        logger.warning(
            "anomaly_service: error checking row count for %s: %s — returning False",
            pipeline_name,
            exc,
        )
        return False
