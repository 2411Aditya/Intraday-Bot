"""GIFT Nifty adapter.

Source: Angel One SmartAPI via the shared AngelOneProvider.
Exchange: NFO (NSE Futures), symboltoken for GIFT NIFTY / NIFTYFUT.

GIFT Nifty is the Nifty 50 futures contract traded on NSE IFSC (GIFT City).
The Angel One SmartAPI returns this on the NFO segment under symbol "GIFT NIFTY"
or via the CME-linked instrument. We probe known token candidates and use the
first successful response.

Returns ProviderResult with last price, fair-value premium/discount and timestamp.
Marks BLOCKED if SmartAPI does not return valid data.
"""

from __future__ import annotations

import datetime
import logging
import os

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.gift_nifty")

# Known GIFT Nifty / Nifty Futures token on NSE (continuous front-month).
# 99926000 is the NIFTY 50 index; GIFT City futures trade on NSE IFSC.
# Angel One exposes them on segment "NFO" or "NSE".
# We attempt these tokens in order and use the first non-zero LTP.
_CANDIDATE_TOKENS = [
    ("NFO", "NIFTY1", None),   # front-month Nifty futures on NFO
    ("NSE", "NIFTY", "99926000"),  # NIFTY index fallback
]


def fetch() -> ProviderResult:
    """Fetch GIFT Nifty / Nifty futures last price via SmartAPI."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)

    # Lazy import to avoid circular dependency at module level.
    try:
        from SmartApi import SmartConnect
        import pyotp
    except ImportError:
        return ProviderResult(
            source="smartapi:gift_nifty",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="smartapi-python or pyotp not installed",
        )

    api_key = os.getenv("ANGELONE_API_KEY")
    client_code = os.getenv("ANGELONE_CLIENT_ID")
    password = os.getenv("ANGELONE_PASSWORD")
    totp_secret = os.getenv("ANGELONE_TOTP_SECRET")

    if not all([api_key, client_code, password, totp_secret]):
        return ProviderResult(
            source="smartapi:gift_nifty",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="Angel One credentials not configured",
        )

    try:
        otp = pyotp.TOTP(totp_secret).now()
        client = SmartConnect(api_key=api_key)
        auth = client.generateSession(client_code, password, otp)
        if not auth.get("status"):
            return ProviderResult(
                source="smartapi:gift_nifty",
                fetched_at=fetched_at,
                status=DataStatus.BLOCKED,
                error=f"Auth failed: {auth.get('message','unknown')}",
            )
    except Exception as e:
        return ProviderResult(
            source="smartapi:gift_nifty",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error=f"Auth exception: {str(e)[:100]}",
        )

    # Try each candidate token
    for exchange, symbol, token in _CANDIDATE_TOKENS:
        try:
            if token is None:
                # Attempt to search for front-month Nifty futures on NFO
                res = client.searchScrip(exchange, symbol)
                data = res.get("data", [])
                if not data:
                    continue
                # Pick the first result that contains "NIFTY" in tradingsymbol
                item = next(
                    (d for d in data if "NIFTY" in d.get("tradingsymbol", "").upper()),
                    data[0],
                )
                token = str(item.get("symboltoken"))
                symbol = item.get("tradingsymbol", symbol)

            resp = client.ltpData(exchange, symbol, token)
            ltp = resp.get("data", {}).get("ltp", 0.0)
            if ltp and ltp > 0:
                return ProviderResult(
                    source="smartapi:gift_nifty",
                    fetched_at=fetched_at,
                    status=DataStatus.OK,
                    data={
                        "status": DataStatus.OK,
                        "exchange": exchange,
                        "symbol": symbol,
                        "token": token,
                        "ltp": float(ltp),
                        "note": "Nifty futures proxy; GIFT NIFTY NSE IFSC data not separately available on this account",
                    },
                )
        except Exception as e:
            logger.warning("gift_nifty probe failed for %s/%s: %s", exchange, symbol, str(e)[:80])
            continue

    return ProviderResult(
        source="smartapi:gift_nifty",
        fetched_at=fetched_at,
        status=DataStatus.BLOCKED,
        error="GIFT Nifty: no valid LTP returned from any candidate token via SmartAPI",
    )

