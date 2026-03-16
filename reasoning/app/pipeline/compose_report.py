"""
reasoning/app/pipeline/compose_report.py — compose_report_node: 7th and final graph node.
Phase 7 | Plan 04 | Requirements: REPT-01, REPT-02, REPT-03, REPT-04

Implements:
    compose_report_node(state) — reads all upstream node outputs and produces a structured
                                 ReportOutput with flat card objects in conclusion-first order,
                                 full Markdown output, and bilingual support.
    _collect_data_warnings(state) — collects freshness/data-quality warnings from all sources.
    _rewrite_narrative_vi(english_narrative, card_type, metrics, term_dict) — re-generates
                                 a card's narrative in Vietnamese using Gemini (gemini-2.5-pro).

Design decisions (locked):
- Conclusion-first ordering: entry_quality → conflict (optional) → macro_regime → valuation → structure.
- report_json uses json.loads(card.model_dump_json(exclude_none=True)) — flat dict, no Pydantic instances.
- WGC gold data gap always flagged for gold assets (known 501 issue).
- For language='vi':
    1. Each card's narrative is re-generated in Vietnamese by Gemini (gemini-2.5-pro).
       This is a fresh generation from the English narrative, not label substitution.
    2. report_json has apply_terms() applied for structured label fields (tier, label, etc.).
    3. render_markdown is called with the Vietnamese-narrative ReportCard.
- For language='en':
    - English narratives from Phase 6 nodes pass through unchanged — no Gemini call.
    - term dictionary NOT applied — labels stay English.
- data_as_of computed from earliest data_as_of timestamp in retrieval rows (fallback: datetime.now(UTC)).
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
from reasoning.app.pipeline.markdown_renderer import render_markdown
from reasoning.app.pipeline.term_dict import apply_terms, load_term_dict

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
# Vietnamese narrative re-generation (synchronous — one call per card)
# ---------------------------------------------------------------------------


def _rewrite_narrative_vi(
    english_narrative: str,
    card_type: str,
    metrics: dict,
    term_dict: dict,
) -> str:
    """
    Re-generate a card's narrative in Vietnamese using Gemini (gemini-2.5-pro).

    This produces a genuine Vietnamese narrative from the English source — it is NOT
    simple label substitution.  The Gemini call receives the English narrative as
    reference material plus key metrics and a prohibited terms list.

    Args:
        english_narrative: The English narrative string from the Phase 6 node.
        card_type:         Card identifier, e.g. "entry_quality", "macro_regime".
        metrics:           Key metrics dict to provide context to Gemini.
        term_dict:         Vietnamese term dictionary (for financial context).

    Returns:
        Vietnamese narrative string generated by Gemini.  Falls back to the
        original English narrative if the Gemini call fails.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            temperature=0.2,
        )

        prompt = f"""Rewrite the following financial analysis narrative in Vietnamese.

Card type: {card_type}
English narrative: {english_narrative}
Key metrics: {json.dumps(metrics, ensure_ascii=False)}

Rules:
- Write naturally in Vietnamese financial language
- Keep English abbreviations inline: P/E, ATH, ETF, P/B, MA, RSI, FOMC, SBV, GDP, CPI, etc.
- NEVER use: 'mua', 'bán', 'xác nhận điểm vào'
- Use assessment language: 'môi trường cho thấy', 'điều kiện dường như', 'cấu trúc cho thấy'
- 3-5 sentences, matching the depth of the English narrative
- Do not add information not present in the English narrative
- Return only the Vietnamese narrative text, no explanation
"""

        response = model.invoke([HumanMessage(content=prompt)])
        return response.content.strip()

    except Exception:
        # Graceful degradation — return English narrative if Gemini fails
        return english_narrative


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
# data_as_of computation
# ---------------------------------------------------------------------------


def _compute_data_as_of(state: dict) -> datetime:
    """
    Compute data_as_of from the earliest data_as_of timestamp found in retrieval rows.

    Iterates all retrieval row lists in state; collects any data_as_of fields;
    returns the minimum (earliest) as a UTC-aware datetime.

    Falls back to datetime.now(UTC) if no timestamps found.
    """
    timestamps: list[datetime] = []

    row_keys = [
        "fred_rows", "regime_analogues", "macro_docs",
        "fundamentals_rows", "structure_marker_rows",
        "gold_price_rows", "gold_etf_rows", "earnings_docs",
    ]

    for key in row_keys:
        rows = state.get(key) or []
        for row in rows:
            ts = getattr(row, "data_as_of", None)
            if ts is not None and isinstance(ts, datetime):
                # Normalize to UTC-aware
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                timestamps.append(ts)

    if timestamps:
        return min(timestamps)

    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# compose_report_node
# ---------------------------------------------------------------------------


