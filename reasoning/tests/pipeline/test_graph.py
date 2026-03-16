"""
reasoning/tests/pipeline/test_graph.py — Unit tests for graph assembly and prefetch.
Phase 7 | Plan 01 | Requirement: REAS-06

Tests verify:
- ReportState extension with language and report_output fields
- ReportOutput Pydantic model structure
- build_graph() returns a 7-node StateGraph with correct edge topology
- prefetch() dispatches to correct retrieval functions for equity vs gold paths
- prefetch() raises ValueError for invalid asset_type
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

from langgraph.graph import StateGraph, START, END


# ---------------------------------------------------------------------------
# Test 1: ReportState has language and report_output fields
# ---------------------------------------------------------------------------


def test_report_state_has_language_field():
    """ReportState TypedDict includes 'language' key."""
    from reasoning.app.nodes.state import ReportState
    # TypedDict __annotations__ contains all declared keys
    assert "language" in ReportState.__annotations__, (
        "ReportState must declare 'language: str' field"
    )


def test_report_state_has_report_output_field():
    """ReportState TypedDict includes 'report_output' key."""
    from reasoning.app.nodes.state import ReportState
    assert "report_output" in ReportState.__annotations__, (
        "ReportState must declare 'report_output: Optional[ReportOutput]' field"
    )


# ---------------------------------------------------------------------------
# Test 2: ReportOutput Pydantic model structure
# ---------------------------------------------------------------------------


def test_report_output_model_exists():
    """ReportOutput is importable from reasoning.app.nodes.state."""
    from reasoning.app.nodes.state import ReportOutput  # noqa: F401


def test_report_output_has_required_fields():
    """ReportOutput model has all required fields with correct types."""
    from reasoning.app.nodes.state import ReportOutput

    fields = ReportOutput.model_fields
    assert "report_json" in fields, "ReportOutput must have report_json field"
    assert "report_markdown" in fields, "ReportOutput must have report_markdown field"
    assert "language" in fields, "ReportOutput must have language field"
    assert "data_as_of" in fields, "ReportOutput must have data_as_of field"
    assert "data_warnings" in fields, "ReportOutput must have data_warnings field"
    assert "model_version" in fields, "ReportOutput must have model_version field"
    assert "warnings" in fields, "ReportOutput must have warnings field"


def test_report_output_validates():
    """ReportOutput can be instantiated with valid data."""
    from reasoning.app.nodes.state import ReportOutput

    output = ReportOutput(
        report_json={"section": "macro", "value": 1},
        report_markdown="# Report\n\nContent here.",
        language="en",
        data_as_of=datetime(2026, 3, 16, tzinfo=timezone.utc),
        data_warnings=["STALE DATA: fred_indicators"],
        model_version="gemini-2.5-pro",
        warnings=[],
    )
    assert output.language == "en"
    assert output.model_version == "gemini-2.5-pro"
    assert output.warnings == []


def test_report_output_default_model_version():
    """ReportOutput model_version defaults to 'gemini-2.5-pro'."""
    from reasoning.app.nodes.state import ReportOutput

    output = ReportOutput(
        report_json={},
        report_markdown="",
        language="vi",
        data_as_of=datetime(2026, 3, 16, tzinfo=timezone.utc),
        data_warnings=[],
    )
    assert output.model_version == "gemini-2.5-pro"


def test_report_output_default_warnings():
    """ReportOutput warnings defaults to empty list."""
    from reasoning.app.nodes.state import ReportOutput

    output = ReportOutput(
        report_json={},
        report_markdown="",
        language="en",
        data_as_of=datetime(2026, 3, 16, tzinfo=timezone.utc),
        data_warnings=[],
    )
    assert output.warnings == []


# ---------------------------------------------------------------------------
# Test 3: build_graph() returns StateGraph with 7 nodes
# ---------------------------------------------------------------------------


def test_build_graph_is_importable():
    """build_graph is importable from reasoning.app.pipeline."""
    from reasoning.app.pipeline import build_graph  # noqa: F401


def test_build_graph_returns_state_graph():
    """build_graph() returns a StateGraph instance."""
    from reasoning.app.pipeline import build_graph

    graph = build_graph()
    assert isinstance(graph, StateGraph), (
        f"build_graph() must return StateGraph, got {type(graph)}"
    )


def test_build_graph_has_seven_nodes():
    """build_graph() StateGraph has exactly 7 nodes."""
    from reasoning.app.pipeline import build_graph

    graph = build_graph()
    # Compile to inspect; no checkpointer needed for unit test
    compiled = graph.compile()
    # Get node names from the graph
    node_names = set(compiled.get_graph().nodes.keys())
    # Remove START and END sentinel nodes if present
    node_names.discard("__start__")
    node_names.discard("__end__")
    expected_nodes = {
        "macro_regime",
        "valuation",
        "structure",
        "conflict",
        "entry_quality",
        "grounding_check",
        "compose_report",
    }
    assert node_names == expected_nodes, (
        f"Expected nodes {expected_nodes}, got {node_names}"
    )


def test_build_graph_compiles_without_error():
    """build_graph().compile() succeeds without a checkpointer (unit test mode)."""
    from reasoning.app.pipeline import build_graph

    graph = build_graph()
    compiled = graph.compile()
    assert compiled is not None


# ---------------------------------------------------------------------------
# Test 4: Graph has correct linear edge topology
# ---------------------------------------------------------------------------


def test_build_graph_linear_edge_topology():
    """Graph has correct linear edges: START→macro_regime→...→compose_report→END."""
    from reasoning.app.pipeline import build_graph

    graph = build_graph()
    compiled = graph.compile()
    graph_repr = compiled.get_graph()

    # Expected linear sequence
    expected_sequence = [
        "__start__",
        "macro_regime",
        "valuation",
        "structure",
        "conflict",
        "entry_quality",
        "grounding_check",
        "compose_report",
        "__end__",
    ]

    edges = graph_repr.edges
    edge_pairs = {(e.source, e.target) for e in edges}

    # Verify each consecutive pair has an edge
    for i in range(len(expected_sequence) - 1):
        src = expected_sequence[i]
        tgt = expected_sequence[i + 1]
        assert (src, tgt) in edge_pairs, (
            f"Missing edge: {src} → {tgt}. All edges: {edge_pairs}"
        )


# ---------------------------------------------------------------------------
# Test 5: prefetch() equity path — correct retrieval function dispatch
# ---------------------------------------------------------------------------


def test_prefetch_is_importable():
    """prefetch is importable from reasoning.app.pipeline."""
    from reasoning.app.pipeline import prefetch  # noqa: F401


def test_prefetch_equity_calls_correct_functions():
    """prefetch() equity path calls get_fundamentals, get_structure_markers,
    get_fred_indicators, search_earnings_docs, search_macro_docs, get_regime_analogues.
    Does NOT call get_gold_price or get_gold_etf."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with (
        patch("reasoning.app.pipeline.prefetch.get_fundamentals", return_value=[]) as mock_fund,
        patch("reasoning.app.pipeline.prefetch.get_structure_markers", return_value=[]) as mock_struct,
        patch("reasoning.app.pipeline.prefetch.get_fred_indicators", return_value=[]) as mock_fred,
        patch("reasoning.app.pipeline.prefetch.search_earnings_docs", return_value=[]) as mock_earn,
        patch("reasoning.app.pipeline.prefetch.search_macro_docs", return_value=[]) as mock_macro,
        patch("reasoning.app.pipeline.prefetch.get_regime_analogues", return_value=[]) as mock_neo,
        patch("reasoning.app.pipeline.prefetch.get_gold_price", return_value=[]) as mock_gold_price,
        patch("reasoning.app.pipeline.prefetch.get_gold_etf", return_value=[]) as mock_gold_etf,
    ):
        result = prefetch(
            ticker="VNM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )

    # Equity-specific functions should be called
    mock_fund.assert_called_once()
    mock_struct.assert_called_once()
    mock_fred.assert_called_once()
    mock_earn.assert_called_once()
    mock_macro.assert_called_once()
    mock_neo.assert_called_once()

    # Gold-specific functions should NOT be called
    mock_gold_price.assert_not_called()
    mock_gold_etf.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: prefetch() gold path — correct retrieval function dispatch
# ---------------------------------------------------------------------------


def test_prefetch_gold_calls_correct_functions():
    """prefetch() gold path calls get_gold_price, get_gold_etf, get_structure_markers
    (with 'GOLD'), get_fred_indicators, search_macro_docs, get_regime_analogues.
    Does NOT call get_fundamentals or search_earnings_docs."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with (
        patch("reasoning.app.pipeline.prefetch.get_fundamentals", return_value=[]) as mock_fund,
        patch("reasoning.app.pipeline.prefetch.get_structure_markers", return_value=[]) as mock_struct,
        patch("reasoning.app.pipeline.prefetch.get_fred_indicators", return_value=[]) as mock_fred,
        patch("reasoning.app.pipeline.prefetch.search_earnings_docs", return_value=[]) as mock_earn,
        patch("reasoning.app.pipeline.prefetch.search_macro_docs", return_value=[]) as mock_macro,
        patch("reasoning.app.pipeline.prefetch.get_regime_analogues", return_value=[]) as mock_neo,
        patch("reasoning.app.pipeline.prefetch.get_gold_price", return_value=[]) as mock_gold_price,
        patch("reasoning.app.pipeline.prefetch.get_gold_etf", return_value=[]) as mock_gold_etf,
    ):
        result = prefetch(
            ticker="GOLD",
            asset_type="gold",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )

    # Gold-specific functions should be called
    mock_gold_price.assert_called_once()
    mock_gold_etf.assert_called_once()
    mock_struct.assert_called_once()
    mock_fred.assert_called_once()
    mock_macro.assert_called_once()
    mock_neo.assert_called_once()

    # Equity-specific functions should NOT be called
    mock_fund.assert_not_called()
    mock_earn.assert_not_called()


def test_prefetch_gold_passes_gold_ticker_to_structure_markers():
    """prefetch() gold path calls get_structure_markers with 'GOLD' ticker."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with (
        patch("reasoning.app.pipeline.prefetch.get_fundamentals", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_structure_markers", return_value=[]) as mock_struct,
        patch("reasoning.app.pipeline.prefetch.get_fred_indicators", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_earnings_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_macro_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_regime_analogues", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_price", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_etf", return_value=[]),
    ):
        prefetch(
            ticker="GOLD",
            asset_type="gold",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )

    # get_structure_markers must be called with "GOLD" as the symbol
    call_args = mock_struct.call_args
    assert call_args is not None
    # Either positional or keyword arg
    args, kwargs = call_args
    symbol_arg = args[0] if args else kwargs.get("symbol")
    assert symbol_arg == "GOLD", (
        f"get_structure_markers must be called with 'GOLD', got {symbol_arg!r}"
    )


# ---------------------------------------------------------------------------
# Test 7: prefetch() raises ValueError for invalid asset_type
# ---------------------------------------------------------------------------


def test_prefetch_invalid_asset_type_raises_value_error():
    """prefetch() raises ValueError for unknown asset_type."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with pytest.raises(ValueError, match="Unknown asset_type"):
        prefetch(
            ticker="BTC",
            asset_type="crypto",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )


# ---------------------------------------------------------------------------
# Test 8: prefetch() returns dict with ReportState shape
# ---------------------------------------------------------------------------


def test_prefetch_equity_returns_report_state_shape():
    """prefetch() equity path returns dict with all ReportState keys, node outputs as None."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with (
        patch("reasoning.app.pipeline.prefetch.get_fundamentals", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_structure_markers", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_fred_indicators", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_earnings_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_macro_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_regime_analogues", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_price", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_etf", return_value=[]),
    ):
        result = prefetch(
            ticker="FPT",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )

    # Must be a dict
    assert isinstance(result, dict), "prefetch() must return a dict"

    # Retrieval fields populated (may be empty lists, not None)
    assert "ticker" in result
    assert "asset_type" in result
    assert "fred_rows" in result
    assert "regime_analogues" in result
    assert "macro_docs" in result
    assert "structure_marker_rows" in result
    assert "retrieval_warnings" in result

    # Node outputs must be None (set by nodes later)
    assert result.get("macro_regime_output") is None
    assert result.get("valuation_output") is None
    assert result.get("structure_output") is None
    assert result.get("entry_quality_output") is None
    assert result.get("grounding_result") is None
    assert result.get("conflict_output") is None
    assert result.get("report_output") is None


def test_prefetch_gold_returns_report_state_shape():
    """prefetch() gold path returns dict with all ReportState keys, node outputs as None."""
    from reasoning.app.pipeline import prefetch

    mock_engine = MagicMock()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    with (
        patch("reasoning.app.pipeline.prefetch.get_fundamentals", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_structure_markers", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_fred_indicators", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_earnings_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.search_macro_docs", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_regime_analogues", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_price", return_value=[]),
        patch("reasoning.app.pipeline.prefetch.get_gold_etf", return_value=[]),
    ):
        result = prefetch(
            ticker="GOLD",
            asset_type="gold",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
        )

    assert isinstance(result, dict)
    assert "gold_price_rows" in result
    assert "gold_etf_rows" in result
    assert result.get("report_output") is None
