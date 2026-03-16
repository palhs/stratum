# Phase 9: Production Hardening and Batch Validation - Research

**Researched:** 2026-03-16
**Domain:** Docker memory management, Gemini API cost alerting, PostgreSQL checkpoint TTL cleanup
**Confidence:** MEDIUM — Docker memory and PostgreSQL cleanup patterns are well-understood; Gemini API spend alerting has a critical nuance (see below)

---

## Summary

Phase 9 has three independent tracks: (1) validate that a 20-stock batch run stays within Docker `mem_limit` bounds, (2) configure tiered Gemini API spend alerts and document them, (3) implement a TTL-based checkpoint cleanup job for the LangGraph PostgreSQL tables.

The batch validation track is a **manual/integration-only** test: it requires running the live Docker stack, firing 20 sequential `POST /reports/generate` requests, and monitoring `docker stats`. No automated unit test can substitute for this — the success criterion is observational. The correct deliverable is a runnable shell script that invokes the batch and a documented baseline.

The Gemini API alerting track has an important split: **Google AI Studio** (where the Gemini API key lives) provides a simple per-project monthly spend cap, while **Google Cloud Billing budgets** provide tiered threshold rules with email/Pub/Sub notifications. If the project's Gemini API key is billed through a Google Cloud project (the standard paid-tier setup), Cloud Billing budgets are the correct tool and support any number of threshold tiers. If it is a pure AI Studio key with no Cloud project, only the AI Studio spend cap is available. The project must document which billing path applies.

The checkpoint cleanup track is the most complex. LangGraph's built-in TTL is only available on **LangGraph Platform** (managed cloud), not on the self-hosted OSS stack this project uses. For self-hosted PostgreSQL, the correct approach is a standalone Python cleanup script that runs direct SQL `DELETE` against the `langgraph.checkpoints` table using a `metadata->>'thread_ts'` timestamp or, more reliably, uses `AsyncPostgresSaver.adelete_thread()` per thread for threads older than a configured TTL. The checkpoint schema does **not** have a standalone `created_at` column — deletion must be driven either by the LangGraph API or by reading `checkpoint` JSONB metadata.

**Primary recommendation:** Implement the three tracks as separate, independently runnable scripts/jobs; plan them as three separate tasks. The batch script and cleanup job are runnable standalone. The spend alert setup is a one-time configuration documented in the repo.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRVC-06 | Batch report generation validated against 20-stock workload with memory baseline | Docker stats monitoring during sequential batch run; shell script to drive 20 `POST /reports/generate` requests; verify no service exceeds its `mem_limit` |
| SRVC-07 | Gemini API spend alerts configured with tiered thresholds; test alert fires correctly; configuration documented | Google Cloud Billing budget with multiple threshold rules (e.g. 50%, 80%, 100%); email notification channel; configuration YAML/screenshot committed to repo |
| SRVC-08 | Checkpoint cleanup job: TTL-based purge of langgraph checkpoint tables; test with synthetic old records; no affect on recent records | Standalone Python script targeting `langgraph.checkpoints`, `langgraph.checkpoint_blobs`, `langgraph.checkpoint_writes`; TTL configurable via env var; delete-by-thread-id cascade |
</phase_requirements>

---

## Standard Stack

### Core

