"""
reasoning/tests/nodes/conftest.py — Mock fixtures for Phase 6 node unit tests.
Phase 6 | Plan 01 | Requirement: REAS-03

All fixtures use realistic but minimal data values based on VN equity market
context. No live service connections required — pure in-memory fixtures.

Design decisions:
- Function scope for all fixtures (cheap to construct, avoids state leakage)
- Realistic VN equity values: VHM ticker, VND amounts, typical VN30 fundamentals
- Gold fixtures use LBMA spot + GLD ETF typical ranges
- base_equity_state / base_gold_state return complete ReportState dicts
"""

from __future__ import annotations

from datetime import datetime
import pytest

from reasoning.app.retrieval.types import (
    DocumentChunk,
    FredIndicatorRow,
    FundamentalsRow,
    GoldEtfRow,
    GoldPriceRow,
    RegimeAnalogue,
    StructureMarkerRow,
)
from reasoning.app.nodes.state import ReportState


# ---------------------------------------------------------------------------
# Shared reference timestamp
# ---------------------------------------------------------------------------

_AS_OF = datetime(2024, 9, 18, 0, 0, 0)


# ---------------------------------------------------------------------------
# FRED indicator fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_fred_rows() -> list[FredIndicatorRow]:
    """
    3 representative FRED indicator rows: fed funds rate, unemployment, CPI.
    Values reflect late-2024 US macro environment.
    """
    return [
        FredIndicatorRow(
            series_id="FEDFUNDS",
            value=5.33,
            frequency="monthly",
            data_as_of=_AS_OF,
        ),
        FredIndicatorRow(
            series_id="UNRATE",
            value=4.2,
            frequency="monthly",
            data_as_of=_AS_OF,
        ),
        FredIndicatorRow(
            series_id="CPIAUCSL",
            value=314.796,
            frequency="monthly",
            data_as_of=_AS_OF,
        ),
        FredIndicatorRow(
            series_id="GS10",
            value=4.25,
            frequency="monthly",
            data_as_of=_AS_OF,
        ),
    ]


