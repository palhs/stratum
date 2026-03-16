# Phase 7: Graph Assembly and End-to-End Report Generation - Research

**Researched:** 2026-03-16
**Domain:** LangGraph StateGraph assembly, AsyncPostgresSaver checkpointing, bilingual report generation, Pydantic report schemas, PostgreSQL report storage
**Confidence:** HIGH (LangGraph StateGraph patterns verified via Context7; AsyncPostgresSaver usage confirmed; existing codebase examined fully; report schema requirements derived from REQUIREMENTS.md and CONTEXT.md)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Vietnamese financial term dictionary:**
- JSON lookup table (~150-200 terms) covering macro, valuation, structure, and entry quality domains comprehensively
- Claude drafts initial dictionary, user reviews and corrects before integration
- English financial abbreviations kept inline in Vietnamese text (P/E, ATH, ETF, etc.) — standard VN financial media practice
- Dictionary covers: tier labels, sub-assessment labels, card headers, conflict patterns, DATA WARNING text, financial metrics, macro concepts, and narrative connectors

**Report card structure:**
- Conclusion-first ordering: Entry Quality → Macro Regime → Valuation → Structure
- When signal conflict exists: separate 5th section "Signal Conflict" appears between Entry Quality and Macro Regime cards
- Full narrative depth per card: Gemini-generated narrative (3-5 sentences), metrics, tier/label with explanation
- JSON report: flat object per card (not nested sub-objects) — simple JSONB querying for Phase 8 API

**Prohibited language enforcement:**
- Prompt constraint only — instruct Gemini to never use prohibited terms; no post-processing filter
- Prohibited in both English AND Vietnamese: 'buy'/'mua', 'sell'/'bán', 'entry confirmed'/'xác nhận điểm vào'
- Compound words allowed: 'buyback', 'sell-off', 'oversold', 'overbought' are acceptable analytical descriptors
- Replacement framing: assessment language — "the environment suggests...", "conditions appear...", "the structure indicates..." (not probability language)

**Data prefetch orchestration:**
- Two-stage pipeline: `prefetch(ticker, asset_type)` returns populated ReportState, then `run_graph(state)` executes the StateGraph — testable independently
- Test assets for v2.0 E2E: VHM (Vinhomes, equity path) AND gold (gold path) — both tested in first run
- Bilingual generation: two separate graph invocations per asset, one with language='vi' and one with language='en' — language is a parameter, not a dual-output node
- Each invocation produces one row in `reports` table (so VHM generates 2 rows: vi + en)

### Claude's Discretion
- StateGraph edge topology (linear vs conditional edges)
- AsyncPostgresSaver configuration and connection pooling
- Prefetch error handling (which store failures are fatal vs degraded)
- Markdown report template structure and formatting
- Vietnamese dictionary term selection within the ~150-200 scope
- Test fixture design for E2E integration tests

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REAS-06 | LangGraph StateGraph assembles all nodes with explicit TypedDict state, documented reducers, and PostgreSQL checkpointing | StateGraph.add_node + add_edge verified via Context7; AsyncPostgresSaver.from_conn_string with `?options=-csearch_path=langgraph` connects to pre-created langgraph schema; all 6 nodes already in `reasoning/app/nodes/__init__.py` |
| REPT-01 | Report output in structured JSON format with card sections (macro regime, valuation, structure, entry quality) | ReportCardJSON Pydantic model maps all node outputs; flat card objects from CONTEXT.md; stored via SQLAlchemy Core INSERT into `reports` table |
| REPT-02 | Report output rendered as Markdown with human-readable narrative | Jinja2 or Python string templating; conclusion-first card ordering; prohibited term enforcement in Gemini prompt |
| REPT-03 | Bilingual generation (Vietnamese primary, English secondary) from structured data using Gemini native Vietnamese | Separate invocation per language; language parameter on compose_report node; JSON term dictionary lookup for VN terms |
| REPT-04 | Reports include explicit "DATA WARNING" sections when `data_as_of` exceeds freshness thresholds | `check_freshness()` + `FRESHNESS_THRESHOLDS` already in `reasoning/app/retrieval/freshness.py`; warnings propagate via `retrieval_warnings` field in ReportState; DATA WARNING rendered as a special section in both JSON and Markdown |
| REPT-05 | Reports stored in PostgreSQL `reports` table with full JSON and metadata | `reports` table exists (V6__reports.sql); INSERT via SQLAlchemy Core; columns: report_id, asset_id, language, report_json, report_markdown, data_as_of, generated_at |
</phase_requirements>

---

## Summary

Phase 7 wires the 6 validated Phase 6 nodes into a `StateGraph`, adds PostgreSQL checkpointing via `AsyncPostgresSaver`, and adds a 7th `compose_report` node that serializes node outputs into JSON + Markdown report structures. The pipeline is invoked twice per asset (once with `language='vi'`, once with `language='en'`), and each invocation writes one row to the `reports` PostgreSQL table.

The core architectural challenge is the two-stage design: `prefetch(ticker, asset_type)` calls all retrieval functions and returns a populated `ReportState`, then `run_graph(state, language, thread_id)` compiles and invokes the `StateGraph` with `AsyncPostgresSaver` checkpointing. This split allows Phase 8 FastAPI to cache prefetch state and call `run_graph` independently. The `language` parameter must be added to `ReportState` for Phase 7; the `compose_report` node reads it to determine which language to use when invoking Gemini.

The bilingual generation approach is deliberate: two invocations produce independently authored reports in each language, not translations. The Vietnamese output uses a JSON term dictionary for controlled vocabulary (~150-200 terms). Both outputs are written to the `reports` table as separate rows. The graph definition itself is language-agnostic — only the `compose_report` node's Gemini prompt differs by language.

