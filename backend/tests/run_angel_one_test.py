"""
Verification script — Angel One SmartAPI real data test.
- Trading day: 2026-10-30 (Friday) — confirmed by datetime.date(2026,10,30).weekday() == 4
- Window: 09:30–10:30 IST (covers up to 12 x 5-min candles)
- Prints: exit status, auth health, symbol token, candle count, first/last timestamps, OHLCV
- Does NOT print: API key, client code, password, TOTP, access token, refresh token
"""
import sys
import datetime
import zoneinfo
from pathlib import Path

# --- Load .env ---
try:
    from dotenv import load_dotenv
    load_dotenv(Path('.env'))
    print("[env] .env loaded")
except Exception as e:
    print(f"[env] dotenv not available: {e}")

sys.path.insert(0, str(Path('.').resolve()))

def run_test():
    # --- Confirm trading-day calendar ---
    test_date = datetime.date(2026, 10, 30)
    weekday_name = test_date.strftime('%A')
    print(f"[calendar] Test date: {test_date} ({weekday_name}, weekday={test_date.weekday()})")
    if test_date.weekday() >= 5:
        print("[calendar] ERROR: date is weekend — pick a weekday")
        sys.exit(1)

    # --- Import provider ---
    from backend.app.market_data.angelone_provider import AngelOneProvider
    print("[import] AngelOneProvider imported successfully")

    provider = AngelOneProvider()

    # --- Step 1: Authenticate ---
    print("\n[auth] Attempting generateSession...")
    try:
        provider._authenticate()
        print(f"[auth] is_healthy = {provider._is_healthy}")
    except Exception as e:
        # Sanitize: never print tokens or passwords
        msg = str(e)
        if len(msg) > 200:
            msg = msg[:200] + "..."
        print(f"[auth] FAILED: {msg}")
        sys.exit(1)

    # --- Step 2: Token lookup ---
    symbol = "NIFTY"
    print(f"\n[token] Resolving NSE instrument token for {symbol}...")
    try:
        token = provider._get_nse_token(symbol)
        print(f"[token] symboltoken = {token}")
    except Exception as e:
        print(f"[token] FAILED: {e}")
        sys.exit(1)

    # --- Step 3: Historical candle fetch ---
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    start = datetime.datetime(2026, 10, 30, 9, 30, tzinfo=ist)
    end = datetime.datetime(2026, 10, 30, 10, 30, tzinfo=ist)
    print(f"\n[candles] Fetching 5-min candles {start.isoformat()} to {end.isoformat()}")

    try:
        candles = provider.get_historical_candles(symbol, "5m", start, end)
    except Exception as e:
        print(f"[candles] FAILED: {e}")
        sys.exit(1)

    print(f"[candles] Count: {len(candles)}")
    if candles:
        c0, cN = candles[0], candles[-1]
        print(f"[candles] First: {c0.timestamp.isoformat()}  O={c0.open} H={c0.high} L={c0.low} C={c0.close} V={c0.volume}")
        print(f"[candles] Last:  {cN.timestamp.isoformat()}  O={cN.open} H={cN.high} L={cN.low} C={cN.close} V={cN.volume}")

        # OHLCV consistency check
        errors = []
        for c in candles:
            if not (c.high >= c.open and c.high >= c.close and c.high >= c.low):
                errors.append(f"OHLCV high error at {c.timestamp}")
            if not (c.low <= c.open and c.low <= c.close and c.low <= c.high):
                errors.append(f"OHLCV low error at {c.timestamp}")
            h = c.timestamp.astimezone(ist)
            if not (datetime.time(9, 15) <= h.time() <= datetime.time(15, 30)):
                errors.append(f"Timestamp outside market hours: {c.timestamp}")
        if errors:
            print(f"[validation] FAIL — {len(errors)} consistency errors:")
            for e in errors[:5]:
                print(f"  {e}")
        else:
            print("[validation] All candles pass OHLCV and market-hours checks")
    else:
        print("[candles] WARNING: 0 candles returned — market may have been closed or token is wrong")

    print("\n[done] Exit 0")

if __name__ == '__main__':
    run_test()
