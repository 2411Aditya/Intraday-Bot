"""Unit Tests for Dynamic Stock Screening Engine."""

from datetime import datetime, timedelta
import zoneinfo
from backend.app.models.domain import Candle, Instrument, MarketTick
from backend.app.screening.screener import DynamicStockScreener


def test_screener_valid_stock():
    """Verify that liquid blue-chip stock with good ATR passes screening."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    base_dt = datetime(2026, 10, 29, 15, 30, tzinfo=ist)

    # 10 daily candles with 2M volume and 2% ATR
    candles = []
    for i in range(10):
        dt = base_dt - timedelta(days=10 - i)
        p = 800.0 + (i * 2.0)
        candles.append(
            Candle(
                symbol="SBIN",
                timestamp=dt,
                open=p,
                high=p + 16.0,  # ~2% range
                low=p - 2.0,
                close=p + 14.0,
                volume=2_500_000,
                timeframe="1d",
            )
        )

    inst = Instrument(symbol="SBIN", token="3045")
    quote = MarketTick(symbol="SBIN", ltp=820.0, bid=819.95, ask=820.05, volume=2500000)

    res = DynamicStockScreener.evaluate_candidate(
        instrument=inst,
        daily_candles=candles,
        quote=quote,
        account_capital=25000.0,
    )
    assert res.passed is True
    assert res.composite_score > 60.0
    assert len(res.rejection_reasons) == 0


def test_screener_rejects_illiquid_stock():
    """Verify that stock with volume below threshold is rejected."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    base_dt = datetime(2026, 10, 29, 15, 30, tzinfo=ist)

    candles = [
        Candle(
            symbol="LOWVOL",
            timestamp=base_dt - timedelta(days=i),
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=50_000,  # Below 1M threshold
            timeframe="1d",
        )
        for i in range(5)
    ]
    inst = Instrument(symbol="LOWVOL", token="9999")
    quote = MarketTick(symbol="LOWVOL", ltp=101.0, bid=100.5, ask=101.5, volume=50000)

    res = DynamicStockScreener.evaluate_candidate(inst, candles, quote, account_capital=10000.0)
    assert res.passed is False
    assert any("LOW_AVERAGE_VOLUME" in r for r in res.rejection_reasons)


def test_screener_capital_affordability():
    """Verify that expensive stock (e.g. ₹5,000) is rejected for micro ₹3,000 account."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    base_dt = datetime(2026, 10, 29, 15, 30, tzinfo=ist)

    candles = [
        Candle(
            symbol="BAJAJFIN",
            timestamp=base_dt - timedelta(days=i),
            open=7000.0,
            high=7150.0,
            low=6950.0,
            close=7100.0,
            volume=1_500_000,
            timeframe="1d",
        )
        for i in range(5)
    ]
    inst = Instrument(symbol="BAJAJFIN", token="317")
    quote = MarketTick(symbol="BAJAJFIN", ltp=7100.0, bid=7099.0, ask=7101.0, volume=1500000)

    res = DynamicStockScreener.evaluate_candidate(inst, candles, quote, account_capital=3000.0)
    assert res.passed is False
    assert any("UNAFFORDABLE_FOR_CAPITAL" in r for r in res.rejection_reasons)

