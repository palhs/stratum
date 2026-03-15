# Phase 6: LangGraph Reasoning Nodes - Research

**Researched:** 2026-03-16
**Domain:** LangGraph node functions, Pydantic v2 structured output via Gemini, grounding verification, TypedDict state design, conflict pattern routing
**Confidence:** HIGH (core LangGraph node patterns verified via Context7; Gemini structured output via langchain-google verified; node-level patterns confirmed; one MEDIUM-confidence item on grounding check implementation approach)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Gold vs equity valuation:**
- Separate valuation assessments for gold and VN equities — not unified
- Gold valuation uses: real yield (FRED data) + GLD ETF flow + macro regime overlay (uses macro_regime node output as context for gold-specific interpretation)
- WGC central bank buying data flagged as DATA WARNING per existing convention (501 stub)
- VN equity valuation compares current P/E, P/B against top 2-3 historical regime analogues weighted by similarity score from Neo4j HAS_ANALOGUE relationships
- When fundamental data is missing (e.g., newly listed stock, no P/E), produce partial assessment with available data and flag which metrics are missing — do not skip entirely

**Entry quality tier criteria:**
- Structure has veto power — weak structure caps the tier regardless of how strong macro and valuation signals are (aligns with Stratum core value: protect from entering at structurally dangerous levels)
- Sub-assessments use domain-specific labels, not uniform 4-tier:
  - Macro: Supportive / Mixed / Headwind (or similar domain-appropriate labels)
  - Valuation: Attractive / Fair / Stretched (or similar)
  - Structure: Constructive / Neutral / Deteriorating (or similar)
- Composite tier remains: Favorable / Neutral / Cautious / Avoid
- When all data sources are stale, still produce a tier but with prominent STALE DATA caveat — do not force Avoid tier on staleness alone
- Tier assignment method (rules-first vs LLM-decided): Claude's discretion

**Conflicting signal presentation:**
- Use both named conflict patterns AND narrative explanation — pattern as header, prose paragraph explaining specifics
- Examples of named patterns: "Strong Thesis, Weak Structure", "Cheap but Deteriorating", etc.
- Structure-biased guidance when signals conflict — the handler notes that structure is the dominant safety signal, consistent with Stratum's core value
- Conflict severity determines tier impact: minor conflicts (e.g., slightly cautious structure with strong everything else) can still be Favorable; major conflicts (e.g., structure = Avoid) force downgrade
- Number of pre-defined conflict patterns: Claude's discretion

**Grounding check strictness:**
- Verify both raw database values AND derived calculation chains (e.g., "P/E is 30% above the analogue average" must trace to source P/E, source analogue P/E values, and valid arithmetic)
- Grounding check runs after each node independently — catches errors early before downstream nodes build on ungrounded claims
- Qualitative claims (non-numeric) require source attribution — cite which data source informed the interpretation (e.g., "based on FRED indicators"), not a specific record ID
- Fail mode when unattributed numeric claim is found: Claude's discretion (SC #5 says "raises an explicit error")

### Claude's Discretion
- Tier assignment method (deterministic rules vs LLM-interpreted)
- Number and naming of conflict patterns
- Grounding check fail mode (error vs flag-and-continue)
- Gemini model selection, temperature, and token budget per node
- ReportState TypedDict schema design and reducer patterns
- Exact domain-specific sub-assessment label vocabulary
- Node testing strategy (mock state construction)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REAS-01 | Macro regime classification node outputs probability distribution over regime types with mixed-signal handling (top confidence < 70% surfaces "Mixed Signal Environment") | LangGraph node function pattern verified; Gemini structured output with Pydantic enables regime probability dict; mixed-signal routing via conditional edge or inline logic |
| REAS-02 | Valuation assessment node produces regime-relative valuation for VN equities (P/E, P/B vs historical analogues) and gold (real yield, ETF flow context) | Retrieval layer (postgres_retriever + neo4j_retriever) already in place; node consumes RegimeAnalogue + FundamentalsRow; dual-path (equity vs gold) via asset_type dispatch |
| REAS-03 | Price structure node interprets pre-computed v1.0 markers (MAs, drawdown, percentile) into narrative without recomputation | get_structure_markers() from postgres_retriever returns StructureMarkerRow directly; node reads and interprets, never computes |
| REAS-04 | Entry quality assessment node outputs qualitative tier (Favorable / Neutral / Cautious / Avoid) with three visible sub-assessments (macro, valuation, structure) | Composite logic with structure-veto pattern; Pydantic output model must include all three sub-assessments before composite field |
| REAS-05 | Grounding check node verifies every numeric claim in report output traces to a specific retrieved database record | Post-processing node inspects prior node outputs; Pydantic source_id citation pattern; raises GroundingError on unattributed numeric claim |
| REAS-07 | Conflicting signal handling produces explicit "strong thesis, weak structure" report type when sub-assessments disagree | Conflict detection logic compares sub-assessment labels; named pattern enum + narrative generation; severity determines tier impact |
</phase_requirements>

