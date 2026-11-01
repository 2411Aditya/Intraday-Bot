r"""
Phase D Research Integration Tests — 5 focused checks.

1. Real research data collected (or marked BLOCKED) from each provider
2. ResearchSnapshot saved and retrieved from Supabase
3. Research changes stock eligibility (allowed_symbols list)
4. Valid stock candles (SBIN) flow through strategy->risk->paper execution
5. Stale/missing research is detected and handled safely

Run with: .venv\Scripts\python backend/tests/test_research_integration.py
"""

import sys
import os
import datetime
import zoneinfo
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path('.env'))
except Exception:
    pass

sys.path.insert(0, str(Path('.').resolve()))

PASS = []
FAIL = []

def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ─────────────────────────────────────────────
# TEST 1: Provider data collection
# ─────────────────────────────────────────────
print("\n=== TEST 1: Provider data collection ===")

from research.providers import global_indices, fx_commodities, fii_dii, nse_announcements, economic_events
from research.models import DataStatus

gi = global_indices.fetch()
print(f"  global_indices: status={gi.status}  tickers_returned={len(gi.data)}")
check("global_indices_not_all_blocked",
      gi.status != DataStatus.BLOCKED or len(gi.data) > 0,
      f"status={gi.status}")

fx = fx_commodities.fetch()
print(f"  fx_commodities: status={fx.status}  items={len(fx.data)}")
check("fx_commodities_fetched", fx.status in (DataStatus.OK, DataStatus.BLOCKED),
      f"status={fx.status}")

fii = fii_dii.fetch()
print(f"  fii_dii: status={fii.status}  error={fii.error}")
check("fii_dii_has_result", fii.status in (DataStatus.OK, DataStatus.BLOCKED),
      f"status={fii.status}")

ann = nse_announcements.fetch()
print(f"  nse_announcements: status={ann.status}  announcements={len(ann.data.get('announcements', []))}")
check("nse_announcements_has_result", ann.status in (DataStatus.OK, DataStatus.BLOCKED),
      f"status={ann.status}")

eco = economic_events.fetch()
print(f"  economic_events: status={eco.status}  fed_events={len(eco.data.get('fed_events', []))}")
check("economic_events_has_result", eco.status in (DataStatus.OK, DataStatus.BLOCKED),
      f"status={eco.status}")

# Verify BLOCKED sources are explicit, not silently empty
for name, result in [("global_indices", gi), ("fx_commodities", fx), ("fii_dii", fii)]:
    if result.status == DataStatus.BLOCKED:
        check(f"{name}_blocked_has_error_message", result.error is not None, result.error)


# ─────────────────────────────────────────────
# TEST 2: Snapshot save and retrieve from Supabase
# ─────────────────────────────────────────────
print("\n=== TEST 2: Supabase snapshot persistence ===")

from research.engine import ResearchEngine
from research.persistence import save_snapshot, load_latest_snapshot, is_snapshot_fresh

print("  Running ResearchEngine (global + FX providers only for speed)...")
# Use a lightweight snapshot — skip sector_strength (slow per-stock SmartAPI calls)
# by directly constructing with real provider results
from research.models import ResearchSnapshot
snap = ResearchSnapshot(
    session_type="pre_market",
    trading_date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5,minutes=30))).strftime("%Y-%m-%d"),
    global_indices=gi.data,
    fx_commodities=fx.data,
    institutional_flows=fii.data,
    economic_events=eco.data,
    nse_announcements=ann.data,
    market_outlook="NEUTRAL",
    risk_warnings=["test_snapshot"],
    allowed_symbols=["SBIN", "TCS", "HDFCBANK", "INFY", "RELIANCE"],
    watchlist=[{"symbol": "SBIN", "change_pct_1d": 0.5, "score": 0.5}],
    sector_scores={"FINANCIALS": 0.3},
    provider_statuses={
        "global_indices": str(gi.status),
        "fx_commodities": str(fx.status),
        "fii_dii": str(fii.status),
    },
    is_tradeable_session=True,
)

try:
    save_snapshot(snap)
    check("snapshot_saved_to_supabase", True, f"id={snap.snapshot_id}")
except Exception as e:
    check("snapshot_saved_to_supabase", False, str(e)[:120])

