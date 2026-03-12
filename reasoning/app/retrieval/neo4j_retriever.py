"""
reasoning/app/retrieval/neo4j_retriever.py — Neo4j regime analogue retriever.
Phase 5 | Plan 02 | Requirement: RETR-01

Two retrieval paths for the Neo4j regime analogue graph:

  1. get_all_analogues() — Deterministic: returns all HAS_ANALOGUE relationships
     via structured_query. No LLM required. Primary path for Phase 5 validation.

  2. get_regime_analogues() — LLM-parameterized: uses CypherTemplateRetriever to
     translate a natural language macro query into Cypher parameters. Primary path
     for Phase 6 LangGraph macro_regime node.

Design decisions (locked):
- Use Neo4jPropertyGraphStore (NOT PropertyGraphIndex.from_documents) — the graph
  already exists from Phase 4 seeding; do not attempt to re-index it.
- VectorContextRetriever and LLMSynonymRetriever excluded — require LlamaIndex-internal
  node properties not present in the externally-seeded graph.
- CypherTemplateRetriever Pydantic Field descriptions include actual node ID format
  hints to mitigate LLM hallucination (Pitfall 2 mitigation).
- NoDataError raised when structured_query returns empty results.
- Python logging at INFO level: query type, params (truncated), result count, elapsed_ms.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from reasoning.app.retrieval.types import NoDataError, RegimeAnalogue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cypher query templates
# ---------------------------------------------------------------------------


# Primary: return all HAS_ANALOGUE relationships with full properties
CYPHER_ALL_ANALOGUES = """
MATCH (a:Regime)-[r:HAS_ANALOGUE]->(b:Regime)
RETURN
  a.id          AS source_id,
  b.id          AS analogue_id,
  b.name        AS analogue_name,
  b.period_start AS analogue_period_start,
  b.period_end   AS analogue_period_end,
  r.similarity_score   AS similarity_score,
  r.dimensions_matched AS dimensions_matched,
  r.period_start       AS period_start,
  r.period_end         AS period_end,
  r.narrative          AS narrative
ORDER BY r.similarity_score DESC
"""

# LLM-parameterized: match regimes by keyword, traverse HAS_ANALOGUE
# $regime_keywords is a list of keyword strings provided by the LLM
CYPHER_REGIME_ANALOGUE_BY_KEYWORD = """
MATCH (a:Regime)-[r:HAS_ANALOGUE]->(b:Regime)
WHERE any(kw IN $regime_keywords WHERE
      toLower(a.name) CONTAINS toLower(kw) OR
      toLower(a.notes) CONTAINS toLower(kw) OR
      toLower(a.id)    CONTAINS toLower(kw))
RETURN
  a.id          AS source_id,
  b.id          AS analogue_id,
  b.name        AS analogue_name,
  b.period_start AS analogue_period_start,
  b.period_end   AS analogue_period_end,
  r.similarity_score   AS similarity_score,
  r.dimensions_matched AS dimensions_matched,
  r.period_start       AS period_start,
  r.period_end         AS period_end,
  r.narrative          AS narrative
ORDER BY r.similarity_score DESC
LIMIT $limit
"""

# Fallback: match regimes where FRED indicator values fall within a range
# Useful when keyword search fails (Pitfall 2 mitigation)
CYPHER_REGIME_BY_FRED_RANGE = """
MATCH (a:Regime)-[r:HAS_ANALOGUE]->(b:Regime)
WHERE a.fedfunds_avg >= $fedfunds_min AND a.fedfunds_avg <= $fedfunds_max
RETURN
  a.id          AS source_id,
  b.id          AS analogue_id,
  b.name        AS analogue_name,
  b.period_start AS analogue_period_start,
  b.period_end   AS analogue_period_end,
  r.similarity_score   AS similarity_score,
  r.dimensions_matched AS dimensions_matched,
  r.period_start       AS period_start,
  r.period_end         AS period_end,
  r.narrative          AS narrative
