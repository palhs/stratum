"""
reasoning/app/nodes/structure.py — structure_node: price structure assessment node.
Phase 6 | Plan 01 | Requirement: REAS-03

The structure node is a pure state-to-output transformation:
  1. Reads StructureMarkerRow from state["structure_marker_rows"]
  2. Determines structure_label via deterministic rules (no LLM for classification)
  3. Generates narrative using Gemini with_structured_output(StructureOutput)
  4. Populates sources dict and propagates warnings

CRITICAL constraints (REAS-03, SC #3):
- NO import of retrieval functions (get_structure_markers, etc.)
- Only TYPE imports from retrieval.types are permitted
- NO recomputation of MAs, drawdowns, or percentiles
- Read ONLY from state["structure_marker_rows"]
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from reasoning.app.nodes.prompts import format_structure_context
from reasoning.app.nodes.state import (
    STRUCTURE_LABELS,
    ReportState,
    StructureOutput,
)

# Type-only import from retrieval layer — no function imports
from reasoning.app.retrieval.types import StructureMarkerRow


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a price structure analyst. Interpret pre-computed technical markers "
    "into a narrative assessment. Do NOT compute or recalculate any values — use "
    "only the provided numbers. Do NOT invent prices or moving averages. "
    "Reference the specific MA values and drawdown percentages given. "
    "The structure_label has already been determined by rules — write a narrative "
    "consistent with it. Include both MA positioning and drawdown context."
)

_MODEL = "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# Deterministic label assignment
# ---------------------------------------------------------------------------


def _determine_label(marker: StructureMarkerRow) -> tuple[str, list[str]]:
    """
    Assign structure_label using deterministic rules based on MA positioning and drawdown.

    Returns:
        (structure_label, warnings) where warnings list missing metrics.

    Rules (applied in priority order):
    1. Deteriorating: close < all available MAs AND drawdown > 20%
    2. Deteriorating: close_pct_rank < 0.2 (bottom quintile)
    3. Constructive: close > all available MAs AND drawdown <= 20%
    4. Neutral: mixed signals (close above some MAs but not all, or moderate drawdown)
    """
    warnings: list[str] = []

    # Collect available MA values and note missing ones
    available_mas: dict[str, float] = {}
    missing_mas: list[str] = []

    for ma_field in ["ma_10w", "ma_20w", "ma_50w"]:
        val = getattr(marker, ma_field)
        if val is not None:
            available_mas[ma_field] = val
        else:
            missing_mas.append(ma_field)
            warnings.append(f"{ma_field} is missing from structure_markers")

    close = marker.close
    drawdown = marker.drawdown_from_ath  # negative float or None
    pct_rank = marker.close_pct_rank

    # Edge case: no close value
    if close is None:
        warnings.append("close is missing from structure_markers — cannot assess MA positioning")
        return "Neutral", warnings

    # With no MAs, rely on drawdown and percentile rank
    if not available_mas:
        warnings.append("All moving averages missing — assessment based on drawdown and rank only")
        if drawdown is not None and drawdown < -0.20:
            return "Deteriorating", warnings
        if pct_rank is not None and pct_rank < 0.20:
            return "Deteriorating", warnings
        return "Neutral", warnings

    # Count how many MAs close is above
    above_count = sum(1 for ma_val in available_mas.values() if close > ma_val)
    below_count = sum(1 for ma_val in available_mas.values() if close < ma_val)
    total_available = len(available_mas)

    # Priority 1: Deteriorating — below all MAs with large drawdown
    if below_count == total_available and drawdown is not None and drawdown < -0.20:
        return "Deteriorating", warnings

    # Priority 2: Deteriorating — bottom quintile percentile rank
    if pct_rank is not None and pct_rank < 0.20:
        return "Deteriorating", warnings

    # Priority 3: Deteriorating — below all MAs (even without severe drawdown, it's bearish)
    if below_count == total_available:
        return "Deteriorating", warnings

    # Priority 4: Constructive — above all MAs with moderate drawdown
    if above_count == total_available and (drawdown is None or drawdown > -0.20):
        return "Constructive", warnings

    # Priority 5: Constructive — above all MAs even with some drawdown
    if above_count == total_available:
        return "Constructive", warnings

    # Default: Neutral (mixed MA signals)
    return "Neutral", warnings


# ---------------------------------------------------------------------------
# Source attribution
# ---------------------------------------------------------------------------


def _build_sources(marker: StructureMarkerRow) -> dict[str, str]:
    """
    Build sources dict mapping each present numeric field to its marker row identifier.
    Format: "structure_markers:{symbol}:{data_as_of ISO}"
    """
    source_id = f"structure_markers:{marker.symbol}:{marker.data_as_of.isoformat()}"
    sources: dict[str, str] = {}

    numeric_fields = [
        "close", "ma_10w", "ma_20w", "ma_50w",
        "drawdown_from_ath", "drawdown_from_52w_high",
        "close_pct_rank", "pe_pct_rank",
    ]
    for field in numeric_fields:
        if getattr(marker, field) is not None:
            sources[field] = source_id

    return sources


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def structure_node(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: reads pre-computed structure markers, produces StructureOutput.

    State reads:
        - state["structure_marker_rows"]: list[StructureMarkerRow]
    State writes:
        - state["structure_output"]: StructureOutput

    Does NOT call any retrieval functions. Does NOT recompute any metrics.
    """
    marker_rows: list[StructureMarkerRow] = state.get("structure_marker_rows", [])

    # Handle empty marker rows
    if not marker_rows:
        return {
            "structure_output": StructureOutput(
                structure_label="Neutral",
                narrative="No structure marker data available — assessment skipped.",
                sources={},
                warnings=["structure_marker_rows is empty — no data to assess"],
            )
        }

    # Use the first row (typically weekly resolution, set by orchestrator priority)
    marker = marker_rows[0]

    # Step 1: Deterministic label assignment
    structure_label, label_warnings = _determine_label(marker)

    # Step 2: Build context string for Gemini prompt
    context_text = format_structure_context(marker_rows)

    # Step 3: Build sources dict
    sources = _build_sources(marker)

    # Step 4: Propagate warnings from input marker
    all_warnings = list(marker.warnings) + label_warnings

    # Step 5: Generate narrative via Gemini with_structured_output
    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
    )

    human_prompt = (
        f"Structure label (already determined): {structure_label}\n\n"
        f"Pre-computed marker data:\n{context_text}\n\n"
        "Write a narrative assessment consistent with the structure label above. "
        "Reference specific MA values and drawdown percentages. "
        "Include MA positioning (above/below) and drawdown severity context."
    )

    chain = llm.with_structured_output(StructureOutput)
    gemini_output: StructureOutput = chain.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ])

    # Step 6: Ensure the deterministic label overrides Gemini's label (consistency)
    # and merge sources + warnings from both deterministic pass and Gemini output
    final_warnings = all_warnings + list(gemini_output.warnings)

    final_output = StructureOutput(
        structure_label=structure_label,  # deterministic — authoritative
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        drawdown_from_52w_high=marker.drawdown_from_52w_high,
        close_pct_rank=marker.close_pct_rank,
        narrative=gemini_output.narrative,
        sources=sources if sources else gemini_output.sources,
        warnings=final_warnings,
    )

    return {"structure_output": final_output}
