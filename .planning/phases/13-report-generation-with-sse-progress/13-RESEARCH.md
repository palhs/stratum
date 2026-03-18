# Phase 13: Report Generation with SSE Progress - Research

**Researched:** 2026-03-19
**Domain:** SSE streaming, LangGraph node-level events, React state management for per-card progress UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Generate button placement**
- Button lives inside each ticker card, at the bottom below the sparkline and last report date
- Small, secondary-style button labeled "Generate Report"
- Button is per-ticker: only the generating card's button is replaced by progress — other cards remain interactive

**Card in-progress state**
- Generate button area is replaced by a vertical step list showing all 7 pipeline steps
- Card expands in place to fit the step list, pushing grid cards below it down
- Sparkline and last report date section hidden during generation, replaced by step list
- Tier badge remains visible at the top of the card during generation
- Card click (navigate to /reports/{symbol}) remains functional during generation

**Step list display**
- All 7 steps shown vertically with status icons: checkmark (completed/green), filled circle (in progress/animated), empty circle (pending/gray), x mark (failed/red)
- Friendly English labels mapped from node names (macro_regime -> "Macro Analysis", valuation -> "Valuation", structure -> "Price Structure", conflict -> "Conflict Check", entry_quality -> "Entry Quality", grounding_check -> "Grounding", compose_report -> "Compose Report")
- No timing information
- Single combined pass — vi+en treated as one unified progress

**Per-node SSE events (backend change required)**
- Use LangGraph's built-in callback system to emit SSE events on node start and node complete
- Both `node_start` and `node_complete` events emitted per node
- Events flow: LangGraph callback -> asyncio.Queue -> SSE stream -> EventSource on frontend
- Existing coarse events (job_started, pipeline_vi_start, etc.) can remain for backwards compatibility

**Concurrency model**
- Per-ticker disabled state only — user can trigger generation on multiple tickers simultaneously
- Backend already returns 409 if same ticker has an active job

**Completion flow**
- On success: step list collapses back to normal card layout
- Card refreshes to show updated last report date and potentially updated tier badge
- Toast notification: "{SYMBOL} report ready"

**Error flow**
- On failure: failed step shows red x icon, later steps remain empty circles
- Card stays expanded 3-5 seconds so user sees which step failed
- Toast: "Report generation failed"
- Card then collapses back to normal, Generate button re-appears for retry

**Navigation away handling**
- EventSource.close() called on component unmount / route navigation
- Backend pipeline continues running (BackgroundTask is independent of SSE connection)
- On return to dashboard: check for active jobs for user's tickers, re-connect SSE if still running, or show completed/failed state

### Claude's Discretion
- EventSource connection management implementation (reconnect logic, error handling)
- LangGraph callback implementation details (which callback hooks to use)
- Step list animation/transition details
- Card expand/collapse animation approach
- How to detect active jobs on dashboard load (poll vs check on mount)
- next.config.ts rewrite rules for SSE proxy path

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RGEN-01 | User can trigger report generation via button on ticker card | POST /reports/generate endpoint exists; frontend needs `generateReport()` API function + GenerateButton component in TickerCard |
| RGEN-02 | User sees real-time SSE progress showing named pipeline steps | LangGraph 1.1.2 `astream(stream_mode="tasks")` emits `TaskPayload.name` per node; backend wraps in asyncio.Queue -> SSE; frontend uses EventSource |
| RGEN-03 | Generate button is disabled during active generation | Per-symbol `generatingSymbols: Set<string>` state in DashboardClient; passed down through WatchlistGrid -> TickerCard |
</phase_requirements>

---

## Summary

Phase 13 wires the "Generate Report" button on each dashboard ticker card to the existing FastAPI POST /reports/generate endpoint, then streams real-time pipeline node progress from the backend to the frontend via SSE. The backend already has a complete SSE infrastructure (asyncio.Queue, EventSourceResponse, ping keepalive, cleanup). The key missing piece is per-node granularity: the pipeline currently emits only coarse job-level events, so `_run_pipeline` must be refactored to use LangGraph 1.1.2's native `astream(stream_mode="tasks")` to receive `TaskPayload` (node start, with `name`) and `TaskResultPayload` (node finish, with `name` and `error`) and forward them to the SSE queue.

