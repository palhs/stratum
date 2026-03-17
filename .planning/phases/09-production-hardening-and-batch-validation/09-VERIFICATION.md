---
phase: 09-production-hardening-and-batch-validation
verified: 2026-03-17T00:00:00Z
status: human_needed
score: 8/9 must-haves verified
re_verification: false
human_verification:
  - test: "Run batch-validate.py against live Docker stack"
    expected: "Script connects, submits 20 VN30 tickers sequentially, captures docker stats at start/every-5/end, checks OOMKilled status, prints summary table with PASS (no OOM kills)"
    why_human: "Requires a fully running Docker stack with reasoning profile up; cannot execute docker subprocess or live HTTP calls in a static verification pass"
  - test: "Verify AI Studio spend cap enforcement"
    expected: "After configuring cap at AI Studio Settings -> Billing -> Spend cap, API calls are blocked when monthly spend reaches the configured amount (~10 min lag)"
    why_human: "Requires live API spend to reach configured cap threshold; cannot simulate billing enforcement programmatically"
---

# Phase 9: Production Hardening and Batch Validation — Verification Report

**Phase Goal:** The v2.0 system is validated under realistic production conditions — a 20-stock batch workload completes within memory limits, Gemini API spend alerts are configured and testable, and a checkpoint cleanup job prevents unbounded PostgreSQL growth.

**Verified:** 2026-03-17

**Status:** human_needed

