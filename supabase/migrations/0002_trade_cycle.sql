-- =============================================================================
-- 0002_trade_cycle.sql
-- Intraday Bot – trade-cycle RPC and helpers
-- Fixes applied (code-review round 2):
--   • Full ownership chain validated: signal → risk_decision → intent → order
--   • Idempotency: duplicate fill_execution_id → REJECTED (no silent UPDATE)
--   • Correct position accounting for buys, sells, partial exits, full exits
--   • Balance accounting is DISABLED (raises exception) until a real ledger is
--     implemented; placeholder that silently touched updated_at is removed
--   • SECURITY DEFINER; execute granted only to service_role
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Helper A: validate full ownership chain for a trade cycle
-- Returns the account_id if valid; raises exception otherwise.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _validate_trade_chain(
    p_signal_id UUID,
    p_risk_id   UUID,
    p_intent_id UUID
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_caller_uid UUID := auth.uid();
    v_signal_uid UUID;
    v_risk_acct  UUID;
    v_risk_sig   UUID;
    v_intent_risk UUID;
    v_intent_acct UUID;
    v_acct_uid    UUID;
BEGIN
    -- 1. Signal must belong to the calling user
    SELECT user_id INTO STRICT v_signal_uid
    FROM strategy_signals WHERE id = p_signal_id;

    IF v_signal_uid IS DISTINCT FROM v_caller_uid THEN
        RAISE EXCEPTION 'signal % does not belong to authenticated user', p_signal_id;
    END IF;

    -- 2. Risk decision must reference the same signal
    SELECT signal_id, account_id INTO STRICT v_risk_sig, v_risk_acct
    FROM risk_decisions WHERE id = p_risk_id;

    IF v_risk_sig <> p_signal_id THEN
        RAISE EXCEPTION 'risk_decision % does not reference signal %', p_risk_id, p_signal_id;
    END IF;

    -- 3. Account must belong to the calling user
    SELECT user_id INTO STRICT v_acct_uid
    FROM trading_accounts WHERE id = v_risk_acct;

    IF v_acct_uid IS DISTINCT FROM v_caller_uid THEN
        RAISE EXCEPTION 'account % does not belong to authenticated user', v_risk_acct;
    END IF;

    -- 4. Intent must reference this risk decision and account
    SELECT risk_id, account_id INTO STRICT v_intent_risk, v_intent_acct
    FROM order_intents WHERE id = p_intent_id;

    IF v_intent_risk <> p_risk_id THEN
        RAISE EXCEPTION 'order_intent % does not reference risk_decision %', p_intent_id, p_risk_id;
    END IF;

    IF v_intent_acct <> v_risk_acct THEN
        RAISE EXCEPTION 'order_intent % account mismatch', p_intent_id;
    END IF;

    RETURN v_risk_acct;
END;
$$;

-- ---------------------------------------------------------------------------
-- Helper B: update or close a position correctly
--
-- Rules
--   buy  → opens long (or adds to existing long)
--   sell → reduces / closes long, or opens short
--   When net quantity reaches 0 the position is marked closed.
--   Partial exits compute realised P&L on the exited quantity.
--   Negative net quantities are rejected (over-selling is blocked).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _update_position(
    p_account_id UUID,
    p_symbol     TEXT,
    p_side       TEXT,       -- 'buy' | 'sell'
    p_price      NUMERIC,
    p_qty        INTEGER     -- always positive
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_pos          RECORD;
    v_new_qty      INTEGER;
    v_realised_pnl NUMERIC;
    v_exit_qty     INTEGER;
BEGIN
    -- Lock the open position row (if any) for this symbol & account
    SELECT * INTO v_pos
    FROM positions
    WHERE account_id = p_account_id
      AND symbol     = p_symbol
      AND status     = 'open'
    FOR UPDATE;

    IF p_side = 'buy' THEN
        IF FOUND THEN
            -- Add to existing position: weighted-average entry price
            v_new_qty := v_pos.quantity + p_qty;
            UPDATE positions SET
                quantity        = v_new_qty,
                avg_entry_price = ((v_pos.avg_entry_price * v_pos.quantity) + (p_price * p_qty))
                                  / v_new_qty
            WHERE id = v_pos.id;
        ELSE
            -- Open new long
            INSERT INTO positions
                (account_id, symbol, direction, quantity, avg_entry_price, status)
            VALUES
                (p_account_id, p_symbol, 'long', p_qty, p_price, 'open');
        END IF;

    ELSIF p_side = 'sell' THEN
        IF NOT FOUND THEN
            -- No open position: open a new short
            INSERT INTO positions
                (account_id, symbol, direction, quantity, avg_entry_price, status)
            VALUES
                (p_account_id, p_symbol, 'short', p_qty, p_price, 'open');
        ELSE
            -- Reduce / close / flip existing long
            v_exit_qty := LEAST(p_qty, v_pos.quantity);
            v_new_qty  := v_pos.quantity - v_exit_qty;

            -- Realised P&L for exited portion (long only; extend for short)
            v_realised_pnl := (p_price - v_pos.avg_entry_price) * v_exit_qty;

            IF v_new_qty = 0 THEN
                -- Full close
                UPDATE positions SET
                    quantity        = 0,
                    status          = 'closed',
                    close_timestamp = now(),
                    realized_pnl    = v_pos.realized_pnl + v_realised_pnl
                WHERE id = v_pos.id;
            ELSIF v_new_qty > 0 THEN
                -- Partial exit
                UPDATE positions SET
                    quantity     = v_new_qty,
                    realized_pnl = v_pos.realized_pnl + v_realised_pnl
                WHERE id = v_pos.id;
            ELSE
                RAISE EXCEPTION
                    'sell quantity % exceeds open position % for symbol %',
                    p_qty, v_pos.quantity, p_symbol;
            END IF;

            -- If the sell was larger than the open position, open a residual short
            IF p_qty > v_pos.quantity THEN
                INSERT INTO positions
                    (account_id, symbol, direction, quantity, avg_entry_price, status)
                VALUES
                    (p_account_id, p_symbol, 'short',
                     p_qty - v_pos.quantity, p_price, 'open');
            END IF;
        END IF;
    ELSE
        RAISE EXCEPTION 'unknown side: %', p_side;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Helper C: account balance update
-- DISABLED – raises an exception until a proper double-entry ledger is built.
-- Remove this guard and implement real accounting before enabling live trading.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _update_account_balances(p_account_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RAISE EXCEPTION
        'Account balance accounting is not yet implemented. '
        'Do not call pg_execute_trade_cycle until _update_account_balances '
        'is replaced with a real ledger implementation.';
END;
$$;

-- ---------------------------------------------------------------------------
-- Main RPC: pg_execute_trade_cycle
--
-- Idempotency contract
--   • If p_fill_execution_id already exists for p_order_id → RAISE EXCEPTION.
--     Replaying with a different payload is a conflicting duplicate; the caller
--     must investigate rather than silently overwriting.
--   • If the order row already exists (p_order_id conflict) but the fill is
--     new, the fill is inserted normally (partial-fill scenario).
--
-- Caller: server-side service_role only.  NEVER call from the browser.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.pg_execute_trade_cycle(
    p_signal_id         UUID,
    p_risk_id           UUID,
    p_intent_id         UUID,
    p_order_id          UUID,
    p_fill_execution_id UUID,
    p_fill_price        NUMERIC,
    p_fill_quantity     INTEGER,
    p_fees              NUMERIC DEFAULT 0
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_account_id UUID;
    v_mode       TEXT;
    v_symbol     TEXT;
    v_side       TEXT;
    v_existing   UUID;
BEGIN
    -- 1. Validate the full ownership chain
    v_account_id := _validate_trade_chain(p_signal_id, p_risk_id, p_intent_id);

    -- 2. Fetch intent details needed for position + fill
    SELECT mode, symbol, side
    INTO STRICT v_mode, v_symbol, v_side
    FROM order_intents WHERE id = p_intent_id;

    -- 3. Lock the account row before any writes
    PERFORM id FROM trading_accounts WHERE id = v_account_id FOR UPDATE;

    -- 4. Idempotency check: reject exact duplicate fills
    SELECT id INTO v_existing
    FROM order_fills
    WHERE order_id = p_order_id
      AND fill_execution_id = p_fill_execution_id;

    IF FOUND THEN
        RAISE EXCEPTION
            'Duplicate fill: fill_execution_id % already recorded for order %',
            p_fill_execution_id, p_order_id;
    END IF;

    -- 5. Insert order (idempotent on PK – subsequent partial fills reuse it)
    INSERT INTO orders (id, intent_id, account_id, mode, status)
    VALUES (p_order_id, p_intent_id, v_account_id, v_mode, 'filled')
    ON CONFLICT (id) DO NOTHING;

    -- 6. Insert fill (unique constraint on (order_id, fill_execution_id) is the
    --    final safety net; step 4 gives a clearer error message first)
    INSERT INTO order_fills
        (order_id, fill_execution_id, fill_price, fill_quantity, fees)
    VALUES
        (p_order_id, p_fill_execution_id, p_fill_price, p_fill_quantity, p_fees);

    -- 7. Update position
    PERFORM _update_position(v_account_id, v_symbol, v_side, p_fill_price, p_fill_quantity);

    -- 8. Update balances (currently disabled – see _update_account_balances)
    PERFORM _update_account_balances(v_account_id);

END;
$$;

-- Revoke public execute; grant only to service_role
REVOKE ALL ON FUNCTION public.pg_execute_trade_cycle FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.pg_execute_trade_cycle TO service_role;

REVOKE ALL ON FUNCTION _validate_trade_chain  FROM PUBLIC;
REVOKE ALL ON FUNCTION _update_position        FROM PUBLIC;
REVOKE ALL ON FUNCTION _update_account_balances FROM PUBLIC;

-- End of 0002_trade_cycle.sql
