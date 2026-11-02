-- =============================================================================
-- 0007_dashboard_access_and_rls.sql
-- Intraday Bot - Secure Dashboard Read Access and RLS Hardening
-- =============================================================================

-- 1. Enable RLS and add SELECT policy on account_snapshots
ALTER TABLE IF EXISTS account_snapshots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'account_snapshots' AND policyname = 'as_select'
    ) THEN
        CREATE POLICY as_select ON account_snapshots
            FOR SELECT
            USING (
                account_id IN (
                    SELECT id FROM trading_accounts WHERE user_id = auth.uid()
                )
            );
    END IF;
END
$$;

-- 2. Enable RLS and add public/authenticated read on research_snapshots (macro intelligence)
ALTER TABLE IF EXISTS research_snapshots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'research_snapshots' AND policyname = 'rs_select'
    ) THEN
        CREATE POLICY rs_select ON research_snapshots
            FOR SELECT
            TO authenticated, anon
            USING (true);
    END IF;
END
$$;

-- 3. Allow authenticated and anon users to read worker candle heartbeat state
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'worker_candle_state' AND policyname = 'wcs_select'
    ) THEN
        CREATE POLICY wcs_select ON worker_candle_state
            FOR SELECT
            TO authenticated, anon
            USING (true);
    END IF;
END
$$;

-- 4. Authorized Bot Operators table:
-- Allows an authenticated Supabase user to securely view their designated bot accounts.
CREATE TABLE IF NOT EXISTS bot_operators (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID        NOT NULL,
    target_account_id  UUID        NOT NULL REFERENCES trading_accounts(id) ON DELETE CASCADE,
    role               TEXT        NOT NULL DEFAULT 'viewer',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_bot_operators_user_account UNIQUE (user_id, target_account_id)
);

ALTER TABLE bot_operators ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'bot_operators' AND policyname = 'bo_select'
    ) THEN
        CREATE POLICY bo_select ON bot_operators
            FOR SELECT
            USING (user_id = auth.uid());
    END IF;
END
$$;

-- 5. Add operator access policies across trading tables so authorized operators can view their bot's records
DO $$
BEGIN
    -- trading_accounts
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'trading_accounts' AND policyname = 'ta_operator_select'
    ) THEN
        CREATE POLICY ta_operator_select ON trading_accounts
            FOR SELECT
            USING (
                id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- positions
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'positions' AND policyname = 'pos_operator_select'
    ) THEN
        CREATE POLICY pos_operator_select ON positions
            FOR SELECT
            USING (
                account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- orders
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'orders' AND policyname = 'o_operator_select'
    ) THEN
        CREATE POLICY o_operator_select ON orders
            FOR SELECT
            USING (
                account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- order_fills
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'order_fills' AND policyname = 'of_operator_select'
    ) THEN
        CREATE POLICY of_operator_select ON order_fills
            FOR SELECT
            USING (
                order_id IN (
                    SELECT o.id FROM orders o
                    WHERE o.account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
                )
            );
    END IF;

    -- strategy_signals
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'strategy_signals' AND policyname = 'ss_operator_select'
    ) THEN
        CREATE POLICY ss_operator_select ON strategy_signals
            FOR SELECT
            USING (
                user_id IN (
                    SELECT ta.user_id FROM trading_accounts ta
                    JOIN bot_operators bo ON bo.target_account_id = ta.id
                    WHERE bo.user_id = auth.uid()
                )
            );
    END IF;

    -- risk_decisions
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'risk_decisions' AND policyname = 'rd_operator_select'
    ) THEN
        CREATE POLICY rd_operator_select ON risk_decisions
            FOR SELECT
            USING (
                account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- order_intents
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'order_intents' AND policyname = 'oi_operator_select'
    ) THEN
        CREATE POLICY oi_operator_select ON order_intents
            FOR SELECT
            USING (
                account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- account_snapshots
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'account_snapshots' AND policyname = 'as_operator_select'
    ) THEN
        CREATE POLICY as_operator_select ON account_snapshots
            FOR SELECT
            USING (
                account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            );
    END IF;

    -- audit_logs
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'audit_logs' AND policyname = 'al_operator_select'
    ) THEN
        CREATE POLICY al_operator_select ON audit_logs
            FOR SELECT
            USING (
                user_id IN (
                    SELECT ta.user_id FROM trading_accounts ta
                    JOIN bot_operators bo ON bo.target_account_id = ta.id
                    WHERE bo.user_id = auth.uid()
                )
            );
    END IF;

    -- processed_candles
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'processed_candles' AND policyname = 'pc_select'
    ) THEN
        CREATE POLICY pc_select ON processed_candles
            FOR SELECT
            USING (
                account_id IN (
                    SELECT id FROM trading_accounts WHERE user_id = auth.uid()
                )
                OR account_id IN (
                    SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid()
                )
            );
    END IF;
END
$$;
