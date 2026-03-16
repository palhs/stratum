"""
reasoning/tests/pipeline/test_compose_report.py — TDD tests for report_schema.py and compose_report.py.
Phase 7 | Plan 02 | Requirements: REPT-01, REPT-04

Tests verify:
- Pydantic card model field presence and validation
- compose_report_node produces correct ReportOutput from mock state
- Conflict card included/excluded based on conflict_output presence
- Data warnings correctly collected (WGC for gold, stale caveats, retrieval warnings)
- report_json is flat (no nested Pydantic instances)
"""

from __future__ import annotations

import pytest
from typing import Optional


# ---------------------------------------------------------------------------
# Schema tests: EntryQualityCard
# ---------------------------------------------------------------------------


def test_entry_quality_card_fields():
    """EntryQualityCard has all required fields."""
    from reasoning.app.pipeline.report_schema import EntryQualityCard

    fields = EntryQualityCard.model_fields
    assert "tier" in fields, "EntryQualityCard must have 'tier' field"
    assert "macro_assessment" in fields, "EntryQualityCard must have 'macro_assessment' field"
    assert "valuation_assessment" in fields, "EntryQualityCard must have 'valuation_assessment' field"
    assert "structure_assessment" in fields, "EntryQualityCard must have 'structure_assessment' field"
    assert "conflict_pattern" in fields, "EntryQualityCard must have 'conflict_pattern' field"
    assert "structure_veto_applied" in fields, "EntryQualityCard must have 'structure_veto_applied' field"
    assert "narrative" in fields, "EntryQualityCard must have 'narrative' field"


def test_entry_quality_card_validates():
    """EntryQualityCard can be instantiated with valid data."""
    from reasoning.app.pipeline.report_schema import EntryQualityCard

    card = EntryQualityCard(
        tier="Cautious",
        macro_assessment="Headwind",
        valuation_assessment="Attractive",
        structure_assessment="Neutral",
        conflict_pattern="Macro–Valuation Divergence",
        structure_veto_applied=False,
        narrative="Entry quality is Cautious.",
    )
    assert card.tier == "Cautious"
    assert card.conflict_pattern == "Macro–Valuation Divergence"
    assert card.structure_veto_applied is False


def test_entry_quality_card_conflict_pattern_optional():
    """EntryQualityCard conflict_pattern defaults to None."""
    from reasoning.app.pipeline.report_schema import EntryQualityCard

    card = EntryQualityCard(
        tier="Neutral",
        macro_assessment="Supportive",
        valuation_assessment="Fair",
        structure_assessment="Constructive",
        structure_veto_applied=False,
        narrative="Neutral entry.",
    )
    assert card.conflict_pattern is None


# ---------------------------------------------------------------------------
# Schema tests: MacroRegimeCard
# ---------------------------------------------------------------------------


def test_macro_regime_card_fields():
    """MacroRegimeCard has all required fields."""
    from reasoning.app.pipeline.report_schema import MacroRegimeCard

    fields = MacroRegimeCard.model_fields
    assert "label" in fields, "MacroRegimeCard must have 'label' field"
    assert "top_confidence" in fields, "MacroRegimeCard must have 'top_confidence' field"
    assert "is_mixed_signal" in fields, "MacroRegimeCard must have 'is_mixed_signal' field"
    assert "narrative" in fields, "MacroRegimeCard must have 'narrative' field"
    assert "regime_probabilities" in fields, "MacroRegimeCard must have 'regime_probabilities' field"


def test_macro_regime_card_validates():
    """MacroRegimeCard can be instantiated with valid data."""
    from reasoning.app.pipeline.report_schema import MacroRegimeCard

    card = MacroRegimeCard(
        label="Headwind",
        top_confidence=0.72,
        is_mixed_signal=False,
        regime_probabilities=[
            {"regime_id": "regime_2008_gfc", "confidence": 0.72, "regime_name": "GFC", "source_analogue_id": "a1"}
        ],
        narrative="Macro is a headwind.",
    )
    assert card.label == "Headwind"
    assert card.top_confidence == 0.72
    assert card.is_mixed_signal is False
    assert len(card.regime_probabilities) == 1


# ---------------------------------------------------------------------------
# Schema tests: ValuationCard
# ---------------------------------------------------------------------------


