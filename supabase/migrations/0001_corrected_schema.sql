-- =============================================================================
-- 0001_corrected_schema.sql
-- Intraday Bot – corrected base schema
-- Fixes applied (code-review round 2):
--   • Added UNIQUE (id, mode) on trading_accounts so composite FK references work
--   • Rewrote every RLS policy with separate statements per command (SELECT /
--     INSERT / UPDATE / DELETE) – PostgreSQL does not allow combining WITH CHECK
--     and USING on the same FOR INSERT policy, and does not allow mixing commands
--     in a single CREATE POLICY statement
--   • Removed broken DO-block RLS guard (tables always exist by this point)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. Trading Accounts
--    UNIQUE (id, mode) is needed so composite foreign keys in later tables
--    can reference (trading_accounts.id, trading_accounts.mode).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trading_accounts (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        NOT NULL,        -- Supabase Auth UID
    mode            TEXT        NOT NULL CHECK (mode IN ('paper', 'live')),
    cash_balance    NUMERIC(20,4) NOT NULL DEFAULT 0,
    reserved_margin NUMERIC(20,4) NOT NULL DEFAULT 0,
    deployed_margin NUMERIC(20,4) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Enforce one account per user per mode
    CONSTRAINT uq_trading_accounts_user_mode UNIQUE (user_id, mode),

    -- Required for composite FK references: (id, mode) must be unique
    CONSTRAINT uq_trading_accounts_id_mode   UNIQUE (id, mode)
);

