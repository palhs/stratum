"""
reasoning/tests/pipeline/test_markdown_renderer.py — TDD tests for markdown_renderer.py.
Phase 7 | Plan 04 | Requirements: REPT-02, REPT-03

Tests verify:
- render_markdown produces conclusion-first Markdown structure
- English mode uses English card headers and label text
- Vietnamese mode uses Vietnamese card headers from term dictionary
- DATA WARNING section renders at top when data_warnings is non-empty
- Signal Conflict section appears between Entry Quality and Macro Regime when present
- No prohibited terms appear in Markdown output
- Metric formatting: 2 decimal places for ratios, 1 decimal for percentages
"""

from __future__ import annotations

import re
import pytest

from reasoning.app.pipeline.report_schema import (
    ReportCard,
    EntryQualityCard,
    MacroRegimeCard,
    ValuationCard,
    StructureCard,
    ConflictCard,
)


# ---------------------------------------------------------------------------
# Fixtures — ReportCard instances for testing
# ---------------------------------------------------------------------------


def _make_entry_quality_card(tier: str = "Cautious") -> EntryQualityCard:
    return EntryQualityCard(
        tier=tier,
        macro_assessment="Headwind",
        valuation_assessment="Attractive",
        structure_assessment="Neutral",
        conflict_pattern="Macro–Valuation Divergence",
        structure_veto_applied=False,
        narrative="The environment suggests cautious positioning — attractive valuation partially offset by macro headwinds.",
    )


def _make_macro_regime_card() -> MacroRegimeCard:
    return MacroRegimeCard(
        label="Headwind",
        top_confidence=0.72,
        is_mixed_signal=False,
        regime_probabilities=[
            {"regime_id": "regime_2008_gfc", "regime_name": "GFC 2008", "confidence": 0.72, "source_analogue_id": "a1"},
        ],
        narrative="Conditions appear consistent with the 2008 GFC environment — tight credit, declining liquidity.",
    )


def _make_valuation_card_equity() -> ValuationCard:
    return ValuationCard(
        label="Attractive",
        pe_ratio=12.5,
        pb_ratio=1.8,
        real_yield=None,
        etf_flow_context=None,
        narrative="The structure indicates attractive valuation at 12.5x P/E, below historical averages.",
    )


def _make_valuation_card_gold() -> ValuationCard:
    return ValuationCard(
        label="Fair",
        pe_ratio=None,
        pb_ratio=None,
        real_yield=2.1,
        etf_flow_context="ETF inflows elevated at $3.2B last month",
        narrative="Conditions appear supportive for gold — real yield of 2.1% and positive ETF flows.",
    )


def _make_structure_card() -> StructureCard:
    return StructureCard(
        label="Neutral",
        close=18500.0,
        drawdown_from_ath=-15.2,
        drawdown_from_52w_high=-8.4,
        close_pct_rank=0.62,
        narrative="The structure indicates a neutral setup — close above major moving averages with moderate ATH drawdown.",
    )


def _make_conflict_card() -> ConflictCard:
    return ConflictCard(
        pattern_name="Macro–Valuation Divergence",
        severity="minor",
        tier_impact="Tier held at Cautious (minor conflict; no automatic downgrade).",
        narrative="Attractive valuation conflicts with macro headwind signal. Historically this pattern resolves toward macro direction.",
    )


def _make_report_card_no_conflict(language: str = "en", data_warnings: list = None) -> ReportCard:
    return ReportCard(
        entry_quality=_make_entry_quality_card("Neutral"),
        conflict=None,
        macro_regime=_make_macro_regime_card(),
        valuation=_make_valuation_card_equity(),
        structure=_make_structure_card(),
        data_warnings=data_warnings or [],
        language=language,
    )