def test_valuation_card_fields():
    """ValuationCard has all required fields."""
    from reasoning.app.pipeline.report_schema import ValuationCard

    fields = ValuationCard.model_fields
    assert "label" in fields, "ValuationCard must have 'label' field"
    assert "pe_ratio" in fields, "ValuationCard must have 'pe_ratio' field"
    assert "pb_ratio" in fields, "ValuationCard must have 'pb_ratio' field"
    assert "real_yield" in fields, "ValuationCard must have 'real_yield' field"
    assert "narrative" in fields, "ValuationCard must have 'narrative' field"


def test_valuation_card_optional_fields_default_none():
    """ValuationCard optional fields default to None."""
    from reasoning.app.pipeline.report_schema import ValuationCard

    card = ValuationCard(label="Fair", narrative="Fair valuation.")
    assert card.pe_ratio is None
    assert card.pb_ratio is None
    assert card.real_yield is None
    assert card.etf_flow_context is None


# ---------------------------------------------------------------------------
# Schema tests: StructureCard
# ---------------------------------------------------------------------------


def test_structure_card_fields():
    """StructureCard has all required fields."""
    from reasoning.app.pipeline.report_schema import StructureCard

    fields = StructureCard.model_fields
    assert "label" in fields, "StructureCard must have 'label' field"
    assert "close" in fields, "StructureCard must have 'close' field"
    assert "drawdown_from_ath" in fields, "StructureCard must have 'drawdown_from_ath' field"
    assert "close_pct_rank" in fields, "StructureCard must have 'close_pct_rank' field"
    assert "narrative" in fields, "StructureCard must have 'narrative' field"


def test_structure_card_optional_fields_default_none():
    """StructureCard optional fields default to None."""
    from reasoning.app.pipeline.report_schema import StructureCard

    card = StructureCard(label="Neutral", narrative="Structure is neutral.")
    assert card.close is None
    assert card.drawdown_from_ath is None
    assert card.drawdown_from_52w_high is None
    assert card.close_pct_rank is None


# ---------------------------------------------------------------------------
# Schema tests: ConflictCard
# ---------------------------------------------------------------------------


def test_conflict_card_fields():
    """ConflictCard has all required fields."""
    from reasoning.app.pipeline.report_schema import ConflictCard

    fields = ConflictCard.model_fields
    assert "pattern_name" in fields, "ConflictCard must have 'pattern_name' field"
    assert "severity" in fields, "ConflictCard must have 'severity' field"
    assert "tier_impact" in fields, "ConflictCard must have 'tier_impact' field"
    assert "narrative" in fields, "ConflictCard must have 'narrative' field"


def test_conflict_card_validates():
    """ConflictCard can be instantiated with valid data."""
    from reasoning.app.pipeline.report_schema import ConflictCard

    card = ConflictCard(
        pattern_name="Macro–Valuation Divergence",
        severity="minor",
        tier_impact="No automatic downgrade — tier held.",
        narrative="Conflict narrative here.",
    )
    assert card.pattern_name == "Macro–Valuation Divergence"
    assert card.severity == "minor"


# ---------------------------------------------------------------------------
# Schema tests: ReportCard
# ---------------------------------------------------------------------------


def test_report_card_fields():
    """ReportCard has all required fields in conclusion-first order."""
    from reasoning.app.pipeline.report_schema import ReportCard

    fields = ReportCard.model_fields
    assert "entry_quality" in fields, "ReportCard must have 'entry_quality' field"
    assert "conflict" in fields, "ReportCard must have 'conflict' field (Optional)"
    assert "macro_regime" in fields, "ReportCard must have 'macro_regime' field"
    assert "valuation" in fields, "ReportCard must have 'valuation' field"
    assert "structure" in fields, "ReportCard must have 'structure' field"
    assert "data_warnings" in fields, "ReportCard must have 'data_warnings' field"
    assert "language" in fields, "ReportCard must have 'language' field"


def test_report_card_conflict_optional():
    """ReportCard conflict field defaults to None."""
    from reasoning.app.pipeline.report_schema import (
        ReportCard, EntryQualityCard, MacroRegimeCard, ValuationCard, StructureCard
    )

    card = ReportCard(
        entry_quality=EntryQualityCard(
            tier="Neutral",
            macro_assessment="Supportive",
            valuation_assessment="Fair",
            structure_assessment="Constructive",
            structure_veto_applied=False,
            narrative="Neutral.",
        ),
        macro_regime=MacroRegimeCard(
            label="Supportive",
            top_confidence=0.80,
            is_mixed_signal=False,
            regime_probabilities=[],
            narrative="Macro narrative.",
        ),
        valuation=ValuationCard(label="Fair", narrative="Valuation narrative."),
        structure=StructureCard(label="Constructive", narrative="Structure narrative."),
    )
    assert card.conflict is None
    assert card.data_warnings == []
    assert card.language == "en"


