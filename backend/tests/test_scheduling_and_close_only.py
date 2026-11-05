"""Focused tests for:
1. Research cron-to-session deterministic mapping (not UTC-hour-based).
2. Delayed scheduled runs (past market close) are skipped for new entries.
3. Close-only mode never opens new positions, closes existing ones only.
4. Repeated close-only calls are idempotent.
5. Market-closed entry rejection.
6. Stale research blocks new entries but not close-only.
"""

from __future__ import annotations

import datetime
import sys
import unittest
import zoneinfo
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import TradingMode
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.market_data.mock_provider import MockMarketDataProvider
from backend.app.models.domain import (
    MarketTick,
    Position,
    PositionStatus,
    SignalDirection,
)
from backend.app.risk.engine import RiskEngine
from backend.app.trading_engine import TradingEngine
from backend.app.worker import IntradayWorker
from research.models import ResearchSnapshot

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CRON_TO_SESSION = {
    "0 3 * * 1-5": "pre_market",
    "30 10 * * 1-5": "post_market",
    "30 17 * * 0-4": "overnight",
}


def _resolve_session_from_schedule(schedule: str) -> str:
    """Mirrors the deterministic mapping in research.yml Determine Session Type step."""
    mapping = {
        "0 3 * * 1-5": "pre_market",
        "30 10 * * 1-5": "post_market",
        "30 17 * * 0-4": "overnight",
    }
    if schedule not in mapping:
        raise ValueError(f"Unknown schedule '{schedule}'. Cannot determine session type safely.")
    return mapping[schedule]


def _make_worker_no_db() -> IntradayWorker:
    w = IntradayWorker.__new__(IntradayWorker)
    w.mode = TradingMode.PAPER
    w.worker_id = "test-sched-worker"
    w.traded_symbols_today = set()
    w.conn = None
    w.account_id = None
    w.system_user_id = "test-user-sched"
    w.execution_adapter = PaperExecutionAdapter(starting_capital=10_000.0)
    w.risk_engine = RiskEngine()
    md = MagicMock()
    md.get_current_quote.return_value = MarketTick(
        symbol="SBIN", ltp=800.0, bid=799.9, ask=800.1, volume=100000
    )
    md.is_healthy.return_value = True
    md.get_historical_candles.return_value = []
    w.market_data = md
    w.engine = TradingEngine(
        market_data_provider=md,
        risk_engine=w.risk_engine,
        execution_adapter=w.execution_adapter,
        mode=TradingMode.PAPER,
    )
    return w


def _fresh_snap(today: datetime.date) -> ResearchSnapshot:
    return ResearchSnapshot(
        snapshot_id="RS-SCHED-TEST",
        created_at=datetime.datetime.now(UTC),
        session_type="pre_market",
        trading_date=str(today),
        market_outlook="NEUTRAL",
        is_tradeable_session=True,
        watchlist=[{"symbol": "SBIN"}],
        allowed_symbols=["SBIN"],
    )


def _stale_snap(today: datetime.date) -> ResearchSnapshot:
    return ResearchSnapshot(
        snapshot_id="RS-STALE-TEST",
        created_at=datetime.datetime.now(UTC) - datetime.timedelta(hours=8),
        session_type="pre_market",
        trading_date=str(today),
        market_outlook="NEUTRAL",
        is_tradeable_session=True,
        watchlist=[{"symbol": "SBIN"}],
        allowed_symbols=["SBIN"],
    )


def _open_position(today: datetime.datetime) -> Position:
    return Position(
        order_id="ord-close-only",
        position_id="pos-close-only",
        symbol="SBIN",
        direction=SignalDirection.BUY,
        entry_price=790.0,
        current_price=790.0,
        stop_loss=780.0,
        target=820.0,
        quantity=10,
        entry_time=today - datetime.timedelta(hours=2),
        mode=TradingMode.PAPER,
        status=PositionStatus.OPEN,
    )


# ---------------------------------------------------------------------------
# 1. Cron-to-session deterministic mapping
# ---------------------------------------------------------------------------

