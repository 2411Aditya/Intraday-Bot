-- =============================================================================
-- phase_c_validation.sql
-- Intraday Bot – Phase C schema validation
--
-- HOW TO RUN
-- ----------
-- Paste into the SQL Editor of a DISPOSABLE test Supabase project that already
-- has 0001 and 0002 applied.  The SQL Editor runs as the postgres superuser,
-- so RLS is bypassed for all DML here – runtime RLS behaviour (auth.uid())
-- requires a real JWT and must be tested via the Supabase JS/REST client.
--
-- This script uses only top-level SQL + DO blocks.  No nested PROCEDURE
-- declarations are used (those are not valid inside DO).
-- All test data is rolled back at the end.
-- NOTICE messages report PASS; RAISE EXCEPTION aborts on unexpected failures.
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1 – CATALOG CHECKS
-- Verify schema objects exist exactly as defined in 0001/0002.
-- =============================================================================

DO $$
DECLARE v_n INTEGER;
BEGIN
    -- T01: all 9 tables present
    SELECT count(*) INTO v_n
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename IN (
        'trading_accounts','account_snapshots','strategy_signals',
        'risk_decisions','order_intents','orders',
        'order_fills','positions','audit_logs');
    IF v_n <> 9 THEN
        RAISE EXCEPTION 'T01 FAIL: expected 9 tables, found %', v_n;
    END IF;
    RAISE NOTICE 'T01 PASS: all 9 tables exist';

    -- T02: trading_accounts required columns (8)
    SELECT count(*) INTO v_n
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'trading_accounts'
      AND column_name  IN (
        'id','user_id','mode','cash_balance',
        'reserved_margin','deployed_margin','created_at','updated_at');
    IF v_n <> 8 THEN
        RAISE EXCEPTION 'T02 FAIL: trading_accounts missing columns, found %', v_n;
    END IF;
    RAISE NOTICE 'T02 PASS: trading_accounts has all 8 required columns';

    -- T03: UNIQUE (id, mode) constraint on trading_accounts
    SELECT count(*) INTO v_n
    FROM pg_constraint
    WHERE conrelid = 'public.trading_accounts'::regclass
      AND contype  = 'u'
      AND conname  = 'uq_trading_accounts_id_mode';
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T03 FAIL: uq_trading_accounts_id_mode not found';
    END IF;
    RAISE NOTICE 'T03 PASS: UNIQUE (id, mode) constraint exists on trading_accounts';

    -- T04: composite FK fk_intent_account_mode on order_intents
    SELECT count(*) INTO v_n
    FROM pg_constraint
    WHERE conrelid = 'public.order_intents'::regclass
      AND conname  = 'fk_intent_account_mode'
      AND contype  = 'f';
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T04 FAIL: fk_intent_account_mode missing on order_intents';
    END IF;
    RAISE NOTICE 'T04 PASS: composite FK fk_intent_account_mode exists on order_intents';

    -- T05: composite FK fk_order_account_mode on orders
    SELECT count(*) INTO v_n
    FROM pg_constraint
    WHERE conrelid = 'public.orders'::regclass
      AND conname  = 'fk_order_account_mode'
      AND contype  = 'f';
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T05 FAIL: fk_order_account_mode missing on orders';
    END IF;
    RAISE NOTICE 'T05 PASS: composite FK fk_order_account_mode exists on orders';

    -- T06: unique index on order_fills (order_id, fill_execution_id)
    SELECT count(*) INTO v_n
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename  = 'order_fills'
      AND indexname  = 'uq_fill_order_execution';
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T06 FAIL: uq_fill_order_execution index missing';
    END IF;
    RAISE NOTICE 'T06 PASS: unique index uq_fill_order_execution exists on order_fills';

    -- T07: RLS enabled on all 7 financial tables
    SELECT count(*) INTO v_n
    FROM pg_class
    WHERE relnamespace = 'public'::regnamespace
      AND relname IN (
        'trading_accounts','order_intents','orders',
        'order_fills','positions','risk_decisions','audit_logs')
      AND relrowsecurity = true;
    IF v_n <> 7 THEN
        RAISE EXCEPTION 'T07 FAIL: RLS not enabled on all 7 tables, only %', v_n;
    END IF;
    RAISE NOTICE 'T07 PASS: RLS enabled on all 7 financial tables';

    -- T08: no UPDATE or DELETE policy on audit_logs (immutability)
    SELECT count(*) INTO v_n
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'audit_logs'
      AND cmd IN ('UPDATE','DELETE');
    IF v_n <> 0 THEN
        RAISE EXCEPTION 'T08 FAIL: audit_logs has UPDATE/DELETE policies (count=%)', v_n;
    END IF;
    RAISE NOTICE 'T08 PASS: audit_logs has no UPDATE/DELETE policy';

    -- T09: pg_execute_trade_cycle is SECURITY DEFINER
    SELECT count(*) INTO v_n
    FROM pg_proc
    WHERE pronamespace = 'public'::regnamespace
      AND proname      = 'pg_execute_trade_cycle'
      AND prosecdef    = true;
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T09 FAIL: pg_execute_trade_cycle is not SECURITY DEFINER or missing';
    END IF;
    RAISE NOTICE 'T09 PASS: pg_execute_trade_cycle is SECURITY DEFINER';

    -- T10: PUBLIC does not have execute on pg_execute_trade_cycle
    --      proacl NULL means no explicit grants beyond owner (PUBLIC revoked).
    --      Otherwise check that '=X/' (public execute) is absent.
    SELECT count(*) INTO v_n
    FROM pg_proc
    WHERE pronamespace = 'public'::regnamespace
      AND proname      = 'pg_execute_trade_cycle'
      AND (
          proacl IS NULL
          OR NOT (array_to_string(proacl::text[], ',') LIKE '%=X/%')
      );
    IF v_n <> 1 THEN
        RAISE EXCEPTION 'T10 FAIL: PUBLIC may still have execute on pg_execute_trade_cycle';
    END IF;
    RAISE NOTICE 'T10 PASS: PUBLIC execute revoked from pg_execute_trade_cycle';

    -- T11: helper functions exist and are SECURITY DEFINER
    SELECT count(*) INTO v_n
    FROM pg_proc
    WHERE pronamespace = 'public'::regnamespace
      AND proname IN ('_validate_trade_chain','_update_position','_update_account_balances')
      AND prosecdef = true;
    IF v_n <> 3 THEN
        RAISE EXCEPTION 'T11 FAIL: expected 3 SECURITY DEFINER helpers, found %', v_n;
    END IF;
    RAISE NOTICE 'T11 PASS: all 3 helper functions exist and are SECURITY DEFINER';

