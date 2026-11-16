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


def _determine_trading_date(session: str, now: datetime.datetime) -> str:
    """Return the intended trading date (YYYY-MM-DD) for a given session.
    For overnight sessions the job is scheduled at 23:00 IST (17:30 UTC).
    The intended trading day is the next calendar day (Monday‑Friday).
    If the job runs after midnight but before 06:00 IST we still target the
    previous night’s session (i.e. the same calendar day as the intended session).
    """
    if session != "overnight":
        return now.strftime("%Y-%m-%d")
    # If we are running on or after the scheduled time (>=20:00 IST) we target tomorrow.
    if now.hour >= 20:
        target = now.date() + datetime.timedelta(days=1)
        return target.strftime("%Y-%m-%d")
    # If we are running early after midnight but before 06:00 IST, we assume the
    # intended session was the previous night, so keep today's date.
    if now.hour < 6:
        return now.strftime("%Y-%m-%d")
    # Otherwise (e.g., early evening before scheduled time) we target today.
    return now.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="Run research job for a specific session")
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
    parser.add_argument(
        "--catchup",
        action="store_true",
        help="Run morning catch-up for overnight session using latest available closing data",
    )
    args = parser.parse_args()

    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    # Determine trading date robustly for overnight sessions
    is_catchup = args.catchup or (args.session == "overnight" and now_ist.hour < 12)
    if is_catchup:
        trading_date = now_ist.strftime("%Y-%m-%d")
        logger.info(
            "[catchup] Overnight morning catch-up triggered at %s IST for trading date %s",
            now_ist.strftime("%H:%M:%S"), trading_date,
        )
    else:
        trading_date = _determine_trading_date(args.session, now_ist)

    logger.info(
        "Starting research job session=%s trading_date=%s IST=%s",
        args.session,
        trading_date,
        now_ist.isoformat(),
    )

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
    # Pass determined trading_date to engine if it supports it
    snapshot = engine.run(session_type=args.session, trading_date=trading_date)
    if is_catchup:
        snapshot.trading_date = trading_date
        snapshot.is_tradeable_session = False
        snapshot.risk_warnings.append(
            f"[MORNING CATCH-UP] Overnight macro research collected at {now_ist.strftime('%H:%M:%S')} IST on {trading_date}. "
            "Informational input for pre-market analysis; cannot authorize trade entries."
        )

    try:
        save_snapshot(snapshot)
        logger.info(
            "Snapshot successfully saved to Supabase (id=%s, outlook=%s)",
            snapshot.snapshot_id,
            snapshot.market_outlook,
        )
    except Exception as e:
        logger.error("Failed to persist research snapshot to Supabase: %s", e)
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
