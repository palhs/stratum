"""
reasoning/app/nodes/prompts.py — Shared prompt-building utilities for reasoning nodes.
Phase 6 | Plan 01 | Requirement: REAS-03

All functions are pure string-formatting utilities — no LLM calls.
Each formatter produces a concise, structured text block ready for injection
into an LLM system/human prompt.
"""

from __future__ import annotations

from reasoning.app.retrieval.types import (
    FredIndicatorRow,
    FundamentalsRow,
    GoldEtfRow,
    GoldPriceRow,
    RegimeAnalogue,
    StructureMarkerRow,
)


def format_fred_context(fred_rows: list[FredIndicatorRow]) -> str:
    """
    Format FRED macroeconomic indicator rows into a concise text block.

    Example output:
        FRED Macro Indicators (as of 2024-09-18):
          FEDFUNDS: 5.33  [monthly]
          UNRATE: 4.2  [monthly]
          CPIAUCSL: 314.796  [monthly]
    """
    if not fred_rows:
        return "FRED Macro Indicators: No data available."

    lines = ["FRED Macro Indicators:"]
    for row in fred_rows:
        as_of = row.data_as_of.strftime("%Y-%m-%d")
        lines.append(f"  {row.series_id}: {row.value}  [{row.frequency}] (as of {as_of})")
        if row.warnings:
            for w in row.warnings:
                lines.append(f"    WARNING: {w}")
    return "\n".join(lines)


def format_analogue_context(analogues: list[RegimeAnalogue]) -> str:
    """
    Format regime analogues into a concise text block with similarity scores.

    Example output:
        Historical Regime Analogues:
          [2008_crisis] 2008 Financial Crisis — similarity: 0.91
            Period: 2008-09 to 2009-03
            Dimensions: inflation, growth, credit_spread
            Narrative: Deep recession driven by housing collapse and credit freeze.
    """
    if not analogues:
        return "Historical Regime Analogues: None identified."

    lines = ["Historical Regime Analogues:"]
    for a in analogues:
        period = ""
        if a.period_start:
            period = f"{a.period_start}"
            if a.period_end:
                period += f" to {a.period_end}"
        dims = ", ".join(a.dimensions_matched) if a.dimensions_matched else "n/a"
        lines.append(f"  [{a.analogue_id}] {a.analogue_name} — similarity: {a.similarity_score:.2f}")
        if period:
            lines.append(f"    Period: {period}")
        lines.append(f"    Dimensions: {dims}")
        if a.narrative:
            lines.append(f"    Narrative: {a.narrative}")
        if a.warnings:
            for w in a.warnings:
                lines.append(f"    WARNING: {w}")
    return "\n".join(lines)


def format_structure_context(markers: list[StructureMarkerRow]) -> str:
    """
    Format price structure marker rows into a concise text block.

    Example output:
        Price Structure Markers — VHM (weekly, as of 2024-09-18):
          Close: 42500.0
          MA 10w: 41200.0 | MA 20w: 40100.0 | MA 50w: 38500.0
          Drawdown from ATH: -12.5% | Drawdown from 52w High: -8.3%
          Close Pct Rank: 0.72
    """
    if not markers:
        return "Price Structure Markers: No data available."

    lines = []
    for m in markers:
        as_of = m.data_as_of.strftime("%Y-%m-%d")
        lines.append(f"Price Structure Markers — {m.symbol} ({m.resolution}, as of {as_of}):")
        lines.append(f"  Asset type: {m.asset_type}")
        if m.close is not None:
            lines.append(f"  Close: {m.close}")
        else:
            lines.append("  Close: N/A")

        ma_parts = []
        for label, val in [("MA 10w", m.ma_10w), ("MA 20w", m.ma_20w), ("MA 50w", m.ma_50w)]:
            ma_parts.append(f"{label}: {val if val is not None else 'N/A'}")
        lines.append("  " + " | ".join(ma_parts))

        dd_ath = f"{m.drawdown_from_ath:.1%}" if m.drawdown_from_ath is not None else "N/A"
        dd_52w = f"{m.drawdown_from_52w_high:.1%}" if m.drawdown_from_52w_high is not None else "N/A"
        lines.append(f"  Drawdown from ATH: {dd_ath} | Drawdown from 52w High: {dd_52w}")

        rank = f"{m.close_pct_rank:.2f}" if m.close_pct_rank is not None else "N/A"
        pe_rank = f"{m.pe_pct_rank:.2f}" if m.pe_pct_rank is not None else "N/A"
        lines.append(f"  Close Pct Rank: {rank} | PE Pct Rank: {pe_rank}")

        if m.warnings:
            for w in m.warnings:
                lines.append(f"  WARNING: {w}")

    return "\n".join(lines)