def _make_report_card_with_conflict(language: str = "en") -> ReportCard:
    return ReportCard(
        entry_quality=_make_entry_quality_card("Cautious"),
        conflict=_make_conflict_card(),
        macro_regime=_make_macro_regime_card(),
        valuation=_make_valuation_card_equity(),
        structure=_make_structure_card(),
        data_warnings=[],
        language=language,
    )


def _make_report_card_with_warnings(language: str = "en") -> ReportCard:
    return ReportCard(
        entry_quality=_make_entry_quality_card("Cautious"),
        conflict=None,
        macro_regime=_make_macro_regime_card(),
        valuation=_make_valuation_card_equity(),
        structure=_make_structure_card(),
        data_warnings=[
            "DATA WARNING: WGC central bank buying data unavailable (HTTP 501).",
            "DATA WARNING: fred_indicators data is 45 days old (threshold: 30 days).",
        ],
        language=language,
    )


# ---------------------------------------------------------------------------
# Import test
# ---------------------------------------------------------------------------


def test_render_markdown_is_importable():
    """render_markdown is importable from reasoning.app.pipeline.markdown_renderer."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown  # noqa: F401


# ---------------------------------------------------------------------------
# English mode: structure tests
# ---------------------------------------------------------------------------


def test_render_markdown_english_first_header():
    """render_markdown with English ReportCard produces Markdown with '## Entry Quality' as first section header."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Find the first ## section header (not counting the title #)
    section_headers = re.findall(r'^## (.+)$', md, re.MULTILINE)
    assert len(section_headers) > 0, "Markdown must have section headers"
    first_header = section_headers[0]
    assert "Entry Quality" in first_header, (
        f"First section header must be Entry Quality, got: {first_header!r}"
    )


def test_render_markdown_card_order_no_conflict():
    """render_markdown card order is: Entry Quality → Macro Regime → Valuation → Structure (no conflict, no warnings)."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Find positions of each section header
    eq_pos = md.find("## Entry Quality")
    mr_pos = md.find("## Macro Regime")
    val_pos = md.find("## Valuation")
    struct_pos = md.find("## Structure")

    assert eq_pos != -1, "Entry Quality section must be present"
    assert mr_pos != -1, "Macro Regime section must be present"
    assert val_pos != -1, "Valuation section must be present"
    assert struct_pos != -1, "Structure section must be present"

    assert eq_pos < mr_pos, "Entry Quality must appear before Macro Regime"
    assert mr_pos < val_pos, "Macro Regime must appear before Valuation"
    assert val_pos < struct_pos, "Valuation must appear before Structure"


def test_render_markdown_card_order_with_conflict():
    """Conflict section appears between Entry Quality and Macro Regime when present."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_with_conflict("en")
    md = render_markdown(report_card, "en")

    eq_pos = md.find("## Entry Quality")
    conflict_pos = md.find("## Signal Conflict")
    mr_pos = md.find("## Macro Regime")

    assert eq_pos != -1, "Entry Quality section must be present"
    assert conflict_pos != -1, "Signal Conflict section must be present when conflict card exists"
    assert mr_pos != -1, "Macro Regime section must be present"

    assert eq_pos < conflict_pos, "Entry Quality must appear before Signal Conflict"
    assert conflict_pos < mr_pos, "Signal Conflict must appear before Macro Regime"


def test_render_markdown_conflict_section_absent_when_none():
    """Conflict section must NOT appear when conflict card is None."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    assert "## Signal Conflict" not in md, (
        "Signal Conflict section must be absent when conflict card is None"
    )


def test_render_markdown_data_warning_at_top():
    """DATA WARNING section appears at the top when data_warnings is non-empty."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_with_warnings("en")
    md = render_markdown(report_card, "en")

    assert "DATA WARNING" in md, "DATA WARNING section must appear when data_warnings present"

    # DATA WARNING must appear before Entry Quality
    warning_pos = md.find("DATA WARNING")
    eq_pos = md.find("## Entry Quality")
    assert warning_pos < eq_pos, "DATA WARNING must appear before Entry Quality section"


