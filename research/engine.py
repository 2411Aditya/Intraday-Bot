"""Research Engine — aggregates provider results into a ResearchSnapshot.

Usage:
    engine = ResearchEngine()
    snapshot = engine.run(session_type="pre_market")
    # snapshot is a ResearchSnapshot ready to persist to Supabase
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from research.models import DataStatus, ProviderResult, ResearchSnapshot
from research.providers import (
    economic_events,
    fii_dii,
    fx_commodities,
    gift_nifty,
    global_indices,
    nse_announcements,
    sector_strength,
)

logger = logging.getLogger("research.engine")

# NSE holiday list for 2026 — add/update annually (IST dates as YYYY-MM-DD strings)
NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-25",  # Holi
    "2026-04-02",  # Ram Navami
    "2026-04-14",  # Dr. Ambedkar Jayanti / Mahavir Jayanti
    "2026-04-17",  # Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-20",  # Diwali Laxmi Pujan
    "2026-11-04",  # Diwali Balipratipada
    "2026-11-25",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
}


def _is_trading_day(date_str: str) -> tuple[bool, str | None]:
    """Return (is_trading_day, reason_if_not)."""
    d = datetime.date.fromisoformat(date_str)
    if d.weekday() >= 5:
        return False, f"{d.strftime('%A')} is a weekend — NSE closed"
    if date_str in NSE_HOLIDAYS_2026:
        return False, f"{date_str} is an NSE holiday"
    return True, None


def _derive_outlook(
    global_data: dict,
    fx_data: dict,
    fii_data: dict,
    sector_data: dict,
    gift_data: dict,
) -> tuple[str, list[str]]:
    """Derive market outlook string and risk warnings from aggregated data."""
    warnings: list[str] = []
    bull_signals = 0
    bear_signals = 0

    # 1. US markets
    sp500 = global_data.get("SP500", {})
    if sp500.get("status") == DataStatus.OK:
        chg = sp500.get("change_pct", 0.0)
        if chg > 0.5:
            bull_signals += 1
        elif chg < -0.5:
            bear_signals += 1
            if chg < -1.5:
                warnings.append(f"SP500 fell {chg}% overnight — caution")

    nasdaq = global_data.get("NASDAQ", {})
    if nasdaq.get("status") == DataStatus.OK:
        chg = nasdaq.get("change_pct", 0.0)
        if chg > 0.5:
            bull_signals += 1
        elif chg < -0.5:
            bear_signals += 1

    # 2. GIFT Nifty
    if gift_data.get("status") == DataStatus.OK:
        pass  # premium/discount analysis could be added later

    # 3. USD/INR (INR weakness → bearish for equities)
    usdinr = fx_data.get("USDINR", {})
    if usdinr.get("status") == DataStatus.OK:
        chg = usdinr.get("change_pct", 0.0)
        if chg > 0.3:
            bear_signals += 1
            warnings.append(f"INR weakening by {chg}% — watch for FII outflows")
        elif chg < -0.3:
            bull_signals += 1

    # 4. Crude oil
    crude = fx_data.get("WTI_CRUDE", {})
    if crude.get("status") == DataStatus.OK:
        chg = crude.get("change_pct", 0.0)
        if chg > 2.0:
            bear_signals += 1
            warnings.append(f"Crude +{chg}% — inflation / CAD risk")

    # 5. VIX
    vix = fx_data.get("CBOE_VIX", {})
    if vix.get("status") == DataStatus.OK:
        vix_val = vix.get("close", 0.0)
        if vix_val > 25:
            bear_signals += 2
            warnings.append(f"CBOE VIX={vix_val} — elevated volatility, reduce position size")
        elif vix_val > 20:
            warnings.append(f"CBOE VIX={vix_val} — moderate volatility")

    # 6. FII flows
    fii_net = fii_data.get("fii_net_buy_sell")
    if fii_net is not None:
        try:
            val = float(str(fii_net).replace(",", ""))
            if val > 0:
                bull_signals += 1
            elif val < -500:
                bear_signals += 1
                warnings.append(f"FII net sell {val} Cr — watch for market pressure")
        except ValueError:
            pass

    # Final outlook
    # HIGH_RISK: Elevated downside pressure (>=2 bear signals) or conflicting macro crosswinds
    if bear_signals >= 2 and bull_signals >= 2:
        warnings.append(f"Conflicting macro signals (bull={bull_signals}, bear={bear_signals}) — high volatility risk")
        return "HIGH_RISK", warnings
    if bear_signals >= 2:
        return "HIGH_RISK", warnings
    if bull_signals >= 3:
        return "BULLISH", warnings
    if bear_signals == 1 and bull_signals == 0:
        return "NEUTRAL", warnings
    return "NEUTRAL", warnings


def _build_watchlist(
    sector_result: ProviderResult,
    allowed_set: set[str],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Build ranked watchlist from sector_strength provider output."""
    ranked = sector_result.data.get("ranked_symbols", [])
    watchlist = []
    for item in ranked:
        sym = item.get("symbol", "")
        if sym in allowed_set:
            watchlist.append({
                "symbol": sym,
                "change_pct_1d": item.get("change_pct_1d"),
                "score": item.get("change_pct_1d", 0.0),  # simple 1d-return score
            })
        if len(watchlist) >= top_n:
            break
    return watchlist


