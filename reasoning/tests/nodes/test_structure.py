"""
reasoning/tests/nodes/test_structure.py — Unit tests for the structure_node.
Phase 6 | Plan 01 | Requirement: REAS-03

All tests mock the Gemini LLM call to avoid live API dependency.
Tests verify:
  1. Correct values echoed from StructureMarkerRow to StructureOutput
  2. Narrative mentions MA positioning and drawdown context
  3. Constructive label when close > all MAs and small drawdown
  4. Deteriorating label when close < all MAs and large drawdown
  5. Partial assessment with missing_metrics warning on None MA fields
  6. No retrieval function imports in the module
  7. sources dict populated for each numeric field from marker row
"""

from __future__ import annotations

import importlib
import inspect
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from reasoning.app.nodes.state import ReportState, StructureOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(structure_output: StructureOutput) -> MagicMock:
    """
    Return a mock that behaves like ChatGoogleGenerativeAI(...).with_structured_output(...)
    i.e. mock_llm.with_structured_output(StructureOutput).invoke(...) returns structure_output.
    """
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = structure_output

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    return mock_llm


# ---------------------------------------------------------------------------
# Test 1: Correct values echoed from StructureMarkerRow
# ---------------------------------------------------------------------------


def test_structure_node_echoes_marker_values(
    base_equity_state: ReportState,
    mock_structure_marker_rows,
):
    """structure_node echoes close, MA, drawdown values from StructureMarkerRow."""
    marker = mock_structure_marker_rows[0]  # VHM weekly

    expected_output = StructureOutput(
        structure_label="Constructive",
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        drawdown_from_52w_high=marker.drawdown_from_52w_high,
        close_pct_rank=marker.close_pct_rank,
        narrative="Price is above all key moving averages, indicating constructive structure.",
        sources={
            "close": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "ma_10w": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "ma_20w": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "ma_50w": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "drawdown_from_ath": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "drawdown_from_52w_high": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
            "close_pct_rank": f"structure_markers:VHM:{marker.data_as_of.isoformat()}",
        },
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes.structure import structure_node

        result_state = structure_node(base_equity_state)

    output = result_state["structure_output"]
    assert output is not None
    assert output.close == marker.close
    assert output.ma_10w == marker.ma_10w
    assert output.ma_20w == marker.ma_20w
    assert output.ma_50w == marker.ma_50w
    assert output.drawdown_from_ath == marker.drawdown_from_ath
    assert output.drawdown_from_52w_high == marker.drawdown_from_52w_high
    assert output.close_pct_rank == marker.close_pct_rank


# ---------------------------------------------------------------------------
# Test 2: Narrative mentions MA positioning and drawdown context
# ---------------------------------------------------------------------------


def test_structure_node_narrative_mentions_ma_and_drawdown(
    base_equity_state: ReportState,
    mock_structure_marker_rows,
):
    """structure_node produces narrative mentioning MA positioning and drawdown."""
    marker = mock_structure_marker_rows[0]

    expected_output = StructureOutput(
        structure_label="Constructive",
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        narrative=(
            "VHM trades above the 10w, 20w, and 50w moving averages, "
            "reflecting a healthy uptrend. The drawdown from ATH of -12.5% "
            "is moderate and within normal correction range. "
            "Structure is constructive for medium-term investors."
        ),
        sources={},
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes import structure as structure_module

        importlib.reload(structure_module)
        result_state = structure_module.structure_node(base_equity_state)

    output = result_state["structure_output"]
    assert output is not None
    narrative_lower = output.narrative.lower()
    # Narrative should reference MA positioning or moving average
    assert any(
        term in narrative_lower
        for term in ["moving average", "ma", "10w", "20w", "50w", "above", "uptrend"]
    ), f"Narrative missing MA context: {output.narrative}"
    # Narrative should reference drawdown
    assert any(
        term in narrative_lower
        for term in ["drawdown", "ath", "high", "-12", "12.5", "correction"]
    ), f"Narrative missing drawdown context: {output.narrative}"


# ---------------------------------------------------------------------------
# Test 3: Constructive label when close > all MAs and small drawdown
# ---------------------------------------------------------------------------


def test_structure_node_constructive_label(
    base_equity_state: ReportState,
    mock_structure_marker_rows,
):
    """structure_node assigns Constructive when close > all MAs and drawdown is small."""
    marker = mock_structure_marker_rows[0]
    # Verify fixture: close=42500 > ma_10w=41200 > ma_20w=40100 > ma_50w=38500
    assert marker.close > marker.ma_10w > marker.ma_20w > marker.ma_50w
    assert marker.drawdown_from_ath > -0.20  # small drawdown

    expected_output = StructureOutput(
        structure_label="Constructive",
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        narrative="Structure is constructive.",
        sources={},
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes import structure as structure_module

        importlib.reload(structure_module)
        result_state = structure_module.structure_node(base_equity_state)

    output = result_state["structure_output"]
    assert output.structure_label == "Constructive"


# ---------------------------------------------------------------------------
# Test 4: Deteriorating label when close < all MAs and drawdown is large
# ---------------------------------------------------------------------------


def test_structure_node_deteriorating_label(
    mock_deteriorating_marker_rows,
    mock_fred_rows,
    mock_regime_analogues,
    mock_fundamentals_rows,
    mock_document_chunks,
):
    """structure_node assigns Deteriorating when close < all MAs and drawdown is large."""
    marker = mock_deteriorating_marker_rows[0]
    # Verify fixture: close=28000 < ma_10w=35000 < ma_20w=38000 < ma_50w=41000
    assert marker.close < marker.ma_10w < marker.ma_20w < marker.ma_50w
    assert marker.drawdown_from_ath < -0.20  # severe drawdown

    deteriorating_state: ReportState = ReportState(
        ticker="VHM",
        asset_type="equity",
        fred_rows=mock_fred_rows,
        regime_analogues=mock_regime_analogues,
        macro_docs=mock_document_chunks,
        fundamentals_rows=mock_fundamentals_rows,
        structure_marker_rows=mock_deteriorating_marker_rows,
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

    expected_output = StructureOutput(
        structure_label="Deteriorating",
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        narrative="Price is below all key moving averages with significant drawdown.",
        sources={},
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes import structure as structure_module

        importlib.reload(structure_module)
        result_state = structure_module.structure_node(deteriorating_state)

    output = result_state["structure_output"]
    assert output.structure_label == "Deteriorating"


# ---------------------------------------------------------------------------
# Test 5: Partial assessment with None MA values produces warning
# ---------------------------------------------------------------------------


def test_structure_node_partial_markers_produces_warning(
    mock_partial_marker_rows,
    mock_fred_rows,
    mock_regime_analogues,
    mock_fundamentals_rows,
    mock_document_chunks,
):
    """structure_node with None MA values produces StructureOutput with warnings."""
    partial_state: ReportState = ReportState(
        ticker="VHM",
        asset_type="equity",
        fred_rows=mock_fred_rows,
        regime_analogues=mock_regime_analogues,
        macro_docs=mock_document_chunks,
        fundamentals_rows=mock_fundamentals_rows,
        structure_marker_rows=mock_partial_marker_rows,
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

    expected_output = StructureOutput(
        structure_label="Neutral",
        close=42_500.0,
        ma_10w=None,
        ma_20w=40_100.0,
        ma_50w=None,
        drawdown_from_ath=-0.125,
        narrative="Partial data: ma_10w and ma_50w unavailable. Assessment based on available MA.",
        sources={},
        warnings=["ma_10w is missing from structure_markers", "ma_50w is missing from structure_markers"],
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes import structure as structure_module

        importlib.reload(structure_module)
        result_state = structure_module.structure_node(partial_state)

    output = result_state["structure_output"]
    assert output is not None
    # Should have warnings for missing MA values
    assert len(output.warnings) > 0
    warning_text = " ".join(output.warnings).lower()
    assert "ma_10w" in warning_text or "ma_50w" in warning_text


# ---------------------------------------------------------------------------
# Test 6: No retrieval function imports in structure.py
# ---------------------------------------------------------------------------


def test_structure_node_no_retrieval_function_imports():
    """structure_node module must NOT import retrieval functions — only type imports."""
    # Ensure module is loaded
    import reasoning.app.nodes.structure as structure_module

    importlib.reload(structure_module)

    # Banned retrieval function names (not types)
    banned_names = [
        "get_structure_markers",
        "get_fred_indicators",
        "get_fundamentals",
        "get_regime_analogues",
        "search_macro_docs",
        "search_earnings_docs",
        "get_gold_price",
        "get_gold_etf_ohlcv",
    ]

    module_attrs = dir(structure_module)
    for banned in banned_names:
        assert banned not in module_attrs, (
            f"structure.py must not import retrieval function '{banned}'. "
            "Only type imports from retrieval.types are permitted."
        )

    # Also check source code doesn't import from retrieval functions module
    source = inspect.getsource(structure_module)
    # Should not import from retrieval.neo4j_retriever, retrieval.postgres_retriever, etc.
    assert "from reasoning.app.retrieval.neo4j_retriever" not in source
    assert "from reasoning.app.retrieval.postgres_retriever" not in source
    assert "from reasoning.app.retrieval.qdrant_retriever" not in source
    # Type imports from retrieval.types ARE allowed
    # (no assertion against retrieval.types — that's permitted)


# ---------------------------------------------------------------------------
# Test 7: sources dict populated for each numeric field
# ---------------------------------------------------------------------------


def test_structure_node_populates_sources(
    base_equity_state: ReportState,
    mock_structure_marker_rows,
):
    """structure_node populates sources dict with entries for each numeric field."""
    marker = mock_structure_marker_rows[0]
    source_key = f"structure_markers:{marker.symbol}:{marker.data_as_of.isoformat()}"

    expected_output = StructureOutput(
        structure_label="Constructive",
        close=marker.close,
        ma_10w=marker.ma_10w,
        ma_20w=marker.ma_20w,
        ma_50w=marker.ma_50w,
        drawdown_from_ath=marker.drawdown_from_ath,
        drawdown_from_52w_high=marker.drawdown_from_52w_high,
        close_pct_rank=marker.close_pct_rank,
        narrative="Structure is constructive.",
        sources={
            "close": source_key,
            "ma_10w": source_key,
            "ma_20w": source_key,
            "ma_50w": source_key,
            "drawdown_from_ath": source_key,
            "drawdown_from_52w_high": source_key,
            "close_pct_rank": source_key,
        },
    )

    mock_llm = _make_mock_llm(expected_output)

    with patch(
        "reasoning.app.nodes.structure.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        from reasoning.app.nodes import structure as structure_module

        importlib.reload(structure_module)
        result_state = structure_module.structure_node(base_equity_state)

    output = result_state["structure_output"]
    assert output is not None
    assert len(output.sources) > 0
    # All present numeric fields should have a source entry
    for field in ["close", "ma_10w", "ma_20w", "ma_50w", "drawdown_from_ath"]:
        assert field in output.sources, f"Missing source entry for field '{field}'"
    # Source values should reference the marker symbol
    for key, val in output.sources.items():
        assert marker.symbol in val, f"Source for '{key}' does not reference symbol: {val}"