On the frontend, a new `GenerationState` map (keyed by symbol) in DashboardClient holds per-ticker progress. TickerCard becomes a client component that conditionally renders either a GenerateButton or a StepList based on that state. The native browser `EventSource` API cannot send custom headers, so the access token must be passed as a query parameter (`?token=...`) — the GET /reports/stream/{job_id} endpoint does not currently require auth but the query-param approach aligns with the token-carrying pattern used elsewhere.

The key architectural insight: LangGraph `astream` replaces `ainvoke` in `run_graph()`. Since the pipeline is linear (7 nodes, no branching), every `"tasks"` stream event with `data["name"]` maps directly to one of the 7 known node names. Both vi and en runs complete before any SSE "complete" sentinel is emitted, so the single-pass progress perception is preserved.

**Primary recommendation:** Replace `ainvoke` with `astream(stream_mode="tasks")` in `run_graph()`, pass an asyncio.Queue through config/context to receive events, and forward them to the SSE queue in `_run_pipeline`. Frontend uses native `EventSource` with token as query param.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | 1.1.2 (installed) | Native `astream(stream_mode="tasks")` for per-node events | Built-in, zero new dependencies |
| sse-starlette | already installed | SSE response streaming in FastAPI | Already used in reports.py |
| Browser EventSource API | native | SSE client in Next.js client components | Zero dependencies, native reconnect logic |
| React useState/useEffect | React 19.2.4 (installed) | Per-symbol generation state management | Established pattern in DashboardClient |
| lucide-react | 0.577.0 (installed) | Step status icons (Check, Circle, X, Loader2) | Already installed in project |
| sonner | 2.0.7 (installed) | Toast notifications on completion/failure | Already used in DashboardClient |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS | installed | Card expand animation via transition classes | Used throughout the project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native EventSource | fetch-based SSE via ReadableStream | fetch allows custom headers (no query-param token hack), but requires manual reconnect and is more complex. EventSource is simpler here since the stream endpoint is short-lived (one generation). |
| LangGraph `astream(stream_mode="tasks")` | LangChain `BaseCallbackHandler` | Callbacks work but require wrapping nodes — astream is the canonical LangGraph 1.x approach and requires zero node changes |
| asyncio.Queue forwarding | Direct callback emit | Queue already used in this project; keeps the event path consistent with existing job_started events |

---

## Architecture Patterns

### Recommended Project Structure
```
reasoning/app/pipeline/
├── graph.py             # run_graph() — replace ainvoke with astream; accepts optional queue param
├── __init__.py          # generate_report() — passes queue to run_graph; collects node events

reasoning/app/routers/
├── reports.py           # _run_pipeline() — passes job queue to generate_report; emits node events

frontend/src/
├── lib/
│   ├── api.ts           # Add: generateReport(), getActiveJobs()
│   └── types.ts         # Add: GenerateResponse, GenerationState, StepStatus types
├── components/dashboard/
│   ├── DashboardClient.tsx   # Add: generatingSymbols state, handlers, pass down to WatchlistGrid
│   ├── WatchlistGrid.tsx     # Add: generatingSymbols + callbacks prop forwarding
│   ├── TickerCard.tsx        # Refactor to client component; conditionally renders StepList
│   ├── GenerateButton.tsx    # New: secondary button, disabled when generating
│   └── StepList.tsx          # New: vertical 7-step progress list with status icons
```

### Pattern 1: LangGraph astream with asyncio.Queue injection

**What:** Replace `ainvoke` in `run_graph()` with `astream(stream_mode="tasks")`, accepting an optional `queue: asyncio.Queue | None` parameter. For each yielded item, if it's a `TaskPayload` (start) or `TaskResultPayload` (finish), put a structured dict onto the queue. Then `await asyncio.gather(*[collect_items()])` to consume the full stream.