class ResearchEngine:
    """Orchestrates all data-source adapters and builds a ResearchSnapshot."""

    def run(self, session_type: str = "pre_market") -> ResearchSnapshot:
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        trading_date = datetime.datetime.now(ist).strftime("%Y-%m-%d")
        is_trading, no_trade_reason = _is_trading_day(trading_date)

        logger.info("ResearchEngine.run session=%s date=%s tradeable=%s", session_type, trading_date, is_trading)

        # Run all providers (always, even on non-trading days for overnight research)
        logger.info("Fetching global indices...")
        gi_result = global_indices.fetch()

        logger.info("Fetching FX and commodities...")
        fx_result = fx_commodities.fetch()

        logger.info("Fetching FII/DII flows...")
        fii_result = fii_dii.fetch()

        logger.info("Fetching NSE announcements...")
        ann_result = nse_announcements.fetch()

        logger.info("Fetching economic events...")
        eco_result = economic_events.fetch()

        logger.info("Fetching GIFT Nifty...")
        gift_result = gift_nifty.fetch()

        logger.info("Fetching sector strength (slow — SmartAPI per-stock)...")
        sec_result = sector_strength.fetch()

        # Derive outlook
        outlook, risk_warnings = _derive_outlook(
            global_data=gi_result.data,
            fx_data=fx_result.data,
            fii_data=fii_result.data,
            sector_data=sec_result.data,
            gift_data=gift_result.data,
        )

        if not is_trading:
            risk_warnings.insert(0, f"NO_TRADE: {no_trade_reason}")
            outlook = "HIGH_RISK"

        # Allowed symbols — use full Nifty 50 minus any with announcements that day
        ann_symbols: set[str] = set()
        for a in ann_result.data.get("announcements", []):
            sym = a.get("symbol", "")
            if sym:
                ann_symbols.add(sym.upper())
        earnings_symbols: set[str] = set()
        for r in ann_result.data.get("earnings", []):
            sym = r.get("symbol", "")
            if sym:
                earnings_symbols.add(sym.upper())

        from research.providers.sector_strength import NIFTY50
        excluded = ann_symbols | earnings_symbols
        allowed = [s for s in NIFTY50 if s not in excluded]
        if excluded:
            risk_warnings.append(f"Excluded {len(excluded)} stocks with announcements/results: {sorted(excluded)[:5]}...")

        # Build watchlist
        watchlist = _build_watchlist(sec_result, set(allowed), top_n=10)

        # Sector scores
        sector_scores = sec_result.data.get("sector_scores", {})

        # Provider statuses for provenance
        provider_statuses = {
            "global_indices": gi_result.status,
            "fx_commodities": fx_result.status,
            "fii_dii": fii_result.status,
            "nse_announcements": ann_result.status,
            "economic_events": eco_result.status,
            "gift_nifty": gift_result.status,
            "sector_strength": sec_result.status,
        }

        snapshot = ResearchSnapshot(
            session_type=session_type,
            trading_date=trading_date,
            global_indices=gi_result.data,
            gift_nifty=gift_result.data,
            fx_commodities=fx_result.data,
            institutional_flows=fii_result.data,
            economic_events=eco_result.data,
            nse_announcements=ann_result.data,
            market_outlook=outlook,
            risk_warnings=risk_warnings,
            allowed_symbols=allowed,
            watchlist=watchlist,
            sector_scores=sector_scores,
            provider_statuses={k: str(v) for k, v in provider_statuses.items()},
            is_tradeable_session=is_trading,
            no_trade_reason=no_trade_reason,
        )
        logger.info("ResearchEngine.run complete. outlook=%s allowed_symbols=%d watchlist=%d",
                    outlook, len(allowed), len(watchlist))
        return snapshot