---

## Summary

Phase 6 builds six LangGraph node functions (structure, valuation, macro_regime, entry_quality, grounding_check, conflicting_signals) and validates each individually with mock state. These nodes are **not yet assembled into a StateGraph** — that is Phase 7. Each node is a plain Python function that accepts a TypedDict-compatible state dict, calls retrieval layer functions, invokes Gemini via `langchain-google-genai`, and returns a Pydantic-validated dict update.

The core architectural pattern is: (1) define a `ReportState` TypedDict with annotated keys for each node's contribution, (2) implement each node as a standalone function that reads inputs from state and writes one specific key back, (3) validate each node independently against mock state before any graph wiring. All node outputs are Pydantic v2 BaseModel instances stored in state — this is the "typed intermediate results" pattern that enables the grounding_check node to inspect upstream outputs structurally.

The grounding_check is the only architecturally novel node: it is a post-processing inspector that walks the Pydantic output of each upstream node and verifies that every `float` field in the output has a corresponding `source_id` citation. The implementation recommendation is to add a `sources: dict[str, str]` field to every node output model (mapping claim_key → source_id), then grounding_check validates completeness. When a numeric claim cannot be attributed, it raises a `GroundingError` exception — this propagates up through LangGraph's error handling as an explicit failure, not a warning.

**Primary recommendation:** Use `langchain-google-genai` (already available via `langchain-google` package) with `with_structured_output(PydanticModel)` for all Gemini calls. Design one Pydantic output model per node. Structure the `ReportState` TypedDict with one key per node output — no reducers needed for node outputs (each node writes its own key exactly once in a linear pipeline). Add LangGraph and langchain-google-genai to `reasoning/requirements.txt` before building any nodes.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=0.2.0 | Node function execution framework, StateGraph for Phase 7 | Required by REAS-06 (Phase 7); nodes must be compatible with StateGraph |
| langchain-google-genai | >=2.0.0 | `ChatGoogleGenerativeAI` + `with_structured_output()` | Official LangChain Gemini integration; handles structured output natively |
| langchain-core | >=0.3.0 | `HumanMessage`, `SystemMessage`, prompt templates | Required dependency of langchain-google-genai |
| pydantic | v2 (already installed) | Node output models, source citation tracking | Already in reasoning/requirements.txt; established project pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain-google-genai (google-genai SDK) | >=1.0.0 | Underlying Gemini client | Used automatically by ChatGoogleGenerativeAI |
| pytest | >=8.0.0 (already installed) | Node-level unit tests with mock state | Phase 6 validation — mock state tests require no live Docker services |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `langchain-google-genai` with `with_structured_output` | `google-genai` SDK directly with `genai.Client()` | Direct SDK avoids LangChain abstraction but loses LangGraph state compatibility; LangChain is correct for nodes that will be wired into StateGraph in Phase 7 |
| Pydantic output models per node | TypedDict for intermediate results | TypedDict lacks runtime validation; Pydantic v2 catches LLM hallucinations at parse time |
| LangGraph `Command` object for routing | Conditional edges | `Command` enables routing from inside the node; cleaner for conflicting_signals handler; both are valid |

**Installation additions to `reasoning/requirements.txt`:**
```bash
pip install langgraph>=0.2.0 langchain-google-genai>=2.0.0 langchain-core>=0.3.0
```

---

## Architecture Patterns

### Recommended Project Structure
```
reasoning/
├── app/
│   ├── retrieval/           # Already exists (Phase 5) — do not modify
│   ├── models/              # Already exists (Phase 5) — do not modify
│   └── nodes/               # NEW in Phase 6
│       ├── __init__.py      # Public API: exports all 6 node functions
│       ├── state.py         # ReportState TypedDict + all Pydantic output models
│       ├── macro_regime.py  # macro_regime_node(state) -> dict
│       ├── valuation.py     # valuation_node(state) -> dict
│       ├── structure.py     # structure_node(state) -> dict
│       ├── entry_quality.py # entry_quality_node(state) -> dict
│       ├── grounding_check.py # grounding_check_node(state) -> dict; raises GroundingError
│       └── conflicting_signals.py # conflicting_signals_handler(state) -> dict
└── tests/
    ├── conftest.py          # Already exists — add mock_state fixture
    └── nodes/               # NEW in Phase 6
        ├── __init__.py
        ├── test_macro_regime.py
        ├── test_valuation.py
        ├── test_structure.py
        ├── test_entry_quality.py
        ├── test_grounding_check.py
        └── test_conflicting_signals.py
```