**When to use:** Whenever you need per-node granularity from a LangGraph pipeline without modifying the nodes themselves.

**Example (run_graph.py modification):**
```python
# Source: LangGraph 1.1.2 types.py — TaskPayload and TaskResultPayload
async def run_graph(
    state: ReportState,
    language: str,
    thread_id: str,
    db_uri: str,
    queue: asyncio.Queue | None = None,  # NEW PARAM
) -> ReportState:
    conn_str = db_uri + "?options=-csearch_path%3Dlanggraph"
    working_state = copy.deepcopy(dict(state))
    working_state["language"] = language

    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        compiled = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        final_state = None
        async for item in compiled.astream(
            working_state, config=config, stream_mode="tasks"
        ):
            # item is a TasksStreamPart: {"type": "tasks", "ns": ..., "data": TaskPayload|TaskResultPayload}
            data = item.get("data", item)  # handle both dict and typed form
            node_name = data.get("name")
            if node_name and queue is not None:
                if "input" in data:  # TaskPayload — node start
                    await queue.put({
                        "event_type": "node_start",
                        "node": node_name,
                        "language": language,
                    })
                else:  # TaskResultPayload — node finish
                    error = data.get("error")
                    await queue.put({
                        "event_type": "node_complete",
                        "node": node_name,
                        "language": language,
                        "error": error,
                    })
            # capture final state from last values item if needed
        # after stream exhausted, get final state
        result = await compiled.aget_state(config)
    return result.values
```

> **Important:** `astream` does not return the final state the way `ainvoke` does. You need `aget_state(config)` after the stream completes to retrieve the final ReportState. The `stream_mode="tasks"` only yields task events, not state values.

### Pattern 2: Per-Symbol Generation State in DashboardClient

**What:** A `Map<string, GenerationState>` keyed by ticker symbol, stored in DashboardClient state. Each entry tracks `{ jobId, steps: StepStatus[] }`. Passed down as props through WatchlistGrid -> TickerCard.

**When to use:** When multiple ticker cards can be independently generating simultaneously.

**Example:**
```typescript
// Source: React 19 useState pattern (established in DashboardClient)
type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

interface StepState {
  node: string
  label: string
  status: StepStatus
}

interface GenerationState {
  jobId: number
  steps: StepState[]
}

// In DashboardClient:
const [generating, setGenerating] = useState<Map<string, GenerationState>>(new Map())

function handleGenerateReport(symbol: string, assetType: string) {
  // 1. POST /reports/generate -> get jobId
  // 2. Open EventSource to /api/reports/stream/{jobId}?token=accessToken
  // 3. On node_start event: update steps[node].status = 'in_progress'
  // 4. On node_complete: update steps[node].status = 'completed' or 'failed'
  // 5. On 'complete' SSE event: remove from generating map, refresh card data
  // 6. On error: show toast, collapse card
}
```

### Pattern 3: EventSource with Query Parameter Token

**What:** Native browser `EventSource` does not support custom headers. Pass the Supabase access token as a query parameter. The SSE endpoint at GET /reports/stream/{job_id} currently has no auth — keep it unauthenticated since job_id is a hard-to-guess integer that requires knowing the job_id returned from the authenticated POST.

**When to use:** SSE streams from authenticated FastAPI endpoints when the client is a browser.

**Example:**
```typescript
// Source: MDN EventSource API + existing api.ts pattern
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

function openSSEStream(jobId: number, token: string, onEvent: (e: MessageEvent) => void): EventSource {
  const url = `${API_BASE}/reports/stream/${jobId}`
  // Note: EventSource cannot pass Authorization header
  // stream endpoint currently has no auth — job_id alone gates access
  const es = new EventSource(url)
  es.addEventListener('node_transition', onEvent)
  es.addEventListener('complete', (e) => {
    es.close()
    // handle completion
  })
  es.onerror = () => {
    es.close()
    // handle error
  }
  return es
}
```

