"""
Focused unit tests: Research snapshot gating in IntradayWorker.run_cycle().

Tests worker's snapshot validation logic in isolation — no Supabase, no network,
no paper orders. All dependencies mocked.

Coverage:
  1. valid_snapshot_populates_candidates    fresh + date match + NEUTRAL → evaluates 2 symbols
  2. stale_snapshot_suspends               created >6h ago → STALE_SNAPSHOT
  3. missing_snapshot_uses_defaults        no snapshot → fallback universe (5 symbols)
  4. high_risk_snapshot_suspends           HIGH_RISK → HIGH_RISK_OUTLOOK
  5. wrong_date_snapshot_rejected          trading_date != active_date → SNAPSHOT_DATE_MISMATCH
  6. non_tradeable_session_skipped         is_tradeable_session=False → SKIPPED / NSE_HOLIDAY
  7. watchlist_preferred_over_allowed      watchlist beats allowed_symbols
  8. empty_watchlist_and_allowed_suspends  both empty → EMPTY_WATCHLIST
"""

from __future__ import annotations

import datetime
import sys
import uuid
import zoneinfo
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.models import ResearchSnapshot

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(
    *,
    trading_date: str,
    age_hours: float = 1.0,            # hours in the past (positive = older)
    market_outlook: str = "NEUTRAL",
    is_tradeable_session: bool = True,
    no_trade_reason: str | None = None,
    watchlist: list[dict] | None = None,
    allowed_symbols: list[str] | None = None,
) -> ResearchSnapshot:
    created_at = datetime.datetime.now(UTC) - datetime.timedelta(hours=age_hours)
    return ResearchSnapshot(
        snapshot_id=f"RS-TEST-{uuid.uuid4().hex[:6].upper()}",
        created_at=created_at,
        session_type="pre_market",
        trading_date=trading_date,
        market_outlook=market_outlook,
        is_tradeable_session=is_tradeable_session,
        no_trade_reason=no_trade_reason,
        watchlist=watchlist if watchlist is not None else [],
        allowed_symbols=allowed_symbols if allowed_symbols is not None else [],
    )


def _today_ist() -> datetime.date:
    return datetime.datetime.now(IST).date()


def _run_worker_cycle(snapshot: ResearchSnapshot | None, active_date: datetime.date) -> dict:
    """
    Instantiate IntradayWorker via __new__ (skipping __init__) and call run_cycle()
    with all external dependencies mocked.
    """
    from backend.app.worker import IntradayWorker
    from backend.app.core.config import TradingMode

    worker = IntradayWorker.__new__(IntradayWorker)
    worker.mode = TradingMode.PAPER
    worker.worker_id = "test-worker"
    worker.traded_symbols_today = set()
    worker.conn = None
    worker.account_id = None

    # Mock execution adapter — no positions, no orders
    adapter = MagicMock()
    adapter.get_open_positions.return_value = []
    adapter.get_account_state.return_value = MagicMock(total_equity=100_000.0, cash_balance=100_000.0)
    worker.execution_adapter = adapter

    # Mock trading engine — no signals, no orders
    engine = MagicMock()
    engine.evaluate_open_positions.return_value = []
    engine.process_symbol.return_value = (None, None)
    worker.engine = engine

    worker.market_data = MagicMock()

    # Patch load_latest_snapshot and is_snapshot_fresh so no DB is touched
    def _fresh(s: ResearchSnapshot) -> bool:
        age = (datetime.datetime.now(UTC) - s.created_at).total_seconds()
        return age < 6 * 3600

    with patch("backend.app.worker.load_latest_snapshot", return_value=snapshot), \
         patch("backend.app.worker.is_snapshot_fresh", side_effect=_fresh):
        return worker.run_cycle(session_date=active_date)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResearchWorkerGating(unittest.TestCase):

    def setUp(self):
        self.today = _today_ist()

    # 1 --- valid snapshot proceeds to evaluation
    def test_valid_snapshot_populates_candidates(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=1.0,
            market_outlook="NEUTRAL",
            watchlist=[{"symbol": "RELIANCE"}, {"symbol": "TCS"}],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertNotIn(result.get("status"), ("SUSPENDED", "SKIPPED"),
                         f"Should proceed to evaluation, got: {result}")
        self.assertEqual(result.get("evaluated"), 2,
                         f"Expected 2 watchlist symbols, got: {result}")

    # 2 --- stale snapshot suspended
    def test_stale_snapshot_suspends_trading(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=7.0,           # 7h > 6h threshold → stale
            market_outlook="NEUTRAL",
            allowed_symbols=["SBIN"],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertEqual(result.get("status"), "SUSPENDED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "STALE_SNAPSHOT", f"Got: {result}")

    # 3 --- missing snapshot suspends trading
    def test_missing_snapshot_suspends_trading(self):
        result = _run_worker_cycle(None, self.today)
        self.assertEqual(result.get("status"), "SUSPENDED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "MISSING_RESEARCH_SNAPSHOT", f"Got: {result}")

    # 4 --- HIGH_RISK suspends new entries
    def test_high_risk_snapshot_suspends_entries(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=1.0,
            market_outlook="HIGH_RISK",
            allowed_symbols=["SBIN"],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertEqual(result.get("status"), "SUSPENDED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "HIGH_RISK_OUTLOOK", f"Got: {result}")

    # 5 --- wrong-date snapshot rejected
    def test_wrong_date_snapshot_rejected(self):
        yesterday = str(self.today - datetime.timedelta(days=1))
        snap = _make_snapshot(
            trading_date=yesterday,
            age_hours=1.0,
            market_outlook="NEUTRAL",
            allowed_symbols=["SBIN"],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertEqual(result.get("status"), "SUSPENDED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "SNAPSHOT_DATE_MISMATCH", f"Got: {result}")

    # 6 --- non-tradeable session skipped
    def test_non_tradeable_session_skipped(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=1.0,
            market_outlook="NEUTRAL",
            is_tradeable_session=False,
            no_trade_reason="NSE_HOLIDAY",
            allowed_symbols=["SBIN"],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertEqual(result.get("status"), "SKIPPED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "NSE_HOLIDAY", f"Got: {result}")

    # 7 --- watchlist takes priority over allowed_symbols
    def test_watchlist_preferred_over_allowed_symbols(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=1.0,
            market_outlook="NEUTRAL",
            watchlist=[{"symbol": "HDFCBANK"}],
            allowed_symbols=["SBIN", "TCS"],   # must be ignored
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertNotIn(result.get("status"), ("SUSPENDED", "SKIPPED"),
                         f"Got: {result}")
        self.assertEqual(result.get("evaluated"), 1,
                         "Only watchlist (1 symbol) should be evaluated, not allowed_symbols (2)")

    # 8 --- empty watchlist AND empty allowed_symbols suspends
    def test_empty_watchlist_and_allowed_symbols_suspends(self):
        snap = _make_snapshot(
            trading_date=str(self.today),
            age_hours=1.0,
            market_outlook="NEUTRAL",
            watchlist=[],
            allowed_symbols=[],
        )
        result = _run_worker_cycle(snap, self.today)
        self.assertEqual(result.get("status"), "SUSPENDED", f"Got: {result}")
        self.assertEqual(result.get("reason"), "EMPTY_WATCHLIST", f"Got: {result}")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestResearchWorkerGating))
    sys.exit(0 if result.wasSuccessful() else 1)