def test_report_card_serializes_flat(mock_report_state_no_conflict):
    """ReportCard serialized with model_dump_json(exclude_none=True) produces flat dict."""
    from reasoning.app.pipeline.report_schema import (
        ReportCard, EntryQualityCard, MacroRegimeCard, ValuationCard, StructureCard
    )
    import json

    card = ReportCard(
        entry_quality=EntryQualityCard(
            tier="Neutral",
            macro_assessment="Supportive",
            valuation_assessment="Fair",
            structure_assessment="Constructive",
            structure_veto_applied=False,
            narrative="Neutral.",
        ),
        macro_regime=MacroRegimeCard(
            label="Supportive",
            top_confidence=0.80,
            is_mixed_signal=False,
            regime_probabilities=[],
            narrative="Macro narrative.",
        ),
        valuation=ValuationCard(label="Fair", narrative="Valuation narrative."),
        structure=StructureCard(label="Constructive", narrative="Structure narrative."),
    )
    result = json.loads(card.model_dump_json(exclude_none=True))
    # Should be a dict (not a list)
    assert isinstance(result, dict)
    # Top-level keys should be card names
    assert "entry_quality" in result
    assert "macro_regime" in result
    assert "valuation" in result
    assert "structure" in result
    # conflict excluded when None
    assert "conflict" not in result


# ---------------------------------------------------------------------------
# compose_report_node tests
# ---------------------------------------------------------------------------


def test_compose_report_node_is_importable():
    """compose_report_node is importable from reasoning.app.pipeline.compose_report."""
    from reasoning.app.pipeline.compose_report import compose_report_node  # noqa: F401


def test_compose_report_node_with_conflict(mock_report_state_with_conflict):
    """compose_report_node with conflict_output returns ReportOutput with conflict card."""
    from reasoning.app.pipeline.compose_report import compose_report_node
    from reasoning.app.nodes.state import ReportOutput

    result = compose_report_node(mock_report_state_with_conflict)

    assert "report_output" in result, "compose_report_node must return dict with 'report_output' key"
    output = result["report_output"]
    assert isinstance(output, ReportOutput), f"report_output must be ReportOutput, got {type(output)}"

    # Verify conflict card present in report_json
    report_json = output.report_json
    assert isinstance(report_json, dict), "report_json must be a dict"
    assert "conflict" in report_json, "report_json must include conflict card when conflict_output present"
    assert report_json["conflict"]["pattern_name"] == "Macro–Valuation Divergence"


def test_compose_report_node_no_conflict(mock_report_state_no_conflict):
    """compose_report_node with conflict_output=None excludes conflict card from report_json."""
    from reasoning.app.pipeline.compose_report import compose_report_node
    from reasoning.app.nodes.state import ReportOutput

    result = compose_report_node(mock_report_state_no_conflict)

    assert "report_output" in result
    output = result["report_output"]
    assert isinstance(output, ReportOutput)

    report_json = output.report_json
    assert isinstance(report_json, dict)
    # conflict excluded (exclude_none=True when conflict is None)
    assert "conflict" not in report_json, (
        "report_json must NOT include conflict card when conflict_output is None"
    )


