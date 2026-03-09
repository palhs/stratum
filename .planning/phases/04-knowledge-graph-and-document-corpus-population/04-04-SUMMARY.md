---
phase: 04-knowledge-graph-and-document-corpus-population
plan: "04"
subsystem: data
tags: [qdrant, fastembed, pdfplumber, langchain-text-splitters, vn30, earnings]

requires:
  - phase: 04-01
    provides: earnings_docs_v1 Qdrant collection created by init-qdrant.sh extension

provides:
  - data/earnings/manifest.json — 120-entry VN30 earnings document registry (30 tickers x 4 quarters FY2024) with lang, source, and curation metadata
  - scripts/seed-qdrant-earnings-docs.py — idempotent seed script that reads PDFs/text files from data/earnings/{TICKER}/, chunks with RecursiveCharacterTextSplitter, embeds with FastEmbed bge-small-en-v1.5, and upserts to Qdrant earnings_docs collection

affects:
  - 05-retrieval-layer-validation (earnings_docs collection must be populated before Qdrant hybrid retriever validation)
  - 06-langgraph-reasoning-nodes (valuation node retrieves company-specific financial context from earnings_docs)

tech-stack:
  added:
    - pdfplumber (PDF text extraction for VN30 annual reports and quarterly statements)
    - langchain-text-splitters (RecursiveCharacterTextSplitter for document chunking)
    - fastembed (BAAI/bge-small-en-v1.5 384-dim English embeddings)
    - qdrant-client (upload_points upsert to earnings_docs_v1)
    - python-dotenv (QDRANT_API_KEY environment loading)
  patterns:
    - Deterministic uuid5 point IDs for idempotent re-runs (doc_id + chunk_index namespace key)
    - chunk_size=2048 chars (~512 tokens), chunk_overlap=256 chars (~12%) — consistent with macro_docs
    - Manifest-driven curation — filename=null entries skipped, processed only when file placed in data/earnings/{TICKER}/
    - lang payload field distinguishes English (high quality) from Vietnamese (degraded) embeddings
    - Post-upsert validation: collection point count + per-ticker similarity search

key-files:
  created:
    - data/earnings/manifest.json
    - scripts/seed-qdrant-earnings-docs.py
  modified: []

key-decisions:
  - "data/earnings/manifest.json covers all 30 current VN30 tickers with 4 quarterly entries each (FY2024) — 120 total entries, all filename=null initially pending manual document download from hsx.vn"
  - "12 large-cap VN30 tickers with known English IR reports marked lang=en (VCB, BID, CTG, VIC, VHM, HPG, MWG, FPT, VNM, MSN, GAS, PLX); remaining 18 marked lang=vi with degraded-embedding-quality warning in notes and script logs"
  - "seed script uses batch-per-ticker upload pattern (all chunks for a ticker uploaded in one upload_points call) for efficient progress tracking and retry granularity"
  - "Seed script creates earnings_docs_v1 collection + alias as a fallback if init-qdrant.sh hasn't run, preventing hard failures when running standalone"

patterns-established:
  - "Manifest-driven document curation: registry file with filename=null as placeholder, manual download then update filename, re-run seed script — same pattern applicable to macro_docs"
  - "Language-aware payload flagging: lang field in each Qdrant point payload distinguishes embedding quality tiers at retrieval time in Phase 5"

requirements-completed:
  - DATA-04

duration: 15min
completed: 2026-03-09
---

# Phase 4 Plan 04: Qdrant earnings_docs Population Summary

**VN30 earnings manifest (120 entries, 30 tickers) and idempotent Qdrant seed script with FastEmbed bge-small-en-v1.5 chunking and language-quality flagging for Vietnamese-only documents**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-09T07:26:34Z
- **Completed:** 2026-03-09T07:41:00Z
- **Tasks:** 1 automated (Task 2 is a human-verify checkpoint for document download guidance)
- **Files modified:** 2 created

## Accomplishments

