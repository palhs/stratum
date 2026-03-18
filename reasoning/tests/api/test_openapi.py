"""
Tests for the auto-generated FastAPI OpenAPI spec.

Verifies that all endpoints appear in the spec with correct response schema refs,
and that all Pydantic response models are documented in components.schemas.

Scenarios:
  - /tickers/{symbol}/ohlcv exists in paths with GET method and OHLCVResponse schema ref
  - /reports/by-ticker/{symbol} exists in paths with GET method and ReportHistoryResponse schema ref
  - /health exists in paths (public endpoint sanity check)
  - OHLCVPoint, OHLCVResponse, ReportHistoryItem, ReportHistoryResponse appear in components.schemas
"""
import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reasoning.app.routers import health, reports, tickers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app_state():
    state = MagicMock()
    state.db_engine = MagicMock()
    state.neo4j_driver = MagicMock()
    state.qdrant_client = MagicMock()
    state.db_uri = "postgresql://user:pass@localhost/stratum"
    state.job_queues = {}
    return state


@pytest.fixture(scope="module")
def openapi_spec():
    """Build a full app with all routers and return the OpenAPI dict."""
    # Must set env var before importing modules that read it at import time
    os.environ.setdefault("SUPABASE_JWKS_URL", "https://test.supabase.co/auth/v1/.well-known/jwks.json")

    app = FastAPI(title="Stratum Reasoning Engine Test")
    app.include_router(health.router)
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.include_router(tickers.router, prefix="/tickers", tags=["tickers"])
    app.state = _make_app_state()

    return app.openapi()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_openapi_has_ohlcv_endpoint(openapi_spec):
    """GET /tickers/{symbol}/ohlcv appears in OpenAPI paths with OHLCVResponse schema."""
    paths = openapi_spec["paths"]
    assert "/tickers/{symbol}/ohlcv" in paths, (
        f"Expected /tickers/{{symbol}}/ohlcv in paths, got: {list(paths.keys())}"
    )
    ohlcv_path = paths["/tickers/{symbol}/ohlcv"]
    assert "get" in ohlcv_path, "Expected GET method on /tickers/{symbol}/ohlcv"

    # Verify response schema references OHLCVResponse
    get_op = ohlcv_path["get"]
    response_200 = get_op.get("responses", {}).get("200", {})
    content = response_200.get("content", {})
    schema_ref = (
        content.get("application/json", {}).get("schema", {}).get("$ref", "")
        or str(content)
    )
    assert "OHLCVResponse" in schema_ref, (
        f"Expected OHLCVResponse schema ref in /tickers/{{symbol}}/ohlcv response, got: {content}"
    )


def test_openapi_has_report_history_endpoint(openapi_spec):
    """GET /reports/by-ticker/{symbol} appears in OpenAPI paths with ReportHistoryResponse schema."""
    paths = openapi_spec["paths"]
    assert "/reports/by-ticker/{symbol}" in paths, (
        f"Expected /reports/by-ticker/{{symbol}} in paths, got: {list(paths.keys())}"
    )
    history_path = paths["/reports/by-ticker/{symbol}"]
    assert "get" in history_path, "Expected GET method on /reports/by-ticker/{symbol}"

    # Verify response schema references ReportHistoryResponse
    get_op = history_path["get"]
    response_200 = get_op.get("responses", {}).get("200", {})
    content = response_200.get("content", {})
    schema_ref = (
        content.get("application/json", {}).get("schema", {}).get("$ref", "")
        or str(content)
    )
    assert "ReportHistoryResponse" in schema_ref, (
        f"Expected ReportHistoryResponse schema ref in /reports/by-ticker response, got: {content}"
    )


def test_openapi_has_health_endpoint(openapi_spec):
    """GET /health appears in OpenAPI paths (public endpoint sanity check)."""
    paths = openapi_spec["paths"]
    assert "/health" in paths, (
        f"Expected /health in paths, got: {list(paths.keys())}"
    )


def test_openapi_schemas_defined(openapi_spec):
    """All Pydantic response schemas appear in OpenAPI components.schemas."""
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    required_schemas = [
        "OHLCVPoint",
        "OHLCVResponse",
        "ReportHistoryItem",
        "ReportHistoryResponse",
    ]
    for schema_name in required_schemas:
        assert schema_name in schemas, (
            f"Expected schema '{schema_name}' in components.schemas, got: {list(schemas.keys())}"
        )