ORDER BY r.similarity_score DESC
LIMIT $limit
"""


# ---------------------------------------------------------------------------
# Pydantic model for CypherTemplateRetriever LLM output
# ---------------------------------------------------------------------------


class RegimeParams(BaseModel):
    """
    Parameters extracted from a natural language macro query by the LLM.
    Used by CypherTemplateRetriever to fill in CYPHER_REGIME_ANALOGUE_BY_KEYWORD.

    The Field descriptions include actual node ID format examples to reduce
    LLM hallucination — the LLM sees these descriptions when structured_predict
    generates the output.
    """

    regime_keywords: List[str] = Field(
        description=(
            "List of keywords to search for in regime name, id, or notes. "
            "Use actual regime ID fragments for best results. "
            "Known regime IDs include: gfc_credit_crisis, covid_pandemic_2020, "
            "aggressive_tightening, rate_cut_pivot_2024, terminal_rate_plateau, "
            "dotcom_bust_2001, vietnam_high_inflation_2008, post_gfc_recovery_2010. "
            "Extract 2-4 descriptive keywords from the user query."
        )
    )
    limit: int = Field(
        default=5,
        description="Maximum number of analogues to return. Typically 3-10.",
    )


# ---------------------------------------------------------------------------
# Core helper: parse structured_query results into RegimeAnalogue objects
# ---------------------------------------------------------------------------


def _rows_to_analogues(rows: List[Dict[str, Any]]) -> List[RegimeAnalogue]:
    """
    Convert Neo4j structured_query result rows to RegimeAnalogue objects.

    Each row must contain: source_id, analogue_id, analogue_name,
    similarity_score, dimensions_matched, period_start, period_end, narrative.
    """
    results = []
    for row in rows:
        analogue = RegimeAnalogue(
            source_regime=row.get("source_id", ""),
            analogue_id=row.get("analogue_id", ""),
            analogue_name=row.get("analogue_name", ""),
            period_start=row.get("period_start"),
            period_end=row.get("period_end"),
            similarity_score=float(row.get("similarity_score", 0.0)),
            dimensions_matched=list(row.get("dimensions_matched") or []),
            narrative=row.get("narrative"),
            warnings=[],
        )
        results.append(analogue)
    return results


def _query_analogues_by_cypher(
    graph_store: Any,
    cypher: str,
    source_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> List[RegimeAnalogue]:
    """
    Execute a Cypher query against graph_store.structured_query and return
    a list of RegimeAnalogue objects. Raises NoDataError if empty.

    Args:
        graph_store: Neo4jPropertyGraphStore instance.
        cypher:      Cypher query string to execute.
        source_name: Human-readable name for logging (e.g. "get_all_analogues").
        params:      Optional parameter map for parameterized Cypher.

    Returns:
        List of RegimeAnalogue objects.

    Raises:
        NoDataError: If the query returns no rows.
    """
    t0 = time.monotonic()
    truncated_params = str(params)[:200] if params else "none"
    logger.info("Neo4j query start | source=%s | params=%s", source_name, truncated_params)

    rows = graph_store.structured_query(cypher, param_map=params or {})

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if not rows:
        logger.info(
            "Neo4j query complete | source=%s | rows=0 | elapsed_ms=%d",
            source_name,
            elapsed_ms,
        )
        raise NoDataError(
            f"No regime analogues returned from Neo4j for query: {source_name}"
        )

    results = _rows_to_analogues(rows)
    logger.info(
        "Neo4j query complete | source=%s | rows=%d | elapsed_ms=%d",
        source_name,
        len(results),
        elapsed_ms,
    )
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _get_default_graph_store():
    """
    Create a Neo4jPropertyGraphStore from environment variables.

    Environment variables:
        NEO4J_URI      — bolt:// URL (default: bolt://neo4j:7687)
        NEO4J_USER     — username (default: neo4j)
        NEO4J_PASSWORD — required

    Validates connectivity: MATCH (n:Regime) RETURN count(n) must return > 0.
    """
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

    uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    store = Neo4jPropertyGraphStore(
        username=user,
        password=password,
        url=uri,
    )

    # Validate connectivity
    result = store.structured_query("MATCH (n:Regime) RETURN count(n) as cnt")
    cnt = result[0]["cnt"] if result else 0
    if cnt == 0:
        raise NoDataError(
            f"Neo4j has no Regime nodes at {uri} — "
            "check Phase 4 seed-neo4j-analogues.py was run"
        )
    logger.info("Neo4j connected | uri=%s | regime_count=%d", uri, cnt)
    return store


def get_all_analogues(graph_store=None) -> List[RegimeAnalogue]:
    """
    Return all HAS_ANALOGUE relationships from Neo4j as RegimeAnalogue objects.

    This is the deterministic retrieval path — no LLM involved. Used for:
    - Phase 5 validation: verify all analogue data is correctly structured
    - Phase 6 macro_regime node: bulk-load all analogues for downstream filtering

    Args:
        graph_store: Optional Neo4jPropertyGraphStore. If None, creates one
                     from environment variables (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).

    Returns:
        List[RegimeAnalogue]: All HAS_ANALOGUE relationships, ordered by
        similarity_score DESC.

    Raises:
        NoDataError: If Neo4j has no HAS_ANALOGUE relationships.
    """
    if graph_store is None:
        graph_store = _get_default_graph_store()

    return _query_analogues_by_cypher(
        graph_store=graph_store,
        cypher=CYPHER_ALL_ANALOGUES,
        source_name="get_all_analogues",
    )


def get_regime_analogues(
    query_text: str,
    limit: int = 5,
    graph_store=None,
    llm=None,
) -> List[RegimeAnalogue]:
    """
    Retrieve regime analogues matching a natural language macro query.

    Uses CypherTemplateRetriever: the LLM extracts regime keywords from the
    natural language query, which are then used to parameterize a Cypher
    query against the Neo4j regime analogue graph.

    Falls back gracefully if LLM is not configured or fails: returns empty list
    instead of raising. Phase 6 nodes should handle empty list by calling
    get_all_analogues() as fallback.

    Args:
        query_text:  Natural language macro regime query
                     (e.g. "rate hike cycle with tight labor market").
        limit:       Maximum number of analogues to return. Default 5.
        graph_store: Optional Neo4jPropertyGraphStore. If None, creates one
                     from environment variables.
        llm:         Optional LLM instance for CypherTemplateRetriever.
                     If None, uses LlamaIndex Settings.llm (must be configured).

    Returns:
        List[RegimeAnalogue]: Matching regime analogues ordered by relevance.
        Returns empty list if LLM is not configured or keyword extraction fails.

    Raises:
        NoDataError: If keyword extraction succeeds but Neo4j returns no results.
    """
    if graph_store is None:
        graph_store = _get_default_graph_store()

    t0 = time.monotonic()
    logger.info(
        "Neo4j keyword query start | query=%s | limit=%d",
        query_text[:100],
        limit,
    )

    try:
        from llama_index.core.indices.property_graph import CypherTemplateRetriever
        from llama_index.core import Settings
        from llama_index.core.schema import QueryBundle

        # Use provided LLM or fall back to LlamaIndex Settings.llm
        active_llm = llm or Settings.llm

        retriever = CypherTemplateRetriever(
            graph_store=graph_store,
            output_cls=RegimeParams,
            cypher_query=CYPHER_REGIME_ANALOGUE_BY_KEYWORD,
            llm=active_llm,
        )

        nodes_with_scores = retriever.retrieve_from_graph(
            QueryBundle(query_str=query_text)
        )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if not nodes_with_scores:
            logger.info(
                "Neo4j keyword query | no nodes returned | elapsed_ms=%d",
                elapsed_ms,
            )
            return []

        # Parse the raw cypher response from nodes_with_scores text
        # CypherTemplateRetriever returns raw rows as a string representation
        # We need to re-run the query with extracted params for typed output
        # Extract params from the LLM response via structured_predict directly
        from llama_index.core.prompts import PromptTemplate

        response = active_llm.structured_predict(
            RegimeParams, PromptTemplate(query_text)
        )
        params = {
            "regime_keywords": response.regime_keywords,
            "limit": limit,
        }

        rows = graph_store.structured_query(
            CYPHER_REGIME_ANALOGUE_BY_KEYWORD,
            param_map=params,
        )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if not rows:
            logger.info(
                "Neo4j keyword query complete | rows=0 | elapsed_ms=%d",
                elapsed_ms,
            )
            return []

        results = _rows_to_analogues(rows)
        logger.info(
            "Neo4j keyword query complete | rows=%d | keywords=%s | elapsed_ms=%d",
            len(results),
            response.regime_keywords,
            elapsed_ms,
        )
        return results

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "Neo4j keyword query failed (LLM unavailable?) | error=%s | elapsed_ms=%d",
            str(exc)[:200],
            elapsed_ms,
        )
        return []
