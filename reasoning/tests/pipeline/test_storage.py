"""
reasoning/tests/pipeline/test_storage.py — TDD tests for storage.py and generate_report().
Phase 7 | Plan 05 | Requirements: REPT-05, REAS-06

Tests verify:
- write_report() inserts correct values into reports table (asset_id, language, report_json, etc.)
- write_report() returns an integer report_id
- write_report() uses plain dict (not Pydantic) for report_json
- write_report() records pipeline_duration_ms when provided
- generate_report() calls prefetch once, run_graph twice (vi then en), write_report twice
- generate_report() uses copy.deepcopy between vi and en invocations
- generate_report() returns tuple of two report IDs
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest

from reasoning.app.nodes.state import ReportOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_report_output(language: str = "en") -> ReportOutput:
    """Create a minimal valid ReportOutput for testing."""
    return ReportOutput(
        report_json={
            "entry_quality": {"tier": "Neutral", "narrative": "Test narrative"},
            "macro_regime": {"label": "Supportive", "narrative": "Macro narrative"},
            "valuation": {"label": "Fair", "narrative": "Val narrative"},
            "structure": {"label": "Constructive", "narrative": "Struct narrative"},
            "language": language,
            "data_warnings": [],
        },
        report_markdown="## Entry Quality\n\nTest narrative",
        language=language,
        data_as_of=datetime(2026, 1, 15, tzinfo=timezone.utc),
        data_warnings=[],
        model_version="gemini-2.5-pro",
        warnings=[],
    )


def _make_mock_db_engine():
    """Create a mock SQLAlchemy engine that captures INSERT calls."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()

    # The returned report_id from scalar_one()
    mock_result.scalar_one.return_value = 42

    # conn.execute() returns result
    mock_conn.execute.return_value = mock_result

    # engine.connect() returns context manager that yields conn
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    return mock_engine, mock_conn, mock_result


# ---------------------------------------------------------------------------
# write_report() importability
# ---------------------------------------------------------------------------


def test_write_report_is_importable():
    """write_report is importable from reasoning.app.pipeline.storage."""
    from reasoning.app.pipeline.storage import write_report  # noqa: F401


# ---------------------------------------------------------------------------
# write_report() return value
# ---------------------------------------------------------------------------


def test_write_report_returns_integer():
    """write_report() returns an integer report_id."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 99

    report_output = _make_report_output("en")

    # Patch Table and insert to avoid real DB schema reflection
    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        report_id = write_report(mock_engine, "VHM", "en", report_output)

    assert isinstance(report_id, int), f"write_report must return int, got {type(report_id)}"
    assert report_id == 99


# ---------------------------------------------------------------------------
# write_report() INSERT values
# ---------------------------------------------------------------------------


def test_write_report_inserts_correct_asset_id():
    """write_report() inserts the correct asset_id."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 1
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        # Capture the values dict passed to .values()
        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("asset_id") == "VHM", (
        f"write_report must insert asset_id='VHM', got: {values_dict.get('asset_id')}"
    )


def test_write_report_inserts_correct_language():
    """write_report() inserts the correct language."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 2
    report_output = _make_report_output("vi")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "GOLD", "vi", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("language") == "vi", (
        f"write_report must insert language='vi', got: {values_dict.get('language')}"
    )


def test_write_report_inserts_report_json_as_plain_dict():
    """write_report() inserts report_json as a plain dict (not Pydantic model)."""
    from reasoning.app.pipeline.storage import write_report
    from pydantic import BaseModel

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 3
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    report_json_val = values_dict.get("report_json")
    assert isinstance(report_json_val, dict), (
        f"report_json must be a plain dict, got {type(report_json_val)}"
    )
    assert not isinstance(report_json_val, BaseModel), (
        "report_json must not be a Pydantic model instance"
    )


def test_write_report_inserts_report_markdown():
    """write_report() inserts report_markdown string."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 4
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("report_markdown") == report_output.report_markdown, (
        "write_report must insert report_markdown from ReportOutput"
    )


