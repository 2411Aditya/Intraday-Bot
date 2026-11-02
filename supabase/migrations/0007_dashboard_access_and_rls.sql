-- =============================================================================
-- 0007_dashboard_access_and_rls.sql
-- Intraday Bot - Secure Private Dashboard RLS Hardening (Authenticated Only)
-- =============================================================================

-- 1. Enable RLS and add SELECT policy on account_snapshots for authenticated owner
ALTER TABLE IF EXISTS account_snapshots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS as_select ON account_snapshots;
    CREATE POLICY as_select ON account_snapshots
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (
                SELECT id FROM trading_accounts WHERE user_id = auth.uid()
            )
        );
END
$$;

-- 2. Restrict research_snapshots to AUTHENTICATED operators only (no anonymous access)
ALTER TABLE IF EXISTS research_snapshots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS rs_select ON research_snapshots;
    CREATE POLICY rs_select ON research_snapshots
        FOR SELECT
        TO authenticated
        USING (true);
END
$$;

-- 3. Restrict worker_candle_state to AUTHENTICATED operators only (no anonymous access)
DO $$
BEGIN
    DROP POLICY IF EXISTS wcs_select ON worker_candle_state;
    CREATE POLICY wcs_select ON worker_candle_state
        FOR SELECT
        TO authenticated
        USING (true);
END
$$;

-- 4. Authorized Bot Operators table:
-- Allows an authenticated Supabase user to securely view designated bot accounts.
-- Write access is restricted to service_role / direct administrative grants.
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
    DROP POLICY IF EXISTS bo_select ON bot_operators;
    CREATE POLICY bo_select ON bot_operators
        FOR SELECT
        TO authenticated
        USING (user_id = auth.uid());
END
$$;

-- 5. Add operator access policies across private trading tables (AUTHENTICATED ONLY)
DO $$
BEGIN
    -- trading_accounts
    DROP POLICY IF EXISTS ta_operator_select ON trading_accounts;
    CREATE POLICY ta_operator_select ON trading_accounts
        FOR SELECT
        TO authenticated
        USING (
            id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- positions
    DROP POLICY IF EXISTS pos_operator_select ON positions;
    CREATE POLICY pos_operator_select ON positions
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- orders
    DROP POLICY IF EXISTS o_operator_select ON orders;
    CREATE POLICY o_operator_select ON orders
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- order_fills
    DROP POLICY IF EXISTS of_operator_select ON order_fills;
    CREATE POLICY of_operator_select ON order_fills
        FOR SELECT
        TO authenticated
        USING (
            order_id IN (
                SELECT o.id FROM orders o
                WHERE o.account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
            )
        );

    -- strategy_signals
    DROP POLICY IF EXISTS ss_operator_select ON strategy_signals;
    CREATE POLICY ss_operator_select ON strategy_signals
        FOR SELECT
        TO authenticated
        USING (
            user_id IN (
                SELECT ta.user_id FROM trading_accounts ta
                JOIN bot_operators bo ON bo.target_account_id = ta.id
                WHERE bo.user_id = auth.uid()
            )
        );

    -- risk_decisions
    DROP POLICY IF EXISTS rd_operator_select ON risk_decisions;
    CREATE POLICY rd_operator_select ON risk_decisions
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- order_intents
    DROP POLICY IF EXISTS oi_operator_select ON order_intents;
    CREATE POLICY oi_operator_select ON order_intents
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- account_snapshots
    DROP POLICY IF EXISTS as_operator_select ON account_snapshots;
    CREATE POLICY as_operator_select ON account_snapshots
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid())
        );

    -- audit_logs
    DROP POLICY IF EXISTS al_operator_select ON audit_logs;
    CREATE POLICY al_operator_select ON audit_logs
        FOR SELECT
        TO authenticated
        USING (
            user_id IN (
                SELECT ta.user_id FROM trading_accounts ta
                JOIN bot_operators bo ON bo.target_account_id = ta.id
                WHERE bo.user_id = auth.uid()
            )
        );

    -- processed_candles
    DROP POLICY IF EXISTS pc_select ON processed_candles;
    CREATE POLICY pc_select ON processed_candles
        FOR SELECT
        TO authenticated
        USING (
            account_id IN (
                SELECT id FROM trading_accounts WHERE user_id = auth.uid()
            )
            OR account_id IN (
                SELECT target_account_id FROM bot_operators WHERE user_id = auth.uid()
            )
        );
END
$$;