-- ---------------------------------------------------------------------------
-- 2. Account Snapshots (append-only historical record)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS account_snapshots (
    id                    UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id            UUID        NOT NULL
                              REFERENCES trading_accounts(id) ON DELETE RESTRICT,
    snapshot_ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    cash_balance          NUMERIC(20,4) NOT NULL,
    reserved_margin       NUMERIC(20,4) NOT NULL,
    deployed_margin       NUMERIC(20,4) NOT NULL,
    position_market_value NUMERIC(20,4) NOT NULL,
    total_equity          NUMERIC(20,4) NOT NULL,   -- cash + deployed + reserved + unrealised
    realized_pnl          NUMERIC(20,4) NOT NULL,
    unrealized_pnl        NUMERIC(20,4) NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. Strategy Signals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_signals (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL,
    symbol      TEXT        NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    direction   TEXT        NOT NULL CHECK (direction IN ('long', 'short')),
    price       NUMERIC(20,4) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_signals_user_time ON strategy_signals (user_id, signal_time);

-- ---------------------------------------------------------------------------
-- 4. Risk Decisions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_decisions (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_id  UUID        NOT NULL
                   REFERENCES strategy_signals(id) ON DELETE RESTRICT,
    account_id UUID        NOT NULL
                   REFERENCES trading_accounts(id) ON DELETE RESTRICT,
    decision   TEXT        NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_account ON risk_decisions (account_id);

-- ---------------------------------------------------------------------------
-- 5. Order Intents
--    Composite FK (account_id, mode) → trading_accounts(id, mode) enforces
--    that every intent is locked to the correct mode for its account.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_intents (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    risk_id     UUID        NOT NULL
                    REFERENCES risk_decisions(id) ON DELETE RESTRICT,
    account_id  UUID        NOT NULL,
    mode        TEXT        NOT NULL CHECK (mode IN ('paper', 'live')),
    symbol      TEXT        NOT NULL,
    quantity    INTEGER     NOT NULL CHECK (quantity > 0),
    side        TEXT        NOT NULL CHECK (side IN ('buy', 'sell')),
    limit_price NUMERIC(20,4),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_intent_account_mode
        FOREIGN KEY (account_id, mode)
        REFERENCES trading_accounts (id, mode)
        ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------------
-- 6. Orders
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_id  UUID        NOT NULL
                   REFERENCES order_intents(id) ON DELETE RESTRICT,
    account_id UUID        NOT NULL,
    mode       TEXT        NOT NULL CHECK (mode IN ('paper', 'live')),
    status     TEXT        NOT NULL
                   CHECK (status IN ('pending', 'filled', 'partial', 'canceled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_order_account_mode
        FOREIGN KEY (account_id, mode)
        REFERENCES trading_accounts (id, mode)
        ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------------
-- 7. Order Fills
--    fill_execution_id is the stable external reference (broker exec ID or
--    deterministic paper-fill UUID).  The unique index prevents duplicate
--    fill records for the same execution event.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_fills (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id          UUID        NOT NULL
                          REFERENCES orders(id) ON DELETE RESTRICT,
    fill_execution_id UUID        NOT NULL,
    fill_price        NUMERIC(20,4) NOT NULL,
    fill_quantity     INTEGER     NOT NULL CHECK (fill_quantity > 0),
    fill_timestamp    TIMESTAMPTZ NOT NULL DEFAULT now(),
    fees              NUMERIC(20,4) NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fill_order_execution
    ON order_fills (order_id, fill_execution_id);

-- ---------------------------------------------------------------------------
-- 8. Positions
--    quantity is allowed to reach 0 only when the position is closed.
--    Enforced in the RPC; the CHECK only blocks negative values.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID        NOT NULL
                        REFERENCES trading_accounts(id) ON DELETE RESTRICT,
    symbol          TEXT        NOT NULL,
    direction       TEXT        NOT NULL CHECK (direction IN ('long', 'short')),
    quantity        INTEGER     NOT NULL CHECK (quantity >= 0),
    avg_entry_price NUMERIC(20,4) NOT NULL,
    open_timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
    close_timestamp TIMESTAMPTZ,
    realized_pnl    NUMERIC(20,4) NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL CHECK (status IN ('open', 'closed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_positions_account ON positions (account_id);

-- ---------------------------------------------------------------------------
-- 9. Audit Logs (write-once; no UPDATE/DELETE policies are created)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL,
    action     TEXT        NOT NULL,
    table_name TEXT        NOT NULL,
    record_id  UUID        NOT NULL,
    details    JSONB,
    logged_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Row-Level Security
-- Each command gets its own policy so WITH CHECK / USING semantics are correct.
-- Write operations are restricted to service_role; read is user-scoped.
-- =============================================================================

-- ── trading_accounts ──────────────────────────────────────────────────────────
ALTER TABLE trading_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY ta_select ON trading_accounts
    FOR SELECT
    USING (user_id = auth.uid());

-- Regular users may never INSERT/UPDATE/DELETE directly.
-- (No INSERT / UPDATE / DELETE policy is created for the authenticated role.)
-- service_role bypasses RLS entirely – no explicit policy needed.

-- ── strategy_signals ──────────────────────────────────────────────────────────
ALTER TABLE strategy_signals ENABLE ROW LEVEL SECURITY;

CREATE POLICY ss_select ON strategy_signals
    FOR SELECT
    USING (user_id = auth.uid());

-- ── risk_decisions ────────────────────────────────────────────────────────────
ALTER TABLE risk_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY rd_select ON risk_decisions
    FOR SELECT
    USING (
        account_id IN (
            SELECT id FROM trading_accounts WHERE user_id = auth.uid()
        )
    );

-- ── order_intents ─────────────────────────────────────────────────────────────
ALTER TABLE order_intents ENABLE ROW LEVEL SECURITY;

CREATE POLICY oi_select ON order_intents
    FOR SELECT
    USING (
        account_id IN (
            SELECT id FROM trading_accounts WHERE user_id = auth.uid()
        )
    );

-- ── orders ────────────────────────────────────────────────────────────────────
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY o_select ON orders
    FOR SELECT
    USING (
        account_id IN (
            SELECT id FROM trading_accounts WHERE user_id = auth.uid()
        )
    );

-- ── order_fills ───────────────────────────────────────────────────────────────
ALTER TABLE order_fills ENABLE ROW LEVEL SECURITY;

CREATE POLICY of_select ON order_fills
    FOR SELECT
    USING (
        order_id IN (
            SELECT o.id FROM orders o
            WHERE o.account_id IN (
                SELECT id FROM trading_accounts WHERE user_id = auth.uid()
            )
        )
    );

-- ── positions ─────────────────────────────────────────────────────────────────
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY pos_select ON positions
    FOR SELECT
    USING (
        account_id IN (
            SELECT id FROM trading_accounts WHERE user_id = auth.uid()
        )
    );

-- ── audit_logs ────────────────────────────────────────────────────────────────
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY al_select ON audit_logs
    FOR SELECT
    USING (user_id = auth.uid());

-- No INSERT / UPDATE / DELETE policy for authenticated users.
-- service_role (used by all server-side writes) bypasses RLS.

-- =============================================================================
-- Trigger: auto-update updated_at on trading_accounts
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_trading_accounts_updated
BEFORE UPDATE ON trading_accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- End of 0001_corrected_schema.sql