### Pattern 1: Node Function Signature
**What:** Each node is a plain Python function accepting `state: ReportState` and returning a dict with one or more state key updates.
**When to use:** All six nodes follow this pattern.
**Example:**
```python
# Source: https://docs.langchain.com/oss/python/langgraph/use-graph-api
from typing_extensions import TypedDict
from reasoning.app.nodes.state import ReportState, MacroRegimeOutput

def macro_regime_node(state: ReportState) -> dict:
    """
    Classify current macro regime from FRED indicators + Neo4j analogues.
    Returns: {"macro_regime_output": MacroRegimeOutput}
    """
    # 1. Pull inputs from state (set by caller/orchestrator in Phase 7)
    ticker = state["ticker"]
    fred_rows = state["fred_rows"]      # list[FredIndicatorRow] — pre-fetched
    analogues = state["regime_analogues"]  # list[RegimeAnalogue] — pre-fetched

    # 2. Call Gemini with structured output
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
    structured_llm = llm.with_structured_output(MacroRegimeOutput)
    result: MacroRegimeOutput = structured_llm.invoke([
        SystemMessage(content=MACRO_REGIME_SYSTEM_PROMPT),
        HumanMessage(content=build_macro_regime_prompt(fred_rows, analogues)),
    ])

    # 3. Return state update (single key per node)
    return {"macro_regime_output": result}
```

### Pattern 2: ReportState TypedDict with Node Output Keys
**What:** One TypedDict holds all state across nodes. Each node writes its own key. No reducers needed (linear pipeline, each key written exactly once).
**When to use:** Phase 6 defines the schema; Phase 7 wires nodes into StateGraph.
**Example:**
```python
# reasoning/app/nodes/state.py
from typing import Optional
from typing_extensions import TypedDict
from reasoning.app.retrieval.types import (
    FredIndicatorRow, RegimeAnalogue, FundamentalsRow,
    StructureMarkerRow, GoldPriceRow, GoldEtfRow, DocumentChunk,
)

class ReportState(TypedDict):
    # --- Inputs (set by orchestrator in Phase 7) ---
    ticker: str
    asset_type: str   # "equity" | "gold"

    # --- Pre-fetched retrieval outputs (set by orchestrator) ---
    fred_rows: list[FredIndicatorRow]
    regime_analogues: list[RegimeAnalogue]
    macro_docs: list[DocumentChunk]
    fundamentals_rows: list[FundamentalsRow]          # equity only
    structure_marker_rows: list[StructureMarkerRow]
    gold_price_rows: list[GoldPriceRow]               # gold only
    gold_etf_rows: list[GoldEtfRow]                   # gold only

    # --- Node outputs (written by each node) ---
    macro_regime_output: Optional[MacroRegimeOutput]
    valuation_output: Optional[ValuationOutput]
    structure_output: Optional[StructureOutput]
    entry_quality_output: Optional[EntryQualityOutput]
    grounding_result: Optional[GroundingResult]
    conflict_output: Optional[ConflictOutput]       # set only when conflict detected
```

### Pattern 3: Pydantic Node Output Model with Source Citations
**What:** Every node output model includes a `sources` dict mapping each numeric claim key to its source record ID. This is what the grounding_check node inspects.
**When to use:** All node output models that produce numeric claims.
**Example:**
```python
# reasoning/app/nodes/state.py (continued)
from pydantic import BaseModel, Field

class RegimeProbability(BaseModel):
    regime_id: str
    regime_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_analogue_id: str   # Neo4j analogue_id that supports this probability

class MacroRegimeOutput(BaseModel):
    regime_probabilities: list[RegimeProbability]
    top_regime_id: str
    top_confidence: float
    is_mixed_signal: bool      # True when top_confidence < 0.70
    mixed_signal_label: Optional[str] = None  # "Mixed Signal Environment"
    top_two_analogues: list[str] = []         # analogue_ids when is_mixed_signal=True
    macro_label: str            # "Supportive" | "Mixed" | "Headwind"
    narrative: str
    sources: dict[str, str]     # claim_key -> source_id (e.g. "top_confidence" -> "fred:FEDFUNDS:2024-01-01")
    warnings: list[str] = []    # propagated from retrieval layer
```

### Pattern 4: Gemini `with_structured_output` via LangChain
**What:** `ChatGoogleGenerativeAI.with_structured_output(PydanticModel)` returns a chain that parses Gemini's response directly into the Pydantic model, raising `ValidationError` on parse failure.
**When to use:** All Gemini LLM calls in Phase 6 nodes.
**Example:**
```python
# Source: https://context7.com/langchain-ai/langchain-google/llms.txt
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.1,
    google_api_key=os.environ["GEMINI_API_KEY"],
)
structured_llm = llm.with_structured_output(MacroRegimeOutput)
result: MacroRegimeOutput = structured_llm.invoke([
    SystemMessage(content="You are a macro regime analyst..."),
    HumanMessage(content=context_text),
])
# result is a validated MacroRegimeOutput instance
```

