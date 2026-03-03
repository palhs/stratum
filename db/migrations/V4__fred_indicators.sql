-- =============================================================================
-- V4__fred_indicators.sql — FRED Macroeconomic Indicators Table
-- Phase 2 | Plan 01 | Requirements: DATA-05, DATA-07
-- =============================================================================
--
-- CONVENTION: Every time-series table MUST include:
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the data was valid in the real world
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- This convention is enforced by requirement DATA-07.
--
-- Tables created:
--   - fred_indicators: Macroeconomic data series from FRED API (DATA-05)
--
-- Key FRED series used by Stratum:
--   GOLDAMGBD228NLBM  — Gold price (London AM fix)
--   DFF               — Federal Funds Rate (effective)
--   T10Y2Y            — 10Y-2Y Treasury yield spread
--   CPIAUCSL          — CPI All Urban Consumers (inflation)
--   USREC             — NBER US Recession Indicators
--   DTWEXBGS          — US Dollar Index (broad)
--

-- =============================================================================
-- fred_indicators — FRED macroeconomic data series (DATA-05)
--
-- One row per (series_id, data_as_of) observation.
-- frequency column captures the native FRED series frequency ('daily', 'weekly', 'monthly', etc.).
-- UNIQUE(series_id, data_as_of) enables idempotent upserts.
-- =============================================================================
CREATE TABLE fred_indicators (
    id          BIGSERIAL        PRIMARY KEY,
    series_id   VARCHAR(50)      NOT NULL,
    value       NUMERIC(20, 6)   NOT NULL,
    frequency   VARCHAR(10)      NOT NULL,
    data_as_of  TIMESTAMPTZ      NOT NULL,
    ingested_at TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (series_id, data_as_of)
);

-- Index for time-series lookups
CREATE INDEX idx_fred_indicators_series_date ON fred_indicators (series_id, data_as_of DESC);
