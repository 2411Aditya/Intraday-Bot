-- =============================================================================
-- 0005_atomic_trade_reservation.sql
-- Atomic Supabase-Backed Trade Slot Reservation Across Concurrent Workers
-- =============================================================================

CREATE TABLE IF NOT EXISTS trade_reservations (
    account_id   UUID NOT NULL,
    symbol       TEXT NOT NULL,
    trading_date DATE NOT NULL,
    reserved_by  TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, symbol, trading_date)
);

ALTER TABLE trade_reservations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'trade_reservations' AND policyname = 'tr_service_role'
    ) THEN
        CREATE POLICY tr_service_role ON trade_reservations
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END
$$;

GRANT ALL ON TABLE trade_reservations TO service_role;

CREATE OR REPLACE FUNCTION public.reserve_trade_slot(
    p_account_id   UUID,
    p_symbol       TEXT,
    p_trading_date DATE,
    p_worker_id    TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO trade_reservations (account_id, symbol, trading_date, reserved_by)
    VALUES (p_account_id, p_symbol, p_trading_date, p_worker_id)
    ON CONFLICT (account_id, symbol, trading_date) DO NOTHING;

    RETURN FOUND;
END;
$$;

REVOKE ALL ON FUNCTION public.reserve_trade_slot FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.reserve_trade_slot TO service_role;

