"""
Unit tests for GET /watchlist and PUT /watchlist endpoints.

Tests are isolated — no real DB connections.
Internal functions (_get_or_seed_watchlist, _replace_watchlist, _validate_symbols) are
patched; require_auth is patched to bypass JWT validation for endpoint logic tests.

Scenarios:
  - GET /watchlist requires auth (401 on missing header)
  - GET /watchlist seeds defaults for new user (empty DB)
  - GET /watchlist returns existing tickers for returning user
  - PUT /watchlist replaces list (204 on success)
  - PUT /watchlist validates symbols (422 on unknown symbol)
  - PUT /watchlist enforces max 30 tickers (422)
  - PUT /watchlist with empty list returns 204
  - PUT /watchlist requires auth (401 on missing header)
  - User A's watchlist is not visible to User B (isolation)
"""
import os
import time
from unittest.mock import MagicMock, patch

# Must be set before importing modules that read env vars at import time
os.environ.setdefault("SUPABASE_JWKS_URL", "https://test.supabase.co/auth/v1/.well-known/jwks.json")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.routers import watchlist


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROUTER_PATH = "reasoning.app.routers.watchlist"

# Test RSA key pair — generated once at module level
_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()

# Reusable mock signing key
_mock_signing_key = MagicMock()
_mock_signing_key.key = _TEST_PUBLIC_KEY

_SAMPLE_WATCHLIST = [
    {"symbol": "VHM", "name": "Vinhomes", "asset_type": "equity"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "asset_type": "gold_etf"},
]

_DEFAULT_WATCHLIST = [
    {"symbol": "GLD", "name": "SPDR Gold Shares", "asset_type": "gold_etf"},
    {"symbol": "VNM", "name": "Vinamilk", "asset_type": "equity"},
    {"symbol": "VHM", "name": "Vinhomes", "asset_type": "equity"},
    {"symbol": "VCB", "name": "Vietcombank", "asset_type": "equity"},
    {"symbol": "HPG", "name": "Hoa Phat Group", "asset_type": "equity"},
    {"symbol": "MSN", "name": "Masan Group", "asset_type": "equity"},
]


def _make_app_state():
    state = MagicMock()
    state.db_engine = MagicMock()
    return state


@pytest.fixture(scope="module")
def test_app():
    """Minimal FastAPI app with watchlist router and mocked app.state."""
    app = FastAPI()
    app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
    app.state = _make_app_state()
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=False)