def compose_report_node(state: ReportState) -> dict[str, Any]:
    """
    7th and final node in the LangGraph pipeline.

    Reads all upstream node outputs from state, assembles a structured ReportCard
    in conclusion-first order, and returns a ReportOutput with both JSON and Markdown.

    For language='vi':
        - Each card's narrative is re-generated in Vietnamese by Gemini (gemini-2.5-pro).
        - report_json has apply_terms() applied for structured label fields.
        - report_markdown uses Vietnamese card headers.

    For language='en':
        - English narratives pass through unchanged — no Gemini call.
        - term dictionary NOT applied — labels stay English.
        - report_markdown uses English card headers.

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

    # ---------------------------------------------------------------------------
    # Bilingual processing
    # ---------------------------------------------------------------------------

    if language == "vi":
        # Load term dictionary for context
        td = load_term_dict()

        # 1. Re-generate each card's narrative in Vietnamese via Gemini
        #    One call per card; replace narrative field on the card object.

        # Entry quality
        eq_metrics = {
            "tier": entry_quality_card.tier,
            "macro_assessment": entry_quality_card.macro_assessment,
            "valuation_assessment": entry_quality_card.valuation_assessment,
            "structure_assessment": entry_quality_card.structure_assessment,
        }
        entry_quality_card.narrative = _rewrite_narrative_vi(
            entry_quality_card.narrative, "entry_quality", eq_metrics, td
        )

        # Macro regime
        mr_metrics = {
            "label": macro_regime_card.label,
            "top_confidence": macro_regime_card.top_confidence,
            "is_mixed_signal": macro_regime_card.is_mixed_signal,
        }
        macro_regime_card.narrative = _rewrite_narrative_vi(
            macro_regime_card.narrative, "macro_regime", mr_metrics, td
        )

        # Valuation
        val_metrics: dict[str, Any] = {"label": valuation_card.label}
        if valuation_card.pe_ratio is not None:
            val_metrics["pe_ratio"] = valuation_card.pe_ratio
        if valuation_card.pb_ratio is not None:
            val_metrics["pb_ratio"] = valuation_card.pb_ratio
        if valuation_card.real_yield is not None:
            val_metrics["real_yield"] = valuation_card.real_yield
        valuation_card.narrative = _rewrite_narrative_vi(
            valuation_card.narrative, "valuation", val_metrics, td
        )

        # Structure
        struct_metrics: dict[str, Any] = {"label": structure_card.label}
        if structure_card.drawdown_from_ath is not None:
            struct_metrics["drawdown_from_ath"] = structure_card.drawdown_from_ath
        if structure_card.close_pct_rank is not None:
            struct_metrics["close_pct_rank"] = structure_card.close_pct_rank
        structure_card.narrative = _rewrite_narrative_vi(
            structure_card.narrative, "structure", struct_metrics, td
        )

        # Conflict card (if present)
        if conflict_card is not None:
            conf_metrics = {
                "pattern_name": conflict_card.pattern_name,
                "severity": conflict_card.severity,
            }
            conflict_card.narrative = _rewrite_narrative_vi(
                conflict_card.narrative, "conflict", conf_metrics, td
            )

        # 2. Rebuild ReportCard with Vietnamese narratives (card objects mutated above)
        report_card = ReportCard(
            entry_quality=entry_quality_card,
            conflict=conflict_card,
            macro_regime=macro_regime_card,
            valuation=valuation_card,
            structure=structure_card,
            data_warnings=data_warnings,
            language=language,
        )

        # 3. Serialize to flat dict
        report_json = json.loads(report_card.model_dump_json(exclude_none=True))

        # 4. Apply term dictionary for structured labels (tier, label, pattern_name)
        report_json = apply_terms(report_json)

    else:
        # English: serialize directly — narratives and labels pass through unchanged
        report_json = json.loads(report_card.model_dump_json(exclude_none=True))

    # ---------------------------------------------------------------------------
    # Markdown rendering
    # ---------------------------------------------------------------------------

    # For Vietnamese: render_markdown uses the report_card with Vietnamese narratives.
    # Labels in report_card are still English at this point — apply_terms was on report_json
    # (the dict), not the Pydantic model. The Markdown renderer uses card headers from
    # term_dict for Vietnamese, and renders narrative text directly from the card.
    report_markdown = render_markdown(report_card, language)

    # ---------------------------------------------------------------------------
    # data_as_of computation
    # ---------------------------------------------------------------------------

    data_as_of = _compute_data_as_of(state)

    report_output = ReportOutput(
        report_json=report_json,
        report_markdown=report_markdown,
        language=language,
        data_as_of=data_as_of,
        data_warnings=data_warnings,
        model_version="gemini-2.5-pro",
        warnings=[],
    )

    return {"report_output": report_output}
