"""
Tests for GET /reports/stream/{job_id} SSE endpoint.

SRVC-03: SSE stream emits node_transition events and complete event.

Test approach:
  Pre-populate asyncio.Queue with events before making the request.
  Since all events including the None sentinel are already in the queue,
  the SSE generator yields all events immediately and closes.
  Uses httpx.AsyncClient with ASGITransport for async SSE response reading.
"""
import asyncio
import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock

from app.routers import reports


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app_state(job_queues=None):
    """Build a mock app.state with all required attributes."""
    state = MagicMock()
    state.db_engine = MagicMock()
    state.neo4j_driver = MagicMock()
    state.qdrant_client = MagicMock()
    state.db_uri = "postgresql://user:pass@localhost/stratum"
    state.job_queues = job_queues if job_queues is not None else {}
    return state


@pytest.fixture
def stream_app():
    """Minimal FastAPI app with reports router for SSE testing."""
    app = FastAPI()
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.state = _make_app_state()
    return app


# ---------------------------------------------------------------------------
# SSE helper — parse SSE lines from response text
# ---------------------------------------------------------------------------


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE event lines into list of {event, data} dicts."""
    events = []
    current = {}
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_stream_emits_events(stream_app):
    """Pre-populate queue with node events + sentinel; SSE yields node_transition events."""
    job_id = 1
    queue = asyncio.Queue()
    queue.put_nowait({"event_type": "job_started", "job_id": job_id, "ticker": "VHM"})
    queue.put_nowait({"event_type": "pipeline_vi_start", "language": "vi"})
    queue.put_nowait({"event_type": "pipeline_vi_complete", "language": "vi"})
    queue.put_nowait(None)  # sentinel

    stream_app.state.job_queues = {job_id: queue}

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            body = await response.aread()
            text = body.decode("utf-8")

    events = _parse_sse_events(text)
    event_types = [e["event"] for e in events if "event" in e]
    assert "node_transition" in event_types, f"Expected node_transition events, got: {event_types}"

    # Verify the node_transition data payload contains event_type
    node_events = [e for e in events if e.get("event") == "node_transition"]
    assert len(node_events) >= 1
    first_data = json.loads(node_events[0]["data"])
    assert "event_type" in first_data


@pytest.mark.asyncio
async def test_sse_stream_complete_event(stream_app):
    """Queue with only None sentinel yields a 'complete' event and stream closes."""
    job_id = 2
    queue = asyncio.Queue()
    queue.put_nowait(None)  # sentinel only

    stream_app.state.job_queues = {job_id: queue}

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            assert response.status_code == 200
            body = await response.aread()
            text = body.decode("utf-8")

    events = _parse_sse_events(text)
    event_types = [e["event"] for e in events if "event" in e]
    assert "complete" in event_types, f"Expected complete event, got: {event_types}"

    complete_events = [e for e in events if e.get("event") == "complete"]
    data = json.loads(complete_events[0]["data"])
    assert data["job_id"] == job_id


@pytest.mark.asyncio
async def test_sse_stream_404(stream_app):
    """GET /reports/stream/{job_id} returns 404 when no queue exists for the job_id."""
    stream_app.state.job_queues = {}  # no queues

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        response = await client.get("/reports/stream/9999")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_sse_queue_cleanup(stream_app):
    """After SSE stream closes, job_id is removed from app.state.job_queues."""
    job_id = 3
    queue = asyncio.Queue()
    queue.put_nowait(None)  # immediate close

    stream_app.state.job_queues = {job_id: queue}
    assert job_id in stream_app.state.job_queues

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            await response.aread()

    # After stream ends, queue should be cleaned up
    assert stream_app.state.job_queues.get(job_id) is None, (
        f"Expected job_id {job_id} to be removed from job_queues after stream close"
    )


@pytest.mark.asyncio
async def test_sse_stream_node_start_and_complete_events(stream_app):
    """SSE stream emits node_transition events for node_start and node_complete."""
    job_id = 10
    queue = asyncio.Queue()
    queue.put_nowait({"event_type": "node_start", "node": "macro_regime"})
    queue.put_nowait({"event_type": "node_complete", "node": "macro_regime", "error": None})
    queue.put_nowait({"event_type": "node_start", "node": "valuation"})
    queue.put_nowait({"event_type": "node_complete", "node": "valuation", "error": None})
    queue.put_nowait(None)  # sentinel

    stream_app.state.job_queues = {job_id: queue}

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            assert response.status_code == 200
            body = await response.aread()
            text = body.decode("utf-8")

    events = _parse_sse_events(text)
    node_events = [e for e in events if e.get("event") == "node_transition"]
    assert len(node_events) == 4  # 2 starts + 2 completes

    # Verify first event is node_start for macro_regime
    first = json.loads(node_events[0]["data"])
    assert first["event_type"] == "node_start"
    assert first["node"] == "macro_regime"

    # Verify second event is node_complete for macro_regime
    second = json.loads(node_events[1]["data"])
    assert second["event_type"] == "node_complete"
    assert second["node"] == "macro_regime"
    assert second["error"] is None


@pytest.mark.asyncio
async def test_sse_stream_node_failure_event(stream_app):
    """SSE stream emits node_transition with error field when a node fails."""
    job_id = 11
    queue = asyncio.Queue()
    queue.put_nowait({"event_type": "node_start", "node": "macro_regime"})
    queue.put_nowait({"event_type": "node_complete", "node": "macro_regime", "error": "LLM timeout"})
    queue.put_nowait(None)

    stream_app.state.job_queues = {job_id: queue}

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            body = await response.aread()
            text = body.decode("utf-8")

    events = _parse_sse_events(text)
    node_events = [e for e in events if e.get("event") == "node_transition"]
    # Find the node_complete event
    complete_data = json.loads(node_events[1]["data"])
    assert complete_data["event_type"] == "node_complete"
    assert complete_data["error"] == "LLM timeout"


@pytest.mark.asyncio
async def test_sse_stream_all_seven_nodes(stream_app):
    """Full pipeline emits node_start + node_complete for all 7 nodes."""
    job_id = 12
    queue = asyncio.Queue()
    nodes = ["macro_regime", "valuation", "structure", "conflict",
             "entry_quality", "grounding_check", "compose_report"]
    for node in nodes:
        queue.put_nowait({"event_type": "node_start", "node": node})
        queue.put_nowait({"event_type": "node_complete", "node": node, "error": None})
    queue.put_nowait(None)

    stream_app.state.job_queues = {job_id: queue}

    async with AsyncClient(
        transport=ASGITransport(app=stream_app), base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/reports/stream/{job_id}") as response:
            body = await response.aread()
            text = body.decode("utf-8")

    events = _parse_sse_events(text)
    node_events = [e for e in events if e.get("event") == "node_transition"]
    assert len(node_events) == 14  # 7 starts + 7 completes

    # Verify all node names present
    node_names = {json.loads(e["data"])["node"] for e in node_events}
    assert node_names == set(nodes)
