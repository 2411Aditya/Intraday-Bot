"""Technical Indicator Calculation Engine."""

from datetime import time
import zoneinfo
from backend.app.models.domain import Candle, IndicatorSnapshot


class TechnicalIndicatorEngine:
    """Computes verified mathematical technical indicators for intraday trading."""

    IST = zoneinfo.ZoneInfo("Asia/Kolkata")

    @classmethod
    def calculate_session_vwap(cls, candles: list[Candle]) -> float:
        """Calculates cumulative Session VWAP starting from 09:15 IST of the current day.

        Formula: sum(TypicalPrice * Volume) / sum(Volume)
        TypicalPrice = (High + Low + Close) / 3
        """
        if not candles:
            return 0.0

        # Anchor to the current session day (Asia/Kolkata)
        target_date = candles[-1].timestamp.astimezone(cls.IST).date()
        session_candles = [
            c for c in candles
            if c.timestamp.astimezone(cls.IST).date() == target_date and c.is_completed
        ]

        if not session_candles:
            return candles[-1].close

        cum_tp_vol = 0.0
        cum_vol = 0

        for c in session_candles:
            tp = (c.high + c.low + c.close) / 3.0
            cum_tp_vol += tp * c.volume
            cum_vol += c.volume

        if cum_vol == 0:
            return session_candles[-1].close

        return round(cum_tp_vol / cum_vol, 2)

    @classmethod
    def calculate_opening_range(cls, candles: list[Candle]) -> tuple[float, float]:
        """Calculates 15-minute Opening Range High and Low (09:15 - 09:30 IST).

        Uses completed 5m candles closing at 09:20, 09:25, and 09:30 IST.
        """
        if not candles:
            return 0.0, 0.0

        target_date = candles[-1].timestamp.astimezone(cls.IST).date()
        orb_candles = [
            c for c in candles
            if c.timestamp.astimezone(cls.IST).date() == target_date
            and c.is_completed
            and time(9, 15) <= c.timestamp.astimezone(cls.IST).time() <= time(9, 30)
        ]

        if not orb_candles:
            # Fallback to latest candle high/low if ORB window not yet reached
            return candles[-1].high, candles[-1].low

        orb_high = max(c.high for c in orb_candles)
        orb_low = min(c.low for c in orb_candles)
        return round(orb_high, 2), round(orb_low, 2)

    @classmethod
    def calculate_ema(cls, candles: list[Candle], period: int = 20) -> float:
        """Calculates Exponential Moving Average of closing prices over specified period.

        Formula: EMA_today = (Close * alpha) + (EMA_prev * (1 - alpha))
        alpha = 2 / (period + 1)
        """
        if not candles:
            return 0.0

        completed = [c for c in candles if c.is_completed]
        if not completed:
            return 0.0

        closes = [c.close for c in completed]
        if len(closes) < period:
            # If warm-up is shorter than period, return simple average of available closes
            return round(sum(closes) / len(closes), 2)

        alpha = 2.0 / (period + 1.0)
        # Seed EMA with initial SMA of first 'period' elements
        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price * alpha) + (ema * (1.0 - alpha))

        return round(ema, 2)

    @classmethod
    def calculate_atr(cls, candles: list[Candle], period: int = 14) -> float:
        """Calculates Average True Range (Wilder's ATR-14)."""
        if not candles:
            return 0.0

        completed = [c for c in candles if c.is_completed]
        if len(completed) < 2:
            return round(completed[-1].high - completed[-1].low, 2) if completed else 1.0

        true_ranges: list[float] = []
        for i in range(1, len(completed)):
            curr = completed[i]
            prev = completed[i - 1]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close),
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return round(sum(true_ranges) / len(true_ranges), 2)

        # Initial SMA
        atr = sum(true_ranges[:period]) / period
        for tr in true_ranges[period:]:
            atr = ((atr * (period - 1)) + tr) / period

        return round(atr, 2)

    @classmethod
    def calculate_volume_sma(cls, candles: list[Candle], period: int = 10) -> float:
        """Calculates Simple Moving Average of Volume for the prior 'period' completed candles."""
        completed = [c for c in candles if c.is_completed]
        if len(completed) < 2:
            return float(completed[-1].volume if completed else 10000)

        # Exclude the current active signal candle (measure baseline against preceding bars)
        prior_volumes = [c.volume for c in completed[:-1]]
        subset = prior_volumes[-period:] if len(prior_volumes) >= period else prior_volumes
        if not subset:
            return float(completed[-1].volume)

        return round(sum(subset) / len(subset), 2)

    @classmethod
    def calculate_relative_volume(cls, candles: list[Candle], period: int = 10) -> float:
        """Calculates Relative Volume: Current Signal Candle Volume / Volume SMA(10)."""
        if not candles:
            return 0.0

        current_vol = candles[-1].volume
        avg_vol = cls.calculate_volume_sma(candles, period)
        if avg_vol <= 0:
            return 1.0

        return round(current_vol / avg_vol, 2)

    @classmethod
    def compute_snapshot(
        cls, candles: list[Candle], nifty_candles: list[Candle] | None = None
    ) -> IndicatorSnapshot:
        """Assembles a verified immutable IndicatorSnapshot for the latest completed candle."""
        if not candles:
            raise ValueError("Cannot compute indicator snapshot on empty candle list.")

        latest = candles[-1]
        orb_h, orb_l = cls.calculate_opening_range(candles)
        vwap = cls.calculate_session_vwap(candles)
        ema20 = cls.calculate_ema(candles, period=20)
        atr14 = cls.calculate_atr(candles, period=14)
        vol_sma = cls.calculate_volume_sma(candles, period=10)
        rvol = cls.calculate_relative_volume(candles, period=10)

        nifty_vwap = None
        nifty_close = None
        if nifty_candles:
            nifty_vwap = cls.calculate_session_vwap(nifty_candles)
            nifty_close = nifty_candles[-1].close

        return IndicatorSnapshot(
            symbol=latest.symbol,
            timestamp=latest.timestamp,
            vwap=vwap,
            ema_20=ema20,
            atr_14=atr14,
            orb_high=orb_h,
            orb_low=orb_l,
            volume_sma_10=vol_sma,
            relative_volume=rvol,
            body_ratio=round(latest.body_ratio, 2),
            nifty_vwap=nifty_vwap,
            nifty_close=nifty_close,
        )

