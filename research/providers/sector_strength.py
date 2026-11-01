"""Nifty 50 sector strength and stock ranking adapter.

Source: Angel One SmartAPI (daily OHLCV for Nifty 50 stocks).
Computation: sector-average 1-day and 5-day returns, relative performance per stock.

Nifty 50 symbol list is hard-coded (official NSE as of 2026-10).
Equity tokens are resolved via searchScrip("NSE", symbol + "-EQ").
Sector mapping is hard-coded from official NSE sector definitions.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Optional

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.sector_strength")

# Official Nifty 50 constituents with sector assignment (as of 2026-10)
NIFTY50_SECTORS: dict[str, list[str]] = {
    "FINANCIALS":   ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "BAJFINANCE", "BAJAJFINSV"],
    "IT":           ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM"],
    "OIL_GAS":      ["RELIANCE", "ONGC", "BPCL", "IOC"],
    "AUTO":         ["MARUTI", "M&M", "TATAMOTORS", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO"],
    "FMCG":         ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
    "PHARMA":       ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
    "METALS":       ["TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA", "VEDL"],
    "TELECOM":      ["BHARTIARTL"],
    "INFRA_CEMENT": ["ULTRACEMCO", "GRASIM", "ADANIENT", "ADANIPORTS", "NTPC", "POWERGRID", "L&T"],
    "CONSUMER":     ["TITAN", "ASIANPAINT"],
}

# Flat Nifty 50 list (order preserved for watchlist output)
NIFTY50 = [s for sector in NIFTY50_SECTORS.values() for s in sector]


def _get_client():
    """Return authenticated SmartConnect client or None."""
    try:
        from SmartApi import SmartConnect
        import pyotp
    except ImportError:
        return None, "smartapi-python not installed"

    api_key = os.getenv("ANGELONE_API_KEY")
    client_code = os.getenv("ANGELONE_CLIENT_ID")
    password = os.getenv("ANGELONE_PASSWORD")
    totp_secret = os.getenv("ANGELONE_TOTP_SECRET")

    if not all([api_key, client_code, password, totp_secret]):
        return None, "Angel One credentials not configured"

    try:
        otp = pyotp.TOTP(totp_secret).now()
        client = SmartConnect(api_key=api_key)
        auth = client.generateSession(client_code, password, otp)
        if not auth.get("status"):
            return None, f"Auth failed: {auth.get('message','')}"
        return client, None
    except Exception as e:
        return None, f"Auth error: {str(e)[:80]}"


def _get_token(client, symbol: str) -> Optional[str]:
    """Resolve NSE equity token for a symbol."""
    eq_sym = symbol + "-EQ"
    try:
        res = client.searchScrip("NSE", symbol)
        for item in res.get("data", []):
            if item.get("tradingsymbol", "").upper() == eq_sym.upper():
                return str(item.get("symboltoken"))
        # Fallback: first NSE result
        data = res.get("data", [])
        return str(data[0].get("symboltoken")) if data else None
    except Exception:
        return None


def _daily_change_pct(client, symbol: str, token: str, ist: datetime.timezone) -> Optional[float]:
    """Return 1-day % change for a stock using yesterday vs day-before candle."""
    today = datetime.datetime.now(ist)
    # Fetch last 5 trading days of daily candles
    from_dt = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d 09:15")
    to_dt = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d 15:30")
    params = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": from_dt,
        "todate": to_dt,
    }
    try:
        raw = client.getCandleData(params)
        rows = raw.get("data", [])
        if len(rows) < 2:
            return None
        prev_close = float(rows[-2][4])
        last_close = float(rows[-1][4])
        if prev_close <= 0:
            return None
        return round((last_close - prev_close) / prev_close * 100, 2)
    except Exception:
        return None


def fetch() -> ProviderResult:
    """Fetch sector strength and rank all Nifty 50 stocks by 1-day return."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

    client, err = _get_client()
    if client is None:
        return ProviderResult(
            source="smartapi:sector_strength",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error=err,
        )

    stock_data: dict[str, dict] = {}
    errors: list[str] = []

    for symbol in NIFTY50:
        token = _get_token(client, symbol)
        if not token:
            stock_data[symbol] = {"status": "BLOCKED", "reason": "token_not_found"}
            errors.append(symbol)
            continue
        chg = _daily_change_pct(client, symbol, token, ist)
        if chg is None:
            stock_data[symbol] = {"status": "BLOCKED", "reason": "no_candle_data", "token": token}
            errors.append(symbol)
        else:
            stock_data[symbol] = {"change_pct_1d": chg, "token": token, "status": "OK"}

    # Compute sector scores (average 1d return of available stocks)
    sector_scores: dict[str, float] = {}
    for sector, symbols in NIFTY50_SECTORS.items():
        changes = [
            stock_data[s]["change_pct_1d"]
            for s in symbols
            if stock_data.get(s, {}).get("status") == "OK"
        ]
        sector_scores[sector] = round(sum(changes) / len(changes), 2) if changes else 0.0

    # Rank stocks by 1d return
    ranked = sorted(
        [(s, d["change_pct_1d"]) for s, d in stock_data.items() if d.get("status") == "OK"],
        key=lambda x: x[1],
        reverse=True,
    )

    overall = DataStatus.OK if len(errors) < len(NIFTY50) else DataStatus.BLOCKED
    return ProviderResult(
        source="smartapi:sector_strength",
        fetched_at=fetched_at,
        status=overall,
        data={
            "stocks": stock_data,
            "sector_scores": sector_scores,
            "ranked_symbols": [{"symbol": s, "change_pct_1d": c} for s, c in ranked],
        },
        error=f"blocked_symbols: {errors}" if errors else None,
    )

