-- =============================================================================
-- V3__gold_data.sql — Gold Market Data Tables
-- Phase 2 | Plan 01 | Requirements: DATA-03, DATA-04, DATA-07
-- =============================================================================
--
-- CONVENTION: Every time-series table MUST include:
--   data_as_of  TIMESTAMPTZ NOT NULL  -- when the data was valid in the real world
--   ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when written to this database
-- This convention is enforced by requirement DATA-07.
--
-- Tables created:
--   - gold_price:       Daily gold spot price in USD (FRED GOLDAMGBD228NLBM) (DATA-03)
--   - gold_etf_ohlcv:   Weekly/monthly OHLCV bars for gold ETFs (GLD default) (DATA-03)
--   - gold_wgc_flows:   World Gold Council ETF flows and central bank data (DATA-04)
--

-- =============================================================================
-- gold_price — Daily gold spot price in USD (DATA-03)
--
-- Primary source: FRED series GOLDAMGBD228NLBM (London AM fix, USD/troy oz).
-- source column allows adding alternative price sources in the future.
-- UNIQUE(source, data_as_of) enables idempotent upserts.
-- =============================================================================
CREATE TABLE gold_price (
    id          BIGSERIAL        PRIMARY KEY,
    source      VARCHAR(50)      NOT NULL DEFAULT 'FRED_GOLDAMGBD228NLBM',
    price_usd   NUMERIC(12, 4)   NOT NULL,
    data_as_of  TIMESTAMPTZ      NOT NULL,
    ingested_at TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (source, data_as_of)
);

-- Index for time-series lookups
CREATE INDEX idx_gold_price_source_date ON gold_price (source, data_as_of DESC);

-- =============================================================================
-- gold_etf_ohlcv — OHLCV bars for gold ETFs (DATA-03)
--
-- Default ticker: GLD (SPDR Gold Shares) via yfinance.
-- resolution CHECK enforces 'weekly' or 'monthly' only.
-- UNIQUE(ticker, resolution, data_as_of) enables idempotent upserts.
-- =============================================================================
CREATE TABLE gold_etf_ohlcv (
    id          BIGSERIAL        PRIMARY KEY,
    ticker      VARCHAR(10)      NOT NULL DEFAULT 'GLD',
    resolution  VARCHAR(10)      NOT NULL CHECK (resolution IN ('weekly', 'monthly')),
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4)   NOT NULL,
    volume      BIGINT,
    data_as_of  TIMESTAMPTZ      NOT NULL,
    ingested_at TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, resolution, data_as_of)
);

-- Index for time-series lookups
CREATE INDEX idx_gold_etf_ohlcv_ticker_date ON gold_etf_ohlcv (ticker, data_as_of DESC);

-- =============================================================================
-- gold_wgc_flows — World Gold Council ETF flows and central bank data (DATA-04)
--
-- Source: World Gold Council (WGC) — manually scraped or downloaded CSV.
-- NOTE: WGC data has a publication lag (see source_lag_note column).
-- Nullable region and fund_name accommodate both ETF flow and central bank rows.
-- UNIQUE uses COALESCE to handle NULLs in the unique constraint.
-- =============================================================================
CREATE TABLE gold_wgc_flows (
    id                          BIGSERIAL        PRIMARY KEY,
    period_end                  DATE             NOT NULL,
    region                      VARCHAR(100),
    fund_name                   VARCHAR(255),
    holdings_tonnes             NUMERIC(12, 4),
    flows_usd_millions          NUMERIC(14, 4),
    central_bank_net_tonnes     NUMERIC(12, 4),
    source_lag_note             TEXT,
    data_as_of                  TIMESTAMPTZ      NOT NULL,
    ingested_at                 TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- Unique index using COALESCE to handle NULLs in uniqueness constraint
-- (PostgreSQL does not support expressions in UNIQUE constraint definition)
CREATE UNIQUE INDEX idx_gold_wgc_flows_unique
    ON gold_wgc_flows (period_end, COALESCE(region, ''), COALESCE(fund_name, ''));

-- Index for time-series lookups
CREATE INDEX idx_gold_wgc_flows_period_end ON gold_wgc_flows (period_end DESC);
CREATE INDEX idx_gold_wgc_flows_fund_name ON gold_wgc_flows (fund_name);
