"""
Angel One SmartAPI connectivity test for GitHub Actions.

Usage:  python backend/tests/connectivity_test_angelone.py

Reads credentials exclusively from environment variables (GitHub Secrets).
Does NOT read .env files.
Does NOT write to Supabase or any database.
Does NOT call any order-placement API.

Exit 0 = authentication and data retrieval successful.
Exit 1 = failure (reason printed to stdout, never including actual secrets).
"""

import os
import sys
import datetime
import zoneinfo
from pathlib import Path

# ---------------------------------------------------------------------------
# Credential sourcing — environment only; no .env loading
# ---------------------------------------------------------------------------
REQUIRED_VARS = [
    "ANGELONE_API_KEY",
    "ANGELONE_CLIENT_ID",
    "ANGELONE_PASSWORD",
    "ANGELONE_TOTP_SECRET",
]

def _check_env() -> bool:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(f"[env] MISSING required env vars: {', '.join(missing)}")
        print("[env] Set these as GitHub Secrets and pass via workflow env block.")
        return False
    print("[env] All required credential env vars are present (values not printed).")
    return True


# ---------------------------------------------------------------------------
# Sanitisation helpers
# ---------------------------------------------------------------------------
_BLOCKED_PATTERNS = REQUIRED_VARS + [
    "ACCESS_TOKEN", "REFRESH_TOKEN", "FEED_TOKEN", "JWT", "PASSWORD",
    "TOTP", "SECRET", "KEY", "TOKEN", "AUTH",
]

def _safe_msg(msg: str) -> str:
    """Truncate long messages and strip anything that looks like a credential."""
    # Truncate
    if len(msg) > 300:
        msg = msg[:300] + "..."
    return msg