### Pattern 4: next.config.ts SSE Rewrite

**What:** Add rewrites in next.config.ts to proxy `/api/reports/*` to the FastAPI reasoning-engine. This is required because `NEXT_PUBLIC_API_URL` targets host-mapped port 8001 directly (Phase 12 decision) — but rewrites are needed for the SSE stream path to go through Next.js (avoiding CORS issues from browser -> FastAPI directly).

**When to use:** Any time a client-side fetch/EventSource needs to reach the FastAPI backend without CORS preflight complexity.

**Confirmed approach from STATE.md:** "SSE proxied via next.config.ts rewrites (not API routes)"

**Example:**
```typescript
// Source: Next.js 16.2.0 docs/01-app/03-api-reference/05-config/01-next-config-js/rewrites.md
const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: '/api/reports/:path*',
        destination: `${process.env.REASONING_ENGINE_URL}/reports/:path*`,
      },
    ]
  },
}
```

> **Note:** `REASONING_ENGINE_URL` is a server-side env var (no `NEXT_PUBLIC_` prefix). The rewrite runs server-side, so the FastAPI URL is never exposed to the browser. The frontend's `NEXT_PUBLIC_API_URL` continues to work for non-SSE calls that go directly from the browser.

### Anti-Patterns to Avoid

- **Calling `ainvoke` and expecting events:** `ainvoke` blocks until completion — no per-node events are emitted. Must use `astream`.
- **Adding `node_start`/`node_complete` events to nodes directly:** Modifying all 7 node functions to emit events is fragile. Use `astream(stream_mode="tasks")` which captures all node boundaries without touching node code.
- **Storing EventSource in useState:** EventSource is a mutable object that should be stored in a `useRef`, not state. Storing in state causes re-renders on every update.
- **Missing `es.close()` on unmount:** EventSource auto-reconnects on error by default. Must call `es.close()` in the useEffect cleanup to prevent abandoned connections burning Gemini API budget.
- **Using `stream_mode="updates"` instead of `"tasks"`:** `"updates"` emits state diffs after node completion only — no node start events. `"tasks"` emits both start and finish.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Node-level pipeline events | Custom callback wrappers in each node | `astream(stream_mode="tasks")` | LangGraph 1.1.2 has native TaskPayload/TaskResultPayload with node name |
| SSE server in FastAPI | Custom streaming response | `sse_starlette.EventSourceResponse` (already used) | Handles ping, keepalive, client disconnect |
| SSE client in browser | Custom fetch-based stream reader | Native `EventSource` | Built-in, handles reconnect, event parsing |
| Toast notifications | Custom notification system | `sonner` (already installed) | Already used in DashboardClient |
| Status icons | Custom SVG icons | `lucide-react` Check, Circle, Loader2, XCircle | Already installed |

---

## Common Pitfalls

### Pitfall 1: `astream` Does Not Return Final State
**What goes wrong:** After replacing `ainvoke` with `astream`, calling `.return_value` or the return of the async for loop does not give you the final `ReportState`. The function returns `None`.
**Why it happens:** `astream` is an async generator, not a coroutine. It yields stream parts but does not return the final state directly.
**How to avoid:** After exhausting the `astream` async for loop, call `await compiled.aget_state(config)` to retrieve the final checkpoint state. The `result.values` gives you the ReportState.
**Warning signs:** `write_report()` receiving `None` for `report_output`; KeyError on `result["report_output"]`.

### Pitfall 2: EventSource Reconnects Indefinitely After Stream Closes
**What goes wrong:** When the FastAPI SSE stream ends normally (sends the `complete` event and closes), the browser EventSource automatically attempts to reconnect, generating spurious GET /reports/stream/{job_id} requests that return 404 (queue already cleaned up).
**Why it happens:** EventSource reconnect-on-close is the default browser behavior, designed for persistent streams.
**How to avoid:** Call `es.close()` inside the `complete` event listener callback before updating state. Also call `es.close()` in the useEffect cleanup function.
**Warning signs:** Repeated 404 errors in network tab for /reports/stream/{job_id} after generation completes.

