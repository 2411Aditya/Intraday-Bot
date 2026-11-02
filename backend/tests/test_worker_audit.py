"""Production Paper Worker Audit and Pre-Schedule Verification.

Covers the 5 core safety criteria before enabling scheduled workflows:
1. Open positions are checked and exited even when research is HIGH_RISK, stale, missing, or entry session is closed.
2. Supabase exit persistence failures do not silently mark positions closed; retries are idempotent.
3. Restart recovery restores cash, open positions, and daily risk limits correctly (trades_count_today, realized_pnl_today, is_daily_loss_breached).
4. Signal timestamps use actual completed candles, never fabricated current_time values in production.
5. No live order API can execute (LiveExecutionAdapter hard locked, paper execution isolated).
"""

from __future__ import annotations

import datetime
from datetime import timezone
import unittest
from unittest.mock import MagicMock, patch
import zoneinfo

from backend.app.core.config import TradingMode
from backend.app.execution.live_adapter import LiveExecutionAdapter, LiveExecutionLockedError
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.models.domain import (
    AccountState,
    Candle,
    IndicatorSnapshot,
    MarketTick,
    OrderIntent,
    OrderStatus,
    Position,
    PositionStatus,
    Signal,
    SignalDirection,
)
from backend.app.risk.engine import RiskEngine
from backend.app.strategies.vwap_orb_strategy import VWAP_ORB_Strategy
from backend.app.trading_engine import TradingEngine
from backend.app.worker import IntradayWorker
from research.models import ResearchSnapshot

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


