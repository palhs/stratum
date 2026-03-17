"""
Reports router — POST /reports/generate, GET /reports/stream/{job_id}, GET /reports/{job_id}.

Phase 8 | Plans 02-03 | Requirements: SRVC-01, SRVC-02, SRVC-03

Endpoints:
  POST /reports/generate           — Submit async report generation job (returns 202)
  GET  /reports/stream/{job_id}    — SSE stream of pipeline progress events
  GET  /reports/{job_id}           — Poll job status or retrieve completed report (200/202/404)

IMPORTANT: /stream/{job_id} is registered BEFORE /{job_id} to prevent FastAPI treating
"stream" as an integer job_id value and returning 422.

All DB operations use SQLAlchemy Core Table reflection (autoload_with=db_engine).
No ORM models — consistent with reasoning/app/pipeline/storage.py pattern.
"""
import asyncio
import json
import logging

from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel
from sqlalchemy import MetaData, Table, text
from sse_starlette import EventSourceResponse

logger = logging.getLogger(__name__)

# Module-level reference to pipeline entry point.
# Defined here so tests can patch 'reasoning.app.routers.reports.generate_report'.
# Assigned lazily on first use to avoid import errors in test environments
# where the 'reasoning' package root is not on sys.path.
generate_report = None  # patched / resolved at call-time via _get_generate_report()


def _get_generate_report():
    """Return generate_report, importing lazily on first call."""
    global generate_report  # noqa: PLW0603
    if generate_report is None:
        from reasoning.app.pipeline import generate_report as _gr  # noqa: PLC0415

        generate_report = _gr
    return generate_report

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    ticker: str
    asset_type: str


class GenerateResponse(BaseModel):
    job_id: int
    status: str


class ReportResponse(BaseModel):
    job_id: int
    status: str
    report_json: dict | None = None
    report_markdown: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# DB helper functions — SQLAlchemy Core
# ---------------------------------------------------------------------------


def _find_active_job(db_engine, asset_id: str) -> int | None:
    """Return job_id of any pending/running job for this asset_id, or None."""
    metadata = MetaData()
    report_jobs = Table("report_jobs", metadata, autoload_with=db_engine)

    with db_engine.connect() as conn:
        stmt = (
            report_jobs.select()
            .where(report_jobs.c.asset_id == asset_id)
            .where(report_jobs.c.status.in_(["pending", "running"]))
            .limit(1)
        )
        row = conn.execute(stmt).fetchone()

    if row is None:
        return None
    return row._mapping["job_id"]


def _create_job(db_engine, asset_id: str) -> int:
    """INSERT a new pending job for asset_id and return the job_id."""
    metadata = MetaData()
    report_jobs = Table("report_jobs", metadata, autoload_with=db_engine)

    with db_engine.begin() as conn:
        result = conn.execute(
            report_jobs.insert()
            .values(asset_id=asset_id, status="pending")
            .returning(report_jobs.c.job_id)
        )
        row = result.fetchone()

    return row._mapping["job_id"]


def _update_job_status(
    db_engine,
    job_id: int,
    status: str,
    report_id: int | None = None,
    error: str | None = None,
) -> None:
    """UPDATE job status and optional report_id / error text."""
    metadata = MetaData()
    report_jobs = Table("report_jobs", metadata, autoload_with=db_engine)

    values = {"status": status, "updated_at": text("NOW()")}
    if report_id is not None:
        values["report_id"] = report_id
    if error is not None:
        values["error"] = error

    with db_engine.begin() as conn:
        conn.execute(
            report_jobs.update()
            .where(report_jobs.c.job_id == job_id)
            .values(**values)
        )


def _get_job(db_engine, job_id: int) -> dict | None:
    """SELECT a single job row by job_id. Returns dict or None."""
    metadata = MetaData()
    report_jobs = Table("report_jobs", metadata, autoload_with=db_engine)

    with db_engine.connect() as conn:
        stmt = report_jobs.select().where(report_jobs.c.job_id == job_id)
        row = conn.execute(stmt).fetchone()

    if row is None:
        return None
    return dict(row._mapping)


def _get_report_by_job(db_engine, job_id: int) -> dict | None:
    """JOIN report_jobs → reports and return the report columns.

    Returns dict with report_json and report_markdown, or None if not found.
    Only called when job status is 'completed'.
    """
    metadata = MetaData()
    report_jobs = Table("report_jobs", metadata, autoload_with=db_engine)
    report_tbl = Table("reports", metadata, autoload_with=db_engine)

    j = report_jobs.join(
        report_tbl,
        report_jobs.c.report_id == report_tbl.c.report_id,
    )

    with db_engine.connect() as conn:
        stmt = (
            report_tbl.select()
            .select_from(j)
            .where(report_jobs.c.job_id == job_id)
        )
        row = conn.execute(stmt).fetchone()

    if row is None:
        return None
    mapping = dict(row._mapping)
    return {
        "report_json": mapping.get("report_json"),
        "report_markdown": mapping.get("report_markdown"),
    }


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _emit(app_state, job_id: int, event: dict) -> None:
    """Put an event dict onto the SSE queue for job_id (no-op if queue missing)."""
    queue = app_state.job_queues.get(job_id)
    if queue is not None:
        await queue.put(event)


