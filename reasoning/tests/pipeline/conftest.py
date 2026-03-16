"""
reasoning/tests/pipeline/conftest.py — Mock state fixtures for compose_report_node tests.
Phase 7 | Plan 02

Provides:
    mock_report_state_with_conflict:  Full ReportState with all node outputs + conflict.
    mock_report_state_no_conflict:    Full ReportState with conflict_output=None.
    mock_report_state_gold:           Gold asset ReportState (triggers WGC warning).
"""

from __future__ import annotations

import pytest
from typing import Optional

from reasoning.app.nodes.state import (
    MacroRegimeOutput,
    ValuationOutput,
    StructureOutput,
    EntryQualityOutput,
    ConflictOutput,
    GroundingResult,
    RegimeProbability,
)


# ---------------------------------------------------------------------------
# Shared output fixtures
# ---------------------------------------------------------------------------


def _make_macro_regime_output() -> MacroRegimeOutput:
    return MacroRegimeOutput(
        regime_probabilities=[
            RegimeProbability(
                regime_id="regime_2008_gfc",
                regime_name="Global Financial Crisis 2008",
                confidence=0.72,
                source_analogue_id="analogue_2008",
            ),
            RegimeProbability(
                regime_id="regime_2020_covid",
                regime_name="COVID Shock 2020",
                confidence=0.18,
                source_analogue_id="analogue_2020",
            ),
        ],
        top_regime_id="regime_2008_gfc",
        top_confidence=0.72,
        is_mixed_signal=False,
        mixed_signal_label=None,
        top_two_analogues=[],
        macro_label="Headwind",
        narrative="Current macro environment resembles the 2008 GFC with tight credit conditions.",
        sources={"fred_indicators": "row_001", "macro_docs": "chunk_001"},
        warnings=[],
    )


def _make_valuation_output_equity() -> ValuationOutput:
    return ValuationOutput(
        asset_type="equity",
        valuation_label="Attractive",
        pe_ratio=12.5,
        pb_ratio=1.8,
        pe_vs_analogue_avg=None,
        pb_vs_analogue_avg=None,
        analogue_ids_used=["analogue_2008"],
        real_yield=None,
        etf_flow_context=None,
        missing_metrics=[],
        narrative="VNM trades at 12.5x P/E, below its historical average, indicating attractive entry.",
        sources={"fundamentals": "row_vnm_001"},
        warnings=[],
    )


def _make_valuation_output_gold() -> ValuationOutput:
    return ValuationOutput(
        asset_type="gold",
        valuation_label="Fair",
        pe_ratio=None,
        pb_ratio=None,
        pe_vs_analogue_avg=None,
        pb_vs_analogue_avg=None,
        analogue_ids_used=["analogue_2008"],
        real_yield=1.2,
        etf_flow_context="ETF inflows elevated at $3.2B last month",
        missing_metrics=["wgc_cb_buying"],
        narrative="Gold real yield of 1.2% supports fair valuation; central bank buying data unavailable.",
        sources={"gold_price": "row_gold_001"},
        warnings=["DATA WARNING: WGC central bank buying data unavailable (HTTP 501)"],
    )


def _make_structure_output() -> StructureOutput:
    return StructureOutput(
        structure_label="Neutral",
        close=18500.0,
        ma_10w=18200.0,
        ma_20w=17900.0,
        ma_50w=17600.0,
        drawdown_from_ath=-15.2,
        drawdown_from_52w_high=-8.4,
        close_pct_rank=0.62,
        narrative="VNM close is above all major moving averages with moderate drawdown from ATH.",
        sources={"structure_markers": "row_vnm_struct_001"},
        warnings=[],
    )


def _make_entry_quality_output() -> EntryQualityOutput:
    return EntryQualityOutput(
        macro_assessment="Headwind",
        valuation_assessment="Attractive",
        structure_assessment="Neutral",
        composite_tier="Cautious",
        conflict_pattern="Macro–Valuation Divergence",
        conflict_narrative="Attractive valuation conflicts with macro headwind signal.",
        structure_veto_applied=False,
        stale_data_caveat=None,
        narrative="Entry quality is Cautious — attractive valuation partially offset by macro headwinds.",
        sources={"entry_quality": "computed"},
        warnings=[],
    )


def _make_entry_quality_output_with_stale() -> EntryQualityOutput:
    return EntryQualityOutput(
        macro_assessment="Headwind",
        valuation_assessment="Attractive",
        structure_assessment="Neutral",
        composite_tier="Cautious",
        conflict_pattern=None,
        conflict_narrative=None,
        structure_veto_applied=False,
        stale_data_caveat="DATA WARNING: fred_indicators data is 45 days old (threshold: 30 days)",
        narrative="Entry quality is Cautious with stale FRED data caveat.",
        sources={"entry_quality": "computed"},
        warnings=[],
    )


