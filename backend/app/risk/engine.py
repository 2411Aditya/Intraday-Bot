"""Independent Risk Management Engine."""

from datetime import datetime, time, timezone
import zoneinfo
from pydantic import BaseModel
from backend.app.core.config import TradingMode
from backend.app.models.domain import (
    AccountState,
    MarketTick,
    OrderIntent,
    Position,
    Signal,
)
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.risk.position_sizer import PositionSizer


class RiskCheckResult(BaseModel):
    """Evaluation outcome from the independent risk engine."""

    approved: bool
    rejection_reason: str | None = None
    order_intent: OrderIntent | None = None
    details: dict = {}


class RiskEngine:
    """Autonomous risk control engine possessing absolute veto authority over trade orders."""

    ENTRY_WINDOW_START = time(9, 30)
    ENTRY_WINDOW_END = time(11, 30)
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")

    def __init__(
        self,
        risk_per_trade_pct: float = 0.5,
        max_daily_loss_pct: float = 1.0,
        max_trades_per_day: int = 2,
        max_concurrent_positions: int = 1,
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions

    def evaluate_signal(
        self,
        signal: Signal,
        account: AccountState,
        quote: MarketTick,
        open_positions: list[Position],
        is_market_data_healthy: bool = True,
        mode: TradingMode = TradingMode.PAPER,
        current_execution_time: datetime | None = None,
    ) -> RiskCheckResult:
        """Evaluates a proposed strategy signal across all independent risk guardrails."""
        # 1. Market Data Integrity & Freshness
        if not is_market_data_healthy:
            return RiskCheckResult(
                approved=False,
                rejection_reason="MARKET_DATA_FEED_UNHEALTHY_OR_STALE",
            )

        # 2. Entry Window Check (09:30 - 11:30 IST)
        signal_time = signal.timestamp.astimezone(self.IST).time()
        if not (self.ENTRY_WINDOW_START <= signal_time <= self.ENTRY_WINDOW_END):
            return RiskCheckResult(
                approved=False,
                rejection_reason=f"TIME_OUTSIDE_ENTRY_WINDOW_{signal_time}",
            )

        # 2.1 Signal Expiry Check: Reject stale setups against actual current execution time
        if signal.expiry_time:
            now_exec = current_execution_time or datetime.now(timezone.utc)
            sig_exp = signal.expiry_time if signal.expiry_time.tzinfo else signal.expiry_time.replace(tzinfo=timezone.utc)
            cmp_ts = now_exec if now_exec.tzinfo else now_exec.replace(tzinfo=timezone.utc)
            if cmp_ts > sig_exp:
                return RiskCheckResult(
                    approved=False,
                    rejection_reason="SIGNAL_EXPIRED",
                )

        # 3. Maximum Trades Per Day Cap
        if account.trades_count_today >= self.max_trades_per_day:
            return RiskCheckResult(
                approved=False,
                rejection_reason=f"MAX_DAILY_TRADES_EXCEEDED_{account.trades_count_today}",
            )

        # 4. Maximum Concurrent Open Positions
        active_positions = [p for p in open_positions if p.status == "OPEN"]
        if len(active_positions) >= self.max_concurrent_positions:
            return RiskCheckResult(
                approved=False,
                rejection_reason=f"MAX_CONCURRENT_POSITIONS_REACHED_{len(active_positions)}",
            )

        # 5. Daily Realized Loss Circuit Breaker
        if account.daily_loss_pct >= self.max_daily_loss_pct or account.is_daily_loss_breached:
            return RiskCheckResult(
                approved=False,
                rejection_reason=f"DAILY_LOSS_LIMIT_BREACHED_{round(account.daily_loss_pct, 2)}PCT",
            )

        # 6. Bid-Ask Spread Viability
        if quote.spread_pct > 0.10:
            return RiskCheckResult(
                approved=False,
                rejection_reason=f"BID_ASK_SPREAD_TOO_WIDE_{round(quote.spread_pct, 3)}PCT",
            )

        # 7. Stop-Loss Volatility Sanity Check (Max 1.5x ATR-14)
        stop_distance = abs(signal.entry_price - signal.stop_loss)
        max_stop_distance = 2.0 * signal.indicators.atr_14
        if stop_distance > max_stop_distance:
            return RiskCheckResult(
                approved=False,
                rejection_reason=(
                    f"STOP_DISTANCE_{round(stop_distance, 2)}_EXCEEDS_1.5X_ATR_{round(max_stop_distance, 2)}"
                ),
            )

        # 8. Capital-Aware Position Sizing
        sizing = PositionSizer.calculate_size(
            trading_equity=account.total_equity,
            available_cash=account.cash_balance,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            risk_pct=self.risk_per_trade_pct,
        )
        if not sizing.is_valid or sizing.quantity < 1:
            return RiskCheckResult(
                approved=False,
                rejection_reason=sizing.rejection_reason or "INSUFFICIENT_QUANTITY_AFTER_SIZING",
            )

        # 9. Comprehensive Transaction Cost Viability Filter
        costs = TransactionCostModel.calculate_roundtrip_costs(
            quantity=sizing.quantity,
            entry_price=signal.entry_price,
            exit_price=signal.target_price,
        )
        is_viable, cost_reason = TransactionCostModel.is_economically_viable(costs)
        if not is_viable:
            return RiskCheckResult(
                approved=False,
                rejection_reason=cost_reason,
                details=costs.model_dump(),
            )



        # 10. Generate Approved Order Intent
        gross_profit = abs(signal.target_price - signal.entry_price) * sizing.quantity
        order_intent = OrderIntent(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=sizing.quantity,
            order_type="STOP_LIMIT" if signal.direction == "BUY" else "LIMIT",
            price=signal.entry_price,
            trigger_price=signal.entry_price if signal.direction == "BUY" else None,
            stop_loss=signal.stop_loss,
            target=signal.target_price,
            mode=mode,
            risk_budget=sizing.risk_budget,
            estimated_costs=costs.total_costs,
            projected_gross_profit=round(gross_profit, 2),
        )

        return RiskCheckResult(
            approved=True,
            rejection_reason=None,
            order_intent=order_intent,
            details={
                "quantity": sizing.quantity,
                "capital_deployed": sizing.capital_deployed,
                "risk_budget": sizing.risk_budget,
                "estimated_costs": costs.total_costs,
                "cost_to_reward_ratio": costs.cost_to_reward_ratio,
            },
        )

