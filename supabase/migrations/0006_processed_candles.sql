-- =============================================================================
-- 0006_processed_candles.sql
-- Durable Cross-Process Candle Idempotency for Paper & Live Worker
-- =============================================================================

CREATE TABLE IF NOT EXISTS processed_candles (
    id              UUID            DEFAULT gen_random_uuid() PRIMARY KEY,
    account_id      UUID            NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
    symbol          TEXT            NOT NULL,
    strategy_id     TEXT            NOT NULL,          -- e.g. 'VWAP_ORB'
    candle_ts       TIMESTAMPTZ     NOT NULL,           -- completed candle timestamp (IST-aware)
    recorded_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_processed_candle
        UNIQUE (account_id, symbol, strategy_id, candle_ts)
);

CREATE INDEX IF NOT EXISTS idx_processed_candles_lookup
    ON processed_candles (account_id, symbol, strategy_id, candle_ts);

ALTER TABLE processed_candles ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'processed_candles' AND policyname = 'pc_service_role'
    ) THEN
        CREATE POLICY pc_service_role ON processed_candles
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END
$$;

GRANT ALL ON TABLE processed_candles TO service_role;