def _make_auth_header(sub: str = "user-1"):
    token = jwt.encode(
        {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600},
        _TEST_PRIVATE_KEY,
        algorithm="RS256",
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /watchlist tests
# ---------------------------------------------------------------------------


def test_get_watchlist_requires_auth(client):
    """GET /watchlist without Authorization header returns 401."""
    response = client.get("/watchlist")
    assert response.status_code == 401


def test_get_watchlist_seeds_defaults(client):
    """GET /watchlist for new user seeds defaults and returns them."""
    with (
        patch(
            f"{ROUTER_PATH}._get_or_seed_watchlist",
            return_value=_DEFAULT_WATCHLIST,
        ) as mock_seed,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/watchlist", headers=_make_auth_header())

    assert response.status_code == 200, response.text
    body = response.json()
    assert "tickers" in body
    assert len(body["tickers"]) == 6
    # Verify the seeding function was called
    mock_seed.assert_called_once()
    call_args = mock_seed.call_args
    # First positional arg is db_engine, second is user_id
    assert call_args.args[1] == "user-1"

    # Verify response shape (symbol, name, asset_type)
    item = body["tickers"][0]
    assert "symbol" in item
    assert "name" in item
    assert "asset_type" in item


def test_get_watchlist_returns_existing(client):
    """GET /watchlist for existing user returns their stored tickers."""
    with (
        patch(
            f"{ROUTER_PATH}._get_or_seed_watchlist",
            return_value=_SAMPLE_WATCHLIST,
        ),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/watchlist", headers=_make_auth_header())

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["tickers"]) == 2
    symbols = [t["symbol"] for t in body["tickers"]]
    assert "VHM" in symbols
    assert "GLD" in symbols


# ---------------------------------------------------------------------------
# PUT /watchlist tests
# ---------------------------------------------------------------------------


def test_put_watchlist_requires_auth(client):
    """PUT /watchlist without Authorization header returns 401."""
    response = client.put("/watchlist", json={"tickers": ["VHM", "GLD"]})
    assert response.status_code == 401


def test_put_watchlist_replaces(client):
    """PUT /watchlist with valid tickers returns 204."""
    with (
        patch(f"{ROUTER_PATH}._validate_symbols", return_value=[]),
        patch(f"{ROUTER_PATH}._replace_watchlist") as mock_replace,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.put(
            "/watchlist",
            json={"tickers": ["VHM", "GLD", "TCB"]},
            headers=_make_auth_header(),
        )

    assert response.status_code == 204, response.text
    mock_replace.assert_called_once()
    call_args = mock_replace.call_args
    # Second positional arg is user_id, third is tickers list
    assert call_args.args[1] == "user-1"
    assert "VHM" in call_args.args[2]
    assert "GLD" in call_args.args[2]
    assert "TCB" in call_args.args[2]


def test_put_watchlist_invalid_symbol(client):
    """PUT /watchlist with unknown symbol returns 422 with invalid symbols listed."""
    with (
        patch(f"{ROUTER_PATH}._validate_symbols", return_value=["INVALID_TICKER"]),
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.put(
            "/watchlist",
            json={"tickers": ["VHM", "INVALID_TICKER"]},
            headers=_make_auth_header(),
        )

    assert response.status_code == 422, response.text
    body = response.json()
    assert "INVALID_TICKER" in body["detail"]


def test_put_watchlist_exceeds_max(client):
    """PUT /watchlist with 31 tickers returns 422 with max size error."""
    tickers_31 = [f"T{i:02d}" for i in range(31)]
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.put(
            "/watchlist",
            json={"tickers": tickers_31},
            headers=_make_auth_header(),
        )

    assert response.status_code == 422, response.text
    body = response.json()
    assert "30" in body["detail"] or "maximum" in body["detail"].lower()


def test_put_watchlist_empty(client):
    """PUT /watchlist with empty list returns 204 (explicit clear)."""
    with (
        patch(f"{ROUTER_PATH}._validate_symbols", return_value=[]),
        patch(f"{ROUTER_PATH}._replace_watchlist") as mock_replace,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.put(
            "/watchlist",
            json={"tickers": []},
            headers=_make_auth_header(),
        )

    assert response.status_code == 204, response.text
    mock_replace.assert_called_once()
    call_args = mock_replace.call_args
    assert call_args.args[2] == []


def test_watchlist_isolation(client):
    """User A's watchlist is not returned to User B."""
    user_a_items = [{"symbol": "VHM", "name": "Vinhomes", "asset_type": "equity"}]
    user_b_items = [{"symbol": "GLD", "name": "SPDR Gold Shares", "asset_type": "gold_etf"}]

    # User A GET
    with (
        patch(f"{ROUTER_PATH}._get_or_seed_watchlist", return_value=user_a_items) as mock_fn,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        resp_a = client.get("/watchlist", headers=_make_auth_header(sub="user-a"))
    assert resp_a.status_code == 200
    assert mock_fn.call_args.args[1] == "user-a"
    assert resp_a.json()["tickers"][0]["symbol"] == "VHM"

    # User B GET
    with (
        patch(f"{ROUTER_PATH}._get_or_seed_watchlist", return_value=user_b_items) as mock_fn,
        patch("reasoning.app.auth._jwks_client") as mock_client,
    ):
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        resp_b = client.get("/watchlist", headers=_make_auth_header(sub="user-b"))
    assert resp_b.status_code == 200
    assert mock_fn.call_args.args[1] == "user-b"
    assert resp_b.json()["tickers"][0]["symbol"] == "GLD"
