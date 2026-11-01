"""Candle Validation Engine."""

from datetime import datetime, time
import zoneinfo
from backend.app.models.domain import Candle


class CandleValidationError(Exception):
    """Raised when a candle fails structural or exchange integrity checks."""
    pass


class CandleValidator:
    """Validates that candles adhere to NSE market session constraints and are strictly completed."""

    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)

    @classmethod
    def validate_completed_candle(cls, candle: Candle, expected_timeframe: str = "5m") -> bool:
        """Strictly validates completed candle integrity.

        Rejects forming/incomplete bars to eliminate lookahead bias and intrabar repainting.
        """
        # 1. Enforce completed flag
        if not candle.is_completed:
            raise CandleValidationError(
                f"Candle for {candle.symbol} at {candle.timestamp} is not completed. Strategy requires confirmed close."
            )

        # 2. Enforce timeframe matching
        if candle.timeframe != expected_timeframe:
            raise CandleValidationError(
                f"Candle timeframe {candle.timeframe} does not match expected {expected_timeframe}."
            )

        # 3. Geometric price validation
        if candle.high < max(candle.open, candle.close):
            raise CandleValidationError(
                f"Invalid candle geometry: High ({candle.high}) < max(Open, Close)."
            )
        if candle.low > min(candle.open, candle.close):
            raise CandleValidationError(
                f"Invalid candle geometry: Low ({candle.low}) > min(Open, Close)."
            )
        if candle.volume < 0:
            raise CandleValidationError(
                f"Invalid candle volume: Volume ({candle.volume}) cannot be negative."
            )

        # 4. Exchange session time validation (IST)
        ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        candle_ist = candle.timestamp.astimezone(ist_tz)
        candle_time = candle_ist.time()

        if candle_time < cls.MARKET_OPEN or candle_time > cls.MARKET_CLOSE:
            raise CandleValidationError(
                f"Candle timestamp {candle_time} is outside NSE regular trading hours (09:15 - 15:30 IST)."
            )

        # 5. Minute alignment for 5m candles
        if expected_timeframe == "5m" and (candle_ist.minute % 5 != 0):
            raise CandleValidationError(
                f"Candle timestamp {candle_ist} is not aligned to a 5-minute boundary."
            )

        return True

