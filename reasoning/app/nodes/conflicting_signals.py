"""
reasoning/app/nodes/conflicting_signals.py — conflicting_signals_handler: conflict detection node.
Phase 6 | Plan 04 | Requirements: REAS-07

Detects disagreement between sub-assessment labels and produces ConflictOutput with named patterns.
Runs before entry_quality_node — entry_quality reads conflict_output from state.

CRITICAL constraints (REAS-07):
- NO import of retrieval functions — only TYPE imports from retrieval.types
- Read ONLY from state fields — no direct database calls
- Pattern matching is DETERMINISTIC — no LLM involvement in conflict detection
- LLM is called ONLY to generate the narrative for a detected conflict
- Patterns where structure_label="Deteriorating" are ALWAYS severity="major"
- Non-conflicting combinations return {"conflict_output": None} — no LLM call
- Narrative must emphasize structure as the dominant safety signal (locked design decision)
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from reasoning.app.nodes.state import (
    ConflictOutput,
    MacroRegimeOutput,
    ReportState,
    StructureOutput,
    ValuationOutput,
)


# ---------------------------------------------------------------------------
# Named Conflict Patterns
# ---------------------------------------------------------------------------
#
# Key: (macro_label, valuation_label, structure_label)
# Value: dict with keys: name (str), severity ("major" | "minor")
#
# Design rules:
# - Patterns where structure_label="Deteriorating" → severity="major" (structure veto applies)
# - Patterns where signals are moderately misaligned → severity="minor"
# - 8–12 patterns covering the most important combinations
# ---------------------------------------------------------------------------

NAMED_CONFLICT_PATTERNS: dict[tuple[str, str, str], dict[str, str]] = {
    # Major conflicts — Deteriorating structure overrides good macro/valuation
    ("Supportive", "Attractive", "Deteriorating"): {
        "name": "Strong Thesis, Weak Structure",
        "severity": "major",
    },
    ("Supportive", "Stretched", "Deteriorating"): {
        "name": "Expensive and Deteriorating",
        "severity": "major",
    },
    ("Headwind", "Attractive", "Deteriorating"): {
        "name": "Cheap and Deteriorating",
        "severity": "major",
    },
    ("Mixed", "Attractive", "Deteriorating"): {
        "name": "Uncertain Regime, Weak Structure",
        "severity": "major",
    },
    ("Headwind", "Stretched", "Deteriorating"): {
        "name": "Headwind with Expensive and Deteriorating Assets",
        "severity": "major",
    },
    ("Supportive", "Fair", "Deteriorating"): {
        "name": "Macro Support Undermined by Structure",
        "severity": "major",
    },
    ("Mixed", "Fair", "Deteriorating"): {
        "name": "Mixed Signals with Structural Breakdown",
        "severity": "major",
    },
    # Minor conflicts — some misalignment but structure is not the problem
    ("Headwind", "Attractive", "Constructive"): {
        "name": "Cheap but Macro Headwind",
        "severity": "minor",
    },
    ("Supportive", "Stretched", "Constructive"): {
        "name": "Momentum Without Value",
        "severity": "minor",
    },
    ("Headwind", "Attractive", "Neutral"): {
        "name": "Attractive Valuation in Headwind",
        "severity": "minor",
    },
    ("Headwind", "Stretched", "Constructive"): {
        "name": "Overvalued in Headwind",
        "severity": "minor",
    },
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.0-flash-001"

_SYSTEM_PROMPT = (
    "You are a financial analyst specializing in identifying signal conflicts across "
    "macro, valuation, and price structure dimensions. "
    "A conflict has been detected between the sub-assessments for this asset. "
    "Write a concise conflict narrative that:\n"
    "1. Explains why the signals disagree\n"
    "2. Quantifies the nature of the disagreement where possible\n"
    "3. EMPHASIZES that structure is the dominant safety signal, consistent with "
    "Stratum's core value of protecting investors from structurally dangerous entry points\n"
    "4. Provides actionable guidance weighted toward the structural signal\n"
    "Do NOT invent numerical data. Reference only the label assessments provided. "
    "Keep the narrative concise (3-5 sentences)."
)


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def conflicting_signals_handler(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: detects signal conflicts between sub-assessments.

    State reads:
        - state["macro_regime_output"]: MacroRegimeOutput (reads .macro_label)
        - state["valuation_output"]: ValuationOutput (reads .valuation_label)
        - state["structure_output"]: StructureOutput (reads .structure_label)

    State writes:
        - state["conflict_output"]: ConflictOutput | None

    Logic:
        1. Extract labels from each sub-assessment node output.
        2. Look up (macro_label, valuation_label, structure_label) in NAMED_CONFLICT_PATTERNS.
        3. If no match: return {"conflict_output": None} — no LLM call needed.
        4. If match: call Gemini to generate a structure-biased narrative.
        5. Return {"conflict_output": ConflictOutput} with the pattern info + LLM narrative.

    Does NOT call any retrieval functions. Does NOT recompute raw market data.
    """
    macro_output: MacroRegimeOutput | None = state.get("macro_regime_output")
    valuation_output: ValuationOutput | None = state.get("valuation_output")
    structure_output: StructureOutput | None = state.get("structure_output")

    # ---- Extract labels (with graceful fallback) ----
    macro_label: str = macro_output.macro_label if macro_output else "Mixed"
    valuation_label: str = valuation_output.valuation_label if valuation_output else "Fair"
    structure_label: str = structure_output.structure_label if structure_output else "Neutral"

    # ---- Deterministic pattern lookup ----
    pattern_key = (macro_label, valuation_label, structure_label)
    matched_pattern = NAMED_CONFLICT_PATTERNS.get(pattern_key)

    if matched_pattern is None:
        # No recognized conflict pattern — no LLM call
        return {"conflict_output": None}

    # ---- Conflict detected — call Gemini for narrative ----
    pattern_name: str = matched_pattern["name"]
    severity: str = matched_pattern["severity"]

    human_prompt = (
        f"Conflict Pattern: {pattern_name}\n"
        f"Severity: {severity}\n"
        f"Macro Assessment: {macro_label}\n"
        f"Valuation Assessment: {valuation_label}\n"
        f"Structure Assessment: {structure_label}\n\n"
        f"The three sub-assessments disagree. "
        f"Explain this conflict and provide structure-biased guidance. "
        f"Remember: structure is the dominant safety signal."
    )

    system_msg = SystemMessage(content=_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=human_prompt)

    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
        temperature=0.2,
    )
    chain = llm.with_structured_output(ConflictOutput)
    gemini_output: ConflictOutput = chain.invoke([system_msg, human_msg])

    # ---- Override deterministic fields — LLM provides narrative only ----
    # Pattern name and severity come from our rules, not LLM
    final_output = ConflictOutput(
        pattern_name=pattern_name,
        severity=severity,
        macro_label=macro_label,
        valuation_label=valuation_label,
        structure_label=structure_label,
        tier_impact=gemini_output.tier_impact,
        narrative=gemini_output.narrative,
        sources=gemini_output.sources,
        warnings=gemini_output.warnings,
    )

    return {"conflict_output": final_output}
