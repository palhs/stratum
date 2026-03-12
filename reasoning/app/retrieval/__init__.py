"""
reasoning/app/retrieval — Public API for the retrieval layer.
Phase 5 | Plans 01-03

Exports shared types, freshness check logic, and threshold constants.
Retriever functions (get_regime_analogues, get_macro_docs, get_earnings_docs, etc.)
are added in Plans 02-03.
"""

from reasoning.app.retrieval.freshness import check_freshness, FRESHNESS_THRESHOLDS
from reasoning.app.retrieval.types import (
    RegimeAnalogue,
    DocumentChunk,
    FundamentalsRow,
    StructureMarkerRow,
    FredIndicatorRow,
    GoldPriceRow,
    GoldEtfRow,
    NoDataError,
)

__all__ = [
    # Freshness
    "check_freshness",
    "FRESHNESS_THRESHOLDS",
    # Types
    "RegimeAnalogue",
    "DocumentChunk",
    "FundamentalsRow",
    "StructureMarkerRow",
    "FredIndicatorRow",
    "GoldPriceRow",
    "GoldEtfRow",
    "NoDataError",
]