def test_compose_report_node_four_required_sections(mock_report_state_no_conflict):
    """compose_report_node always includes 4 required card sections."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    result = compose_report_node(mock_report_state_no_conflict)
    report_json = result["report_output"].report_json

    assert "entry_quality" in report_json, "report_json must include entry_quality section"
    assert "macro_regime" in report_json, "report_json must include macro_regime section"
    assert "valuation" in report_json, "report_json must include valuation section"
    assert "structure" in report_json, "report_json must include structure section"


def test_compose_report_node_report_json_is_flat(mock_report_state_no_conflict):
    """report_json contains flat dicts per card section (no nested Pydantic instances)."""
    from reasoning.app.pipeline.compose_report import compose_report_node
    from pydantic import BaseModel

    result = compose_report_node(mock_report_state_no_conflict)
    report_json = result["report_output"].report_json

    # Each card section should be a plain dict, not a Pydantic model instance
    for section_name in ["entry_quality", "macro_regime", "valuation", "structure"]:
        section = report_json[section_name]
        assert isinstance(section, dict), (
            f"report_json['{section_name}'] must be dict, got {type(section)}"
        )
        assert not isinstance(section, BaseModel), (
            f"report_json['{section_name}'] must not be a Pydantic model instance"
        )


def test_compose_report_node_language_propagated(mock_report_state_no_conflict):
    """compose_report_node reads language from state and includes in ReportOutput."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    mock_report_state_no_conflict["language"] = "vi"
    result = compose_report_node(mock_report_state_no_conflict)

    output = result["report_output"]
    assert output.language == "vi"
    assert output.report_json["language"] == "vi"


def test_compose_report_node_data_warnings_gold(mock_report_state_gold):
    """compose_report_node for gold asset includes WGC data gap warning."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    result = compose_report_node(mock_report_state_gold)
    output = result["report_output"]

    # WGC warning must appear in data_warnings
    wgc_warnings = [w for w in output.data_warnings if "WGC" in w or "central bank" in w.lower()]
    assert len(wgc_warnings) > 0, (
        f"Gold asset must have WGC data gap warning in data_warnings. Got: {output.data_warnings}"
    )


def test_compose_report_node_data_warnings_stale_caveat(mock_report_state_with_retrieval_warnings):
    """compose_report_node includes stale_data_caveat from entry_quality_output when present."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    result = compose_report_node(mock_report_state_with_retrieval_warnings)
    output = result["report_output"]

    stale_warnings = [w for w in output.data_warnings if "fred_indicators" in w and "45 days" in w]
    assert len(stale_warnings) > 0, (
        f"Stale data caveat must appear in data_warnings. Got: {output.data_warnings}"
    )


def test_compose_report_node_data_warnings_retrieval(mock_report_state_with_retrieval_warnings):
    """compose_report_node includes retrieval_warnings from state in data_warnings."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    result = compose_report_node(mock_report_state_with_retrieval_warnings)
    output = result["report_output"]

    retrieval_warnings = [w for w in output.data_warnings if "earnings_docs" in w]
    assert len(retrieval_warnings) > 0, (
        f"Retrieval warnings must appear in data_warnings. Got: {output.data_warnings}"
    )


def test_compose_report_node_data_as_of_is_datetime(mock_report_state_no_conflict):
    """compose_report_node sets data_as_of to a datetime."""
    from reasoning.app.pipeline.compose_report import compose_report_node
    from datetime import datetime

    result = compose_report_node(mock_report_state_no_conflict)
    output = result["report_output"]

    assert isinstance(output.data_as_of, datetime), (
        f"data_as_of must be a datetime, got {type(output.data_as_of)}"
    )


def test_compose_report_node_report_markdown_empty(mock_report_state_no_conflict):
    """compose_report_node sets report_markdown to empty string (placeholder for Plan 03)."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    result = compose_report_node(mock_report_state_no_conflict)
    output = result["report_output"]

    assert output.report_markdown == "", (
        "report_markdown must be empty string placeholder (real rendering in Plan 03)"
    )


# ---------------------------------------------------------------------------
# _collect_data_warnings helper tests
# ---------------------------------------------------------------------------


def test_collect_data_warnings_gold_always_has_wgc():
    """_collect_data_warnings for gold asset always includes WGC warning."""
    from reasoning.app.pipeline.compose_report import _collect_data_warnings
    from reasoning.app.nodes.state import (
        EntryQualityOutput, ValuationOutput, MacroRegimeOutput, StructureOutput,
        RegimeProbability
    )

    state = {
        "asset_type": "gold",
        "retrieval_warnings": [],
        "entry_quality_output": EntryQualityOutput(
            macro_assessment="Headwind",
            valuation_assessment="Fair",
            structure_assessment="Neutral",
            composite_tier="Cautious",
            stale_data_caveat=None,
            structure_veto_applied=False,
            narrative="Cautious.",
        ),
        "macro_regime_output": MacroRegimeOutput(
            top_regime_id="r1", top_confidence=0.7,
            is_mixed_signal=False, macro_label="Mixed",
            narrative="Mixed.", sources={}, warnings=[],
        ),
        "valuation_output": ValuationOutput(
            asset_type="gold", valuation_label="Fair",
            narrative="Fair.", sources={}, warnings=[],
        ),
        "structure_output": StructureOutput(
            structure_label="Neutral", narrative="Neutral.", sources={}, warnings=[],
        ),
        "conflict_output": None,
    }
    warnings = _collect_data_warnings(state)
    wgc_warnings = [w for w in warnings if "WGC" in w or "central bank" in w.lower()]
    assert len(wgc_warnings) > 0, f"WGC warning must always be present for gold assets. Got: {warnings}"


