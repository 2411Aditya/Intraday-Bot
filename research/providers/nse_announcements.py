"""NSE corporate announcements, earnings and news adapter.

Source: NSE public JSON API (no auth required).
Endpoints:
  Corporate announcements: https://www.nseindia.com/api/corporate-announcements?index=equities
  Corporate results (earnings): https://www.nseindia.com/api/corporates-pit?index=equities&from_date=...&to_date=...

Returns recent announcements for Nifty 50 constituents (last 2 trading days).
"""

from __future__ import annotations

import datetime
import logging

import requests

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.nse_announcements")

NSE_BASE = "https://www.nseindia.com"
NSE_ANNOUNCEMENTS_URL = f"{NSE_BASE}/api/corporate-announcements?index=equities"
NSE_RESULTS_URL = f"{NSE_BASE}/api/corporates-pit?index=equities"
_TIMEOUT = 12

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/corporate-announcements",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    try:
        s.get(NSE_BASE, timeout=_TIMEOUT)
    except Exception:
        pass
    return s


def _safe_get(session: requests.Session, url: str) -> tuple[bool, list | dict | None, str]:
    try:
        r = session.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        return True, r.json(), ""
    except requests.exceptions.HTTPError as e:
        return False, None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return False, None, str(e)[:100]


def fetch() -> ProviderResult:
    """Fetch NSE corporate announcements and results."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    session = _session()
    data: dict = {}
    errors: list[str] = []

    # 1. Announcements
    ok, ann_payload, err = _safe_get(session, NSE_ANNOUNCEMENTS_URL)
    if ok and isinstance(ann_payload, list):
        # Keep last 30 items for Nifty universe
        data["announcements"] = ann_payload[:30]
        data["announcements_count"] = len(ann_payload)
    else:
        data["announcements"] = []
        errors.append(f"announcements:{err}")
        logger.warning("nse_announcements: %s", err)

    # 2. Earnings results
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    today_ist = datetime.datetime.now(ist)
    from_dt = (today_ist - datetime.timedelta(days=3)).strftime("%d-%m-%Y")
    to_dt = today_ist.strftime("%d-%m-%Y")
    results_url = f"{NSE_RESULTS_URL}&from_date={from_dt}&to_date={to_dt}"
    ok2, res_payload, err2 = _safe_get(session, results_url)
    if ok2 and isinstance(res_payload, (list, dict)):
        rows = res_payload if isinstance(res_payload, list) else res_payload.get("data", [])
        data["earnings"] = rows[:20]
        data["earnings_count"] = len(rows)
    else:
        data["earnings"] = []
        errors.append(f"earnings:{err2}")
        logger.warning("nse_announcements earnings: %s", err2)

    status = DataStatus.BLOCKED if len(errors) == 2 else DataStatus.OK
    return ProviderResult(
        source="nse:announcements",
        fetched_at=fetched_at,
        status=status,
        data=data,
        error="; ".join(errors) if errors else None,
    )

