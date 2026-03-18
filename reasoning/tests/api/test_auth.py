"""
Unit tests for the require_auth FastAPI dependency.

Tests JWT validation in isolation using a minimal FastAPI app.
Uses RS256 key pair and mocks the module-level PyJWKClient singleton.

Scenarios:
  - No Authorization header -> 401
  - Expired JWT -> 403
  - Wrong audience JWT -> 403
  - Valid JWT -> 200 with decoded payload
  - Malformed/garbage token -> 401
"""
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from reasoning.app.auth import require_auth


# ---------------------------------------------------------------------------
# Test RSA key pair — generated once at module level
# ---------------------------------------------------------------------------

_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()

# Reusable mock signing key: .key attribute is what PyJWT uses for decoding
_mock_signing_key = MagicMock()
_mock_signing_key.key = _TEST_PUBLIC_KEY


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(payload: dict) -> str:
    """Encode a JWT with the test RSA private key (RS256)."""
    return jwt.encode(payload, _TEST_PRIVATE_KEY, algorithm="RS256")


def _future_exp() -> int:
    return int(time.time()) + 3600  # 1 hour from now


def _past_exp() -> int:
    return int(time.time()) - 3600  # 1 hour ago


# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Minimal FastAPI app with a single protected endpoint for testing require_auth."""
    app = FastAPI()

    @app.get("/test")
    async def protected(payload: dict = Depends(require_auth)):
        return {"sub": payload.get("sub"), "aud": payload.get("aud")}

    return app


@pytest.fixture(scope="module")
def client():
    app = _build_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_auth_no_header_returns_401(client):
    """Request with no Authorization header returns 401."""
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/test")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_auth_valid_token_passes(client):
    """Valid RS256 JWT returns decoded payload and 200."""
    token = _make_token({"sub": "user-123", "aud": "authenticated", "exp": _future_exp()})
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "user-123"
    assert body["aud"] == "authenticated"


def test_auth_expired_token_returns_403(client):
    """Request with expired RS256 JWT returns 403."""
    token = _make_token({"sub": "user-123", "aud": "authenticated", "exp": _past_exp()})
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "expired" in response.json()["detail"].lower()


def test_auth_wrong_audience_returns_403(client):
    """JWT with audience != 'authenticated' returns 403."""
    token = _make_token({"sub": "user-123", "aud": "wrong", "exp": _future_exp()})
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.return_value = _mock_signing_key
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "audience" in response.json()["detail"].lower()


def test_auth_malformed_token_returns_401(client):
    """Garbage/malformed token string returns 401."""
    with patch("reasoning.app.auth._jwks_client") as mock_client:
        mock_client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError("bad key")
        response = client.get("/test", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