def format_fundamentals_context(rows: list[FundamentalsRow]) -> str:
    """
    Format stock fundamentals rows into a concise text block.

    Example output:
        Fundamentals — VHM (annual, as of 2024-06-30):
          P/E: 12.4 | P/B: 1.8 | EPS: 3420.0
          ROE: 14.2% | ROA: 4.1%
          Revenue Growth: 18.5% | Net Margin: 11.2%
          Market Cap: 85000000000
    """
    if not rows:
        return "Fundamentals: No data available."

    lines = []
    for r in rows:
        as_of = r.data_as_of.strftime("%Y-%m-%d")
        lines.append(f"Fundamentals — {r.symbol} ({r.period_type}, as of {as_of}):")

        pe = f"{r.pe_ratio:.1f}" if r.pe_ratio is not None else "N/A"
        pb = f"{r.pb_ratio:.1f}" if r.pb_ratio is not None else "N/A"
        eps = f"{r.eps:.1f}" if r.eps is not None else "N/A"
        lines.append(f"  P/E: {pe} | P/B: {pb} | EPS: {eps}")

        roe = f"{r.roe:.1%}" if r.roe is not None else "N/A"
        roa = f"{r.roa:.1%}" if r.roa is not None else "N/A"
        lines.append(f"  ROE: {roe} | ROA: {roa}")

        rev_g = f"{r.revenue_growth:.1%}" if r.revenue_growth is not None else "N/A"
        net_m = f"{r.net_margin:.1%}" if r.net_margin is not None else "N/A"
        lines.append(f"  Revenue Growth: {rev_g} | Net Margin: {net_m}")

        if r.market_cap is not None:
            lines.append(f"  Market Cap: {r.market_cap:,.0f}")

        if r.warnings:
            for w in r.warnings:
                lines.append(f"  WARNING: {w}")

    return "\n".join(lines)


def format_gold_context(
    price_rows: list[GoldPriceRow],
    etf_rows: list[GoldEtfRow],
) -> str:
    """
    Format gold price and ETF rows into a concise text block.

    Example output:
        Gold Price (as of 2024-09-18):
          LBMA: 2580.00 USD/oz
        Gold ETF (GLD weekly, as of 2024-09-18):
          Close: 238.50 | Volume: 15420000
    """
    lines = []

    if price_rows:
        lines.append("Gold Price:")
        for r in price_rows:
            as_of = r.data_as_of.strftime("%Y-%m-%d")
            lines.append(f"  {r.source}: {r.price_usd:.2f} USD/oz (as of {as_of})")
            if r.warnings:
                for w in r.warnings:
                    lines.append(f"  WARNING: {w}")
    else:
        lines.append("Gold Price: No data available.")

    if etf_rows:
        lines.append("Gold ETF Data:")
        for r in etf_rows:
            as_of = r.data_as_of.strftime("%Y-%m-%d")
            vol = f"{r.volume:,}" if r.volume is not None else "N/A"
            lines.append(
                f"  {r.ticker} ({r.resolution}, as of {as_of}): "
                f"Close {r.close:.2f} | Volume {vol}"
            )
            if r.warnings:
                for w in r.warnings:
                    lines.append(f"  WARNING: {w}")
    else:
        lines.append("Gold ETF Data: No data available.")

    return "\n".join(lines)