| Component | Version/Tool | Purpose | Why This |
|-----------|-------------|---------|----------|
| `docker stats` CLI | Docker 24+ | Observe per-container memory during batch run | Built-in; shows `MEM USAGE / LIMIT` column; `--no-stream` gives snapshot |
| Google Cloud Billing Console | n/a (web UI) | Create budget with tiered threshold rules | Only mechanism for multi-threshold email alerts on Gemini API spend |
| AI Studio Spend Page | n/a (web UI) | Set project-level monthly spend cap | Hard cap (experimental); complementary to billing alerts |
| `psycopg` (psycopg3) | `psycopg[binary]` (already in stack) | Execute cleanup SQL against langgraph schema | Already used by `init-langgraph-schema.py`; no new dep |
| `langgraph-checkpoint-postgres` | Already in requirements.txt | `AsyncPostgresSaver.adelete_thread()` — soft API for per-thread cleanup | Avoids raw SQL against internal JSONB; cleaner than hand-writing DELETE |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| `requests` or `httpx` | Already in stack (httpx) | Drive batch HTTP requests in the test script | Use `httpx` (already a dep) for the batch validation script |
| `time` / `datetime` | stdlib | TTL age computation in cleanup script | stdlib — no extra dep |
| `asyncio` | stdlib | Required for `AsyncPostgresSaver.adelete_thread()` | If using the API-level cleanup path |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Cloud Billing budget alerts | AI Studio spend cap only | Spend cap is a hard stop (not a notification); cap alone does not provide tiered alert emails — both should be used together |
| `AsyncPostgresSaver.adelete_thread()` | Direct SQL `DELETE FROM langgraph.checkpoints WHERE ...` | Direct SQL is simpler but the schema lacks a top-level `created_at` column; thread timestamps are embedded in JSONB `metadata` making SQL-level age filtering fragile. API-level deletion handles cascade to `checkpoint_blobs` and `checkpoint_writes` correctly |
| Direct SQL DELETE (all tables) | CASCADE via FK if added | LangGraph's OSS schema does not define FK cascades between `checkpoints`, `checkpoint_blobs`, and `checkpoint_writes` — deleting from `checkpoints` alone leaves orphaned rows in sibling tables |

---

## Architecture Patterns

### Pattern 1: Batch Validation Script (SRVC-06)

**What:** A shell or Python script that submits 20 sequential `POST /reports/generate` requests to the running `reasoning-engine` service, polls each job to completion, and captures `docker stats --no-stream` output during the run.

**When to use:** Run manually against a fully-started Docker stack (`docker compose --profile reasoning up -d`).

**Key constraint from existing code:** The `_find_active_job()` check in `reports.py` returns 409 if a pending/running job exists for the same `asset_id`. The batch script must use 20 distinct tickers (not the same ticker 20 times), or wait for each job to complete before submitting the next.

**Sequence:**
1. Start all services with `docker compose --profile reasoning up -d`
2. Wait for `reasoning-engine` healthcheck to pass
3. Submit batch: for each of 20 VN30 tickers, `POST /reports/generate`
4. Poll `GET /reports/{job_id}` until `status == "completed"` or `"failed"`
5. After all jobs settle, capture `docker stats --no-stream` and compare each service's `MEM USAGE` against its `mem_limit`
6. Assert no service shows OOM exit (`docker inspect <container> | grep OOMKilled`)

**Recommended VN30 tickers (20):** VHM, VNM, VCB, BID, VPB, TCB, MBB, CTG, HPG, MSN, VIC, GAS, SAB, FPT, MWG, REE, VJC, HDB, STB, ACB — these 20 are large-cap VN30 constituents with sufficient data in the corpus.

**Baseline targets (already defined in `docker-compose.yml`):**

| Service | `mem_limit` |
|---------|------------|
| postgres | 512m |
| neo4j | 2g |
| qdrant | 1g |
| n8n | 512m |
| data-sidecar | 512m |
| reasoning-engine | 2g |

**Memory pressure concern:** Each pipeline run invokes 6 Gemini API calls (one per node that calls Gemini) and holds LangGraph state in memory until `run_graph()` returns. With sequential processing, peak memory is one-pipeline-at-a-time, which is manageable. If concurrent submissions are used, multiple pipelines could overlap — **use sequential processing** for this validation.

### Pattern 2: Gemini API Spend Alert Configuration (SRVC-07)

**What:** Google Cloud Billing budget with three threshold rules — 50%, 80%, 100% of a monthly budget amount — configured with email notifications to the billing account admin, plus an AI Studio monthly spend cap as a hard stop.

**Steps:**
1. In Google Cloud Console → Billing → Budgets & alerts → Create Budget
2. Scope: select the Cloud project linked to the Gemini API key
3. Budget amount: set in USD (e.g., $20/month as a conservative starting budget for a single-user system)
4. Alert threshold rules: Add three rules — 50% (actual), 80% (actual), 100% (actual) — customizable
5. Notification: enable "Email alerts to billing admins and users"; optionally add a Cloud Monitoring notification channel for custom email
6. In AI Studio → Spend page: set monthly spend cap as a safety backstop

**Documentation deliverable:** A `docs/gemini-spend-alerts.md` (or inline in `.planning/`) that records:
- The budget amount and threshold tiers chosen
- How to verify an alert (Cloud Billing has a "Test notification" button per rule in the UI)
- The AI Studio spend cap value

