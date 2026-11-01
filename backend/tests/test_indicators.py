"""Unit Tests for Technical Indicator Calculation Engine."""

from datetime import datetime, time
import zoneinfo
import pytest
from backend.app.indicators.engine import TechnicalIndicatorEngine
from backend.app.models.domain import Candle


@pytest.fixture
def sample_session_candles():
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    base_date = datetime(2026, 10, 29, 9, 20, tzinfo=ist)

    # 4 candles at 09:20, 09:25, 09:30, 09:35 IST
    c1 = Candle(
        symbol="SBIN",
        timestamp=base_date,
        open=800.0,
        high=805.0,
        low=799.0,
        close=803.0,
        volume=10000,
        timeframe="5m",
        is_completed=True,
    )
    c2 = Candle(
        symbol="SBIN",
        timestamp=datetime(2026, 10, 29, 9, 25, tzinfo=ist),
        open=803.0,
        high=808.0,  # ORB High
        low=802.0,
        close=806.0,
        volume=15000,
        timeframe="5m",
        is_completed=True,
    )
    c3 = Candle(
        symbol="SBIN",
        timestamp=datetime(2026, 10, 29, 9, 30, tzinfo=ist),
        open=806.0,
        high=807.0,
        low=795.0,  # ORB Low
        close=798.0,
        volume=12000,
        timeframe="5m",
        is_completed=True,
    )
    c4 = Candle(
        symbol="SBIN",
        timestamp=datetime(2026, 10, 29, 9, 35, tzinfo=ist),
        open=798.0,
        high=812.0,
        low=798.0,
        close=811.0,
        volume=30000,
        timeframe="5m",
        is_completed=True,
    )
    return [c1, c2, c3, c4]


def test_session_vwap_calculation(sample_session_candles):
    """Verifies that Session VWAP equals sum(TypicalPrice * Vol) / sum(Vol)."""
    vwap = TechnicalIndicatorEngine.calculate_session_vwap(sample_session_candles)

    # Manual verification:
    # c1: tp = (805+799+803)/3 = 802.3333 * 10000 = 8023333.33
    # c2: tp = (808+802+806)/3 = 805.3333 * 15000 = 12080000.0
    # c3: tp = (807+795+798)/3 = 800.0000 * 12000 = 9600000.0
    # c4: tp = (812+798+811)/3 = 807.0000 * 30000 = 24210000.0
    # Total TP*V = 53,913,333.33 / 67000 = 804.6766 -> 804.68
    assert vwap == 804.68


def test_opening_range_calculation(sample_session_candles):
    """Verifies 15-minute Opening Range High and Low (09:15 - 09:30 IST)."""
    orb_high, orb_low = TechnicalIndicatorEngine.calculate_opening_range(sample_session_candles)
    assert orb_high == 808.0
    assert orb_low == 795.0


def test_ema_calculation(sample_session_candles):
    """Verifies EMA calculation."""
    ema = TechnicalIndicatorEngine.calculate_ema(sample_session_candles, period=3)
    assert ema > 790.0 and ema < 820.0


def test_relative_volume(sample_session_candles):
    """Verifies RVol calculation against preceding bars."""
    # Prior volumes: c1(10000), c2(15000), c3(12000). Avg = 12333.33
    # c4 volume: 30000 -> 30000 / 12333.33 = 2.43
    rvol = TechnicalIndicatorEngine.calculate_relative_volume(sample_session_candles)
    assert rvol == pytest.approx(2.43, abs=0.05)


def test_compute_snapshot(sample_session_candles):
    """Verifies complete indicator snapshot generation."""
    snapshot = TechnicalIndicatorEngine.compute_snapshot(sample_session_candles)
    assert snapshot.symbol == "SBIN"
    assert snapshot.orb_high == 808.0
    assert snapshot.orb_low == 795.0
    assert snapshot.vwap == 804.68
    assert snapshot.body_ratio >= 0.50

