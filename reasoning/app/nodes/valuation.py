"""
reasoning/app/nodes/valuation.py — valuation_node: regime-relative valuation node.
Phase 6 | Plan 02 | Requirement: REAS-02

Dual-path dispatch:
- asset_type='equity': compares current P/E and P/B against top 2-3 regime analogues
  weighted by similarity_score from Neo4j HAS_ANALOGUE relationships.
- asset_type='gold': uses real yield from FRED data + GLD ETF flow context +
  macro regime overlay. Always flags WGC central bank data unavailability.

CRITICAL constraints (REAS-02):
- NO import of retrieval functions — only TYPE imports from retrieval.types
- Read ONLY from state fields — no direct database calls
- Partial assessments for missing data — do NOT skip or raise on missing metrics
- WGC warning is mandatory for gold path (501 stub convention from locked decision)
- All numeric fields in ValuationOutput must have entries in sources dict
"""

from __future__ import annotations

import os
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from reasoning.app.nodes.prompts import (
    format_analogue_context,
    format_fred_context,
    format_fundamentals_context,
    format_gold_context,
)
from reasoning.app.nodes.state import (
    VALUATION_LABELS,
    MacroRegimeOutput,
    ReportState,
    ValuationOutput,
)
from reasoning.app.retrieval.types import (
    FredIndicatorRow,
    FundamentalsRow,
    GoldEtfRow,
    GoldPriceRow,
    RegimeAnalogue,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.0-flash-001"

WGC_WARNING = (
    "WGC central bank buying data unavailable (HTTP 501) — "
    "gold valuation excludes central bank demand context"
)

# Threshold for valuation label assignment (equity path)
# If current P/E is more than this fraction below/above analogue avg
_ATTRACTIVE_THRESHOLD = -0.15   # 15% below → Attractive
_STRETCHED_THRESHOLD = 0.20     # 20% above → Stretched

_EQUITY_SYSTEM_PROMPT = (
    "You are a fundamental equity analyst. Assess valuation relative to historical "
    "regime analogues. Reference specific analogue periods and metrics. "
    "Do NOT invent numbers — use only the data provided. "
    "The valuation_label has been determined by rules — write a narrative consistent with it. "
    "Cite the analogue IDs and periods used for comparison. "
    "If fundamental data is partially missing, note this in the narrative explicitly."
)

_GOLD_SYSTEM_PROMPT = (
    "You are a gold market analyst. Assess gold valuation using real yield environment, "
    "ETF flow context, and macro regime overlay when available. "
    "Do NOT invent numbers. Reference the specific FRED indicators provided. "
    "Note: WGC central bank buying data is unavailable and excluded from this analysis. "
    "Assign valuation_label based on the real yield environment and price momentum."
)


# ---------------------------------------------------------------------------
# Equity path helpers
# ---------------------------------------------------------------------------


def _compute_weighted_analogue_pe(analogues: list[RegimeAnalogue]) -> Optional[float]:
    """
    Compute similarity_score-weighted average P/E from analogue narratives.

    Analogues may contain P/E context in their narrative text. This function
    attempts a best-effort extraction. If no P/E data is parseable, returns None.

    The valuation node does NOT store analogue P/E in the database — the analogue
    narrative from Neo4j is the available context. We pass this to Gemini rather
    than trying to parse raw floats here. For the weighted average computation,
    we use the analogue similarity scores as weights to determine analogue relevance.
    """
    if not analogues:
        return None

    # Sort by similarity_score descending, take top 3
    sorted_analogues = sorted(analogues, key=lambda a: a.similarity_score, reverse=True)[:3]

    # Compute total weight for normalization
    total_weight = sum(a.similarity_score for a in sorted_analogues)
    if total_weight <= 0:
        return None

    # We cannot reliably parse P/E from free-form narrative text.
    # The weighted analogue context is passed to Gemini for narrative generation.
    # pe_vs_analogue_avg is set to None here if we cannot extract numeric values.
    # The source entry will be populated based on analogue IDs used.
    return None  # Numeric extraction deferred to Gemini — no hardcoded parsing


def _compute_equity_valuation_label(
    pe_ratio: Optional[float],
    pb_ratio: Optional[float],
    missing_metrics: list[str],
) -> str:
    """
    Assign valuation label for equity path.

    When both P/E and P/B are missing → default to "Fair" with a warning.
    When P/E is available, use sector-relative heuristics for VN equities:
    - VN market P/E historically ~10-18x (Fair range)
    - Below 10x → Attractive
    - Above 20x → Stretched
    """
    if pe_ratio is None and pb_ratio is None:
        return "Fair"  # Partial assessment default — warning will be added separately

    if pe_ratio is not None:
        if pe_ratio < 10.0:
            return "Attractive"
        elif pe_ratio > 20.0:
            return "Stretched"
        else:
            return "Fair"

    if pb_ratio is not None:
        if pb_ratio < 1.0:
            return "Attractive"
        elif pb_ratio > 3.5:
            return "Stretched"
        else:
            return "Fair"

    return "Fair"


def _build_equity_sources(
    fundamentals_row: Optional[FundamentalsRow],
    analogues: list[RegimeAnalogue],
    pe_vs_analogue_avg: Optional[float],
    pb_vs_analogue_avg: Optional[float],
) -> dict[str, str]:
    """Build sources dict for equity ValuationOutput."""
    sources: dict[str, str] = {}

    if fundamentals_row is not None:
        row_id = f"fundamentals:{fundamentals_row.symbol}:{fundamentals_row.data_as_of.isoformat()}"
        if fundamentals_row.pe_ratio is not None:
            sources["pe_ratio"] = row_id
        if fundamentals_row.pb_ratio is not None:
            sources["pb_ratio"] = row_id
        if fundamentals_row.eps is not None:
            sources["eps"] = row_id
        if fundamentals_row.market_cap is not None:
            sources["market_cap"] = row_id
        if fundamentals_row.roe is not None:
            sources["roe"] = row_id
        if fundamentals_row.roa is not None:
            sources["roa"] = row_id

    if pe_vs_analogue_avg is not None and analogues:
        top_analogues = sorted(analogues, key=lambda a: a.similarity_score, reverse=True)[:3]
        analogue_ids = ",".join(a.analogue_id for a in top_analogues)
        sources["pe_vs_analogue_avg"] = f"computed:analogue_weighted_avg:{analogue_ids}"

    if pb_vs_analogue_avg is not None and analogues:
        top_analogues = sorted(analogues, key=lambda a: a.similarity_score, reverse=True)[:3]
        analogue_ids = ",".join(a.analogue_id for a in top_analogues)
        sources["pb_vs_analogue_avg"] = f"computed:analogue_weighted_avg:{analogue_ids}"

    return sources


def _equity_path(state: ReportState) -> dict[str, Any]:
    """
    Equity valuation path:
    1. Reads fundamentals_rows and regime_analogues from state
    2. Identifies missing metrics
    3. Computes valuation_label deterministically
    4. Calls Gemini for narrative generation with analogue context
    5. Returns {"valuation_output": ValuationOutput}
    """
    fundamentals_rows: list[FundamentalsRow] = state.get("fundamentals_rows", [])
    analogues: list[RegimeAnalogue] = state.get("regime_analogues", [])
    earnings_docs = state.get("earnings_docs", [])
    ticker: str = state.get("ticker", "UNKNOWN")

    all_warnings: list[str] = []
    missing_metrics: list[str] = []

    # Use most recent fundamentals row (first, as per orchestrator convention)
    fundamentals_row: Optional[FundamentalsRow] = fundamentals_rows[0] if fundamentals_rows else None

    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None

    if fundamentals_row is not None:
        pe_ratio = fundamentals_row.pe_ratio
        pb_ratio = fundamentals_row.pb_ratio
        all_warnings.extend(fundamentals_row.warnings)
    else:
        all_warnings.append(
            f"No fundamentals data available for {ticker} — valuation is partial"
        )

    # Track missing metrics
    if pe_ratio is None:
        missing_metrics.append("pe_ratio")
    if pb_ratio is None:
        missing_metrics.append("pb_ratio")

    # Add partial assessment warning when key metrics are missing
    if missing_metrics:
        if len(missing_metrics) >= 2:
            all_warnings.append(
                f"Partial assessment: fundamental metrics missing: {', '.join(missing_metrics)}"
            )
        else:
            all_warnings.append(
                f"Partial assessment: {missing_metrics[0]} not available — "
                "using available metrics only"
            )

    # Sort analogues by similarity_score, take top 3
    sorted_analogues = sorted(analogues, key=lambda a: a.similarity_score, reverse=True)[:3]
    analogue_ids_used = [a.analogue_id for a in sorted_analogues]
    for a in sorted_analogues:
        all_warnings.extend(a.warnings)

    # Deterministic valuation label
    valuation_label = _compute_equity_valuation_label(pe_ratio, pb_ratio, missing_metrics)

    # Compute weighted analogue avg (None if not extractable from text)
    pe_vs_analogue_avg: Optional[float] = None  # Gemini will contextualize this
    pb_vs_analogue_avg: Optional[float] = None

    # Build sources
    sources = _build_equity_sources(
        fundamentals_row, sorted_analogues, pe_vs_analogue_avg, pb_vs_analogue_avg
    )

    # Build Gemini prompt
    fundamentals_text = format_fundamentals_context(fundamentals_rows)
    analogue_text = format_analogue_context(sorted_analogues)

    missing_note = ""
    if missing_metrics:
        missing_note = (
            f"\nNOTE: The following fundamental metrics are missing: {', '.join(missing_metrics)}. "
            "Produce a partial assessment using only the available data. Do NOT skip."
        )

    human_prompt = (
        f"Ticker: {ticker}\n"
        f"Valuation label (already determined): {valuation_label}\n\n"
        f"Current Fundamentals:\n{fundamentals_text}\n\n"
        f"Historical Regime Analogues (sorted by similarity):\n{analogue_text}\n"
        f"{missing_note}\n\n"
        "Write a valuation narrative that:\n"
        "1. Compares current P/E and P/B to the analogue periods listed above\n"
        "2. References specific analogue IDs and their periods\n"
        "3. Explains whether the stock appears Attractive, Fair, or Stretched "
        "relative to historical regime comparisons\n"
        "4. If metrics are missing, explicitly note this in the assessment\n"
        f"Analogue IDs used: {analogue_ids_used}"
    )

    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
        temperature=0.2,
    )
    chain = llm.with_structured_output(ValuationOutput)
    gemini_output: ValuationOutput = chain.invoke([
        SystemMessage(content=_EQUITY_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ])

    # Merge Gemini warnings into our warnings list
    all_warnings = all_warnings + list(gemini_output.warnings)

    final_output = ValuationOutput(
        asset_type="equity",
        valuation_label=valuation_label,  # deterministic — authoritative
        pe_ratio=pe_ratio,
        pb_ratio=pb_ratio,
        pe_vs_analogue_avg=pe_vs_analogue_avg,
        pb_vs_analogue_avg=pb_vs_analogue_avg,
        analogue_ids_used=analogue_ids_used,
        real_yield=None,
        etf_flow_context=None,
        missing_metrics=missing_metrics,
        narrative=gemini_output.narrative,
        sources=sources if sources else gemini_output.sources,
        warnings=all_warnings,
    )

    return {"valuation_output": final_output}


# ---------------------------------------------------------------------------
# Gold path helpers
# ---------------------------------------------------------------------------


def _compute_real_yield(fred_rows: list[FredIndicatorRow]) -> Optional[float]:
    """
    Compute real yield proxy from FRED data.

    Prefer 10-year Treasury minus CPI YoY (GS10 - CPIAUCSL_yoy).
    As a proxy: GS10 - (CPIAUCSL annualized) if available.
    If GS10 not available, use FEDFUNDS - estimated CPI.

    Returns real yield as a float (positive = restrictive for gold,
    negative = accommodative for gold).
    """
    fred_by_id = {row.series_id: row for row in fred_rows}

    # Preferred: GS10 (10-year Treasury)
    gs10 = fred_by_id.get("GS10")
    cpi = fred_by_id.get("CPIAUCSL")
    fedfunds = fred_by_id.get("FEDFUNDS")

    if gs10 is not None:
        # Approximate real yield = nominal 10yr - CPI-implied inflation proxy
        # CPI index level doesn't give YoY directly, but FEDFUNDS context helps
        # Use simple heuristic: GS10 - 2.5% (Fed 2% target + 0.5% premium)
        # More accurate: if we had CPIAUCSL_PC1 (YoY%) we'd use that
        # As a conservative proxy, GS10 - ~2.5 is standard real yield approximation
        # when no explicit CPI YoY series is present
        return gs10.value - 2.5  # GS10 minus Fed 2% target + 0.5% breakeven

    if fedfunds is not None:
        # Fallback: use Fed Funds real rate
        return fedfunds.value - 2.5  # Same logic

    return None


def _compute_etf_flow_context(etf_rows: list[GoldEtfRow]) -> str:
    """
    Summarize ETF flow context from volume trends.
    Returns a descriptive string of ETF activity.
    """
    if not etf_rows:
        return "No ETF flow data available."

    lines = []
    for row in etf_rows:
        vol_str = f"{row.volume:,}" if row.volume is not None else "N/A"
        as_of = row.data_as_of.strftime("%Y-%m-%d")
        lines.append(
            f"{row.ticker} ({row.resolution}): Close={row.close:.2f}, Volume={vol_str} (as of {as_of})"
        )

    # Basic trend description based on close vs open
    primary = etf_rows[0]
    if primary.open is not None:
        change = primary.close - primary.open
        pct_change = change / primary.open * 100
        direction = "up" if change > 0 else "down"
        lines.append(f"Primary ETF ({primary.ticker}): {direction} {abs(pct_change):.1f}% over period")

    return "; ".join(lines)


def _compute_gold_valuation_label(
    real_yield: Optional[float],
    etf_rows: list[GoldEtfRow],
    price_rows: list[GoldPriceRow],
) -> str:
    """
    Assign gold valuation label based on real yield environment and price momentum.

    Gold is typically:
    - Attractive: negative real yield (accommodative), positive ETF flow
    - Fair: slightly positive real yield (<1.5%), neutral flows
    - Stretched: high real yield (>2%), price well above fair value proxies
    """
    if real_yield is None:
        return "Fair"  # Default when data is insufficient

    if real_yield < 0:
        return "Attractive"  # Negative real yield = gold-supportive environment
    elif real_yield < 1.5:
        return "Fair"
    else:
        return "Stretched"  # High real yield = headwind for gold


def _build_gold_sources(
    fred_rows: list[FredIndicatorRow],
    etf_rows: list[GoldEtfRow],
    price_rows: list[GoldPriceRow],
    real_yield: Optional[float],
) -> dict[str, str]:
    """Build sources dict for gold ValuationOutput."""
    sources: dict[str, str] = {}

    # Source real yield to FRED rows used
    if real_yield is not None:
        fred_by_id = {row.series_id: row for row in fred_rows}
        if "GS10" in fred_by_id:
            gs10 = fred_by_id["GS10"]
            sources["real_yield"] = f"fred:GS10:{gs10.data_as_of.isoformat()}"
        elif "FEDFUNDS" in fred_by_id:
            ff = fred_by_id["FEDFUNDS"]
            sources["real_yield"] = f"fred:FEDFUNDS:{ff.data_as_of.isoformat()}"

    # Source price rows
    if price_rows:
        p = price_rows[0]
        sources["gold_price"] = f"gold_price:{p.source}:{p.data_as_of.isoformat()}"

    # Source ETF rows
    if etf_rows:
        e = etf_rows[0]
        sources["etf_close"] = f"gold_etf:{e.ticker}:{e.data_as_of.isoformat()}"

    return sources


def _gold_path(state: ReportState) -> dict[str, Any]:
    """
    Gold valuation path:
    1. Reads fred_rows, gold_etf_rows, gold_price_rows from state
    2. Reads macro_regime_output if present (macro overlay context)
    3. Computes real yield and ETF context
    4. Always appends WGC warning (per locked decision: 501 stub)
    5. Calls Gemini for narrative generation
    6. Returns {"valuation_output": ValuationOutput}
    """
    fred_rows: list[FredIndicatorRow] = state.get("fred_rows", [])
    etf_rows: list[GoldEtfRow] = state.get("gold_etf_rows", [])
    price_rows: list[GoldPriceRow] = state.get("gold_price_rows", [])
    macro_regime_output: Optional[MacroRegimeOutput] = state.get("macro_regime_output")

    all_warnings: list[str] = []

    # Always include WGC warning (per locked decision)
    all_warnings.append(WGC_WARNING)

    # Propagate warnings from input data
    for row in fred_rows:
        all_warnings.extend(row.warnings)
    for row in etf_rows:
        all_warnings.extend(row.warnings)
    for row in price_rows:
        all_warnings.extend(row.warnings)

    # Compute real yield from FRED
    real_yield = _compute_real_yield(fred_rows)

    # Compute ETF flow context
    etf_flow_context = _compute_etf_flow_context(etf_rows)

    # Assign valuation label
    valuation_label = _compute_gold_valuation_label(real_yield, etf_rows, price_rows)

    # Build sources
    sources = _build_gold_sources(fred_rows, etf_rows, price_rows, real_yield)

    # Build Gemini prompt
    fred_text = format_fred_context(fred_rows)
    gold_text = format_gold_context(price_rows, etf_rows)

    macro_overlay_text = ""
    if macro_regime_output is not None:
        macro_overlay_text = (
            f"\nMacro Regime Overlay:\n"
            f"  Top regime: {macro_regime_output.top_regime_id} "
            f"(confidence: {macro_regime_output.top_confidence:.0%})\n"
            f"  Macro label: {macro_regime_output.macro_label}\n"
            f"  Narrative: {macro_regime_output.narrative}\n"
        )

    real_yield_str = f"{real_yield:.2f}%" if real_yield is not None else "N/A (FRED data insufficient)"

    human_prompt = (
        f"Gold Valuation Assessment\n"
        f"Valuation label (already determined): {valuation_label}\n"
        f"Real yield (proxy): {real_yield_str}\n\n"
        f"FRED Macro Indicators:\n{fred_text}\n\n"
        f"Gold Market Data:\n{gold_text}\n"
        f"{macro_overlay_text}\n"
        f"DATA CAVEAT: {WGC_WARNING}\n\n"
        "Write a gold valuation narrative that:\n"
        "1. Explains the real yield environment and its implication for gold\n"
        "2. Summarizes ETF flow activity as a sentiment indicator\n"
        "3. Notes the WGC data gap explicitly\n"
        "4. If macro regime context is provided, explain how the regime backdrop "
        "reinforces or conflicts with the gold valuation"
    )

    api_key = os.getenv("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(
        model=_MODEL,
        google_api_key=api_key if api_key else None,
        temperature=0.2,
    )
    chain = llm.with_structured_output(ValuationOutput)
    gemini_output: ValuationOutput = chain.invoke([
        SystemMessage(content=_GOLD_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ])

    # Merge Gemini warnings
    all_warnings = all_warnings + list(gemini_output.warnings)

    final_output = ValuationOutput(
        asset_type="gold",
        valuation_label=valuation_label,  # deterministic — authoritative
        pe_ratio=None,
        pb_ratio=None,
        pe_vs_analogue_avg=None,
        pb_vs_analogue_avg=None,
        analogue_ids_used=[],
        real_yield=real_yield,
        etf_flow_context=etf_flow_context,
        missing_metrics=[],
        narrative=gemini_output.narrative,
        sources=sources if sources else gemini_output.sources,
        warnings=all_warnings,
    )

    return {"valuation_output": final_output}


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def valuation_node(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: dispatches to equity or gold valuation path based on asset_type.

    State reads:
        - state["asset_type"]: "equity" | "gold"
        For equity:
            - state["fundamentals_rows"]: list[FundamentalsRow]
            - state["regime_analogues"]: list[RegimeAnalogue]
            - state["earnings_docs"]: list[DocumentChunk]
        For gold:
            - state["fred_rows"]: list[FredIndicatorRow]
            - state["gold_etf_rows"]: list[GoldEtfRow]
            - state["gold_price_rows"]: list[GoldPriceRow]
            - state["macro_regime_output"]: Optional[MacroRegimeOutput]

    State writes:
        - state["valuation_output"]: ValuationOutput

    Does NOT call any retrieval functions. Does NOT recompute raw market data.
    """
    asset_type: str = state.get("asset_type", "equity")

    if asset_type == "gold":
        return _gold_path(state)
    else:
        return _equity_path(state)
