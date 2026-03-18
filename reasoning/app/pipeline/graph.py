"""
reasoning/app/pipeline/graph.py — LangGraph StateGraph assembly and run_graph.
Phase 7 | Plan 01 | Requirement: REAS-06

Implements:
    build_graph() — Assemble 7-node linear StateGraph with all Phase 6 nodes
                    plus compose_report_node (implemented in Plan 02).
    run_graph()   — Async: compile graph with AsyncPostgresSaver checkpointer
                    using langgraph schema search path, then invoke graph.

Design decisions (locked):
- Node names: "macro_regime", "valuation", "structure", "conflict",
  "entry_quality", "grounding_check", "compose_report"
- Linear edge topology: START→macro_regime→valuation→structure→conflict
  →entry_quality→grounding_check→compose_report→END (8 edges total)
- Checkpointer uses: db_uri + "?options=-csearch_path%3Dlanggraph"
  (URL-encoded = sign, Phase 3 langgraph schema decision)
- compose_report_node real implementation added in Plan 02 (replaces placeholder)
- run_graph() deepcopies state before mutation to avoid caller side-effects
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from langgraph.graph import StateGraph, START, END

from reasoning.app.nodes.state import ReportState
from reasoning.app.nodes import (
    macro_regime_node,
    valuation_node,
    structure_node,
    conflicting_signals_handler,
    entry_quality_node,
    grounding_check_node,
)
from reasoning.app.pipeline.compose_report import compose_report_node


# ---------------------------------------------------------------------------
# build_graph()
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """
    Assemble the 7-node linear LangGraph StateGraph.

    Nodes (in execution order):
        1. macro_regime     — MacroRegimeOutput (Phase 6 Plan 01)
        2. valuation        — ValuationOutput   (Phase 6 Plan 02)
        3. structure        — StructureOutput   (Phase 6 Plan 01)
        4. conflict         — ConflictOutput    (Phase 6 Plan 04)
        5. entry_quality    — EntryQualityOutput (Phase 6 Plan 04)
        6. grounding_check  — GroundingResult   (Phase 6 Plan 05)
        7. compose_report   — ReportOutput      (Phase 7 Plan 02 — placeholder)

    Edges (8 total, linear):
        START → macro_regime → valuation → structure → conflict
        → entry_quality → grounding_check → compose_report → END

    Returns:
        StateGraph: Compiled-ready graph. Call .compile() to get a runnable graph.
        For unit tests, call .compile() with no arguments (checkpointer=None).
        For production, compile with an AsyncPostgresSaver checkpointer via run_graph().
    """
    graph = StateGraph(ReportState)

    # Add all 7 nodes
    graph.add_node("macro_regime", macro_regime_node)
    graph.add_node("valuation", valuation_node)
    graph.add_node("structure", structure_node)
    graph.add_node("conflict", conflicting_signals_handler)
    graph.add_node("entry_quality", entry_quality_node)
    graph.add_node("grounding_check", grounding_check_node)
    graph.add_node("compose_report", compose_report_node)

    # Add 8 linear edges
    graph.add_edge(START, "macro_regime")
    graph.add_edge("macro_regime", "valuation")
    graph.add_edge("valuation", "structure")
    graph.add_edge("structure", "conflict")
    graph.add_edge("conflict", "entry_quality")
    graph.add_edge("entry_quality", "grounding_check")
    graph.add_edge("grounding_check", "compose_report")
    graph.add_edge("compose_report", END)

    return graph


# ---------------------------------------------------------------------------
# run_graph()
# ---------------------------------------------------------------------------


async def run_graph(
    state: ReportState,
    language: str,
    thread_id: str,
    db_uri: str,
    queue: asyncio.Queue | None = None,
) -> ReportState:
    """
    Compile the graph with AsyncPostgresSaver and invoke it with the given state.

    Args:
        state:     Pre-fetched ReportState dict from prefetch() (or equivalent).
        language:  Report language code — "vi" or "en". Set on state before invocation.
        thread_id: LangGraph checkpoint thread ID for resume/replay support.
        db_uri:    PostgreSQL connection URI (without schema override).
        queue:     Optional asyncio.Queue for SSE progress events. When provided,
                   uses astream(stream_mode="tasks") to emit node_start and
                   node_complete events per node. When None, uses ainvoke (fast path).

    Returns:
        The final ReportState after all nodes have executed.

    Connection string:
        db_uri + "?options=-csearch_path%3Dlanggraph"
        This targets the langgraph schema created in Phase 3 Plan 03
        (raw DDL, not AsyncPostgresSaver.setup() — public schema only).
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # Deep-copy to avoid mutating the caller's state dict
    working_state = copy.deepcopy(dict(state))
    working_state["language"] = language

    # Build connection string with langgraph schema search path
    # URL-encoded: = → %3D (so -csearch_path=langgraph → -csearch_path%3Dlanggraph)
    conn_str = db_uri + "?options=-csearch_path%3Dlanggraph"

    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        compiled = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        if queue is None:
            # Fast path: no streaming needed — use ainvoke (no regression)
            result = await compiled.ainvoke(working_state, config=config)
            return result

        # Streaming path: emit node_start and node_complete events via astream
        async for item in compiled.astream(working_state, config=config, stream_mode="tasks"):
            data = item if isinstance(item, dict) else {}
            # TasksStreamPart: {"type": "tasks", "ns": ..., "data": TaskPayload|TaskResultPayload}
            payload = data.get("data", {})
            node_name = payload.get("name") if isinstance(payload, dict) else None
            if node_name:
                if "input" in payload:  # TaskPayload — start event
                    await queue.put({"event_type": "node_start", "node": node_name})
                elif "result" in payload or "error" in payload:  # TaskResultPayload — finish
                    error = payload.get("error")
                    await queue.put({
                        "event_type": "node_complete",
                        "node": node_name,
                        "error": str(error) if error else None,
                    })

        # Retrieve final state from checkpoint after stream exhausted
        # astream does NOT return final state directly — must use aget_state
        final = await compiled.aget_state(config)
        return final.values