def test_write_report_inserts_data_as_of():
    """write_report() inserts data_as_of datetime."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 5
    report_output = _make_report_output("en")
    expected_dt = datetime(2026, 1, 15, tzinfo=timezone.utc)

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("data_as_of") == expected_dt, (
        f"write_report must insert data_as_of={expected_dt}, got {values_dict.get('data_as_of')}"
    )


def test_write_report_inserts_model_version():
    """write_report() inserts model_version from ReportOutput."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 6
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("model_version") == "gemini-2.5-pro", (
        f"write_report must insert model_version='gemini-2.5-pro', got {values_dict.get('model_version')}"
    )


def test_write_report_inserts_generated_at():
    """write_report() inserts a generated_at UTC datetime."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 7
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    generated_at = values_dict.get("generated_at")
    assert isinstance(generated_at, datetime), (
        f"generated_at must be a datetime, got {type(generated_at)}"
    )
    assert generated_at.tzinfo is not None, "generated_at must be timezone-aware (UTC)"


def test_write_report_records_pipeline_duration_ms():
    """write_report() records pipeline_duration_ms when provided."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 8
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output, pipeline_duration_ms=1234)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("pipeline_duration_ms") == 1234, (
        f"write_report must pass pipeline_duration_ms=1234, got {values_dict.get('pipeline_duration_ms')}"
    )