async def _run_pipeline(job_id: int, ticker: str, asset_type: str, app_state) -> None:
    """Execute the full pipeline and update job status when done.

    Emits job-level progress events to the SSE queue so clients can observe
    pipeline execution via GET /reports/stream/{job_id}.

    Reads generate_report from the module namespace each time so that test
    patches (patch('app.routers.reports.generate_report', ...)) take effect.
    Falls back to lazy-importing from app.pipeline if the attribute is still None.
    """
    import sys  # noqa: PLC0415

    _mod = sys.modules[__name__]
    _fn = getattr(_mod, "generate_report", None) or _get_generate_report()

    db_engine = app_state.db_engine
    try:
        _update_job_status(db_engine, job_id, "running")
        await _emit(app_state, job_id, {"event_type": "job_started", "job_id": job_id, "ticker": ticker})

        await _emit(app_state, job_id, {"event_type": "pipeline_vi_start", "language": "vi"})
        # generate_report handles both vi + en internally; we emit language events around the full call
        vi_id, en_id = await _fn(
            ticker=ticker,
            asset_type=asset_type,
            db_engine=db_engine,
            neo4j_driver=app_state.neo4j_driver,
            qdrant_client=app_state.qdrant_client,
            db_uri=app_state.db_uri,
        )
        await _emit(app_state, job_id, {"event_type": "pipeline_vi_complete", "language": "vi"})
        await _emit(app_state, job_id, {"event_type": "pipeline_en_complete", "language": "en"})

        _update_job_status(db_engine, job_id, "completed", report_id=vi_id)
        queue = app_state.job_queues.get(job_id)
        if queue:
            await queue.put(None)  # SSE completion sentinel
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for job_id=%d: %s", job_id, exc)
        _update_job_status(db_engine, job_id, "failed", error=str(exc))
        queue = app_state.job_queues.get(job_id)
        if queue:
            await queue.put(None)  # SSE sentinel even on failure


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", status_code=202)
async def generate(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> JSONResponse:
    """Submit an async report generation job.

    Returns 202 immediately with a job_id.
    Returns 409 if a pending/running job already exists for the same asset.
    """
    asset_id = f"{body.ticker}:{body.asset_type}"
    db_engine = request.app.state.db_engine

    existing_id = _find_active_job(db_engine, asset_id)
    if existing_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Job {existing_id} already pending/running for {asset_id}",
        )

    job_id = _create_job(db_engine, asset_id)

    # Set up SSE queue for streaming (Plan 03)
    request.app.state.job_queues[job_id] = asyncio.Queue()

    background_tasks.add_task(
        _run_pipeline,
        job_id,
        body.ticker,
        body.asset_type,
        request.app.state,
    )

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "pending"},
    )


@router.get("/stream/{job_id}")
async def stream_report_events(job_id: int, request: Request):
    """Stream real-time pipeline progress events via Server-Sent Events.

    Emits:
      node_transition — each job-level event posted by _run_pipeline
      complete        — when pipeline finishes (None sentinel received)
      ping            — keepalive every 15s to prevent proxy timeout

    Returns 404 if no SSE queue exists for the given job_id (job not started or
    queue already cleaned up).

    Queue is cleaned up in the generator's finally block to prevent memory leaks.
    Pipeline continues running even if the client disconnects (SSE is read-only).
    """
    queue = request.app.state.job_queues.get(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or stream not available")

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keepalive"}
                    continue
                if event is None:
                    yield {"event": "complete", "data": json.dumps({"job_id": job_id})}
                    break
                yield {"event": "node_transition", "data": json.dumps(event)}
        except asyncio.CancelledError:
            raise
        finally:
            request.app.state.job_queues.pop(job_id, None)

    return EventSourceResponse(event_generator(), ping=15)


@router.get("/{job_id}")
async def get_report(job_id: int, request: Request) -> JSONResponse:
    """Retrieve job status or completed report.

    Returns:
      404 — job_id not found
      202 — job is pending or running
      200 — job completed (includes report_json, report_markdown) or failed (includes error)
    """
    db_engine = request.app.state.db_engine
    job = _get_job(db_engine, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    status = job["status"]

    if status in ("pending", "running"):
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "status": status},
        )

    if status == "completed":
        report = _get_report_by_job(db_engine, job_id)
        return JSONResponse(
            status_code=200,
            content={
                "job_id": job_id,
                "status": "completed",
                "report_json": report.get("report_json") if report else None,
                "report_markdown": report.get("report_markdown") if report else None,
                "error": None,
            },
        )

    # status == "failed"
    return JSONResponse(
        status_code=200,
        content={
            "job_id": job_id,
            "status": "failed",
            "report_json": None,
            "report_markdown": None,
            "error": job.get("error"),
        },
    )