# ---------------------------------------------------------------------------
# Regime analogue fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_regime_analogues() -> list[RegimeAnalogue]:
    """
    2 representative regime analogues for VN equity analysis context.
    """
    return [
        RegimeAnalogue(
            source_regime="current_2024",
            analogue_id="post_gfc_recovery_2010",
            analogue_name="Post-GFC Recovery 2010",
            period_start="2010-01",
            period_end="2011-06",
            similarity_score=0.88,
            dimensions_matched=["inflation", "credit_spread", "growth_momentum"],
            narrative=(
                "Recovery phase following the 2008 financial crisis. "
                "Fed remained accommodative, inflation moderate. "
                "Equity markets rebounded strongly from distressed lows."
            ),
        ),
        RegimeAnalogue(
            source_regime="current_2024",
            analogue_id="mid_cycle_expansion_2016",
            analogue_name="Mid-Cycle Expansion 2016",
            period_start="2016-07",
            period_end="2018-01",
            similarity_score=0.74,
            dimensions_matched=["growth_momentum", "credit_spread"],
            narrative=(
                "Mid-cycle expansion with moderate rate hikes. "
                "Earnings growth supportive; valuations stretched but not extreme."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Structure marker fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_structure_marker_rows() -> list[StructureMarkerRow]:
    """
    2 StructureMarkerRow instances with realistic VN equity values (VHM).
    Weekly resolution, values in VND.
    close > all MAs => Constructive signal.
    """
    return [
        StructureMarkerRow(
            symbol="VHM",
            asset_type="equity",
            resolution="weekly",
            close=42_500.0,
            ma_10w=41_200.0,
            ma_20w=40_100.0,
            ma_50w=38_500.0,
            drawdown_from_ath=-0.125,       # -12.5% from ATH
            drawdown_from_52w_high=-0.083,  # -8.3% from 52w high
            close_pct_rank=0.72,
            pe_pct_rank=0.58,
            data_as_of=_AS_OF,
        ),
        StructureMarkerRow(
            symbol="VHM",
            asset_type="equity",
            resolution="daily",
            close=42_600.0,
            ma_10w=41_500.0,
            ma_20w=40_800.0,
            ma_50w=39_200.0,
            drawdown_from_ath=-0.121,
            drawdown_from_52w_high=-0.079,
            close_pct_rank=0.74,
            pe_pct_rank=0.60,
            data_as_of=_AS_OF,
        ),
    ]


@pytest.fixture()
def mock_deteriorating_marker_rows() -> list[StructureMarkerRow]:
    """
    StructureMarkerRow with close < all MAs and large drawdown => Deteriorating signal.
    """
    return [
        StructureMarkerRow(
            symbol="VHM",
            asset_type="equity",
            resolution="weekly",
            close=28_000.0,
            ma_10w=35_000.0,
            ma_20w=38_000.0,
            ma_50w=41_000.0,
            drawdown_from_ath=-0.38,       # -38% from ATH (severe)
            drawdown_from_52w_high=-0.28,
            close_pct_rank=0.12,           # bottom decile
            pe_pct_rank=0.15,
            data_as_of=_AS_OF,
        ),
    ]


@pytest.fixture()
def mock_partial_marker_rows() -> list[StructureMarkerRow]:
    """
    StructureMarkerRow with some None MA values — tests partial assessment path.
    """
    return [
        StructureMarkerRow(
            symbol="VHM",
            asset_type="equity",
            resolution="weekly",
            close=42_500.0,
            ma_10w=None,     # missing
            ma_20w=40_100.0,
            ma_50w=None,     # missing
            drawdown_from_ath=-0.125,
            drawdown_from_52w_high=-0.083,
            close_pct_rank=0.72,
            pe_pct_rank=None,
            data_as_of=_AS_OF,
        ),
    ]


# ---------------------------------------------------------------------------
# Fundamentals fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_fundamentals_rows() -> list[FundamentalsRow]:
    """
    2 FundamentalsRow instances with realistic VN equity values (VHM).
    """
    return [
        FundamentalsRow(
            symbol="VHM",
            period_type="annual",
            pe_ratio=12.4,
            pb_ratio=1.8,
            eps=3_420.0,
            market_cap=85_000_000_000.0,
            roe=0.142,
            roa=0.041,
            revenue_growth=0.185,
            net_margin=0.112,
            data_as_of=datetime(2024, 6, 30),
        ),
        FundamentalsRow(
            symbol="VHM",
            period_type="ttm",
            pe_ratio=11.8,
            pb_ratio=1.7,
            eps=3_650.0,
            market_cap=85_000_000_000.0,
            roe=0.156,
            roa=0.045,
            revenue_growth=0.212,
            net_margin=0.118,
            data_as_of=_AS_OF,
        ),
    ]


# ---------------------------------------------------------------------------
# Document chunk fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_document_chunks() -> list[DocumentChunk]:
    """
    3 DocumentChunk instances representing FOMC and SBV document excerpts.
    """
    return [
        DocumentChunk(
            id="fomc_20240918_chunk_001",
            text=(
                "The Committee decided to lower the target range for the federal funds rate "
                "by 1/2 percentage point to 4-3/4 to 5 percent. "
                "Inflation has made progress toward the 2 percent objective."
            ),
            score=0.92,
            source="fomc_20240918",
            lang="en",
            metadata={"date": "2024-09-18", "doc_type": "fomc_minutes"},
        ),
        DocumentChunk(
            id="fomc_20240918_chunk_002",
            text=(
                "Job gains have slowed, and the unemployment rate has moved up "
                "but remains low. The economic outlook is uncertain."
            ),
            score=0.87,
            source="fomc_20240918",
            lang="en",
            metadata={"date": "2024-09-18", "doc_type": "fomc_minutes"},
        ),
        DocumentChunk(
            id="sbv_20240601_chunk_001",
            text=(
                "Ngan hang Nha nuoc Viet Nam dieu chinh lai suat tai cap xuat "
                "cho vay qua dem len 4.5% nham on dinh thi truong tien te."
            ),
            score=0.79,
            source="sbv_20240601",
            lang="vi",
            metadata={"date": "2024-06-01", "doc_type": "sbv_decision"},
        ),
    ]


# ---------------------------------------------------------------------------
# Gold fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_gold_price_rows() -> list[GoldPriceRow]:
    """1 GoldPriceRow at late-2024 LBMA spot price."""
    return [
        GoldPriceRow(
            source="LBMA",
            price_usd=2_580.0,
            data_as_of=_AS_OF,
        ),
    ]


@pytest.fixture()
def mock_gold_etf_rows() -> list[GoldEtfRow]:
    """2 GoldEtfRow instances (GLD weekly + daily)."""
    return [
        GoldEtfRow(
            ticker="GLD",
            resolution="weekly",
            open=236.10,
            high=239.80,
            low=235.40,
            close=238.50,
            volume=15_420_000,
            data_as_of=_AS_OF,
        ),
        GoldEtfRow(
            ticker="IAU",
            resolution="weekly",
            open=47.90,
            high=48.60,
            low=47.70,
            close=48.30,
            volume=8_230_000,
            data_as_of=_AS_OF,
        ),
    ]


# ---------------------------------------------------------------------------
# Composite state fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_equity_state(
    mock_fred_rows,
    mock_regime_analogues,
    mock_structure_marker_rows,
    mock_fundamentals_rows,
    mock_document_chunks,
    mock_gold_price_rows,
    mock_gold_etf_rows,
) -> ReportState:
    """
    Complete ReportState dict for asset_type='equity' (VHM).
    All node outputs are None — ready for individual node execution.
    """
    return ReportState(
        ticker="VHM",
        asset_type="equity",
        fred_rows=mock_fred_rows,
        regime_analogues=mock_regime_analogues,
        macro_docs=mock_document_chunks,
        fundamentals_rows=mock_fundamentals_rows,
        structure_marker_rows=mock_structure_marker_rows,
        gold_price_rows=[],
        gold_etf_rows=[],
        earnings_docs=mock_document_chunks[:1],
        macro_regime_output=None,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )


@pytest.fixture()
def base_gold_state(
    mock_fred_rows,
    mock_regime_analogues,
    mock_gold_price_rows,
    mock_gold_etf_rows,
    mock_document_chunks,
) -> ReportState:
    """
    Complete ReportState dict for asset_type='gold'.
    All node outputs are None — ready for individual node execution.
    """
    return ReportState(
        ticker="GOLD",
        asset_type="gold",
        fred_rows=mock_fred_rows,
        regime_analogues=mock_regime_analogues,
        macro_docs=mock_document_chunks,
        fundamentals_rows=[],
        structure_marker_rows=[],
        gold_price_rows=mock_gold_price_rows,
        gold_etf_rows=mock_gold_etf_rows,
        earnings_docs=[],
        macro_regime_output=None,
        valuation_output=None,
        structure_output=None,
        entry_quality_output=None,
        grounding_result=None,
        conflict_output=None,
        retrieval_warnings=[],
    )