### Pattern 5: Mixed Signal Handler (Inline Branch vs Separate Handler)
**What:** The conflicting_signals handler can be implemented as either a separate node or inline logic within entry_quality_node. Based on the success criteria (SC #6) and CONTEXT.md, it is a separate handler that inspects sub-assessment label combinations and produces a `ConflictOutput` when disagreement is detected.
**When to use:** When entry_quality_node detects that sub-assessments conflict (e.g., macro=Supportive + structure=Deteriorating).
**Example:**
```python
# reasoning/app/nodes/conflicting_signals.py
NAMED_CONFLICT_PATTERNS = {
    ("Supportive", "Attractive", "Deteriorating"): "Strong Thesis, Weak Structure",
    ("Supportive", "Stretched", "Deteriorating"):  "Expensive and Deteriorating",
    ("Headwind",   "Attractive", "Constructive"):  "Cheap but Macro Headwind",
    ("Headwind",   "Attractive", "Deteriorating"): "Cheap but Deteriorating",
    # ... additional patterns at Claude's discretion
}

def conflicting_signals_handler(state: ReportState) -> dict:
    macro_label    = state["macro_regime_output"].macro_label
    valuation_label = state["valuation_output"].valuation_label
    structure_label = state["structure_output"].structure_label

    key = (macro_label, valuation_label, structure_label)
    pattern_name = NAMED_CONFLICT_PATTERNS.get(key)
    if pattern_name is None:
        # No named conflict — entry_quality proceeds without conflict annotation
        return {"conflict_output": None}

    # Conflict detected — produce named pattern + narrative
    structured_llm = llm.with_structured_output(ConflictOutput)
    result = structured_llm.invoke([...])
    return {"conflict_output": result}
```

### Pattern 6: Grounding Check — Explicit Error on Unattributed Numeric Claim
**What:** grounding_check_node iterates over all node output Pydantic models in state and verifies that every `float` field has a matching key in `sources`. Raises `GroundingError` (not a warning) when any numeric claim is unattributed.
**When to use:** Called after each node independently (per locked decision: "grounding check runs after each node").
**Implementation note:** Since LangGraph StateGraph is not assembled in Phase 6, the grounding check is invoked manually in tests by calling the node function directly after the node under test.
**Example:**
```python
# reasoning/app/nodes/grounding_check.py

class GroundingError(Exception):
    """Raised when a numeric claim in node output cannot be attributed to a source record."""
    pass

def grounding_check_node(state: ReportState) -> dict:
    """
    Verify all numeric claims in node outputs trace to a source record ID.
    Raises GroundingError if any float field lacks a sources entry.
    """
    errors = []
    for output_key in ["macro_regime_output", "valuation_output", "structure_output"]:
        output = state.get(output_key)
        if output is None:
            continue
        _verify_output(output, output_key, errors)

    if errors:
        raise GroundingError(
            f"Grounding check failed — {len(errors)} unattributed numeric claims:\n"
            + "\n".join(errors)
        )
    return {"grounding_result": GroundingResult(status="pass", checked_keys=list(state.keys()))}
```

### Anti-Patterns to Avoid
- **Assembling StateGraph in Phase 6:** Phase 6 is node isolation only. StateGraph assembly, PostgreSQL checkpointing, and inter-node wiring are Phase 7. Do not call `builder.compile()` in Phase 6 code.
- **Importing LangGraph reducers for Phase 6:** No `Annotated[list, operator.add]` reducers needed in Phase 6. The ReportState TypedDict defined here uses plain `Optional[NodeOutput]` fields — Phase 7 may add reducers if parallel execution is needed, but Phase 6 keeps it simple.
- **Calling Gemini without `with_structured_output`:** Using `llm.invoke()` and then manually parsing the string output is fragile. Always use `llm.with_structured_output(PydanticModel)` so Pydantic validation catches malformed LLM output at parse time.
- **Raising GroundingError on qualitative claims:** The locked decision specifies: qualitative claims require source attribution by data source name (e.g., "based on FRED indicators"), not by record ID. Only `float` fields and derived calculations require record ID citations. Do not run regex on narrative strings.
- **Having structure_node recompute MA or drawdown:** Per SC #3, the structure node reads `StructureMarkerRow` fields and produces narrative — it must never compute its own MA from price data. All computation is pre-computed by the v1.0 marker pipeline in PostgreSQL.
- **Forcing Avoid tier on stale data alone:** The locked decision explicitly says "produce a tier with STALE DATA caveat" — staleness does not default to Avoid. The tier is still computed from the actual (stale) data signals.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gemini structured JSON parsing | Custom regex/string parser on LLM response | `ChatGoogleGenerativeAI.with_structured_output(PydanticModel)` | Handles JSON extraction, Pydantic validation, retry on parse failure; LangChain manages the complexity |
| Probability distribution normalization for regime probabilities | Manual sum-and-normalize loop | Pydantic `model_validator` + `Field(ge=0.0, le=1.0)` | Validate at parse time; let Pydantic reject invalid distributions |
| LLM retry on structured output parse failure | Custom retry wrapper with exponential backoff | LangChain's built-in retry via `.with_retry()` on the chain | Off-the-shelf; handles `OutputParserException` correctly |
| Token budget enforcement | Custom truncation logic | Explicit context window management in prompt builder functions — keep prompts concise | Gemini 2.0 Flash has 1M context; token budget is about cost/speed, not correctness. Keep data payloads minimal |
| Conflict pattern matching | Complex NLP-based signal comparison | Enum-based lookup dict on (macro_label, valuation_label, structure_label) tuple | Labels are controlled vocabulary (locked enum values); tuple lookup is O(1) and deterministic |

**Key insight:** Phase 6's complexity is in the design of the Pydantic output schemas and prompt engineering — not in infrastructure. All the LLM call mechanics (structured output, retry, async/sync) are handled by LangChain. Focus engineering effort on schema correctness and grounding verification logic.

---

## Common Pitfalls

### Pitfall 1: `with_structured_output` Model Inconsistency Between LangChain Versions
**What goes wrong:** `ChatGoogleGenerativeAI.with_structured_output(MyModel)` works differently between `langchain-google-genai` 1.x and 2.x. In 1.x, it uses `from langchain_core.pydantic_v1 import BaseModel` internally; in 2.x it uses native Pydantic v2.
**Why it happens:** The project uses Pydantic v2 throughout (established in Phase 5). If `langchain-google-genai` 1.x is installed, there are subtle incompatibilities with `model_dump()` vs `dict()`.
**How to avoid:** Pin `langchain-google-genai>=2.0.0` in requirements.txt. Use `pydantic.BaseModel` (not `langchain_core.pydantic_v1.BaseModel`) for all node output models.
**Warning signs:** `AttributeError: model_dump` or `ValidationError` that refers to pydantic_v1 types.

### Pitfall 2: Gemini `with_structured_output` Drops Optional Fields
**What goes wrong:** If `Optional[str]` fields in the Pydantic model have no default, Gemini may omit them from the JSON response, causing `ValidationError: field required`.
**Why it happens:** Gemini treats fields without explicit defaults as required, but the LLM may not always include them.
**How to avoid:** All `Optional` fields MUST have `= None` default. Example: `top_two_analogues: list[str] = []` not `top_two_analogues: list[str]`.
**Warning signs:** `ValidationError: 1 validation error for MacroRegimeOutput / top_two_analogues / Field required`.

### Pitfall 3: State Key Collisions When Testing Nodes in Isolation
**What goes wrong:** Testing `entry_quality_node` requires `macro_regime_output`, `valuation_output`, and `structure_output` to already be in state. Building these mock objects manually is verbose and may diverge from actual node output schemas.
**Why it happens:** Phase 6 tests node isolation but node outputs have upstream dependencies.
**How to avoid:** Build pytest fixtures that construct valid mock `MacroRegimeOutput`, `ValuationOutput`, and `StructureOutput` Pydantic instances using `model_validate({...})` with representative but minimal data. Keep one fixture file per node output model in `tests/nodes/conftest.py`.
**Warning signs:** Test code that manually constructs large dicts for mock state — sign that fixtures are missing.

### Pitfall 4: `GroundingError` Raised During Normal Stale-Data Flows
**What goes wrong:** The grounding check incorrectly flags stale-data values as unattributed because the source_id for a stale record may be formatted differently (e.g., includes a stale warning tag).
**Why it happens:** Grounding check logic is too strict about source_id format.
**How to avoid:** Source IDs should always be the bare database record key (e.g., `"fred:FEDFUNDS:2024-01-01"`). Staleness warnings go in the `warnings: list[str]` field and are completely separate from source attribution. The grounding check only checks presence of a source_id, not freshness.
**Warning signs:** `GroundingError` raised when data is correct but stale.

### Pitfall 5: Structure Node Accidentally Fetching Data
**What goes wrong:** A developer adds a direct call to `get_structure_markers()` inside `structure_node()` to get "the latest data," bypassing the pre-fetched state.
**Why it happens:** The distinction between pre-fetched retrieval outputs (in state) and live queries is not explicitly enforced.
**How to avoid:** By convention, all Phase 6 nodes read exclusively from `state`. Retrieval functions are called by the orchestrator (Phase 7), not by nodes. Document this at the top of each node file. The test strategy enforces this: unit tests pass mock state with no live DB connections.
**Warning signs:** Any `import` of retrieval functions inside a node module (except for type imports).

### Pitfall 6: Mixed-Signal Threshold Is Exclusive of 70%
**What goes wrong:** Per SC #1, `top_confidence < 0.70` triggers mixed signal. An implementation using `<= 0.70` would incorrectly flag a 70% confident reading as mixed.
**Why it happens:** Off-by-one on threshold boundary.
**How to avoid:** Use strict less-than: `is_mixed_signal = (top_confidence < 0.70)`. Document the boundary in a constant: `MIXED_SIGNAL_THRESHOLD = 0.70`.
**Warning signs:** Test case at exactly 70% behaving inconsistently.

---

## Code Examples

Verified patterns from official sources:

### Gemini Structured Output with Pydantic v2
```python
# Source: https://context7.com/langchain-ai/langchain-google/llms.txt
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
import os

class MacroRegimeOutput(BaseModel):
    top_regime_id: str
    top_confidence: float = Field(ge=0.0, le=1.0)
    is_mixed_signal: bool
    macro_label: str
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.1,
    google_api_key=os.environ["GEMINI_API_KEY"],
)
structured_llm = llm.with_structured_output(MacroRegimeOutput)
result: MacroRegimeOutput = structured_llm.invoke([
    SystemMessage(content="Classify the current macro regime based on FRED data."),
    HumanMessage(content="FEDFUNDS: 5.33%, UNRATE: 3.7%, CPI: 3.2%..."),
])
assert isinstance(result, MacroRegimeOutput)
assert result.top_confidence >= 0.0
```

### Mock State Construction for Node Unit Tests
```python
# tests/nodes/conftest.py
import pytest
from reasoning.app.nodes.state import MacroRegimeOutput, ValuationOutput, StructureOutput, ReportState
from reasoning.app.retrieval.types import FredIndicatorRow, RegimeAnalogue, StructureMarkerRow
from datetime import datetime, timezone

@pytest.fixture
def mock_macro_output() -> MacroRegimeOutput:
    return MacroRegimeOutput(
        top_regime_id="aggressive_tightening",
        top_confidence=0.82,
        is_mixed_signal=False,
        macro_label="Headwind",
        narrative="Rising rates environment with elevated inflation.",
        sources={"top_confidence": "fred:FEDFUNDS:2024-01-01"},
        warnings=[],
    )

@pytest.fixture
def base_report_state(mock_macro_output) -> ReportState:
    return {
        "ticker": "VNM",
        "asset_type": "equity",
        "fred_rows": [],
        "regime_analogues": [],
        "macro_docs": [],
        "fundamentals_rows": [],
        "structure_marker_rows": [],
        "gold_price_rows": [],
        "gold_etf_rows": [],
        "macro_regime_output": mock_macro_output,
        "valuation_output": None,
        "structure_output": None,
        "entry_quality_output": None,
        "grounding_result": None,
        "conflict_output": None,
    }
```

### Entry Quality Tier with Structure Veto Logic
```python
# reasoning/app/nodes/entry_quality.py (excerpt)
STRUCTURE_VETO_MAP = {
    "Deteriorating": "Cautious",  # Structure=Deteriorating caps tier at Cautious
    "Avoid":         "Avoid",     # Structure=Avoid forces tier to Avoid
}

def _apply_structure_veto(tier: str, structure_label: str) -> str:
    """Apply structure veto: cap tier if structure is weak."""
    TIER_ORDER = ["Favorable", "Neutral", "Cautious", "Avoid"]
    veto_cap = STRUCTURE_VETO_MAP.get(structure_label)
    if veto_cap is None:
        return tier  # No veto for Constructive or Neutral structure
    # Cap tier at veto_cap (take the worse of tier vs cap)
    tier_rank = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    cap_rank  = TIER_ORDER.index(veto_cap)
    return TIER_ORDER[max(tier_rank, cap_rank)]
```

### Grounding Check — Numeric Field Verification
```python
# reasoning/app/nodes/grounding_check.py (excerpt)
def _collect_float_fields(model: BaseModel, prefix: str) -> list[str]:
    """Return field names that are float-typed and non-None."""
    result = []
    for field_name, field_info in model.model_fields.items():
        value = getattr(model, field_name)
        if isinstance(value, float):
            result.append(f"{prefix}.{field_name}")
    return result

def _verify_output(output: BaseModel, output_key: str, errors: list[str]) -> None:
    """Check all float fields have entries in output.sources."""
    sources = getattr(output, "sources", {})
    for claim_key in _collect_float_fields(output, output_key):
        short_key = claim_key.split(".")[-1]
        if short_key not in sources:
            errors.append(f"Unattributed numeric claim: {claim_key} (no entry in sources)")
```

---

## Gemini Model Selection (Claude's Discretion)

Based on verified documentation and project constraints:

**Recommendation: `gemini-2.0-flash` for all nodes, `temperature=0.1`**

Rationale:
- `gemini-2.0-flash` has a 1M token context window — sufficient for multi-node structured output generation
- Temperature 0.1 (not 0.0) reduces hallucination risk while preserving some narrative variation — important for regime classification and structure narrative nodes
- `gemini-2.5-flash` (Preview as of early 2026) is faster and cheaper but Preview status carries breaking-change risk; benchmark against 2.0-flash during Wave 0 before committing
- `gemini-1.5-pro` is higher quality for complex reasoning but ~3x the cost; use only for `macro_regime_node` if 2.0-flash produces poor probability distributions

The STATE.md pending todo notes: "Gemini model selection (2.0-flash vs 2.5-flash) — benchmark during Phase 6 before committing to production config." This benchmark should be a Wave 0 task using the same structured output schema.

**Token budget estimate per node call:**
| Node | Input tokens (est.) | Output tokens (est.) |
|------|--------------------|--------------------|
| macro_regime | ~2,000 (FRED rows + analogue narratives) | ~500 |
| valuation (equity) | ~3,000 (fundamentals + analogue P/E + macro context) | ~700 |
| valuation (gold) | ~2,500 (FRED real yield + ETF flows + macro context) | ~600 |
| structure | ~1,000 (structure marker row) | ~400 |
| entry_quality | ~1,500 (3 sub-assessment outputs) | ~300 |
| grounding_check | ~2,000 (all node outputs) | ~200 |
| conflicting_signals | ~2,000 (sub-assessment labels + narratives) | ~500 |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain `LLMChain` with output parsers | `with_structured_output(PydanticModel)` | LangChain 0.1+ | Native Pydantic binding; no custom parser needed; ValidationError on failure |
| `google-generativeai` SDK directly | `langchain-google-genai` | 2024 migration in this project (commit e01a362 in STATE.md) | Consistent with LangChain ecosystem; ready for Phase 7 StateGraph wiring |
| LangGraph nodes with `MessagesState` | LangGraph nodes with domain TypedDict | LangGraph 0.1+ | Custom TypedDict enables typed intermediate results per domain; not limited to message lists |
| Grounding as post-hoc audit | Grounding as explicit pipeline node | Phase 6 decision | Early failure on unattributed claims; prevents downstream nodes from reasoning over hallucinated values |

**Deprecated/outdated:**
- `google-generativeai` Python SDK: Project STATE.md confirms migration to `google-genai>=1.0.0` (commit e01a362). Use `ChatGoogleGenerativeAI` from `langchain-google-genai` in Phase 6.
- `langchain_core.pydantic_v1.BaseModel`: Compatibility shim for Pydantic v1. Use `pydantic.BaseModel` (v2) — already established project standard.

---

## Open Questions

1. **Should retrieval calls happen inside nodes or outside (in the orchestrator)?**
   - What we know: CONTEXT.md `code_context` lists retrieval assets as "reusable" but doesn't specify where they're called. Phase 7 assembles the graph.
   - What's unclear: If retrieval happens inside each node, nodes are self-contained but slower (each makes its own DB calls). If retrieval happens before nodes, the state is pre-populated and nodes are pure transformation functions.
   - Recommendation: **Pre-fetch pattern** — retrieval happens before node execution; nodes read from state only. This makes nodes testable with mock state (no live DB needed in unit tests) and avoids redundant retrieval calls. The orchestrator (Phase 7) fetches all required data before starting the node chain. This aligns with the test strategy in CONTEXT.md ("mock state construction") and with SC #3 (structure node "reads only from PostgreSQL structure_markers" — implying data is already in state).
   - Confidence: HIGH on recommendation.

2. **How should the grounding_check node be positioned in the Phase 6 test pipeline when there is no StateGraph?**
   - What we know: "Grounding check runs after each node independently." StateGraph not assembled until Phase 7.
   - What's unclear: Whether grounding_check tests call the node function directly after each preceding node, or whether tests set up full state with all nodes' outputs and run a single grounding check.
   - Recommendation: Tests for grounding_check should construct state with partially complete outputs (e.g., `macro_regime_output` set, `valuation_output` = None) and verify that only the present outputs are checked. This matches the "runs after each node independently" semantics without a graph.
   - Confidence: MEDIUM — depends on final test strategy decision.

3. **Should `conflicting_signals_handler` be a separate node or a branch inside `entry_quality_node`?**
   - What we know: SC #6 says "conflicting signal handler produces explicit output" — named as a separate handler. CONTEXT.md treats it as a distinct component.
   - What's unclear: Whether it runs before or after entry_quality, and whether it replaces or supplements entry_quality output.
   - Recommendation: Implement as a **pre-step** to entry_quality: conflicting_signals_handler runs first, detects conflicts, and writes `conflict_output` to state. `entry_quality_node` then reads `conflict_output` (if present) to inform tier assignment and include the named conflict pattern in its output. This keeps entry_quality as the single authoritative tier producer.
   - Confidence: MEDIUM — architecture is correct but sequencing may shift when Phase 7 wires the graph.

---

## Validation Architecture

> `workflow.nyquist_validation` key not present in `.planning/config.json`. Including Validation Architecture as directly required by Phase 6 success criteria and locked test strategy ("mock state construction").

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ (already in reasoning/requirements.txt) |
| Config file | `reasoning/pytest.ini` (exists from Phase 5) |
| Quick run command | `pytest reasoning/tests/nodes/ -x` |
| Full suite command | `pytest reasoning/tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REAS-01 | macro_regime_node returns MacroRegimeOutput with `is_mixed_signal=True` when `top_confidence < 0.70`; `top_two_analogues` contains 2 entries | unit (mock state, mock Gemini response) | `pytest reasoning/tests/nodes/test_macro_regime.py -x` | Wave 0 gap |
| REAS-02 | valuation_node produces separate equity/gold outputs depending on asset_type; equity output cites specific analogue_id in sources; gold output cites FRED and GLD sources | unit (mock state) | `pytest reasoning/tests/nodes/test_valuation.py -x` | Wave 0 gap |
| REAS-03 | structure_node reads StructureMarkerRow values and produces narrative without calling any retrieval function | unit (mock state, assert no DB calls) | `pytest reasoning/tests/nodes/test_structure.py -x` | Wave 0 gap |
| REAS-04 | entry_quality_node includes all 3 sub-assessment labels in output before composite tier; structure veto caps tier correctly | unit (mock state with various sub-assessment combinations) | `pytest reasoning/tests/nodes/test_entry_quality.py -x` | Wave 0 gap |
| REAS-05 | grounding_check_node raises GroundingError when a float field has no sources entry; passes when all float fields are attributed | unit (mock state with intentionally unattributed values) | `pytest reasoning/tests/nodes/test_grounding_check.py -x` | Wave 0 gap |
| REAS-07 | conflicting_signals_handler produces ConflictOutput with named pattern when signals disagree; returns None when no conflict | unit (mock state with various label combinations) | `pytest reasoning/tests/nodes/test_conflicting_signals.py -x` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** `pytest reasoning/tests/nodes/test_{node_name}.py -x`
- **Per wave merge:** `pytest reasoning/tests/nodes/ -v`
- **Phase gate:** `pytest reasoning/tests/ -v` (full suite including Phase 5 retrieval tests) before phase close

### Wave 0 Gaps
- [ ] `reasoning/app/nodes/` directory and `__init__.py`
- [ ] `reasoning/app/nodes/state.py` — ReportState TypedDict + all 6 Pydantic output models
- [ ] `reasoning/tests/nodes/` directory and `__init__.py`
- [ ] `reasoning/tests/nodes/conftest.py` — mock fixtures for all 6 output models
- [ ] Add to `reasoning/requirements.txt`: `langgraph>=0.2.0`, `langchain-google-genai>=2.0.0`, `langchain-core>=0.3.0`
- [ ] Gemini model benchmark script (2.0-flash vs 2.5-flash) — validates structured output quality before committing model choice

---

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/langchain_oss_python_langgraph` — TypedDict state patterns, node function signatures, conditional edge routing, Command object for node-level routing
- Context7 `/langchain-ai/langchain-google` — `ChatGoogleGenerativeAI.with_structured_output(PydanticModel)`, nested Pydantic structured output, json_mode, Vertex AI structured output examples
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/retrieval/types.py` — Established Pydantic v2 pattern with `warnings: list[str] = []`; `NoDataError` for empty retrieval
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/retrieval/freshness.py` — `check_freshness()` with `now_override` for testing; warnings propagation pattern
- `/Users/phananhle/Desktop/phananhle/stratum/reasoning/app/retrieval/postgres_retriever.py` — Confirmed sync SQLAlchemy Core pattern; `get_structure_markers()` confirmed as Phase 6 input
- `/Users/phananhle/Desktop/phananhle/stratum/.planning/phases/06-langgraph-reasoning-nodes/06-CONTEXT.md` — User decisions (structure veto, gold vs equity separation, named conflict patterns, grounding check strictness)
- `/Users/phananhle/Desktop/phananhle/stratum/.planning/STATE.md` — Established decisions: Gemini API only; qualitative tier (no score); psycopg2 sync for retrieval; both-layer regime classification

### Secondary (MEDIUM confidence)
- https://docs.langchain.com/oss/python/langgraph/ — LangGraph node patterns, StateGraph TypedDict state, conditional branching (verified via Context7 results)
- https://github.com/langchain-ai/langchain-google — `with_structured_output` method on `ChatGoogleGenerativeAI` (verified via Context7)

### Tertiary (LOW confidence)
- Gemini 2.5-flash Preview stability for production use — not verified; benchmark recommended before committing
- `with_structured_output` retry behavior on `ValidationError` — LangChain documentation describes general retry support but specific behavior for Gemini structured output parse failures not confirmed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — LangGraph node patterns verified via Context7; langchain-google-genai structured output confirmed; existing retrieval layer fully documented
- Architecture: HIGH — ReportState TypedDict design follows LangGraph conventions; node-isolation pattern confirmed; pre-fetch pattern aligns with locked test strategy
- Pitfalls: HIGH — Pydantic v2 / pydantic_v1 issue is a known version compatibility trap; Optional field default issue is documented in Gemini structured output usage; structure veto and threshold boundary pitfalls derived directly from success criteria
- Gemini model selection: MEDIUM — 2.0-flash is the stable choice; 2.5-flash Preview recommendation is LOW confidence

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (LangGraph and langchain-google move fast; re-verify `with_structured_output` API if >30 days)