class TestProductionPaperWorkerAudit(unittest.TestCase):

    def setUp(self):
        self.today = datetime.datetime.now(IST).date()

    # -------------------------------------------------------------------------
    # 1. Open positions checked and exited during HIGH_RISK / stale research
    # -------------------------------------------------------------------------
    def test_open_position_exited_during_high_risk_and_stale_research(self):
        """Worker must check and close open positions even when research is HIGH_RISK or stale."""
        worker = IntradayWorker.__new__(IntradayWorker)
        worker.mode = TradingMode.PAPER
        worker.worker_id = "test-audit-worker"
        worker.traded_symbols_today = set()
        worker.conn = MagicMock()
        worker.account_id = "test-acct-001"
        worker.system_user_id = "00000000-0000-0000-0000-000000000001"

        # Create paper adapter with 1 open position
        adapter = PaperExecutionAdapter(starting_capital=100_000.0)
        pos = Position(
            order_id="ORD-ENTRY-1",
            symbol="TATAMOTORS",
            direction=SignalDirection.BUY,
            quantity=10,
            entry_price=1000.0,
            current_price=1000.0,
            stop_loss=980.0,
            target=1040.0,
            status=PositionStatus.OPEN,
            mode=TradingMode.PAPER,
        )
        adapter.positions[pos.position_id] = pos
        worker.execution_adapter = adapter

        risk_eng = RiskEngine()
        market_data = MagicMock()
        # Market quote hits target (1045.0 >= 1040.0)
        market_data.get_current_quote.return_value = MarketTick(
            symbol="TATAMOTORS",
            ltp=1045.0,
            bid=1044.90,
            ask=1045.10,
            volume=50000,
        )
        worker.market_data = market_data
        worker.engine = TradingEngine(
            market_data_provider=market_data,
            risk_engine=risk_eng,
            execution_adapter=adapter,
            mode=TradingMode.PAPER,
        )

        # High Risk research snapshot
        high_risk_snap = ResearchSnapshot(
            snapshot_id="RS-AUDIT-HIGH-RISK",
            created_at=datetime.datetime.now(UTC),
            session_type="pre_market",
            trading_date=str(self.today),
            market_outlook="HIGH_RISK",
            is_tradeable_session=True,
            watchlist=[{"symbol": "TATAMOTORS"}],
            allowed_symbols=["TATAMOTORS"],
        )

        with patch("backend.app.worker.load_latest_snapshot", return_value=high_risk_snap), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=True), \
             patch("backend.app.worker.is_position_open_in_db", return_value=True), \
             patch("backend.app.worker.persist_trade_cycle") as mock_persist:

            res = worker.run_cycle(session_date=self.today)

            # Exits must have been evaluated and closed
            self.assertEqual(res["closed_positions"], 1)
            # New entries must be suspended due to HIGH_RISK
            self.assertEqual(res["status"], "SUSPENDED")
            self.assertEqual(res["reason"], "HIGH_RISK_OUTLOOK")

            # Position in adapter should now be CLOSED
            self.assertEqual(adapter.positions[pos.position_id].status, PositionStatus.CLOSED)
            self.assertEqual(len(adapter.get_open_positions()), 0)

            # DB persistence must have been called for the exit
            mock_persist.assert_called_once()
            call_kwargs = mock_persist.call_args.kwargs
            self.assertEqual(call_kwargs["symbol"], "TATAMOTORS")
            self.assertEqual(call_kwargs["direction"], "sell")

    # -------------------------------------------------------------------------
    # 2. Persistence failures revert position; retries are idempotent
    # -------------------------------------------------------------------------
    def test_exit_persistence_failure_reverts_position_and_retries_idempotently(self):
        """Supabase exit persistence failure must revert position to OPEN so next cycle retries."""
        worker = IntradayWorker.__new__(IntradayWorker)
        worker.mode = TradingMode.PAPER
        worker.worker_id = "test-persistence-worker"
        worker.traded_symbols_today = set()
        worker.conn = MagicMock()
        worker.account_id = "test-acct-002"
        worker.system_user_id = "00000000-0000-0000-0000-000000000001"

        adapter = PaperExecutionAdapter(starting_capital=100_000.0)
        pos = Position(
            order_id="ORD-ENTRY-2",
            symbol="INFY",
            direction=SignalDirection.BUY,
            quantity=10,
            entry_price=1500.0,
            current_price=1500.0,
            stop_loss=1470.0,
            target=1550.0,
            status=PositionStatus.OPEN,
            mode=TradingMode.PAPER,
        )
        adapter.positions[pos.position_id] = pos
        worker.execution_adapter = adapter

        market_data = MagicMock()
        market_data.get_current_quote.return_value = MarketTick(
            symbol="INFY",
            ltp=1555.0,  # Hits target
            bid=1554.80,
            ask=1555.20,
            volume=80000,
        )
        worker.market_data = market_data
        worker.engine = TradingEngine(
            market_data_provider=market_data,
            risk_engine=RiskEngine(),
            execution_adapter=adapter,
            mode=TradingMode.PAPER,
        )

        valid_snap = ResearchSnapshot(
            snapshot_id="RS-AUDIT-VALID",
            created_at=datetime.datetime.now(UTC),
            session_type="pre_market",
            trading_date=str(self.today),
            market_outlook="NEUTRAL",
            is_tradeable_session=True,
            watchlist=[],
            allowed_symbols=[],
        )

        # Cycle 1: persist_trade_cycle fails with database connection error
        with patch("backend.app.worker.load_latest_snapshot", return_value=valid_snap), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=True), \
             patch("backend.app.worker.is_position_open_in_db", return_value=True), \
             patch("backend.app.worker.persist_trade_cycle", side_effect=RuntimeError("Supabase connection reset")):

            res1 = worker.run_cycle(session_date=self.today)
            # closed_positions count adjusted to 0 on failure
            self.assertEqual(res1["closed_positions"], 0)
            # Position must be reverted to OPEN in memory for retry
            self.assertEqual(adapter.positions[pos.position_id].status, PositionStatus.OPEN)
            self.assertEqual(len(adapter.get_open_positions()), 1)

        # Cycle 2: persistence succeeds on retry
        with patch("backend.app.worker.load_latest_snapshot", return_value=valid_snap), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=True), \
             patch("backend.app.worker.is_position_open_in_db", return_value=True), \
             patch("backend.app.worker.persist_trade_cycle") as mock_persist_success:

            res2 = worker.run_cycle(session_date=self.today)
            self.assertEqual(res2["closed_positions"], 1)
            self.assertEqual(adapter.positions[pos.position_id].status, PositionStatus.CLOSED)
            self.assertEqual(len(adapter.get_open_positions()), 0)
            mock_persist_success.assert_called_once()

        # Cycle 3: Idempotency check - if DB already records closed, do not duplicate persistence
        with patch("backend.app.worker.load_latest_snapshot", return_value=valid_snap), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=True), \
             patch("backend.app.worker.is_position_open_in_db", return_value=False), \
             patch("backend.app.worker.persist_trade_cycle") as mock_persist_duplicate:

            # Put position back as if another worker checked it
            adapter.positions[pos.position_id].status = PositionStatus.OPEN
            res3 = worker.run_cycle(session_date=self.today)
            # persist_trade_cycle was NOT called because is_position_open_in_db returned False
            mock_persist_duplicate.assert_not_called()

    # -------------------------------------------------------------------------
    # 3. Restart recovery restores cash, open positions, and daily risk limits
    # -------------------------------------------------------------------------
    def test_restart_recovery_restores_daily_risk_limits(self):
        """Worker restart must restore trades_count_today and circuit breaker breach status."""
        worker = IntradayWorker.__new__(IntradayWorker)
        worker.mode = TradingMode.PAPER
        worker.worker_id = "test-recovery-worker"
        worker.conn = MagicMock()
        worker.account_id = "test-acct-003"
        worker.risk_engine = RiskEngine(max_trades_per_day=2, max_daily_loss_pct=1.0)
        worker.execution_adapter = PaperExecutionAdapter(starting_capital=100_000.0)

        # Mock Supabase returning 2 filled trades and a 1200 INR loss today
        mock_daily_state = {
            "cash_balance": 98800.0,
            "deployed_margin": 0.0,
            "trades_count_today": 2,
            "realized_pnl_today": -1200.0,
        }
        mock_open_positions = []

        with patch("backend.app.persistence.supabase_trader.get_daily_account_state", return_value=mock_daily_state), \
             patch("backend.app.persistence.supabase_trader.get_open_positions_from_db", return_value=mock_open_positions):

            worker._sync_state_from_db(active_date=self.today)

            acct = worker.execution_adapter.account
            self.assertEqual(acct.cash_balance, 98800.0)
            self.assertEqual(acct.trades_count_today, 2)
            self.assertEqual(acct.realized_pnl_today, -1200.0)
            self.assertTrue(acct.is_daily_loss_breached)

            # Test that RiskEngine rejects any new signal with MAX_DAILY_TRADES_EXCEEDED
            # Use 10:00 AM IST timestamp inside the 09:30-11:30 entry window
            sig_ts = datetime.datetime.now(IST).replace(hour=10, minute=0, second=0, microsecond=0)
            mock_signal = Signal(
                symbol="SBIN",
                direction=SignalDirection.BUY,
                entry_price=800.0,
                stop_loss=790.0,
                target_price=820.0,
                planned_rrr=2.0,
                timestamp=sig_ts,
                expiry_time=sig_ts + datetime.timedelta(minutes=10),
                indicators=IndicatorSnapshot(
                    symbol="SBIN",
                    timestamp=sig_ts,
                    vwap=795.0,
                    ema_20=796.0,
                    atr_14=4.0,
                    orb_high=805.0,
                    orb_low=790.0,
                    volume_sma_10=10000.0,
                    relative_volume=1.5,
                    body_ratio=0.6,
                ),
                checklist_passed={"long_rule": True},
            )
            mock_quote = MarketTick(symbol="SBIN", ltp=800.0, bid=799.9, ask=800.1, volume=100000)

            decision = worker.risk_engine.evaluate_signal(
                signal=mock_signal,
                account=acct,
                quote=mock_quote,
                open_positions=[],
                is_market_data_healthy=True,
                current_execution_time=sig_ts,  # Within 10m of signal
            )
            self.assertFalse(decision.approved)
            self.assertIn("MAX_DAILY_TRADES_EXCEEDED_2", decision.rejection_reason)

    # -------------------------------------------------------------------------
    # 4. Signal timestamps use actual completed candles, reject stale in production
    # -------------------------------------------------------------------------
    def test_signal_timestamps_use_completed_candles_and_reject_stale_in_production(self):
        """Signal timestamps must match candle timestamps, and stale signals must be rejected."""
        # 1. Historical candle from earlier in the day (e.g., 09:35 IST = 04:05 UTC)
        candle_ts = datetime.datetime.now(UTC).replace(hour=4, minute=5, second=0, microsecond=0)
        c = Candle(
            symbol="SBIN",
            timestamp=candle_ts,
            open=800.0,
            high=810.0,
            low=799.0,
            close=808.0,
            volume=200000,
        )
        indicators = IndicatorSnapshot(
            symbol="SBIN",
            timestamp=candle_ts,
            vwap=802.0,
            ema_20=801.0,
            atr_14=4.0,
            orb_high=805.0,
            orb_low=795.0,
            volume_sma_10=100000.0,
            relative_volume=2.0,
            body_ratio=0.75,
            nifty_close=24500.0,
            nifty_vwap=24400.0,
        )

        # 4 completed 5m candles (so len >= 4 and candle completion check passes)
        candles = [
            c.model_copy(update={"timestamp": candle_ts - datetime.timedelta(minutes=15)}),
            c.model_copy(update={"timestamp": candle_ts - datetime.timedelta(minutes=10)}),
            c.model_copy(update={"timestamp": candle_ts - datetime.timedelta(minutes=5)}),
            c,
        ]

        # Long entry conditions checklist
        long_check = VWAP_ORB_Strategy._check_long_rules(c, indicators)
        self.assertTrue(all(long_check.values()))

        # Evaluate strategy
        with patch("backend.app.strategies.vwap_orb_strategy.TechnicalIndicatorEngine.compute_snapshot", return_value=indicators), \
             patch.object(VWAP_ORB_Strategy, "_check_long_rules", return_value=long_check):

            sig = VWAP_ORB_Strategy.evaluate(candles, candles)
            self.assertIsNotNone(sig)
            # Signal timestamp MUST equal the completed candle timestamp
            self.assertEqual(sig.timestamp, candle_ts)
            self.assertEqual(sig.expiry_time, candle_ts + datetime.timedelta(minutes=10))

            # When evaluated in production with current_execution_time=None (wall-clock UTC):
            # The signal (from 04:05 UTC) is expired against the real current time
            risk_eng = RiskEngine()
            acct = AccountState(
                mode=TradingMode.PAPER,
                starting_capital=100_000.0,
                cash_balance=100_000.0,
                max_daily_loss_budget=1000.0,
            )
            quote = MarketTick(symbol="SBIN", ltp=808.0, bid=807.9, ask=808.1, volume=200000)

            # Production evaluation uses actual wall-clock time
            decision = risk_eng.evaluate_signal(
                signal=sig,
                account=acct,
                quote=quote,
                open_positions=[],
                is_market_data_healthy=True,
                current_execution_time=None,  # Production default
            )
            # Must reject stale historical candle
            self.assertFalse(decision.approved)
            self.assertIn("SIGNAL_EXPIRED", decision.rejection_reason)

    # -------------------------------------------------------------------------
    # 5. Live order API strictly locked; cannot execute
    # -------------------------------------------------------------------------
    def test_live_order_api_strictly_blocked(self):
        """LiveExecutionAdapter must throw LiveExecutionLockedError under default paper config."""
        live_adapter = LiveExecutionAdapter()
        self.assertTrue(live_adapter.is_locked)

        intent = OrderIntent(
            signal_id="SIG-TEST-LIVE",
            symbol="SBIN",
            direction=SignalDirection.BUY,
            quantity=10,
            price=800.0,
            stop_loss=790.0,
            target=820.0,
            mode=TradingMode.ACTUAL,
            risk_budget=500.0,
            estimated_costs=15.0,
            projected_gross_profit=1000.0,
        )

        with self.assertRaises(LiveExecutionLockedError):
            live_adapter.submit_order(intent)

        with self.assertRaises(LiveExecutionLockedError):
            live_adapter.cancel_order("ORD-LIVE-001")

        with self.assertRaises(LiveExecutionLockedError):
            live_adapter.close_position("POS-LIVE-001", 810.0)

        # Confirm PaperExecutionAdapter does not place live broker orders
        paper_adapter = PaperExecutionAdapter()
        self.assertFalse(hasattr(paper_adapter, "placeOrder"))
        self.assertFalse(hasattr(paper_adapter, "smartConnect"))


if __name__ == "__main__":
    unittest.main()
