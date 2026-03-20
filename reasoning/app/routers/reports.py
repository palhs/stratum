"""
Reports router — POST /reports/generate, GET /reports/by-ticker/{symbol},
                 GET /reports/by-report-id/{report_id},
                 GET /reports/stream/{job_id}, GET /reports/{job_id}.

Phase 8 | Plans 02-03 | Requirements: SRVC-01, SRVC-02, SRVC-03
Phase 10 | Plan 02     | Requirements: INFR-05
Phase 14 | Plan 01     | Requirements: RVEW-01, RVEW-04, RHST-03

Endpoints:
  POST /reports/generate                   — Submit async report generation job (returns 202) [auth required]
  GET  /reports/by-ticker/{symbol}         — Paginated history of reports for a symbol [auth required]
  GET  /reports/by-report-id/{report_id}  — Full report content (both vi and en) for a given report_id [auth required]
  GET  /reports/stream/{job_id}            — SSE stream of pipeline progress events
  GET  /reports/{job_id}                   — Poll job status or retrieve completed report (200/202/404)

IMPORTANT: /by-ticker/{symbol}, /by-report-id/{report_id}, and /stream/{job_id} are registered
BEFORE /{job_id} to prevent FastAPI treating string path segments as an integer job_id and returning 422.

All DB operations use SQLAlchemy Core Table reflection (autoload_with=db_engine).
No ORM models — consistent with reasoning/app/pipeline/storage.py pattern.
"""
import asyncio
import json
import logging

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel
from sqlalchemy import MetaData, Table, distinct, func, select, text
from sse_starlette import EventSourceResponse

from reasoning.app.auth import require_auth
from reasoning.app.schemas import ReportHistoryItem, ReportHistoryResponse, ReportContentResponse

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


def _query_report_history(
    db_engine, symbol: str, page: int, per_page: int
) -> tuple[list[dict], int]:
    """Return paginated report history for a ticker symbol.

    Groups vi+en reports by generated_at (one entry per generation run).
    Extracts tier and narrative from report_json JSONB via raw SQL expressions.
    Returns (items_list, total_count).
    """
    metadata = MetaData()
    reports = Table("reports", metadata, autoload_with=db_engine)

    where_clause = reports.c.asset_id == symbol.upper()

    # Main query: one row per generation run (grouped by generated_at)
    history_stmt = (
        select(
            func.min(reports.c.report_id).label("report_id"),
            reports.c.generated_at,
            text("MIN(report_json->'entry_quality'->>'tier') AS tier"),
            text("MIN(report_json->'entry_quality'->>'narrative') AS verdict"),
        )
        .where(where_clause)
        .group_by(reports.c.generated_at)
        .order_by(reports.c.generated_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )

    # Count query: distinct generation runs
    count_stmt = select(func.count(distinct(reports.c.generated_at))).where(where_clause)

    with db_engine.connect() as conn:
        rows = conn.execute(history_stmt).fetchall()
        total_count = conn.execute(count_stmt).scalar() or 0

    items = []
    for row in rows:
        mapping = dict(row._mapping)
        generated_at = mapping.get("generated_at")
        if generated_at is not None and hasattr(generated_at, "isoformat"):
            generated_at = generated_at.isoformat()
        else:
            generated_at = str(generated_at) if generated_at is not None else ""
        items.append(
            {
                "report_id": int(mapping["report_id"]),
                "generated_at": generated_at,
                "tier": mapping.get("tier") or "Unknown",
                "verdict": mapping.get("verdict") or "",
            }
        )

    return items, int(total_count)


def _get_report_content_by_id(db_engine, report_id: int) -> dict | None:
    """Fetch both vi and en report rows for a given report_id's generation run."""
    metadata = MetaData()
    reports = Table("reports", metadata, autoload_with=db_engine)

    with db_engine.connect() as conn:
        anchor = conn.execute(
            reports.select().where(reports.c.report_id == report_id)
        ).fetchone()
        if anchor is None:
            return None
        anchor_map = dict(anchor._mapping)

        rows = conn.execute(
            reports.select()
            .where(reports.c.asset_id == anchor_map["asset_id"])
            .where(reports.c.generated_at == anchor_map["generated_at"])
        ).fetchall()

    report_json = anchor_map.get("report_json") or {}
    entry_quality = report_json.get("entry_quality", {})
    generated_at = anchor_map.get("generated_at")
    if generated_at is not None and hasattr(generated_at, "isoformat"):
        generated_at = generated_at.isoformat()
    else:
        generated_at = str(generated_at) if generated_at is not None else ""

    result = {
        "report_id": report_id,
        "generated_at": generated_at,
        "tier": entry_quality.get("tier", "Unknown"),
        "verdict": entry_quality.get("narrative", ""),
        "macro_assessment": entry_quality.get("macro_assessment", ""),
        "valuation_assessment": entry_quality.get("valuation_assessment", ""),
        "structure_assessment": entry_quality.get("structure_assessment", ""),
        "report_markdown_vi": None,
        "report_markdown_en": None,
    }
    for row in rows:
        m = dict(row._mapping)
        lang = m.get("language")
        if lang == "vi":
            result["report_markdown_vi"] = m.get("report_markdown")
        elif lang == "en":
            result["report_markdown_en"] = m.get("report_markdown")

    return result


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
        # generate_report handles both vi + en internally; we emit language events around the full call.
        # Pass sse_queue so generate_report can forward per-node node_start/node_complete events.
        queue = app_state.job_queues.get(job_id)
        vi_id, en_id = await _fn(
            ticker=ticker,
            asset_type=asset_type,
            db_engine=db_engine,
            neo4j_driver=app_state.neo4j_driver,
            qdrant_client=app_state.qdrant_client,
            db_uri=app_state.db_uri,
            sse_queue=queue,
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
    _: dict = Depends(require_auth),
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


@router.get("/by-ticker/{symbol}", response_model=ReportHistoryResponse)
async def get_report_history(
    symbol: str,
    page: int = 1,
    per_page: int = 20,
    request: Request = ...,
    _: dict = Depends(require_auth),
) -> ReportHistoryResponse:
    """Return paginated report history for a ticker symbol.

    Groups vi+en reports by generated_at — one entry per generation run.
    Returns newest reports first.

    Returns 200 with empty items and total=0 for unknown symbols.
    Returns 401 if Authorization header is missing.
    """
    items, total = _query_report_history(
        request.app.state.db_engine, symbol, page, per_page
    )
    return ReportHistoryResponse(
        symbol=symbol.upper(),
        page=page,
        per_page=per_page,
        total=total,
        items=items,
    )


@router.get("/by-report-id/{report_id}", response_model=ReportContentResponse)
async def get_report_content(
    report_id: int,
    request: Request,
    _: dict = Depends(require_auth),
) -> ReportContentResponse:
    """Return full report content (both vi and en) for a given report_id.

    The report_id identifies the anchor row; both language rows sharing the same
    asset_id + generated_at are returned in a single response.

    Returns 404 if report_id does not exist.
    """
    result = _get_report_content_by_id(request.app.state.db_engine, report_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return ReportContentResponse(**result)


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
