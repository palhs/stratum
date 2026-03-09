---
phase: 04-knowledge-graph-and-document-corpus-population
plan: "03"
subsystem: data
tags: [qdrant, fastembed, pdfplumber, langchain, fomc, sbv, vector-embeddings, document-corpus]

# Dependency graph
requires:
  - phase: 04-knowledge-graph-and-document-corpus-population
    provides: macro_docs_v1 Qdrant collection (created by init-qdrant.sh in Plan 01)
provides:
  - scripts/seed-qdrant-macro-docs.py — idempotent seeder for FOMC + SBV documents into Qdrant macro_docs
  - data/fomc/manifest.json — 15 FOMC minutes at key monetary policy turning points (2008-2024)
  - data/sbv/manifest.json — 22 SBV documents registry for manual curation (rate decisions, annual reports)
affects:
  - phase-05-qdrant-hybrid-retriever
  - phase-06-macro-regime-reasoning-node

# Tech tracking
tech-stack:
  added:
    - pdfplumber (PDF text extraction)
    - langchain-text-splitters (RecursiveCharacterTextSplitter)
    - fastembed (BAAI/bge-small-en-v1.5 384-dim embeddings)
    - qdrant-client (upload_points to macro_docs_v1)
    - httpx (FOMC PDF downloads from federalreserve.gov)
  patterns:
    - Deterministic uuid5 point IDs for idempotent Qdrant upserts
    - Manifest-driven document registry pattern (manifest.json + null filename for pending manual curation)
    - Graceful HTTP 404 handling for historical Fed document downloads
    - English-only embedding guard with language warning for non-English docs

key-files:
  created:
    - scripts/seed-qdrant-macro-docs.py
    - data/fomc/manifest.json
    - data/sbv/manifest.json
  modified: []

key-decisions:
  - "FOMC manifest covers 15 key turning points (2008-2024) including GFC emergency cuts, QE announcements, taper tantrum, rate normalization, COVID emergency, 2022 aggressive tightening, 2023 hold, and 2024 easing cycle start"
  - "SBV manifest uses null filename pattern — script skips entries without filenames, user places PDFs in data/sbv/ and updates manifest"
  - "chunk_size=2048 characters (~512 tokens for bge-small-en-v1.5), chunk_overlap=256 (~12%) per RESEARCH.md Pattern 4"
  - "uuid5 with fixed namespace UUID for deterministic point IDs — re-runs overwrite same points without duplication"
  - "English-only documents enforced — Vietnamese SBV docs trigger warning about degraded bge-small-en-v1.5 quality"

patterns-established:
  - "Manifest-driven corpus: manifest.json registry + null filename sentinel for manual document curation workflow"
  - "Idempotent Qdrant seeder: uuid5(namespace, doc_id::chunk_index) deterministic IDs with upload_points wait=True"
  - "Graceful failure pipeline: download errors, PDF extraction errors, and zero-character PDFs all logged and skipped without crashing"

requirements-completed:
  - DATA-03

# Metrics
duration: 8min
completed: 2026-03-09
---

# Phase 4 Plan 03: Macro Document Corpus Seed Script Summary

**Qdrant macro_docs seeder with 15 FOMC minutes + 22-entry SBV registry, chunking at 2048 chars with FastEmbed bge-small-en-v1.5, idempotent via uuid5 point IDs**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-09T07:26:23Z
- **Completed:** 2026-03-09T07:34:00Z
- **Tasks:** 1 of 2 complete (Task 2 is human-verify checkpoint)
- **Files modified:** 3

## Accomplishments
- Created `scripts/seed-qdrant-macro-docs.py` — complete seeder that downloads FOMC PDFs from federalreserve.gov, reads SBV PDFs, chunks with RecursiveCharacterTextSplitter (2048 chars, 256 overlap), embeds with FastEmbed BAAI/bge-small-en-v1.5, and upserts to Qdrant macro_docs_v1 with deterministic uuid5 IDs
- Created `data/fomc/manifest.json` — 15 FOMC minutes spanning key monetary policy turning points: GFC emergency cuts (Oct/Dec 2008), QE1 (Mar 2009), QE2 (Nov 2010), taper tantrum (Jun 2013), first hike (Dec 2015), pivot (Jul 2019), COVID emergency (Mar 2020), inflation signals (Nov 2021), aggressive 75bp hikes (Jun/Sep 2022), pause/hold (Jun/Nov 2023), easing start (Sep 2024), slower easing (Dec 2024)
- Created `data/sbv/manifest.json` — 22-entry SBV document registry covering 2008-2024 with null filenames for manual curation workflow; includes rate decisions, annual reports, and policy reports aligned to regime_context periods

