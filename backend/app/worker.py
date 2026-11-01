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
    get_db_connection,
    get_last_processed_candle_ts,
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

    def __init__(self, mode: TradingMode = TradingMode.PAPER, use_mock: bool = False):
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
        self.system_user_id = os.getenv("BOT_USER_ID", "00000000-0000-0000-0000-000000000001")
        try:
            self.conn = get_db_connection()
            self.account_id = ensure_trading_account(
                self.conn,
                self.system_user_id,
                mode=self.mode.value.lower(),
                starting_capital=settings.VIRTUAL_STARTING_CAPITAL,
            )
            logger.info("Connected to Supabase. Account ID: %s", self.account_id)
        except Exception as e:
            logger.warning("Supabase connection not initialized for worker: %s", e)

        # Idempotency cache: tracks symbols traded today (in-memory fast cache backed by DB)
        self.traded_symbols_today: set[str] = set()

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

    def run_cycle(self, session_date: datetime.date | None = None) -> dict:
        """Run a single evaluation cycle across candidate stocks."""
        now_ist = datetime.datetime.now(IST)
        active_date = session_date or now_ist.date()

        logger.info("--- Starting Intraday Evaluation Cycle (date=%s, time=%s IST) ---", active_date, now_ist.strftime("%H:%M:%S"))

        # 1. Check research snapshot
        snapshot: ResearchSnapshot | None = None
        try:
            snapshot = load_latest_snapshot("pre_market") or load_latest_snapshot()
        except Exception as e:
            logger.warning("Could not query research snapshot from DB: %s", e)

        # Research gating policy
        allowed_symbols: list[str] = []
        if snapshot:
            fresh = is_snapshot_fresh(snapshot)
            logger.info("Found snapshot id=%s outlook=%s fresh=%s tradeable=%s",
                        snapshot.snapshot_id, snapshot.market_outlook, fresh, snapshot.is_tradeable_session)
            if not snapshot.is_tradeable_session:
                logger.info("Snapshot specifies non-tradeable session (%s). Skipping.", snapshot.no_trade_reason)
                return {"status": "SKIPPED", "reason": snapshot.no_trade_reason}

            if snapshot.market_outlook == "HIGH_RISK":
                logger.info("Research outlook is HIGH_RISK. New trade entries suspended for safety.")
                return {"status": "SUSPENDED", "reason": "HIGH_RISK_OUTLOOK"}

            # Candidate selection from watchlist
            if snapshot.watchlist:
                allowed_symbols = [w["symbol"] for w in snapshot.watchlist if "symbol" in w][:5]
            elif snapshot.allowed_symbols:
                allowed_symbols = snapshot.allowed_symbols[:5]
        else:
            logger.info("No research snapshot available. Falling back to default high-liquidity universe.")
            allowed_symbols = ["SBIN", "TCS", "HDFCBANK", "INFY", "RELIANCE"]

        logger.info("Evaluation candidates (%d): %s", len(allowed_symbols), allowed_symbols)

        # 2. Window for 5-minute candles
        session_start = datetime.datetime.combine(active_date, datetime.time(9, 15), tzinfo=IST)
        session_end = datetime.datetime.combine(active_date, datetime.time(15, 30), tzinfo=IST)

        cycle_results = {
            "evaluated": len(allowed_symbols),
            "signals": 0,
            "orders": 0,
            "closed_positions": 0,
        }

        # 3. Monitor existing open positions first (exits take priority over entries)
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
