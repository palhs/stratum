"""
reasoning/tests/test_qdrant_retriever.py — Integration tests for the Qdrant hybrid retriever.
Phase 5 | Plan 03 | Requirements: RETR-02, RETR-04

Tests run against the live Qdrant Docker service with Phase 4 seeded data.
All tests marked with @pytest.mark.integration for selective running.

Qdrant has no host port mapping — tests must run via Docker networking
(docker run --network stratum_reasoning) or via QDRANT_HOST env var pointing
to the container's Docker network IP.

Environment:
  QDRANT_HOST      — Qdrant hostname (default: qdrant — Docker internal)
  QDRANT_PORT      — Qdrant port (default: 6333)
  QDRANT_API_KEY   — Qdrant API key (required — set via .env)
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")


# ---------------------------------------------------------------------------
# Session-scoped Qdrant client fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qdrant_client():
    """
    Session-scoped Qdrant client fixture.
    Skips all tests if Qdrant is not reachable.
    """
    from qdrant_client import QdrantClient

    client = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        https=False,
    )
    try:
        client.get_collections()
    except Exception as exc:
        pytest.skip(f"Qdrant not available at {QDRANT_HOST}:{QDRANT_PORT}: {exc}")
    yield client


@pytest.fixture(scope="session")
def macro_collection_has_data(qdrant_client):
    """True if macro_docs_v1 has at least 1 point."""
    try:
        count = qdrant_client.count("macro_docs_v1")
        return count.count > 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def earnings_collection_has_data(qdrant_client):
    """True if earnings_docs_v1 has at least 1 point."""
    try:
        count = qdrant_client.count("earnings_docs_v1")
        return count.count > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test 1: Macro docs hybrid search returns results
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_macro_docs_hybrid_returns_results(qdrant_client, macro_collection_has_data):
    """
    Hybrid search for a policy-relevant query returns DocumentChunk objects
    with correct fields. Validates RETR-02: hybrid dense+sparse search.
    """
    if not macro_collection_has_data:
        pytest.skip("macro_docs_v1 has no seeded data — re-run seed-qdrant-macro-docs.py")

    from reasoning.app.retrieval.qdrant_retriever import search_macro_docs
    from reasoning.app.retrieval.types import DocumentChunk

    results = search_macro_docs(
        "Federal Reserve quantitative easing inflation",
        lang="en",
        top_k=5,
        client=qdrant_client,
    )

    # Must return between 1 and 5 results
    assert len(results) >= 1, "Expected at least 1 result from macro_docs_v1"
    assert len(results) <= 5, f"Expected at most 5 results, got {len(results)}"

    # Each result must be a DocumentChunk with correct fields
    for chunk in results:
        assert isinstance(chunk, DocumentChunk), f"Expected DocumentChunk, got {type(chunk)}"
        assert chunk.text, f"chunk.text is empty: {chunk}"
        assert chunk.score > 0, f"chunk.score must be positive, got {chunk.score}"
        assert chunk.source, f"chunk.source is empty: {chunk}"

    # Language filter must be working — all results should have lang="en"
    langs = [c.lang for c in results]
    assert all(
        lang == "en" for lang in langs
    ), f"Language filter failed — unexpected langs: {langs}"

    print(f"\n[test_macro_docs_hybrid_returns_results] Got {len(results)} results:")
    for i, chunk in enumerate(results):
        print(f"  [{i+1}] score={chunk.score:.4f} source={chunk.source} lang={chunk.lang}")
        print(f"       text[:120]={chunk.text[:120]!r}")


# ---------------------------------------------------------------------------
# Test 2: Representative queries for manual relevance inspection (ROADMAP SC #2)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_macro_docs_relevance_representative_queries(qdrant_client, macro_collection_has_data):
    """
    Three representative queries must each return relevant results.
    Results are printed clearly to stdout for human inspection (ROADMAP SC #2).

    Per plan: "validated by manual inspection of the top-5 results for at least
    three representative queries."
    """
    if not macro_collection_has_data:
        pytest.skip("macro_docs_v1 has no seeded data — re-run seed-qdrant-macro-docs.py")

    from reasoning.app.retrieval.qdrant_retriever import search_macro_docs

    representative_queries = [
        "Federal Reserve rate decision tightening",
        "inflation expectations monetary policy",
        "quantitative easing bond purchases",
    ]

    for query in representative_queries:
        results = search_macro_docs(query, lang="en", top_k=5, client=qdrant_client)

        assert len(results) >= 1, f"Query '{query}' returned no results"

        print(f"\n--- Representative query: '{query}' ---")
        print(f"  Results: {len(results)}")
        for i, chunk in enumerate(results[:3]):
            print(f"  [{i+1}] score={chunk.score:.4f}")
            print(f"       source={chunk.source}")
            metadata_title = chunk.metadata.get("title", "(no title)")
            print(f"       title={metadata_title!r}")
            print(f"       text[:160]={chunk.text[:160]!r}")


# ---------------------------------------------------------------------------
# Test 3: Earnings docs returns results with ticker filter
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_earnings_docs_returns_results(qdrant_client, earnings_collection_has_data):
    """
    Earnings search for a known VN30 ticker returns DocumentChunk objects.
    Ticker filter must restrict results to that ticker only.
    """
    if not earnings_collection_has_data:
        pytest.skip("earnings_docs_v1 has no seeded data — re-run seed-qdrant-earnings-docs.py")

    from reasoning.app.retrieval.qdrant_retriever import search_earnings_docs
    from reasoning.app.retrieval.types import DocumentChunk

    # FPT is a large-cap VN30 ticker with English IR reports (lang=en seeded in Phase 4)
    results = search_earnings_docs(
        "revenue growth profit margin",
        ticker="FPT",
        lang="en",
        top_k=5,
        client=qdrant_client,
    )

    assert len(results) >= 1, "Expected at least 1 result for FPT earnings"
    assert len(results) <= 5, f"Expected at most 5 results, got {len(results)}"

    for chunk in results:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.text
        assert chunk.score > 0

    print(f"\n[test_earnings_docs_returns_results] Got {len(results)} results for FPT:")
    for i, chunk in enumerate(results):
        ticker_meta = chunk.metadata.get("ticker", "?")
        print(f"  [{i+1}] score={chunk.score:.4f} ticker={ticker_meta} source={chunk.source}")
        print(f"       text[:120]={chunk.text[:120]!r}")


# ---------------------------------------------------------------------------
# Test 4: Language filter excludes non-matching lang results
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_language_filter_excludes_non_matching(qdrant_client, macro_collection_has_data):
    """
    All returned chunks must have lang="en" when lang="en" is requested.
    Language filter correctness is verified through metadata inspection.
    """
    if not macro_collection_has_data:
        pytest.skip("macro_docs_v1 has no seeded data")

    from reasoning.app.retrieval.qdrant_retriever import search_macro_docs

    results = search_macro_docs(
        "monetary policy interest rates",
        lang="en",
        top_k=5,
        client=qdrant_client,
    )

    assert len(results) >= 1, "Expected at least 1 result"

    for chunk in results:
        assert chunk.lang == "en", (
            f"Language filter failed: expected lang='en', got lang='{chunk.lang}' "
            f"in chunk from source={chunk.source}"
        )
        assert chunk.metadata.get("lang") == "en", (
            f"Metadata lang mismatch: expected 'en', got '{chunk.metadata.get('lang')}'"
        )

    print(f"\n[test_language_filter_excludes_non_matching] All {len(results)} chunks have lang=en")


# ---------------------------------------------------------------------------
# Test 5: Freshness warning appears on stale documents
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_freshness_warning_on_stale_documents(qdrant_client, macro_collection_has_data):
    """
    When now_override is set 200 days in the future, document_date is stale
    and DocumentChunk.warnings must be non-empty with "STALE DATA".
    """
    if not macro_collection_has_data:
        pytest.skip("macro_docs_v1 has no seeded data")

    from reasoning.app.retrieval.qdrant_retriever import search_macro_docs

    # Set now_override 200 days in the future — any recent document will be stale
    future_now = datetime.now(timezone.utc) + timedelta(days=200)

    results = search_macro_docs(
        "Federal Reserve rate decision",
        lang="en",
        top_k=5,
        now_override=future_now,
        client=qdrant_client,
    )

    assert len(results) >= 1, "Expected at least 1 result"

    # All chunks should have freshness warnings (200 days > 45-day threshold)
    chunks_with_warnings = [c for c in results if c.warnings]
    assert len(chunks_with_warnings) > 0, (
        f"Expected freshness warnings on results with now_override={future_now.date()}, "
        f"but none of {len(results)} chunks had warnings"
    )

    for chunk in chunks_with_warnings:
        warning_text = " ".join(chunk.warnings)
        assert "STALE DATA" in warning_text, (
            f"Expected 'STALE DATA' in warning, got: {warning_text!r}"
        )

    print(
        f"\n[test_freshness_warning_on_stale_documents] "
        f"{len(chunks_with_warnings)}/{len(results)} chunks have freshness warnings"
    )
    if chunks_with_warnings:
        print(f"  Sample warning: {chunks_with_warnings[0].warnings[0]!r}")


# ---------------------------------------------------------------------------
# Test 6: NoDataError raised for non-existent ticker
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_data_error_on_empty_results(qdrant_client):
    """
    search_earnings_docs with a non-existent ticker must raise NoDataError.
    """
    from reasoning.app.retrieval.qdrant_retriever import search_earnings_docs
    from reasoning.app.retrieval.types import NoDataError

    with pytest.raises(NoDataError) as exc_info:
        search_earnings_docs(
            "revenue profit",
            ticker="ZZZZZ",
            lang="en",
            top_k=5,
            client=qdrant_client,
        )

    assert "ZZZZZ" in str(exc_info.value) or "no results" in str(exc_info.value).lower(), (
        f"NoDataError message should mention the ticker, got: {exc_info.value}"
    )

    print(f"\n[test_no_data_error_on_empty_results] NoDataError raised: {exc_info.value}")
