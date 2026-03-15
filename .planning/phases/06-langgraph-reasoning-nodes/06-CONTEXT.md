# Phase 6: LangGraph Reasoning Nodes - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Five individual LangGraph reasoning nodes (structure, valuation, macro_regime, entry_quality, grounding_check) and one special-case handler (conflicting_signals) built and validated in isolation with mock state. Each node produces Pydantic-validated structured output via Gemini, consumes only what the next node needs, and handles edge cases (mixed signals, missing data, conflicting sub-assessments) explicitly. No graph assembly, no report rendering, no API endpoints — those are Phase 7+.

</domain>

<decisions>
## Implementation Decisions

### Gold vs equity valuation
- Separate valuation assessments for gold and VN equities — not unified
- Gold valuation uses: real yield (FRED data) + GLD ETF flow + macro regime overlay (uses macro_regime node output as context for gold-specific interpretation)
- WGC central bank buying data flagged as DATA WARNING per existing convention (501 stub)
- VN equity valuation compares current P/E, P/B against top 2-3 historical regime analogues weighted by similarity score from Neo4j HAS_ANALOGUE relationships
- When fundamental data is missing (e.g., newly listed stock, no P/E), produce partial assessment with available data and flag which metrics are missing — do not skip entirely

### Entry quality tier criteria
- Structure has veto power — weak structure caps the tier regardless of how strong macro and valuation signals are (aligns with Stratum core value: protect from entering at structurally dangerous levels)
- Sub-assessments use domain-specific labels, not uniform 4-tier:
  - Macro: Supportive / Mixed / Headwind (or similar domain-appropriate labels)
  - Valuation: Attractive / Fair / Stretched (or similar)
  - Structure: Constructive / Neutral / Deteriorating (or similar)
- Composite tier remains: Favorable / Neutral / Cautious / Avoid
- When all data sources are stale, still produce a tier but with prominent STALE DATA caveat — do not force Avoid tier on staleness alone
- Tier assignment method (rules-first vs LLM-decided): Claude's discretion

### Conflicting signal presentation
- Use both named conflict patterns AND narrative explanation — pattern as header, prose paragraph explaining specifics
- Examples of named patterns: "Strong Thesis, Weak Structure", "Cheap but Deteriorating", etc.
- Structure-biased guidance when signals conflict — the handler notes that structure is the dominant safety signal, consistent with Stratum's core value
- Conflict severity determines tier impact: minor conflicts (e.g., slightly cautious structure with strong everything else) can still be Favorable; major conflicts (e.g., structure = Avoid) force downgrade
- Number of pre-defined conflict patterns: Claude's discretion

### Grounding check strictness
- Verify both raw database values AND derived calculation chains (e.g., "P/E is 30% above the analogue average" must trace to source P/E, source analogue P/E values, and valid arithmetic)
- Grounding check runs after each node independently — catches errors early before downstream nodes build on ungrounded claims
- Qualitative claims (non-numeric) require source attribution — cite which data source informed the interpretation (e.g., "based on FRED indicators"), not a specific record ID
- Fail mode when unattributed numeric claim is found: Claude's discretion (SC #5 says "raises an explicit error")

### Claude's Discretion
- Tier assignment method (deterministic rules vs LLM-interpreted)
- Number and naming of conflict patterns
- Grounding check fail mode (error vs flag-and-continue)
- Gemini model selection, temperature, and token budget per node
- ReportState TypedDict schema design and reducer patterns
- Exact domain-specific sub-assessment label vocabulary
- Node testing strategy (mock state construction)

</decisions>

<specifics>
## Specific Ideas

- Gold and equity are separate assessment cards — the valuation node produces two distinct outputs depending on asset_type, not one unified output
- Gold valuation benefits from macro regime context overlay (e.g., "gold typically outperforms in rate-cutting regimes") — the macro_regime node output should be available as context to the gold valuation path
- Named conflict patterns should be educational over time — investors learn to think in terms like "Strong Thesis, Weak Structure" as a mental model
- Structure-biased conflict guidance aligns with the product tagline: "protect from being fundamentally right but entering at a structurally dangerous price level"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/retrieval/types.py`: All retrieval return types (RegimeAnalogue, DocumentChunk, FundamentalsRow, StructureMarkerRow, FredIndicatorRow, GoldPriceRow, GoldEtfRow) — nodes consume these directly
- `reasoning/app/retrieval/freshness.py`: check_freshness() with FRESHNESS_THRESHOLDS dict and now_override for testing — nodes call this or receive warnings from retriever layer
- `reasoning/app/retrieval/neo4j_retriever.py`: get_regime_analogues() returns RegimeAnalogue list with similarity scores and narratives
- `reasoning/app/retrieval/qdrant_retriever.py`: search_macro_docs() and search_earnings_docs() with language filtering and alpha weights
- `reasoning/app/retrieval/postgres_retriever.py`: Direct query functions for fundamentals, structure_markers, fred_indicators, gold_price, gold_etf_ohlcv
- NoDataError exception for empty retrieval results — nodes should catch and handle gracefully

### Established Patterns
- Pydantic v2 BaseModel with `warnings: list[str] = []` on all return types — nodes should follow this pattern for their outputs
- warnings propagation: retrieval warnings bubble up through pipeline without exceptions
- data_as_of + ingested_at timestamp convention on all data
- FastEmbed 384-dim (BAAI/bge-small-en-v1.5) locked for Qdrant
- SQLAlchemy Core (not ORM) for all PostgreSQL operations

### Integration Points
- Retrieval layer at `reasoning/app/retrieval/` — nodes import retrievers and types from here
- LangGraph checkpoint schema in `langgraph` PostgreSQL schema (Phase 3)
- Gemini API via GEMINI_API_KEY environment variable
- Phase 7 will assemble these nodes into a StateGraph — nodes must have compatible state schemas
- Phase 7 bilingual generation depends on structured output from these nodes

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-langgraph-reasoning-nodes*
*Context gathered: 2026-03-16*
