"""
reasoning/app/pipeline/compose_report.py — compose_report_node: 7th and final graph node.
Phase 7 | Plan 02 | Requirements: REPT-01, REPT-04

Implements:
    compose_report_node(state) — reads all upstream node outputs and produces a structured
                                 ReportOutput with flat card objects in conclusion-first order.
    _collect_data_warnings(state) — collects freshness/data-quality warnings from all sources.

Design decisions (locked):
- Conclusion-first ordering: entry_quality → conflict (optional) → macro_regime → valuation → structure.
- report_json uses json.loads(card.model_dump_json(exclude_none=True)) — flat dict, no Pydantic instances.
- WGC gold data gap always flagged for gold assets (known 501 issue).
- report_markdown = "" placeholder — real Markdown rendering built in Plan 03.
- data_as_of = datetime.now(timezone.utc) placeholder — refined in Plan 03.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from reasoning.app.nodes.state import (
    ReportState,
    ReportOutput,
    EntryQualityOutput,
    MacroRegimeOutput,
    ValuationOutput,
    StructureOutput,
    ConflictOutput,
)
from reasoning.app.pipeline.report_schema import (
    EntryQualityCard,
    MacroRegimeCard,
    ValuationCard,
    StructureCard,
    ConflictCard,
    ReportCard,
)

# WGC gold data gap — permanent warning for gold assets (HTTP 501 on central bank buying endpoint)
_WGC_GOLD_WARNING = (
    "DATA WARNING: WGC central bank buying data unavailable — "
    "gold valuation assessed without central bank demand context (HTTP 501)."
)


# ---------------------------------------------------------------------------
# Data warning collector
# ---------------------------------------------------------------------------


def _collect_data_warnings(state: dict) -> list[str]:
    """
    Collect all data quality and freshness warnings from the pipeline state.

    Sources (in collection order):
        1. retrieval_warnings — set during prefetch() by retrieval layer
        2. entry_quality_output.stale_data_caveat — stale data caveats from entry quality
        3. WGC gold data gap — always present for gold assets
        4. Node output .warnings lists (macro_regime, valuation, structure, conflict)

    Returns:
        Deduplicated list of warning strings (insertion-order preserved).
    """
    warnings: list[str] = []
    seen: set[str] = set()

    def _add(w: str) -> None:
        if w and w not in seen:
            warnings.append(w)
            seen.add(w)

    # 1. Retrieval warnings from prefetch layer
    for w in state.get("retrieval_warnings", []):
        _add(w)

    # 2. Stale data caveat from entry_quality_output
    entry_quality: EntryQualityOutput | None = state.get("entry_quality_output")
    if entry_quality and entry_quality.stale_data_caveat:
        _add(entry_quality.stale_data_caveat)

    # 3. WGC gold data gap — always flagged for gold assets
    asset_type = state.get("asset_type", "")
    if asset_type == "gold":
        _add(_WGC_GOLD_WARNING)

    # 4. Node output .warnings lists
    for output_key in ["macro_regime_output", "valuation_output", "structure_output"]:
        node_output = state.get(output_key)
        if node_output is not None:
            for w in getattr(node_output, "warnings", []):
                _add(w)

    conflict: ConflictOutput | None = state.get("conflict_output")
    if conflict is not None:
        for w in getattr(conflict, "warnings", []):
            _add(w)

    return warnings


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------


def _build_entry_quality_card(output: EntryQualityOutput) -> EntryQualityCard:
    return EntryQualityCard(
        tier=output.composite_tier,
        macro_assessment=output.macro_assessment,
        valuation_assessment=output.valuation_assessment,
        structure_assessment=output.structure_assessment,
        conflict_pattern=output.conflict_pattern,
        structure_veto_applied=output.structure_veto_applied,
        narrative=output.narrative,
    )


def _build_macro_regime_card(output: MacroRegimeOutput) -> MacroRegimeCard:
    # Dump regime_probabilities as list of plain dicts
    regime_probs = [p.model_dump() for p in output.regime_probabilities]
    return MacroRegimeCard(
        label=output.macro_label,
        top_confidence=output.top_confidence,
        is_mixed_signal=output.is_mixed_signal,
        regime_probabilities=regime_probs,
        narrative=output.narrative,
    )


def _build_valuation_card(output: ValuationOutput) -> ValuationCard:
    return ValuationCard(
        label=output.valuation_label,
        pe_ratio=output.pe_ratio,
        pb_ratio=output.pb_ratio,
        real_yield=output.real_yield,
        etf_flow_context=output.etf_flow_context,
        narrative=output.narrative,
    )


def _build_structure_card(output: StructureOutput) -> StructureCard:
    return StructureCard(
        label=output.structure_label,
        close=output.close,
        drawdown_from_ath=output.drawdown_from_ath,
        drawdown_from_52w_high=output.drawdown_from_52w_high,
        close_pct_rank=output.close_pct_rank,
        narrative=output.narrative,
    )


def _build_conflict_card(output: ConflictOutput) -> ConflictCard:
    return ConflictCard(
        pattern_name=output.pattern_name,
        severity=output.severity,
        tier_impact=output.tier_impact,
        narrative=output.narrative,
    )


# ---------------------------------------------------------------------------
# compose_report_node
# ---------------------------------------------------------------------------


def compose_report_node(state: ReportState) -> dict[str, Any]:
    """
    7th and final node in the LangGraph pipeline.

    Reads all upstream node outputs from state, assembles a structured ReportCard
    in conclusion-first order, and returns a ReportOutput for JSONB storage.

    Args:
        state: ReportState with all node outputs populated.

    Returns:
        dict with key "report_output" containing a ReportOutput instance.

    Report section order (conclusion-first):
        1. entry_quality — composite tier and assessment
        2. conflict — optional; present only when conflict_output is not None
        3. macro_regime — macro label and regime probabilities
        4. valuation — asset valuation context
        5. structure — price structure and technical positioning
    """
    language = state.get("language", "en")

    # Collect all data warnings
    data_warnings = _collect_data_warnings(state)

    # Build each card from corresponding node output
    entry_quality_output: EntryQualityOutput = state["entry_quality_output"]
    macro_regime_output: MacroRegimeOutput = state["macro_regime_output"]
    valuation_output: ValuationOutput = state["valuation_output"]
    structure_output: StructureOutput = state["structure_output"]
    conflict_output: ConflictOutput | None = state.get("conflict_output")

    entry_quality_card = _build_entry_quality_card(entry_quality_output)
    macro_regime_card = _build_macro_regime_card(macro_regime_output)
    valuation_card = _build_valuation_card(valuation_output)
    structure_card = _build_structure_card(structure_output)

    # Build conflict card only when conflict_output is present
    conflict_card = _build_conflict_card(conflict_output) if conflict_output is not None else None

    # Assemble ReportCard in conclusion-first order
    report_card = ReportCard(
        entry_quality=entry_quality_card,
        conflict=conflict_card,
        macro_regime=macro_regime_card,
        valuation=valuation_card,
        structure=structure_card,
        data_warnings=data_warnings,
        language=language,
    )

    # Serialize to flat dict using exclude_none=True — suitable for JSONB storage
    # No nested Pydantic instances in the result
    report_json = json.loads(report_card.model_dump_json(exclude_none=True))

    # Placeholder values — refined in Plan 03 (report_markdown) and Plan 03 (data_as_of)
    report_markdown = ""
    data_as_of = datetime.now(timezone.utc)

    report_output = ReportOutput(
        report_json=report_json,
        report_markdown=report_markdown,
        language=language,
        data_as_of=data_as_of,
        data_warnings=data_warnings,
        model_version="gemini-2.0-flash-001",
        warnings=[],
    )

    return {"report_output": report_output}