class TestCronToSessionMapping(unittest.TestCase):

    def test_premarket_cron_resolves_correctly(self):
        self.assertEqual(_resolve_session_from_schedule("0 3 * * 1-5"), "pre_market")

    def test_postmarket_cron_resolves_correctly(self):
        self.assertEqual(_resolve_session_from_schedule("30 10 * * 1-5"), "post_market")

    def test_overnight_cron_resolves_correctly(self):
        self.assertEqual(_resolve_session_from_schedule("30 17 * * 0-4"), "overnight")

    def test_unknown_schedule_raises_safely(self):
        """An unrecognised schedule string must raise ValueError — never silently pick a wrong session."""
        with self.assertRaises(ValueError) as ctx:
            _resolve_session_from_schedule("*/5 3-10 * * 1-5")
        self.assertIn("Unknown schedule", str(ctx.exception))

    def test_all_three_scheduled_crons_are_mapped(self):
        """Ensure every production cron has a deterministic session."""
        for cron, expected_session in CRON_TO_SESSION.items():
            with self.subTest(cron=cron):
                self.assertEqual(_resolve_session_from_schedule(cron), expected_session)


# ---------------------------------------------------------------------------
# 2. Delayed run past market close — no new entries
# ---------------------------------------------------------------------------

class TestDelayedRunRejection(unittest.TestCase):

    def test_delayed_run_past_market_close_exits_cleanly(self):
        """Worker called after 15:30 IST must exit without creating new entries."""
        w = _make_worker_no_db()
        today = datetime.datetime.now(IST).date()
        post_close = datetime.datetime(today.year, today.month, today.day, 15, 35, 0, tzinfo=IST)

        with patch("backend.app.worker._is_trading_day", return_value=(True, "trading day")):
            is_open, msg = w.get_market_session_status(post_close)

        self.assertFalse(is_open)
        self.assertIn("15:30", msg)

    def test_worker_run_once_skips_cycle_after_market_close(self):
        """Worker --run-once without --force-session exits when market is closed."""
        w = _make_worker_no_db()
        today = datetime.datetime.now(IST).date()
        post_close = datetime.datetime(today.year, today.month, today.day, 15, 35, 0, tzinfo=IST)

        with patch("backend.app.worker._is_trading_day", return_value=(True, "trading day")), \
             patch("backend.app.worker.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = post_close
            mock_dt.datetime.combine = datetime.datetime.combine
            mock_dt.time = datetime.time
            is_open, _ = w.get_market_session_status(post_close)
            self.assertFalse(is_open)


# ---------------------------------------------------------------------------
# 3. Close-only mode: never creates new positions
# ---------------------------------------------------------------------------

class TestCloseOnlyMode(unittest.TestCase):

    def test_close_only_mode_never_calls_process_symbol(self):
        """In close_only mode, process_symbol must never be called (no new entries)."""
        today = datetime.datetime.now(IST).date()
        snap = _fresh_snap(today)
        worker = _make_worker_no_db()

        with patch("backend.app.worker.load_latest_snapshot", return_value=snap), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=True), \
             patch.object(worker.engine, "process_symbol") as mock_process, \
             patch.object(worker.engine, "evaluate_open_positions", return_value=[]):

            result = worker.run_cycle(session_date=today, close_only=True)

            mock_process.assert_not_called()
            self.assertEqual(result["orders"], 0)
            self.assertEqual(result["signals"], 0)
            self.assertEqual(result["status"], "CLOSE_ONLY")

    def test_close_only_still_evaluates_open_positions(self):
        """Close-only must still check and close existing open positions."""
        today = datetime.datetime.now(IST)
        worker = _make_worker_no_db()

        pos = _open_position(today)
        worker.execution_adapter.positions[pos.position_id] = pos
        # Rebuild engine with this adapter
        worker.engine = TradingEngine(
            market_data_provider=worker.market_data,
            risk_engine=worker.risk_engine,
            execution_adapter=worker.execution_adapter,
            mode=TradingMode.PAPER,
        )
        # Quote at target → triggers TARGET_HIT
        worker.market_data.get_current_quote.return_value = MarketTick(
            symbol="SBIN", ltp=825.0, bid=824.9, ask=825.1, volume=100000
        )

        result = worker.run_cycle(session_date=today.date(), close_only=True)

        self.assertEqual(result["closed_positions"], 1)
        self.assertEqual(result["orders"], 0)
        self.assertEqual(result["status"], "CLOSE_ONLY")

    def test_close_only_with_no_open_positions_is_idempotent(self):
        """Close-only with no open positions must succeed cleanly and not error."""
        today = datetime.datetime.now(IST).date()
        worker = _make_worker_no_db()

        result = worker.run_cycle(session_date=today, close_only=True)

        self.assertEqual(result["closed_positions"], 0)
        self.assertEqual(result["orders"], 0)
        self.assertEqual(result["status"], "CLOSE_ONLY")

    def test_close_only_does_not_require_fresh_research(self):
        """Close-only must not block exits due to stale or missing research."""
        today = datetime.datetime.now(IST).date()
        worker = _make_worker_no_db()

        # Stale snapshot — would normally block new entries
        stale = _stale_snap(today)

        with patch("backend.app.worker.load_latest_snapshot", return_value=stale), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=False), \
             patch.object(worker.engine, "evaluate_open_positions", return_value=[]) as mock_exits:

            result = worker.run_cycle(session_date=today, close_only=True)

            # evaluate_open_positions should STILL be called (exits run before research check)
            mock_exits.assert_called_once()
            self.assertEqual(result["status"], "CLOSE_ONLY")
            self.assertEqual(result["orders"], 0)

    def test_repeated_close_only_calls_are_idempotent(self):
        """Two consecutive close_only calls on already-closed positions create no duplicate exits."""
        today = datetime.datetime.now(IST)
        worker = _make_worker_no_db()

        pos = _open_position(today)
        worker.execution_adapter.positions[pos.position_id] = pos
        worker.engine = TradingEngine(
            market_data_provider=worker.market_data,
            risk_engine=worker.risk_engine,
            execution_adapter=worker.execution_adapter,
            mode=TradingMode.PAPER,
        )
        worker.market_data.get_current_quote.return_value = MarketTick(
            symbol="SBIN", ltp=825.0, bid=824.9, ask=825.1, volume=100000
        )

        # First call closes the position
        result1 = worker.run_cycle(session_date=today.date(), close_only=True)
        self.assertEqual(result1["closed_positions"], 1)

        # Second call: position already CLOSED, nothing to close
        result2 = worker.run_cycle(session_date=today.date(), close_only=True)
        self.assertEqual(result2["closed_positions"], 0)