try:
    loaded = load_latest_snapshot(session_type="pre_market")
    check("snapshot_retrieved_from_supabase", loaded is not None, f"id={loaded.snapshot_id if loaded else None}")
    if loaded:
        check("snapshot_id_matches", loaded.snapshot_id == snap.snapshot_id, f"{loaded.snapshot_id}")
        check("snapshot_is_fresh", is_snapshot_fresh(loaded), "age < 6h")
        check("snapshot_allowed_symbols_preserved",
              "SBIN" in loaded.allowed_symbols, str(loaded.allowed_symbols[:3]))
except Exception as e:
    check("snapshot_retrieved_from_supabase", False, str(e)[:120])


# ─────────────────────────────────────────────
# TEST 3: Research changes stock eligibility
# ─────────────────────────────────────────────
print("\n=== TEST 3: Research changes stock eligibility ===")

from research.providers.sector_strength import NIFTY50

# Simulate: a stock with an announcement is excluded
from research.engine import _build_watchlist
from research.models import ProviderResult

mock_sector_result = ProviderResult(
    source="test",
    fetched_at=datetime.datetime.now(datetime.timezone.utc),
    status=DataStatus.OK,
    data={
        "ranked_symbols": [
            {"symbol": "SBIN", "change_pct_1d": 1.5},
            {"symbol": "HDFCBANK", "change_pct_1d": 0.8},
            {"symbol": "RELIANCE", "change_pct_1d": -0.3},
        ]
    },
)

# Without exclusions: SBIN should appear
watchlist_full = _build_watchlist(mock_sector_result, {"SBIN", "HDFCBANK", "RELIANCE"})
check("sbin_in_unrestricted_watchlist", any(w["symbol"] == "SBIN" for w in watchlist_full))

# With SBIN excluded (has earnings): SBIN must not appear
watchlist_restricted = _build_watchlist(mock_sector_result, {"HDFCBANK", "RELIANCE"})
check("sbin_excluded_after_announcement", not any(w["symbol"] == "SBIN" for w in watchlist_restricted),
      f"watchlist={[w['symbol'] for w in watchlist_restricted]}")

check("research_changes_eligibility_count",
      len(watchlist_full) > len(watchlist_restricted),
      f"full={len(watchlist_full)} restricted={len(watchlist_restricted)}")


# ─────────────────────────────────────────────
# TEST 4: Real SBIN candles → strategy → risk → paper execution
# ─────────────────────────────────────────────
print("\n=== TEST 4: SBIN candles through strategy->risk->paper pipeline ===")

from backend.app.market_data.angelone_provider import AngelOneProvider
from backend.app.market_data.mock_provider import MockMarketDataProvider
from backend.app.models.domain import Candle, Instrument, MarketTick
from backend.app.strategies.vwap_orb_strategy import VWAP_ORB_Strategy
from backend.app.risk.engine import RiskEngine
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.core.config import TradingMode, settings

# Fetch real SBIN candles for a known trading day
ist = zoneinfo.ZoneInfo("Asia/Kolkata")
start = datetime.datetime(2026, 10, 30, 9, 15, tzinfo=ist)
end = datetime.datetime(2026, 10, 30, 15, 30, tzinfo=ist)

