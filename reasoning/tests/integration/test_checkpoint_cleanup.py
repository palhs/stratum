"""Integration tests for checkpoint cleanup script.

Phase 9 | Plan 03 | Requirement: SRVC-08

Unit tests (no Docker required) use unittest.mock to verify SQL execution order,
dry-run behavior, early exit on zero expired rows, and init script DDL.

Integration tests (marked @pytest.mark.integration) require a live Docker
PostgreSQL connection.
"""

import importlib.util
import sys
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cleanup_module():
    """Load cleanup-checkpoints.py as a Python module."""
    spec = importlib.util.spec_from_file_location(
        "cleanup_checkpoints",
        "scripts/cleanup-checkpoints.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mock_conn_returning_count(count: int) -> MagicMock:
    """Return a mock psycopg connection where COUNT query returns `count`.

    The cleanup script uses psycopg.connect() as a context manager, so we
    need to wire __enter__ to return the same mock used inside the `with` block.
    """
    mock_conn = MagicMock()
    # Make context manager return mock_conn itself so conn.execute is trackable
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_result = MagicMock()
    mock_result.fetchone.return_value = (count,)
    mock_rowcount = MagicMock()
    mock_rowcount.rowcount = 0

    # execute() returns mock_result for the first call (COUNT), then
    # mock_rowcount for subsequent DELETE calls
    mock_conn.execute.side_effect = (
        [mock_result] + [mock_rowcount] * 3
    )
    return mock_conn


# ---------------------------------------------------------------------------
# Unit tests — no Docker required
# ---------------------------------------------------------------------------


def test_cleanup_deletes_in_correct_order():
    """Verify DELETE order: checkpoint_writes → checkpoint_blobs → checkpoints."""
    mock_conn = _mock_conn_returning_count(3)

    with patch("psycopg.connect", return_value=mock_conn):
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "CHECKPOINT_TTL_DAYS": "7",
            },
        ):
            with patch("sys.argv", ["cleanup-checkpoints.py"]):
                mod = _load_cleanup_module()
                mod.main()

    execute_calls = mock_conn.execute.call_args_list
    # Collect SQL strings from positional args
    sql_calls = [c[0][0].strip() for c in execute_calls if c[0]]
    delete_sqls = [s for s in sql_calls if s.upper().startswith("DELETE")]

    assert len(delete_sqls) == 3, f"Expected 3 DELETE calls, got {len(delete_sqls)}"
    assert "checkpoint_writes" in delete_sqls[0], (
        f"First DELETE should target checkpoint_writes, got: {delete_sqls[0][:60]}"
    )
    assert "checkpoint_blobs" in delete_sqls[1], (
        f"Second DELETE should target checkpoint_blobs, got: {delete_sqls[1][:60]}"
    )
    assert "DELETE FROM langgraph.checkpoints" in delete_sqls[2], (
        f"Third DELETE should target langgraph.checkpoints, got: {delete_sqls[2][:60]}"
    )


def test_cleanup_dry_run_no_deletes(capsys):
    """Verify --dry-run does not execute DELETE statements."""
    mock_conn = _mock_conn_returning_count(5)

    with patch("psycopg.connect", return_value=mock_conn):
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "CHECKPOINT_TTL_DAYS": "7",
            },
        ):
            with patch("sys.argv", ["cleanup-checkpoints.py", "--dry-run"]):
                mod = _load_cleanup_module()
                mod.main()

    execute_calls = mock_conn.execute.call_args_list
    sql_calls = [c[0][0].strip() for c in execute_calls if c[0]]
    delete_sqls = [s for s in sql_calls if s.upper().startswith("DELETE")]

    assert len(delete_sqls) == 0, (
        f"--dry-run should not execute any DELETE statements, got {delete_sqls}"
    )

    captured = capsys.readouterr()
    assert "dry run" in captured.out.lower() or "dry-run" in captured.out.lower(), (
        "Dry run output should mention dry run mode"
    )


def test_cleanup_no_expired_exits_early():
    """Verify zero expired count results in early exit without any DELETE."""
    mock_conn = _mock_conn_returning_count(0)

    with patch("psycopg.connect", return_value=mock_conn):
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "CHECKPOINT_TTL_DAYS": "7",
            },
        ):
            with patch("sys.argv", ["cleanup-checkpoints.py"]):
                mod = _load_cleanup_module()
                mod.main()

    execute_calls = mock_conn.execute.call_args_list
    sql_calls = [c[0][0].strip() for c in execute_calls if c[0]]
    delete_sqls = [s for s in sql_calls if s.upper().startswith("DELETE")]

    assert len(delete_sqls) == 0, (
        "When no expired rows exist, no DELETE statements should be executed"
    )


def test_init_script_adds_created_at():
    """Verify init script DDL includes ALTER TABLE for created_at column."""
    with open("scripts/init-langgraph-schema.py") as f:
        source = f.read()

    assert "created_at" in source, "init script must reference created_at column"
    assert "ADD COLUMN IF NOT EXISTS" in source, (
        "init script must use ADD COLUMN IF NOT EXISTS for idempotency"
    )
    assert "TIMESTAMPTZ" in source, "created_at column must be TIMESTAMPTZ type"
    assert "DEFAULT NOW()" in source, "created_at column must have DEFAULT NOW()"


def test_cleanup_script_parses_help():
    """Verify cleanup script can be invoked with --help without error."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/cleanup-checkpoints.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"--help exited with {result.returncode}: {result.stderr}"
    assert "--dry-run" in result.stdout, "--help output must mention --dry-run"


def test_cleanup_script_valid_syntax():
    """Verify cleanup script has valid Python syntax."""
    import ast
    with open("scripts/cleanup-checkpoints.py") as f:
        source = f.read()
    # Should not raise SyntaxError
    tree = ast.parse(source)
    assert tree is not None
