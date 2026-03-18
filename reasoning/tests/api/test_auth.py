"""
Unit tests for the require_auth FastAPI dependency.

Tests JWT validation in isolation using a minimal FastAPI app.

Scenarios:
  - No Authorization header -> 401
  - Expired JWT -> 403
  - Wrong audience JWT -> 403
  - Valid JWT -> 200 with decoded payload
  - Malformed/garbage token -> 401
"""
import os
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from reasoning.app.auth import require_auth


# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------

_SECRET = "test-secret-for-unit-tests"


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
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, _SECRET, algorithm="HS256")


def _future_exp() -> int:
    return int(time.time()) + 3600  # 1 hour from now


def _past_exp() -> int:
    return int(time.time()) - 3600  # 1 hour ago


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_auth_no_header_returns_401(client):
    """Request with no Authorization header returns 401."""
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}):
        response = client.get("/test")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_auth_valid_token_passes(client):
    """Valid JWT returns decoded payload and 200."""
    token = _make_token({"sub": "user-123", "aud": "authenticated", "exp": _future_exp()})
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "user-123"
    assert body["aud"] == "authenticated"


def test_auth_expired_token_returns_403(client):
    """Request with expired JWT returns 403."""
    token = _make_token({"sub": "user-123", "aud": "authenticated", "exp": _past_exp()})
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "expired" in response.json()["detail"].lower()


def test_auth_wrong_audience_returns_403(client):
    """JWT with audience != 'authenticated' returns 403."""
    token = _make_token({"sub": "user-123", "aud": "wrong", "exp": _future_exp()})
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "audience" in response.json()["detail"].lower()


def test_auth_malformed_token_returns_401(client):
    """Garbage/malformed token string returns 401."""
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}):
        response = client.get("/test", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
