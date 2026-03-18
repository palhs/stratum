---
phase: 13-report-generation-with-sse-progress
plan: "01"
subsystem: reasoning-backend
tags: [sse, langgraph, streaming, pipeline, backend]
dependency_graph:
  requires: []
  provides: [run_graph-queue-param, generate_report-sse_queue-param, per-node-sse-events]
  affects: [reasoning/app/pipeline/graph.py, reasoning/app/pipeline/__init__.py, reasoning/app/routers/reports.py]
tech_stack:
  added: []
  patterns: [langgraph-astream-tasks, asyncio-queue-injection, aget_state-after-astream]
key_files:
  created: []
  modified:
    - reasoning/app/pipeline/graph.py
    - reasoning/app/pipeline/__init__.py
    - reasoning/app/routers/reports.py
    - reasoning/tests/api/test_stream.py
decisions:
  - "ainvoke preserved as fast-path when queue=None — en run gets no queue, vi run gets sse_queue"
  - "aget_state(config) called after astream exhausted to retrieve final ReportState (astream does not return state)"
  - "queue forwarded from _run_pipeline to generate_report as sse_queue kwarg — no architectural change"
metrics:
  duration: "3 min"
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_modified: 4
---

# Phase 13 Plan 01: Backend SSE Per-Node Events Summary

**One-liner:** LangGraph astream(stream_mode="tasks") wired into run_graph with asyncio.Queue injection, emitting node_start/node_complete SSE events for all 7 pipeline nodes.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add queue param to run_graph/generate_report, emit per-node events | 3000fe5 | graph.py, __init__.py, reports.py |
| 2 | Add SSE stream tests for per-node events | a1f1878 | tests/api/test_stream.py |

## What Was Built

### Task 1: Backend streaming changes

**`reasoning/app/pipeline/graph.py`** — `run_graph()` gains `queue: asyncio.Queue | None = None`:
- `queue is None` (fast path): existing `ainvoke` call preserved — no regression for en run or non-SSE callers
- `queue is not None` (streaming path): uses `astream(stream_mode="tasks")` to iterate `TaskPayload` and `TaskResultPayload` events. For each item with a `name` key: if it has `"input"` key → emit `node_start`, if it has `"result"` or `"error"` key → emit `node_complete`. After loop exhausted, calls `await compiled.aget_state(config)` to retrieve final state (astream does not return state directly).

**`reasoning/app/pipeline/__init__.py`** — `generate_report()` gains `sse_queue: asyncio.Queue | None = None`:
- Vi run: `run_graph(..., queue=sse_queue)` — forwards the SSE queue for node-level events
- En run: `run_graph(..., )` — no queue (vi already showed all 7 steps; avoids 14-event duplication)

**`reasoning/app/routers/reports.py`** — `_run_pipeline()`:
- Gets `queue = app_state.job_queues.get(job_id)` at call time
- Passes `sse_queue=queue` to the `_fn(...)` call

### Task 2: New SSE tests

Added 3 new tests to `reasoning/tests/api/test_stream.py`:
- `test_sse_stream_node_start_and_complete_events`: Pre-populates queue with node_start/node_complete for 2 nodes, asserts 4 node_transition SSE events received with correct event_type and node fields
- `test_sse_stream_node_failure_event`: Asserts error field propagated in node_complete event ("LLM timeout")
- `test_sse_stream_all_seven_nodes`: Pre-populates all 7 node pairs (14 events), asserts 14 node_transition events and all 7 node names present

All 4 existing SSE tests still pass (backwards compatible).

## Verification Results

```
reasoning/tests/api/test_stream.py: 7 passed (4 existing + 3 new)
reasoning/tests/api/test_reports.py: 8 passed (no regression)
run_graph has queue param: OK
generate_report has sse_queue param: OK
```

## Decisions Made

1. **ainvoke preserved as fast path** — `if queue is None: result = await compiled.ainvoke(...)`. This keeps the en run fast (no streaming overhead) and preserves any non-SSE callers.

2. **aget_state(config) after astream** — LangGraph's `astream` is an async generator that yields stream parts but does not return the final state. After exhausting the loop, `await compiled.aget_state(config)` retrieves the final checkpoint state and `final.values` is returned as `ReportState`.

3. **vi-only queue forwarding** — Passing `sse_queue` to vi run only avoids 14 events appearing for users (7 nodes × 2 languages). The vi run runs first and represents the full analytical work.

4. **queue retrieved at call time in _run_pipeline** — Added `queue = app_state.job_queues.get(job_id)` immediately before the `_fn(...)` call. The existing `_emit()` helper already retrieved queue per-call; this is consistent.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- FOUND: reasoning/app/pipeline/graph.py
- FOUND: reasoning/app/pipeline/__init__.py
- FOUND: reasoning/app/routers/reports.py
- FOUND: reasoning/tests/api/test_stream.py

Commits exist:
- FOUND: 3000fe5 (feat(13-01): add queue param...)
- FOUND: a1f1878 (test(13-01): add SSE stream tests...)
