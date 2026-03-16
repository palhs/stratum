"""
reasoning/app/nodes/state.py — ReportState TypedDict and all Pydantic output models.
Phase 6 | Plan 01 | Requirement: REAS-03

Design decisions (locked):
- ReportState TypedDict is the single contract between the orchestrator and all nodes.
- All node output fields are Optional in state to allow incremental population.
- All output models have sources: dict[str,str] = {} and warnings: list[str] = [].
- GroundingError is raised (not returned) when numeric claims cannot be attributed.
- Constants for thresholds and label sets are defined here as the canonical source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from typing_extensions import TypedDict

from pydantic import BaseModel, Field

from reasoning.app.retrieval.types import (
    FredIndicatorRow,
    RegimeAnalogue,
    DocumentChunk,
    FundamentalsRow,
    StructureMarkerRow,
    GoldPriceRow,
    GoldEtfRow,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIXED_SIGNAL_THRESHOLD = 0.70  # is_mixed_signal = (top_confidence < 0.70)

COMPOSITE_TIERS = ["Favorable", "Neutral", "Cautious", "Avoid"]
MACRO_LABELS = ["Supportive", "Mixed", "Headwind"]
VALUATION_LABELS = ["Attractive", "Fair", "Stretched"]
STRUCTURE_LABELS = ["Constructive", "Neutral", "Deteriorating"]


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class GroundingError(Exception):
    """Raised when a numeric claim cannot be attributed to a source record."""
    pass


# ---------------------------------------------------------------------------
# Pydantic output models — one per reasoning node
# ---------------------------------------------------------------------------


class RegimeProbability(BaseModel):
    """Probability entry for a single historical regime analogue."""

    regime_id: str
    regime_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_analogue_id: str


class MacroRegimeOutput(BaseModel):
    """Output of the macro_regime node."""

    regime_probabilities: list[RegimeProbability] = []
    top_regime_id: str
    top_confidence: float
    is_mixed_signal: bool
    mixed_signal_label: Optional[str] = None
    top_two_analogues: list[str] = []
    macro_label: str  # "Supportive" | "Mixed" | "Headwind"
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []


class ValuationOutput(BaseModel):
    """Output of the valuation node."""

    asset_type: str
    valuation_label: str  # "Attractive" | "Fair" | "Stretched"
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    pe_vs_analogue_avg: Optional[float] = None
    pb_vs_analogue_avg: Optional[float] = None
    analogue_ids_used: list[str] = []
    real_yield: Optional[float] = None         # gold path only
    etf_flow_context: Optional[str] = None     # gold path only
    missing_metrics: list[str] = []
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []


class StructureOutput(BaseModel):
    """Output of the structure node."""

    structure_label: str  # "Constructive" | "Neutral" | "Deteriorating"
    close: Optional[float] = None
    ma_10w: Optional[float] = None
    ma_20w: Optional[float] = None
    ma_50w: Optional[float] = None
    drawdown_from_ath: Optional[float] = None
    drawdown_from_52w_high: Optional[float] = None
    close_pct_rank: Optional[float] = None
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []


class EntryQualityOutput(BaseModel):
    """Output of the entry_quality node — final composite assessment."""

    macro_assessment: str
    valuation_assessment: str
    structure_assessment: str
    composite_tier: str  # "Favorable" | "Neutral" | "Cautious" | "Avoid"
    conflict_pattern: Optional[str] = None
    conflict_narrative: Optional[str] = None
    structure_veto_applied: bool = False
    stale_data_caveat: Optional[str] = None
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []


class GroundingResult(BaseModel):
    """Output of the grounding node — verifies numeric attribution."""

    status: str  # "pass" | "fail"
    checked_outputs: list[str] = []
    unattributed_claims: list[str] = []
    warnings: list[str] = []


class ConflictOutput(BaseModel):
    """Output of the conflict node — documents signal conflicts."""

    pattern_name: str
    severity: str  # "minor" | "major"
    macro_label: str
    valuation_label: str
    structure_label: str
    tier_impact: str
    narrative: str
    sources: dict[str, str] = {}
    warnings: list[str] = []


class ReportOutput(BaseModel):
    """Final report output produced by compose_report_node (Phase 7 Plan 02).

    Fields:
        report_json:     Flat card structure for JSONB storage.
        report_markdown: Human-readable Markdown for pre-rendering.
        language:        Report language code — "vi" or "en".
        data_as_of:      Oldest data_as_of timestamp across all sources.
        data_warnings:   Collected freshness/data-quality warnings from retrieval + nodes.
        model_version:   Gemini model version used for reasoning.
        warnings:        Additional pipeline-level warnings.
    """

    report_json: dict
    report_markdown: str
    language: str
    data_as_of: datetime
    data_warnings: list[str]
    model_version: str = "gemini-2.5-pro"
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# ReportState — single LangGraph state contract
# ---------------------------------------------------------------------------


class ReportState(TypedDict, total=False):
    """
    LangGraph state for the full report pipeline.

    Inputs are set by the orchestrator (Phase 7) before the graph runs.
    Pre-fetched retrieval outputs are set by the retrieval fan-out layer.
    Node outputs are populated one-by-one as each node completes.
    All node output fields are Optional to allow incremental population.
    """

    # ---- Orchestrator inputs ----
    ticker: str
    asset_type: str  # "equity" | "gold"

    # ---- Pre-fetched retrieval outputs ----
    fred_rows: list[FredIndicatorRow]
    regime_analogues: list[RegimeAnalogue]
    macro_docs: list[DocumentChunk]
    fundamentals_rows: list[FundamentalsRow]
    structure_marker_rows: list[StructureMarkerRow]
    gold_price_rows: list[GoldPriceRow]
    gold_etf_rows: list[GoldEtfRow]
    earnings_docs: list[DocumentChunk]

    # ---- Node outputs (Optional — populated by each node) ----
    macro_regime_output: Optional[MacroRegimeOutput]
    valuation_output: Optional[ValuationOutput]
    structure_output: Optional[StructureOutput]
    entry_quality_output: Optional[EntryQualityOutput]
    grounding_result: Optional[GroundingResult]
    conflict_output: Optional[ConflictOutput]

    # ---- Phase 7 fields ----
    language: str  # "vi" or "en" — set by run_graph() caller
    report_output: Optional[ReportOutput]  # written by compose_report_node (Plan 02)

    # ---- Warnings accumulator ----
    retrieval_warnings: list[str]
