"""
reasoning/app/pipeline — LangGraph StateGraph assembly and two-stage pipeline.
Phase 7 | Plan 01 | Requirement: REAS-06
Phase 7 | Plan 05 | Requirement: REPT-05

Exports:
    generate_report  — Async: full pipeline entry point — prefetch → run_graph(vi) → write → run_graph(en) → write
    build_graph      — Build the 7-node linear StateGraph (no checkpointer, for compilation)
    run_graph        — Async: compile graph with AsyncPostgresSaver and invoke it
    prefetch         — Two-stage prefetch: retrieve all data before graph runs
"""

import asyncio
import copy
import uuid
import time

from reasoning.app.pipeline.graph import build_graph, run_graph
from reasoning.app.pipeline.prefetch import prefetch
from reasoning.app.pipeline.storage import write_report

__all__ = [
    "generate_report",
    "build_graph",
    "run_graph",
    "prefetch",
]


async def generate_report(
    ticker: str,
    asset_type: str,
    db_engine,
    neo4j_driver,
    qdrant_client,
    db_uri: str,
    sse_queue: asyncio.Queue | None = None,
) -> tuple[int, int]:
    """
    Full pipeline entry point — orchestrates prefetch → run_graph(vi) → write → run_graph(en) → write.

    This is the single public entry point for Phase 8 FastAPI.

    Args:
        ticker:        Asset ticker symbol (e.g. "VHM", "GOLD").
        asset_type:    Asset type — "equity" or "gold".
        db_engine:     SQLAlchemy Engine for PostgreSQL retrieval and storage.
        neo4j_driver:  Neo4j driver / graph store for regime analogue retrieval.
        qdrant_client: Qdrant client for vector search retrieval.
        db_uri:        PostgreSQL connection URI (without schema override).
                       Used by run_graph() for AsyncPostgresSaver checkpointer.

    Returns:
        tuple[int, int]: (vi_report_id, en_report_id) — the generated report IDs
                         for the Vietnamese and English reports respectively.

    Pipeline:
        1. prefetch() — retrieve all data sources (PostgreSQL, Neo4j, Qdrant)
        2. run_graph(state_vi, "vi", ...) — Vietnamese LangGraph execution
        3. write_report(vi_result["report_output"]) — store vi report, get vi_id
        4. run_graph(state_en, "en", ...) — English LangGraph execution
        5. write_report(en_result["report_output"]) — store en report, get en_id

    State isolation:
        copy.deepcopy(state) is used between vi and en invocations to prevent
        state mutation from the vi run affecting the en run.
    """
    # Stage 1: Prefetch all data sources
    state = prefetch(ticker, asset_type, db_engine, neo4j_driver, qdrant_client)

    # Stage 2a: Vietnamese graph execution — pass sse_queue for node-level progress events
    state_vi = copy.deepcopy(state)
    thread_id_vi = f"{ticker}-vi-{uuid.uuid4()}"
    start_vi = time.monotonic()
    result_vi = await run_graph(state_vi, "vi", thread_id_vi, db_uri, queue=sse_queue)
    duration_vi = int((time.monotonic() - start_vi) * 1000)

    # Stage 3a: Store Vietnamese report
    vi_id = write_report(db_engine, ticker, "vi", result_vi["report_output"], duration_vi)

    # Stage 2b: English graph execution (deep copy from original prefetch state)
    # No queue for en run — vi already showed all 7 steps (single-pass progress perception)
    state_en = copy.deepcopy(state)
    thread_id_en = f"{ticker}-en-{uuid.uuid4()}"
    start_en = time.monotonic()
    result_en = await run_graph(state_en, "en", thread_id_en, db_uri)
    duration_en = int((time.monotonic() - start_en) * 1000)

    # Stage 3b: Store English report
    en_id = write_report(db_engine, ticker, "en", result_en["report_output"], duration_en)

    return (vi_id, en_id)
