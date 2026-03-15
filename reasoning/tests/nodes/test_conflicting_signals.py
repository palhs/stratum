"""
reasoning/tests/nodes/test_conflicting_signals.py — Unit tests for conflicting_signals_handler.
Phase 6 | Plan 04 | Requirements: REAS-04, REAS-07

Tests verify:
- Named conflict patterns are correctly matched from (macro, valuation, structure) labels
- ConflictOutput has correct pattern_name and severity per pattern
- Non-conflicting combinations return {"conflict_output": None}
- Conflict narrative includes structure-biased guidance
- Severity is "major" when structure_label is "Deteriorating"; "minor" for less severe disagreements
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reasoning.app.nodes.state import (
    ConflictOutput,
    MacroRegimeOutput,
    RegimeProbability,
    ReportState,
    StructureOutput,
    ValuationOutput,
)


# ---------------------------------------------------------------------------
# Helpers to build partial states with specific label combinations
# ---------------------------------------------------------------------------


def _make_state_with_labels(
    macro_label: str,
    valuation_label: str,
    structure_label: str,
    macro_warnings: list[str] | None = None,
    valuation_warnings: list[str] | None = None,
    structure_warnings: list[str] | None = None,
) -> ReportState:
    """Build a minimal ReportState with specific sub-assessment labels."""
    macro_output = MacroRegimeOutput(
        top_regime_id="test_regime",
        top_confidence=0.85,
        is_mixed_signal=False,
        macro_label=macro_label,
        narrative="Test macro narrative.",
        sources={"top_confidence": "fred:FEDFUNDS:2024-09-18"},
        warnings=macro_warnings or [],
    )
    valuation_output = ValuationOutput(
        asset_type="equity",
        valuation_label=valuation_label,
        narrative="Test valuation narrative.",
        sources={},
        warnings=valuation_warnings or [],
    )
    structure_output = StructureOutput(
        structure_label=structure_label,
        narrative="Test structure narrative.",
        sources={},
        warnings=structure_warnings or [],
    )
    return ReportState(
        ticker="VHM",
        asset_type="equity",
        fred_rows=[],
        regime_analogues=[],
        macro_docs=[],
        fundamentals_rows=[],
        structure_marker_rows=[],
        gold_price_rows=[],
        gold_etf_rows=[],
        earnings_docs=[],
        macro_regime_output=macro_output,
        valuation_output=valuation_output,
        structure_output=structure_output,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )


def _make_mock_conflict_output(
    pattern_name: str,
    severity: str,
    macro_label: str,
    valuation_label: str,
    structure_label: str,
    narrative: str = "Structure is the dominant safety signal.",
) -> ConflictOutput:
    """Build a mock ConflictOutput for Gemini return value."""
    return ConflictOutput(
        pattern_name=pattern_name,
        severity=severity,
        macro_label=macro_label,
        valuation_label=valuation_label,
        structure_label=structure_label,
        tier_impact="Caps tier at Cautious regardless of macro/valuation signals.",
        narrative=narrative,
    )


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import reasoning.app.nodes.conflicting_signals as conflicting_signals_module
from reasoning.app.nodes.conflicting_signals import (
    NAMED_CONFLICT_PATTERNS,
    conflicting_signals_handler,
)


# ---------------------------------------------------------------------------
# Test 1: Strong Thesis, Weak Structure (major severity)
# ---------------------------------------------------------------------------


def test_supportive_attractive_deteriorating_is_major_conflict():
    """
    (Supportive, Attractive, Deteriorating) → major conflict named "Strong Thesis, Weak Structure".
    """
    state = _make_state_with_labels("Supportive", "Attractive", "Deteriorating")
    mock_output = _make_mock_conflict_output(
        pattern_name="Strong Thesis, Weak Structure",
        severity="major",
        macro_label="Supportive",
        valuation_label="Attractive",
        structure_label="Deteriorating",
        narrative=(
            "Strong macro and valuation signals are undermined by deteriorating price structure. "
            "Structure is the dominant safety signal — avoid entry until structure recovers."
        ),
    )

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_cls.return_value = mock_llm

        result = conflicting_signals_handler(state)

    assert result["conflict_output"] is not None
    conflict = result["conflict_output"]
    assert conflict.pattern_name == "Strong Thesis, Weak Structure"
    assert conflict.severity == "major"


# ---------------------------------------------------------------------------
# Test 2: Cheap but Macro Headwind (minor severity)
# ---------------------------------------------------------------------------


def test_headwind_attractive_constructive_is_minor_conflict():
    """
    (Headwind, Attractive, Constructive) → minor conflict named "Cheap but Macro Headwind".
    """
    state = _make_state_with_labels("Headwind", "Attractive", "Constructive")
    mock_output = _make_mock_conflict_output(
        pattern_name="Cheap but Macro Headwind",
        severity="minor",
        macro_label="Headwind",
        valuation_label="Attractive",
        structure_label="Constructive",
        narrative=(
            "Asset appears attractively valued but faces meaningful macro headwinds. "
            "Structure remains constructive, suggesting patient accumulation may be appropriate, "
            "but timing matters — structure is the guide for entry timing."
        ),
    )

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_cls.return_value = mock_llm

        result = conflicting_signals_handler(state)

    assert result["conflict_output"] is not None
    conflict = result["conflict_output"]
    assert conflict.pattern_name == "Cheap but Macro Headwind"
    assert conflict.severity == "minor"


# ---------------------------------------------------------------------------
# Test 3: Expensive and Deteriorating (major severity)
# ---------------------------------------------------------------------------


def test_supportive_stretched_deteriorating_is_major_conflict():
    """
    (Supportive, Stretched, Deteriorating) → major conflict named "Expensive and Deteriorating".
    """
    state = _make_state_with_labels("Supportive", "Stretched", "Deteriorating")
    mock_output = _make_mock_conflict_output(
        pattern_name="Expensive and Deteriorating",
        severity="major",
        macro_label="Supportive",
        valuation_label="Stretched",
        structure_label="Deteriorating",
        narrative=(
            "Valuation is stretched and price structure is deteriorating despite macro support. "
            "Structure veto applies — structure is the dominant safety signal."
        ),
    )

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_cls.return_value = mock_llm

        result = conflicting_signals_handler(state)

    assert result["conflict_output"] is not None
    conflict = result["conflict_output"]
    assert "Expensive" in conflict.pattern_name or "Deteriorating" in conflict.pattern_name
    assert conflict.severity == "major"


# ---------------------------------------------------------------------------
# Test 4: No conflict — all aligned favorable
# ---------------------------------------------------------------------------


def test_supportive_attractive_constructive_no_conflict():
    """
    (Supportive, Attractive, Constructive) → No conflict — returns {"conflict_output": None}.
    All signals aligned — no Gemini call expected.
    """
    state = _make_state_with_labels("Supportive", "Attractive", "Constructive")

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        result = conflicting_signals_handler(state)
        # LLM should NOT be called for non-conflicting combinations
        mock_llm_cls.assert_not_called()

    assert result["conflict_output"] is None


# ---------------------------------------------------------------------------
# Test 5: No conflict — ambiguous but not conflicting (Mixed, Fair, Neutral)
# ---------------------------------------------------------------------------


def test_mixed_fair_neutral_no_conflict():
    """
    (Mixed, Fair, Neutral) → No conflict — all ambiguous signals, no named pattern match.
    Returns {"conflict_output": None}.
    """
    state = _make_state_with_labels("Mixed", "Fair", "Neutral")

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        result = conflicting_signals_handler(state)
        mock_llm_cls.assert_not_called()

    assert result["conflict_output"] is None


# ---------------------------------------------------------------------------
# Test 6: Conflict narrative includes structure-biased guidance
# ---------------------------------------------------------------------------


def test_conflict_narrative_includes_structure_guidance():
    """
    Conflict narrative must reference structure as the dominant safety signal
    (per locked design decision: structure biased guidance in all conflict narratives).
    """
    state = _make_state_with_labels("Headwind", "Attractive", "Deteriorating")
    structure_guidance = (
        "Structure is the dominant safety signal, consistent with Stratum's core value. "
        "Do not enter despite attractive valuation — price structure must confirm."
    )
    mock_output = _make_mock_conflict_output(
        pattern_name="Cheap and Deteriorating",
        severity="major",
        macro_label="Headwind",
        valuation_label="Attractive",
        structure_label="Deteriorating",
        narrative=structure_guidance,
    )

    with patch.object(
        conflicting_signals_module, "ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain
        mock_llm_cls.return_value = mock_llm

        result = conflicting_signals_handler(state)

    assert result["conflict_output"] is not None
    # Narrative includes structure-biased guidance — could contain keywords like "structure"
    assert "structure" in result["conflict_output"].narrative.lower() or \
           "dominant" in result["conflict_output"].narrative.lower()


# ---------------------------------------------------------------------------
# Test 7: Deteriorating structure → major severity in patterns dict
# ---------------------------------------------------------------------------


def test_deteriorating_structure_patterns_are_major_severity():
    """
    All NAMED_CONFLICT_PATTERNS entries where structure_label='Deteriorating'
    must have severity='major'.
    """
    for (macro_l, val_l, struct_l), pattern_info in NAMED_CONFLICT_PATTERNS.items():
        if struct_l == "Deteriorating":
            assert pattern_info["severity"] == "major", (
                f"Pattern ({macro_l}, {val_l}, {struct_l}) has severity="
                f"'{pattern_info['severity']}' but expected 'major' "
                f"because structure_label is 'Deteriorating'."
            )
