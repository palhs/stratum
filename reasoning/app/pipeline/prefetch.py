"""
reasoning/app/pipeline/prefetch.py — Two-stage prefetch for the report pipeline.
Phase 7 | Plan 01 | Requirement: REAS-06

Implements:
    prefetch() — Retrieve all data sources before the LangGraph graph runs.

Design decisions (locked):
- Equity path: calls get_fundamentals, get_structure_markers, get_fred_indicators,
  search_earnings_docs, search_macro_docs, get_regime_analogues.
  Gold fields (gold_price_rows, gold_etf_rows) set to empty list.
- Gold path: calls get_gold_price, get_gold_etf, get_structure_markers("GOLD"),
  get_fred_indicators, search_macro_docs, get_regime_analogues.
  Equity fields (fundamentals_rows, earnings_docs) set to empty list.
- Invalid asset_type: raises ValueError("Unknown asset_type: {asset_type}")
- All retrieval functions accept engine/driver/client as first positional arg
  for test injection (matching Phase 5 function signatures).
- retrieval_warnings accumulated from check_freshness() calls on each source
  (via warnings field on returned Pydantic rows).
- All node output fields set to None — populated by LangGraph nodes.
- get_regime_analogues() called with a macro query string (current regime context).
"""

from __future__ import annotations

import logging
from typing import Any

from reasoning.app.retrieval.neo4j_retriever import get_regime_analogues
from reasoning.app.retrieval.postgres_retriever import (
    get_fundamentals,
    get_structure_markers,
    get_fred_indicators,
    get_gold_price,
    get_gold_etf,
)
from reasoning.app.retrieval.qdrant_retriever import search_macro_docs, search_earnings_docs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default FRED series IDs to prefetch for all asset types
# ---------------------------------------------------------------------------

_DEFAULT_FRED_SERIES = [
    "FEDFUNDS",   # Federal Funds Rate
    "UNRATE",     # Unemployment Rate
    "CPIAUCSL",   # CPI All Urban Consumers
    "GS10",       # 10-Year Treasury Constant Maturity Rate
    "DGS2",       # 2-Year Treasury Constant Maturity Rate
]

# Default macro context query for regime analogue retrieval
_DEFAULT_MACRO_QUERY = "current macroeconomic regime interest rates inflation growth"


# ---------------------------------------------------------------------------
# prefetch()
# ---------------------------------------------------------------------------


