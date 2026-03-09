-- =============================================================================
-- V6__reports.sql — Reports table for storing generated analysis output
-- Phase 3 | Plan 01 | Requirement: INFRA-01
-- =============================================================================
--
-- Stores generated analysis output from the reasoning pipeline.
-- Design decisions:
--   - One row per language: each language ('vi'/'en') is a separate row per run.
--   - Keep all historical reports: every pipeline run creates a new row,
--     no upsert/overwrite — supports "how did the assessment change over time" queries.
--   - report_markdown column included: pre-rendered Markdown for Phase 7 render
--     speed, avoids on-demand rendering overhead during API reads.
--   - data_as_of: source data freshness timestamp (downstream phases use this
--     for DATA WARNING sections).
--   - model_version: audit trail for which LLM produced the report.
--   - pipeline_duration_ms: performance monitoring for Phase 9 batch validation.
--
-- Follows project timestamp convention (TIMESTAMPTZ columns):
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the source data was valid
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- =============================================================================

CREATE TABLE reports (
    report_id             BIGSERIAL    PRIMARY KEY,
    asset_id              VARCHAR(20)  NOT NULL,
    language              VARCHAR(5)   NOT NULL CHECK (language IN ('vi', 'en')),
    report_json           JSONB        NOT NULL,
    report_markdown       TEXT,
    data_as_of            TIMESTAMPTZ  NOT NULL,
    model_version         VARCHAR(100),
    pipeline_duration_ms  INTEGER,
    generated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Primary query pattern: latest report for an asset in a specific language
-- e.g., GET /reports?asset_id=VNM&language=vi ORDER BY generated_at DESC LIMIT 1
CREATE INDEX idx_reports_asset_language ON reports (asset_id, language, generated_at DESC);

-- Query pattern: all reports for an asset across languages
-- e.g., GET /reports?asset_id=VNM (both 'vi' and 'en' rows)
CREATE INDEX idx_reports_asset_id ON reports (asset_id, generated_at DESC);
