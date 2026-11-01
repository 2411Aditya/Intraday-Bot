-- =============================================================================
-- 0004_worker_state.sql
-- Intraday Bot - Persistent Worker & Candle Processing State
-- =============================================================================

CREATE TABLE IF NOT EXISTS worker_candle_state (
    symbol                   TEXT        NOT NULL,
    trading_date             DATE        NOT NULL,
    last_processed_candle_ts TIMESTAMPTZ NOT NULL,
    last_evaluated_signal_id UUID,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trading_date)
);

ALTER TABLE worker_candle_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY wcs_service_role ON worker_candle_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT ALL ON TABLE worker_candle_state TO service_role;

