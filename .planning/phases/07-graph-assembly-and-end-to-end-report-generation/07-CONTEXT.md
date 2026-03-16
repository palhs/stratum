# Phase 7: Graph Assembly and End-to-End Report Generation - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Assemble all 6 validated Phase 6 nodes into a LangGraph StateGraph with PostgreSQL AsyncPostgresSaver checkpointing. Produce a first end-to-end bilingual report (Vietnamese primary, English) for VHM (equity) and gold test assets. Report stored in PostgreSQL `reports` table. Report must pass grounding check, data freshness validation, and Vietnamese term consistency. No API endpoints (Phase 8), no batch processing (Phase 9).

</domain>

<decisions>
## Implementation Decisions

### Vietnamese financial term dictionary
- JSON lookup table (~150-200 terms) covering macro, valuation, structure, and entry quality domains comprehensively
- Claude drafts initial dictionary, user reviews and corrects before integration
- English financial abbreviations kept inline in Vietnamese text (P/E, ATH, ETF, etc.) — standard VN financial media practice
- Dictionary covers: tier labels, sub-assessment labels, card headers, conflict patterns, DATA WARNING text, financial metrics, macro concepts, and narrative connectors

### Report card structure
- Conclusion-first ordering: Entry Quality → Macro Regime → Valuation → Structure
- When signal conflict exists: separate 5th section "Signal Conflict" appears between Entry Quality and Macro Regime cards
- Full narrative depth per card: Gemini-generated narrative (3-5 sentences), metrics, tier/label with explanation
- JSON report: flat object per card (not nested sub-objects) — simple JSONB querying for Phase 8 API

### Prohibited language enforcement
- Prompt constraint only — instruct Gemini to never use prohibited terms; no post-processing filter
- Prohibited in both English AND Vietnamese: 'buy'/'mua', 'sell'/'bán', 'entry confirmed'/'xác nhận điểm vào'
- Compound words allowed: 'buyback', 'sell-off', 'oversold', 'overbought' are acceptable analytical descriptors
- Replacement framing: assessment language — "the environment suggests...", "conditions appear...", "the structure indicates..." (not probability language)

### Data prefetch orchestration
- Two-stage pipeline: `prefetch(ticker, asset_type)` returns populated ReportState, then `run_graph(state)` executes the StateGraph — testable independently
- Test assets for v2.0 E2E: VHM (Vinhomes, equity path) AND gold (gold path) — both tested in first run
- Bilingual generation: two separate graph invocations per asset, one with language='vi' and one with language='en' — language is a parameter, not a dual-output node
- Each invocation produces one row in `reports` table (so VHM generates 2 rows: vi + en)

### Claude's Discretion
- StateGraph edge topology (linear vs conditional edges)
- AsyncPostgresSaver configuration and connection pooling
- Prefetch error handling (which store failures are fatal vs degraded)
- Markdown report template structure and formatting
- Vietnamese dictionary term selection within the ~150-200 scope
- Test fixture design for E2E integration tests

</decisions>

<specifics>
## Specific Ideas

- Conclusion-first ordering is intentional: investors want the bottom line (entry quality tier) before reading supporting analysis — scan-readers get the answer, deep-readers scroll for detail
- Conflict section as separate 5th card makes disagreements prominent — investors shouldn't miss that signals are fighting
- Assessment language ("conditions appear", "the structure indicates") is deliberately passive/observational — Stratum describes, it doesn't prescribe
- Two-stage prefetch/run_graph split means Phase 8 FastAPI can potentially cache prefetched state for repeated runs with different language parameters

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reasoning/app/nodes/__init__.py`: All 6 node functions exported (structure_node, valuation_node, macro_regime_node, entry_quality_node, grounding_check_node, conflicting_signals_handler)
- `reasoning/app/nodes/state.py`: ReportState TypedDict (13 keys), all Pydantic output models, GroundingError exception, label constants
- `reasoning/app/retrieval/`: 3 retrievers (postgres, neo4j, qdrant) with Pydantic return types — prefetch() calls these
- `reasoning/app/retrieval/freshness.py`: check_freshness() with FRESHNESS_THRESHOLDS — used for DATA WARNING generation
- `db/migrations/V6__reports.sql`: reports table with report_json (JSONB), report_markdown (TEXT), language, asset_id, generated_at columns

### Established Patterns
- Node signature: `(state: ReportState) -> dict[str, Any]` — all 6 nodes follow this
- `warnings: list[str] = []` on all Pydantic outputs — warnings propagate through pipeline
- Deterministic labels + Gemini narrative — rules assign tiers/labels, LLM writes prose only
- `gemini-2.5-pro` model locked across all nodes (user-confirmed, API verified)
- SQLAlchemy Core for PostgreSQL operations

### Integration Points
- LangGraph checkpoint schema in `langgraph` PostgreSQL schema (Phase 3, `?options=-csearch_path=langgraph`)
- Retrieval layer at `reasoning/app/retrieval/` — prefetch() orchestrates all 3 stores
- `reports` table for final storage — one row per (asset, language) per run
- Phase 8 will wrap `generate_report()` in FastAPI endpoints

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-graph-assembly-and-end-to-end-report-generation*
*Context gathered: 2026-03-16*
