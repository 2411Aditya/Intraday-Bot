"""FII/DII institutional flows adapter.

Source: NSE public API (no auth required).
Endpoint: https://www.nseindia.com/api/fiidiiTradeReact

NSE blocks headless requests without browser-like headers. We use a
session with Accept and User-Agent headers that mimic a browser. If NSE
returns a non-200 or the JSON schema changes, the provider returns BLOCKED.

Data: FII/DII net buy/sell for the most recent trading day.
"""

from __future__ import annotations

import datetime
import logging

import requests

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.fii_dii")

NSE_FII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
NSE_BASE_URL = "https://www.nseindia.com"

_SESSION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/market-data/fii-dii-trade-data",
    "DNT": "1",
}

_TIMEOUT = 10  # seconds


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_SESSION_HEADERS)
    # Warm up the session with a base page hit so NSE sets cookies
    try:
        s.get(NSE_BASE_URL, timeout=_TIMEOUT)
    except Exception:
        pass
    return s


def fetch() -> ProviderResult:
    """Fetch latest FII/DII net flow data from NSE public API."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        session = _make_session()
        resp = session.get(NSE_FII_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout:
        return ProviderResult(
            source="nse:fii_dii",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="NSE FII/DII API timeout",
        )
    except requests.exceptions.HTTPError as e:
        return ProviderResult(
            source="nse:fii_dii",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error=f"NSE FII/DII HTTP {e.response.status_code}",
        )
    except Exception as e:
        return ProviderResult(
            source="nse:fii_dii",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error=f"NSE FII/DII error: {str(e)[:120]}",
        )

    # NSE returns a list of dicts; we look for the most recent date entry.
    if not isinstance(payload, list) or not payload:
        return ProviderResult(
            source="nse:fii_dii",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error="Unexpected NSE FII/DII response format",
        )

    try:
        # Fields vary; pick the latest row
        row = payload[0]
        data = {
            "date": row.get("date", ""),
            "fii_net_buy_sell": row.get("fiiBuySell", {}).get("net", None),
            "dii_net_buy_sell": row.get("diiBuySell", {}).get("net", None),
            "raw": row,
        }
    except Exception as e:
        return ProviderResult(
            source="nse:fii_dii",
            fetched_at=fetched_at,
            status=DataStatus.BLOCKED,
            error=f"FII/DII parse error: {str(e)[:100]}",
        )

    return ProviderResult(
        source="nse:fii_dii",
        fetched_at=fetched_at,
        status=DataStatus.OK,
        data=data,
    )