**Primary recommendation:** Implement `StateGraph` with linear edges (no conditionals required in Phase 7; conflicting_signals_handler always runs and returns `None` when no conflict). Add `language: str` to `ReportState`. Add a `compose_report` node that converts all upstream outputs to JSON card structure + Markdown. Use `AsyncPostgresSaver.from_conn_string(DB_URI + "?options=-csearch_path=langgraph")` for checkpointing (matches Phase 3 schema). Use SQLAlchemy Core INSERT (not ORM) for the `reports` table write — matches the established project pattern.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=0.2.0 (already installed) | `StateGraph`, `START`, `END`, `AsyncPostgresSaver` | Required by REAS-06; already in requirements.txt |
| langgraph-checkpoint-postgres | bundled with langgraph | `AsyncPostgresSaver` class | PostgreSQL checkpointing; langgraph schema pre-created in Phase 3 |
| langchain-google-genai | >=2.0.0 (already installed) | `ChatGoogleGenerativeAI` for compose_report node | Established pattern from all Phase 6 nodes; same API |
| pydantic | v2 (already installed) | Report card Pydantic schemas for JSON validation | Established project standard |
| sqlalchemy | >=2.0.0 (already installed) | Core INSERT for `reports` table write | Established project pattern (postgres_retriever.py uses SQLAlchemy Core) |
| psycopg (psycopg3) | already in langgraph-checkpoint-postgres deps | AsyncPostgresSaver's underlying async driver | AsyncPostgresSaver requires psycopg3 async |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Run async graph invocation in sync context | `asyncio.run(run_graph(...))` when calling from sync entry point |
| json | stdlib | Serialize Pydantic model to JSONB payload | `report_json = json.loads(report_card.model_dump_json())` |
| datetime | stdlib | `generated_at` timestamp for reports table row | `datetime.now(timezone.utc)` |
| pytest-asyncio | >=0.24.0 (already installed) | Async test fixtures for E2E integration test | E2E test must run AsyncPostgresSaver in async context |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AsyncPostgresSaver` | `PostgresSaver` (sync) | Sync is simpler but Phase 8 FastAPI will be async; starting async now avoids a rewrite |
| Pydantic `ReportCard` schema for JSON card | Raw `dict` from node outputs | Pydantic ensures report_json has correct structure before insertion; catches missing fields |
| SQLAlchemy Core INSERT for reports table | `psycopg3` raw INSERT | SQLAlchemy Core matches established project pattern from postgres_retriever.py; no new patterns |
| Two-stage `prefetch` + `run_graph` | Single function calling retrieval inside nodes | Two-stage is testable independently; Phase 8 FastAPI can cache prefetch; already locked in CONTEXT.md |

**Installation additions** (none needed — all packages already in `reasoning/requirements.txt`):
```bash
# No new packages needed — langgraph, langchain-google-genai, sqlalchemy, pydantic all present
# Verify langgraph-checkpoint-postgres is available:
pip show langgraph | grep -i postgres  # bundled or as langgraph[postgres]
```

If `langgraph-checkpoint-postgres` is not bundled, add:
```bash
pip install langgraph-checkpoint-postgres
```

---

## Architecture Patterns

### Recommended Project Structure
```
reasoning/
├── app/
│   ├── retrieval/           # Phase 5 — unchanged
│   ├── models/              # Phase 5 — unchanged
│   ├── nodes/               # Phase 6 — unchanged (6 nodes + state.py)
│   └── pipeline/            # NEW in Phase 7
│       ├── __init__.py      # Exports prefetch(), run_graph(), generate_report()
│       ├── graph.py         # StateGraph definition, compile(), run_graph()
│       ├── prefetch.py      # prefetch(ticker, asset_type) -> ReportState
│       ├── compose_report.py # compose_report_node(state) -> dict (7th node)
│       ├── report_schema.py # ReportCard Pydantic models (JSON + Markdown schemas)
│       ├── term_dict.py     # VN term dictionary loader + apply_terms()
│       ├── term_dict_vi.json # Vietnamese financial term dictionary (~150-200 terms)
│       └── storage.py       # write_report() — SQLAlchemy Core INSERT to reports table
├── tests/
│   ├── nodes/               # Phase 6 — unchanged
│   └── pipeline/            # NEW in Phase 7
│       ├── __init__.py
│       ├── conftest.py      # Pipeline test fixtures (mock prefetch state)
│       ├── test_compose_report.py  # Unit tests for compose_report_node
│       ├── test_graph.py    # Unit tests for graph definition (importable, compilable)
│       ├── test_term_dict.py # Unit tests for term dictionary lookup
│       └── test_e2e.py      # Integration test — full pipeline run (requires Docker)
```

### Pattern 1: Linear StateGraph Assembly
**What:** All 6 Phase 6 nodes + 1 new `compose_report` node assembled in linear order with explicit edges. No conditional routing needed in Phase 7 (conflicting_signals_handler always runs; returns `{"conflict_output": None}` when no conflict, which is a valid state update).
**When to use:** This is the REAS-06 assembly.

```python
# Source: https://docs.langchain.com/oss/python/langgraph/persistence (verified via Context7)
# reasoning/app/pipeline/graph.py

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from reasoning.app.nodes import (
    macro_regime_node,
    valuation_node,
    structure_node,
    conflicting_signals_handler,
    entry_quality_node,
    grounding_check_node,
)
from reasoning.app.pipeline.compose_report import compose_report_node
from reasoning.app.nodes.state import ReportState


def build_graph() -> StateGraph:
    """
    Assemble all reasoning nodes into a linear StateGraph.

    Node execution order (matches conclusion-first card ordering):
        START
        → macro_regime_node
        → valuation_node
        → structure_node
        → conflicting_signals_handler   (always runs; returns None conflict if no pattern)
        → entry_quality_node
        → grounding_check_node          (raises GroundingError on unattributed claims)
        → compose_report_node           (7th node: serializes to JSON + Markdown)
        → END
    """
    builder = StateGraph(ReportState)
    builder.add_node("macro_regime", macro_regime_node)
    builder.add_node("valuation", valuation_node)
    builder.add_node("structure", structure_node)
    builder.add_node("conflict", conflicting_signals_handler)
    builder.add_node("entry_quality", entry_quality_node)
    builder.add_node("grounding_check", grounding_check_node)
    builder.add_node("compose_report", compose_report_node)

    builder.add_edge(START, "macro_regime")
    builder.add_edge("macro_regime", "valuation")
    builder.add_edge("valuation", "structure")
    builder.add_edge("structure", "conflict")
    builder.add_edge("conflict", "entry_quality")
    builder.add_edge("entry_quality", "grounding_check")
    builder.add_edge("grounding_check", "compose_report")
    builder.add_edge("compose_report", END)

    return builder


