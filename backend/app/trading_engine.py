"""Authoritative Master Trading Engine.

Coordinates market data ingestion, strategy signal evaluation, independent risk checks,
position sizing, and adapter dispatch.
"""

import logging
from datetime import datetime, time, timedelta, timezone
import zoneinfo
from backend.app.core.config import TradingMode
from backend.app.execution.adapter_interface import ExecutionAdapter
from backend.app.logging.audit_logger import AuditLogger, audit_logger
from backend.app.market_data.interface import MarketDataProvider
from backend.app.models.domain import (
    Order,
    Position,
    PositionStatus,
    Signal,
    SignalDirection,
)
from backend.app.risk.engine import RiskEngine
from backend.app.strategies.vwap_orb_strategy import VWAP_ORB_Strategy

logger = logging.getLogger("IntradayBot.TradingEngine")


class TradingEngine:
    """Authoritative trading engine shared identically across Paper and Live trading."""

    def __init__(
        self,
        market_data_provider: MarketDataProvider,
        risk_engine: RiskEngine,
        execution_adapter: ExecutionAdapter,
        logger_instance: AuditLogger | None = None,
        mode: TradingMode = TradingMode.PAPER,
    ):
        self.market_data = market_data_provider
        self.risk_engine = risk_engine
        self.execution = execution_adapter
        self.audit = logger_instance or audit_logger
        self.mode = mode

    def process_symbol(
        self,
        symbol: str,
        nifty_symbol: str = "NIFTY",
        start: datetime | None = None,
        end: datetime | None = None,
        last_processed_ts: datetime | None = None,
        current_execution_time: datetime | None = None,
    ) -> tuple[Signal | None, Order | None]:
        """Evaluates a single instrument through the complete pipeline:

        Candle Ingestion -> Chronological Multi-Candle Evaluation -> Strategy Evaluation -> Independent Risk -> Execution Dispatch.
        """
        start_time = start or candles_start_placeholder()
        end_time = end or candles_end_placeholder()

        # 1. Fetch completed 5-minute candles
        candles = self.market_data.get_historical_candles(
            symbol=symbol,
            timeframe="5m",
            start=start_time,
            end=end_time,
        )
        if not candles or len(candles) < 4:
            return None, None

        nifty_candles = self.market_data.get_historical_candles(
            symbol=nifty_symbol,
            timeframe="5m",
            start=start_time,
            end=end_time,
        )

        # 2. Determine eligible candidate bar slices
        # If last_processed_ts is provided, process all completed candles strictly after it
        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        if last_processed_ts:
            norm_last = last_processed_ts if last_processed_ts.tzinfo else last_processed_ts.replace(tzinfo=timezone.utc)
            eval_indices = [
                i for i in range(3, len(candles))
                if (candles[i].timestamp if candles[i].timestamp.tzinfo else candles[i].timestamp.replace(tzinfo=timezone.utc)) > norm_last
            ]
        else:
            # Default to evaluating the latest completed candle
            eval_indices = [len(candles) - 1]

        # Only evaluate bars completed at or after 09:30 IST (post 15-min ORB formation)
        eval_indices = [
            i for i in eval_indices
            if candles[i].timestamp.astimezone(ist).time() >= time(9, 30)
        ]

        if not eval_indices:
            logger.debug("No new completed candles for %s since %s", symbol, last_processed_ts)
            return None, None

        latest_signal = None
        executed_order = None

        # 3. Evaluate each completed candle chronologically
        for idx in eval_indices:
            current_bar = candles[idx]
            candles_slice = candles[: idx + 1]
            nifty_slice = [n for n in nifty_candles if n.timestamp <= current_bar.timestamp] if nifty_candles else []

            signal: Signal | None = VWAP_ORB_Strategy.evaluate(
                candles=candles_slice, nifty_candles=nifty_slice
            )
            if not signal:
                continue

            latest_signal = signal
            self.audit.log_signal(signal, self.mode)

            # Independent Risk Management & Position Sizing
            account = self.execution.get_account_state()
            quote = self.market_data.get_current_quote(symbol)
            open_positions = self.execution.get_open_positions()
            is_healthy = self.market_data.is_healthy()

            risk_decision = self.risk_engine.evaluate_signal(
                signal=signal,
                account=account,
                quote=quote,
                open_positions=open_positions,
                is_market_data_healthy=is_healthy,
                mode=self.mode,
                current_execution_time=current_execution_time,
            )

            if not risk_decision.approved or not risk_decision.order_intent:
                self.audit.log_rejection(
                    symbol=symbol,
                    reason=risk_decision.rejection_reason or "REJECTED_BY_RISK_ENGINE",
                    mode=self.mode,
                    details=risk_decision.details,
                )
                continue

            # Dispatch Approved Intent to Execution Adapter
            order = self.execution.submit_order(risk_decision.order_intent)
            self.audit.log_order(order)
            executed_order = order
            break  # Executed trade for this symbol; stop processing further bars

        return latest_signal, executed_order

    def evaluate_open_positions(
        self,
        current_quotes: dict[str, float],
        current_time: datetime | None = None,
    ) -> list[Position]:
        """Monitors open positions against structural stop loss, target prices, and intraday square-off.

        Square-off rule: Any position still open at or after 15:15 IST is forcibly closed
        at the current market price, regardless of stop-loss or target status. This prevents
        illegal overnight carry of intraday paper positions.
        """
        IST = zoneinfo.ZoneInfo("Asia/Kolkata")
        SQUARE_OFF_TIME = time(15, 15)

        now_ist = (current_time.astimezone(IST) if current_time else datetime.now(IST))
        must_square_off = now_ist.time() >= SQUARE_OFF_TIME

        closed_positions: list[Position] = []
        open_positions = self.execution.get_open_positions()

        for pos in open_positions:
            price = current_quotes.get(pos.symbol)
            if price is None:
                continue

            pos.current_price = price

            # Compulsory intraday square-off at 15:15 IST — takes priority over SL/TP
            if must_square_off:
                logger.info(
                    "SQUARE_OFF: Forcing close of %s at %.2f (time=%s IST >= 15:15)",
                    pos.symbol, price, now_ist.strftime("%H:%M"),
                )
                closed = self.execution.close_position(
                    pos.position_id, exit_price=price, reason="INTRADAY_SQUARE_OFF"
                )
                closed_positions.append(closed)
                continue

            # Long position exits
            if pos.direction == SignalDirection.BUY:
                if price <= pos.stop_loss:
                    closed = self.execution.close_position(
                        pos.position_id, exit_price=price, reason="STOP_LOSS_HIT"
                    )
                    closed_positions.append(closed)
                elif price >= pos.target:
                    closed = self.execution.close_position(
                        pos.position_id, exit_price=price, reason="TARGET_HIT"
                    )
                    closed_positions.append(closed)

            # Short position exits
            elif pos.direction == SignalDirection.SELL:
                if price >= pos.stop_loss:
                    closed = self.execution.close_position(
                        pos.position_id, exit_price=price, reason="STOP_LOSS_HIT"
                    )
                    closed_positions.append(closed)
                elif price <= pos.target:
                    closed = self.execution.close_position(
                        pos.position_id, exit_price=price, reason="TARGET_HIT"
                    )
                    closed_positions.append(closed)

        return closed_positions


def candles_start_placeholder():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) - timedelta(days=1)


def candles_end_placeholder():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(days=1)