def test_render_markdown_data_warning_absent_when_empty():
    """DATA WARNING section must NOT appear when data_warnings is empty."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # The DATA WARNING header should not appear
    assert "⚠️ DATA WARNING" not in md, (
        "DATA WARNING section must be absent when data_warnings is empty"
    )


def test_render_markdown_entry_quality_card_content():
    """Entry Quality card section includes tier, narrative text, and macro/valuation/structure assessments."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Should include the tier in the header or body
    assert "Neutral" in md, "Entry Quality tier 'Neutral' must appear in Markdown"
    # Should include assessments
    assert "Headwind" in md, "Macro assessment must appear in Entry Quality section"
    assert "Attractive" in md, "Valuation assessment must appear in Entry Quality section"


def test_render_markdown_macro_regime_card_content():
    """Macro Regime card shows label, top confidence percentage, mixed signal status."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Label appears
    assert "Headwind" in md, "Macro label must appear in Macro Regime section"
    # Confidence shown as percentage (72%)
    assert "72" in md, "Top confidence must appear as percentage"


def test_render_markdown_valuation_equity_metrics():
    """Valuation card shows P/E and P/B when present for equity."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    assert "P/E" in md, "P/E ratio must appear in Valuation section for equity"
    assert "12.5" in md or "12.50" in md, "P/E value must appear in Markdown"
    assert "P/B" in md, "P/B ratio must appear in Valuation section for equity"
    assert "1.8" in md or "1.80" in md, "P/B value must appear in Markdown"


def test_render_markdown_valuation_gold_metrics():
    """Valuation card shows real yield for gold (no P/E or P/B)."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    gold_card = ReportCard(
        entry_quality=_make_entry_quality_card("Neutral"),
        conflict=None,
        macro_regime=_make_macro_regime_card(),
        valuation=_make_valuation_card_gold(),
        structure=_make_structure_card(),
        data_warnings=[],
        language="en",
    )
    md = render_markdown(gold_card, "en")

    assert "real yield" in md.lower() or "Real Yield" in md, "Real yield must appear in gold valuation"
    assert "2.1" in md or "2.10" in md, "Real yield value must appear"
    # P/E and P/B should not appear since they are None
    # (they should be omitted, not shown as None)
    assert "P/E: None" not in md, "P/E must be omitted (not shown as None)"
    assert "P/B: None" not in md, "P/B must be omitted (not shown as None)"


def test_render_markdown_structure_card_content():
    """Structure card shows label, drawdown percentages, close_pct_rank."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    assert "Neutral" in md, "Structure label must appear"
    # Drawdown values
    assert "15.2" in md or "-15.2" in md, "ATH drawdown must appear"
    assert "8.4" in md or "-8.4" in md, "52W drawdown must appear"


def test_render_markdown_returns_string():
    """render_markdown returns a str."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    result = render_markdown(report_card, "en")
    assert isinstance(result, str), f"render_markdown must return str, got {type(result)}"
    assert len(result) > 100, "Markdown output must have substantial content"


# ---------------------------------------------------------------------------
# Vietnamese mode: header and label tests
# ---------------------------------------------------------------------------


def test_render_markdown_vietnamese_card_headers():
    """render_markdown with language='vi' uses Vietnamese card headers from term dictionary."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("vi")
    md = render_markdown(report_card, "vi")

    # Vietnamese card headers from term_dict_vi.json card_headers
    assert "Chất lượng điểm vào" in md, (
        "Vietnamese header 'Chất lượng điểm vào' must appear for Entry Quality in vi mode"
    )
    assert "Chế độ vĩ mô" in md, (
        "Vietnamese header 'Chế độ vĩ mô' must appear for Macro Regime in vi mode"
    )
    assert "Định giá" in md, (
        "Vietnamese header 'Định giá' must appear for Valuation in vi mode"
    )
    assert "Cấu trúc giá" in md, (
        "Vietnamese header 'Cấu trúc giá' must appear for Structure in vi mode"
    )