async def run_graph(
    state: ReportState,
    language: str,
    thread_id: str,
    db_uri: str,
) -> ReportState:
    """
    Compile the StateGraph with AsyncPostgresSaver and invoke it.

    The langgraph schema was pre-created in Phase 3 (init-langgraph-schema.py).
    Connect using ?options=-csearch_path=langgraph to route to the correct schema.
    """
    conn_str = db_uri + "?options=-csearch_path%3Dlanggraph"
    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        state["language"] = language  # inject language before invocation
        result = await graph.ainvoke(state, config)
    return result
```

### Pattern 2: `ReportState` Extension — Add `language` and Report Output Fields
**What:** `ReportState` needs two new fields for Phase 7: `language: str` (consumed by `compose_report_node`) and `report_output: Optional[ReportOutput]` (written by `compose_report_node`).
**When to use:** Add to `reasoning/app/nodes/state.py` before Phase 7 node implementation.

```python
# Addition to reasoning/app/nodes/state.py

class ReportOutput(BaseModel):
    """Output of the compose_report node — final serialized report."""
    report_json: dict            # flat card structure for JSONB storage
    report_markdown: str         # human-readable Markdown
    language: str                # "vi" | "en"
    data_as_of: datetime         # most recent data_as_of across all sources
    data_warnings: list[str]     # collected from retrieval_warnings + node warnings
    model_version: str = "gemini-2.5-pro"
    warnings: list[str] = []

# Add to ReportState TypedDict:
class ReportState(TypedDict, total=False):
    # ... existing fields ...

    # ---- Phase 7 additions ----
    language: str                          # "vi" | "en" — set by run_graph() caller
    report_output: Optional[ReportOutput]  # written by compose_report_node
```

### Pattern 3: `compose_report_node` — 7th Node
**What:** Reads all node outputs from state, serializes into flat JSON card structure and Markdown, applies VN term dictionary if `language='vi'`.
**When to use:** Final node before END in the graph.

```python
# reasoning/app/pipeline/compose_report.py

from reasoning.app.nodes.state import ReportState, ReportOutput
from reasoning.app.pipeline.term_dict import apply_terms
from reasoning.app.pipeline.report_schema import (
    EntryQualityCard, MacroRegimeCard, ValuationCard, StructureCard,
    ConflictCard, DataWarningCard, ReportCard
)


def compose_report_node(state: ReportState) -> dict:
    """
    Build the final report from all upstream node outputs.

    State reads:
        - macro_regime_output, valuation_output, structure_output
        - entry_quality_output, conflict_output, grounding_result
        - retrieval_warnings, language
    State writes:
        - report_output: ReportOutput
    """
    language = state.get("language", "en")

    # 1. Build card objects (Pydantic models for validation)
    eq_card = _build_entry_quality_card(state, language)
    macro_card = _build_macro_regime_card(state, language)
    val_card = _build_valuation_card(state, language)
    struct_card = _build_structure_card(state, language)
    conflict_card = _build_conflict_card(state, language)  # None if no conflict
    data_warnings = _collect_data_warnings(state)

    # 2. Assemble ordered report (conclusion-first: Entry Quality first)
    report_card = ReportCard(
        entry_quality=eq_card,
        conflict=conflict_card,          # None → omitted from JSON output
        macro_regime=macro_card,
        valuation=val_card,
        structure=struct_card,
        data_warnings=data_warnings,
        language=language,
    )

    # 3. Apply VN term dictionary (vi only)
    if language == "vi":
        report_card = apply_terms(report_card)

    # 4. Serialize to JSON (flat per card — not nested sub-objects)
    report_json = report_card.model_dump(exclude_none=True)

    # 5. Render Markdown
    report_markdown = _render_markdown(report_card, language)

    # 6. Compute data_as_of (earliest warning timestamp, or now)
    data_as_of = _compute_data_as_of(state)

    return {
        "report_output": ReportOutput(
            report_json=report_json,
            report_markdown=report_markdown,
            language=language,
            data_as_of=data_as_of,
            data_warnings=data_warnings,
        )
    }
```

### Pattern 4: `prefetch()` — Retrieval Stage
**What:** Calls all retrieval functions and returns a pre-populated `ReportState` dict. Graph nodes read from this state without making any DB calls themselves.
**When to use:** First stage of `generate_report()`. Phase 8 FastAPI can call `prefetch()` at request time and cache the result.

```python
# reasoning/app/pipeline/prefetch.py

from reasoning.app.retrieval import (
    get_fundamentals, get_structure_markers, get_fred_indicators,
    get_gold_price, get_gold_etf, get_regime_analogues,
    search_macro_docs, search_earnings_docs,
)
from reasoning.app.nodes.state import ReportState


def prefetch(ticker: str, asset_type: str, db_engine, neo4j_driver, qdrant_client) -> ReportState:
    """
    Fetch all data required for the report pipeline.
    Returns a populated ReportState dict — no live calls after this point.

    Prefetch error strategy (Claude's discretion):
    - Fatal: fred_rows empty (macro regime node cannot run without FRED data)
    - Degraded: regime_analogues empty (macro node falls back to indicator-only reasoning)
    - Degraded: fundamentals_rows empty (valuation node uses partial assessment path)
    - Degraded: macro_docs empty (macro narrative has less context)
    - Degraded: earnings_docs empty (valuation narrative has less context)
    - Gold path: gold_price_rows empty → fatal for gold asset_type only
    """
    warnings = []

    fred_rows = get_fred_indicators(db_engine)  # may raise NoDataError
    regime_analogues = get_regime_analogues(neo4j_driver, ...)

    if asset_type == "equity":
        fundamentals_rows = get_fundamentals(db_engine, ticker)
        structure_marker_rows = get_structure_markers(db_engine, ticker)
        gold_price_rows = []
        gold_etf_rows = []
        earnings_docs = search_earnings_docs(qdrant_client, ticker)
    elif asset_type == "gold":
        fundamentals_rows = []
        structure_marker_rows = get_structure_markers(db_engine, "GOLD")
        gold_price_rows = get_gold_price(db_engine)
        gold_etf_rows = get_gold_etf(db_engine)
        earnings_docs = []
    else:
        raise ValueError(f"Unknown asset_type: {asset_type}")

    macro_docs = search_macro_docs(qdrant_client, ...)

    return ReportState(
        ticker=ticker,
        asset_type=asset_type,
        fred_rows=fred_rows,
        regime_analogues=regime_analogues,
        macro_docs=macro_docs,
        fundamentals_rows=fundamentals_rows,
        structure_marker_rows=structure_marker_rows,
        gold_price_rows=gold_price_rows,
        gold_etf_rows=gold_etf_rows,
        earnings_docs=earnings_docs,
        retrieval_warnings=warnings,
        macro_regime_output=None,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
    )
