"""Intraday Trading Worker.

Portable execution worker for scheduled paper trading on GitHub Actions
and continuous daemon execution on Linux VPS.

Key Responsibilities:
1. Load latest valid ResearchSnapshot from Supabase.
2. Verify market session and tradeability (NSE hours 09:15 - 15:30 IST, holidays, event risk).
3. Filter symbols through research-approved watchlist.
4. Ingest real 5-minute equity candles with genuine volume.
5. Execute VWAP + 15-min ORB + EMA20 strategy via TradingEngine.
6. Guard all orders through RiskEngine and PaperExecutionAdapter (live broker calls strictly blocked).
7. Handle position exits (SL / TP) and idempotency.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is at sys.path[0] and remove backend/app to prevent shadowing stdlib 'logging'
app_dir = str(Path(__file__).resolve().parent)
while app_dir in sys.path:
    sys.path.remove(app_dir)
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import argparse
import datetime
import logging
import os
import time
import uuid
import zoneinfo

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(Path(root_dir) / ".env")
except Exception:
    pass

from backend.app.core.config import TradingMode, settings
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.market_data.angelone_provider import AngelOneProvider
from backend.app.market_data.mock_provider import MockMarketDataProvider
from backend.app.persistence.supabase_trader import (
    ensure_trading_account,
    get_daily_account_state,
    get_db_connection,
    get_last_processed_candle_ts,
    is_position_open_in_db,
    is_symbol_traded_today,
    persist_trade_cycle,
    reserve_trade_slot,
    save_last_processed_candle_ts,
)
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.risk.engine import RiskEngine
from backend.app.trading_engine import TradingEngine
from research.engine import _is_trading_day
from research.models import ResearchSnapshot
from research.persistence import is_snapshot_fresh, load_latest_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("IntradayWorker")

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


class IntradayWorker:
    """Portable Intraday Trading Worker."""

    def __init__(self, mode: TradingMode = TradingMode.PAPER, use_mock: bool = False, user_id: str | None = None):
        self.mode = mode
        self.use_mock = use_mock

        # Setup market data provider
        if use_mock:
            logger.info("Using MockMarketDataProvider")
            self.market_data = MockMarketDataProvider()
        else:
            logger.info("Using real AngelOneProvider")
            self.market_data = AngelOneProvider()

        # Core engines
        self.risk_engine = RiskEngine()
        self.execution_adapter = PaperExecutionAdapter(
            starting_capital=settings.VIRTUAL_STARTING_CAPITAL,
            max_daily_loss_pct=settings.MAX_DAILY_LOSS_PCT,
            slippage_rate=settings.MAX_SLIPPAGE_PCT / 100.0,
        )
        self.engine = TradingEngine(
            market_data_provider=self.market_data,
            risk_engine=self.risk_engine,
            execution_adapter=self.execution_adapter,
            mode=self.mode,
        )

        # Worker unique identifier for concurrency arbitration
        self.worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"

        # Database connection for state tracking and persistent idempotency
        self.conn = None
        self.account_id = None
        self.system_user_id = user_id or os.getenv("BOT_USER_ID", "00000000-0000-0000-0000-000000000001")
        try:
            self.conn = get_db_connection()
            self.account_id = ensure_trading_account(
                self.conn,
                self.system_user_id,
                mode=self.mode.value.lower(),
                starting_capital=settings.VIRTUAL_STARTING_CAPITAL,
            )
            logger.info("Connected to Supabase. Account ID: %s", self.account_id)
            self._sync_state_from_db()
        except Exception as e:
            logger.warning("Supabase connection not initialized for worker: %s", e)

        # Idempotency cache: tracks symbols traded today (in-memory fast cache backed by DB)
        self.traded_symbols_today: set[str] = set()

    def _sync_state_from_db(self, active_date: datetime.date | None = None) -> None:
        """Syncs account balance, daily risk limits, and open positions from Supabase on startup/restart."""
        if not self.conn or not self.account_id:
            return
        try:
            from backend.app.persistence.supabase_trader import (
                get_daily_account_state,
                get_open_positions_from_db,
            )
            today = active_date or datetime.datetime.now(IST).date()
            daily_state = get_daily_account_state(self.conn, self.account_id, today)

            if daily_state.get("cash_balance") is not None:
                db_cash = daily_state["cash_balance"]
                db_deployed = daily_state.get("deployed_margin") or 0.0
                # Only sync if account has activity in Supabase
                if db_cash > 0 and (db_cash != settings.VIRTUAL_STARTING_CAPITAL or db_deployed > 0):
                    self.execution_adapter.account.cash_balance = db_cash
                    self.execution_adapter.account.deployed_margin = db_deployed
                    logger.info("Restored ledger from Supabase: cash=%.2f deployed=%.2f", db_cash, db_deployed)

            # Restore daily risk counters
            db_trades = daily_state.get("trades_count_today", 0)
            db_pnl = daily_state.get("realized_pnl_today", 0.0)
            self.execution_adapter.account.trades_count_today = db_trades
            self.execution_adapter.account.realized_pnl_today = db_pnl
            if (
                db_pnl < 0 and abs(db_pnl) >= self.execution_adapter.account.max_daily_loss_budget
            ) or self.execution_adapter.account.daily_loss_pct >= self.risk_engine.max_daily_loss_pct:
                self.execution_adapter.account.is_daily_loss_breached = True
            logger.info(
                "Restored daily risk state: trades_count=%d realized_pnl=%.2f breach=%s",
                db_trades, db_pnl, self.execution_adapter.account.is_daily_loss_breached,
            )

            # Restore open positions
            open_db_positions = get_open_positions_from_db(self.conn, self.account_id)
            for db_p in open_db_positions:
                sym = db_p["symbol"]
                if sym not in [p.symbol for p in self.execution_adapter.get_open_positions()]:
                    from backend.app.models.domain import Position, PositionStatus, SignalDirection
                    dir_enum = SignalDirection.BUY if db_p["direction"].lower() in ("long", "buy") else SignalDirection.SELL
                    stop_loss = db_p["avg_entry_price"] * (0.98 if dir_enum == SignalDirection.BUY else 1.02)
                    target = db_p["avg_entry_price"] * (1.04 if dir_enum == SignalDirection.BUY else 0.96)
                    restored_pos = Position(
                        order_id=db_p.get("order_id", f"restored-{uuid.uuid4().hex[:6]}"),
                        symbol=sym,
                        direction=dir_enum,
                        quantity=db_p["quantity"],
                        entry_price=db_p["avg_entry_price"],
                        current_price=db_p["avg_entry_price"],
                        stop_loss=stop_loss,
                        target=target,
                        status=PositionStatus.OPEN,
                        mode=self.mode,
                    )
                    self.execution_adapter.positions[restored_pos.position_id] = restored_pos
                    logger.info("Restored open position from Supabase for %s (qty=%d @ %.2f)", sym, restored_pos.quantity, restored_pos.entry_price)
        except Exception as e:
            logger.warning("Could not sync state from Supabase: %s", e)

    def get_market_session_status(self, now: datetime.datetime) -> tuple[bool, str]:
        """Check if currently within regular NSE trading hours (09:15 - 15:30 IST)."""
        now_ist = now.astimezone(IST)
        date_str = now_ist.strftime("%Y-%m-%d")

        is_trading, reason = _is_trading_day(date_str)
        if not is_trading:
            return False, f"Non-trading day: {reason}"

        market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)

        if now_ist < market_open:
            return False, f"Pre-market: Current time {now_ist.strftime('%H:%M')} is before 09:15 IST"
        if now_ist > market_close:
            return False, f"Post-market: Current time {now_ist.strftime('%H:%M')} is after 15:30 IST"

        return True, "Market is OPEN"

    def run_cycle(self, session_date: datetime.date | None = None, current_time: datetime.datetime | None = None) -> dict:
        """Run a single evaluation cycle across candidate stocks."""
        now_ist = current_time.astimezone(IST) if current_time else datetime.datetime.now(IST)
        active_date = session_date or now_ist.date()

        logger.info("--- Starting Intraday Evaluation Cycle (date=%s, time=%s IST) ---", active_date, now_ist.strftime("%H:%M:%S"))

        cycle_results = {
            "evaluated": 0,
            "signals": 0,
            "orders": 0,
            "closed_positions": 0,
        }

        # 1. Open Position Monitoring & Exits ALWAYS run first
        # (Positions must be checked and closed even when research is HIGH_RISK, stale, missing, or entry session is closed)
        quotes: dict[str, float] = {}
        for pos in self.execution_adapter.get_open_positions():
            try:
                q = self.market_data.get_current_quote(pos.symbol)
                quotes[pos.symbol] = q.ltp
            except Exception as e:
                logger.warning("Could not fetch quote for open position %s: %s", pos.symbol, e)

        closed = self.engine.evaluate_open_positions(quotes)
        cycle_results["closed_positions"] = len(closed)
        if closed:
            logger.info("Closed %d positions during cycle", len(closed))
            if self.conn and self.account_id:
                for c_pos in closed:
                    try:
                        # Idempotency check: only persist if position is still open in DB
                        if is_position_open_in_db(self.conn, self.account_id, c_pos.symbol):
                            from backend.app.models.domain import SignalDirection
                            exit_direction = "sell" if c_pos.direction == SignalDirection.BUY else "buy"
                            exit_fees = TransactionCostModel.calculate_leg_costs(
                                quantity=c_pos.quantity,
                                price=c_pos.exit_price,
                                side=exit_direction.upper(),
                            )
                            persist_trade_cycle(
                                conn=self.conn,
                                user_id=self.system_user_id,
                                account_id=self.account_id,
                                symbol=c_pos.symbol,
                                direction=exit_direction,
                                signal_price=c_pos.exit_price,
                                fill_price=c_pos.exit_price,
                                quantity=c_pos.quantity,
                                fees=exit_fees,
                                research_snapshot_id=None,
                            )
                            logger.info("Persisted exit trade cycle to Supabase for %s", c_pos.symbol)
                        else:
                            logger.info("Position for %s is already closed in DB. Skipping duplicate exit persistence.", c_pos.symbol)
                    except Exception as e:
                        logger.error("Failed to persist exit trade cycle to Supabase for %s: %s. Reverting position to OPEN in memory for retry.", c_pos.symbol, e)
                        self.execution_adapter.revert_position_to_open(c_pos.position_id)
                        cycle_results["closed_positions"] -= 1

        # 2. Check research snapshot for new trade entries (strictly scoped to active_date)
        snapshot: ResearchSnapshot | None = None
        try:
            snapshot = (
                load_latest_snapshot("pre_market", trading_date=active_date)
                or load_latest_snapshot(trading_date=active_date)
            )
        except Exception as e:
            logger.warning("Could not query research snapshot from DB: %s", e)

        # Reject missing research snapshots — only trade on active_date research
        if not snapshot:
            logger.warning("No research snapshot available for session date %s. Suspending new entries.", active_date)
            cycle_results["status"] = "SUSPENDED"
            cycle_results["reason"] = "MISSING_RESEARCH_SNAPSHOT"
            return cycle_results

        # Research gating policy for new entries
        allowed_symbols: list[str] = []
        fresh = is_snapshot_fresh(snapshot)
        date_match = (snapshot.trading_date == str(active_date))
        logger.info(
            "Found snapshot id=%s outlook=%s fresh=%s date_match=%s tradeable=%s",
            snapshot.snapshot_id, snapshot.market_outlook, fresh, date_match, snapshot.is_tradeable_session,
        )

        # Reject stale snapshots — do not trade on outdated research
        if not fresh:
            logger.warning(
                "Research snapshot %s is stale (created_at=%s). Suspending new entries.",
                snapshot.snapshot_id, snapshot.created_at.isoformat(),
            )
            cycle_results["status"] = "SUSPENDED"
            cycle_results["reason"] = "STALE_SNAPSHOT"
            return cycle_results

        # Reject wrong-date snapshots — snapshot must match today's trading date
        if not date_match:
            logger.warning(
                "Research snapshot %s is for date %s, not today's session %s. Suspending new entries.",
                snapshot.snapshot_id, snapshot.trading_date, active_date,
            )
            cycle_results["status"] = "SUSPENDED"
            cycle_results["reason"] = "SNAPSHOT_DATE_MISMATCH"
            return cycle_results

        if not snapshot.is_tradeable_session:
            logger.info("Snapshot specifies non-tradeable session (%s). Skipping new entries.", snapshot.no_trade_reason)
            cycle_results["status"] = "SKIPPED"
            cycle_results["reason"] = snapshot.no_trade_reason
            return cycle_results

        if snapshot.market_outlook == "HIGH_RISK":
            logger.info("Research outlook is HIGH_RISK. New trade entries suspended for safety.")
            cycle_results["status"] = "SUSPENDED"
            cycle_results["reason"] = "HIGH_RISK_OUTLOOK"
            return cycle_results

        # Candidate selection from watchlist (ranked) then allowed_symbols fallback
        if snapshot.watchlist:
            allowed_symbols = [w["symbol"] for w in snapshot.watchlist if "symbol" in w][:5]
        elif snapshot.allowed_symbols:
            allowed_symbols = snapshot.allowed_symbols[:5]

        if not allowed_symbols:
            logger.warning("Snapshot %s has no watchlist or allowed_symbols. Suspending new entries.", snapshot.snapshot_id)
            cycle_results["status"] = "SUSPENDED"
            cycle_results["reason"] = "EMPTY_WATCHLIST"
            return cycle_results

        logger.info("Evaluation candidates (%d): %s", len(allowed_symbols), allowed_symbols)
        cycle_results["evaluated"] = len(allowed_symbols)

        # 3. Window for 5-minute candles
        session_start = datetime.datetime.combine(active_date, datetime.time(9, 15), tzinfo=IST)
        session_end = datetime.datetime.combine(active_date, datetime.time(15, 30), tzinfo=IST)

        # 4. Evaluate candidates for entries
        for symbol in allowed_symbols:
            # Idempotency check: in-memory cache OR Supabase-backed persistent check
            if symbol in self.traded_symbols_today:
                logger.debug("Symbol %s already traded today (in-memory). Skipping for idempotency.", symbol)
                continue

            if self.conn and self.account_id:
                try:
                    if is_symbol_traded_today(self.conn, self.account_id, symbol, active_date):
                        logger.info("Symbol %s already traded today in Supabase. Skipping for idempotency.", symbol)
                        self.traded_symbols_today.add(symbol)
                        continue
                except Exception as e:
                    logger.warning("Could not query Supabase idempotency for %s: %s", symbol, e)

            # Check persistent candle processing state
            last_ts = None
            if self.conn:
                try:
                    last_ts = get_last_processed_candle_ts(self.conn, symbol, active_date)
                except Exception as e:
                    logger.warning("Could not query last candle ts for %s: %s", symbol, e)

            try:
                signal, order = self.engine.process_symbol(
                    symbol=symbol,
                    nifty_symbol="NIFTY",
                    start=session_start,
                    end=session_end,
                    last_processed_ts=last_ts,
                    current_execution_time=current_time,
                )
                if signal:
                    cycle_results["signals"] += 1
                    logger.info("Signal generated for %s: %s @ %.2f", symbol, signal.direction.value, signal.entry_price)

                if order:
                    cycle_results["orders"] += 1
                    self.traded_symbols_today.add(symbol)
                    logger.info("Order executed for %s: qty=%d @ %.2f status=%s", symbol, order.quantity, order.price, order.status.value)

                    # Persist atomic trade reservation and trade cycle to Supabase
                    if self.conn and self.account_id:
                        try:
                            reserve_trade_slot(self.conn, self.account_id, symbol, active_date, self.worker_id)
                            leg_fees = TransactionCostModel.calculate_leg_costs(
                                quantity=order.quantity,
                                price=order.average_fill_price,
                                side=order.direction.value,
                            )
                            persist_trade_cycle(
                                conn=self.conn,
                                user_id=self.system_user_id,
                                account_id=self.account_id,
                                symbol=symbol,
                                direction=order.direction.value,
                                signal_price=signal.entry_price if signal else order.price,
                                fill_price=order.average_fill_price,
                                quantity=order.quantity,
                                fees=leg_fees,
                                research_snapshot_id=snapshot.snapshot_id if snapshot else None,
                            )
                            logger.info("Persisted trade cycle to Supabase for %s", symbol)
                        except Exception as e:
                            logger.error("Failed to persist trade cycle to Supabase: %s", e)

                # Persist candle checkpoint
                if self.conn and signal:
                    try:
                        save_last_processed_candle_ts(
                            self.conn,
                            symbol,
                            active_date,
                            signal.timestamp,
                            signal.signal_id if signal else None,
                        )
                    except Exception as e:
                        logger.warning("Failed to save last candle ts for %s: %s", symbol, e)

            except Exception as e:
                logger.error("Error evaluating symbol %s: %s", symbol, e)

        account = self.execution_adapter.get_account_state()
        logger.info("Cycle finished. Account equity=%.2f cash=%.2f positions=%d",
                    account.total_equity, account.cash_balance, len(self.execution_adapter.get_open_positions()))
        return cycle_results


def main():
    parser = argparse.ArgumentParser(description="Intraday Trading Worker")
    parser.add_argument("--run-once", action="store_true", help="Run a single evaluation cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously with 5-minute sleep intervals")
    parser.add_argument("--use-mock", action="store_true", help="Use MockMarketDataProvider instead of Angel One")
    parser.add_argument("--force-session", action="store_true", help="Bypass market-hours check (for testing)")
    args = parser.parse_args()

    worker = IntradayWorker(mode=TradingMode.PAPER, use_mock=args.use_mock)

    if args.run_once:
        now = datetime.datetime.now(IST)
        is_open, msg = worker.get_market_session_status(now)
        if not is_open and not args.force_session:
            logger.info("Session check: %s. Exiting cleanly.", msg)
            sys.exit(0)

        results = worker.run_cycle()
        logger.info("Run-once results: %s", results)
        sys.exit(0)

    elif args.loop:
        logger.info("Entering continuous loop mode (polling every 5 minutes)...")
        while True:
            now = datetime.datetime.now(IST)
            is_open, msg = worker.get_market_session_status(now)
            if is_open or args.force_session:
                try:
                    worker.run_cycle()
                except Exception as e:
                    logger.error("Cycle error: %s", e)
            else:
                logger.info("Market closed (%s). Sleeping...", msg)
            time.sleep(300)
    else:
        # Default behavior: run once
        worker.run_cycle()


if __name__ == "__main__":
    main()
