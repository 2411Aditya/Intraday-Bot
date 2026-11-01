"""Global indices adapter — S&P 500, Nasdaq, Asian markets.

Source: yfinance (free, no auth required).
Tickers: ^GSPC (S&P 500), ^IXIC (Nasdaq), ^N225 (Nikkei), ^HSI (Hang Seng),
         ^STI (Straits Times), ^KS11 (KOSPI), ^AXJO (ASX 200).

Returns ProviderResult with latest close, % change and 52-week range.
Marks individual tickers BLOCKED when yfinance returns no data.
"""

from __future__ import annotations

import datetime
import logging

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.global_indices")

TICKERS = {
    "SP500":   "^GSPC",
    "NASDAQ":  "^IXIC",
    "NIKKEI":  "^N225",
    "HANGSENG":"^HSI",
    "KOSPI":   "^KS11",
    "ASX200":  "^AXJO",
}


def fetch() -> ProviderResult:
    """Fetch latest close and 1-day change for all global index tickers."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        import yfinance as yf
    except ImportError:
        return ProviderResult(
            source="yfinance:global_indices",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="yfinance not installed",
        )

    results: dict = {}
    errors: list[str] = []

    for name, ticker in TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=True)
            if hist.empty or len(hist) < 2:
                results[name] = {"status": DataStatus.BLOCKED, "reason": "no_data"}
                errors.append(f"{name}:no_data")
                continue
            latest = hist.iloc[-1]
            prev = hist.iloc[-2]
            close = round(float(latest["Close"]), 2)
            prev_close = round(float(prev["Close"]), 2)
            chg_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            ts = hist.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            results[name] = {
                "ticker": ticker,
                "close": close,
                "prev_close": prev_close,
                "change_pct": chg_pct,
                "timestamp": str(ts),
                "status": DataStatus.OK,
            }
        except Exception as e:
            msg = str(e)[:120]
            results[name] = {"status": DataStatus.BLOCKED, "reason": msg}
            errors.append(f"{name}:{msg}")
            logger.warning("global_indices fetch error for %s: %s", name, msg)

    overall = DataStatus.OK if not errors else (
        DataStatus.BLOCKED if len(errors) == len(TICKERS) else DataStatus.OK
    )
    return ProviderResult(
        source="yfinance:global_indices",
        fetched_at=fetched_at,
        status=overall,
        data=results,
        error="; ".join(errors) if errors else None,
    )