```

### Pattern 5: `generate_report()` — Public Entry Point
**What:** Top-level function that calls `prefetch()`, invokes `run_graph()` twice (vi + en), writes both rows to `reports` table.
**When to use:** Phase 8 FastAPI will call this. In Phase 7, called from E2E test.

```python
# reasoning/app/pipeline/__init__.py

async def generate_report(
    ticker: str,
    asset_type: str,
    db_engine,
    neo4j_driver,
    qdrant_client,
    db_uri: str,
) -> tuple[int, int]:
    """
    Generate bilingual report for one asset.
    Returns (vi_report_id, en_report_id) from reports table.
    """
    import uuid

    # Stage 1: Prefetch
    state = prefetch(ticker, asset_type, db_engine, neo4j_driver, qdrant_client)

    # Stage 2a: Vietnamese invocation
    thread_id_vi = f"{ticker}-vi-{uuid.uuid4()}"
    state_vi = await run_graph(state.copy(), "vi", thread_id_vi, db_uri)
    vi_id = write_report(db_engine, ticker, "vi", state_vi["report_output"])

    # Stage 2b: English invocation
    thread_id_en = f"{ticker}-en-{uuid.uuid4()}"
    state_en = await run_graph(state.copy(), "en", thread_id_en, db_uri)
    en_id = write_report(db_engine, ticker, "en", state_en["report_output"])

    return vi_id, en_id
```

### Pattern 6: `write_report()` — PostgreSQL Storage
**What:** SQLAlchemy Core INSERT into `reports` table. Matches established project pattern.
**When to use:** After each `run_graph()` invocation.

```python
# reasoning/app/pipeline/storage.py
# Source: established pattern from reasoning/app/retrieval/postgres_retriever.py

from sqlalchemy import insert
from datetime import datetime, timezone
import json


def write_report(db_engine, asset_id: str, language: str, report_output: ReportOutput) -> int:
    """
    Insert one row into the reports table.
    Returns the generated report_id.
    """
    reports_table = Table("reports", MetaData(), autoload_with=db_engine)

    with db_engine.connect() as conn:
        result = conn.execute(
            insert(reports_table).values(
                asset_id=asset_id,
                language=language,
                report_json=json.loads(report_output.model_dump_json())["report_json"],
                report_markdown=report_output.report_markdown,
                data_as_of=report_output.data_as_of,
                model_version=report_output.model_version,
                generated_at=datetime.now(timezone.utc),
            ).returning(reports_table.c.report_id)
        )
        conn.commit()
        return result.scalar_one()
```

### Pattern 7: DATA WARNING Generation (REPT-04)
**What:** Collect all `data_as_of` timestamps from retrieval outputs and run `check_freshness()`. If stale, include explicit `DATA WARNING` section naming source and staleness duration. WGC gold data gap is a known permanent warning (WGC returns 501).
**When to use:** Inside `compose_report_node` — collect from `retrieval_warnings` already in state, plus re-check timestamps from fetched rows.

```python
# In compose_report.py _collect_data_warnings()

def _collect_data_warnings(state: ReportState) -> list[str]:
    """
    Collect all data freshness warnings from the state.
    Sources: retrieval_warnings (set during prefetch) + any stale_data_caveat from entry_quality.
    """
    warnings = list(state.get("retrieval_warnings", []))

    # Add stale caveat from entry_quality node if present
    eq_output = state.get("entry_quality_output")
    if eq_output and eq_output.stale_data_caveat:
        warnings.append(eq_output.stale_data_caveat)

    # WGC gold data: always a known gap — always include for gold asset_type
    if state.get("asset_type") == "gold":
        warnings.append(
            "DATA WARNING: WGC central bank buying data unavailable (source returned 501). "
            "Gold valuation assessment excludes central bank flow context."
        )

    return warnings