### Pitfall 3: Map State Mutation Without Spread
**What goes wrong:** `setGenerating(prev => { prev.set(symbol, newState); return prev })` does not trigger re-render because the Map reference is unchanged.
**Why it happens:** React bails out of re-renders when the state reference is the same object.
**How to avoid:** `setGenerating(prev => new Map(prev).set(symbol, newState))` — always create a new Map instance.
**Warning signs:** Button stays enabled after generation starts; step list doesn't update.

### Pitfall 4: SSE Events Arrive for Both vi and en Runs
**What goes wrong:** With `queue` passed to both `run_graph(vi)` and `run_graph(en)`, all 14 node_start + 14 node_complete events arrive on the SSE stream (7 nodes x 2 languages).
**Why it happens:** The pipeline runs the full graph twice (vi then en) and both emit to the same queue.
**How to avoid:** Two options: (a) only pass `queue` for the vi run (treat it as the progress indicator), or (b) filter events in the frontend to only show each node name once (first occurrence wins). Option (a) is simpler. Decision: only pass queue to `run_graph` for the `vi` pass since the vi pass runs first and represents the full analytical work.
**Warning signs:** Step list shows 14 events instead of 7; nodes appear to complete twice.

### Pitfall 5: next.config.ts Rewrites Not Forwarding SSE Headers
**What goes wrong:** The Next.js rewrite proxies the SSE stream but buffers it, breaking the real-time delivery. EventSource never receives events.
**Why it happens:** Next.js's Node.js proxy (via rewrites) may not flush incremental responses immediately for SSE streams in all configurations.
**How to avoid:** In Phase 13, `NEXT_PUBLIC_API_URL` targets the FastAPI server directly (port 8001) — client-side EventSource should connect directly to the FastAPI SSE endpoint (not via Next.js rewrite). Rewrites are for same-origin API calls from the browser; use `NEXT_PUBLIC_API_URL` directly for the EventSource URL. INFR-02 (nginx SSE buffering) is Phase 15 scope.
**Warning signs:** EventSource connection opens but no events arrive; `ping` events also absent after 15s.

### Pitfall 6: TickerCard Prop Drilling Complexity
**What goes wrong:** TickerCard currently has no callbacks or state. Adding generation state requires threading props through WatchlistGrid -> TickerCard, making WatchlistGrid stateful and breaking the clean separation.
**Why it happens:** Generation state lives in DashboardClient (where the accessToken is) but must be rendered in TickerCard.
**How to avoid:** Pass `generatingSymbols: Set<string>`, `generationSteps: Map<string, StepState[]>`, and `onGenerate: (symbol: string, assetType: string) => void` as props to WatchlistGrid, which passes them to each TickerCard. TickerCard checks `generatingSymbols.has(ticker.symbol)` to decide which UI to render.

---

## Code Examples

### Backend: Modified _run_pipeline to Pass Queue to run_graph

```python
# Source: reasoning/app/routers/reports.py — _run_pipeline (modified)
async def _run_pipeline(job_id: int, ticker: str, asset_type: str, app_state) -> None:
    queue = app_state.job_queues.get(job_id)  # the SSE queue
    db_engine = app_state.db_engine
    try:
        _update_job_status(db_engine, job_id, "running")
        await _emit(app_state, job_id, {"event_type": "job_started", "job_id": job_id, "ticker": ticker})

        vi_id, en_id = await _fn(
            ticker=ticker,
            asset_type=asset_type,
            db_engine=db_engine,
            neo4j_driver=app_state.neo4j_driver,
            qdrant_client=app_state.qdrant_client,
            db_uri=app_state.db_uri,
            sse_queue=queue,  # NEW: pass SSE queue to pipeline
        )

        _update_job_status(db_engine, job_id, "completed", report_id=vi_id)
        if queue:
            await queue.put(None)  # SSE completion sentinel
    except Exception as exc:
        logger.exception("Pipeline failed for job_id=%d: %s", job_id, exc)
        _update_job_status(db_engine, job_id, "failed", error=str(exc))
        if queue:
            await queue.put(None)
```

