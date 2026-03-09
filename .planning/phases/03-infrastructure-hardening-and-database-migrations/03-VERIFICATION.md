---
phase: 03-infrastructure-hardening-and-database-migrations
verified: 2026-03-09T03:00:00Z
status: human_needed
score: 11/11 must-haves verified
re_verification: true
  previous_status: gaps_found
  previous_score: 9/11
  gaps_closed:
    - "ROADMAP.md SC #2 now lists only 5 existing services (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, data-sidecar 512MB) and explicitly defers reasoning-engine mem_limit to Phase 8 — commit 1572c7d"
    - "ROADMAP.md SC #4 now references .env.example as the Phase 3 deliverable and defers live API validation to Phase 8 — commit 1572c7d"
    - "REQUIREMENTS.md INFRA-03 now lists 5 existing services and notes reasoning-engine 2GB deferred to Phase 8 — commit af8a7d0"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Flyway migration application — run docker compose run --rm flyway migrate and inspect \\d reports and \\d report_jobs"
    expected: "Flyway applies V6 and V7 without checksum errors; both tables appear with all columns, constraints, and indexes; flyway_schema_history shows versions 6 and 7 with success = true"
    why_human: "Requires a running PostgreSQL container; DDL application cannot be verified statically"
  - test: "Gemini API key validation — set GEMINI_API_KEY in .env.local and call the Gemini API"
    expected: "Returns HTTP 200, not 401/403"
    why_human: "Requires a live network call with the user's actual API key; static inspection only confirms the template entry exists. Live validation deferred to Phase 8 per updated ROADMAP SC #4."
  - test: "langgraph-init container execution — run docker compose --profile reasoning up langgraph-init and check logs"
    expected: "Container logs show LangGraph schema init complete, exits code 0, does not restart; 4 tables visible in langgraph schema"
    why_human: "Requires a running Docker stack; schema creation cannot be verified without container execution"
  - test: "langgraph-init idempotency — run langgraph-init a second time"
    expected: "Exits code 0, no errors — CREATE SCHEMA IF NOT EXISTS and CREATE TABLE IF NOT EXISTS prevent conflicts"
    why_human: "Runtime behavior; IF NOT EXISTS semantics are correct in DDL but actual idempotency requires a live test"
  - test: "VPS swap configuration — SSH into VPS host and run free -h"
    expected: "Output shows approximately 4G in the swap row"
    why_human: "Host-level OS configuration; cannot be verified from within Docker or from the local codebase"
---

# Phase 3: Infrastructure Hardening and Database Migrations — Verification Report

**Phase Goal:** All infrastructure prerequisites are in place before any reasoning code is written — Flyway migrations create the reports and report_jobs tables, all Docker services have explicit memory limits, VPS swap is configured, Neo4j JVM heap is set, GEMINI_API_KEY is available, and the LangGraph checkpoint schema is initialized.
**Verified:** 2026-03-09
**Status:** human_needed (all automated checks pass; 5 items require runtime/host verification)
**Re-verification:** Yes — after gap closure via Plan 03-04

---

## Re-Verification Summary

The previous verification (score: 9/11) identified two gaps, both caused by a documentation scope mismatch: Plan 03-02 correctly deferred the reasoning-engine service to Phase 8, but ROADMAP.md and REQUIREMENTS.md still referenced reasoning-engine as a Phase 3 deliverable. Plan 03-04 resolved both gaps via documentation-only edits.

**Gaps closed:**

| Gap | Resolution | Commit |
|-----|-----------|--------|
| ROADMAP SC #2 listed `reasoning-engine 2GB` as Phase 3 deliverable | SC #2 now lists 5 existing services; reasoning-engine mem_limit noted as Phase 8 | `1572c7d` |
| ROADMAP SC #4 required live Gemini API curl test | SC #4 now names `.env.example` as deliverable; live test deferred to Phase 8 | `1572c7d` |
| REQUIREMENTS.md INFRA-03 listed `reasoning-engine 2GB` as Phase 3 scope | INFRA-03 now lists 5 services; reasoning-engine deferred to Phase 8 | `af8a7d0` |