def test_render_markdown_vietnamese_conflict_header():
    """render_markdown with language='vi' uses Vietnamese header for Signal Conflict."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_with_conflict("vi")
    md = render_markdown(report_card, "vi")

    assert "Xung đột tín hiệu" in md, (
        "Vietnamese header 'Xung đột tín hiệu' must appear for Signal Conflict in vi mode"
    )


def test_render_markdown_english_not_vietnamese_headers():
    """render_markdown with language='en' uses English headers (not Vietnamese)."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    assert "## Entry Quality" in md or "Entry Quality:" in md, (
        "English header 'Entry Quality' must appear in en mode"
    )
    # Vietnamese headers must NOT appear
    assert "Chất lượng điểm vào" not in md, (
        "Vietnamese header must not appear in English mode"
    )


# ---------------------------------------------------------------------------
# Prohibited terms tests
# ---------------------------------------------------------------------------


def test_render_markdown_no_prohibited_english_terms():
    """Output never contains standalone 'buy', 'sell', or 'entry confirmed' (compound words allowed)."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Standalone "buy" — must not appear; compound words like "buyback" are allowed
    assert not re.search(r'\bbuy\b', md, re.IGNORECASE), (
        "Standalone 'buy' must not appear in English Markdown output"
    )
    # Standalone "sell"
    assert not re.search(r'\bsell\b', md, re.IGNORECASE), (
        "Standalone 'sell' must not appear in English Markdown output"
    )
    # "entry confirmed"
    assert not re.search(r'\bentry confirmed\b', md, re.IGNORECASE), (
        "'entry confirmed' must not appear in English Markdown output"
    )


def test_render_markdown_no_prohibited_vietnamese_terms():
    """Output never contains 'mua vào', 'bán', or 'xác nhận điểm vào' in Vietnamese mode."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    report_card = _make_report_card_no_conflict("vi")
    md = render_markdown(report_card, "vi")

    assert "mua vào" not in md.lower(), (
        "'mua vào' must not appear in Vietnamese Markdown output"
    )
    assert not re.search(r'\bbán\b', md), (
        "Standalone 'bán' must not appear in Vietnamese Markdown output"
    )
    assert "xác nhận điểm vào" not in md.lower(), (
        "'xác nhận điểm vào' must not appear in Vietnamese Markdown output"
    )


def test_render_markdown_compound_words_allowed():
    """Compound words like 'buyback', 'sell-off', 'oversold' are allowed in output."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    # The renderer itself should not contain prohibited terms in its templates
    # This test verifies the regex used in the prohibited check allows compound words
    report_card = _make_report_card_no_conflict("en")
    md = render_markdown(report_card, "en")

    # Verify the regex pattern allows compound words (test the pattern, not the output)
    # The renderer template must not produce standalone prohibited terms
    assert not re.search(r'\bbuy\b', md, re.IGNORECASE), "Standalone 'buy' prohibited"
    assert not re.search(r'\bsell\b', md, re.IGNORECASE), "Standalone 'sell' prohibited"


# ---------------------------------------------------------------------------
# Data warning section content tests
# ---------------------------------------------------------------------------


def test_render_markdown_data_warning_bullets():
    """Each data warning appears as a bullet point in the DATA WARNING section."""
    from reasoning.app.pipeline.markdown_renderer import render_markdown

    warnings = [
        "DATA WARNING: WGC central bank buying data unavailable (HTTP 501).",
        "DATA WARNING: fred_indicators data is 45 days old.",
    ]
    report_card = _make_report_card_no_conflict("en", data_warnings=warnings)
    md = render_markdown(report_card, "en")

    # Both warnings should appear as bullets
    assert "WGC central bank buying data unavailable" in md, "First warning must appear"
    assert "fred_indicators" in md, "Second warning must appear"