- Created `data/earnings/manifest.json` covering all 30 current VN30 index constituents with 4 quarterly entries each (FY2024), 120 total entries with full metadata: ticker, company_name, fiscal_period, doc_type, lang, source, curation notes
- Created `scripts/seed-qdrant-earnings-docs.py` — production-ready seed script that reads PDFs and text files from `data/earnings/{TICKER}/`, chunks with RecursiveCharacterTextSplitter (2048 chars, 256 overlap), embeds with FastEmbed BAAI/bge-small-en-v1.5, and upserts to Qdrant earnings_docs collection with deterministic uuid5 point IDs
- Correctly identified and flagged that Vietnamese companies do NOT have earnings call transcripts (per RESEARCH.md Pitfall 5) — manifest and script use "financial reports" / "quarterly_financial_statement" terminology and source from hsx.vn disclosure portal
- 12 large-cap tickers with known English IR reports marked `lang: "en"` for full embedding quality; 18 tickers marked `lang: "vi"` with explicit quality limitation warnings in both manifest notes and runtime script logs

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VN30 earnings document manifest and seed script** - `75ec0ab` (feat)

**Plan metadata:** see final docs commit

## Files Created/Modified

- `data/earnings/manifest.json` — 120-entry VN30 earnings document registry; each entry carries ticker, company_name, fiscal_period, fiscal_year, doc_type, filename (null pending download), lang, source, and curation notes
- `scripts/seed-qdrant-earnings-docs.py` — Idempotent Python seed script; supports PDF and .txt files; RecursiveCharacterTextSplitter chunking; FastEmbed bge-small-en-v1.5 embedding; upload_points upsert with batch_size=64; post-upsert validation via collection point count and per-ticker similarity search

## Decisions Made

- All 120 manifest entries start with `filename: null` — this is intentional. The seed script skips null-filename entries and logs how many were skipped, keeping the curation workflow clear: download document, place in `data/earnings/{TICKER}/`, update manifest filename, re-run script.
- 12 tickers classified as English-capable based on RESEARCH.md guidance: VCB, BID, CTG, VIC, VHM, HPG, MWG, FPT, VNM, MSN, GAS, PLX. These publish English annual reports for international investor relations. The remaining 18 are Vietnamese-only for quarterly financial statements.
- Batch-per-ticker upload pattern chosen: all chunks for a given ticker are accumulated then uploaded in a single `upload_points` call, giving natural progress granularity and simpler retry boundaries.
- Collection creation is included as a fallback in the seed script (not just in init-qdrant.sh) so the script can run standalone during development without requiring the full Docker stack.

## Deviations from Plan

None — plan executed exactly as written. The manifest and seed script were built exactly per spec in the plan's `<action>` block.

## Issues Encountered

None.

## User Setup Required

**Document download required before running the seed script:**

Task 2 (checkpoint:human-verify) provides the document curation checklist. Key steps:

1. Review `data/earnings/manifest.json` — verify the VN30 ticker list matches the current index composition
2. For English-capable tickers (VCB, BID, CTG, VIC, VHM, HPG, FPT, VNM, MWG, MSN, GAS, PLX): download English annual reports from company IR pages or HOSE portal (hsx.vn), place in `data/earnings/{TICKER}/`
3. Update each manifest entry's `filename` field to match the downloaded file name
4. For Vietnamese-only tickers: decide whether to use Vietnamese documents (with degraded embedding quality) or defer
5. After placing documents: run `python3 scripts/seed-qdrant-earnings-docs.py` to populate Qdrant
6. Verify: `MATCH (n) RETURN n` on Qdrant (or check collection point count via API)

## Next Phase Readiness

- `data/earnings/manifest.json` and `scripts/seed-qdrant-earnings-docs.py` are complete and verified (script syntax check passes, manifest has 120 entries for all 30 VN30 tickers)
- Actual Qdrant population requires manual document download step (Task 2 checkpoint)
- Phase 5 retrieval layer validation requires the earnings_docs collection to be populated — this plan delivers the tooling; document download is the remaining prerequisite
- No blockers beyond the expected manual document curation step documented in RESEARCH.md

## Self-Check: PASSED

- FOUND: scripts/seed-qdrant-earnings-docs.py
- FOUND: data/earnings/manifest.json
- FOUND: .planning/phases/04-knowledge-graph-and-document-corpus-population/04-04-SUMMARY.md
- FOUND: commit 75ec0ab (feat(04-04): create VN30 earnings manifest and Qdrant seed script)

---
*Phase: 04-knowledge-graph-and-document-corpus-population*
*Completed: 2026-03-09*
