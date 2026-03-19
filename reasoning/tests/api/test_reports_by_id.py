"""
Tests for GET /reports/by-report-id/{report_id} endpoint.

Tests are isolated — no real DB connections.
_get_report_content_by_id is patched to return sample data; require_auth is
overridden at the app level to bypass JWT validation for endpoint logic tests.

Scenarios:
  - Valid report_id returns 200 with full ReportContentResponse shape
  - Non-existent report_id returns 404
  - No Authorization header returns 401 (auth not bypassed for that test)

Phase 14 | Plan 01 | Requirements: RVEW-01, RVEW-04, RHST-03
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.auth import require_auth
from reasoning.app.routers import reports


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROUTER_PATH = "reasoning.app.routers.reports"

_SAMPLE_CONTENT = {
    "report_id": 42,
    "generated_at": "2026-03-15T10:00:00",
    "tier": "Favorable",
    "verdict": "Strong entry signal with macro tailwinds",
    "macro_assessment": "Macro regime is supportive",
    "valuation_assessment": "Trading at attractive discount to intrinsic value",
    "structure_assessment": "Price structure shows accumulation pattern",
    "report_markdown_vi": "# Báo cáo VHM\n...",
    "report_markdown_en": "# VHM Report\n...",
}


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
    call GET /reports/by-report-id/{report_id} without providing a real JWT token.
    """
    app = FastAPI()
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.state = _make_app_state()
    # Override auth dependency — these tests focus on endpoint logic, not JWT validation
    app.dependency_overrides[require_auth] = _mock_require_auth
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GET /reports/by-report-id/{report_id} — success
# ---------------------------------------------------------------------------


def test_get_report_content_returns_200(client):
    """GET /reports/by-report-id/42 returns 200 with full ReportContentResponse shape."""
    with patch(
        f"{ROUTER_PATH}._get_report_content_by_id",
        return_value=_SAMPLE_CONTENT,
    ):
        response = client.get("/reports/by-report-id/42")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_id"] == 42
    assert body["generated_at"] == "2026-03-15T10:00:00"
    assert body["tier"] == "Favorable"
    assert body["verdict"] == "Strong entry signal with macro tailwinds"
    assert body["macro_assessment"] == "Macro regime is supportive"
    assert body["valuation_assessment"] == "Trading at attractive discount to intrinsic value"
    assert body["structure_assessment"] == "Price structure shows accumulation pattern"
    assert body["report_markdown_vi"] == "# Báo cáo VHM\n..."
    assert body["report_markdown_en"] == "# VHM Report\n..."


def test_get_report_content_nullable_markdown(client):
    """GET /reports/by-report-id/{report_id} handles None markdown fields."""
    content_no_md = {**_SAMPLE_CONTENT, "report_markdown_vi": None, "report_markdown_en": None}
    with patch(
        f"{ROUTER_PATH}._get_report_content_by_id",
        return_value=content_no_md,
    ):
        response = client.get("/reports/by-report-id/42")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_markdown_vi"] is None
    assert body["report_markdown_en"] is None


# ---------------------------------------------------------------------------
# GET /reports/by-report-id/{report_id} — 404
# ---------------------------------------------------------------------------


def test_get_report_content_not_found(client):
    """GET /reports/by-report-id/9999 returns 404 when report_id does not exist."""
    with patch(
        f"{ROUTER_PATH}._get_report_content_by_id",
        return_value=None,
    ):
        response = client.get("/reports/by-report-id/9999")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "9999" in body["detail"]


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


def test_get_report_content_requires_auth():
    """GET /reports/by-report-id/{report_id} without auth returns 401.

    Uses a separate app without the dependency override so require_auth runs.
    """
    app = FastAPI()
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.state = _make_app_state()
    # No dependency_overrides — auth will run normally

    tc = TestClient(app, raise_server_exceptions=False)
    response = tc.get("/reports/by-report-id/42")
    assert response.status_code == 401
