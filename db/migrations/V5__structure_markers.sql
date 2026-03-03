-- =============================================================================
-- V5__structure_markers.sql — Price Structure Markers Table
-- Phase 2 | Plan 01 | Requirements: DATA-06, DATA-07
-- =============================================================================
--
-- CONVENTION: Every time-series table MUST include:
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the data was valid in the real world
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- This convention is enforced by requirement DATA-07.
--
-- Tables created:
--   - structure_markers: Computed price structure and ranking metrics (DATA-06)
--
-- structure_markers is computed by the Stratum reasoning pipeline from raw OHLCV data.
-- It is NOT directly ingested from external APIs.
-- Computed columns: moving averages, drawdowns, percentile ranks.
-- These feed directly into the StructureAnalyzer node in the reasoning graph.
--

-- =============================================================================
-- structure_markers — Computed price structure and ranking metrics (DATA-06)
--
-- One row per (symbol, resolution, data_as_of) observation.
-- asset_type CHECK enforces valid asset categories.
-- resolution CHECK enforces 'weekly' or 'monthly' only.
-- UNIQUE(symbol, resolution, data_as_of) enables idempotent upserts.
--
-- Moving averages (ma_10w, ma_20w, ma_50w):
--   Denominated in weeks regardless of resolution, for consistency.
-- Drawdowns (drawdown_from_ath, drawdown_from_52w_high):
--   Stored as negative fractions (e.g., -0.15 = 15% below peak).
-- Percentile ranks (close_pct_rank, pe_pct_rank):
--   Range 0.0 to 1.0 (0 = cheapest ever, 1 = most expensive ever).
-- =============================================================================
CREATE TABLE structure_markers (
    id                      BIGSERIAL        PRIMARY KEY,
    symbol                  VARCHAR(20)      NOT NULL,
    asset_type              VARCHAR(20)      NOT NULL CHECK (asset_type IN ('stock', 'gold_spot', 'gold_etf')),
    resolution              VARCHAR(10)      NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    close                   NUMERIC(18, 4),
    ma_10w                  NUMERIC(18, 4),
    ma_20w                  NUMERIC(18, 4),
    ma_50w                  NUMERIC(18, 4),
    drawdown_from_ath       NUMERIC(8, 6),
    drawdown_from_52w_high  NUMERIC(8, 6),
    close_pct_rank          NUMERIC(6, 4),
    pe_pct_rank             NUMERIC(6, 4),
    data_as_of              TIMESTAMPTZ      NOT NULL,
    ingested_at             TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, resolution, data_as_of)
);

-- Index for time-series lookups
CREATE INDEX idx_structure_markers_symbol_resolution_date ON structure_markers (symbol, resolution, data_as_of DESC);
CREATE INDEX idx_structure_markers_asset_type ON structure_markers (asset_type);