```

### Pattern 8: Vietnamese Term Dictionary
**What:** JSON file with ~150-200 terms. `apply_terms(report_card)` replaces English tier labels, card headers, and technical terms in Vietnamese report fields. English abbreviations (P/E, ATH, ETF) are preserved inline.
**Structure:**

```json
// term_dict_vi.json (partial — full dictionary drafted by Claude, reviewed by user)
{
  "tiers": {
    "Favorable": "Thuận lợi",
    "Neutral": "Trung lập",
    "Cautious": "Thận trọng",
    "Avoid": "Tránh"
  },
  "macro_labels": {
    "Supportive": "Hỗ trợ",
    "Mixed": "Hỗn hợp",
    "Headwind": "Bất lợi"
  },
  "valuation_labels": {
    "Attractive": "Hấp dẫn",
    "Fair": "Hợp lý",
    "Stretched": "Căng thẳng"
  },
  "structure_labels": {
    "Constructive": "Tích cực",
    "Neutral": "Trung lập",
    "Deteriorating": "Suy giảm"
  },
  "card_headers": {
    "Entry Quality": "Chất lượng điểm vào",
    "Macro Regime": "Chế độ vĩ mô",
    "Valuation": "Định giá",
    "Structure": "Cấu trúc giá",
    "Signal Conflict": "Xung đột tín hiệu",
    "Data Warning": "Cảnh báo dữ liệu"
  },
  "narrative_connectors": {
    "the environment suggests": "môi trường cho thấy",
    "conditions appear": "điều kiện dường như",
    "the structure indicates": "cấu trúc cho thấy"
  }
}
```

### Anti-Patterns to Avoid
- **Running retrieval inside graph nodes:** All retrieval happens in `prefetch()` before graph invocation. Nodes read from state only. Never add retrieval calls to existing Phase 6 nodes.
- **Using `.setup()` on AsyncPostgresSaver:** The `langgraph` schema was pre-created in Phase 3 using raw DDL. Calling `.setup()` again would target the `public` schema (no schema parameter) and create duplicate tables. Connect with `?options=-csearch_path=langgraph` and skip `.setup()`.
- **Calling `asyncio.run()` inside an already-async context:** The `run_graph()` function is async. In the E2E test, use `@pytest.mark.asyncio` from `pytest-asyncio`. In sync entry points, use `asyncio.run()` at the top level only.
- **Sharing a single `state` dict across both language invocations:** `state.copy()` is a shallow copy — `list` fields share references. Use `copy.deepcopy(state)` or reconstruct the state for each invocation to prevent mutation between vi and en runs.
- **Generating JSON with nested sub-objects per card:** CONTEXT.md locks "flat object per card (not nested sub-objects)." Each card is a flat dict, not `{"macro": {"label": ..., "narrative": ...}}`. Use `model_dump(mode='json')` and verify field paths before any Phase 8 JSONB queries.
- **Translating English output to Vietnamese:** REPT-03 requires bilingual generation from structured data, not translation. Two separate Gemini invocations with the same structured inputs but different language prompts. The Vietnamese report is independently authored.
- **Using `state["language"]` in Phase 6 nodes:** Phase 6 nodes do not read `language`. Only `compose_report_node` uses it. Do not add language-awareness to existing Phase 6 nodes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgreSQL checkpointing | Custom checkpoint storage | `AsyncPostgresSaver` from `langgraph.checkpoint.postgres.aio` | Handles serialization, thread isolation, retry; schema pre-created in Phase 3 |
| JSON schema validation of report cards | Manual dict key checks | Pydantic `ReportCard` model with `model_validate()` | Catches missing required card fields before database insert |
| Vietnamese term substitution | Regex-replace on rendered Markdown | `apply_terms(report_card)` operating on Pydantic model fields before Markdown render | Field-level substitution is structured and reversible; regex on Markdown is fragile |
| State copy between invocations | Shallow dict copy | `copy.deepcopy(state)` | State contains nested Pydantic objects and lists; shallow copy causes mutations |
| Markdown rendering | Custom Jinja2 template | Simple f-string template function or Python string Template | Report Markdown has no conditional logic that requires Jinja2; f-strings are readable and debuggable |
| `data_as_of` aggregation across sources | Manual min/max loops | Extract `data_as_of` from all prefetched row objects and take `min()` | Establishes "report is as fresh as its oldest source" semantics |

**Key insight:** Phase 7's complexity is in the orchestration plumbing (two-stage design, bilingual invocation, PostgreSQL write) and the `compose_report` node (term dictionary, card structure). The LangGraph graph definition itself is trivially simple — 7 nodes, 7 edges, linear. Don't over-engineer the graph topology.

---

## Common Pitfalls

### Pitfall 1: AsyncPostgresSaver Targets `public` Schema
**What goes wrong:** If `AsyncPostgresSaver.from_conn_string(db_uri)` is called without the schema search path override, it connects to `public` and finds no checkpoint tables (they're in `langgraph` schema). Operations silently fail or raise `UndefinedTable`.
**Why it happens:** Phase 3 created tables in `langgraph` schema specifically because `.setup()` only works with `public`. The connection URI must override the search path.
**How to avoid:** Always use `db_uri + "?options=-csearch_path%3Dlanggraph"` (URL-encoded `=`). Alternatively: `db_uri + "?options=-csearch_path=langgraph"` — test which encoding the psycopg3 URL parser accepts.
**Warning signs:** `UndefinedTable: relation "checkpoints" does not exist` or silent checkpoint failures.

### Pitfall 2: State Mutation Between Language Invocations
**What goes wrong:** `state.copy()` does not deep-copy nested lists and Pydantic objects. When `run_graph` for `language='vi'` mutates state fields (adding `language`, writing `report_output`), the English invocation uses the already-mutated state.
**Why it happens:** Python dict `.copy()` is shallow — `list` fields like `fred_rows` share the same list objects.
**How to avoid:** Use `import copy; state_copy = copy.deepcopy(state)` before each invocation, or rebuild a fresh `ReportState` from the same retrieval data.
**Warning signs:** English report contains Vietnamese narrative, or `language` field is wrong in one report.

### Pitfall 3: `compose_report_node` Calling Gemini Without Language-Aware Prompt
**What goes wrong:** The compose_report node uses the same system prompt for both languages. Vietnamese output is a translation of English, not independently authored.
**Why it happens:** Language parameter is added to state but the Gemini call doesn't read it.
**How to avoid:** Separate `_SYSTEM_PROMPT_VI` and `_SYSTEM_PROMPT_EN` constants. Select based on `state.get("language", "en")` before building the LLM chain.
**Warning signs:** Vietnamese report uses English sentence structure with just word substitutions.

### Pitfall 4: `GroundingError` Propagates Past Grounding Check Node
**What goes wrong:** `grounding_check_node` raises `GroundingError` inside the LangGraph node. LangGraph may catch this and mark the graph run as failed, but the error may not surface clearly to the caller.
**Why it happens:** LangGraph wraps node exceptions in its own error types. The `GroundingError` may be buried inside a `GraphBuildException` or similar.
**How to avoid:** In `run_graph()`, wrap `await graph.ainvoke(state, config)` in a `try/except` that catches both `GroundingError` directly and any LangGraph wrapper exceptions. Re-raise `GroundingError` with original message for clean surfacing.
**Warning signs:** `run_graph()` raises a generic `GraphInterruptException` with no clear grounding context.

### Pitfall 5: `reports` Table INSERT with Pydantic Nested Objects in `report_json`
**What goes wrong:** `model_dump()` returns Python objects including Pydantic model instances for nested fields. Passing this directly to SQLAlchemy JSONB fails with `TypeError: Object of type X is not JSON serializable`.
**Why it happens:** Pydantic's `model_dump()` returns native Python types for most fields, but nested Pydantic instances remain as objects.
**How to avoid:** Use `json.loads(report_card.model_dump_json())` — `model_dump_json()` serializes to JSON string first (handling all Pydantic types), then `json.loads()` converts to a plain Python dict safe for JSONB.
**Warning signs:** `TypeError: Object of type datetime/Decimal is not JSON serializable` during INSERT.

### Pitfall 6: `ReportState` Missing `language` Field Breaks Existing Phase 6 Tests
**What goes wrong:** Adding `language: str` to `ReportState` TypedDict changes the expected structure. Existing Phase 6 unit tests construct `ReportState` dicts manually and will fail if `language` is required (not Optional).
**Why it happens:** `ReportState` uses `total=False` (all fields Optional at TypedDict level), but test fixtures that call `ReportState(...)` constructor directly may not pass `language`.
**How to avoid:** Add `language: str` with a default or make it `Optional[str]` in the TypedDict. `compose_report_node` uses `state.get("language", "en")` as fallback. Phase 6 test fixtures do not need to set `language`.
**Warning signs:** Phase 6 tests fail after `language` is added to state.py.

### Pitfall 7: WGC Gold Gap Not Explicitly Named in DATA WARNING
**What goes wrong:** The DATA WARNING section says "data is stale" generically instead of explicitly naming "WGC gold data unavailable."
**Why it happens:** The generic `retrieval_warnings` list may have a generic STALE DATA message if the WGC gap is represented as a staleness warning rather than a 501-stub warning.
**How to avoid:** In `prefetch.py`, when gold_wgc_flows returns no data (empty list or 501 error), add an explicit warning string: `"DATA WARNING: WGC central bank buying data unavailable (source returned 501)."` to `retrieval_warnings`. The `compose_report_node` includes this verbatim in the report. Success criterion #5 requires explicitly naming the source.
**Warning signs:** DATA WARNING section present but does not name "WGC" or "central bank buying."

---

## Code Examples

Verified patterns from official sources:

### AsyncPostgresSaver with langgraph schema search path
```python
# Source: https://docs.langchain.com/oss/python/langgraph/add-memory (Context7-verified)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Phase 3 created tables in 'langgraph' schema — connect with search_path override
DB_URI = "postgresql://stratum:stratum_password@postgres:5432/stratum"
CONN_STR = DB_URI + "?options=-csearch_path%3Dlanggraph"