## Task Commits

Each task was committed atomically:

1. **Task 1: Create macro document manifests and seed script** - `7d6c18c` (feat)
2. **Task 2: Verify macro_docs population results** - awaiting human checkpoint

**Plan metadata:** (pending after checkpoint)

## Files Created/Modified
- `scripts/seed-qdrant-macro-docs.py` — Downloads FOMC PDFs, reads SBV PDFs, chunks (2048/256), embeds (bge-small-en-v1.5), upserts to Qdrant macro_docs_v1; idempotent via uuid5; handles 404s gracefully; validates with test similarity search post-upload
- `data/fomc/manifest.json` — 15 FOMC minute entries with url, date, title, doc_type, regime_context fields; all URLs follow federalreserve.gov/monetarypolicy/files/ pattern
- `data/sbv/manifest.json` — 22 SBV document entries (rate decisions, annual reports, policy reports) with null filenames as registry for manual PDF curation from sbv.gov.vn/en

## Decisions Made
- FOMC manifest targets 15 key turning points rather than complete coverage — quality over quantity, focused on regime-defining moments
- SBV manifest uses null-filename sentinel pattern: script skips entries without filenames gracefully, user places PDFs in data/sbv/ and updates manifest entry by entry
- chunk_size=2048 characters (not tokens) with chunk_overlap=256 — ~512 tokens per chunk for bge-small-en-v1.5 384-dim model, matching RESEARCH.md Pattern 4
- Fixed namespace UUID `8e4b7c6a-2d5f-4e9a-b1c3-0f7e8d2a6b4c` for uuid5 ensures deterministic point IDs across re-runs without a database lookup
- English-only enforcement: Vietnamese documents trigger logged warning about degraded embedding quality (bge-small-en-v1.5 is English-only per RESEARCH.md Pitfall 2)

## Deviations from Plan

None — plan executed exactly as written. All must_have truths satisfied:
- Script uses RecursiveCharacterTextSplitter at chunk_size=2048 (~512 tokens), chunk_overlap=256 (~12% overlap)
- FastEmbed BAAI/bge-small-en-v1.5 (384-dim) used for all embeddings
- Deterministic uuid5 IDs ensure idempotent re-runs overwrite same points
- Full metadata payload per point: source, document_date, doc_type, chunk_index, text, title, regime_context, lang
- Graceful HTTP 404 handling: logs warning and skips without crashing
- Post-upsert validation runs similarity search for "Federal Reserve rate decision"

## Issues Encountered
None — `python3` used for verification (system has python3, not python alias).

## User Setup Required

**SBV documents require manual curation before the seeder can populate SBV content.**

Steps:
1. Visit sbv.gov.vn/en to download SBV monetary policy documents
2. Place downloaded PDFs in `/data/sbv/` directory
3. Update `data/sbv/manifest.json` — set `filename` field for each document you've downloaded
4. Run `python3 scripts/seed-qdrant-macro-docs.py` (requires Docker stack with Qdrant running)
5. Verify FOMC downloads: `ls -la data/fomc/*.pdf | wc -l` — should show up to 15 PDFs (some historical URLs may 404)
6. Verify Qdrant: `curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/macro_docs_v1 | python3 -m json.tool`

**Note:** FOMC PDFs download automatically. SBV PDFs require manual download due to no programmatic access pattern.

## Next Phase Readiness
- Script is ready to run once Docker stack is up with Qdrant and `QDRANT_API_KEY` set
- `macro_docs_v1` collection must exist before running (created by `scripts/init-qdrant.sh` from Plan 01)
- SBV documents need manual download before SBV content populates; FOMC will populate independently
- Phase 5 Qdrant hybrid retriever can proceed once `macro_docs` collection has FOMC chunks (SBV is additive)

---
*Phase: 04-knowledge-graph-and-document-corpus-population*
*Completed: 2026-03-09*

## Self-Check: PASSED

- FOUND: scripts/seed-qdrant-macro-docs.py
- FOUND: data/fomc/manifest.json
- FOUND: data/sbv/manifest.json
- FOUND: .planning/phases/04-knowledge-graph-and-document-corpus-population/04-03-SUMMARY.md
- FOUND: commit 7d6c18c — feat(04-03): create macro document manifests and Qdrant seed script
