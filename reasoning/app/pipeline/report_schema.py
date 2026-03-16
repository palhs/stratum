"""
reasoning/app/pipeline/report_schema.py — Pydantic card models for JSON report structure.
Phase 7 | Plan 02 | Requirements: REPT-01, REPT-04

Design decisions (locked):
- Flat card models — each card is a flat BaseModel (no nested sub-objects).
- Conclusion-first ordering: entry_quality → conflict (optional) → macro_regime → valuation → structure.
- model_dump(exclude_none=True) on ReportCard produces JSONB-ready flat structure.
- ConflictCard is Optional — absent when no named conflict pattern detected.
- data_warnings collected from retrieval, node warnings, and WGC gold data gap.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Individual card models — flat, no nested Pydantic instances
# ---------------------------------------------------------------------------


class EntryQualityCard(BaseModel):
    """Conclusion-first card: composite entry quality assessment."""

    tier: str                                      # "Favorable" | "Neutral" | "Cautious" | "Avoid"
    macro_assessment: str                          # "Supportive" | "Mixed" | "Headwind"
    valuation_assessment: str                      # "Attractive" | "Fair" | "Stretched"
    structure_assessment: str                      # "Constructive" | "Neutral" | "Deteriorating"
    conflict_pattern: Optional[str] = None         # named conflict pattern, if any
    structure_veto_applied: bool = False           # True when structure veto capped the tier
    narrative: str                                 # LLM-generated composite narrative


class MacroRegimeCard(BaseModel):
    """Macro regime classification card."""

    label: str                                     # "Supportive" | "Mixed" | "Headwind"
    top_confidence: float                          # 0.0–1.0 confidence in top regime
    is_mixed_signal: bool                          # True when top_confidence < 0.70
    regime_probabilities: list[dict]              # list of {regime_id, regime_name, confidence, source_analogue_id}
    narrative: str                                 # LLM-generated macro narrative


class ValuationCard(BaseModel):
    """Asset valuation card."""

    label: str                                     # "Attractive" | "Fair" | "Stretched"
    pe_ratio: Optional[float] = None              # equity path only
    pb_ratio: Optional[float] = None              # equity path only
    real_yield: Optional[float] = None            # gold path only
    etf_flow_context: Optional[str] = None        # gold path only
    narrative: str                                 # LLM-generated valuation narrative


class StructureCard(BaseModel):
    """Price structure / technical positioning card."""

    label: str                                     # "Constructive" | "Neutral" | "Deteriorating"
    close: Optional[float] = None                 # latest closing price
    drawdown_from_ath: Optional[float] = None     # drawdown from all-time high (negative pct)
    drawdown_from_52w_high: Optional[float] = None  # drawdown from 52-week high (negative pct)
    close_pct_rank: Optional[float] = None        # percentile rank of close price
    narrative: str                                 # LLM-generated structure narrative


class ConflictCard(BaseModel):
    """Signal conflict card — present only when a named conflict pattern is detected."""

    pattern_name: str                             # e.g. "Macro–Valuation Divergence"
    severity: str                                 # "minor" | "major"
    tier_impact: str                              # description of how tier was adjusted
    narrative: str                                # LLM-generated conflict narrative


# ---------------------------------------------------------------------------
# Top-level report card — wraps all section cards
# ---------------------------------------------------------------------------


class ReportCard(BaseModel):
    """
    Top-level report card in conclusion-first ordering.

    Sections ordered: entry_quality → conflict (optional) → macro_regime → valuation → structure.
    Serialized with model_dump_json(exclude_none=True) for JSONB storage.
    """

    entry_quality: EntryQualityCard
    conflict: Optional[ConflictCard] = None       # included only when conflict detected
    macro_regime: MacroRegimeCard
    valuation: ValuationCard
    structure: StructureCard
    data_warnings: list[str] = []
    language: str = "en"
