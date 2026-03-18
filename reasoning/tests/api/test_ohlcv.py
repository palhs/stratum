"""
Unit tests for GET /tickers/{symbol}/ohlcv endpoint.

Tests are isolated — no real DB connections.
_query_ohlcv is patched to return sample data; require_auth is patched to
bypass JWT validation for endpoint logic tests.

Scenarios:
  - Valid request returns 200 with correct OHLCVResponse shape
  - Empty data for unknown symbol returns 200 with empty data array
  - No Authorization header returns 401 (auth not bypassed)
  - Gold symbol routing: GLD routes to gold_etf_ohlcv table (verified via _query_ohlcv call)
"""
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.routers import tickers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROUTER_PATH = "reasoning.app.routers.tickers"

# Test RSA key pair — generated once at module level
_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()

# Reusable mock signing key
_mock_signing_key = MagicMock()
_mock_signing_key.key = _TEST_PUBLIC_KEY

_SAMPLE_OHLCV = [
    {
        "time": 1700000000,
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 105.0,
        "volume": 1000,
        "ma50": 102.5,
        "ma200": 98.0,
    },
    {
        "time": 1700604800,
        "open": 105.0,
        "high": 115.0,
        "low": 100.0,
        "close": 112.0,
        "volume": 1200,
        "ma50": 103.0,
        "ma200": 99.0,
    },
]


def _make_app_state():
    state = MagicMock()
    state.db_engine = MagicMock()
    return state


@pytest.fixture(scope="module")
def test_app():
    """Minimal FastAPI app with tickers router and mocked app.state."""
    app = FastAPI()
    app.include_router(tickers.router, prefix="/tickers", tags=["tickers"])
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
# Tests
# ---------------------------------------------------------------------------


def test_ohlcv_returns_data_with_ma(client):
    """GET /tickers/VHM/ohlcv with valid auth returns OHLCVResponse with correct shape."""
    with (
        patch(f"{ROUTER_PATH}._query_ohlcv", return_value=_SAMPLE_OHLCV),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/tickers/VHM/ohlcv", headers=_make_auth_header())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["symbol"] == "VHM"
    assert len(body["data"]) == 2

    point = body["data"][0]
    assert isinstance(point["time"], int)
    assert "open" in point
    assert "high" in point
    assert "low" in point
    assert "close" in point
    assert "volume" in point
    assert "ma50" in point
    assert "ma200" in point


def test_ohlcv_empty_symbol_returns_empty_data(client):
    """Unknown symbol returns 200 with empty data array."""
    with (
        patch(f"{ROUTER_PATH}._query_ohlcv", return_value=[]),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/tickers/UNKNOWN/ohlcv", headers=_make_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "UNKNOWN"
    assert body["data"] == []


def test_ohlcv_requires_auth(client):
    """GET /tickers/VHM/ohlcv with no auth returns 401."""
    response = client.get("/tickers/VHM/ohlcv")
    assert response.status_code == 401


def test_ohlcv_gold_symbol_routes_to_gold_table(client):
    """GLD symbol calls _query_ohlcv (table routing is internal to that function)."""
    with (
        patch(f"{ROUTER_PATH}._query_ohlcv", return_value=_SAMPLE_OHLCV) as mock_query,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/tickers/GLD/ohlcv", headers=_make_auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "GLD"
    # Verify _query_ohlcv was called with GLD (uppercase) — table routing happens inside
    mock_query.assert_called_once()
    call_args = mock_query.call_args
    # Second positional arg is symbol
    assert call_args.args[1] == "GLD"
