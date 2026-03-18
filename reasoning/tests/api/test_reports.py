"""
Tests for POST /reports/generate and GET /reports/{job_id} endpoints.

Uses a minimal test app with mocked DB helpers and pipeline to avoid
real database/service connections.

SRVC-01: POST /reports/generate returns 202 with job_id and status=pending
SRVC-02: GET /reports/{job_id} returns report or status based on job state

Note: POST /reports/generate now requires JWT auth (Phase 10-02).
These tests override the require_auth dependency so they focus on endpoint logic,
not JWT validation (which is tested separately in test_auth.py).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.auth import require_auth
from reasoning.app.routers import reports


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app_state():
    """Build a mock app.state with all required attributes."""
    state = MagicMock()
    state.db_engine = MagicMock()
    state.neo4j_driver = MagicMock()
    state.qdrant_client = MagicMock()
    state.db_uri = "postgresql://user:pass@localhost/stratum"
    state.job_queues = {}
    return state


async def _mock_require_auth():
    """Dummy auth dependency — returns a fake payload without JWT validation."""
    return {"sub": "test-user", "aud": "authenticated"}


@pytest.fixture(scope="module")
def test_app():
    """Minimal FastAPI app with reports router and mocked app.state.

    require_auth is overridden at the app level so endpoint logic tests can
    call POST /reports/generate without providing a real JWT token.
    """
    app = FastAPI()
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.state = _make_app_state()
    # Override auth dependency — these tests are for endpoint logic, not JWT validation
    app.dependency_overrides[require_auth] = _mock_require_auth
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test helpers — common mock patches
# ---------------------------------------------------------------------------

ROUTER_PATH = "reasoning.app.routers.reports"


# ---------------------------------------------------------------------------
# POST /reports/generate
# ---------------------------------------------------------------------------


def test_generate_returns_202(test_app, client):
    """POST /reports/generate returns 202 with job_id and status=pending."""
    # Reset job_queues each test to prevent inter-test contamination
    test_app.state.job_queues = {}

    with (
        patch(f"{ROUTER_PATH}._find_active_job", return_value=None),
        patch(f"{ROUTER_PATH}._create_job", return_value=42),
        patch(f"{ROUTER_PATH}._run_pipeline", new=AsyncMock()),
        patch(f"{ROUTER_PATH}._update_job_status"),
    ):
        response = client.post(
            "/reports/generate",
            json={"ticker": "VHM", "asset_type": "equity"},
        )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["job_id"] == 42
    assert body["status"] == "pending"


def test_generate_409_conflict(test_app, client):
    """POST /reports/generate returns 409 when pending/running job exists."""
    test_app.state.job_queues = {}

    with (
        patch(f"{ROUTER_PATH}._find_active_job", return_value=7),
        patch(f"{ROUTER_PATH}._create_job", return_value=99),
    ):
        response = client.post(
            "/reports/generate",
            json={"ticker": "VHM", "asset_type": "equity"},
        )

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "7" in body["detail"] or "VHM:equity" in body["detail"]


def test_generate_retry_after_failed(test_app, client):
    """POST /reports/generate accepts re-submission when prior job was failed.

    When no active (pending/running) job is found for the same asset_id,
    the endpoint should allow a new submission — even if prior failed jobs exist.
    _find_active_job returns None for failed jobs (they are not active).
    """
    test_app.state.job_queues = {}

    with (
        patch(f"{ROUTER_PATH}._find_active_job", return_value=None),
        patch(f"{ROUTER_PATH}._create_job", return_value=10),
        patch(f"{ROUTER_PATH}._run_pipeline", new=AsyncMock()),
        patch(f"{ROUTER_PATH}._update_job_status"),
    ):
        response = client.post(
            "/reports/generate",
            json={"ticker": "VHM", "asset_type": "equity"},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /reports/{job_id}
# ---------------------------------------------------------------------------


def test_get_report_completed(test_app, client):
    """GET /reports/{job_id} returns 200 with report data when job is completed."""
    job_row = {
        "job_id": 5,
        "status": "completed",
        "asset_id": "VHM:equity",
        "report_id": 1,
        "error": None,
    }
    report_row = {
        "report_json": {"macro_regime": "tight", "entry_quality": "Attractive"},
        "report_markdown": "# VHM Report\n...",
    }

    with (
        patch(f"{ROUTER_PATH}._get_job", return_value=job_row),
        patch(f"{ROUTER_PATH}._get_report_by_job", return_value=report_row),
    ):
        response = client.get("/reports/5")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == 5
    assert body["status"] == "completed"
    assert body["report_json"] == {"macro_regime": "tight", "entry_quality": "Attractive"}
    assert body["report_markdown"] == "# VHM Report\n..."


def test_get_report_pending(test_app, client):
    """GET /reports/{job_id} returns 202 with status when job is pending/running."""
    job_row = {
        "job_id": 3,
        "status": "pending",
        "asset_id": "VHM:equity",
        "report_id": None,
        "error": None,
    }

    with patch(f"{ROUTER_PATH}._get_job", return_value=job_row):
        response = client.get("/reports/3")

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == 3
    assert body["status"] == "pending"


def test_get_report_running(test_app, client):
    """GET /reports/{job_id} returns 202 with status when job is running."""
    job_row = {
        "job_id": 4,
        "status": "running",
        "asset_id": "VHM:equity",
        "report_id": None,
        "error": None,
    }

    with patch(f"{ROUTER_PATH}._get_job", return_value=job_row):
        response = client.get("/reports/4")

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == 4
    assert body["status"] == "running"


def test_get_report_not_found(test_app, client):
    """GET /reports/{job_id} returns 404 when job_id does not exist."""
    with patch(f"{ROUTER_PATH}._get_job", return_value=None):
        response = client.get("/reports/9999")

    assert response.status_code == 404


def test_background_task_calls_pipeline(test_app, client):
    """Background task calls generate_report() and updates job status to completed.

    TestClient executes BackgroundTasks synchronously, so after the POST
    the background task should have run and _update_job_status called with 'completed'.
    """
    test_app.state.job_queues = {}

    mock_generate = AsyncMock(return_value=(1, 2))
    mock_update = MagicMock()

    with (
        patch(f"{ROUTER_PATH}._find_active_job", return_value=None),
        patch(f"{ROUTER_PATH}._create_job", return_value=20),
        patch(
            f"{ROUTER_PATH}.generate_report",
            new=mock_generate,
        ),
        patch(f"{ROUTER_PATH}._update_job_status", new=mock_update),
    ):
        response = client.post(
            "/reports/generate",
            json={"ticker": "VHM", "asset_type": "equity"},
        )

    assert response.status_code == 202

    # Verify the pipeline was called with correct arguments
    mock_generate.assert_awaited_once()
    call_kwargs = mock_generate.call_args.kwargs
    assert call_kwargs["ticker"] == "VHM"
    assert call_kwargs["asset_type"] == "equity"

    # Verify job transitioned through running → completed
    # _update_job_status(db_engine, job_id, status) — status is the 3rd positional arg (index 2)
    status_calls = [call.args[2] for call in mock_update.call_args_list]
    assert "running" in status_calls
    assert "completed" in status_calls
