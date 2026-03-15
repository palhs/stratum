"""
reasoning/app/nodes/macro_regime.py — macro_regime_node: macro regime classification node.
Phase 6 | Plan 03 | Requirement: REAS-01

Classifies the current macroeconomic environment based on FRED indicator data and
historical regime analogues. Outputs a probability distribution over regime types
with explicit mixed-signal handling when top_confidence < MIXED_SIGNAL_THRESHOLD (0.70).

CRITICAL constraints (REAS-01):
- NO import of retrieval functions — only TYPE imports from retrieval.types
- Read ONLY from state fields — no direct database calls
- mixed-signal logic is DETERMINISTIC in Python — do NOT trust LLM to compute threshold
- is_mixed_signal = (top_confidence < MIXED_SIGNAL_THRESHOLD) — strict less-than
- top_two_analogues populated ONLY when is_mixed_signal is True
- All numeric claims in sources must have source citations
- Warnings from fred_rows and regime_analogues propagated to output
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from reasoning.app.nodes.prompts import format_analogue_context, format_fred_context
from reasoning.app.nodes.state import (
    MACRO_LABELS,
    MIXED_SIGNAL_THRESHOLD,
    MacroRegimeOutput,
    RegimeProbability,
    ReportState,
)
from reasoning.app.retrieval.types import DocumentChunk, FredIndicatorRow, RegimeAnalogue


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.0-flash-001"

_SYSTEM_PROMPT = (
    "You are a macro regime analyst. Classify the current macroeconomic environment "
    "based on FRED indicator data and historical regime analogues. "
    "Output a probability distribution over regime types — probabilities must sum to 1.0. "
    "Each regime probability must reference the specific analogue_id that supports it. "
    "Assign macro_label as one of: Supportive, Mixed, Headwind — based on the regime classification. "
    "Supportive: low rates/easy financial conditions favoring risk assets. "
    "Headwind: high rates/tightening/recessionary pressure. "
    "Mixed: conflicting signals across indicators. "
    "Do NOT invent numbers. Reference specific FRED indicator values and analogue period names. "
    "Populate sources with 'top_confidence' citing the FRED series IDs used. "
    "If analogue data is unavailable, note this explicitly in narrative and warnings."
)

_MACRO_LABEL_FALLBACKS = {
    "Supportive": "Supportive",
    "Mixed": "Mixed",
    "Headwind": "Headwind",
    # Case-insensitive fallback variants
    "supportive": "Supportive",
    "mixed": "Mixed",
    "headwind": "Headwind",
    "SUPPORTIVE": "Supportive",
    "MIXED": "Mixed",
    "HEADWIND": "Headwind",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_fred_source_string(fred_rows: list[FredIndicatorRow]) -> str:
    """Build a sources string referencing the FRED series IDs used."""
    if not fred_rows:
        return "fred:no_data"
    series_ids = ",".join(row.series_id for row in fred_rows)
    # Use the most recent data_as_of date from the rows
    most_recent = max(fred_rows, key=lambda r: r.data_as_of)
    return f"fred:{series_ids}:{most_recent.data_as_of.strftime('%Y-%m-%d')}"


def _sanitize_macro_label(raw_label: str) -> str:
    """
    Ensure macro_label is one of the valid MACRO_LABELS values.
    If the LLM returns an invalid value, default to 'Mixed'.
    """
    sanitized = _MACRO_LABEL_FALLBACKS.get(raw_label, None)
    if sanitized is not None:
        return sanitized
    # Check if it's already a valid label (case-insensitive)
    for label in MACRO_LABELS:
        if raw_label.lower() == label.lower():
            return label
    return "Mixed"  # Safest default when LLM returns unexpected value


def _build_human_prompt(
    fred_rows: list[FredIndicatorRow],
    analogues: list[RegimeAnalogue],
    macro_docs: list[DocumentChunk],
) -> str:
    """Build the human message prompt for the LLM call."""
    fred_text = format_fred_context(fred_rows)
    analogue_text = format_analogue_context(analogues)

    docs_text = ""
    if macro_docs:
        doc_lines = ["Macro Document Context (FOMC/SBV excerpts):"]
        for doc in macro_docs[:5]:  # Cap at 5 to avoid token explosion
            doc_lines.append(f"  [{doc.source}] (score: {doc.score:.2f}): {doc.text[:300]}")
        docs_text = "\n" + "\n".join(doc_lines)

    no_analogues_note = ""
    if not analogues:
        no_analogues_note = (
            "\nNOTE: No historical regime analogues are available. "
            "Classify based solely on FRED indicator values. "
            "Output a single regime probability with confidence=1.0. "
            "Include a warning in the output about the absence of analogue context."
        )

    return (
        f"Current FRED Macro Indicators:\n{fred_text}\n\n"
        f"Historical Regime Analogues:\n{analogue_text}"
        f"{docs_text}"
        f"{no_analogues_note}\n\n"
        "Classify the current macro regime by:\n"
        "1. Assigning probability weights to each historical analogue regime\n"
        "2. Ensuring probabilities sum to 1.0\n"
        "3. Setting macro_label to one of: Supportive, Mixed, Headwind\n"
        "4. Writing a narrative that references specific FRED indicator values "
        "and analogue period names\n"
        "5. Populating sources with 'top_confidence' citing the FRED series IDs used\n"
        "6. Including any data quality warnings in the warnings list"
    )


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def macro_regime_node(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: classifies current macro regime with probability distribution.

    State reads:
        - state["fred_rows"]: list[FredIndicatorRow]
        - state["regime_analogues"]: list[RegimeAnalogue]
        - state["macro_docs"]: list[DocumentChunk]

    State writes:
        - state["macro_regime_output"]: MacroRegimeOutput

    Post-processing (deterministic, does NOT trust LLM):
        - Sorts regime_probabilities by confidence descending
        - Sets top_regime_id and top_confidence from highest probability
        - is_mixed_signal = (top_confidence < MIXED_SIGNAL_THRESHOLD)  -- strict less-than
        - If is_mixed_signal: set mixed_signal_label, populate top_two_analogues (top 2 IDs)
        - If not is_mixed_signal: clear mixed_signal_label and top_two_analogues
        - Validates macro_label against MACRO_LABELS
        - Ensures sources["top_confidence"] is populated
        - Propagates warnings from fred_rows and regime_analogues

    Does NOT call any retrieval functions. Does NOT recompute raw market data.
    """
    fred_rows: list[FredIndicatorRow] = state.get("fred_rows", [])
    analogues: list[RegimeAnalogue] = state.get("regime_analogues", [])
    macro_docs: list[DocumentChunk] = state.get("macro_docs", [])

    # ---- Collect warnings from input data ----
    all_warnings: list[str] = []

    for row in fred_rows:
        all_warnings.extend(row.warnings)
    for analogue in analogues:
        all_warnings.extend(analogue.warnings)

    if not analogues:
        all_warnings.append(
            "No historical regime analogues available — macro regime classification "
            "based solely on FRED indicator data without analogue context"
        )

    # ---- Build prompts ----
    system_msg = SystemMessage(content=_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=_build_human_prompt(fred_rows, analogues, macro_docs))

    # ---- Call Gemini with structured output ----
    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
        temperature=0.1,  # Low temperature for consistency in probability distribution
    )
    chain = llm.with_structured_output(MacroRegimeOutput)
    gemini_output: MacroRegimeOutput = chain.invoke([system_msg, human_msg])

    # ---- Post-process: deterministic threshold logic ----
    # Sort regime_probabilities by confidence descending
    sorted_probs: list[RegimeProbability] = sorted(
        gemini_output.regime_probabilities,
        key=lambda rp: rp.confidence,
        reverse=True,
    )

    # Determine top confidence from sorted list (fall back to LLM value if empty)
    if sorted_probs:
        top_confidence = sorted_probs[0].confidence
        top_regime_id = sorted_probs[0].regime_id
    else:
        top_confidence = gemini_output.top_confidence
        top_regime_id = gemini_output.top_regime_id

    # CRITICAL: strict less-than semantics (0.70 < 0.70 is False → not mixed signal)
    is_mixed_signal = top_confidence < MIXED_SIGNAL_THRESHOLD

    # Populate mixed-signal fields deterministically
    if is_mixed_signal:
        mixed_signal_label = "Mixed Signal Environment"
        # top_two_analogues: take the top 2 analogue IDs from sorted_probs
        top_two_analogues = [rp.source_analogue_id for rp in sorted_probs[:2]]
    else:
        mixed_signal_label = None
        top_two_analogues = []

    # ---- Validate and sanitize macro_label ----
    macro_label = _sanitize_macro_label(gemini_output.macro_label)

    # ---- Build sources dict ----
    # Ensure top_confidence is sourced; merge with LLM-provided sources
    sources = dict(gemini_output.sources)
    if "top_confidence" not in sources or not sources.get("top_confidence"):
        sources["top_confidence"] = _build_fred_source_string(fred_rows)

    # ---- Merge warnings ----
    all_warnings = all_warnings + list(gemini_output.warnings)

    # ---- Assemble final output ----
    final_output = MacroRegimeOutput(
        regime_probabilities=sorted_probs,
        top_regime_id=top_regime_id,
        top_confidence=top_confidence,
        is_mixed_signal=is_mixed_signal,
        mixed_signal_label=mixed_signal_label,
        top_two_analogues=top_two_analogues,
        macro_label=macro_label,
        narrative=gemini_output.narrative,
        sources=sources,
        warnings=all_warnings,
    )

    return {"macro_regime_output": final_output}
