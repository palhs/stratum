"""
Pipeline run logging service for the Stratum Data Sidecar.
Phase 2 | Plan 04

Every sidecar endpoint calls log_pipeline_run() after each run (success or failure).
This creates an auditable trail in pipeline_run_log for health monitoring and anomaly
detection history.

Schema (V1 migration):
  pipeline_run_log: id, pipeline_name, run_at, status, rows_ingested,
                    error_message, duration_ms, data_as_of, ingested_at
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import pipeline_run_log

logger = logging.getLogger(__name__)


def log_pipeline_run(
    db_session: Session,
    pipeline_name: str,
    status: str,
    rows_ingested: int,
    data_as_of,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[int]:
    """
    Insert a new record into pipeline_run_log for every pipeline run.

    This is always a simple INSERT (not upsert) — every run creates a new log record.
    Never raises: failures are logged at WARNING level and return None.

    Args:
        db_session:     SQLAlchemy session.
        pipeline_name:  Consistent identifier (e.g. "vnstock_ohlcv", "fred_indicators").
        status:         One of "success", "failure", "partial".
        rows_ingested:  Number of rows upserted (0 on failure).
        data_as_of:     The date of the data being ingested (pass-through from endpoint).
                        Accepts str (ISO date), date, datetime, or pandas Timestamp.
        error_message:  Error string on failure; None on success.
        duration_ms:    Wall-clock milliseconds for the pipeline run.

    Returns:
        The inserted record id, or None if the log INSERT itself failed.
    """
    try:
        now_utc = datetime.now(tz=timezone.utc)

        # Normalise data_as_of to a timezone-aware datetime
        if data_as_of is None:
            data_as_of_dt = now_utc
        elif isinstance(data_as_of, str):
            dt = datetime.fromisoformat(data_as_of.replace("Z", "+00:00"))
            data_as_of_dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        elif hasattr(data_as_of, "tzinfo"):
            # datetime or pandas Timestamp
            data_as_of_dt = (
                data_as_of if data_as_of.tzinfo else data_as_of.replace(tzinfo=timezone.utc)
            )
        else:
            # date object — convert to datetime at midnight UTC
            data_as_of_dt = datetime(
                data_as_of.year, data_as_of.month, data_as_of.day, tzinfo=timezone.utc
            )

        stmt = pipeline_run_log.insert().values(
            pipeline_name=pipeline_name,
            run_at=now_utc,
            status=status,
            rows_ingested=rows_ingested,
            data_as_of=data_as_of_dt,
            ingested_at=now_utc,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        result = db_session.execute(stmt)
        db_session.commit()

        inserted_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        logger.debug(
            "pipeline_run_log: recorded run id=%s pipeline=%s status=%s rows=%d duration_ms=%s",
            inserted_id,
            pipeline_name,
            status,
            rows_ingested,
            duration_ms,
        )
        return inserted_id

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pipeline_run_log: failed to record run for pipeline=%s status=%s: %s",
            pipeline_name,
            status,
            exc,
        )
        # Roll back the failed INSERT so the session stays usable
        try:
            db_session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
