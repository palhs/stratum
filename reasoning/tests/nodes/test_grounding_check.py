"""
reasoning/tests/nodes/test_grounding_check.py — Tests for grounding_check_node.
Phase 6 | Plan 05 | Requirement: REAS-05

Tests verify:
- All float fields in node outputs require source attribution
- GroundingError raised with comprehensive error listing for unattributed claims
- Partial and empty state handled gracefully
- Nested Pydantic models (RegimeProbability) inspected via source_analogue_id
- None float fields are skipped (not checked)
- Qualitative / string fields are NOT checked
"""

from __future__ import annotations

import pytest

from reasoning.app.nodes.state import (
    GroundingError,
    GroundingResult,
    MacroRegimeOutput,
    RegimeProbability,
    ReportState,
    StructureOutput,
    ValuationOutput,
)
from reasoning.app.nodes.grounding_check import grounding_check_node


# ---------------------------------------------------------------------------
# Helpers to build minimal node outputs
# ---------------------------------------------------------------------------


def _macro_output_all_grounded() -> MacroRegimeOutput:
    """MacroRegimeOutput with top_confidence sourced, regime_probabilities with source_analogue_id."""
    return MacroRegimeOutput(
        regime_probabilities=[
            RegimeProbability(
                regime_id="post_gfc_2010",
                regime_name="Post-GFC Recovery",
                confidence=0.75,
                source_analogue_id="post_gfc_2010",
            ),
        ],
        top_regime_id="post_gfc_2010",
        top_confidence=0.75,
        is_mixed_signal=False,
        macro_label="Supportive",
        narrative="Rates falling, growth resuming.",
        sources={
            "top_confidence": "fred:FEDFUNDS,UNRATE:2024-09-18",
        },
    )


def _macro_output_unattributed() -> MacroRegimeOutput:
    """MacroRegimeOutput with top_confidence but NO sources entry for it."""
    return MacroRegimeOutput(
        regime_probabilities=[],
        top_regime_id="mid_cycle_2016",
        top_confidence=0.85,
        is_mixed_signal=False,
        macro_label="Supportive",
        narrative="Solid growth environment.",
        sources={},  # missing "top_confidence" key
    )


def _valuation_output_all_grounded() -> ValuationOutput:
    """ValuationOutput with pe_ratio and pb_ratio both sourced."""
    return ValuationOutput(
        asset_type="equity",
        valuation_label="Attractive",
        pe_ratio=12.4,
        pb_ratio=1.8,
        narrative="Below historical median.",
        sources={
            "pe_ratio": "fundamentals:VHM:annual:2024-06-30",
            "pb_ratio": "fundamentals:VHM:annual:2024-06-30",
        },
    )


def _structure_output_all_grounded() -> StructureOutput:
    """StructureOutput with all float fields sourced."""
    return StructureOutput(
        structure_label="Constructive",
        close=42_500.0,
        ma_10w=41_200.0,
        ma_20w=40_100.0,
        ma_50w=38_500.0,
        drawdown_from_ath=-0.125,
        drawdown_from_52w_high=-0.083,
        close_pct_rank=0.72,
        narrative="Price above all MAs.",
        sources={
            "close": "structure:VHM:weekly:2024-09-18",
            "ma_10w": "structure:VHM:weekly:2024-09-18",
            "ma_20w": "structure:VHM:weekly:2024-09-18",
            "ma_50w": "structure:VHM:weekly:2024-09-18",
            "drawdown_from_ath": "structure:VHM:weekly:2024-09-18",
            "drawdown_from_52w_high": "structure:VHM:weekly:2024-09-18",
            "close_pct_rank": "structure:VHM:weekly:2024-09-18",
        },
    )


# ---------------------------------------------------------------------------
# Test 1: All grounded — passes cleanly
# ---------------------------------------------------------------------------


