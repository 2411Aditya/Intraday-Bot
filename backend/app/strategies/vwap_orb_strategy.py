"""Authoritative VWAP + ORB + EMA + Volume Confirmation Strategy Engine."""

from datetime import datetime, time, timedelta
import zoneinfo
from backend.app.indicators.engine import TechnicalIndicatorEngine
from backend.app.market_data.validator import CandleValidator
from backend.app.models.domain import (
    Candle,
    IndicatorSnapshot,
    Signal,
    SignalDirection,
)


class VWAP_ORB_Strategy:
    """Strategy Version 1.0.0.

    Authoritative trading strategy engine shared identically between Virtual Paper
    and Actual Live trading modes.
    """

    STRATEGY_NAME = "VWAP_ORB_EMA_VOL"
    STRATEGY_VERSION = "1.0.0"
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
    ORB_END_TIME = time(9, 30)

    @classmethod
    def evaluate(
        cls,
        candles: list[Candle],
        nifty_candles: list[Candle] | None = None,
        planned_rrr: float = 2.0,
    ) -> Signal | None:
        """Evaluates completed candles and generates authoritative trading signals."""
        if not candles or len(candles) < 4:
            return None

        latest = candles[-1]

        # 1. Strict candle completion validation
        CandleValidator.validate_completed_candle(latest, expected_timeframe="5m")

        latest_time = latest.timestamp.astimezone(cls.IST).time()
        # Signals only evaluated after first 15-minute range is formed (after 09:30 IST)
        if latest_time < cls.ORB_END_TIME:
            return None

        # 2. Compute point-in-time indicators
        indicators: IndicatorSnapshot = TechnicalIndicatorEngine.compute_snapshot(
            candles, nifty_candles
        )

        # 3. Evaluate Long Entry Rules
        long_checklist = cls._check_long_rules(latest, indicators)
        if all(long_checklist.values()):
            entry_price = round(latest.close, 2)
            # Structural Stop: Min of signal candle low and (ORB High - 0.05% buffer)
            orb_buffer = round(indicators.orb_high * 0.0005, 2)
            structural_stop = min(latest.low, indicators.orb_high - orb_buffer)
            stop_loss = round(structural_stop, 2)

            risk_per_share = entry_price - stop_loss
            if risk_per_share >= 0.05:
                target_price = round(entry_price + (planned_rrr * risk_per_share), 2)
                expiry_time = latest.timestamp + timedelta(minutes=10)

                return Signal(
                    symbol=latest.symbol,
                    direction=SignalDirection.BUY,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    planned_rrr=planned_rrr,
                    timestamp=latest.timestamp,
                    expiry_time=expiry_time,
                    indicators=indicators,
                    checklist_passed=long_checklist,
                )

        # 4. Evaluate Short Entry Rules
        short_checklist = cls._check_short_rules(latest, indicators)
        if all(short_checklist.values()):
            entry_price = round(latest.close, 2)
            # Structural Stop: Max of signal candle high and (ORB Low + 0.05% buffer)
            orb_buffer = round(indicators.orb_low * 0.0005, 2)
            structural_stop = max(latest.high, indicators.orb_low + orb_buffer)
            stop_loss = round(structural_stop, 2)

            risk_per_share = stop_loss - entry_price
            if risk_per_share >= 0.05:
                target_price = round(entry_price - (planned_rrr * risk_per_share), 2)
                expiry_time = latest.timestamp + timedelta(minutes=10)

                return Signal(
                    symbol=latest.symbol,
                    direction=SignalDirection.SELL,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    planned_rrr=planned_rrr,
                    timestamp=latest.timestamp,
                    expiry_time=expiry_time,
                    indicators=indicators,
                    checklist_passed=short_checklist,
                )

        return None

    @classmethod
    def _check_long_rules(cls, candle: Candle, ind: IndicatorSnapshot) -> dict[str, bool]:
        """Evaluates the 18-point long entry checklist."""
        nifty_aligned = True
        if ind.nifty_close is not None and ind.nifty_vwap is not None:
            nifty_aligned = ind.nifty_close > ind.nifty_vwap

        return {
            "candle_completed": candle.is_completed,
            "nifty_above_vwap": nifty_aligned,
            "stock_above_vwap": candle.close > ind.vwap,
            "stock_above_ema20": candle.close > ind.ema_20,
            "orb_high_broken": candle.high > ind.orb_high,
            "orb_high_close_confirmed": candle.close > ind.orb_high,
            "volume_surge_confirmed": ind.relative_volume >= 1.50,
            "candle_body_conviction": ind.body_ratio >= 0.50,
            "candle_bullish": candle.close > candle.open,
        }

    @classmethod
    def _check_short_rules(cls, candle: Candle, ind: IndicatorSnapshot) -> dict[str, bool]:
        """Evaluates the 18-point short entry checklist."""
        nifty_aligned = True
        if ind.nifty_close is not None and ind.nifty_vwap is not None:
            nifty_aligned = ind.nifty_close < ind.nifty_vwap

        return {
            "candle_completed": candle.is_completed,
            "nifty_below_vwap": nifty_aligned,
            "stock_below_vwap": candle.close < ind.vwap,
            "stock_below_ema20": candle.close < ind.ema_20,
            "orb_low_broken": candle.low < ind.orb_low,
            "orb_low_close_confirmed": candle.close < ind.orb_low,
            "volume_surge_confirmed": ind.relative_volume >= 1.50,
            "candle_body_conviction": ind.body_ratio >= 0.50,
            "candle_bearish": candle.close < candle.open,
        }

