-- =============================================================================
-- V1__initial_schema.sql — Initial PostgreSQL Schema
-- Phase 1 | Plan 02 | Requirement: INFRA-01, DATA-07, DATA-08
-- =============================================================================
--
-- CONVENTION: Every time-series table MUST include:
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the data was valid in the real world
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- This convention is enforced by requirement DATA-07.
-- Phase 2 migrations will add tables following this pattern.
--

-- =============================================================================
-- Pipeline Run Log (DATA-08)
--
-- Tracks each execution of a data ingestion pipeline:
--   - pipeline_name: identifies which pipeline ran (e.g., 'fred_indicators', 'gold_price')
--   - run_at: when the pipeline execution started
--   - status: outcome of the run (success / failure / partial)
--   - rows_ingested: number of rows written on success or partial run
--   - error_message: failure detail when status = 'failure' or 'partial'
--   - duration_ms: wall-clock duration of the pipeline run
--   - data_as_of: the as-of date of the data ingested (follows timestamp convention)
--   - ingested_at: when this log row was written (follows timestamp convention)
-- =============================================================================
CREATE TABLE pipeline_run_log (
    id             BIGSERIAL    PRIMARY KEY,
    pipeline_name  VARCHAR(255) NOT NULL,
    run_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    status         VARCHAR(50)  NOT NULL CHECK (status IN ('success', 'failure', 'partial')),
    rows_ingested  INTEGER,
    error_message  TEXT,
    duration_ms    INTEGER,
    data_as_of     TIMESTAMPTZ  NOT NULL,
    ingested_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index for looking up recent runs by pipeline
CREATE INDEX idx_pipeline_run_log_pipeline_name ON pipeline_run_log (pipeline_name);
CREATE INDEX idx_pipeline_run_log_run_at ON pipeline_run_log (run_at DESC);
CREATE INDEX idx_pipeline_run_log_data_as_of ON pipeline_run_log (data_as_of DESC);
