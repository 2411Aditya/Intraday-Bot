-- 0003_research_schema.sql
-- Creates the research_snapshots table for persisting market intelligence.
-- Safe to run multiple times (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS research_snapshots (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id         TEXT        NOT NULL UNIQUE,
    session_type        TEXT        NOT NULL,          -- 'overnight' | 'pre_market' | 'post_market'
    trading_date        DATE        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_json       JSONB       NOT NULL,
    market_outlook      TEXT        NOT NULL DEFAULT 'NEUTRAL',
    is_tradeable_session BOOLEAN    NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_research_snapshots_created_at
    ON research_snapshots (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_snapshots_trading_date
    ON research_snapshots (trading_date DESC);

COMMENT ON TABLE research_snapshots IS
    'Persisted market-intelligence snapshots produced by the research engine.';

