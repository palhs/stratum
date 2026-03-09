-- =============================================================================
-- V7__report_jobs.sql — Report jobs table for tracking pipeline run status
-- Phase 3 | Plan 01 | Requirement: INFRA-02
-- =============================================================================
--
-- Tracks pipeline execution status for the Phase 8 FastAPI gateway.
-- Design decisions:
--   - Simple four-state machine: pending -> running -> completed / failed.
--     No node-level tracking in the table.
--   - FK relationship: report_jobs.report_id references reports.report_id,
--     nullable until the job completes (set when status becomes 'completed').
--   - error column: TEXT for error message/traceback when status='failed',
--     avoids digging through Docker logs for debugging.
--   - One job per asset: batch runs (Phase 9) create 20 individual job rows,
--     not a parent-child hierarchy — keeps the model simple.
-- =============================================================================

CREATE TABLE report_jobs (
    job_id      BIGSERIAL   PRIMARY KEY,
    asset_id    VARCHAR(20) NOT NULL,
    status      VARCHAR(20) NOT NULL
                    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
                    DEFAULT 'pending',
    report_id   BIGINT      REFERENCES reports(report_id),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Query pattern: find jobs for an asset by status
-- e.g., SELECT * FROM report_jobs WHERE asset_id='VNM' AND status='pending'
CREATE INDEX idx_report_jobs_asset_status ON report_jobs (asset_id, status);

-- Query pattern: find all pending/running jobs (Phase 9 batch orchestration)
-- e.g., SELECT * FROM report_jobs WHERE status='pending' ORDER BY created_at DESC
CREATE INDEX idx_report_jobs_status ON report_jobs (status, created_at DESC);
