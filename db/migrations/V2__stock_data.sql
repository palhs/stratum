-- =============================================================================
-- V2__stock_data.sql — Vietnamese Stock Market Data Tables
-- Phase 2 | Plan 01 | Requirements: DATA-01, DATA-02, DATA-07
-- =============================================================================
--
-- CONVENTION: Every time-series table MUST include:
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the data was valid in the real world
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- This convention is enforced by requirement DATA-07.
--
-- Tables created:
--   - stock_ohlcv:          Weekly/monthly OHLCV bars for VN30 stocks (DATA-01)
--   - stock_fundamentals:   Annual/quarterly fundamental ratios for VN30 stocks (DATA-02)
--

-- =============================================================================
-- stock_ohlcv — OHLCV bars for Vietnamese stocks (DATA-01)
--
-- Ingested via vnstock VCI source.
-- resolution CHECK enforces 'weekly' or 'monthly' only (single table — no separate tables per resolution).
-- UNIQUE(symbol, resolution, data_as_of) enables idempotent upserts.
-- =============================================================================
CREATE TABLE stock_ohlcv (
    id          BIGSERIAL        PRIMARY KEY,
    symbol      VARCHAR(20)      NOT NULL,
    resolution  VARCHAR(10)      NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    open        NUMERIC(18, 4),
    high        NUMERIC(18, 4),
    low         NUMERIC(18, 4),
    close       NUMERIC(18, 4)   NOT NULL,
    volume      BIGINT,
    data_as_of  TIMESTAMPTZ      NOT NULL,
    ingested_at TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, resolution, data_as_of)
);

-- Indexes for time-series lookups
CREATE INDEX idx_stock_ohlcv_symbol_date ON stock_ohlcv (symbol, data_as_of DESC);
CREATE INDEX idx_stock_ohlcv_resolution ON stock_ohlcv (resolution);

-- =============================================================================
-- stock_fundamentals — Fundamental ratios for Vietnamese stocks (DATA-02)
--
-- Ingested via vnstock VCI source (TCBS source is broken as of 2025 — use VCI only).
-- period_type CHECK enforces 'year' or 'quarter' only.
-- UNIQUE(symbol, period_type, data_as_of) enables idempotent upserts.
-- =============================================================================
CREATE TABLE stock_fundamentals (
    id              BIGSERIAL        PRIMARY KEY,
    symbol          VARCHAR(20)      NOT NULL,
    period_type     VARCHAR(10)      NOT NULL CHECK (period_type IN ('year', 'quarter')),
    pe_ratio        NUMERIC(12, 4),
    pb_ratio        NUMERIC(12, 4),
    eps             NUMERIC(12, 4),
    market_cap      NUMERIC(24, 2),
    roe             NUMERIC(10, 4),
    roa             NUMERIC(10, 4),
    revenue_growth  NUMERIC(10, 4),
    net_margin      NUMERIC(10, 4),
    data_as_of      TIMESTAMPTZ      NOT NULL,
    ingested_at     TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, period_type, data_as_of)
);

-- Indexes for time-series lookups
CREATE INDEX idx_stock_fundamentals_symbol_date ON stock_fundamentals (symbol, data_as_of DESC);
CREATE INDEX idx_stock_fundamentals_period_type ON stock_fundamentals (period_type);
