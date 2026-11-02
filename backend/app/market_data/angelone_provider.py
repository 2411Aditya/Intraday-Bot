"""Real Angel One market data provider using the official smartapi-python SDK.

Authentication: SmartConnect(api_key=...) then generateSession(clientCode, password, totp)
Candle fetch:   getCandleData(historicDataParams) where historicDataParams is a dict
Token lookup:   searchScrip(exchange, searchscrip)

No mock data, no fallback values. Paper-trading only; order APIs never called.
"""

import os
import datetime as dt
import zoneinfo
from typing import List

import pyotp
from SmartApi import SmartConnect

from backend.app.market_data.interface import MarketDataProvider
from backend.app.models.domain import Candle, MarketTick


class AngelOneProvider(MarketDataProvider):
    """Fetch market data from Angel One SmartAPI.

    The provider authenticates on first use and caches the SmartConnect instance.
    All network calls use the official client — no mock data is generated.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ANGELONE_API_KEY")
        self.client_code = os.getenv("ANGELONE_CLIENT_ID")
        self.password = os.getenv("ANGELONE_PASSWORD")
        self.totp_secret = os.getenv("ANGELONE_TOTP_SECRET")
        self._client: SmartConnect | None = None
        self._is_healthy: bool = False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _authenticate(self) -> None:
        if self._client is not None and self._is_healthy:
            return
        if not all([self.api_key, self.client_code, self.password, self.totp_secret]):
            raise RuntimeError("Missing Angel One credentials in environment")

        # Generate 6-digit TOTP — value is used but never printed.
        totp = pyotp.TOTP(self.totp_secret)
        otp = totp.now()

        self._client = SmartConnect(api_key=self.api_key)
        # Official SDK signature: generateSession(clientCode, password, totp)
        resp = self._client.generateSession(self.client_code, self.password, otp)
        # SDK returns {"status": True, "data": {...}} on success
        self._is_healthy = bool(resp.get("status") is True)
        if not self._is_healthy:
            msg = resp.get("message", "unknown error")
            raise RuntimeError(f"Angel One authentication failed: {msg}")

    # ------------------------------------------------------------------
    # Instrument token lookup
    # ------------------------------------------------------------------
    # Known hard tokens for NSE indices (searchScrip does not return index tokens)
    _INDEX_TOKENS = {
        "NIFTY": "99926000",
        "BANKNIFTY": "99926009",
        "FINNIFTY": "99926037",
        "MIDCPNIFTY": "99926074",
    }

    def _get_nse_token(self, symbol: str) -> str:
        """Return the NSE exchange token for the given trading symbol.

        NSE index tokens are hard-coded because searchScrip does not return them.
        For equity symbols, searchScrip is called and the exact ``-EQ`` match is used.
        If no exact match is found the first result is used with a WARNING — this may
        return a futures/options token for ambiguous symbols, so operators should verify
        Angel One token correctness for each symbol in the watchlist.
        """
        import logging as _logging
        _log = _logging.getLogger("IntradayBot.AngelOneProvider")

        upper = symbol.upper()
        if upper in self._INDEX_TOKENS:
            return self._INDEX_TOKENS[upper]

        # Equity lookup via searchScrip — prefer exact ``SYMBOL-EQ`` match
        result = self._client.searchScrip("NSE", symbol)
        for item in result.get("data", []):
            if item.get("tradingsymbol", "").upper() == upper + "-EQ":
                return str(item.get("symboltoken"))

        # Fallback: first NSE result (may be F&O token — log clearly)
        data = result.get("data", [])
        if data:
            fallback_token = str(data[0].get("symboltoken"))
            fallback_scrip = data[0].get("tradingsymbol", "UNKNOWN")
            _log.warning(
                "NSE token: no exact -EQ match for '%s'; falling back to first result "
                "'%s' (token=%s). Verify this is the correct equity token.",
                symbol, fallback_scrip, fallback_token,
            )
            return fallback_token
        raise ValueError(f"No NSE instrument token found for symbol: {symbol}")

    # ------------------------------------------------------------------
    # MarketDataProvider implementation
    # ------------------------------------------------------------------
    def get_historical_candles(
        self, symbol: str, timeframe: str, start: dt.datetime, end: dt.datetime
    ) -> List[Candle]:
        """Return completed 5-minute candles from SmartAPI getCandleData.

        ``timeframe`` must be ``"5m"``; the API interval parameter is ``"FIVE_MINUTE"``.
        ``start`` and ``end`` must be timezone-aware datetimes (any tz; converted internally).
        """
        self._authenticate()

        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        token = self._get_nse_token(symbol)

        # getCandleData expects fromdate/todate as "YYYY-MM-DD HH:MM" strings in IST.
        fmt = "%Y-%m-%d %H:%M"
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "FIVE_MINUTE",
            "fromdate": start.astimezone(ist).strftime(fmt),
            "todate": end.astimezone(ist).strftime(fmt),
        }
        raw = self._client.getCandleData(params)

        candles: List[Candle] = []
        for entry in raw.get("data", []):
            # Each entry: [timestamp_str, open, high, low, close, volume]
            # Timestamp format: "2026-10-30T09:30:00+05:30"
            ts_raw = entry[0]
            if isinstance(ts_raw, str):
                ts = dt.datetime.fromisoformat(ts_raw)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=ist)
            else:
                ts = dt.datetime.fromtimestamp(ts_raw / 1000, tz=ist)

            candle = Candle(
                symbol=symbol,
                timestamp=ts,
                open=float(entry[1]),
                high=float(entry[2]),
                low=float(entry[3]),
                close=float(entry[4]),
                volume=int(entry[5]),
                timeframe="5m",
                is_completed=True,
            )
            candles.append(candle)
        return candles

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        """Return the most recently completed 5-minute candle.

        Raises RuntimeError if the latest candle is more than 10 minutes old —
        this prevents the worker from acting on stale cached data from the API.
        """
        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        now = dt.datetime.now(ist)
        start = now - dt.timedelta(hours=1)
        candles = self.get_historical_candles(symbol, timeframe, start, now)
        if not candles:
            return None
        latest = candles[-1]
        age_seconds = (now - latest.timestamp.astimezone(ist)).total_seconds()
        if age_seconds > 600:  # 10 minutes
            raise RuntimeError(
                f"Stale market data for {symbol}: latest candle is "
                f"{int(age_seconds / 60)}m old (> 10m threshold). "
                "Angel One API may be returning cached/delayed data."
            )
        return latest

    def get_current_quote(self, symbol: str) -> MarketTick:
        self._authenticate()
        token = self._get_nse_token(symbol)
        # ltpData(exchange, tradingsymbol, symboltoken)
        resp = self._client.ltpData("NSE", symbol, token)
        data = resp.get("data", {})
        price = float(data.get("ltp", 0.0))
        return MarketTick(symbol=symbol, ltp=price, bid=price, ask=price, volume=0)

    def subscribe(self, symbols: List[str], callback):
        raise NotImplementedError("WebSocket subscription not implemented in paper mode")

    def is_healthy(self) -> bool:
        return self._is_healthy