def test_collect_data_warnings_stale_caveat():
    """_collect_data_warnings includes stale_data_caveat from entry_quality_output."""
    from reasoning.app.pipeline.compose_report import _collect_data_warnings
    from reasoning.app.nodes.state import (
        EntryQualityOutput, ValuationOutput, MacroRegimeOutput, StructureOutput,
    )

    state = {
        "asset_type": "equity",
        "retrieval_warnings": [],
        "entry_quality_output": EntryQualityOutput(
            macro_assessment="Mixed",
            valuation_assessment="Fair",
            structure_assessment="Neutral",
            composite_tier="Neutral",
            stale_data_caveat="DATA WARNING: fred_indicators is stale",
            structure_veto_applied=False,
            narrative="Neutral.",
        ),
        "macro_regime_output": MacroRegimeOutput(
            top_regime_id="r1", top_confidence=0.7,
            is_mixed_signal=False, macro_label="Mixed",
            narrative="Mixed.", sources={}, warnings=[],
        ),
        "valuation_output": ValuationOutput(
            asset_type="equity", valuation_label="Fair",
            narrative="Fair.", sources={}, warnings=[],
        ),
        "structure_output": StructureOutput(
            structure_label="Neutral", narrative="Neutral.", sources={}, warnings=[],
        ),
        "conflict_output": None,
    }
    warnings = _collect_data_warnings(state)
    stale = [w for w in warnings if "fred_indicators" in w]
    assert len(stale) > 0, f"Stale data caveat must appear in warnings. Got: {warnings}"


def test_collect_data_warnings_retrieval_warnings():
    """_collect_data_warnings includes retrieval_warnings from state."""
    from reasoning.app.pipeline.compose_report import _collect_data_warnings
    from reasoning.app.nodes.state import (
        EntryQualityOutput, ValuationOutput, MacroRegimeOutput, StructureOutput,
    )

    state = {
        "asset_type": "equity",
        "retrieval_warnings": ["DATA WARNING: macro_docs 90 days stale"],
        "entry_quality_output": EntryQualityOutput(
            macro_assessment="Mixed",
            valuation_assessment="Fair",
            structure_assessment="Neutral",
            composite_tier="Neutral",
            stale_data_caveat=None,
            structure_veto_applied=False,
            narrative="Neutral.",
        ),
        "macro_regime_output": MacroRegimeOutput(
            top_regime_id="r1", top_confidence=0.7,
            is_mixed_signal=False, macro_label="Mixed",
            narrative="Mixed.", sources={}, warnings=[],
        ),
        "valuation_output": ValuationOutput(
            asset_type="equity", valuation_label="Fair",
            narrative="Fair.", sources={}, warnings=[],
        ),
        "structure_output": StructureOutput(
            structure_label="Neutral", narrative="Neutral.", sources={}, warnings=[],
        ),
        "conflict_output": None,
    }
    warnings = _collect_data_warnings(state)
    retrieval = [w for w in warnings if "macro_docs" in w]
    assert len(retrieval) > 0, f"Retrieval warnings must appear. Got: {warnings}"


# ---------------------------------------------------------------------------
# graph.py integration test
# ---------------------------------------------------------------------------


def test_graph_uses_real_compose_report_node():
    """graph.py imports compose_report_node from reasoning.app.pipeline.compose_report."""
    import reasoning.app.pipeline.graph as graph_module

    # Check that the module does not define compose_report_node locally
    # (it was replaced with the import from compose_report.py)
    import inspect
    source = inspect.getsource(graph_module)
    assert "from reasoning.app.pipeline.compose_report import compose_report_node" in source, (
        "graph.py must import compose_report_node from reasoning.app.pipeline.compose_report"
    )