**Testing:** Google Cloud Billing provides a **"Test notification"** button in the budget UI that fires the configured notification channel without requiring actual spend. This is the correct "test alert fires" mechanism per the success criterion.

**Confidence note (MEDIUM):** The "Test notification" button exists per official Cloud Billing docs fetched above. Confirmed via the Create/Edit budgets page. AI Studio spend cap is marked "experimental" in the docs — it may change behavior. Both mechanisms should be configured for defense in depth.

### Pattern 3: Checkpoint Cleanup Job (SRVC-08)

**What:** A standalone Python script (`scripts/cleanup-checkpoints.py`) that connects to PostgreSQL, identifies `thread_id` values in `langgraph.checkpoints` older than a configured TTL, and deletes them using `AsyncPostgresSaver.adelete_thread()`.

**Critical schema finding:** The `langgraph.checkpoints` table (as defined in `scripts/init-langgraph-schema.py`) has this schema:

```sql
CREATE TABLE IF NOT EXISTS langgraph.checkpoints (
    thread_id            TEXT NOT NULL,
    checkpoint_ns        TEXT NOT NULL DEFAULT '',
    checkpoint_id        TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type                 TEXT,
    checkpoint           JSONB NOT NULL,
    metadata             JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

There is **no `created_at` column**. Age must be inferred from `checkpoint_id`, which is a UUID v1 (time-based) in LangGraph's current implementation, or from `metadata->>'thread_ts'` if present. The most reliable approach is: query distinct `thread_id` values, then check the most recent `checkpoint_id` timestamp per thread using `checkpoint_id` UUID timestamp extraction — or add a `created_at` column via a Flyway migration (V8) to make the cleanup query straightforward.

**Recommended approach — add `created_at` via Flyway migration:**

```sql
-- V8__checkpoint_created_at.sql
ALTER TABLE langgraph.checkpoints
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
```

This is the cleanest solution. Once the column exists, cleanup is a simple `DELETE FROM langgraph.checkpoints WHERE created_at < NOW() - INTERVAL '{TTL}'` — but must also clean sibling tables. Since LangGraph's schema has no FK cascade, the cleanup script must delete from all three tables:

```python
# Cleanup order: checkpoint_writes and checkpoint_blobs first (reference thread_id),
# then checkpoints last (the primary table)
DELETE FROM langgraph.checkpoint_writes
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(secs => :ttl_seconds)
    );

DELETE FROM langgraph.checkpoint_blobs
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(secs => :ttl_seconds)
    );

DELETE FROM langgraph.checkpoints
    WHERE created_at < NOW() - make_interval(secs => :ttl_seconds);
