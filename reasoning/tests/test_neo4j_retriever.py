"""
reasoning/tests/test_neo4j_retriever.py — Integration tests for the Neo4j retriever.
Phase 5 | Plan 02 | Requirement: RETR-01

Tests run against the live Neo4j Docker service with Phase 4 seeded data.
No mocks — locked decision.

Environment:
  NEO4J_URI defaults to bolt://localhost:7687 (host access to Docker container)
  NEO4J_PASSWORD from .env: localdev_neo4j
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()

# Use localhost for host-based test execution (Neo4j exposes 7687 on host)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "localdev_neo4j")


@pytest.fixture(scope="session")
def neo4j_graph_store():
    """
    Session-scoped Neo4j PropertyGraphStore fixture.
    Used by the retriever functions for live integration tests.
    """
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
    try:
        store = Neo4jPropertyGraphStore(
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
        )
        # Validate connectivity
        result = store.structured_query("MATCH (n:Regime) RETURN count(n) as cnt")
        assert result and result[0]["cnt"] > 0, "No Regime nodes found in Neo4j"
    except Exception as exc:
        pytest.skip(f"Neo4j not available at {NEO4J_URI}: {exc}")
    yield store


# ---------------------------------------------------------------------------
# Tests for get_all_analogues() — deterministic retrieval
# ---------------------------------------------------------------------------


class TestGetAllAnalogues:
    """Tests for get_all_analogues() — returns all HAS_ANALOGUE relationships."""

    def test_returns_non_empty_list(self, neo4j_graph_store):
        """get_all_analogues() returns a non-empty list of RegimeAnalogue objects."""
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues
        from reasoning.app.retrieval.types import RegimeAnalogue

        results = get_all_analogues(graph_store=neo4j_graph_store)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, RegimeAnalogue) for r in results)

    def test_all_analogues_have_required_fields(self, neo4j_graph_store):
        """Every RegimeAnalogue has the 5 required non-None properties."""
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues

        results = get_all_analogues(graph_store=neo4j_graph_store)
        assert len(results) > 0

        for analogue in results:
            assert analogue.similarity_score is not None, (
                f"similarity_score is None for analogue: {analogue.analogue_id}"
            )
            assert analogue.dimensions_matched is not None, (
                f"dimensions_matched is None for analogue: {analogue.analogue_id}"
            )
            assert len(analogue.dimensions_matched) > 0, (
                f"dimensions_matched is empty for analogue: {analogue.analogue_id}"
            )
            assert analogue.period_start is not None, (
                f"period_start is None for analogue: {analogue.analogue_id}"
            )
            assert analogue.period_end is not None, (
                f"period_end is None for analogue: {analogue.analogue_id}"
            )

    def test_some_analogues_have_narrative(self, neo4j_graph_store):
        """At least some RegimeAnalogue objects have a non-empty narrative string.

        Validates that Phase 4 Gemini-generated narratives were stored in Neo4j.
        """
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues

        results = get_all_analogues(graph_store=neo4j_graph_store)
        assert len(results) > 0

        narratives = [r.narrative for r in results if r.narrative and len(r.narrative) > 10]
        assert len(narratives) > 0, (
            "No analogues have narratives — Phase 4 Gemini seeding may not have run"
        )

    def test_similarity_scores_in_valid_range(self, neo4j_graph_store):
        """similarity_score values are in [0.0, 1.0] range."""
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues

        results = get_all_analogues(graph_store=neo4j_graph_store)
        assert len(results) > 0

        for analogue in results:
            assert 0.0 <= analogue.similarity_score <= 1.0, (
                f"similarity_score out of range: {analogue.similarity_score} "
                f"for analogue: {analogue.analogue_id}"
            )

    def test_source_and_analogue_ids_populated(self, neo4j_graph_store):
        """source_regime and analogue_id are non-empty strings."""
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues

        results = get_all_analogues(graph_store=neo4j_graph_store)
        assert len(results) > 0

        for analogue in results:
            assert analogue.source_regime and len(analogue.source_regime) > 0
            assert analogue.analogue_id and len(analogue.analogue_id) > 0

    def test_expected_analogue_count(self, neo4j_graph_store):
        """At least 10 analogue relationships exist (16 regimes participate, threshold 0.75).

        Phase 4 seeded 75 relationships based on seed script output.
        """
        from reasoning.app.retrieval.neo4j_retriever import get_all_analogues

        results = get_all_analogues(graph_store=neo4j_graph_store)
        assert len(results) >= 10, (
            f"Expected at least 10 analogues, got {len(results)} — "
            "check Phase 4 neo4j-analogue seed ran successfully"
        )


# ---------------------------------------------------------------------------
# Tests for get_regime_analogues() — LLM-parameterized retrieval
# ---------------------------------------------------------------------------


class TestGetRegimeAnalogues:
    """Tests for get_regime_analogues() — natural language regime query."""

    def test_returns_list_type(self, neo4j_graph_store):
        """get_regime_analogues() returns a list (may be empty if LLM not configured)."""
        from reasoning.app.retrieval.neo4j_retriever import get_regime_analogues

        # This test only validates the return type — LLM may not be available
        # get_regime_analogues falls back gracefully when LLM is not configured
        result = get_regime_analogues(
            query_text="financial crisis recession",
            limit=3,
            graph_store=neo4j_graph_store,
        )
        assert isinstance(result, list)

    def test_accepts_query_and_limit_parameters(self, neo4j_graph_store):
        """get_regime_analogues() accepts query_text and limit parameters."""
        from reasoning.app.retrieval.neo4j_retriever import get_regime_analogues

        # Should not raise
        result = get_regime_analogues(
            query_text="inflationary period 2022",
            limit=5,
            graph_store=neo4j_graph_store,
        )
        assert isinstance(result, list)
        # If results returned, validate they are RegimeAnalogue objects
        if result:
            from reasoning.app.retrieval.types import RegimeAnalogue
            assert all(isinstance(r, RegimeAnalogue) for r in result)

    def test_returned_analogues_have_required_fields(self, neo4j_graph_store):
        """RegimeAnalogue objects from get_regime_analogues() have required fields."""
        from reasoning.app.retrieval.neo4j_retriever import get_regime_analogues

        result = get_regime_analogues(
            query_text="rate hikes inflation monetary policy tightening",
            limit=3,
            graph_store=neo4j_graph_store,
        )
        # Only validate field presence if results returned
        for analogue in result:
            assert analogue.similarity_score is not None
            assert analogue.dimensions_matched is not None
            assert analogue.period_start is not None
            assert analogue.period_end is not None


# ---------------------------------------------------------------------------
# Tests for NoDataError behavior
# ---------------------------------------------------------------------------


class TestNoDataError:
    """Tests for NoDataError being raised on empty results."""

    def test_no_data_error_on_empty_query(self, neo4j_graph_store):
        """NoDataError is raised when structured_query returns empty results."""
        from reasoning.app.retrieval.neo4j_retriever import _query_analogues_by_cypher
        from reasoning.app.retrieval.types import NoDataError

        # Use a Cypher query that matches nothing
        impossible_cypher = (
            "MATCH (a:Regime {id: '__nonexistent_regime_xyz__'})"
            "-[r:HAS_ANALOGUE]->(b:Regime) "
            "RETURN a.id AS source_id, b.id AS analogue_id, "
            "b.name AS analogue_name, r.similarity_score, "
            "r.dimensions_matched, r.period_start, r.period_end, r.narrative"
        )
        with pytest.raises(NoDataError):
            _query_analogues_by_cypher(
                graph_store=neo4j_graph_store,
                cypher=impossible_cypher,
                source_name="test_empty_query",
            )
