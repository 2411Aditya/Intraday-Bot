"""Unit Tests for Completed 5-Minute Candle Validation."""

from datetime import datetime
import zoneinfo
import pytest
from backend.app.market_data.validator import CandleValidationError, CandleValidator
from backend.app.models.domain import Candle


@pytest.fixture
def valid_ist_candle():
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    return Candle(
        symbol="INFY",
        timestamp=datetime(2026, 10, 29, 9, 35, tzinfo=ist),
        open=1500.0,
        high=1510.0,
        low=1498.0,
        close=1508.0,
        volume=25000,
        timeframe="5m",
        is_completed=True,
    )


def test_valid_completed_candle(valid_ist_candle):
    assert CandleValidator.validate_completed_candle(valid_ist_candle) is True


def test_reject_uncompleted_candle(valid_ist_candle):
    """Must strictly reject incomplete or forming bar."""
    valid_ist_candle.is_completed = False
    with pytest.raises(CandleValidationError, match="not completed"):
        CandleValidator.validate_completed_candle(valid_ist_candle)


def test_reject_invalid_geometry(valid_ist_candle):
    """High cannot be lower than max(Open, Close)."""
    valid_ist_candle.high = 1490.0  # Invalid! Lower than Open/Close
    with pytest.raises(CandleValidationError, match="Invalid candle geometry"):
        CandleValidator.validate_completed_candle(valid_ist_candle)


def test_reject_outside_market_hours(valid_ist_candle):
    """Reject bars occurring before 09:15 or after 15:30 IST."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    valid_ist_candle.timestamp = datetime(2026, 10, 29, 8, 45, tzinfo=ist)
    with pytest.raises(CandleValidationError, match="outside NSE regular trading hours"):
        CandleValidator.validate_completed_candle(valid_ist_candle)


def test_reject_unaligned_boundary(valid_ist_candle):
    """Reject bars not aligned to 5m intervals (e.g. 09:37 IST)."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    valid_ist_candle.timestamp = datetime(2026, 10, 29, 9, 37, tzinfo=ist)
    with pytest.raises(CandleValidationError, match="not aligned to a 5-minute boundary"):
        CandleValidator.validate_completed_candle(valid_ist_candle)