```

**Alternative approach — use `AsyncPostgresSaver.adelete_thread()` per thread:**
If avoiding schema migrations, use the LangGraph API:
1. Query distinct `thread_id` values from `langgraph.checkpoints`
2. Filter by age using UUID v1 timestamp extraction from `checkpoint_id` (fragile, UUIDs may be v4 depending on LangGraph version)
3. Call `await saver.adelete_thread(thread_id)` for each expired thread

This is cleaner from a library-coupling perspective but requires the UUID timestamp extraction hack if no `created_at` column exists.

**Recommended:** Add `created_at` via Flyway migration (V8) — gives a clean SQL timestamp, eliminates UUID parsing fragility, and aligns with the project's migration-driven schema management. The migration is minimal (one `ALTER TABLE`) and idempotent via `IF NOT EXISTS`.

**Script interface:**
```
CHECKPOINT_TTL_DAYS=7  # configurable via env
DATABASE_URL=...       # same as reasoning-engine env
python scripts/cleanup-checkpoints.py [--dry-run]
```

**Validation test:** Insert synthetic `langgraph.checkpoints` rows with `created_at` set to `NOW() - INTERVAL '8 days'` (older than 7-day TTL) and rows with `created_at = NOW()` (recent). Run the script. Assert old rows are deleted and recent rows survive.

### Anti-Patterns to Avoid

- **Submitting the same ticker 20 times in the batch:** The 409 guard in `reports.py` will reject duplicates while a job is still running/pending. Use 20 distinct tickers.
- **Relying on `docker stats` percentage alone:** MEM% is relative to the host, not the container limit. Use `MEM USAGE / LIMIT` column and compare to known `mem_limit` values from `docker-compose.yml`.
- **Deleting from `langgraph.checkpoints` without first deleting from `checkpoint_blobs` and `checkpoint_writes`:** No FK cascade exists — orphaned rows accumulate. Always delete sibling tables first, then the primary `checkpoints` table.
- **Using AI Studio spend cap as the sole alert mechanism:** The cap is a hard stop with ~10 min billing data lag, meaning overages can still occur. It is not a notification system. Cloud Billing budget alerts (email) are the correct alerting mechanism.
- **Manual SQL UUID timestamp extraction from `checkpoint_id`:** LangGraph does not guarantee UUID v1 format across versions. This is fragile. Add a `created_at` column via Flyway.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container memory monitoring | Custom cgroup reader | `docker stats --no-stream --format "table ..."` | Built-in, works across all Docker versions, returns structured output parseable by shell |
| Gemini API spend tracking | Custom token counter | Google Cloud Billing budget alerts + AI Studio spend cap | Token counting is inaccurate (batching, system prompts, retries); billing API is the authoritative source |
| Checkpoint age computation via UUID parsing | Custom UUID v1 timestamp extractor | Flyway V8 migration adding `created_at` column | UUID format is an implementation detail; `created_at` is stable and explicit |
| Multi-tier spend alerting logic | Custom spend monitoring webhook | Cloud Billing Pub/Sub programmatic notifications | Google sends notifications multiple times per day automatically; no need to build a poller |

---

## Common Pitfalls

### Pitfall 1: OOM Kill During Batch Is a Race, Not a Constant
**What goes wrong:** A single pipeline run may not OOM, but the 15th run in sequence has accumulated leaked memory in the reasoning-engine process (Python doesn't always GC between requests).
**Why it happens:** FastAPI uses a persistent process; SQLAlchemy connection pool keeps connections open; LangGraph state dicts may not be GC'd immediately.
**How to avoid:** Run the full 20-stock sequence (not just a few) before declaring pass. Watch `reasoning-engine` memory specifically — it carries the LangGraph graph and all Gemini response objects.
**Warning signs:** MEM USAGE of `reasoning-engine` creeping upward with each successive report generation, not returning to baseline.

### Pitfall 2: `docker stats` Shows Container Memory Above `mem_limit`
**What goes wrong:** Seeing MEM USAGE apparently exceed `mem_limit` in `docker stats` output.
**Why it happens:** `docker stats` shows memory including cache. On Linux, the CLI subtracts cache; the API value is raw. The relevant comparison is RSS (working set), which Docker stats approximates after cache subtraction.
**How to avoid:** Check `docker inspect <container_name> | grep OOMKilled` for actual OOM events. `OOMKilled: false` is the definitive pass condition, not just staying under the displayed limit number.

### Pitfall 3: Gemini API Key Not Linked to a Cloud Project (AI Studio Free/Pay-As-You-Go)
**What goes wrong:** You navigate to Cloud Billing but find no project-level spend data for the Gemini API key.
**Why it happens:** Some Gemini API keys are provisioned via AI Studio directly without being linked to a Google Cloud project with a billing account.
**How to avoid:** Check AI Studio → Settings → Billing to confirm whether the key is linked to a Cloud project. If yes, use Cloud Billing budgets. If no, only the AI Studio spend cap is available; document this limitation explicitly.

### Pitfall 4: Checkpoint Cleanup Script Affects Running Pipelines
**What goes wrong:** The cleanup script runs while a pipeline is mid-execution, deletes the active thread's intermediate checkpoints, and the pipeline fails on resume.
**Why it happens:** The cleanup script doesn't know which threads are currently active.
**How to avoid:** Run the cleanup script at a quiet time (e.g., as a cron job at 3am) or add a guard: only delete threads whose most recent checkpoint `created_at` is older than TTL (i.e., no recent activity). The SQL-based approach with `created_at` naturally handles this — an active thread has a recent `created_at` and won't be selected.

### Pitfall 5: Flyway Migration Fails if LangGraph Schema Not Present
**What goes wrong:** V8 migration runs before `langgraph-init` has created the `langgraph.checkpoints` table, causing a Flyway error.
**Why it happens:** Flyway runs in the `storage` profile; `langgraph-init` runs only in the `reasoning` profile.
**How to avoid:** Make the V8 migration conditional — use `DO $$ ... IF NOT EXISTS ... $$` pattern, or target only the `public` schema in Flyway and run the `langgraph.checkpoints` alteration from within the `init-langgraph-schema.py` script instead. **Recommended:** Add the `created_at` column DDL to `init-langgraph-schema.py` (already the authoritative location for langgraph schema DDL) rather than Flyway.

---

## Code Examples

### Batch validation script (skeleton)
```python
# scripts/batch-validate.py
# Usage: python scripts/batch-validate.py --base-url http://localhost:8001
import httpx, time, sys