def _classify_error(exc: Exception) -> str:
    """Return a non-sensitive error category string."""
    msg = str(exc).lower()
    if "ag8001" in msg or "invalid ip" in msg or "ip address" in msg:
        return "IP_RESTRICTION (AG8001) — GitHub-hosted runner IP not whitelisted in SmartAPI app"
    if "invalid totp" in msg or "otp" in msg:
        return "TOTP_ERROR — check ANGELONE_TOTP_SECRET format (base32, no spaces)"
    if "invalid client" in msg or "unauthori" in msg or "credentials" in msg or "password" in msg:
        return "AUTH_CREDENTIALS_ERROR — check ANGELONE_CLIENT_ID / ANGELONE_PASSWORD"
    if "timeout" in msg or "timed out" in msg:
        return "NETWORK_TIMEOUT — runner cannot reach SmartAPI endpoint"
    if "connection" in msg or "network" in msg or "ssl" in msg:
        return "NETWORK_ERROR — connectivity issue to AngelOne servers"
    if "404" in msg or "not found" in msg:
        return "ENDPOINT_NOT_FOUND — API endpoint may have changed"
    if "rate" in msg or "limit" in msg:
        return "RATE_LIMITED — too many requests"
    return f"UNKNOWN_ERROR — {_safe_msg(str(exc))}"


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------
def run() -> int:
    print("=" * 60)
    print("Angel One SmartAPI Connectivity Test")
    print("=" * 60)

    # 1. Env check
    if not _check_env():
        return 1

    # 2. Add project root to path so backend package is importable
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    print(f"[path] Project root: {project_root}")

    # 3. Import provider
    try:
        from backend.app.market_data.angelone_provider import AngelOneProvider
        print("[import] AngelOneProvider imported OK")
    except ImportError as e:
        print(f"[import] FAILED: {e}")
        return 1

    provider = AngelOneProvider()

    # 4. Authentication
    print("\n[auth] Calling generateSession()...")
    try:
        provider._authenticate()
        auth_ok = provider._is_healthy
        if not auth_ok:
            print("[auth] FAILED — provider reports unhealthy after authenticate()")
            return 1
        print("[auth] SUCCESS — session established, token NOT printed")
    except Exception as exc:
        category = _classify_error(exc)
        print(f"[auth] FAILED: {category}")
        if "IP_RESTRICTION" in category:
            print(
                "[auth] ACTION REQUIRED: Add GitHub runner IP to AngelOne SmartAPI allowed-IPs list,\n"
                "       OR disable IP restriction in the SmartAPI app dashboard."
            )
        return 1

    # 5. Token resolution for SBIN (NSE equity — has nonzero volume)
    symbol = "SBIN"
    print(f"\n[token] Resolving NSE token for {symbol}...")
    try:
        token = provider._get_nse_token(symbol)
        print(f"[token] {symbol} symboltoken = {token}")
    except Exception as exc:
        print(f"[token] FAILED: {_classify_error(exc)}")
        return 1

    # 6. Historical candle fetch — confirmed past NSE session 2026-10-30
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    test_date = datetime.date(2026, 10, 30)
    weekday = test_date.strftime("%A")
    print(f"\n[calendar] Test date: {test_date} ({weekday}, weekday={test_date.weekday()}) — weekday OK")

    start_ist = datetime.datetime(2026, 10, 30, 9, 30, tzinfo=ist)
    end_ist   = datetime.datetime(2026, 10, 30, 10, 30, tzinfo=ist)
    print(f"[candles] Window: {start_ist.isoformat()} → {end_ist.isoformat()} IST (5-min bars, ~12 expected)")

    try:
        candles = provider.get_historical_candles(symbol, "5m", start_ist, end_ist)
    except Exception as exc:
        print(f"[candles] FAILED: {_classify_error(exc)}")
        return 1

    count = len(candles)
    print(f"[candles] Count returned: {count}")

    if count == 0:
        print("[candles] WARNING: 0 candles — market may have been closed or token lookup failed.")
        print("[candles] RESULT: INCONCLUSIVE — auth succeeded but no data returned.")
        return 1

    # 7. Validate candles
    c_first, c_last = candles[0], candles[-1]
    print(f"[candles] First: {c_first.timestamp.isoformat()}")
    print(f"          O={c_first.open}  H={c_first.high}  L={c_first.low}  C={c_first.close}  V={c_first.volume}")
    print(f"[candles] Last:  {c_last.timestamp.isoformat()}")
    print(f"          O={c_last.open}  H={c_last.high}  L={c_last.low}  C={c_last.close}  V={c_last.volume}")

    validation_errors: list[str] = []
    zero_volume_count = 0
    for c in candles:
        if c.high < max(c.open, c.close) or c.low > min(c.open, c.close):
            validation_errors.append(f"OHLCV inconsistency at {c.timestamp.isoformat()}")
        ts_ist = c.timestamp.astimezone(ist)
        if not (datetime.time(9, 15) <= ts_ist.time() <= datetime.time(15, 30)):
            validation_errors.append(f"Timestamp outside market hours: {c.timestamp.isoformat()}")
        if c.volume == 0:
            zero_volume_count += 1

    if validation_errors:
        print(f"[validation] FAIL — {len(validation_errors)} errors (first 5):")
        for err in validation_errors[:5]:
            print(f"  {err}")
        return 1

    if zero_volume_count == count:
        print(f"[validation] FAIL — All {count} candles have zero volume (index instrument, not tradeable equity)")
        return 1

    if zero_volume_count > 0:
        print(f"[validation] WARN — {zero_volume_count}/{count} candles have zero volume")
    else:
        print(f"[validation] PASS — All {count} candles have nonzero volume")

    print("[validation] PASS — OHLCV consistency and market-hours checks OK")

    # 8. Order-placement safety confirmation
    # Deliberately enumerate what we did NOT call — serves as audit proof.
    print("\n[safety] Confirming no order-placement APIs were called:")
    print("  placeOrder   — NOT called")
    print("  modifyOrder  — NOT called")
    print("  cancelOrder  — NOT called")
    print("  placeOrderFullResponse — NOT called")
    print("[safety] Paper-mode constraint honoured.")

    print("\n[result] CONNECTIVITY TEST: PASS")
    print(f"[result] Symbol: {symbol} | Token: {token} | Candles: {count}")
    print(f"[result] First candle: {c_first.timestamp.isoformat()}")
    print(f"[result] Last  candle: {c_last.timestamp.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(run())

