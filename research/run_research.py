"""CLI runner for automated research jobs (overnight, pre_market, post_market).

Portable across GitHub Actions, cron, and future Linux VPS.

Usage:
    python research/run_research.py --session overnight
    python research/run_research.py --session pre_market
    python research/run_research.py --session post_market
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
import zoneinfo
from pathlib import Path

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
except Exception:
    pass

sys.path.insert(0, str(Path(".").resolve()))

from research.engine import ResearchEngine, _is_trading_day
from research.models import ResearchSnapshot
from research.persistence import save_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_research")


def main():
    parser = argparse.ArgumentParser(description="Automated Market Research Runner")
    parser.add_argument(
        "--session",
        choices=["overnight", "pre_market", "post_market"],
        default="pre_market",
        help="Research session type",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even on holidays or weekends",
    )
    args = parser.parse_args()

    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    if args.session == "overnight" and now_ist.hour >= 20:
        trading_date = (now_ist.date() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        trading_date = now_ist.strftime("%Y-%m-%d")

    logger.info("Starting research job session=%s trading_date=%s IST=%s", args.session, trading_date, now_ist.isoformat())

    is_trading, no_trade_reason = _is_trading_day(trading_date)
    if not is_trading and not args.force:
        logger.info("Non-trading day detected (%s).", no_trade_reason)
        if args.session == "pre_market":
            logger.info("Pre-market research skipped on non-trading day.")
            # Record a non-tradeable snapshot to document the day
            snap = ResearchSnapshot(
                session_type=args.session,
                trading_date=trading_date,
                market_outlook="HIGH_RISK",
                risk_warnings=[f"NO_TRADE: {no_trade_reason}"],
                is_tradeable_session=False,
                no_trade_reason=no_trade_reason,
            )
            try:
                save_snapshot(snap)
            except Exception as e:
                logger.warning("Could not save non-trading snapshot: %s", e)
            return

    engine = ResearchEngine()
    snapshot = engine.run(session_type=args.session)

    try:
        save_snapshot(snapshot)
        logger.info("Snapshot successfully saved to Supabase (id=%s, outlook=%s)", snapshot.snapshot_id, snapshot.market_outlook)
    except Exception as e:
        logger.error("Failed to persist research snapshot to Supabase: %s", e)
        # We don't fail the job hard if DB is temporarily unreachable, but log error
        sys.exit(1)

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESEARCH SUMMARY: {snapshot.session_type.upper()} ({snapshot.trading_date})")
    print(f"Outlook: {snapshot.market_outlook}")
    print(f"Tradeable Session: {snapshot.is_tradeable_session}")
    if snapshot.no_trade_reason:
        print(f"Reason: {snapshot.no_trade_reason}")
    print(f"Allowed Symbols: {len(snapshot.allowed_symbols)}")
    print(f"Watchlist Top 5: {[w['symbol'] for w in snapshot.watchlist[:5]]}")
    if snapshot.risk_warnings:
        print(f"Risk Warnings ({len(snapshot.risk_warnings)}):")
        for w in snapshot.risk_warnings[:3]:
            print(f"  - {w}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