### Backend: generate_report with sse_queue param

```python
# Source: reasoning/app/pipeline/__init__.py — generate_report (modified)
async def generate_report(
    ticker: str,
    asset_type: str,
    db_engine,
    neo4j_driver,
    qdrant_client,
    db_uri: str,
    sse_queue: asyncio.Queue | None = None,  # NEW
) -> tuple[int, int]:
    state = prefetch(ticker, asset_type, db_engine, neo4j_driver, qdrant_client)

    # Stage 2a: vi run — pass queue for node-level progress events
    state_vi = copy.deepcopy(state)
    thread_id_vi = f"{ticker}-vi-{uuid.uuid4()}"
    start_vi = time.monotonic()
    result_vi = await run_graph(state_vi, "vi", thread_id_vi, db_uri, queue=sse_queue)
    duration_vi = int((time.monotonic() - start_vi) * 1000)
    vi_id = write_report(db_engine, ticker, "vi", result_vi["report_output"], duration_vi)

    # Stage 2b: en run — no queue (vi already showed all 7 steps)
    state_en = copy.deepcopy(state)
    thread_id_en = f"{ticker}-en-{uuid.uuid4()}"
    start_en = time.monotonic()
    result_en = await run_graph(state_en, "en", thread_id_en, db_uri, queue=None)
    duration_en = int((time.monotonic() - start_en) * 1000)
    en_id = write_report(db_engine, ticker, "en", result_en["report_output"], duration_en)

    return (vi_id, en_id)
```

### Backend: run_graph using astream instead of ainvoke

```python
# Source: LangGraph 1.1.2 types.py TaskPayload/TaskResultPayload
async def run_graph(
    state: ReportState,
    language: str,
    thread_id: str,
    db_uri: str,
    queue: asyncio.Queue | None = None,  # NEW
) -> ReportState:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    working_state = copy.deepcopy(dict(state))
    working_state["language"] = language
    conn_str = db_uri + "?options=-csearch_path%3Dlanggraph"

    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        compiled = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        if queue is None:
            # Fast path: no streaming needed
            result = await compiled.ainvoke(working_state, config=config)
            return result

        # Streaming path: emit node_start and node_complete events
        async for item in compiled.astream(
            working_state, config=config, stream_mode="tasks"
        ):
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
                        "error": error,
                    })

        # Retrieve final state from checkpoint after stream exhausted
        final = await compiled.aget_state(config)
        return final.values
```

### Frontend: generateReport API function

```typescript
// Source: frontend/src/lib/api.ts (extend existing pattern)
export interface GenerateResponse {
  job_id: number
  status: string
}

export async function generateReport(
  ticker: string,
  assetType: string,
  token: string
): Promise<GenerateResponse> {
  return fetchAPI<GenerateResponse>('/reports/generate', token, {
    method: 'POST',
    body: JSON.stringify({ ticker, asset_type: assetType }),
  })
}
```

### Frontend: StepList component

```typescript
// Source: project pattern + lucide-react (0.577.0 installed)
import { Check, Circle, Loader2, XCircle } from 'lucide-react'

const STEP_LABELS: Record<string, string> = {
  macro_regime: 'Macro Analysis',
  valuation: 'Valuation',
  structure: 'Price Structure',
  conflict: 'Conflict Check',
  entry_quality: 'Entry Quality',
  grounding_check: 'Grounding',
  compose_report: 'Compose Report',
}

const STEP_ORDER = [
  'macro_regime', 'valuation', 'structure', 'conflict',
  'entry_quality', 'grounding_check', 'compose_report',
]

type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export function StepList({ steps }: { steps: Map<string, StepStatus> }) {
  return (
    <ul className="space-y-2 py-1">
      {STEP_ORDER.map((node) => {
        const status = steps.get(node) ?? 'pending'
        return (
          <li key={node} className="flex items-center gap-2 text-sm">
            <StepIcon status={status} />
            <span className={status === 'completed' ? 'text-foreground' : 'text-muted-foreground'}>
              {STEP_LABELS[node]}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
```