async with AsyncPostgresSaver.from_conn_string(CONN_STR) as checkpointer:
    # Do NOT call checkpointer.setup() — schema already exists from Phase 3
    graph = build_graph().compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "VHM-vi-abc123"}}
    result = await graph.ainvoke(initial_state, config)
```

### StateGraph definition (verified via Context7)
```python
# Source: https://docs.langchain.com/oss/python/langgraph/persistence (Context7-verified)
from langgraph.graph import StateGraph, START, END

builder = StateGraph(ReportState)
builder.add_node("macro_regime", macro_regime_node)
builder.add_node("valuation", valuation_node)
builder.add_node("structure", structure_node)
builder.add_node("conflict", conflicting_signals_handler)
builder.add_node("entry_quality", entry_quality_node)
builder.add_node("grounding_check", grounding_check_node)
builder.add_node("compose_report", compose_report_node)

builder.add_edge(START, "macro_regime")
builder.add_edge("macro_regime", "valuation")
builder.add_edge("valuation", "structure")
builder.add_edge("structure", "conflict")
builder.add_edge("conflict", "entry_quality")
builder.add_edge("entry_quality", "grounding_check")
builder.add_edge("grounding_check", "compose_report")
builder.add_edge("compose_report", END)

# Instantiate without checkpointer (for import/unit test verification)
graph_no_checkpoint = builder.compile()
```

### Pydantic ReportCard schema (flat per-card structure)
```python
# reasoning/app/pipeline/report_schema.py
from pydantic import BaseModel
from typing import Optional

class EntryQualityCard(BaseModel):
    """Flat JSON card for Entry Quality — no nested sub-objects."""
    tier: str                     # "Favorable" | "Neutral" | "Cautious" | "Avoid"
    macro_assessment: str
    valuation_assessment: str
    structure_assessment: str
    structure_veto_applied: bool
    conflict_pattern: Optional[str] = None
    narrative: str

class MacroRegimeCard(BaseModel):
    top_regime_id: str
    top_confidence: float
    is_mixed_signal: bool
    macro_label: str
    narrative: str

class ValuationCard(BaseModel):
    asset_type: str
    valuation_label: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    real_yield: Optional[float] = None
    narrative: str

class StructureCard(BaseModel):
    structure_label: str
    close: Optional[float] = None
    drawdown_from_ath: Optional[float] = None
    close_pct_rank: Optional[float] = None
    narrative: str

class ConflictCard(BaseModel):
    pattern_name: str
    severity: str
    narrative: str

class ReportCard(BaseModel):
    """Complete report with all cards. JSON output is flat per card."""
    entry_quality: EntryQualityCard
    macro_regime: MacroRegimeCard
    valuation: ValuationCard
    structure: StructureCard
    conflict: Optional[ConflictCard] = None      # None → excluded from JSON
    data_warnings: list[str] = []
    language: str
```

### SQLAlchemy Core INSERT into reports table
```python
# reasoning/app/pipeline/storage.py
# Pattern matches reasoning/app/retrieval/postgres_retriever.py (established project pattern)
from sqlalchemy import Table, MetaData, insert
from datetime import datetime, timezone
import json

