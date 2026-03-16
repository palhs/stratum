"""
reasoning/app/pipeline/markdown_renderer.py — Markdown report renderer.
Phase 7 | Plan 04 | Requirements: REPT-02, REPT-03

Implements:
    render_markdown(report_card, language) -> str
        Produces a human-readable Markdown string with conclusion-first card ordering.

Design decisions (locked):
- f-string templates only (no Jinja2) — no conditional logic requiring Jinja2.
- Conclusion-first ordering: DATA WARNING (if any) → Entry Quality → Signal Conflict
  (if present) → Macro Regime → Valuation → Structure.
- Card headers: Vietnamese headers loaded from load_term_dict()["card_headers"] if vi.
- Labels in section body: rendered as-is from the ReportCard (apply_terms was already
  applied by compose_report_node for Vietnamese before calling render_markdown).
- Metric formatting: 2 decimal places for ratios (P/E, P/B, real_yield),
  percentages with 1 decimal place.
- Optional metrics omitted entirely when value is None.
- Prohibited terms must never appear in template strings:
    English: 'buy' (standalone), 'sell' (standalone), 'entry confirmed'
    Vietnamese: 'mua vào', 'bán' (standalone), 'xác nhận điểm vào'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from reasoning.app.pipeline.report_schema import ReportCard
from reasoning.app.pipeline.term_dict import load_term_dict


# ---------------------------------------------------------------------------
# English card headers (canonical)
# ---------------------------------------------------------------------------

_EN_HEADERS = {
    "Entry Quality": "Entry Quality",
    "Signal Conflict": "Signal Conflict",
    "Macro Regime": "Macro Regime",
    "Valuation": "Valuation",
    "Structure": "Structure",
    "Data Warning": "DATA WARNING",
}


def _get_headers(language: str) -> dict[str, str]:
    """Return card header strings for the given language."""
    if language == "vi":
        td = load_term_dict()
        vi_headers = td.get("card_headers", {})
        return {
            "Entry Quality": vi_headers.get("Entry Quality", "Entry Quality"),
            "Signal Conflict": vi_headers.get("Signal Conflict", "Signal Conflict"),
            "Macro Regime": vi_headers.get("Macro Regime", "Macro Regime"),
            "Valuation": vi_headers.get("Valuation", "Valuation"),
            "Structure": vi_headers.get("Structure", "Structure"),
            "Data Warning": vi_headers.get("Data Warning", "CẢNH BÁO DỮ LIỆU"),
        }
    return _EN_HEADERS.copy()


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _fmt_pct(value: float) -> str:
    """Format a 0.0–1.0 confidence as percentage with 1 decimal place."""
    return f"{value * 100:.1f}%"


def _fmt_ratio(value: float) -> str:
    """Format a ratio with 2 decimal places."""
    return f"{value:.2f}"


def _fmt_drawdown(value: float) -> str:
    """Format a drawdown percentage with 1 decimal place."""
    return f"{value:.1f}%"


def _render_data_warning_section(data_warnings: list[str], header: str) -> str:
    if not data_warnings:
        return ""
    bullets = "\n".join(f"- {w}" for w in data_warnings)
    return f"## ⚠️ {header}\n\n{bullets}\n\n---\n\n"


def _render_entry_quality_section(report_card: ReportCard, header: str) -> str:
    eq = report_card.entry_quality
    tier = eq.tier
    narrative = eq.narrative
    macro_assessment = eq.macro_assessment
    valuation_assessment = eq.valuation_assessment
    structure_assessment = eq.structure_assessment

    lines = [
        f"## {header}: {tier}",
        "",
        f"**Assessment:** {narrative}",
        f"- Macro: {macro_assessment}",
        f"- Valuation: {valuation_assessment}",
        f"- Structure: {structure_assessment}",
    ]

    if eq.conflict_pattern:
        lines.append(f"- Conflict: {eq.conflict_pattern}")

    if eq.structure_veto_applied:
        lines.append("- *Structure veto applied — tier capped by price structure.*")

    lines.extend(["", "---", ""])
    return "\n".join(lines) + "\n"


def _render_conflict_section(report_card: ReportCard, header: str) -> str:
    conflict = report_card.conflict
    if conflict is None:
        return ""

    lines = [
        f"## {header}: {conflict.pattern_name} ({conflict.severity})",
        "",
        f"**Impact:** {conflict.tier_impact}",
        "",
        conflict.narrative,
        "",
        "---",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_macro_regime_section(report_card: ReportCard, header: str) -> str:
    mr = report_card.macro_regime
    label = mr.label
    confidence_pct = f"{mr.top_confidence * 100:.1f}"
    mixed_label = "Yes" if mr.is_mixed_signal else "No"

    lines = [
        f"## {header}: {label}",
        "",
        f"**Confidence:** {confidence_pct}% | Mixed Signal: {mixed_label}",
        "",
        mr.narrative,
        "",
        "---",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_valuation_section(report_card: ReportCard, header: str) -> str:
    val = report_card.valuation
    label = val.label

    lines = [
        f"## {header}: {label}",
        "",
    ]

    # Equity metrics
    if val.pe_ratio is not None:
        lines.append(f"- P/E: {_fmt_ratio(val.pe_ratio)}x")
    if val.pb_ratio is not None:
        lines.append(f"- P/B: {_fmt_ratio(val.pb_ratio)}x")

    # Gold metrics
    if val.real_yield is not None:
        lines.append(f"- Real Yield: {_fmt_ratio(val.real_yield)}%")
    if val.etf_flow_context is not None:
        lines.append(f"- ETF Flows: {val.etf_flow_context}")

    lines.extend([
        "",
        val.narrative,
        "",
        "---",
        "",
    ])
    return "\n".join(lines) + "\n"


def _render_structure_section(report_card: ReportCard, header: str) -> str:
    struct = report_card.structure
    label = struct.label

    lines = [
        f"## {header}: {label}",
        "",
    ]

    if struct.drawdown_from_ath is not None:
        lines.append(f"- Drawdown from ATH: {_fmt_drawdown(struct.drawdown_from_ath)}")
    if struct.drawdown_from_52w_high is not None:
        lines.append(f"- Drawdown from 52W High: {_fmt_drawdown(struct.drawdown_from_52w_high)}")
    if struct.close_pct_rank is not None:
        lines.append(f"- Close Percentile Rank: {_fmt_pct(struct.close_pct_rank)}")
    if struct.close is not None:
        lines.append(f"- Close: {struct.close:.2f}")

    lines.extend([
        "",
        struct.narrative,
        "",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_markdown(report_card: ReportCard, language: str) -> str:
    """
    Produce a human-readable Markdown report from a ReportCard.

    Args:
        report_card: Assembled ReportCard in conclusion-first order.
        language:    'en' for English, 'vi' for Vietnamese.
                     For Vietnamese, labels in report_card must already be
                     translated (apply_terms called by compose_report_node before
                     this function).

    Returns:
        Markdown string. Card order:
            1. Report title and metadata
            2. DATA WARNING (if data_warnings is non-empty)
            3. Entry Quality
            4. Signal Conflict (if conflict card present)
            5. Macro Regime
            6. Valuation
            7. Structure

    Prohibited terms (never appear in template):
        English: standalone 'buy', 'sell', 'entry confirmed'
        Vietnamese: 'mua vào', 'bán', 'xác nhận điểm vào'
    """
    headers = _get_headers(language)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lang_display = "Vietnamese" if language == "vi" else "English"

    # Title and metadata block
    title_block = (
        f"# Analysis Report\n\n"
        f"> Generated: {now} | Language: {lang_display}\n\n"
        f"---\n\n"
    )

    # DATA WARNING section (rendered at top)
    data_warning_section = _render_data_warning_section(
        report_card.data_warnings,
        headers["Data Warning"],
    )

    # Entry Quality section (conclusion-first)
    entry_quality_section = _render_entry_quality_section(
        report_card,
        headers["Entry Quality"],
    )

    # Signal Conflict section (optional, between Entry Quality and Macro Regime)
    conflict_section = _render_conflict_section(
        report_card,
        headers["Signal Conflict"],
    )

    # Macro Regime section
    macro_regime_section = _render_macro_regime_section(
        report_card,
        headers["Macro Regime"],
    )

    # Valuation section
    valuation_section = _render_valuation_section(
        report_card,
        headers["Valuation"],
    )

    # Structure section (last)
    structure_section = _render_structure_section(
        report_card,
        headers["Structure"],
    )

    return (
        title_block
        + data_warning_section
        + entry_quality_section
        + conflict_section
        + macro_regime_section
        + valuation_section
        + structure_section
    )