VN30_TICKERS = [
    "VHM", "VNM", "VCB", "BID", "VPB",
    "TCB", "MBB", "CTG", "HPG", "MSN",
    "VIC", "GAS", "SAB", "FPT", "MWG",
    "REE", "VJC", "HDB", "STB", "ACB",
]

def run_batch(base_url: str):
    job_ids = []
    for ticker in VN30_TICKERS:
        r = httpx.post(f"{base_url}/reports/generate",
                       json={"ticker": ticker, "asset_type": "equity"})
        assert r.status_code == 202, f"{ticker}: {r.status_code} {r.text}"
        job_id = r.json()["job_id"]
        job_ids.append((ticker, job_id))
        print(f"Submitted {ticker} → job_id={job_id}")
        # Poll until complete before next submit (sequential — avoids 409)
        _poll_until_done(base_url, ticker, job_id)
    return job_ids

def _poll_until_done(base_url, ticker, job_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(f"{base_url}/reports/{job_id}")
        status = r.json()["status"]
        if status in ("completed", "failed"):
            print(f"  {ticker} job_id={job_id} → {status}")
            return
        time.sleep(5)
    raise TimeoutError(f"{ticker} job_id={job_id} did not complete in {timeout}s")
```

### Checkpoint cleanup script (skeleton)
```python
# scripts/cleanup-checkpoints.py
# Usage: CHECKPOINT_TTL_DAYS=7 DATABASE_URL=... python scripts/cleanup-checkpoints.py
import os, asyncio, psycopg
from datetime import timedelta

TTL_DAYS = int(os.environ.get("CHECKPOINT_TTL_DAYS", "7"))
DATABASE_URL = os.environ["DATABASE_URL"]

# SQL: delete from sibling tables first, then checkpoints
# Requires created_at column added to langgraph.checkpoints (see init-langgraph-schema.py)
DELETE_WRITES = """
    DELETE FROM langgraph.checkpoint_writes
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(days => %s)
    )
"""
DELETE_BLOBS = """
    DELETE FROM langgraph.checkpoint_blobs
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(days => %s)
    )
"""
DELETE_CHECKPOINTS = """
    DELETE FROM langgraph.checkpoints
    WHERE created_at < NOW() - make_interval(days => %s)
"""
COUNT_QUERY = """
    SELECT COUNT(*) FROM langgraph.checkpoints
    WHERE created_at < NOW() - make_interval(days => %s)
"""

def main():
    with psycopg.connect(DATABASE_URL, options="-csearch_path=langgraph") as conn:
        count_result = conn.execute(COUNT_QUERY, (TTL_DAYS,)).fetchone()
        expired_count = count_result[0] if count_result else 0
        print(f"Found {expired_count} checkpoint thread(s) older than {TTL_DAYS} days")
        if expired_count == 0:
            print("Nothing to clean up.")
            return
        conn.execute(DELETE_WRITES, (TTL_DAYS,))
        conn.execute(DELETE_BLOBS, (TTL_DAYS,))
        result = conn.execute(DELETE_CHECKPOINTS, (TTL_DAYS,))
        conn.commit()
        print(f"Deleted {result.rowcount} checkpoint row(s)")

if __name__ == "__main__":
    main()
```

### docker stats snapshot command
```bash
# Capture a one-time snapshot of all service memory during batch run
docker stats --no-stream --format \
  "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" \
  stratum-postgres-1 stratum-neo4j-1 stratum-qdrant-1 \
  stratum-reasoning-engine-1
```

### Check OOM kill status
```bash
# Definitive OOM check — false = no OOM kill
docker inspect stratum-reasoning-engine-1 | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('OOMKilled:', d[0]['State']['OOMKilled'])"
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| LangGraph TTL via `langgraph.json` | Only works on LangGraph Platform (managed) | Self-hosted OSS has no built-in TTL; custom cleanup script is required |
| `deploy.resources.limits` in docker-compose | `mem_limit` (legacy key) | Project is already using `mem_limit` (locked decision from Phase 3-02); do not change |
| Gemini API budget alerts via AI Studio only | Cloud Billing budget (multi-threshold) + AI Studio spend cap | Two-layer approach: alerts + hard cap |

---

## Open Questions

1. **Is the Gemini API key linked to a Google Cloud project with a billing account?**
   - What we know: The key is in `.env` as `GEMINI_API_KEY`; Phase 3 decision deferred live API validation to Phase 8
   - What's unclear: Whether this is a pure AI Studio key or a Cloud project key — determines whether Cloud Billing budgets apply
   - Recommendation: Check AI Studio → Settings → Billing before implementing. If Cloud-project-linked, implement Cloud Billing budget. If AI Studio only, document the spend cap as the sole mechanism and note the limitation.

2. **Should the cleanup script be a cron job inside Docker or a standalone script?**
   - What we know: The project has no existing cron/scheduler service; success criterion says "a test run confirms deletion"
   - What's unclear: Whether a recurring schedule is required or just a runnable script
   - Recommendation: Implement as a standalone Python script (`scripts/cleanup-checkpoints.py`) with clear documentation on how to run it manually or schedule it. A Docker `cleanup-runner` one-shot service (similar to `seed-runner`) can be added to `docker-compose.yml` with a `cleanup` profile for easy invocation. Cron scheduling on the host/VPS is out of scope for this phase.

3. **Which VN30 tickers have sufficient data in the PostgreSQL `fundamentals` and `structure_markers` tables for a successful pipeline run?**
   - What we know: 12 large-cap VN30 tickers have English IR reports (lang=en); 18 have Vietnamese with degraded-embedding-quality warnings; fundamentals data depends on what the n8n ingestion workflows have populated
   - What's unclear: Whether all 20 proposed tickers will produce `completed` status or `failed` due to missing fundamentals data
   - Recommendation: The batch validation script should tolerate `failed` jobs as long as the pipeline failure is not due to OOM. OOM criteria is `docker inspect OOMKilled: false`, not zero failed jobs. Document expected failures clearly.

---

## Sources

### Primary (HIGH confidence)
- Docker official docs (resource constraints) — `mem_limit` behavior, OOM kill mechanism, `docker stats` columns
- Google Cloud Billing docs (`docs.cloud.google.com/billing/docs/how-to/budgets`) — budget creation, threshold rules, notification channels
- Project source: `scripts/init-langgraph-schema.py` — definitive langgraph schema (no `created_at` column confirmed)
- Project source: `docker-compose.yml` — all service `mem_limit` values
- Project source: `reasoning/app/routers/reports.py` — 409 guard for duplicate active jobs (impacts batch sequencing)

### Secondary (MEDIUM confidence)
- Google Cloud Billing programmatic notifications docs — Pub/Sub message format and tiered alert capability
- AI Studio spend page docs — spend cap is experimental, 10-min billing lag noted
- LangChain support article — TTL only applies to LangGraph Platform, not OSS self-hosted
- LangGraph forum thread (checkpoint-cleanup/3037) — community confirms no built-in TTL in OSS; custom SQL cleanup is the recommended path

### Tertiary (LOW confidence)
- LangGraph GitHub issue #1138 (JS) — community-proposed threads table + FK cascade pattern; not official; informative for understanding cascade behavior
- `sparkco.ai` blog post on LangGraph checkpointing — references `ShallowPostgresSaver` as alternative to reduce volume; not verified against current library version

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Docker stats and psycopg3 are well-understood; Cloud Billing docs are authoritative
- Architecture: MEDIUM — Batch script is straightforward; checkpoint cleanup has the `created_at` column gap that requires a design decision (add via init script vs Flyway)
- Pitfalls: MEDIUM — OOM behavior and billing lag are verified; LangGraph TTL limitation confirmed by multiple sources

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable area; Gemini API billing UI may evolve)
