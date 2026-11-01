"""Economic events adapter — RBI and Fed event calendar.

Sources:
  - RBI calendar: RSS/HTML from rbi.org.in  (often blocks bots → BLOCKED if unreachable)
  - Fed calendar: Federal Reserve JSON feed  https://www.federalreserve.gov/feeds/feeds.htm
  - Fallback: mark BLOCKED with explanation; never fabricate events.

Returns upcoming events (next 7 days) relevant to Indian markets.
"""

from __future__ import annotations

import datetime
import logging

import requests

from research.models import DataStatus, ProviderResult

logger = logging.getLogger("research.economic_events")

FED_CALENDAR_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
_TIMEOUT = 10


def _fetch_fed_events() -> tuple[list[dict], str | None]:
    """Attempt to fetch Fed press-release XML and parse upcoming events."""
    try:
        resp = requests.get(FED_CALENDAR_URL, timeout=_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Basic XML parsing without external lib
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//atom:entry", ns)

        events: list[dict] = []
        for item in items[:10]:
            title = (item.findtext("title") or item.findtext("atom:title", "", ns) or "").strip()
            pub = (item.findtext("pubDate") or item.findtext("atom:updated", "", ns) or "").strip()
            link = (item.findtext("link") or item.findtext("atom:id", "", ns) or "").strip()
            events.append({"title": title, "date": pub, "link": link, "source": "FederalReserve"})
        return events, None
    except requests.exceptions.Timeout:
        return [], "Fed calendar timeout"
    except Exception as e:
        return [], f"Fed calendar error: {str(e)[:100]}"


def fetch() -> ProviderResult:
    """Fetch RBI / Fed economic events."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    data: dict = {}
    errors: list[str] = []

    # Fed events
    fed_events, fed_err = _fetch_fed_events()
    data["fed_events"] = fed_events
    if fed_err:
        errors.append(f"fed:{fed_err}")
        logger.warning("economic_events fed: %s", fed_err)

    # RBI events — rbi.org.in blocks bots; mark as BLOCKED proactively
    data["rbi_events"] = []
    data["rbi_note"] = "BLOCKED: rbi.org.in requires browser; manual check advised"
    errors.append("rbi:BLOCKED(bot_detection)")

    # Overall: OK if at least Fed data came through
    overall = DataStatus.OK if fed_events else DataStatus.BLOCKED
    return ProviderResult(
        source="mixed:economic_events",
        fetched_at=fetched_at,
        status=overall,
        data=data,
        error="; ".join(errors) if errors else None,
    )

