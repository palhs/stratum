"""
reasoning/app/retrieval/qdrant_retriever.py — Qdrant hybrid dense+sparse retriever.
Phase 5 | Plan 03 | Requirements: RETR-02, RETR-04

Provides hybrid search (dense + sparse BM25) over macro_docs_v1 and earnings_docs_v1
Qdrant collections. Both collections use named vectors:
  - text-dense:  384-dim Cosine (BAAI/bge-small-en-v1.5)
  - text-sparse: sparse IDF (BM25 via Qdrant/bm25 fastembed model)

Collection-specific alpha weights (dense vs sparse balance):
  - macro_docs_v1:    alpha=0.7 (favors dense — FOMC policy language is semantically rich)
  - earnings_docs_v1: alpha=0.5 (balanced — earnings docs have keyword-heavy numbers + narrative)

Design decisions (locked in Phase 5 Research and Plan):
  - Language filter applied via MetadataFilters at retriever level
  - Module-level QdrantClient creation (reused across calls unless overridden)
  - NoDataError raised on empty results — Phase 6 nodes catch and handle gracefully
  - Transient Qdrant failures propagate to Phase 6 (LangGraph checkpoint/retry handles them)
  - now_override parameter enables deterministic freshness testing
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

from qdrant_client import QdrantClient

from reasoning.app.retrieval.freshness import FRESHNESS_THRESHOLDS, check_freshness
from reasoning.app.retrieval.types import DocumentChunk, NoDataError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client (reused across calls unless overridden for testing)
# ---------------------------------------------------------------------------

_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    """Return the module-level Qdrant client, creating it if not yet initialized."""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "qdrant"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            api_key=os.getenv("QDRANT_API_KEY") or None,
            https=False,
        )
    return _client


# ---------------------------------------------------------------------------
# Collection configuration
# ---------------------------------------------------------------------------

_MACRO_COLLECTION = "macro_docs_v1"
_EARNINGS_COLLECTION = "earnings_docs_v1"

# Alpha controls dense vs sparse weight in hybrid Relative Score Fusion.
# 1.0 = dense only, 0.0 = sparse only.
_MACRO_ALPHA = 0.7       # Dense-favored: FOMC policy language is semantically rich
_EARNINGS_ALPHA = 0.5    # Balanced: earnings docs mix keyword-heavy numbers + narrative

# Freshness thresholds (days) — from FRESHNESS_THRESHOLDS constants
_MACRO_FRESHNESS_THRESHOLD = FRESHNESS_THRESHOLDS["qdrant_macro_docs"]        # 45 days
_EARNINGS_FRESHNESS_THRESHOLD = FRESHNESS_THRESHOLDS["qdrant_earnings_docs"]  # 120 days


# ---------------------------------------------------------------------------
# LlamaIndex node to DocumentChunk conversion
# ---------------------------------------------------------------------------


def _node_to_chunk(node_with_score, warnings: list[str]) -> DocumentChunk:
    """
    Convert a LlamaIndex NodeWithScore to a DocumentChunk.

    Args:
        node_with_score: LlamaIndex NodeWithScore object from retriever.
        warnings:        Pre-computed freshness warnings to attach to chunk.

    Returns:
        DocumentChunk with fields populated from the node payload.
    """
    node = node_with_score.node
    metadata = node.metadata or {}
    return DocumentChunk(
        id=node.id_,
        text=node.text or "",
        score=float(node_with_score.score or 0.0),
        source=metadata.get("source", ""),
        lang=metadata.get("lang", ""),
        metadata=metadata,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Shared hybrid retrieval helper
# ---------------------------------------------------------------------------


def _run_hybrid_search(
    query: str,
    collection_name: str,
    lang: str,
    top_k: int,
    alpha: float,
    client: QdrantClient,
    extra_filters: Optional[list] = None,
) -> list:
    """
    Run a hybrid dense+sparse search against the given Qdrant collection.

    Args:
        query:           Natural language query string.
        collection_name: Qdrant collection name (e.g., "macro_docs_v1").
        lang:            Language filter value (e.g., "en").
        top_k:           Number of results to return.
        alpha:           Dense weight in hybrid fusion (0.0-1.0).
        client:          QdrantClient instance to use.
        extra_filters:   Additional MetadataFilter objects to combine with lang filter.

    Returns:
        List of LlamaIndex NodeWithScore objects.
    """
    from llama_index.core import VectorStoreIndex
    from llama_index.core.vector_stores.types import (
        MetadataFilter,
        MetadataFilters,
        FilterOperator,
        VectorStoreQueryMode,
    )
    from llama_index.embeddings.fastembed import FastEmbedEmbedding
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from llama_index.vector_stores.qdrant.utils import fastembed_sparse_encoder

    # Build language filter
    lang_filter = MetadataFilter(
        key="lang",
        value=lang,
        operator=FilterOperator.EQ,
    )

    all_filters = [lang_filter]
    if extra_filters:
        all_filters.extend(extra_filters)

    metadata_filters = MetadataFilters(filters=all_filters)

    # Provide explicit BM25 sparse encoder functions to bypass auto-detection.
    # LlamaIndex 0.9.x treats "text-sparse" as the "old format" and falls back
    # to SPLADE (which requires torch). We use fastembed BM25 explicitly since
    # our seed scripts compute BM25 sparse vectors at index time.
    bm25_encoder = fastembed_sparse_encoder(model_name="Qdrant/bm25")

    # Create QdrantVectorStore with hybrid search enabled
    # Named vectors must match collection schema: text-dense + text-sparse
    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=bm25_encoder,
        sparse_query_fn=bm25_encoder,
        dense_vector_name="text-dense",
        sparse_vector_name="text-sparse",
    )

    # Create index over the existing collection (no re-indexing)
    embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )

    # Configure hybrid retriever with alpha for dense/sparse weighting
    retriever = index.as_retriever(
        similarity_top_k=top_k,
        sparse_top_k=top_k * 2,
        vector_store_query_mode=VectorStoreQueryMode.HYBRID,
        alpha=alpha,
        filters=metadata_filters,
    )

    return retriever.retrieve(query)


# ---------------------------------------------------------------------------
# Public retriever functions
# ---------------------------------------------------------------------------


def search_macro_docs(
    query: str,
    lang: str = "en",
    top_k: int = 5,
    now_override: Optional[datetime] = None,
    client: Optional[QdrantClient] = None,
) -> list[DocumentChunk]:
    """
    Hybrid dense+sparse search over macro_docs_v1 (FOMC minutes + SBV policy reports).

    Args:
        query:        Natural language query string (e.g., "Federal Reserve rate decision").
        lang:         Language filter — returns only documents with matching lang payload field.
                      Defaults to "en". FOMC documents are lang="en"; SBV docs vary by seeding.
        top_k:        Number of results to return (default 5, locked decision).
        now_override: Override current time for freshness checking (testing only).
        client:       Override the module-level QdrantClient (testing only).

    Returns:
        list[DocumentChunk] with score, text, source, lang, metadata, and freshness warnings.

    Raises:
        NoDataError: If the retriever returns 0 results for the given query and filters.
    """
    _client = client or _get_client()
    start_ms = time.monotonic()

    nodes = _run_hybrid_search(
        query=query,
        collection_name=_MACRO_COLLECTION,
        lang=lang,
        top_k=top_k,
        alpha=_MACRO_ALPHA,
        client=_client,
    )

    elapsed_ms = int((time.monotonic() - start_ms) * 1000)
    logger.info(
        "search_macro_docs: query=%r collection=%s lang=%s results=%d elapsed_ms=%d",
        query[:100],
        _MACRO_COLLECTION,
        lang,
        len(nodes),
        elapsed_ms,
    )

    if not nodes:
        raise NoDataError(
            f"search_macro_docs: no results for query={query!r} lang={lang!r} "
            f"in collection {_MACRO_COLLECTION}"
        )

    chunks = []
    for node_with_score in nodes:
        # Extract document_date from payload for freshness check
        metadata = node_with_score.node.metadata or {}
        document_date_str = metadata.get("document_date")

        warnings: list[str] = []
        if document_date_str:
            try:
                # document_date is stored as ISO date string (YYYY-MM-DD)
                doc_date = datetime.fromisoformat(str(document_date_str))
                warnings = check_freshness(
                    data_as_of=doc_date,
                    threshold_days=_MACRO_FRESHNESS_THRESHOLD,
                    source_name="qdrant_macro_docs",
                    now_override=now_override,
                )
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "search_macro_docs: could not parse document_date=%r: %s",
                    document_date_str,
                    exc,
                )

        chunks.append(_node_to_chunk(node_with_score, warnings))

    return chunks


def search_earnings_docs(
    query: str,
    ticker: Optional[str] = None,
    lang: str = "en",
    top_k: int = 5,
    now_override: Optional[datetime] = None,
    client: Optional[QdrantClient] = None,
) -> list[DocumentChunk]:
    """
    Hybrid dense+sparse search over earnings_docs_v1 (VN30 quarterly/annual reports).

    Args:
        query:        Natural language query string (e.g., "revenue growth profit margin").
        ticker:       Optional VN30 ticker filter (e.g., "FPT", "VNM"). Restricts results
                      to that ticker's documents. If None, searches all earnings docs.
        lang:         Language filter — returns only documents with matching lang payload field.
                      Defaults to "en". Only 12 large-cap VN30 tickers have lang=en data.
        top_k:        Number of results to return (default 5, locked decision).
        now_override: Override current time for freshness checking (testing only).
        client:       Override the module-level QdrantClient (testing only).

    Returns:
        list[DocumentChunk] with score, text, source, lang, metadata, and freshness warnings.

    Raises:
        NoDataError: If the retriever returns 0 results for the given query and filters.
    """
    from llama_index.core.vector_stores.types import MetadataFilter, FilterOperator

    _client = client or _get_client()
    start_ms = time.monotonic()

    extra_filters = []
    if ticker:
        extra_filters.append(
            MetadataFilter(
                key="ticker",
                value=ticker,
                operator=FilterOperator.EQ,
            )
        )

    nodes = _run_hybrid_search(
        query=query,
        collection_name=_EARNINGS_COLLECTION,
        lang=lang,
        top_k=top_k,
        alpha=_EARNINGS_ALPHA,
        client=_client,
        extra_filters=extra_filters,
    )

    elapsed_ms = int((time.monotonic() - start_ms) * 1000)
    logger.info(
        "search_earnings_docs: query=%r collection=%s ticker=%r lang=%s results=%d elapsed_ms=%d",
        query[:100],
        _EARNINGS_COLLECTION,
        ticker,
        lang,
        len(nodes),
        elapsed_ms,
    )

    if not nodes:
        raise NoDataError(
            f"search_earnings_docs: no results for query={query!r} ticker={ticker!r} "
            f"lang={lang!r} in collection {_EARNINGS_COLLECTION}"
        )

    chunks = []
    for node_with_score in nodes:
        metadata = node_with_score.node.metadata or {}
        document_date_str = metadata.get("document_date")

        warnings: list[str] = []
        if document_date_str:
            try:
                doc_date = datetime.fromisoformat(str(document_date_str))
                warnings = check_freshness(
                    data_as_of=doc_date,
                    threshold_days=_EARNINGS_FRESHNESS_THRESHOLD,
                    source_name="qdrant_earnings_docs",
                    now_override=now_override,
                )
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "search_earnings_docs: could not parse document_date=%r: %s",
                    document_date_str,
                    exc,
                )

        chunks.append(_node_to_chunk(node_with_score, warnings))

    return chunks