def _make_conflict_output() -> ConflictOutput:
    return ConflictOutput(
        pattern_name="Macro–Valuation Divergence",
        severity="minor",
        macro_label="Headwind",
        valuation_label="Attractive",
        structure_label="Neutral",
        tier_impact="Tier held at Cautious (minor conflict; no automatic downgrade).",
        narrative="Attractive valuation in a macro headwind environment. Historically this resolves toward macro direction.",
        sources={"conflict": "pattern_lookup"},
        warnings=[],
    )


def _make_grounding_result() -> GroundingResult:
    return GroundingResult(
        status="pass",
        checked_outputs=["macro_regime_output", "valuation_output", "structure_output"],
        unattributed_claims=[],
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_report_state_with_conflict() -> dict:
    """Full mock ReportState with all node outputs + conflict_output populated."""
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
        "earnings_docs": [],
        "macro_regime_output": _make_macro_regime_output(),
        "valuation_output": _make_valuation_output_equity(),
        "structure_output": _make_structure_output(),
        "entry_quality_output": _make_entry_quality_output(),
        "grounding_result": _make_grounding_result(),
        "conflict_output": _make_conflict_output(),
        "report_output": None,
        "language": "en",
        "retrieval_warnings": [],
    }


@pytest.fixture
def mock_report_state_no_conflict() -> dict:
    """Full mock ReportState with conflict_output=None (no conflict detected)."""
    entry = _make_entry_quality_output()
    # Remove conflict fields for no-conflict path
    entry = EntryQualityOutput(
        macro_assessment=entry.macro_assessment,
        valuation_assessment=entry.valuation_assessment,
        structure_assessment=entry.structure_assessment,
        composite_tier="Neutral",
        conflict_pattern=None,
        conflict_narrative=None,
        structure_veto_applied=False,
        stale_data_caveat=None,
        narrative="Entry quality is Neutral — balanced signals.",
        sources=entry.sources,
        warnings=[],
    )
    return {
        "ticker": "FPT",
        "asset_type": "equity",
        "fred_rows": [],
        "regime_analogues": [],
        "macro_docs": [],
        "fundamentals_rows": [],
        "structure_marker_rows": [],
        "gold_price_rows": [],
        "gold_etf_rows": [],
        "earnings_docs": [],
        "macro_regime_output": _make_macro_regime_output(),
        "valuation_output": _make_valuation_output_equity(),
        "structure_output": _make_structure_output(),
        "entry_quality_output": entry,
        "grounding_result": _make_grounding_result(),
        "conflict_output": None,
        "report_output": None,
        "language": "en",
        "retrieval_warnings": [],
    }


@pytest.fixture
def mock_report_state_gold() -> dict:
    """Gold asset ReportState — triggers WGC data gap warning."""
    entry = EntryQualityOutput(
        macro_assessment="Headwind",
        valuation_assessment="Fair",
        structure_assessment="Neutral",
        composite_tier="Cautious",
        conflict_pattern=None,
        conflict_narrative=None,
        structure_veto_applied=False,
        stale_data_caveat=None,
        narrative="Gold entry quality is Cautious under macro headwinds.",
        sources={"entry_quality": "computed"},
        warnings=[],
    )
    return {
        "ticker": "GOLD",
        "asset_type": "gold",
        "fred_rows": [],
        "regime_analogues": [],
        "macro_docs": [],
        "fundamentals_rows": [],
        "structure_marker_rows": [],
        "gold_price_rows": [],
        "gold_etf_rows": [],
        "earnings_docs": [],
        "macro_regime_output": _make_macro_regime_output(),
        "valuation_output": _make_valuation_output_gold(),
        "structure_output": _make_structure_output(),
        "entry_quality_output": entry,
        "grounding_result": _make_grounding_result(),
        "conflict_output": None,
        "report_output": None,
        "language": "en",
        "retrieval_warnings": [],
    }


@pytest.fixture
def mock_report_state_with_retrieval_warnings() -> dict:
    """ReportState with retrieval_warnings populated for warning collection tests."""
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
        "earnings_docs": [],
        "macro_regime_output": _make_macro_regime_output(),
        "valuation_output": _make_valuation_output_equity(),
        "structure_output": _make_structure_output(),
        "entry_quality_output": _make_entry_quality_output_with_stale(),
        "grounding_result": _make_grounding_result(),
        "conflict_output": None,
        "report_output": None,
        "language": "en",
        "retrieval_warnings": [
            "DATA WARNING: earnings_docs freshness check failed — data is 60 days old"
        ],
    }