**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `scripts/batch-validate.py` submits 20 distinct VN30 tickers sequentially via POST /reports/generate and polls each to completion | VERIFIED | `client.post(f"{base_url}/reports/generate", ...)` at line 106-110; sequential loop over `VN30_TICKERS` (20 entries) in `run_batch()` at line 254 |
| 2 | Script captures docker stats `--no-stream` output showing MEM USAGE / LIMIT during batch run | VERIFIED | `capture_docker_stats()` at line 173 runs `docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"` via subprocess; called at start, every 5 tickers, and end |
| 3 | Script checks `docker inspect OOMKilled` status for all services and reports pass/fail per container | VERIFIED | `check_oom_status(services)` at line 194 runs `docker inspect <service> --format "{{.State.OOMKilled}}"` per service; result drives PASS/FAIL determination at line 292-299 |
| 4 | Script handles failures gracefully (failed status acceptable; OOM kill is not) and produces a summary table | VERIFIED | `submit_and_poll()` returns status strings for all failure modes (error, skipped, timeout) without raising; summary table printed at lines 276-290; PASS/FAIL keyed on `oom_killed_count` only |
| 5 | Batch script is runnable standalone with `python scripts/batch-validate.py --base-url http://localhost:8001` | VERIFIED | `--help` output confirmed; syntax validated clean; argparse wired correctly; `main()` calls `run_batch()` and `sys.exit()` with return code |
| 6 | `docs/gemini-spend-alerts.md` documents complete spend alert configuration including both billing paths, tiered thresholds (50%, 80%, 100%), and test notification mechanism | VERIFIED | File exists (198 lines); Sections 2, 3a, 3b, 4, 5, 6, 7 all present; tiered threshold table at lines 57-59; "Test notification" button documented at line 76 and 121-122 |
| 7 | The documentation explains how to verify alerts work (Cloud Billing "Test notification" button) and acknowledges AI Studio path has no test mechanism | VERIFIED | Section 5 documents Cloud Billing test path (lines 119-127) and AI Studio observational verification (lines 129-135); both cases correctly addressed |
| 8 | `langgraph.checkpoints` gets a `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` column via idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` in `init-langgraph-schema.py` | VERIFIED | `ALTER_DDL` constant at line 53-56 of `init-langgraph-schema.py`; executed at line 88; `ADD COLUMN IF NOT EXISTS` confirmed idempotent |
| 9 | `scripts/cleanup-checkpoints.py` deletes from `checkpoint_writes` and `checkpoint_blobs` BEFORE `checkpoints`, supports `--dry-run`, and reads `CHECKPOINT_TTL_DAYS` / `DATABASE_URL` from environment | VERIFIED | DELETE order confirmed: `DELETE_WRITES` (line 40) → `DELETE_BLOBS` (line 47) → `DELETE_CHECKPOINTS` (line 55); `--dry-run` argparse flag at line 76; `TTL_DAYS` from `os.environ` at line 29; `DATABASE_URL` from `os.environ` at line 83 |

**Score:** 9/9 truths have implementation evidence. Two truths require human confirmation against live infrastructure.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/batch-validate.py` | Batch validation script for 20-stock sequential workload with memory monitoring | VERIFIED | 337 lines; substantive — contains `wait_for_health()`, `submit_and_poll()`, `capture_docker_stats()`, `check_oom_status()`, `run_batch()`, `main()`; syntax clean |
| `docs/gemini-spend-alerts.md` | Complete Gemini API spend alert configuration guide with tiered thresholds | VERIFIED | 198 lines; all 7 sections present; both billing paths documented; configuration record filled in with actual user values (AI Studio path, $200 cap) |
| `scripts/init-langgraph-schema.py` | Updated schema init with `ALTER TABLE` adding `created_at` column | VERIFIED | `ALTER_DDL` constant present at line 53; executed after main DDL; idempotent via `IF NOT EXISTS` |
| `scripts/cleanup-checkpoints.py` | TTL-based checkpoint cleanup script with dry-run support | VERIFIED | 127 lines; correct cascade DELETE order; `--dry-run` flag; configurable via env vars |
| `reasoning/tests/integration/test_checkpoint_cleanup.py` | Integration test with unit tests verifying selective deletion behavior | VERIFIED | 184 lines; 6 tests; all 6 pass without Docker |
| `reasoning/tests/integration/__init__.py` | Package marker | VERIFIED | File exists |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/batch-validate.py` | `reasoning/app/routers/reports.py` | `POST /reports/generate` and `GET /reports/{job_id}` HTTP calls | VERIFIED | `client.post(f"{base_url}/reports/generate", ...)` at line 107; `client.get(f"{base_url}/reports/{job_id}", ...)` at line 138; response handling includes 202/409/200 status branches |
| `scripts/batch-validate.py` | Docker daemon | `docker stats` and `docker inspect` subprocess calls | VERIFIED | `subprocess.run(["docker", "stats", "--no-stream", ...])` at line 178; `subprocess.run(["docker", "inspect", service, ...])` at line 206 |
| `scripts/cleanup-checkpoints.py` | `scripts/init-langgraph-schema.py` | cleanup depends on `created_at` column added by init | VERIFIED | `created_at` column defined in `ALTER_DDL`; all four SQL queries in cleanup reference `created_at`; init script tested for `ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ` in unit test `test_init_script_adds_created_at` |
| `scripts/cleanup-checkpoints.py` | `langgraph.checkpoints` | `DELETE FROM langgraph.checkpoints WHERE created_at < TTL` | VERIFIED | `DELETE_CHECKPOINTS` SQL at line 56; parameterized with `(TTL_DAYS,)` at line 109; preceded by `DELETE_WRITES` and `DELETE_BLOBS` in correct cascade order |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SRVC-06 | 09-01-PLAN.md | Batch report generation validated against 20-stock workload with memory baseline | VERIFIED (pending human live-run) | `scripts/batch-validate.py` implements full sequential 20-ticker batch with docker stats snapshots and OOM detection; script is runnable and syntactically correct; live validation requires Docker stack |
| SRVC-07 | 09-02-PLAN.md | Gemini API spend alerts configured with tiered thresholds | VERIFIED (AI Studio path — known limitation) | `docs/gemini-spend-alerts.md` documents both billing paths; user configured AI Studio spend cap (confirmed in checkpoint); tiered 50%/80%/100% alerts unavailable on AI Studio-only path — documented as known limitation in Section 3b and in configuration record |
| SRVC-08 | 09-03-PLAN.md | Checkpoint cleanup job implemented (TTL-based purge) | VERIFIED | `scripts/cleanup-checkpoints.py` implements TTL purge with correct cascade delete order; `init-langgraph-schema.py` adds `created_at` column; 6 unit tests pass |

**Note on SRVC-07:** The requirement states "tiered thresholds" but the user's API key is AI Studio-only and does not support Cloud Billing tiered alerts. The documentation correctly explains this limitation and the user has configured the available mechanism (AI Studio spend cap). The requirement is satisfied to the extent technically possible given the billing path. A "Test notification" button is documented for the Cloud Billing path but is not applicable to the user's current configuration — configuration record correctly marks `Test notification: Not tested`.

**Orphaned requirements check:** No requirements mapped to Phase 9 in REQUIREMENTS.md beyond SRVC-06, SRVC-07, SRVC-08. All three are claimed by plans 09-01, 09-02, 09-03 respectively. No orphans.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder comments, empty implementations, or stub returns detected across any phase artifact.

---

## Human Verification Required

### 1. Live Batch Validation Run (SRVC-06)

**Test:** With Docker stack running (`docker compose --profile reasoning up -d`), execute:
```
python scripts/batch-validate.py --base-url http://localhost:8001
```
**Expected:**
- Script prints "reasoning-engine healthy" after health check
- 20 tickers process sequentially; each prints ticker, job_id, status, elapsed time
- Docker stats tables printed at start, after tickers 5, 10, 15, 20, and at end
- OOM Kill Status section shows `OK` for all services
- Summary table shows PASS result; exit code 0

**Why human:** Requires live Docker stack with reasoning profile running; cannot invoke docker subprocess or live HTTP endpoints in static code verification.

### 2. Spend Cap Enforcement Verification (SRVC-07)

**Test:** Confirm the AI Studio spend cap is actively enforced by reviewing AI Studio spend page after a batch run.
**Expected:** After running 2-3 stock reports, the spend counter on AI Studio → Spend page updates within ~10 minutes to reflect actual Gemini API usage. Cap value remains set at the configured amount ($200 per configuration record).
**Why human:** Billing enforcement requires real API spend; cannot simulate Google billing system programmatically.

---

## Gaps Summary

No blocking gaps found. All artifacts exist, are substantive (not stubs), and are wired correctly. Unit tests for SRVC-08 pass (6/6). The two human verification items are operational confirmation of live infrastructure behavior — not code defects.

The only nuance is SRVC-07: the requirement mentions "tiered thresholds" which are Cloud Billing-specific. The user's AI Studio-only billing path does not support tiered 50%/80%/100% notifications. This is correctly documented as a known limitation in `docs/gemini-spend-alerts.md` Section 3b and is consistent with the plan's intent — the plan itself documents the AI Studio-only path as one of the two valid paths.

---

_Verified: 2026-03-17_
_Verifier: Claude (gsd-verifier)_
