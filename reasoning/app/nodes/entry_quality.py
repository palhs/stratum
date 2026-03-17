"""
reasoning/app/nodes/entry_quality.py — entry_quality_node: composite entry assessment node.
Phase 6 | Plan 04 | Requirements: REAS-04

Synthesizes macro, valuation, and structure sub-assessments into a single composite tier.
Reads conflict_output from state (set by conflicting_signals_handler) to inform tier assignment.

CRITICAL constraints (REAS-04, per CONTEXT.md locked decisions):
- NO import of retrieval functions — only TYPE imports from retrieval.types
- Read ONLY from state fields — no direct database calls
- Structure has VETO power — Deteriorating caps tier at Cautious regardless of other signals
- Sub-assessments use domain-specific labels (not uniform 4-tier)
- NO numeric score field — qualitative tier only (anti-feature, per locked decision)
- Stale data does NOT force Avoid — produce tier with caveat
- Conflict severity determines impact:
  - minor → no automatic downgrade (Favorable can remain)
  - major → downgrade tier by at least 1 level
- Composite tier is DETERMINISTIC — LLM generates narrative only; tier overrides LLM's suggestion
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from reasoning.app.nodes.state import (
    COMPOSITE_TIERS,
    ConflictOutput,
    EntryQualityOutput,
    MacroRegimeOutput,
    ReportState,
    StructureOutput,
    ValuationOutput,
)


# ---------------------------------------------------------------------------
# Constants and tier logic
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.5-pro"

# Structure veto map: structure_label → maximum allowed tier
STRUCTURE_VETO_MAP: dict[str, str] = {
    "Deteriorating": "Cautious",  # Caps composite tier at Cautious
}

# Tier ordering: lower index = more favorable
TIER_ORDER: list[str] = ["Favorable", "Neutral", "Cautious", "Avoid"]

# Label-to-score mapping (higher = more favorable)
_LABEL_SCORES: dict[str, int] = {
    # Macro labels
    "Supportive": 2,
    "Mixed": 1,
    "Headwind": 0,
    # Valuation labels
    "Attractive": 2,
    "Fair": 1,
    "Stretched": 0,
    # Structure labels
    "Constructive": 2,
    "Neutral": 1,
    "Deteriorating": 0,
}

# Score thresholds → composite tier
# Max score = 6 (2+2+2), Min = 0 (0+0+0)
_SCORE_TO_TIER: list[tuple[int, str]] = [
    (5, "Favorable"),   # score 5-6
    (3, "Neutral"),     # score 3-4
    (1, "Cautious"),    # score 1-2
    (0, "Avoid"),       # score 0
]

_SYSTEM_PROMPT = (
    "You are a senior financial analyst producing an entry quality assessment. "
    "You have received macro regime, valuation, and price structure sub-assessments. "
    "Synthesize these into a final entry quality narrative that:\n"
    "1. References all three sub-assessments explicitly (macro, valuation, structure)\n"
    "2. Explains the composite assessment in clear, investment-grade language\n"
    "3. Highlights any conflicts between sub-assessments if present\n"
    "4. Provides practical guidance for the investor\n"
    "5. Notes any stale data caveats if indicated\n"
    "Do NOT invent numerical data. Do NOT assign a numeric score. "
    "The composite_tier will be provided separately — focus on narrative quality. "
    "Keep the narrative to 4-6 sentences."
)


# ---------------------------------------------------------------------------
# Deterministic tier logic helpers
# ---------------------------------------------------------------------------


def _compute_base_tier(macro_label: str, valuation_label: str, structure_label: str) -> str:
    """
    Compute base composite tier from sub-assessment labels using a score model.

    Score model (each label → points):
        Supportive/Attractive/Constructive = 2
        Mixed/Fair/Neutral = 1
        Headwind/Stretched/Deteriorating = 0

    Thresholds:
        5-6 → Favorable
        3-4 → Neutral
        1-2 → Cautious
        0   → Avoid
    """
    macro_score = _LABEL_SCORES.get(macro_label, 1)
    valuation_score = _LABEL_SCORES.get(valuation_label, 1)
    structure_score = _LABEL_SCORES.get(structure_label, 1)
    total = macro_score + valuation_score + structure_score

    for threshold, tier in _SCORE_TO_TIER:
        if total >= threshold:
            return tier
    return "Avoid"


def _apply_structure_veto(tier: str, structure_label: str) -> tuple[str, bool]:
    """
    Apply structure veto: Deteriorating structure caps composite tier at Cautious.

    Returns:
        (final_tier, veto_was_applied)
    """
    if structure_label not in STRUCTURE_VETO_MAP:
        return tier, False

    veto_cap = STRUCTURE_VETO_MAP[structure_label]
    veto_idx = TIER_ORDER.index(veto_cap)
    current_idx = TIER_ORDER.index(tier)

    # If current tier is more favorable (lower index) than the veto cap, apply veto
    if current_idx < veto_idx:
        return veto_cap, True

    # Current tier is already at or worse than veto cap — no change but still record veto
    # (structure_label IS in veto map, so veto_applied=True even if no change needed)
    return tier, True


def _apply_conflict_impact(tier: str, conflict_output: ConflictOutput | None) -> str:
    """
    Apply conflict severity impact to the tier.

    - None: no change
    - minor: no automatic downgrade (Favorable can remain)
    - major: downgrade tier by at least 1 level (Favorable→Neutral, Neutral→Cautious, etc.)
    """
    if conflict_output is None:
        return tier

    if conflict_output.severity == "major":
        current_idx = TIER_ORDER.index(tier)
        # Downgrade by 1 level, capped at "Avoid" (last index)
        new_idx = min(current_idx + 1, len(TIER_ORDER) - 1)
        return TIER_ORDER[new_idx]

    # minor severity → no automatic downgrade
    return tier


def _detect_stale_warnings(*warning_lists: list[str]) -> str | None:
    """
    Check across all input warning lists for stale data markers.
    Returns a caveat string if any stale warnings found, None otherwise.
    """
    stale_warnings = []
    for warnings in warning_lists:
        for w in warnings:
            if "STALE" in w.upper() or "stale" in w.lower() or "stale data" in w.lower():
                stale_warnings.append(w)

    if not stale_warnings:
        return None

    return (
        "STALE DATA CAVEAT: One or more data inputs may be outdated. "
        "Tier reflects current available signals; verify freshness before acting. "
        f"Affected: {len(stale_warnings)} warning(s) detected."
    )


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def entry_quality_node(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: produces composite entry quality assessment.

    State reads:
        - state["macro_regime_output"]: MacroRegimeOutput
        - state["valuation_output"]: ValuationOutput
        - state["structure_output"]: StructureOutput
        - state["conflict_output"]: ConflictOutput | None (set by conflicting_signals_handler)

    State writes:
        - state["entry_quality_output"]: EntryQualityOutput

    Tier assignment pipeline (DETERMINISTIC — not LLM):
        1. Compute base tier from label scores
        2. Apply structure veto (Deteriorating caps at Cautious)
        3. Apply conflict impact (major → downgrade 1 level; minor → no change)
        4. Override LLM's composite_tier with the rule-derived tier

    LLM is called ONLY for narrative generation.
    Does NOT call any retrieval functions. Does NOT recompute raw market data.
    """
    macro_output: MacroRegimeOutput | None = state.get("macro_regime_output")
    valuation_output: ValuationOutput | None = state.get("valuation_output")
    structure_output: StructureOutput | None = state.get("structure_output")
    conflict_output: ConflictOutput | None = state.get("conflict_output")

    # ---- Extract labels (graceful fallbacks) ----
    macro_label: str = macro_output.macro_label if macro_output else "Mixed"
    valuation_label: str = valuation_output.valuation_label if valuation_output else "Fair"
    structure_label: str = structure_output.structure_label if structure_output else "Neutral"

    # ---- Collect all warnings for stale detection ----
    macro_warnings = macro_output.warnings if macro_output else []
    valuation_warnings = valuation_output.warnings if valuation_output else []
    structure_warnings = structure_output.warnings if structure_output else []

    # ---- Stale data detection ----
    stale_data_caveat = _detect_stale_warnings(
        macro_warnings, valuation_warnings, structure_warnings
    )

    # ---- Deterministic tier pipeline ----
    base_tier = _compute_base_tier(macro_label, valuation_label, structure_label)
    vetoed_tier, veto_applied = _apply_structure_veto(base_tier, structure_label)
    final_tier = _apply_conflict_impact(vetoed_tier, conflict_output)

    # ---- Prepare sub-assessment strings for output ----
    macro_assessment = (
        macro_output.narrative[:200] if macro_output and macro_output.narrative
        else f"Macro regime: {macro_label}"
    )
    valuation_assessment = (
        valuation_output.narrative[:200] if valuation_output and valuation_output.narrative
        else f"Valuation: {valuation_label}"
    )
    structure_assessment = (
        structure_output.narrative[:200] if structure_output and structure_output.narrative
        else f"Price structure: {structure_label}"
    )

    # ---- Build LLM prompt for narrative synthesis ----
    conflict_section = ""
    if conflict_output:
        conflict_section = (
            f"\nConflict Detected:\n"
            f"  Pattern: {conflict_output.pattern_name}\n"
            f"  Severity: {conflict_output.severity}\n"
            f"  Conflict Narrative: {conflict_output.narrative}\n"
        )

    stale_section = ""
    if stale_data_caveat:
        stale_section = f"\nData Freshness Warning:\n  {stale_data_caveat}\n"

    human_prompt = (
        f"Asset: {state.get('ticker', 'Unknown')} ({state.get('asset_type', 'unknown')})\n\n"
        f"Macro Sub-Assessment ({macro_label}):\n{macro_assessment}\n\n"
        f"Valuation Sub-Assessment ({valuation_label}):\n{valuation_assessment}\n\n"
        f"Structure Sub-Assessment ({structure_label}):\n{structure_assessment}\n"
        f"{conflict_section}"
        f"{stale_section}"
        f"\nComposite Tier (DETERMINISTIC — do not change): {final_tier}\n"
        f"Structure Veto Applied: {veto_applied}\n\n"
        "Write the entry quality narrative synthesizing all three sub-assessments. "
        "Populate macro_assessment, valuation_assessment, and structure_assessment fields "
        "with concise summaries of each sub-assessment. "
        "DO NOT include a numeric score. DO NOT override the composite_tier provided above."
    )

    system_msg = SystemMessage(content=_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=human_prompt)

    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
        temperature=0.2,
    )
    chain = llm.with_structured_output(EntryQualityOutput)
    gemini_output: EntryQualityOutput = chain.invoke([system_msg, human_msg])

    # ---- Build final output — override LLM's tier with deterministic result ----
    # Conflict fields: use conflict_output from state if present
    conflict_pattern: str | None = None
    conflict_narrative_str: str | None = None
    if conflict_output:
        conflict_pattern = conflict_output.pattern_name
        conflict_narrative_str = conflict_output.narrative

    # If LLM provided conflict fields, use them as supplement (but state's conflict_output wins)
    if conflict_pattern is None and gemini_output.conflict_pattern:
        conflict_pattern = gemini_output.conflict_pattern
    if conflict_narrative_str is None and gemini_output.conflict_narrative:
        conflict_narrative_str = gemini_output.conflict_narrative

    # Build final output — tier is DETERMINISTIC (LLM narrative only)
    final_output = EntryQualityOutput(
        macro_assessment=gemini_output.macro_assessment or macro_assessment,
        valuation_assessment=gemini_output.valuation_assessment or valuation_assessment,
        structure_assessment=gemini_output.structure_assessment or structure_assessment,
        composite_tier=final_tier,            # DETERMINISTIC override
        conflict_pattern=conflict_pattern,
        conflict_narrative=conflict_narrative_str,
        structure_veto_applied=veto_applied,  # DETERMINISTIC override
        stale_data_caveat=stale_data_caveat or gemini_output.stale_data_caveat,
        narrative=gemini_output.narrative,
        sources=gemini_output.sources,
        warnings=gemini_output.warnings + (macro_warnings + valuation_warnings + structure_warnings),
    )

    return {"entry_quality_output": final_output}