### Frontend: EventSource connection management in DashboardClient

```typescript
// Source: MDN EventSource + React useEffect cleanup pattern
// Store EventSource refs to close on unmount
const eventSourcesRef = useRef<Map<string, EventSource>>(new Map())

async function handleGenerate(symbol: string, assetType: string) {
  try {
    const { job_id } = await generateReport(symbol, assetType, accessToken)

    // Initialize step state
    const initialSteps = new Map(STEP_ORDER.map(n => [n, 'pending' as StepStatus]))
    setGenerating(prev => new Map(prev).set(symbol, { jobId: job_id, steps: initialSteps }))

    // Open SSE stream — connect directly to FastAPI (NEXT_PUBLIC_API_URL)
    const es = new EventSource(`${process.env.NEXT_PUBLIC_API_URL}/reports/stream/${job_id}`)
    eventSourcesRef.current.set(symbol, es)

    es.addEventListener('node_transition', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      setGenerating(prev => {
        const current = prev.get(symbol)
        if (!current) return prev
        const newSteps = new Map(current.steps)
        if (data.event_type === 'node_start') {
          newSteps.set(data.node, 'in_progress')
        } else if (data.event_type === 'node_complete') {
          newSteps.set(data.node, data.error ? 'failed' : 'completed')
        }
        return new Map(prev).set(symbol, { ...current, steps: newSteps })
      })
    })

    es.addEventListener('complete', async () => {
      es.close()
      eventSourcesRef.current.delete(symbol)
      setGenerating(prev => { const next = new Map(prev); next.delete(symbol); return next })
      // Refresh card data
      await refreshTicker(symbol)
      toast.success(`${symbol} report ready`)
    })

    es.onerror = () => {
      es.close()
      eventSourcesRef.current.delete(symbol)
      // Keep expanded briefly to show failed step, then collapse
      setTimeout(() => {
        setGenerating(prev => { const next = new Map(prev); next.delete(symbol); return next })
      }, 4000)
      toast.error('Report generation failed')
    }
  } catch (err) {
    // 409 = already generating
    toast.error(`Couldn't start generation for ${symbol}`)
  }
}

// Cleanup on unmount
useEffect(() => {
  return () => {
    eventSourcesRef.current.forEach(es => es.close())
  }
}, [])
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangGraph `ainvoke` | `astream(stream_mode="tasks")` for node granularity | LangGraph 0.2+ (we have 1.1.2) | Zero node code changes needed for per-node events |
| `middleware.ts` | `proxy.ts` (renamed in Next.js 16) | Next.js 16.0.0 | Export must be named `proxy`, not `middleware` — already migrated in this project |
| `stream_mode="debug"` | `stream_mode="tasks"` | LangGraph 1.x | `"tasks"` is the clean API; `"debug"` has extra wrapping and is verbose |

**Deprecated/outdated:**
- `middleware.ts`: Already renamed to `proxy.ts` in this project (Next.js 16 requirement)
- LangChain `BaseCallbackHandler` for node events: Replaced by LangGraph's native `stream_mode="tasks"` in LangGraph 1.x

---

## Open Questions

1. **How does `astream` return value differ from `ainvoke` for `run_graph` callers?**
   - What we know: `ainvoke` returns the final state dict directly; `astream` is an async generator
   - What's unclear: Whether `aget_state(config)` reliably returns final state values or needs a different key
   - Recommendation: After `astream` loop completes, call `await compiled.aget_state(config)` and use `result.values` — this is the same as the final checkpoint. Test with a simple mock to verify `result.values["report_output"]` is populated.