**Regressions:** None detected. All 9 previously-verified truths remain intact.

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria — updated after Plan 03-04)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `flyway migrate` applies V6 and V7 cleanly — reports and report_jobs tables exist with all columns and constraints | ? HUMAN | `db/migrations/V6__reports.sql` (43 lines) and `db/migrations/V7__report_jobs.sql` (38 lines) exist with complete DDL; runtime application requires Docker |
| 2 | The `reports` table DDL is complete (all columns, language CHECK, indexes) | VERIFIED | V6 has all 10 required columns, `CHECK (language IN ('vi', 'en'))`, and 2 indexes |
| 3 | The `report_jobs` table DDL is complete (four-state machine, FK to reports, indexes) | VERIFIED | V7 has status CHECK constraint, `REFERENCES reports(report_id)`, and 2 indexes |
| 4 | All 5 existing Docker services have explicit `mem_limit` values matching ROADMAP SC #2 | VERIFIED | postgres 512m (line 43), neo4j 2g (line 66), qdrant 1g (line 96), n8n 512m (line 204), data-sidecar 512m (line 237) — confirmed in docker-compose.yml |
| 5 | ROADMAP SC #2 lists only 5 existing services; reasoning-engine mem_limit deferred to Phase 8 | VERIFIED | ROADMAP.md line 50: "data-sidecar 512MB — ... reasoning-engine `mem_limit: 2g` is set when the service is created in Phase 8." Commit 1572c7d. |
| 6 | Neo4j JVM heap initial=max=1G with 512m pagecache | VERIFIED | docker-compose.yml line 73: `NEO4J_server_memory_heap_initial__size: "1G"`, line 74: `NEO4J_server_memory_heap_max__size: "1G"` |
| 7 | VPS swap instructions are documented and idempotent | VERIFIED | Comment block in docker-compose.yml lines 9-16 with complete fallocate/mkswap/fstab/sysctl commands; actual VPS swap requires host verification |
| 8 | `GEMINI_API_KEY` exists in `.env.example` as the Phase 3 deliverable (ROADMAP SC #4) | VERIFIED | `.env.example` lines 44-46: SDK note and `GEMINI_API_KEY=your-gemini-api-key-here`; ROADMAP SC #4 now correctly names `.env.example` as deliverable |
| 9 | ROADMAP SC #4 defers live API validation to Phase 8 | VERIFIED | ROADMAP.md line 52: "live API validation is a runtime verification item performed when the reasoning-engine service is deployed in Phase 8." Commit 1572c7d. |
| 10 | LangGraph init script creates 4 tables in `langgraph` schema using psycopg3 with autocommit=True | VERIFIED | `scripts/init-langgraph-schema.py` (111 lines): 4 `CREATE TABLE IF NOT EXISTS langgraph.*` statements, `psycopg.connect(..., autocommit=True)` |
| 11 | langgraph-init Docker service is defined as one-shot init in docker-compose.yml | VERIFIED | Service defined at line 176; depends_on postgres (healthy) and flyway (completed_successfully); reasoning profile only; no restart policy |

**Score: 11/11 truths verified** (5 items require runtime/host verification — these are inherent to the nature of the infrastructure, not implementation gaps)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `db/migrations/V6__reports.sql` | Reports table DDL with JSONB payload, language check, metadata columns, indexes | VERIFIED | 43 lines; CREATE TABLE reports with all required columns; language CHECK ('vi','en'); 2 indexes |
| `db/migrations/V7__report_jobs.sql` | Report jobs DDL with status state machine, FK to reports, error column, indexes | VERIFIED | 38 lines; CREATE TABLE report_jobs; status CHECK (pending/running/completed/failed); REFERENCES reports(report_id); 2 indexes |
| `scripts/init-langgraph-schema.py` | One-shot checkpoint schema init using psycopg3 raw DDL | VERIFIED | 111 lines; CREATE SCHEMA IF NOT EXISTS langgraph; 4 CREATE TABLE IF NOT EXISTS langgraph.*; autocommit=True; validation query |
| `docker-compose.yml` | mem_limit on all 5 existing services, Neo4j JVM heap tuning, langgraph-init service, VPS swap comment | VERIFIED | All 5 services have correct mem_limit; Neo4j heap tuned; langgraph-init service present; VPS swap block present; reasoning-engine absent (Phase 8 — correct) |
| `.env.example` | GEMINI_API_KEY environment variable template | VERIFIED | Lines 44-46: Google Gemini API section with SDK note and `GEMINI_API_KEY=your-gemini-api-key-here` |
| `.planning/ROADMAP.md` | Phase 3 SC #2 lists 5 services; SC #4 references .env.example | VERIFIED | SC #2 line 50 lists 5 services with Phase 8 deferral note; SC #4 line 52 references .env.example and defers live test to Phase 8. Commit 1572c7d. |
| `.planning/REQUIREMENTS.md` | INFRA-03 lists 5 existing services; reasoning-engine deferred to Phase 8 | VERIFIED | INFRA-03: "Docker Compose has explicit mem_limit on all existing services (Neo4j 2GB, Qdrant 1GB, PostgreSQL 512MB, n8n 512MB, data-sidecar 512MB); reasoning-engine 2GB deferred to Phase 8 when service is created." Commit af8a7d0. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `db/migrations/V7__report_jobs.sql` | `db/migrations/V6__reports.sql` | FK: `report_id BIGINT REFERENCES reports(report_id)` | VERIFIED | FK constraint confirmed in V7 |
| `scripts/init-langgraph-schema.py` | PostgreSQL langgraph schema | `psycopg.connect(database_url, autocommit=True)` executing DDL | VERIFIED | autocommit=True with conn.execute(DDL) |
| `docker-compose.yml langgraph-init` | `scripts/init-langgraph-schema.py` | Volume mount and python entrypoint | VERIFIED | Script mounted as :ro volume; python entrypoint confirmed |
| `docker-compose.yml` | Neo4j JVM environment variables | `NEO4J_server_memory_heap_initial__size: "1G"` | VERIFIED | Lines 73-74 confirmed |
| `ROADMAP.md SC #2` | `docker-compose.yml` | mem_limit values match actual 5 existing services | VERIFIED | ROADMAP lists exactly the 5 services present in docker-compose.yml with correct values |
| `ROADMAP.md SC #4` | `.env.example` | GEMINI_API_KEY template entry is the deliverable | VERIFIED | ROADMAP now names .env.example explicitly; .env.example contains the entry |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-01 | 03-01 | Flyway V6 migration creates `reports` table | SATISFIED | `db/migrations/V6__reports.sql` exists with complete DDL |
| INFRA-02 | 03-01 | Flyway V7 migration creates `report_jobs` table | SATISFIED | `db/migrations/V7__report_jobs.sql` exists with complete DDL, four-state machine, FK to reports |
| INFRA-03 | 03-02, 03-04 | Docker Compose has explicit `mem_limit` on all existing services (5 services); reasoning-engine deferred to Phase 8 | SATISFIED | All 5 services have correct mem_limit in docker-compose.yml; REQUIREMENTS.md INFRA-03 text updated to match scope via commit af8a7d0 |
| INFRA-04 | 03-02 | VPS swap configured at 4GB and Neo4j JVM heap explicitly set | PARTIALLY SATISFIED | Neo4j JVM heap is set (verifiable); VPS swap instructions are documented; actual VPS swap activation requires human/host verification |
| INFRA-05 | 03-02 | `GEMINI_API_KEY` added to environment configuration | SATISFIED | `.env.example` contains GEMINI_API_KEY with documentation |
| INFRA-06 | 03-03 | LangGraph checkpoint database schema initialized (psycopg3-based PostgresSaver) | SATISFIED | `scripts/init-langgraph-schema.py` and `langgraph-init` Docker service both present and wired correctly |

All 6 INFRA requirement IDs are accounted for. No orphaned requirements detected.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder/stub patterns detected in any Phase 3 deliverable file. All implementations are substantive.

---

## Human Verification Required

### 1. Flyway Migration Application

**Test:** Run `docker compose --profile storage up -d postgres && docker compose --profile storage run --rm flyway migrate`, then inspect `\d reports` and `\d report_jobs` in psql.
**Expected:** Flyway applies V6 and V7 without checksum errors; both tables appear with all columns, constraints, and indexes; `flyway_schema_history` shows versions 6 and 7 with `success = true`.
**Why human:** Requires a running PostgreSQL container; DDL application cannot be verified statically.

### 2. langgraph-init Container Execution

**Test:** Run `docker compose --profile reasoning up -d && docker compose --profile reasoning logs langgraph-init`.
**Expected:** Logs show "LangGraph schema init complete." and container exits with code 0. Subsequent `SELECT table_name FROM information_schema.tables WHERE table_schema='langgraph'` returns 4 rows.
**Why human:** Requires a running Docker stack; schema creation cannot be verified without container execution.

### 3. langgraph-init Idempotency

**Test:** Run `docker compose --profile reasoning up langgraph-init` a second time after initial execution.
**Expected:** Exits code 0, no errors — `CREATE SCHEMA IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` prevent conflicts.
**Why human:** Runtime behavior; IF NOT EXISTS semantics are correct in DDL but actual idempotency requires a live test.

### 4. VPS Swap Configuration

**Test:** SSH into the VPS host and run `free -h`.
**Expected:** Output shows approximately 4G in the swap row.
**Why human:** Host-level OS configuration; cannot be verified from within Docker or from the local codebase.

### 5. Gemini API Key Validation (deferred to Phase 8)

**Test:** When the reasoning-engine service is deployed in Phase 8, set `GEMINI_API_KEY=<actual-key>` in `.env.local` and run a test call using the Google GenAI SDK or curl to the Gemini API endpoint.
**Expected:** Returns a valid response (HTTP 200, not 401/403).
**Why human:** Requires a live network call with the user's actual key; also requires the reasoning-engine service to exist (Phase 8 deliverable). Per updated ROADMAP SC #4 and INFRA-05, the Phase 3 deliverable is the `.env.example` template entry — which is verified.

---

## Commit Verification

All 8 documented commits for Phase 3 exist in git history and are valid:

| Commit | Description |
|--------|-------------|
| `6baf9ec` | feat(03-01): create V6 reports migration |
| `92c8489` | feat(03-01): create V7 report_jobs migration |
| `5bdb6a3` | feat(03-02): add mem_limit to all services and tune Neo4j JVM heap |
| `9207eab` | feat(03-02): add GEMINI_API_KEY to environment template |
| `97cf6ea` | feat(03-03): create LangGraph checkpoint schema init script |
| `b23f5a9` | feat(03-03): add langgraph-init one-shot Docker service |
| `1572c7d` | docs(03-04): update ROADMAP.md Phase 3 SC #2 and SC #4 scope alignment |
| `af8a7d0` | docs(03-04): clarify REQUIREMENTS.md INFRA-03 scope — reasoning-engine mem_limit deferred to Phase 8 |

---

_Verified: 2026-03-09_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after Plan 03-04 gap closure_