def test_all_grounded_passes():
    """State with macro and valuation outputs fully attributed passes with status='pass'."""
    state: ReportState = ReportState(
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
        macro_regime_output=_macro_output_all_grounded(),
        valuation_output=_valuation_output_all_grounded(),
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    result = grounding_check_node(state)
    grounding = result["grounding_result"]
    assert isinstance(grounding, GroundingResult)
    assert grounding.status == "pass"
    assert len(grounding.unattributed_claims) == 0


# ---------------------------------------------------------------------------
# Test 2: Unattributed claim — raises GroundingError mentioning field name
# ---------------------------------------------------------------------------


def test_unattributed_claim_raises_grounding_error():
    """MacroRegimeOutput with top_confidence but no source → GroundingError mentioning 'top_confidence'."""
    state: ReportState = ReportState(
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
        macro_regime_output=_macro_output_unattributed(),
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    with pytest.raises(GroundingError) as exc_info:
        grounding_check_node(state)
    assert "top_confidence" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3: Partial state — only macro_regime_output set, others None
# ---------------------------------------------------------------------------


def test_partial_state_checks_only_present_outputs():
    """When only macro_regime_output is set, grounding check only verifies that output."""
    state: ReportState = ReportState(
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
        macro_regime_output=_macro_output_all_grounded(),
        valuation_output=None,  # absent
        structure_output=None,  # absent
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    result = grounding_check_node(state)
    grounding = result["grounding_result"]
    assert grounding.status == "pass"
    # Only macro_regime_output was checked
    assert "macro_regime_output" in grounding.checked_outputs
    assert "valuation_output" not in grounding.checked_outputs
    assert "structure_output" not in grounding.checked_outputs


# ---------------------------------------------------------------------------
# Test 4: Nested model — RegimeProbability.confidence checked via source_analogue_id
# ---------------------------------------------------------------------------


def test_nested_regime_probability_with_source_passes():
    """RegimeProbability.confidence is grounded via source_analogue_id — should pass."""
    macro = MacroRegimeOutput(
        regime_probabilities=[
            RegimeProbability(
                regime_id="post_gfc_2010",
                regime_name="Post-GFC Recovery",
                confidence=0.75,
                source_analogue_id="post_gfc_2010",  # present → grounded
            ),
        ],
        top_regime_id="post_gfc_2010",
        top_confidence=0.75,
        is_mixed_signal=False,
        macro_label="Supportive",
        narrative="Context narrative.",
        sources={
            "top_confidence": "fred:FEDFUNDS:2024-09-18",
        },
    )
    state: ReportState = ReportState(
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
        macro_regime_output=macro,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    result = grounding_check_node(state)
    assert result["grounding_result"].status == "pass"


def test_nested_regime_probability_missing_source_analogue_raises():
    """RegimeProbability.confidence without source_analogue_id → GroundingError."""
    # RegimeProbability requires source_analogue_id, so we test the case where
    # the model has an empty source_analogue_id string (falsy).
    # Since the Pydantic model enforces source_analogue_id as str (not Optional),
    # we simulate by passing empty string — grounding check should treat empty as unattributed.
    macro = MacroRegimeOutput(
        regime_probabilities=[
            RegimeProbability(
                regime_id="post_gfc_2010",
                regime_name="Post-GFC Recovery",
                confidence=0.75,
                source_analogue_id="",  # empty → unattributed
            ),
        ],
        top_regime_id="post_gfc_2010",
        top_confidence=0.75,
        is_mixed_signal=False,
        macro_label="Supportive",
        narrative="Context narrative.",
        sources={
            "top_confidence": "fred:FEDFUNDS:2024-09-18",
        },
    )
    state: ReportState = ReportState(
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
        macro_regime_output=macro,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    with pytest.raises(GroundingError) as exc_info:
        grounding_check_node(state)
    assert "confidence" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 5: Optional None floats — not checked
# ---------------------------------------------------------------------------


def test_none_float_fields_not_checked():
    """ValuationOutput with pe_ratio=None and pb_ratio=None — no grounding error even without sources."""
    valuation = ValuationOutput(
        asset_type="equity",
        valuation_label="Fair",
        pe_ratio=None,   # None → skip
        pb_ratio=None,   # None → skip
        narrative="Metrics unavailable.",
        sources={},  # no sources needed for None float fields
    )
    state: ReportState = ReportState(
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
        macro_regime_output=None,
        valuation_output=valuation,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    result = grounding_check_node(state)
    assert result["grounding_result"].status == "pass"


# ---------------------------------------------------------------------------
# Test 6: Qualitative fields (str) NOT checked
# ---------------------------------------------------------------------------


def test_qualitative_str_fields_not_checked():
    """Narrative, label, and other string fields do not trigger GroundingError."""
    macro = MacroRegimeOutput(
        regime_probabilities=[],
        top_regime_id="some_regime",
        top_confidence=0.80,
        is_mixed_signal=False,
        macro_label="Headwind",
        narrative="Very long narrative without any source citation in sources dict.",
        sources={
            "top_confidence": "fred:FEDFUNDS:2024-09-18",
        },
    )
    state: ReportState = ReportState(
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
        macro_regime_output=macro,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    # Should not raise even though narrative/macro_label have no sources entry
    result = grounding_check_node(state)
    assert result["grounding_result"].status == "pass"


# ---------------------------------------------------------------------------
# Test 7: Error message lists ALL unattributed claims (not just first)
# ---------------------------------------------------------------------------


def test_error_message_lists_all_unattributed_claims():
    """GroundingError message contains all unattributed float fields, not just the first."""
    valuation = ValuationOutput(
        asset_type="equity",
        valuation_label="Stretched",
        pe_ratio=22.5,   # unattributed
        pb_ratio=4.1,    # unattributed
        real_yield=1.75, # unattributed (gold path field present here)
        narrative="High valuations.",
        sources={},  # no source for ANY float field
    )
    state: ReportState = ReportState(
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
        macro_regime_output=None,
        valuation_output=valuation,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    with pytest.raises(GroundingError) as exc_info:
        grounding_check_node(state)
    error_msg = str(exc_info.value)
    # All three unattributed float fields must appear in the error
    assert "pe_ratio" in error_msg
    assert "pb_ratio" in error_msg
    assert "real_yield" in error_msg


# ---------------------------------------------------------------------------
# Test 8: Empty state — all outputs None → passes with empty checked_outputs
# ---------------------------------------------------------------------------


def test_empty_state_passes():
    """When all node outputs are None, grounding check passes with checked_outputs=[]."""
    state: ReportState = ReportState(
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
        macro_regime_output=None,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
    result = grounding_check_node(state)
    grounding = result["grounding_result"]
    assert grounding.status == "pass"
    assert grounding.checked_outputs == []
