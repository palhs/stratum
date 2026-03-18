-- V8__watchlist.sql
-- Per-user watchlist and admin-editable default seed list

CREATE TABLE user_watchlist (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL,
    symbol      VARCHAR(20) NOT NULL,
    asset_type  VARCHAR(20) NOT NULL
                    CHECK (asset_type IN ('equity', 'gold_etf')),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

CREATE INDEX idx_user_watchlist_user ON user_watchlist (user_id);

CREATE TABLE watchlist_defaults (
    symbol      VARCHAR(20) PRIMARY KEY,
    asset_type  VARCHAR(20) NOT NULL
                    CHECK (asset_type IN ('equity', 'gold_etf')),
    sort_order  INTEGER     NOT NULL DEFAULT 0
);

-- Seed defaults: GLD + 5 core VN30 tickers
INSERT INTO watchlist_defaults (symbol, asset_type, sort_order) VALUES
    ('GLD',  'gold_etf', 0),
    ('VNM',  'equity',   1),
    ('VHM',  'equity',   2),
    ('VCB',  'equity',   3),
    ('HPG',  'equity',   4),
    ('MSN',  'equity',   5);