def write_report(db_engine, asset_id: str, language: str, report_output) -> int:
    metadata = MetaData()
    reports = Table("reports", metadata, autoload_with=db_engine)

    report_json_payload = json.loads(
        report_output.model_dump_json()
    )["report_json"]  # Plain Python dict — safe for JSONB

    with db_engine.connect() as conn:
        result = conn.execute(
            insert(reports).values(
                asset_id=asset_id,
                language=language,
                report_json=report_json_payload,
                report_markdown=report_output.report_markdown,
                data_as_of=report_output.data_as_of,
                model_version=report_output.model_version,
                generated_at=datetime.now(timezone.utc),
            ).returning(reports.c.report_id)
        )
        conn.commit()
        return result.scalar_one()
```

### E2E Test Skeleton
```python
# reasoning/tests/pipeline/test_e2e.py
# Requires live Docker services (postgres, neo4j, qdrant) — mark as integration

import asyncio
import pytest
from reasoning.app.pipeline import generate_report

@pytest.mark.asyncio
@pytest.mark.integration  # skipped unless --integration flag
async def test_e2e_vhm_report(db_engine, neo4j_driver, qdrant_client):
    """Full pipeline run for VHM equity — both vi and en."""
    vi_id, en_id = await generate_report(
        ticker="VHM",
        asset_type="equity",
        db_engine=db_engine,
        neo4j_driver=neo4j_driver,
        qdrant_client=qdrant_client,
        db_uri=DATABASE_URL,
    )

    # SC #6: report is in reports table
    assert vi_id is not None
    assert en_id is not None

    # Verify report content via SELECT
    with db_engine.connect() as conn:
        vi_row = conn.execute(
            text("SELECT report_json, language FROM reports WHERE report_id = :id"),
            {"id": vi_id}
        ).fetchone()
    assert vi_row["language"] == "vi"
    assert "entry_quality" in vi_row["report_json"]

    # SC #3: no prohibited terms in Markdown
    vi_markdown = conn.execute(...)  # fetch report_markdown
    for term in ["buy", "sell", "entry confirmed", "mua", "bán", "xác nhận điểm vào"]:
        assert term not in vi_markdown.lower()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangGraph `setup()` for checkpoint tables | Phase 3 raw DDL in `langgraph` schema | Phase 3 decision | `AsyncPostgresSaver` connects without re-running DDL; avoids public schema collision |
| Single-language report | Two separate graph invocations per language | CONTEXT.md decision | Each language is independently authored; Phase 8 API can re-invoke for different languages |
| Translation pipeline (EN → VN) | Structured data → native VN via Gemini | REQUIREMENTS.md (REPT-03) | Higher quality Vietnamese output; bilingual from source, not derivative |
| `setup()` at runtime | Pre-created schema (Phase 3) | Phase 3-07 architecture | Separates schema creation (ops concern) from application code (dev concern) |

**Deprecated/outdated:**
- `InMemorySaver`: Used for Phase 6 testing only. Phase 7 uses `AsyncPostgresSaver` for durable checkpoints. Do not use `InMemorySaver` in production graph runs.
- `PostgresSaver` (sync): Phase 8 FastAPI will be async; use `AsyncPostgresSaver` now to avoid a future migration.

---

## Open Questions

