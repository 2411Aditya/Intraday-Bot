"""Pre-flight check for Windows local automated trading system.

Validates environment, trading day, Supabase connectivity, and Angel One API readiness.
Never prints credentials, secrets, or passwords.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import zoneinfo
from pathlib import Path

# Setup paths
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preflight")

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def check_preflight() -> bool:
    all_ok = True
    now_ist = datetime.datetime.now(IST)
    logger.info("Starting Pre-Flight Sanity Checks (Time: %s IST)", now_ist.strftime("%Y-%m-%d %H:%M:%S"))

    # 1. Trading Mode & Safety Guardrails
    trading_mode = os.getenv("TRADING_MODE", "").lower()
    live_enabled = os.getenv("LIVE_TRADING_ENABLED", "").lower()
    bot_user_id = os.getenv("BOT_USER_ID", "")

    if live_enabled == "true" or trading_mode == "live":
        logger.error("[FAIL] Live trading is enabled in environment! Hard lock triggered.")
        return False

    if trading_mode != "paper":
        logger.error("[FAIL] TRADING_MODE is '%s', expected 'paper'", trading_mode)
        all_ok = False
    else:
        logger.info("[OK] Trading mode verified as PAPER (Live trading disabled)")

    if not bot_user_id:
        logger.warning("[WARN] BOT_USER_ID not set, will default to clean paper account")
    else:
        logger.info("[OK] Target Bot User ID configured: ...%s", bot_user_id[-8:])

    # 2. Exchange Trading Day & Holiday Verification
    from research.engine import _is_trading_day
    date_str = now_ist.strftime("%Y-%m-%d")
    is_trading, reason = _is_trading_day(date_str)
    if is_trading:
        logger.info("[OK] Today (%s) is an active NSE trading day", date_str)
    else:
        logger.info("[INFO] Today (%s) is a non-trading day: %s", date_str, reason)

    # 3. Supabase Database Connectivity Check
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        logger.error("[FAIL] SUPABASE_DB_URL missing in environment")
        all_ok = False
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=10)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            conn.close()
            logger.info("[OK] Supabase PostgreSQL connectivity verified (SELECT 1 OK)")
        except Exception as e:
            logger.error("[FAIL] Supabase connection failed: %s", e)
            all_ok = False

    # 4. Angel One API Credentials Presence
    angel_key = os.getenv("ANGELONE_API_KEY")
    angel_client = os.getenv("ANGELONE_CLIENT_ID")
    angel_pwd = os.getenv("ANGELONE_PASSWORD")
    angel_totp = os.getenv("ANGELONE_TOTP_SECRET")

    if not all([angel_key, angel_client, angel_pwd, angel_totp]):
        logger.error("[FAIL] Missing Angel One credentials in .env")
        all_ok = False
    else:
        logger.info("[OK] Angel One credentials present in environment")
        # Lightweight TOTP validation without logging secrets
        try:
            import pyotp
            totp = pyotp.TOTP(angel_totp)
            code = totp.now()
            if len(code) == 6 and code.isdigit():
                logger.info("[OK] TOTP generator verified (6-digit code produced)")
            else:
                logger.error("[FAIL] TOTP generation produced invalid token format")
                all_ok = False
        except Exception as e:
            logger.error("[FAIL] TOTP secret validation failed: %s", e)
            all_ok = False

    # 5. Disk Space & Memory Sanity Check
    try:
        import shutil
        total, used, free = shutil.disk_usage(repo_root)
        free_gb = free // (2**30)
        logger.info("[OK] Available disk space: %d GB", free_gb)
        if free_gb < 5:
            logger.warning("[WARN] Low disk space (< 5 GB remaining)")
    except Exception:
        pass

    logger.info("Pre-Flight Status: %s", "PASSED" if all_ok else "FAILED")
    return all_ok


if __name__ == "__main__":
    success = check_preflight()
    sys.exit(0 if success else 1)