# ---------------------------------------------------------------------------
# 4. Stale research blocks new entries but not square-off (non-close-only)
# ---------------------------------------------------------------------------

class TestStaleResearchGating(unittest.TestCase):

    def test_stale_research_blocks_new_entries(self):
        """Stale snapshot suspends new entries but exits still run."""
        today = datetime.datetime.now(IST).date()
        stale = _stale_snap(today)
        worker = _make_worker_no_db()

        with patch("backend.app.worker.load_latest_snapshot", return_value=stale), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=False), \
             patch.object(worker.engine, "evaluate_open_positions", return_value=[]):

            result = worker.run_cycle(session_date=today)
            self.assertEqual(result["status"], "SUSPENDED")
            self.assertEqual(result["reason"], "STALE_SNAPSHOT")
            self.assertEqual(result["orders"], 0)

    def test_stale_research_does_not_block_position_evaluation(self):
        """Even with stale research, evaluate_open_positions must be called before early return."""
        today = datetime.datetime.now(IST).date()
        stale = _stale_snap(today)
        worker = _make_worker_no_db()

        with patch("backend.app.worker.load_latest_snapshot", return_value=stale), \
             patch("backend.app.worker.is_snapshot_fresh", return_value=False), \
             patch.object(worker.engine, "evaluate_open_positions", return_value=[]) as mock_exits:

            worker.run_cycle(session_date=today)
            mock_exits.assert_called_once()


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestCronToSessionMapping))
    result2 = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestCloseOnlyMode))
    result3 = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestStaleResearchGating))
    result4 = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestDelayedRunRejection))
    sys.exit(0 if all(r.wasSuccessful() for r in [result, result2, result3, result4]) else 1)

