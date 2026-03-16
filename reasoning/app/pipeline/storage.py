"""
reasoning/app/pipeline/storage.py — PostgreSQL report storage.
Phase 7 | Plan 05 | Requirement: REPT-05

Implements:
    write_report() — SQLAlchemy Core INSERT into the reports table.
                     Reflects the table schema at call time; returns the generated report_id.

Design decisions (locked):
- Uses SQLAlchemy Core (Table reflection + insert()) for database independence.
- report_json is stored as a plain dict (already a dict from ReportOutput.report_json).
- pipeline_duration_ms is Optional — may be None when timing is not captured.
- generated_at is set to datetime.now(timezone.utc) in Python (not DB DEFAULT).
- conn.commit() is called explicitly after execute() — not auto-commit mode.
- Returns int report_id via result.scalar_one() from RETURNING clause.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Table, MetaData, insert

from reasoning.app.nodes.state import ReportOutput


def write_report(
    db_engine,
    asset_id: str,
    language: str,
    report_output: ReportOutput,
    pipeline_duration_ms: Optional[int] = None,
) -> int:
    """
    Insert a single report row into the PostgreSQL reports table.

    Args:
        db_engine:            SQLAlchemy Engine connected to PostgreSQL.
        asset_id:             Asset ticker symbol (e.g. "VHM", "GOLD").
        language:             Report language code — "vi" or "en".
        report_output:        ReportOutput Pydantic model from compose_report_node.
        pipeline_duration_ms: Optional pipeline execution duration in milliseconds.

    Returns:
        int: The generated report_id (BIGSERIAL primary key) of the inserted row.

    Notes:
        - report_json is stored as a plain dict (JSONB column).
        - generated_at is set explicitly to UTC now (not relying on DB DEFAULT).
        - conn.commit() is called explicitly to commit the transaction.
    """
    reports_table = Table("reports", MetaData(), autoload_with=db_engine)

    values = {
        "asset_id": asset_id,
        "language": language,
        "report_json": report_output.report_json,
        "report_markdown": report_output.report_markdown,
        "data_as_of": report_output.data_as_of,
        "model_version": report_output.model_version,
        "pipeline_duration_ms": pipeline_duration_ms,
        "generated_at": datetime.now(timezone.utc),
    }

    stmt = insert(reports_table).values(**values).returning(reports_table.c.report_id)

    with db_engine.connect() as conn:
        result = conn.execute(stmt)
        conn.commit()
        return result.scalar_one()
