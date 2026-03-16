"""
reasoning/app/pipeline — LangGraph StateGraph assembly and two-stage pipeline.
Phase 7 | Plan 01 | Requirement: REAS-06

Exports:
    build_graph  — Build the 7-node linear StateGraph (no checkpointer, for compilation)
    run_graph    — Async: compile graph with AsyncPostgresSaver and invoke it
    prefetch     — Two-stage prefetch: retrieve all data before graph runs

Note: generate_report (end-to-end orchestrator) is added in Plan 05.
"""

from reasoning.app.pipeline.graph import build_graph, run_graph
from reasoning.app.pipeline.prefetch import prefetch

__all__ = [
    "build_graph",
    "run_graph",
    "prefetch",
]