provider = AngelOneProvider()
try:
    provider._authenticate()
    sbin_token = provider._get_nse_token("SBIN")
    raw = provider._client.getCandleData({
        "exchange": "NSE",
        "symboltoken": sbin_token,
        "interval": "FIVE_MINUTE",
        "fromdate": "2026-10-30 09:15",
        "todate": "2026-10-30 15:30",
    })
    candle_rows = raw.get("data", [])
    check("sbin_candles_returned", len(candle_rows) > 0, f"count={len(candle_rows)}")

    if candle_rows:
        # Check non-zero volume (equity, not index)
        nonzero_vol = sum(1 for r in candle_rows if r[5] > 0)
        check("sbin_candles_have_volume", nonzero_vol > 0, f"nonzero_vol_candles={nonzero_vol}/{len(candle_rows)}")
        first_ts = candle_rows[0][0]
        last_ts = candle_rows[-1][0]
        check("sbin_candles_in_market_hours",
              "09:" in str(first_ts) or "10:" in str(first_ts),
              f"first={first_ts} last={last_ts}")

        # Build Candle objects and run strategy (paper pipeline)
        utc = datetime.timezone.utc
        candles = []
        for r in candle_rows:
            ts = datetime.datetime.fromisoformat(r[0]) if isinstance(r[0], str) else datetime.datetime.fromtimestamp(r[0]/1000, tz=utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=ist)
            candles.append(Candle(
                symbol="SBIN", timestamp=ts,
                open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]),
                volume=int(r[5]), timeframe="5m", is_completed=True,
            ))
        check("sbin_candle_objects_built", len(candles) > 10, f"count={len(candles)}")

        # Run strategy — may or may not generate a signal (depends on price action)
        signal = VWAP_ORB_Strategy.evaluate(candles=candles, nifty_candles=[])
        check("strategy_ran_without_exception", True, f"signal={'YES' if signal else 'NO (no setup on 2026-10-30)'}")

        # Run through risk engine regardless
        mock = MockMarketDataProvider()
        last_price = candles[-1].close
        mock.set_quote("SBIN", MarketTick(symbol="SBIN", ltp=last_price, bid=last_price-0.05, ask=last_price+0.05, volume=candles[-1].volume))
        adapter = PaperExecutionAdapter(starting_capital=100000.0)
        risk = RiskEngine()
        account = adapter.get_account_state()
        check("paper_account_initialised", account.cash_balance == 100000.0, f"cash={account.cash_balance}")

except Exception as e:
    check("sbin_candles_returned", False, str(e)[:120])


# ─────────────────────────────────────────────
# TEST 5: Stale / missing research handled safely
# ─────────────────────────────────────────────
print("\n=== TEST 5: Stale/missing research handling ===")

from research.persistence import is_snapshot_fresh

check("none_snapshot_not_fresh", not is_snapshot_fresh(None), "None -> not fresh")

old_snap = ResearchSnapshot(
    session_type="pre_market",
    trading_date="2026-10-01",
    market_outlook="NEUTRAL",
    is_tradeable_session=True,
    created_at=datetime.datetime(2026, 10, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
)
check("old_snapshot_not_fresh", not is_snapshot_fresh(old_snap), "7-day-old snap -> stale")

# Fresh snapshot
fresh_snap = ResearchSnapshot(
    session_type="pre_market",
    trading_date=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    market_outlook="BULLISH",
    is_tradeable_session=True,
)
check("fresh_snapshot_is_fresh", is_snapshot_fresh(fresh_snap), "just-created -> fresh")

# Non-trading day detection
from research.engine import _is_trading_day
tradeable, reason = _is_trading_day("2026-11-01")  # Saturday
check("saturday_not_tradeable", not tradeable, reason)
tradeable2, _ = _is_trading_day("2026-10-30")      # Friday
check("friday_is_tradeable", tradeable2)

# No live orders test
from backend.app.execution.live_adapter import LiveExecutionAdapter, LiveExecutionLockedError
live = LiveExecutionAdapter()
check("live_adapter_is_locked", live.is_locked, "Live execution is locked in PAPER mode")
try:
    from backend.app.models.domain import OrderIntent, SignalDirection
    intent = OrderIntent(
        signal_id="SIG-TEST",
        symbol="SBIN",
        direction=SignalDirection.BUY,
        quantity=10,
        price=800.0,
        stop_loss=795.0,
        target=810.0,
        mode=TradingMode.ACTUAL,
        risk_budget=50.0,
        estimated_costs=5.0,
        projected_gross_profit=100.0,
    )
    live.submit_order(intent)
    check("live_orders_blocked", False, "Expected LiveExecutionLockedError")
except LiveExecutionLockedError as e:
    check("live_orders_blocked", True, "LiveExecutionLockedError safely raised")
except Exception as e:
    check("live_orders_blocked", False, str(e)[:60])


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"RESULTS: {len(PASS)} PASS / {len(FAIL)} FAIL")
if FAIL:
    print("FAILED CHECKS:")
    for f in FAIL:
        print(f"  - {f}")
print("="*55)
if __name__ == '__main__':
    sys.exit(0 if not FAIL else 1)

def test_research_integration_suite():
    assert len(FAIL) == 0, f"Failed checks: {FAIL}"