1. **Should `compose_report_node` call Gemini for narrative synthesis, or assemble from existing node narratives?**
   - What we know: All Phase 6 nodes already produce `narrative` fields via Gemini. `entry_quality_node` synthesizes sub-assessments into a composite narrative. `compose_report_node` could either assemble these existing narratives into the report structure OR call Gemini again for a "report introduction" / bilingual rendering.
   - What's unclear: Whether the bilingual requirement (REPT-03) means re-generating each card narrative in the target language, or just applying term translation to existing English narratives.
   - Recommendation: **Re-invoke Gemini per card per language.** The existing node narratives are in English (Phase 6 nodes don't have language awareness). For `language='vi'`, `compose_report_node` must call Gemini to produce Vietnamese-native narratives for each card. For `language='en'`, it assembles existing node narratives without additional LLM calls. This satisfies REPT-03 ("bilingual generation from structured data, not translation").
   - Confidence: MEDIUM — this is the cleanest interpretation, but adds Gemini API cost (4-6 additional calls for vi path). The planner should make the final call.

2. **Which data freshness timestamps to use for `data_as_of` in the reports table row?**
   - What we know: `reports` table has a `data_as_of TIMESTAMPTZ` column. Multiple data sources have different `data_as_of` values (FRED is weekly, fundamentals quarterly, etc.).
   - Recommendation: Use `min(all data_as_of timestamps)` — the report is only as fresh as its oldest data source. Document this choice in `storage.py`.
   - Confidence: HIGH — this is the conservative, correct interpretation.

3. **Should `prefetch()` be synchronous or asynchronous?**
   - What we know: `postgres_retriever.py` uses synchronous SQLAlchemy Core (established in Phase 5). Neo4j driver is synchronous. Qdrant client has both sync and async APIs.
   - What's unclear: Whether to make `prefetch()` async to match `run_graph()`, or keep it sync for consistency with existing retrieval patterns.
   - Recommendation: Keep `prefetch()` **synchronous**. The retrieval layer (Phase 5) is fully synchronous. Converting to async would require changing all Phase 5 retrievers — out of scope. `generate_report()` calls sync `prefetch()` then async `run_graph()`. This mixed pattern is fine in Python (`asyncio.run()` wraps the async part at the top level).
   - Confidence: HIGH.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ (already in reasoning/requirements.txt) |
| Config file | `reasoning/pytest.ini` (exists from Phase 5) |
| Quick run command | `pytest reasoning/tests/pipeline/ -x -m "not integration"` |
| Full suite command | `pytest reasoning/tests/ -v` |
| E2E integration run | `pytest reasoning/tests/pipeline/test_e2e.py -v -m integration` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REAS-06 | StateGraph imports without errors and compiles with/without checkpointer | unit (no Docker) | `pytest reasoning/tests/pipeline/test_graph.py -x` | Wave 0 gap |
| REAS-06 | AsyncPostgresSaver connects to langgraph schema without error | integration (requires Docker postgres) | `pytest reasoning/tests/pipeline/test_graph.py -x -m integration` | Wave 0 gap |
| REPT-01 | `compose_report_node` produces ReportCard with 4 card sections; Pydantic validation passes | unit (mock state with all node outputs) | `pytest reasoning/tests/pipeline/test_compose_report.py -x` | Wave 0 gap |
| REPT-02 | Markdown output contains no "buy", "sell", "entry confirmed" in any variant | unit (mock compose_report output) | `pytest reasoning/tests/pipeline/test_compose_report.py::test_prohibited_terms -x` | Wave 0 gap |
| REPT-03 | `language='vi'` invocation produces Vietnamese card headers and tier labels using term dictionary | unit (mock state, mock Gemini) | `pytest reasoning/tests/pipeline/test_compose_report.py::test_vi_terms -x` | Wave 0 gap |
| REPT-04 | Stale WGC gold data produces DATA WARNING section naming "WGC" in both JSON and Markdown | unit (mock state with stale gold warnings) | `pytest reasoning/tests/pipeline/test_compose_report.py::test_data_warning -x` | Wave 0 gap |
| REPT-05 | `write_report()` inserts row with correct report_id, asset_id, generated_at, report_json | integration (requires Docker postgres) | `pytest reasoning/tests/pipeline/test_storage.py -x -m integration` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** `pytest reasoning/tests/pipeline/ -x -m "not integration"`
- **Per wave merge:** `pytest reasoning/tests/ -v -m "not integration"`
- **Phase gate:** `pytest reasoning/tests/ -v` (requires live Docker services for integration tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `reasoning/app/pipeline/` directory and `__init__.py`
- [ ] `reasoning/app/pipeline/graph.py` — StateGraph definition + `run_graph()`
- [ ] `reasoning/app/pipeline/prefetch.py` — `prefetch()` orchestration
- [ ] `reasoning/app/pipeline/compose_report.py` — 7th node
- [ ] `reasoning/app/pipeline/report_schema.py` — ReportCard Pydantic models
- [ ] `reasoning/app/pipeline/storage.py` — `write_report()` SQLAlchemy Core INSERT
- [ ] `reasoning/app/pipeline/term_dict.py` — Term dictionary loader + `apply_terms()`
- [ ] `reasoning/app/pipeline/term_dict_vi.json` — Vietnamese term dictionary (Claude drafts, user reviews)
- [ ] `reasoning/app/nodes/state.py` — Add `language: str` and `report_output: Optional[ReportOutput]` fields
- [ ] `reasoning/tests/pipeline/` directory and `__init__.py`
- [ ] `reasoning/tests/pipeline/conftest.py` — Mock pipeline fixtures (prefetched state + all node outputs)
- [ ] `reasoning/tests/pipeline/test_graph.py` — Graph definition tests
- [ ] `reasoning/tests/pipeline/test_compose_report.py` — compose_report_node tests
- [ ] `reasoning/tests/pipeline/test_term_dict.py` — Term dictionary tests
- [ ] `reasoning/tests/pipeline/test_e2e.py` — E2E integration test
- [ ] Verify `langgraph-checkpoint-postgres` is available: `pip show langgraph-checkpoint-postgres`
- [ ] `reasoning/app/pipeline/report_schema.py` — Add `reports` Table definition for SQLAlchemy autoload

---

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/langchain_oss_python_langgraph` — `StateGraph.add_node`, `add_edge`, `START`/`END`, `compile(checkpointer=...)`, `AsyncPostgresSaver.from_conn_string`, `ainvoke` with `thread_id` config
- Context7 `/langchain-ai/langgraph` — `PostgresSaver`/`AsyncPostgresSaver` from `langgraph.checkpoint.postgres.aio`, `autocommit=True` + `row_factory=dict_row` requirement, checkpoint table structure
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/nodes/state.py` — `ReportState` TypedDict schema (13 keys), all Pydantic output models, `GroundingError` exception
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/nodes/__init__.py` — All 6 nodes exported and ready for assembly
- `/Users/phananhle/Desktop/phananhle/stratum/db/migrations/V6__reports.sql` — Exact `reports` table schema (columns, constraints, indexes)
- `/Users/phananhle/Desktop/phananhle/stratum/.planning/phases/03-infrastructure-hardening-and-database-migrations/03-03-PLAN.md` — `langgraph` schema creation decisions; `?options=-csearch_path=langgraph` connection pattern established
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/retrieval/postgres_retriever.py` — SQLAlchemy Core INSERT pattern (established project standard)
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/retrieval/freshness.py` — `check_freshness()` + `FRESHNESS_THRESHOLDS` for DATA WARNING generation
- `/Users/phananhle/Desktop/phananhle/stratum/.planning/STATE.md` — WGC 501 gap documented as known blocker; bilingual generation decision confirmed

### Secondary (MEDIUM confidence)
- Phase 6 RESEARCH.md patterns for `with_structured_output` — still valid for `compose_report_node`'s Gemini calls
- Python `copy.deepcopy()` for state isolation between language invocations — standard Python stdlib behavior

### Tertiary (LOW confidence)
- URL encoding of `?options=-csearch_path=langgraph` vs `%3D` — exact encoding accepted by psycopg3 URL parser not verified; test both during Wave 0
- `langgraph-checkpoint-postgres` package availability as standalone vs bundled — verify with `pip show langgraph-checkpoint-postgres` in the reasoning venv

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — LangGraph StateGraph patterns verified via Context7; all libraries already installed; PostgreSQL schema pre-created in Phase 3
- Architecture: HIGH — two-stage prefetch/run_graph design locked in CONTEXT.md; StateGraph linear topology appropriate for deterministic pipeline; SQLAlchemy Core INSERT matches established pattern
- Pitfalls: HIGH — schema search path issue confirmed by Phase 3 design decisions; state mutation between invocations is a known Python dict behavior; most pitfalls derived from existing code review
- Bilingual generation: MEDIUM — "independently authored, not translation" approach is correct but the exact Gemini prompt strategy for `compose_report_node` bilingual generation needs validation during implementation
- `langgraph-checkpoint-postgres` availability: LOW — not verified if it ships bundled with `langgraph>=0.2.0` or requires separate install; Wave 0 must verify

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (LangGraph checkpointer API moves fast; re-verify `AsyncPostgresSaver` import path if >30 days)
