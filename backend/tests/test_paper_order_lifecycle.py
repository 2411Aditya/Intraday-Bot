"""Complete Paper-Order Lifecycle Verification.

Validates the full production pipeline using deterministic mocked market data
and a valid NORMAL (NEUTRAL/tradeable) research snapshot:
  1. Signal generation (VWAP + 15-min ORB + 20 EMA + 1.5x volume breakout)
  2. Risk approval (0.5% risk budget, 1 position max, cost drag check)
  3. Paper entry (PaperExecutionAdapter with 0.05% adverse slippage and fee deduction)
  4. Supabase persistence (persist_trade_cycle, orders, fills, positions, cash_balance)
  5. Paper exit (target hit, exit slippage, exit fee deduction)
  6. Fees and P&L reconciliation (zero discrepancy between paper ledger and Supabase)
  7. Worker restart & idempotency (state restore, duplicate trade rejection via DB)

Uses the real production code path with NO mock shortcuts on the business logic.
Never bypasses risk checks or calls live order APIs.
"""

from __future__ import annotations

import datetime
import os
import unittest
from unittest.mock import patch
import uuid
import zoneinfo
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from backend.app.core.config import TradingMode
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.market_data.mock_provider import MockMarketDataProvider
from backend.app.models.domain import (
    Candle,
    MarketTick,
    PositionStatus,
    SignalDirection,
)
from backend.app.persistence.supabase_trader import (
    ensure_trading_account,
    get_account_ledger,
    get_db_connection,
    is_symbol_traded_today,
    persist_trade_cycle,
    reserve_trade_slot,
)
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.risk.engine import RiskEngine
from backend.app.strategies.vwap_orb_strategy import VWAP_ORB_Strategy
from backend.app.worker import IntradayWorker
from research.models import ResearchSnapshot
from research.persistence import save_snapshot

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class TestPaperOrderLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conn = get_db_connection()
        cls.test_user_id = str(uuid.uuid4())
        # Ensure fresh unique paper account for this test run with exactly 100,000 capital
        cls.account_id = ensure_trading_account(
            cls.conn,
            cls.test_user_id,
            mode="paper",
            starting_capital=100_000.0,
        )

    @classmethod
    def tearDownClass(cls):
        if cls.conn:
            try:
                with cls.conn.cursor() as cur:
                    cur.execute("DELETE FROM order_fills WHERE order_id IN (SELECT id FROM orders WHERE account_id = %s);", (cls.account_id,))
                    cur.execute("DELETE FROM orders WHERE account_id = %s;", (cls.account_id,))
                    cur.execute("DELETE FROM order_intents WHERE account_id = %s;", (cls.account_id,))
                    cur.execute("DELETE FROM positions WHERE account_id = %s;", (cls.account_id,))
                    cur.execute("DELETE FROM trade_reservations WHERE account_id = %s;", (cls.account_id,))
                    cur.execute("DELETE FROM risk_decisions WHERE account_id = %s;", (cls.account_id,))
                    cur.execute("DELETE FROM trading_accounts WHERE id = %s;", (cls.account_id,))
                cls.conn.commit()
            except Exception:
                pass
            finally:
                cls.conn.close()

    def test_complete_paper_order_lifecycle(self):
        # -------------------------------------------------------------
        # STEP 0: Create and save a valid NORMAL research snapshot
        # -------------------------------------------------------------
        active_date = datetime.date(2026, 10, 30)
        symbol = "TATASTEEL"
        snap = ResearchSnapshot(
            snapshot_id=f"RS-LIFECYCLE-{uuid.uuid4().hex[:6].upper()}",
            session_type="pre_market",
            trading_date=str(active_date),
            market_outlook="NEUTRAL",
            is_tradeable_session=True,
            allowed_symbols=[symbol, "SBIN", "RELIANCE"],
            watchlist=[{"symbol": symbol, "score": 1.5, "change_pct_1d": 1.5}],
        )

        # -------------------------------------------------------------
        # STEP 1: Signal Generation (VWAP + ORB Breakout on deterministic candles)
        # -------------------------------------------------------------
        candles = MockMarketDataProvider.generate_synthetic_session(
            symbol=symbol,
            base_price=150.0,
            pattern="BULLISH_BREAKOUT",
            date=datetime.datetime(2026, 10, 30, tzinfo=IST),
        )
        self.assertEqual(len(candles), 14, "Must have 14 deterministic 5-minute candles")

        signal = VWAP_ORB_Strategy.evaluate(candles)
        self.assertIsNotNone(signal, "Strategy must generate a valid signal on genuine breakout")
        self.assertEqual(signal.direction, SignalDirection.BUY)
        self.assertEqual(signal.symbol, symbol)
        self.assertEqual(signal.entry_price, candles[-1].close)
        self.assertTrue(signal.stop_loss < signal.entry_price)
        self.assertTrue(signal.target_price > signal.entry_price)
        self.assertAlmostEqual(
            (signal.target_price - signal.entry_price) / (signal.entry_price - signal.stop_loss),
            2.0,
            places=1,
            msg="Target must enforce 2R risk-to-reward ratio",
        )

        # -------------------------------------------------------------
        # STEP 2: Risk Approval (RiskEngine evaluates budget & guardrails)
        # -------------------------------------------------------------
        risk_engine = RiskEngine(
            risk_per_trade_pct=0.5,
            max_daily_loss_pct=1.0,
            max_trades_per_day=2,
            max_concurrent_positions=1,
        )
        paper_adapter = PaperExecutionAdapter(
            starting_capital=100_000.0,
            max_daily_loss_pct=1.0,
            slippage_rate=0.0005,
        )
        quote = MarketTick(
            symbol=symbol,
            ltp=signal.entry_price,
            bid=signal.entry_price - 0.05,
            ask=signal.entry_price + 0.05,
            volume=candles[-1].volume,
        )

        decision = risk_engine.evaluate_signal(
            signal=signal,
            account=paper_adapter.get_account_state(),
            quote=quote,
            open_positions=[],
            is_market_data_healthy=True,
            mode=TradingMode.PAPER,
            current_execution_time=signal.timestamp,
        )
        self.assertTrue(decision.approved, f"Risk must approve valid intent: {decision.rejection_reason}")
        self.assertIsNotNone(decision.order_intent)
        intent = decision.order_intent
        self.assertEqual(intent.risk_budget, 500.0, "0.5% of 100k capital = 500.0")
        self.assertTrue(intent.quantity > 0)

        # -------------------------------------------------------------
        # STEP 3: Paper Entry Execution (PaperExecutionAdapter fills with slippage)
        # -------------------------------------------------------------
        order = paper_adapter.submit_order(intent)
        self.assertEqual(order.status.value, "FILLED")
        self.assertEqual(order.quantity, intent.quantity)
        expected_slippage = round(intent.price * 0.0005, 2)
        expected_fill = round(intent.price + expected_slippage, 2)
        self.assertEqual(order.average_fill_price, expected_fill)

        open_positions = paper_adapter.get_open_positions()
        self.assertEqual(len(open_positions), 1)
        pos = open_positions[0]
        self.assertEqual(pos.status, PositionStatus.OPEN)
        self.assertEqual(pos.quantity, order.quantity)

        # -------------------------------------------------------------
        # STEP 4: Supabase Entry Persistence & Accounting Parity
        # -------------------------------------------------------------
        entry_fees = TransactionCostModel.calculate_leg_costs(
            quantity=order.quantity,
            price=order.average_fill_price,
            side="BUY",
        )
        reserve_trade_slot(self.conn, self.account_id, symbol, active_date, "worker-test-01")

        entry_db_res = persist_trade_cycle(
            conn=self.conn,
            user_id=self.test_user_id,
            account_id=self.account_id,
            symbol=symbol,
            direction="long",
            signal_price=signal.entry_price,
            fill_price=order.average_fill_price,
            quantity=order.quantity,
            fees=entry_fees,
            research_snapshot_id=snap.snapshot_id,
        )
        paper_acct = paper_adapter.get_account_state()
        self.assertAlmostEqual(
            paper_acct.cash_balance,
            float(entry_db_res["cash_balance"]),
            places=2,
            msg="Entry cash balance must match Supabase to ₹0.00 discrepancy",
        )
        self.assertEqual(entry_db_res["position"]["status"], "open")

        # -------------------------------------------------------------
        # STEP 5: Paper Exit Execution (Target Reached)
        # -------------------------------------------------------------
        target_price = pos.target
        closed_pos = paper_adapter.close_position(
            pos.position_id,
            exit_price=target_price,
            reason="TARGET_HIT",
        )
        self.assertEqual(closed_pos.status, PositionStatus.CLOSED)
        self.assertTrue(closed_pos.realized_pnl > 0, "Target hit on long trade must yield positive net P&L")

        # -------------------------------------------------------------
        # STEP 6: Supabase Exit Persistence & Full Accounting Reconciliation
        # -------------------------------------------------------------
        exit_fees = TransactionCostModel.calculate_leg_costs(
            quantity=closed_pos.quantity,
            price=closed_pos.exit_price,
            side="SELL",
        )
        exit_db_res = persist_trade_cycle(
            conn=self.conn,
            user_id=self.test_user_id,
            account_id=self.account_id,
            symbol=symbol,
            direction="sell",
            signal_price=target_price,
            fill_price=closed_pos.exit_price,
            quantity=closed_pos.quantity,
            fees=exit_fees,
            research_snapshot_id=snap.snapshot_id,
        )
        paper_acct_final = paper_adapter.get_account_state()
        self.assertAlmostEqual(
            paper_acct_final.cash_balance,
            float(exit_db_res["cash_balance"]),
            places=2,
            msg="Exit cash balance must reconcile exactly with Supabase to ₹0.00 discrepancy",
        )
        self.assertEqual(exit_db_res["position"]["status"], "closed")

        # -------------------------------------------------------------
        # STEP 7: Worker Restart & Idempotency Check
        # -------------------------------------------------------------
        # Simulate a completely fresh worker process starting up (e.g. next GitHub Actions run)
        fresh_worker = IntradayWorker(mode=TradingMode.PAPER, use_mock=True, user_id=self.test_user_id)

        # Worker must connect and restore ledger balance
        ledger = get_account_ledger(self.conn, self.account_id)
        self.assertAlmostEqual(ledger["cash_balance"], float(exit_db_res["cash_balance"]), places=2)
        self.assertAlmostEqual(fresh_worker.execution_adapter.account.cash_balance, float(exit_db_res["cash_balance"]), places=2)

        # Idempotency: Supabase must confirm symbol was already traded today
        already_traded = is_symbol_traded_today(self.conn, self.account_id, symbol, active_date)
        self.assertTrue(already_traded, "Database must atomically identify symbol as already traded today")

        # Second trade reservation by another worker process must be rejected
        second_reservation = reserve_trade_slot(self.conn, self.account_id, symbol, active_date, "worker-test-02")
        self.assertFalse(second_reservation, "Second worker must be atomically blocked from reserving trade slot")

    def test_worker_run_cycle_full_lifecycle(self):
        """End-to-end worker.run_cycle execution: entry cycle -> exit cycle -> Supabase reconciliation."""
        active_date = datetime.date(2026, 10, 30)
        symbol = "JSWSTEEL"
        test_user = str(uuid.uuid4())
        test_acct_id = ensure_trading_account(
            self.conn,
            test_user,
            mode="paper",
            starting_capital=100_000.0,
        )

        # Clear any prior state for this test symbol and date
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM worker_candle_state WHERE symbol = %s AND trading_date = %s;", (symbol, active_date))
            cur.execute("DELETE FROM trade_reservations WHERE symbol = %s AND trading_date = %s;", (symbol, active_date))
        self.conn.commit()

        # 1. Normal fresh research snapshot for active_date
        snap = ResearchSnapshot(
            snapshot_id=f"RS-CYCLE-{uuid.uuid4().hex[:6].upper()}",
            session_type="pre_market",
            trading_date=str(active_date),
            market_outlook="NEUTRAL",
            is_tradeable_session=True,
            allowed_symbols=[symbol],
            watchlist=[{"symbol": symbol, "score": 2.0, "change_pct_1d": 2.0}],
        )

        # 2. Setup mock market data with synthetic breakout candles
        candles = MockMarketDataProvider.generate_synthetic_session(
            symbol=symbol,
            base_price=150.0,
            pattern="BULLISH_BREAKOUT",
            date=datetime.datetime(2026, 10, 30, tzinfo=IST),
        )

        worker = IntradayWorker(mode=TradingMode.PAPER, use_mock=True, user_id=test_user)
        worker.account_id = test_acct_id
        worker.market_data.set_candles(symbol, candles)
        worker.market_data.set_quote(symbol, MarketTick(
            symbol=symbol,
            ltp=candles[-1].close,
            bid=candles[-1].close - 0.05,
            ask=candles[-1].close + 0.05,
            volume=candles[-1].volume,
        ))

        try:
            with patch("backend.app.worker.load_latest_snapshot", return_value=snap):
                # 3. Cycle 1: Entry execution
                entry_time = datetime.datetime.combine(active_date, datetime.time(9, 36), tzinfo=IST)
                res1 = worker.run_cycle(session_date=active_date, current_time=entry_time)
                self.assertEqual(res1["orders"], 1, "Must execute 1 paper order on breakout")
                self.assertEqual(len(worker.execution_adapter.get_open_positions()), 1)
                open_pos = worker.execution_adapter.get_open_positions()[0]

                # Supabase entry ledger check
                ledger1 = get_account_ledger(self.conn, test_acct_id)
                self.assertAlmostEqual(
                    worker.execution_adapter.account.cash_balance,
                    ledger1["cash_balance"],
                    places=2,
                    msg="Entry cash must match Supabase ledger exactly",
                )

                # 4. Cycle 2: Target hit exit
                target_price = open_pos.target
                worker.market_data.set_quote(symbol, MarketTick(
                    symbol=symbol,
                    ltp=target_price,
                    bid=target_price - 0.05,
                    ask=target_price + 0.05,
                    volume=50000,
                ))

                exit_time = datetime.datetime.combine(active_date, datetime.time(10, 0), tzinfo=IST)
                res2 = worker.run_cycle(session_date=active_date, current_time=exit_time)
                self.assertEqual(res2["closed_positions"], 1, "Must close 1 position when target reached")
                self.assertEqual(res2["orders"], 0, "Idempotency must prevent new entries for same symbol")
                self.assertEqual(len(worker.execution_adapter.get_open_positions()), 0)

                # Supabase exit reconciliation
                ledger2 = get_account_ledger(self.conn, test_acct_id)
                self.assertAlmostEqual(
                    worker.execution_adapter.account.cash_balance,
                    ledger2["cash_balance"],
                    places=2,
                    msg="Exit cash must match Supabase ledger exactly to ₹0.00 discrepancy",
                )
                self.assertTrue(ledger2["cash_balance"] > 100_000.0, "Target hit profit must increase net cash above starting capital")
                self.assertEqual(ledger2["deployed_margin"], 0.0, "Deployed margin must be 0 after position close")
        finally:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM order_fills WHERE order_id IN (SELECT id FROM orders WHERE account_id = %s);", (test_acct_id,))
                cur.execute("DELETE FROM orders WHERE account_id = %s;", (test_acct_id,))
                cur.execute("DELETE FROM order_intents WHERE account_id = %s;", (test_acct_id,))
                cur.execute("DELETE FROM positions WHERE account_id = %s;", (test_acct_id,))
                cur.execute("DELETE FROM trade_reservations WHERE account_id = %s;", (test_acct_id,))
                cur.execute("DELETE FROM risk_decisions WHERE account_id = %s;", (test_acct_id,))
                cur.execute("DELETE FROM trading_accounts WHERE id = %s;", (test_acct_id,))
            self.conn.commit()


if __name__ == "__main__":
    unittest.main()
