"""
reasoning/app/retrieval — Public API for the retrieval layer.
Phase 5 | Plans 01-03

Exports shared types, freshness check logic, threshold constants,
and all retriever functions (added in Plans 02-03).
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
from reasoning.app.retrieval.neo4j_retriever import (
    get_regime_analogues,
    get_all_analogues,
)
from reasoning.app.retrieval.postgres_retriever import (
    get_fundamentals,
    get_structure_markers,
    get_fred_indicators,
    get_gold_price,
    get_gold_etf,
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
    # Neo4j retrievers
    "get_regime_analogues",
    "get_all_analogues",
    # PostgreSQL retrievers
    "get_fundamentals",
    "get_structure_markers",
    "get_fred_indicators",
    "get_gold_price",
    "get_gold_etf",
]
