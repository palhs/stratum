"""
Tests for GET /health endpoint.

Uses a minimal test app (no lifespan) to avoid real DB connections.
The health router has no app.state dependencies.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import health


@pytest.fixture(scope="module")
def test_app():
    """Minimal FastAPI app with health router only — no lifespan."""
    app = FastAPI()
    app.include_router(health.router)
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return TestClient(test_app)


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client):
    response = client.get("/health")
    body = response.json()
    assert "status" in body
    assert "service" in body
    assert body["status"] == "ok"
    assert body["service"] == "reasoning-engine"
