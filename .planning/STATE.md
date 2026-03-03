---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-03-04T17:49:06Z"
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 14
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Protect investors from being fundamentally right but entering at a structurally dangerous price level — by combining macro regime analysis, valuation context, and price structure into a single actionable entry quality assessment.
**Current focus:** Phase 2 in progress — Plans 01, 02, 03 complete

## Current Position

Phase: 2 of 7 (Data Ingestion Pipeline) — IN PROGRESS
Plan: 3 of 5 in Phase 2 complete (02-01, 02-02, 02-03 complete)
Status: Phase 2 in progress
Last activity: 2026-03-04 — Phase 2 Plan 3 complete: structure marker computation service (MAs, drawdowns, percentile ranks), POST /compute/structure-markers endpoint

Progress: [████░░░░░░] 28% (4/14 plans total)

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~4 min
- Total execution time: ~0.24 hours

**By Phase:**

| Phase | Plans | Total Time | Avg/Plan |
|-------|-------|------------|----------|
| 01-infrastructure-and-storage-foundation | 2/2 | 5 min | 2.5 min |
| 02-data-ingestion-pipeline | 3/5 | ~13 min | ~4.3 min |

**Recent Trend:**
- Last 5 plans: ~4 min
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Retrieval validation kept as Phase 3 (not folded into Phase 4) — MACRO-04 is the anchor requirement; retrieval bugs inside a 5-node graph are nearly impossible to root-cause
- [Roadmap]: Phase 4 reasoning implementation split from Phase 5 synthesis — analytical nodes (MACRO/VAL/STRUC) validated independently before EntryQualityScorer and ReportComposer are built
- [Roadmap]: RPT-04 (report UI aesthetic) assigned to Phase 7 (Frontend) — it is a rendering concern, not a reasoning pipeline concern
- [Phase 01-infrastructure-and-storage-foundation]: n8n on ingestion network only, storage services on both networks — INFRA-02 enforced at Docker network level
- [Phase 01-infrastructure-and-storage-foundation]: postgres and qdrant ports not exposed on host; only Neo4j Browser (7474/7687) and n8n UI (5678) exposed
- [Phase 01-infrastructure-and-storage-foundation]: Named volumes for all persistent data, no bind mounts — avoids Qdrant APFS POSIX incompatibility on macOS
- [Phase 01-02]: Vector size 384 (FastEmbed BAAI/bge-small-en-v1.5) instead of 1536 (OpenAI) — more memory-efficient for 8GB VPS; FastEmbed is the chosen embedding approach
- [Phase 01-02]: Neo4j init entrypoint split: constraints run -d neo4j, APOC triggers run -d system — constraints cannot be created on system database
- [Phase 01-02]: n8n database created via PostgreSQL initdb (create-n8n-db.sql) — CREATE DATABASE cannot run inside a Flyway transaction
- [Phase 02-01]: VCI source used exclusively for vnstock calls — TCBS source is broken as of 2025
- [Phase 02-01]: VN30 symbols fetched live via Listing.symbols_by_group() — never hard-coded
- [Phase 02-01]: Single stock_ohlcv table with resolution column — no separate tables per resolution (locked decision)
- [Phase 02-01]: SQLAlchemy Core Table() style over ORM declarative — required for pg_insert().on_conflict_do_update() upsert pattern
- [Phase 02-01]: data-sidecar has no host port mapping — n8n calls it as data-sidecar:8000 on ingestion network
- [Phase 02-01]: UNIQUE constraint with COALESCE in gold_wgc_flows implemented as CREATE UNIQUE INDEX (PostgreSQL table-level UNIQUE does not support expressions)
- [Phase 02-03]: Full recompute strategy for structure markers — at VN30 scale (~7,800 rows) < 5s; incremental adds complexity with no meaningful gain
- [Phase 02-03]: gold_price rows treated as weekly resolution for gold spot (XAU) — assigns symbol='XAU', resolution='weekly' to spot price series
- [Phase 02-03]: PE percentile rank computed via merge_asof (backward join) to align annual PE reports to weekly bars

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: World Gold Council data ingestion method and specific API endpoint structure not confirmed — validate before Phase 2 planning begins
- [Phase 2]: Neo4j initial regime graph seed data source is unresolved (manual curation vs automated historical ingestion vs one-time import) — needs explicit plan in Phase 2
- [Phase 4]: Ollama model selection for local LLM fallback not determined — requires VPS RAM constraint evaluation before Phase 4 planning
- [Phase 4/5]: Vietnamese financial terminology dictionary does not exist yet — must be authored before ReportComposer node (Phase 5) and glossary sidebar (Phase 7) can be implemented; this is a content asset, not a code task

## Session Continuity

Last session: 2026-03-04
Stopped at: Completed 02-data-ingestion-pipeline 02-03-PLAN.md
Resume file: .planning/phases/02-data-ingestion-pipeline/02-04-PLAN.md