def test_write_report_pipeline_duration_ms_none_by_default():
    """write_report() pipeline_duration_ms defaults to None when not provided."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 9
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

        values_call = mock_insert_stmt.values.call_args
        values_dict = values_call.kwargs if values_call.kwargs else values_call.args[0]

    assert values_dict.get("pipeline_duration_ms") is None, (
        f"pipeline_duration_ms must default to None, got {values_dict.get('pipeline_duration_ms')}"
    )


def test_write_report_calls_conn_commit():
    """write_report() calls conn.commit() after executing INSERT."""
    from reasoning.app.pipeline.storage import write_report

    mock_engine, mock_conn, mock_result = _make_mock_db_engine()
    mock_result.scalar_one.return_value = 10
    report_output = _make_report_output("en")

    with patch("reasoning.app.pipeline.storage.Table") as mock_table_cls, \
         patch("reasoning.app.pipeline.storage.insert") as mock_insert_fn:

        mock_table = MagicMock()
        mock_table_cls.return_value = mock_table
        mock_insert_stmt = MagicMock()
        mock_insert_fn.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.returning.return_value = mock_insert_stmt

        write_report(mock_engine, "VHM", "en", report_output)

    mock_conn.commit.assert_called_once(), "write_report must call conn.commit() after INSERT"


# ---------------------------------------------------------------------------
# generate_report() importability and signature
# ---------------------------------------------------------------------------


def test_generate_report_is_importable():
    """generate_report is importable from reasoning.app.pipeline."""
    from reasoning.app.pipeline import generate_report  # noqa: F401


def test_generate_report_in_all_exports():
    """generate_report is in __all__ of reasoning.app.pipeline."""
    import reasoning.app.pipeline as pipeline_module

    assert "generate_report" in pipeline_module.__all__, (
        "generate_report must be in reasoning.app.pipeline.__all__"
    )
    assert "prefetch" in pipeline_module.__all__
    assert "run_graph" in pipeline_module.__all__
    assert "build_graph" in pipeline_module.__all__


# ---------------------------------------------------------------------------
# generate_report() orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_report_calls_prefetch_once():
    """generate_report() calls prefetch exactly once."""
    from reasoning.app.pipeline import generate_report

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()
    mock_state = {"ticker": "VHM", "asset_type": "equity", "language": "en"}

    report_vi = _make_report_output("vi")
    report_en = _make_report_output("en")

    mock_result_vi = {"report_output": report_vi}
    mock_result_en = {"report_output": report_en}

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report") as mock_write_report:

        mock_prefetch.return_value = mock_state
        mock_run_graph.side_effect = [mock_result_vi, mock_result_en]
        mock_write_report.side_effect = [101, 102]

        await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    mock_prefetch.assert_called_once_with(
        "VHM", "equity", mock_engine, mock_neo4j, mock_qdrant
    )


@pytest.mark.asyncio
async def test_generate_report_calls_run_graph_twice():
    """generate_report() calls run_graph twice — once for 'vi', once for 'en'."""
    from reasoning.app.pipeline import generate_report

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()
    mock_state = {"ticker": "VHM", "asset_type": "equity", "language": "en"}

    report_vi = _make_report_output("vi")
    report_en = _make_report_output("en")

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report") as mock_write_report:

        mock_prefetch.return_value = mock_state
        mock_run_graph.side_effect = [{"report_output": report_vi}, {"report_output": report_en}]
        mock_write_report.side_effect = [201, 202]

        await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    assert mock_run_graph.call_count == 2, (
        f"run_graph must be called twice, got {mock_run_graph.call_count}"
    )
    # First call must be 'vi', second must be 'en'
    first_lang = mock_run_graph.call_args_list[0].args[1] if mock_run_graph.call_args_list[0].args else mock_run_graph.call_args_list[0].kwargs.get("language")
    second_lang = mock_run_graph.call_args_list[1].args[1] if mock_run_graph.call_args_list[1].args else mock_run_graph.call_args_list[1].kwargs.get("language")
    assert first_lang == "vi", f"First run_graph call must be 'vi', got '{first_lang}'"
    assert second_lang == "en", f"Second run_graph call must be 'en', got '{second_lang}'"


@pytest.mark.asyncio
async def test_generate_report_calls_write_report_twice():
    """generate_report() calls write_report twice — once for vi, once for en."""
    from reasoning.app.pipeline import generate_report

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()
    mock_state = {"ticker": "VHM", "asset_type": "equity", "language": "en"}

    report_vi = _make_report_output("vi")
    report_en = _make_report_output("en")

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report") as mock_write_report:

        mock_prefetch.return_value = mock_state
        mock_run_graph.side_effect = [{"report_output": report_vi}, {"report_output": report_en}]
        mock_write_report.side_effect = [301, 302]

        await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    assert mock_write_report.call_count == 2, (
        f"write_report must be called twice, got {mock_write_report.call_count}"
    )


@pytest.mark.asyncio
async def test_generate_report_returns_tuple_of_two_ids():
    """generate_report() returns (vi_report_id, en_report_id) as a tuple of two ints."""
    from reasoning.app.pipeline import generate_report

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()
    mock_state = {"ticker": "VHM", "asset_type": "equity", "language": "en"}

    report_vi = _make_report_output("vi")
    report_en = _make_report_output("en")

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report") as mock_write_report:

        mock_prefetch.return_value = mock_state
        mock_run_graph.side_effect = [{"report_output": report_vi}, {"report_output": report_en}]
        mock_write_report.side_effect = [401, 402]

        result = await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    assert isinstance(result, tuple), f"generate_report must return a tuple, got {type(result)}"
    assert len(result) == 2, f"generate_report must return tuple of length 2, got {len(result)}"
    vi_id, en_id = result
    assert vi_id == 401, f"First element (vi_id) must be 401, got {vi_id}"
    assert en_id == 402, f"Second element (en_id) must be 402, got {en_id}"


@pytest.mark.asyncio
async def test_generate_report_uses_deepcopy_between_vi_and_en():
    """generate_report() uses copy.deepcopy between vi and en invocations."""
    from reasoning.app.pipeline import generate_report

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()
    mock_state = {"ticker": "VHM", "asset_type": "equity", "language": "en"}

    report_vi = _make_report_output("vi")
    report_en = _make_report_output("en")

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report") as mock_write_report, \
         patch("reasoning.app.pipeline.copy") as mock_copy_module:

        mock_prefetch.return_value = mock_state
        # deepcopy returns a copy of the state
        mock_copy_module.deepcopy.return_value = dict(mock_state)
        mock_run_graph.side_effect = [{"report_output": report_vi}, {"report_output": report_en}]
        mock_write_report.side_effect = [501, 502]

        await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    assert mock_copy_module.deepcopy.call_count >= 1, (
        f"copy.deepcopy must be called at least once, got {mock_copy_module.deepcopy.call_count}"
    )
