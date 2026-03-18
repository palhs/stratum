"""
Unit tests for GET /reports/by-ticker/{symbol} endpoint.

Tests are isolated — no real DB connections.
_query_report_history is patched to return sample data; require_auth is patched
to bypass JWT validation for endpoint logic tests.

Scenarios:
  - Valid request returns 200 with paginated ReportHistoryResponse shape
  - Empty data for unknown symbol returns 200 with empty items array and total=0
  - No Authorization header returns 401 (auth not bypassed)
  - POST /reports/generate without auth returns 401
  - GET /health returns 200 without any Authorization header
"""
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.routers import health, reports


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROUTER_PATH = "reasoning.app.routers.reports"

# Test RSA key pair — generated once at module level
_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()

# Reusable mock signing key
_mock_signing_key = MagicMock()
_mock_signing_key.key = _TEST_PUBLIC_KEY

_SAMPLE_HISTORY = [
    {
        "report_id": 1,
        "generated_at": "2026-03-15T10:00:00",
        "tier": "Favorable",
        "verdict": "Strong entry",
    }
]


def _make_app_state():
    state = MagicMock()
    state.db_engine = MagicMock()
    state.neo4j_driver = MagicMock()
    state.qdrant_client = MagicMock()
    state.db_uri = "postgresql://user:pass@localhost/stratum"
    state.job_queues = {}
    return state


@pytest.fixture(scope="module")
def test_app():
    """Minimal FastAPI app with reports router and mocked app.state."""
    app = FastAPI()
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.state = _make_app_state()
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=False)


def _make_auth_header():
    token = jwt.encode(
        {"sub": "user-1", "aud": "authenticated", "exp": int(time.time()) + 3600},
        _TEST_PRIVATE_KEY,
        algorithm="RS256",
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /reports/by-ticker/{symbol}
# ---------------------------------------------------------------------------


def test_report_history_returns_paginated_list(client):
    """GET /reports/by-ticker/VHM returns ReportHistoryResponse with correct shape."""
    with (
        patch(
            f"{ROUTER_PATH}._query_report_history",
            return_value=(_SAMPLE_HISTORY, 1),
        ),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get(
            "/reports/by-ticker/VHM",
            headers=_make_auth_header(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symbol"] == "VHM"
    assert body["page"] == 1
    assert body["per_page"] == 20
    assert body["total"] == 1
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["report_id"] == 1
    assert item["generated_at"] == "2026-03-15T10:00:00"
    assert item["tier"] == "Favorable"
    assert item["verdict"] == "Strong entry"


def test_report_history_pagination(client):
    """GET /reports/by-ticker/VHM?page=2&per_page=5 passes correct params."""
    with (
        patch(
            f"{ROUTER_PATH}._query_report_history",
            return_value=([], 10),
        ) as mock_query,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get(
            "/reports/by-ticker/VHM?page=2&per_page=5",
            headers=_make_auth_header(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page"] == 2
    assert body["per_page"] == 5
    assert body["total"] == 10
    # Verify the helper was called with the right pagination params
    call_args = mock_query.call_args
    assert call_args.args[2] == 2    # page
    assert call_args.args[3] == 5   # per_page


def test_report_history_empty_symbol(client):
    """Unknown symbol returns 200 with empty items array and total=0."""
    with (
        patch(
            f"{ROUTER_PATH}._query_report_history",
            return_value=([], 0),
        ),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get(
            "/reports/by-ticker/UNKNOWN",
            headers=_make_auth_header(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symbol"] == "UNKNOWN"
    assert body["total"] == 0
    assert body["items"] == []


def test_report_history_requires_auth(client):
    """GET /reports/by-ticker/VHM without auth returns 401."""
    response = client.get("/reports/by-ticker/VHM")
    assert response.status_code == 401


def test_generate_requires_auth(client):
    """POST /reports/generate without auth returns 401."""
    response = client.post(
        "/reports/generate",
        json={"ticker": "VHM", "asset_type": "equity"},
    )
    assert response.status_code == 401


def test_health_no_auth_required():
    """GET /health returns 200 without any Authorization header."""
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    mock_state = _make_app_state()
    app.state = mock_state

    tc = TestClient(app, raise_server_exceptions=False)
    response = tc.get("/health")
    assert response.status_code == 200