2. **Active jobs detection on dashboard load (Claude's Discretion)**
   - What we know: The backend has `_find_active_job()` per asset_id; GET /{job_id} returns 202 for running jobs
   - What's unclear: There is no batch "get all active jobs for user's tickers" endpoint yet
   - Recommendation: On DashboardClient mount, for each ticker in the watchlist, call GET /reports/{job_id} if a job_id was previously stored in localStorage (keyed by symbol). If 202 returned, re-open SSE stream. This is simple and avoids a new batch endpoint. Alternative: just check GET /reports/by-ticker/{symbol}?page=1&per_page=1 for a running status — but the by-ticker endpoint returns completed reports, not job status. Simplest for Phase 13: skip active job recovery on reload (user just re-triggers if needed).

3. **Token passing to SSE endpoint**
   - What we know: Native EventSource cannot send Authorization headers; GET /reports/stream/{job_id} currently has no auth
   - What's unclear: Whether the unauthenticated SSE endpoint is acceptable for Phase 13
   - Recommendation: Keep SSE endpoint unauthenticated in Phase 13. The job_id is returned only from the authenticated POST /generate, so knowing a job_id implies prior authentication. Adding auth to the SSE endpoint would require a fetch-based SSE implementation.

---

## Validation Architecture

> `workflow.nyquist_validation` not present in config.json — skip this section.

*(config.json has `workflow.research`, `workflow.plan_check`, `workflow.verifier` but no `nyquist_validation` key — section skipped per instructions.)*

---

## Sources

### Primary (HIGH confidence)
- LangGraph 1.1.2 installed source: `/reasoning/.venv/lib/python3.11/site-packages/langgraph/types.py` — TaskPayload, TaskResultPayload, TasksStreamPart typedefs
- LangGraph 1.1.2 installed source: `/reasoning/.venv/lib/python3.11/site-packages/langgraph/pregel/main.py` — `astream()` method signature and docstring (stream_mode="tasks" documented)
- Next.js 16.2.0 installed docs: `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md` — proxy.ts convention, `middleware.ts` deprecated
- Next.js 16.2.0 installed docs: `node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/rewrites.md` — rewrites API
- Project source: `reasoning/app/routers/reports.py` — existing SSE infrastructure (asyncio.Queue, EventSourceResponse, _emit, _run_pipeline)
- Project source: `reasoning/app/pipeline/graph.py` — 7-node linear StateGraph, node names confirmed
- Project source: `reasoning/app/pipeline/__init__.py` — generate_report entry point, vi+en two-stage structure
- Project source: `frontend/src/components/dashboard/DashboardClient.tsx` — useCallback/useState patterns, accessToken prop, toast usage
- Project source: `frontend/src/components/dashboard/TickerCard.tsx` — current card structure for modification
- Project source: `frontend/src/components/dashboard/WatchlistGrid.tsx` — prop interface to extend
- Project source: `frontend/src/lib/api.ts` — fetchAPI helper pattern
- Project source: `frontend/src/lib/types.ts` — existing type interfaces
- Project source: `frontend/next.config.ts` — current minimal config (no rewrites yet)
- Project source: `frontend/src/proxy.ts` — auth middleware, SSE route not currently protected

### Secondary (MEDIUM confidence)
- STATE.md accumulated decisions — "SSE proxied via next.config.ts rewrites (not API routes)" and "NEXT_PUBLIC_API_URL targets host-mapped reasoning-engine port 8001 for client-side fetches"

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from installed sources; no new dependencies needed
- Architecture: HIGH — LangGraph `astream(stream_mode="tasks")` verified from installed source; pattern is mechanically sound
- Pitfalls: HIGH — derived from direct code analysis of existing _run_pipeline, EventSource spec, and React state update semantics

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable stack: LangGraph 1.1.2, Next.js 16.2.0, React 19 — no expected breaking changes in 30 days)
