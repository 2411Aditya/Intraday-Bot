"""System health and connectivity diagnostics for Intraday-Bot."""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import zoneinfo
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def run_diagnostics() -> dict:
    results = {}
    now_ist = datetime.datetime.now(IST)

    # 1. Timing & Exchange Session
    from research.engine import _is_trading_day
    date_str = now_ist.strftime("%Y-%m-%d")
    is_trading, reason = _is_trading_day(date_str)
    mkt_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    mkt_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    sq_off = now_ist.replace(hour=15, minute=15, second=0, microsecond=0)

    is_open = is_trading and (mkt_open <= now_ist <= mkt_close)
    if not is_trading:
        phase = f"NON_TRADING_DAY ({reason})"
    elif now_ist < mkt_open:
        phase = "PRE_MARKET (Before 09:15 IST)"
    elif now_ist >= sq_off and now_ist <= mkt_close:
        phase = "SQUARE_OFF_WINDOW (15:15 - 15:30 IST)"
    elif now_ist > mkt_close:
        phase = "POST_MARKET (After 15:30 IST)"
    else:
        phase = "REGULAR_TRADING_HOURS (09:15 - 15:15 IST)"

    results["ist_time"] = now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    results["trading_day"] = "YES" if is_trading else f"NO ({reason})"
    results["session_status"] = "OPEN" if is_open else "CLOSED"
    results["session_phase"] = phase

    # 2. Database Connectivity & Ledger Balance
    db_url = os.getenv("SUPABASE_DB_URL")
    user_id = os.getenv("BOT_USER_ID", "00000000-0000-0000-0000-000000000002")
    if not db_url:
        results["db_status"] = "ERROR: SUPABASE_DB_URL missing"
        results["paper_cash"] = 0.0
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=8)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cash_balance FROM trading_accounts WHERE user_id = %s AND mode = 'paper' LIMIT 1;",
                    (user_id,),
                )
                row = cur.fetchone()
                results["paper_cash"] = float(row[0]) if row else 10000.0
                results["db_status"] = f"CONNECTED (Paper Cash: ₹{results['paper_cash']:,.2f})"

                # Latest worker heartbeat in worker_candle_state
                cur.execute(
                    "SELECT symbol, last_processed_candle_ts, updated_at FROM worker_candle_state ORDER BY updated_at DESC LIMIT 1;"
                )
                hb_row = cur.fetchone()
                if hb_row:
                    sym, candle_ts, updated_at = hb_row
                    results["last_heartbeat"] = f"{sym} @ {updated_at.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S IST')}"
                else:
                    results["last_heartbeat"] = "None recorded yet"
            conn.close()
        except Exception as e:
            results["db_status"] = f"FAILED: {e}"
            results["paper_cash"] = 0.0
            results["last_heartbeat"] = "N/A"

    # 3. Angel One Credentials & TOTP Token
    totp_secret = os.getenv("ANGELONE_TOTP_SECRET")
    client_id = os.getenv("ANGELONE_CLIENT_ID")
    if not client_id:
        results["angelone_status"] = "FAILED: ANGELONE_CLIENT_ID missing"
    elif not totp_secret:
        results["angelone_status"] = "FAILED: ANGELONE_TOTP_SECRET missing"
    else:
        try:
            import pyotp
            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()
            if len(otp) == 6 and otp.isdigit():
                results["angelone_status"] = f"READY (Client: ...{client_id[-4:]}, TOTP Active)"
            else:
                results["angelone_status"] = "FAILED: Invalid TOTP output"
        except Exception as e:
            results["angelone_status"] = f"FAILED: {e}"

    return results


if __name__ == "__main__":
    diag = run_diagnostics()
    for k, v in diag.items():
        print(f"{k.upper()}={v}")
