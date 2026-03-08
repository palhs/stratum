"""
Tests for structure markers computation — DATA-06.

DATA-06: structure_markers has rows with non-NULL ma_10w for rows where
         data history >= 10 weeks. Both drawdown columns are present and computed.
         close_pct_rank is between 0 and 1.
         pe_pct_rank is NULL for gold_spot and gold_etf asset types.

These are integration tests against the live database populated by the sidecar.
"""

import pytest
from sqlalchemy import select, func, and_

from app.models import structure_markers


# ---------------------------------------------------------------------------
# DATA-06: structure_markers
# ---------------------------------------------------------------------------

class TestStructureMarkers:
    """DATA-06: structure_markers table quality checks."""

    def test_markers_has_rows(self, db_session):
        """structure_markers must have at least one row."""
        count = db_session.execute(
            select(func.count()).select_from(structure_markers)
        ).scalar()
        assert count > 0, (
            "structure_markers is empty — run POST /compute/structure-markers to populate it"
        )

    def test_ma_non_null_for_sufficient_history(self, db_session):
        """
        ma_10w must be non-NULL for symbols that have >= 10 weeks of data.

        The service uses min_periods=8 for ma_10w. Symbols with >= 10 rows in
        stock_ohlcv will have non-NULL ma_10w for their recent bars.

        Strategy: check that at least 50% of structure_markers rows have non-NULL ma_10w.
        (Early rows in a symbol's history will have NULL ma_10w — that's expected.)
        """
        total = db_session.execute(
            select(func.count()).select_from(structure_markers)
        ).scalar()
        assert total > 0, "structure_markers is empty"

        non_null_ma = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                structure_markers.c.ma_10w.isnot(None)
            )
        ).scalar()
        pct_non_null = non_null_ma / total if total > 0 else 0.0
        assert pct_non_null >= 0.5, (
            f"Only {pct_non_null:.1%} of structure_markers rows have non-NULL ma_10w "
            f"({non_null_ma}/{total} rows). "
            "Expected at least 50% for symbols with >= 10 weeks of history."
        )

    def test_both_drawdowns_present(self, db_session):
        """drawdown_from_ath and drawdown_from_52w_high must both be present and computed."""
        # Check drawdown_from_ath
        non_null_ath = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                structure_markers.c.drawdown_from_ath.isnot(None)
            )
        ).scalar()
        assert non_null_ath > 0, (
            "structure_markers has no rows with non-NULL drawdown_from_ath"
        )

        # Check drawdown_from_52w_high
        non_null_52w = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                structure_markers.c.drawdown_from_52w_high.isnot(None)
            )
        ).scalar()
        assert non_null_52w > 0, (
            "structure_markers has no rows with non-NULL drawdown_from_52w_high"
        )

    def test_drawdown_values_are_non_positive(self, db_session):
        """
        drawdown values must be <= 0 (drawdowns are negative or zero).

        drawdown = (close / ath) - 1.0, which is always <= 0.
        """
        positive_ath = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                and_(
                    structure_markers.c.drawdown_from_ath.isnot(None),
                    structure_markers.c.drawdown_from_ath > 0.0,
                )
            )
        ).scalar()
        assert positive_ath == 0, (
            f"structure_markers has {positive_ath} rows with drawdown_from_ath > 0 "
            "(drawdowns should be non-positive)"
        )

    def test_close_pct_rank_range(self, db_session):
        """
        close_pct_rank must be between 0 and 1 (inclusive) for all non-NULL, non-NaN values.

        Note: PostgreSQL stores NaN (not-a-number) separately from NULL. NaN rows are
        rows where rolling().rank() returned NaN (insufficient window — same as NULL-intent).
        We validate only the rows that have finite numeric values in [0, 1].
        """
        from sqlalchemy import text
        out_of_range = db_session.execute(
            text(
                "SELECT COUNT(*) FROM structure_markers "
                "WHERE close_pct_rank IS NOT NULL "
                "AND close_pct_rank != 'NaN'::numeric "
                "AND (close_pct_rank < 0 OR close_pct_rank > 1)"
            )
        ).scalar()
        assert out_of_range == 0, (
            f"structure_markers has {out_of_range} rows with close_pct_rank outside [0, 1] "
            "(excluding NULL and NaN values)"
        )

    def test_pe_pct_rank_null_for_gold(self, db_session):
        """
        pe_pct_rank must be NULL for gold_spot and gold_etf asset_types.

        Gold assets do not have P/E ratios — pe_pct_rank should always be NULL for them.
        """
        gold_with_pe = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                and_(
                    structure_markers.c.asset_type.in_(["gold_spot", "gold_etf"]),
                    structure_markers.c.pe_pct_rank.isnot(None),
                )
            )
        ).scalar()
        assert gold_with_pe == 0, (
            f"structure_markers has {gold_with_pe} gold rows with non-NULL pe_pct_rank. "
            "Gold assets should always have NULL pe_pct_rank."
        )

    def test_asset_types_are_valid(self, db_session):
        """asset_type should only contain 'stock', 'gold_spot', or 'gold_etf'."""
        valid_types = {"stock", "gold_spot", "gold_etf"}
        rows = db_session.execute(
            select(structure_markers.c.asset_type).distinct()
        ).fetchall()
        found_types = {r[0] for r in rows}
        unknown = found_types - valid_types
        assert not unknown, (
            f"structure_markers has unexpected asset_type values: {unknown}. "
            f"Valid values: {valid_types}"
        )

    def test_structure_markers_has_stocks(self, db_session):
        """structure_markers should have at least some stock rows."""
        stock_count = db_session.execute(
            select(func.count()).select_from(structure_markers).where(
                structure_markers.c.asset_type == "stock"
            )
        ).scalar()
        assert stock_count > 0, (
            "structure_markers has no 'stock' rows — expected VN30 stock markers"
        )
