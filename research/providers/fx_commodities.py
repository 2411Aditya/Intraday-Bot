"""FX, crude oil and volatility indicators adapter.

Sources:
  USD/INR  → yfinance ticker "USDINR=X"
  Crude Oil (WTI) → yfinance ticker "CL=F"
  Brent Crude → yfinance ticker "BZ=F"
  India VIX  → yfinance ticker "^INDIAVIX"  (may be unavailable; falls back to BLOCKED)
  VIX (CBOE) → yfinance ticker "^VIX"
"""

from __future__ import annotations

import datetime
import logging

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.fx_commodities")

TICKERS = {
    "USDINR":    "USDINR=X",
    "WTI_CRUDE": "CL=F",
    "BRENT":     "BZ=F",
    "INDIA_VIX": "^INDIAVIX",
    "CBOE_VIX":  "^VIX",
}


def fetch() -> ProviderResult:
    """Fetch latest FX, crude oil and volatility data."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        import yfinance as yf
    except ImportError:
        return ProviderResult(
            source="yfinance:fx_commodities",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="yfinance not installed",
        )

    results: dict = {}
    errors: list[str] = []

    for name, ticker in TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=True)
            if hist.empty:
                results[name] = {"status": DataStatus.BLOCKED, "reason": "no_data"}
                errors.append(f"{name}:no_data")
                continue
            latest = hist.iloc[-1]
            close = round(float(latest["Close"]), 4)
            chg_pct = 0.0
            if len(hist) >= 2:
                prev = float(hist.iloc[-2]["Close"])
                chg_pct = round((close - prev) / prev * 100, 2) if prev else 0.0
            results[name] = {
                "ticker": ticker,
                "close": close,
                "change_pct": chg_pct,
                "timestamp": str(hist.index[-1]),
                "status": DataStatus.OK,
            }
        except Exception as e:
            msg = str(e)[:120]
            results[name] = {"status": DataStatus.BLOCKED, "reason": msg}
            errors.append(f"{name}:{msg}")
            logger.warning("fx_commodities fetch error for %s: %s", name, msg)

    overall = DataStatus.BLOCKED if len(errors) == len(TICKERS) else DataStatus.OK
    return ProviderResult(
        source="yfinance:fx_commodities",
        fetched_at=fetched_at,
        status=overall,
        data=results,
        error="; ".join(errors) if errors else None,
    )

