"""
reasoning/tests/nodes/test_macro_regime.py — Unit tests for macro_regime_node.
Phase 6 | Plan 03 | Requirement: REAS-01

Tests cover:
1. High confidence: top_confidence >= 0.70 → is_mixed_signal=False, top_two_analogues=[]
2. Mixed signal: top_confidence < 0.70 → is_mixed_signal=True, mixed_signal_label set,
   top_two_analogues has exactly 2 entries
3. Threshold boundary: exactly 0.70 → is_mixed_signal=False (strict less-than per pitfall #6)
4. Probability sum: sum of all regime_probabilities[].confidence values ~1.0 (within 0.05)
5. macro_label assignment: macro_label is one of "Supportive", "Mixed", "Headwind"
6. Sources populated: top_confidence has source citation; each RegimeProbability has
   source_analogue_id
7. Warnings propagation: warnings from input fred_rows and regime_analogues appear in output
8. Empty analogues: node still produces output with appropriate warning

All Gemini calls are mocked via patch.object — no live API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import reasoning.app.nodes.macro_regime as macro_regime_module
from reasoning.app.nodes.state import MacroRegimeOutput, RegimeProbability
from reasoning.app.retrieval.types import FredIndicatorRow, RegimeAnalogue


# ---------------------------------------------------------------------------
# Helper: build a mock MacroRegimeOutput for Gemini-returned values
# ---------------------------------------------------------------------------


def _make_mock_regime_output(
    regime_probabilities: list[RegimeProbability] | None = None,
    top_regime_id: str = "post_gfc_recovery_2010",
    top_confidence: float = 0.82,
    is_mixed_signal: bool = False,
    mixed_signal_label: str | None = None,
    top_two_analogues: list[str] | None = None,
    macro_label: str = "Supportive",
    narrative: str = "Mock macro regime narrative with FRED data context.",
    sources: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> MacroRegimeOutput:
    """Build a MacroRegimeOutput with pre-set values for mocking Gemini responses."""
    if regime_probabilities is None:
        regime_probabilities = [
            RegimeProbability(
                regime_id="post_gfc_recovery_2010",
                regime_name="Post-GFC Recovery 2010",
                confidence=0.82,
                source_analogue_id="post_gfc_recovery_2010",
            ),
            RegimeProbability(
                regime_id="mid_cycle_expansion_2016",
                regime_name="Mid-Cycle Expansion 2016",
                confidence=0.18,
                source_analogue_id="mid_cycle_expansion_2016",
            ),
        ]
    return MacroRegimeOutput(
        regime_probabilities=regime_probabilities,
        top_regime_id=top_regime_id,
        top_confidence=top_confidence,
        is_mixed_signal=is_mixed_signal,
        mixed_signal_label=mixed_signal_label,
        top_two_analogues=top_two_analogues or [],
        macro_label=macro_label,
        narrative=narrative,
        sources=sources or {"top_confidence": "fred:FEDFUNDS,GS10,UNRATE"},
        warnings=warnings or [],
    )


def _make_mock_chain(output: MacroRegimeOutput) -> MagicMock:
    """Returns a mock that behaves like llm.with_structured_output(...).invoke(...)"""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = output
    return mock_chain


# ---------------------------------------------------------------------------
# Test 1: High confidence → is_mixed_signal=False, top_two_analogues=[]
# ---------------------------------------------------------------------------


def test_high_confidence_not_mixed_signal(base_equity_state):
    """
    macro_regime_node with strong single-regime FRED data returns MacroRegimeOutput
    with top_confidence >= 0.70, is_mixed_signal=False, top_two_analogues=[].
    """
    # LLM returns high-confidence output; post-processing must preserve is_mixed_signal=False
    llm_output = _make_mock_regime_output(
        top_confidence=0.82,
        is_mixed_signal=True,   # LLM may return wrong value — post-processing must override
        mixed_signal_label="Wrong",
        top_two_analogues=["should_be_cleared"],
        macro_label="Supportive",
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(base_equity_state)

    assert "macro_regime_output" in result
    output: MacroRegimeOutput = result["macro_regime_output"]
    assert isinstance(output, MacroRegimeOutput)
    assert output.top_confidence == 0.82
    assert output.is_mixed_signal is False
    assert output.top_two_analogues == []
    assert output.mixed_signal_label is None


# ---------------------------------------------------------------------------
# Test 2: Mixed signal — top_confidence < 0.70 → is_mixed_signal=True, 2 entries
# ---------------------------------------------------------------------------


def test_mixed_signal_when_confidence_below_threshold(base_equity_state):
    """
    macro_regime_node with ambiguous FRED data (LLM returns top_confidence < 0.70)
    returns is_mixed_signal=True, mixed_signal_label="Mixed Signal Environment",
    top_two_analogues has exactly 2 entries.
    """
    # Two analogues in fixture: post_gfc_recovery_2010 and mid_cycle_expansion_2016
    regime_probs = [
        RegimeProbability(
            regime_id="post_gfc_recovery_2010",
            regime_name="Post-GFC Recovery 2010",
            confidence=0.55,
            source_analogue_id="post_gfc_recovery_2010",
        ),
        RegimeProbability(
            regime_id="mid_cycle_expansion_2016",
            regime_name="Mid-Cycle Expansion 2016",
            confidence=0.45,
            source_analogue_id="mid_cycle_expansion_2016",
        ),
    ]
    llm_output = _make_mock_regime_output(
        regime_probabilities=regime_probs,
        top_regime_id="post_gfc_recovery_2010",
        top_confidence=0.55,
        is_mixed_signal=False,  # LLM returns wrong value; post-processing must override
        mixed_signal_label=None,
        top_two_analogues=[],
        macro_label="Mixed",
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(base_equity_state)

    output: MacroRegimeOutput = result["macro_regime_output"]
    assert output.top_confidence == 0.55
    assert output.is_mixed_signal is True
    assert output.mixed_signal_label == "Mixed Signal Environment"
    assert len(output.top_two_analogues) == 2


# ---------------------------------------------------------------------------
# Test 3: Threshold boundary — exactly 0.70 → is_mixed_signal=False (strict <)
# ---------------------------------------------------------------------------


def test_threshold_boundary_exactly_070_is_not_mixed_signal(base_equity_state):
    """
    Exactly 0.70 top_confidence → is_mixed_signal=False.
    The rule is strict less-than: top_confidence < MIXED_SIGNAL_THRESHOLD.
    0.70 < 0.70 is False, so is_mixed_signal must be False.
    """
    regime_probs = [
        RegimeProbability(
            regime_id="post_gfc_recovery_2010",
            regime_name="Post-GFC Recovery 2010",
            confidence=0.70,
            source_analogue_id="post_gfc_recovery_2010",
        ),
        RegimeProbability(
            regime_id="mid_cycle_expansion_2016",
            regime_name="Mid-Cycle Expansion 2016",
            confidence=0.30,
            source_analogue_id="mid_cycle_expansion_2016",
        ),
    ]
    llm_output = _make_mock_regime_output(
        regime_probabilities=regime_probs,
        top_confidence=0.70,
        is_mixed_signal=True,   # LLM may compute incorrectly — must be overridden
        macro_label="Supportive",
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(base_equity_state)

    output: MacroRegimeOutput = result["macro_regime_output"]
    assert output.top_confidence == 0.70
    assert output.is_mixed_signal is False, (
        "Exactly 0.70 must NOT be mixed signal — rule is strict less-than (< 0.70)"
    )
    assert output.top_two_analogues == []
    assert output.mixed_signal_label is None


# ---------------------------------------------------------------------------
# Test 4: Probability sum — sum of regime_probabilities[].confidence ~1.0
# ---------------------------------------------------------------------------


def test_probability_sum_approximately_one(base_equity_state):
    """
    Sum of all regime_probabilities[].confidence values is approximately 1.0
    (within 0.05 tolerance).
    """
    regime_probs = [
        RegimeProbability(
            regime_id="regime_a",
            regime_name="Regime A",
            confidence=0.60,
            source_analogue_id="analogue_a",
        ),
        RegimeProbability(
            regime_id="regime_b",
            regime_name="Regime B",
            confidence=0.25,
            source_analogue_id="analogue_b",
        ),
        RegimeProbability(
            regime_id="regime_c",
            regime_name="Regime C",
            confidence=0.15,
            source_analogue_id="analogue_c",
        ),
    ]
    llm_output = _make_mock_regime_output(
        regime_probabilities=regime_probs,
        top_confidence=0.60,
        macro_label="Supportive",
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(base_equity_state)

    output: MacroRegimeOutput = result["macro_regime_output"]
    total = sum(rp.confidence for rp in output.regime_probabilities)
    assert abs(total - 1.0) <= 0.05, (
        f"Probability distribution sums to {total:.3f}, expected ~1.0 (within 0.05)"
    )


# ---------------------------------------------------------------------------
# Test 5: macro_label assignment — must be one of Supportive/Mixed/Headwind
# ---------------------------------------------------------------------------


def test_macro_label_is_valid_value(base_equity_state):
    """
    macro_label in MacroRegimeOutput is one of "Supportive", "Mixed", "Headwind"
    and matches the regime classification from the LLM.
    """
    valid_labels = {"Supportive", "Mixed", "Headwind"}

    for label in valid_labels:
        llm_output = _make_mock_regime_output(
            top_confidence=0.80,
            macro_label=label,
        )
        mock_chain = _make_mock_chain(llm_output)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_chain

        with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
            result = macro_regime_module.macro_regime_node(base_equity_state)

        output: MacroRegimeOutput = result["macro_regime_output"]
        assert output.macro_label in valid_labels, (
            f"macro_label={output.macro_label!r} not in valid set {valid_labels}"
        )
        assert output.macro_label == label


# ---------------------------------------------------------------------------
# Test 6: Sources populated — top_confidence sourced; each RegimeProbability has
#         source_analogue_id
# ---------------------------------------------------------------------------


def test_sources_populated(base_equity_state):
    """
    top_confidence has a source citation in sources dict.
    Each RegimeProbability has a non-empty source_analogue_id.
    """
    regime_probs = [
        RegimeProbability(
            regime_id="post_gfc_recovery_2010",
            regime_name="Post-GFC Recovery 2010",
            confidence=0.75,
            source_analogue_id="post_gfc_recovery_2010",
        ),
        RegimeProbability(
            regime_id="mid_cycle_expansion_2016",
            regime_name="Mid-Cycle Expansion 2016",
            confidence=0.25,
            source_analogue_id="mid_cycle_expansion_2016",
        ),
    ]
    llm_output = _make_mock_regime_output(
        regime_probabilities=regime_probs,
        top_confidence=0.75,
        sources={"top_confidence": "fred:FEDFUNDS,GS10,UNRATE:2024-09-18"},
        macro_label="Supportive",
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(base_equity_state)

    output: MacroRegimeOutput = result["macro_regime_output"]

    # top_confidence must be cited
    assert "top_confidence" in output.sources, (
        f"top_confidence not in sources: {output.sources}"
    )
    assert output.sources["top_confidence"] != ""

    # Each RegimeProbability must have a non-empty source_analogue_id
    for rp in output.regime_probabilities:
        assert rp.source_analogue_id != "", (
            f"RegimeProbability {rp.regime_id} has empty source_analogue_id"
        )


# ---------------------------------------------------------------------------
# Test 7: Warnings propagation — input warnings appear in output
# ---------------------------------------------------------------------------


def test_warnings_propagated_from_input(base_equity_state):
    """
    Warnings attached to fred_rows and regime_analogues in input state
    appear in the output warnings list.
    """
    from datetime import datetime
    from reasoning.app.retrieval.types import FredIndicatorRow, RegimeAnalogue

    state = dict(base_equity_state)
    state["fred_rows"] = [
        FredIndicatorRow(
            series_id="FEDFUNDS",
            value=5.33,
            frequency="monthly",
            data_as_of=datetime(2024, 9, 18),
            warnings=["FEDFUNDS data may be 30 days stale"],
        ),
    ]
    state["regime_analogues"] = [
        RegimeAnalogue(
            source_regime="current_2024",
            analogue_id="post_gfc_recovery_2010",
            analogue_name="Post-GFC Recovery 2010",
            period_start="2010-01",
            period_end="2011-06",
            similarity_score=0.88,
            dimensions_matched=["inflation"],
            narrative="Recovery phase.",
            warnings=["Neo4j analogue data may be outdated"],
        ),
    ]

    llm_output = _make_mock_regime_output(top_confidence=0.80, macro_label="Supportive")
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(state)

    output: MacroRegimeOutput = result["macro_regime_output"]
    all_warnings_text = " ".join(output.warnings)
    assert "FEDFUNDS data may be 30 days stale" in all_warnings_text, (
        f"FRED warning not propagated: {output.warnings}"
    )
    assert "Neo4j analogue data may be outdated" in all_warnings_text, (
        f"Analogue warning not propagated: {output.warnings}"
    )


# ---------------------------------------------------------------------------
# Test 8: Empty analogues — node still produces output with appropriate warning
# ---------------------------------------------------------------------------


def test_empty_analogues_produces_output_with_warning(base_equity_state):
    """
    When regime_analogues is empty, macro_regime_node still produces a MacroRegimeOutput
    (no exception raised) and includes an appropriate warning in the output.
    """
    state = dict(base_equity_state)
    state["regime_analogues"] = []

    llm_output = _make_mock_regime_output(
        regime_probabilities=[
            RegimeProbability(
                regime_id="unknown",
                regime_name="Unknown Regime",
                confidence=1.0,
                source_analogue_id="none",
            )
        ],
        top_regime_id="unknown",
        top_confidence=1.0,
        macro_label="Mixed",
        warnings=["No historical analogues available"],
    )
    mock_chain = _make_mock_chain(llm_output)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    with patch.object(macro_regime_module, "ChatGoogleGenerativeAI", return_value=mock_llm):
        result = macro_regime_module.macro_regime_node(state)

    assert "macro_regime_output" in result
    output: MacroRegimeOutput = result["macro_regime_output"]
    assert isinstance(output, MacroRegimeOutput)

    # Should have at least one warning about missing analogues
    all_warnings_text = " ".join(output.warnings).lower()
    assert (
        "analogue" in all_warnings_text or "no historical" in all_warnings_text
    ), f"Expected analogue warning, got: {output.warnings}"