END;
$$;

-- =============================================================================
-- SECTION 2 – DATA INTEGRITY CHECKS
-- All inserts follow the real FK chain:
--   trading_accounts → strategy_signals → risk_decisions
--   → order_intents → orders → order_fills
-- =============================================================================

DO $$
DECLARE
    v_acct_id   uuid := 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_user_id   uuid := 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_signal_id uuid := 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_risk_id   uuid := 'd0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_intent_id uuid := 'e0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_order_id  uuid := 'f0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_exec_id_1 uuid := '10eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_exec_id_2 uuid := '20eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
    v_fill_id   uuid;
    v_qty       integer;
    v_status    text;
    v_pnl       numeric;
BEGIN
    -- Seed the FK chain (paper account)
    INSERT INTO trading_accounts
        (id, user_id, mode, cash_balance, reserved_margin, deployed_margin)
    VALUES
        (v_acct_id, v_user_id, 'paper', 100000, 0, 0);

    INSERT INTO strategy_signals (id, user_id, symbol, signal_time, direction, price)
    VALUES (v_signal_id, v_user_id, 'SBIN', now(), 'long', 800);

    INSERT INTO risk_decisions (id, signal_id, account_id, decision)
    VALUES (v_risk_id, v_signal_id, v_acct_id, 'approved');

    INSERT INTO order_intents (id, risk_id, account_id, mode, symbol, quantity, side)
    VALUES (v_intent_id, v_risk_id, v_acct_id, 'paper', 'SBIN', 10, 'buy');

    INSERT INTO orders (id, intent_id, account_id, mode, status)
    VALUES (v_order_id, v_intent_id, v_acct_id, 'paper', 'filled');

    RAISE NOTICE 'T12 PASS: full FK chain inserted without error';

    -- T13: Paper/live isolation – mismatched mode must be rejected
    BEGIN
        INSERT INTO order_intents (id, risk_id, account_id, mode, symbol, quantity, side)
        VALUES (uuid_generate_v4(), v_risk_id,
                v_acct_id,  -- paper account
                'live',     -- mismatched
                'SBIN', 5, 'buy');
        RAISE EXCEPTION 'T13 FAIL: mismatched mode accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'T13 PASS: mismatched mode correctly rejected by FK';
    END;

    -- T14: mode CHECK constraint – invalid value
    BEGIN
        INSERT INTO trading_accounts
            (id, user_id, mode, cash_balance, reserved_margin, deployed_margin)
        VALUES (uuid_generate_v4(), v_user_id, 'sandbox', 0, 0, 0);
        RAISE EXCEPTION 'T14 FAIL: invalid mode accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'T14 PASS: mode CHECK constraint rejected invalid value';
    END;

    -- T15: quantity CHECK constraint on order_intents
    BEGIN
        INSERT INTO order_intents (id, risk_id, account_id, mode, symbol, quantity, side)
        VALUES (uuid_generate_v4(), v_risk_id, v_acct_id, 'paper', 'SBIN', 0, 'buy');
        RAISE EXCEPTION 'T15 FAIL: zero quantity accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'T15 PASS: quantity > 0 CHECK rejected zero';
    END;

    -- T16: direction CHECK on positions
    BEGIN
        INSERT INTO positions
            (account_id, symbol, direction, quantity, avg_entry_price, status)
        VALUES (v_acct_id, 'SBIN', 'flat', 10, 800, 'open');
        RAISE EXCEPTION 'T16 FAIL: invalid direction accepted';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'T16 PASS: direction CHECK rejected invalid value';
    END;

    -- T17: First fill succeeds
    INSERT INTO order_fills (order_id, fill_execution_id, fill_price, fill_quantity, fees)
    VALUES (v_order_id, v_exec_id_1, 800.40, 10, 5.00);
    RAISE NOTICE 'T17 PASS: first fill inserted';

    -- T18: Duplicate (same order_id + fill_execution_id) must be rejected
    BEGIN
        INSERT INTO order_fills (order_id, fill_execution_id, fill_price, fill_quantity, fees)
        VALUES (v_order_id, v_exec_id_1, 801.00, 5, 2.50);
        RAISE EXCEPTION 'T18 FAIL: duplicate fill_execution_id accepted';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'T18 PASS: duplicate fill correctly rejected';
    END;

    -- T19: Different fill_execution_id on same order is allowed (partial fill)
    INSERT INTO order_fills (order_id, fill_execution_id, fill_price, fill_quantity, fees)
    VALUES (v_order_id, v_exec_id_2, 800.50, 5, 2.50);
    RAISE NOTICE 'T19 PASS: second fill with different execution ID accepted';

    -- T20: Position created by _update_position (buy)
    PERFORM _update_position(v_acct_id, 'SBIN', 'buy', 800.40, 10);
    SELECT quantity, status INTO v_qty, v_status
    FROM positions WHERE account_id = v_acct_id AND symbol = 'SBIN' AND status = 'open';
    IF v_qty <> 10 OR v_status <> 'open' THEN
        RAISE EXCEPTION 'T20 FAIL: position after buy – qty=%, status=%', v_qty, v_status;
    END IF;
    RAISE NOTICE 'T20 PASS: buy created open position qty=10';

    -- T21: Partial sell reduces position
    PERFORM _update_position(v_acct_id, 'SBIN', 'sell', 810.00, 4);
    SELECT quantity, status INTO v_qty, v_status
    FROM positions WHERE account_id = v_acct_id AND symbol = 'SBIN' AND status = 'open';
    IF v_qty <> 6 OR v_status <> 'open' THEN
        RAISE EXCEPTION 'T21 FAIL: after partial sell – qty=%, status=%', v_qty, v_status;
    END IF;
    RAISE NOTICE 'T21 PASS: partial sell left qty=6 open';

    -- T22: Full exit closes position, computes realised P&L
    PERFORM _update_position(v_acct_id, 'SBIN', 'sell', 820.00, 6);
    SELECT quantity, status, realized_pnl
    INTO v_qty, v_status, v_pnl
    FROM positions WHERE account_id = v_acct_id AND symbol = 'SBIN' AND status = 'closed';
    IF v_qty <> 0 OR v_status <> 'closed' THEN
        RAISE EXCEPTION 'T22 FAIL: after full exit – qty=%, status=%', v_qty, v_status;
    END IF;
    IF v_pnl IS NULL OR v_pnl = 0 THEN
        RAISE EXCEPTION 'T22 FAIL: realized_pnl is zero or null after full exit';
    END IF;
    RAISE NOTICE 'T22 PASS: full exit closed position, realized_pnl=%', v_pnl;

    -- T23: Over-sell rejected
    -- Open a fresh position first
    INSERT INTO positions
        (account_id, symbol, direction, quantity, avg_entry_price, status)
    VALUES (v_acct_id, 'RELIANCE', 'long', 5, 2500, 'open');

    BEGIN
        PERFORM _update_position(v_acct_id, 'RELIANCE', 'sell', 2550, 10);
        RAISE EXCEPTION 'T23 FAIL: over-sell was accepted';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE '%exceeds open position%' THEN
            RAISE NOTICE 'T23 PASS: over-sell correctly rejected';
        ELSE
            RAISE EXCEPTION 'T23 FAIL unexpected error: %', SQLERRM;
        END IF;
    END;

    -- T24: _update_account_balances raises exception (disabled guard)
    BEGIN
        PERFORM _update_account_balances(v_acct_id);
        RAISE EXCEPTION 'T24 FAIL: _update_account_balances should raise exception';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE '%not yet implemented%' THEN
            RAISE NOTICE 'T24 PASS: _update_account_balances correctly disabled';
        ELSE
            RAISE EXCEPTION 'T24 FAIL unexpected error: %', SQLERRM;
        END IF;
    END;

END;
$$;

-- Roll back all test data
ROLLBACK;

-- End of phase_c_validation.sql