def prefetch(
    ticker: str,
    asset_type: str,
    db_engine: Any,
    neo4j_driver: Any,
    qdrant_client: Any,
) -> dict:
    """
    Retrieve all data sources for the report pipeline before the graph runs.

    This is the first stage of the two-stage pipeline:
        Stage 1: prefetch() — fan-out retrieval from all data sources
        Stage 2: run_graph() — LangGraph nodes consume pre-fetched state

    Args:
        ticker:        Asset ticker symbol (e.g. "VNM" for equity, "GOLD" for gold).
        asset_type:    Asset type — "equity" or "gold".
        db_engine:     SQLAlchemy Engine for PostgreSQL retrieval functions.
        neo4j_driver:  Neo4j driver / graph store for regime analogue retrieval.
        qdrant_client: Qdrant client for vector search retrieval.

    Returns:
        dict matching ReportState shape with all retrieved data populated and
        all node output fields set to None (to be populated by LangGraph nodes).

    Raises:
        ValueError: If asset_type is not "equity" or "gold".
    """
    if asset_type not in ("equity", "gold"):
        raise ValueError(f"Unknown asset_type: {asset_type}")

    retrieval_warnings: list[str] = []

    if asset_type == "equity":
        # ---- Equity path ----
        # Fundamentals (quarterly)
        try:
            fundamentals_rows = get_fundamentals(ticker, engine=db_engine)
            for row in fundamentals_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_fundamentals failed | ticker=%s | error=%s", ticker, exc)
            fundamentals_rows = []

        # Structure markers
        try:
            structure_marker_rows = get_structure_markers(ticker, engine=db_engine)
            for row in structure_marker_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_structure_markers failed | ticker=%s | error=%s", ticker, exc)
            structure_marker_rows = []

        # FRED macro indicators
        try:
            fred_rows = get_fred_indicators(_DEFAULT_FRED_SERIES, engine=db_engine)
            for row in fred_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_fred_indicators failed | error=%s", exc)
            fred_rows = []

        # Earnings docs (equity-specific)
        try:
            earnings_docs = search_earnings_docs(
                query=f"{ticker} revenue earnings profit growth",
                ticker=ticker,
                client=qdrant_client,
            )
            for chunk in earnings_docs:
                retrieval_warnings.extend(chunk.warnings)
        except Exception as exc:
            logger.warning("prefetch: search_earnings_docs failed | ticker=%s | error=%s", ticker, exc)
            earnings_docs = []

        # Macro docs
        try:
            macro_docs = search_macro_docs(
                query=_DEFAULT_MACRO_QUERY,
                client=qdrant_client,
            )
            for chunk in macro_docs:
                retrieval_warnings.extend(chunk.warnings)
        except Exception as exc:
            logger.warning("prefetch: search_macro_docs failed | error=%s", exc)
            macro_docs = []

        # Regime analogues (Neo4j)
        try:
            regime_analogues = get_regime_analogues(
                query_text=_DEFAULT_MACRO_QUERY,
                graph_store=neo4j_driver,
            )
        except Exception as exc:
            logger.warning("prefetch: get_regime_analogues failed | error=%s", exc)
            regime_analogues = []

        # Gold fields empty for equity
        gold_price_rows = []
        gold_etf_rows = []

    else:
        # ---- Gold path ----
        # Gold price
        try:
            gold_price_rows = get_gold_price(engine=db_engine)
            for row in gold_price_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_gold_price failed | error=%s", exc)
            gold_price_rows = []

        # Gold ETF OHLCV
        try:
            gold_etf_rows = get_gold_etf(engine=db_engine)
            for row in gold_etf_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_gold_etf failed | error=%s", exc)
            gold_etf_rows = []

        # Structure markers for GOLD
        try:
            structure_marker_rows = get_structure_markers("GOLD", engine=db_engine)
            for row in structure_marker_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_structure_markers(GOLD) failed | error=%s", exc)
            structure_marker_rows = []

        # FRED macro indicators
        try:
            fred_rows = get_fred_indicators(_DEFAULT_FRED_SERIES, engine=db_engine)
            for row in fred_rows:
                retrieval_warnings.extend(row.warnings)
        except Exception as exc:
            logger.warning("prefetch: get_fred_indicators failed | error=%s", exc)
            fred_rows = []

        # Macro docs
        try:
            macro_docs = search_macro_docs(
                query=_DEFAULT_MACRO_QUERY,
                client=qdrant_client,
            )
            for chunk in macro_docs:
                retrieval_warnings.extend(chunk.warnings)
        except Exception as exc:
            logger.warning("prefetch: search_macro_docs failed | error=%s", exc)
            macro_docs = []

        # Regime analogues (Neo4j)
        try:
            regime_analogues = get_regime_analogues(
                query_text=_DEFAULT_MACRO_QUERY,
                graph_store=neo4j_driver,
            )
        except Exception as exc:
            logger.warning("prefetch: get_regime_analogues failed | error=%s", exc)
            regime_analogues = []

        # Equity fields empty for gold
        fundamentals_rows = []
        earnings_docs = []

    logger.info(
        "prefetch complete | ticker=%s | asset_type=%s | warnings=%d",
        ticker, asset_type, len(retrieval_warnings),
    )

    # Return ReportState-shaped dict with node outputs as None
    return {
        # Orchestrator inputs
        "ticker": ticker,
        "asset_type": asset_type,
        # Pre-fetched retrieval outputs
        "fred_rows": fred_rows,
        "regime_analogues": regime_analogues,
        "macro_docs": macro_docs,
        "fundamentals_rows": fundamentals_rows,
        "structure_marker_rows": structure_marker_rows,
        "gold_price_rows": gold_price_rows,
        "gold_etf_rows": gold_etf_rows,
        "earnings_docs": earnings_docs,
        # Warnings accumulator
        "retrieval_warnings": retrieval_warnings,
        # Node outputs — all None, populated by LangGraph nodes
        "macro_regime_output": None,
        "valuation_output": None,
        "structure_output": None,
        "entry_quality_output": None,
        "grounding_result": None,
        "conflict_output": None,
        "report_output": None,
    }
