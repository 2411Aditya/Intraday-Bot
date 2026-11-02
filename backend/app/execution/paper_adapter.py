"""Virtual Broker and Paper Execution Adapter."""

from datetime import datetime, timezone
from backend.app.core.config import TradingMode
from backend.app.execution.adapter_interface import ExecutionAdapter
from backend.app.models.domain import (
    AccountState,
    Order,
    OrderIntent,
    OrderStatus,
    Position,
    PositionStatus,
    SignalDirection,
)
from backend.app.risk.cost_model import TransactionCostModel


class PaperExecutionAdapter(ExecutionAdapter):
    """Realistic Virtual Broker simulation with conservative fills, slippage, and fee deduction."""

    def __init__(
        self,
        starting_capital: float = 10000.0,
        slippage_rate: float = 0.0005,  # 0.05% slippage
        max_daily_loss_pct: float = 1.0,
    ):
        self.slippage_rate = slippage_rate
        self.account = AccountState(
            mode=TradingMode.PAPER,
            starting_capital=starting_capital,
            cash_balance=starting_capital,
            deployed_margin=0.0,
            realized_pnl_today=0.0,
            trades_count_today=0,
            max_daily_loss_budget=round(starting_capital * (max_daily_loss_pct / 100.0), 2),
            is_daily_loss_breached=False,
        )
        self.orders: dict[str, Order] = {}
        self.positions: dict[str, Position] = {}

    def submit_order(self, intent: OrderIntent) -> Order:
        """Simulates conservative order placement and fill execution with adverse slippage."""
        # 1. Enforce mode consistency
        if intent.mode != TradingMode.PAPER:
            raise ValueError(f"PaperExecutionAdapter cannot execute order for mode {intent.mode}")

        # 2. Check cash adequacy
        required_cash = intent.quantity * intent.price
        if required_cash > self.account.cash_balance:
            order = Order(
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                direction=intent.direction,
                quantity=intent.quantity,
                price=intent.price,
                status=OrderStatus.REJECTED,
                mode=TradingMode.PAPER,
                rejection_reason="INSUFFICIENT_VIRTUAL_CASH",
            )
            self.orders[order.order_id] = order
            return order

        # 3. Model conservative adverse fill price with slippage
        slippage_amount = round(intent.price * self.slippage_rate, 2)
        if intent.direction == SignalDirection.BUY:
            fill_price = round(intent.price + slippage_amount, 2)
        else:
            fill_price = round(intent.price - slippage_amount, 2)

        # 4. Create filled Order
        order = Order(
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            direction=intent.direction,
            quantity=intent.quantity,
            price=intent.price,
            status=OrderStatus.FILLED,
            filled_quantity=intent.quantity,
            average_fill_price=fill_price,
            filled_at=datetime.now(timezone.utc),
            mode=TradingMode.PAPER,
            broker_order_id=f"VIRT-BROKER-{order_id_suffix(intent.intent_id)}",
        )
        self.orders[order.order_id] = order

        # 5. Deduct deployed cash and entry statutory fees
        entry_fees = TransactionCostModel.calculate_leg_costs(
            quantity=order.quantity,
            price=fill_price,
            side=intent.direction.value,
        )
        deployed = order.quantity * fill_price
        self.account.cash_balance -= (deployed + entry_fees)
        self.account.deployed_margin += deployed

        # 6. Create active Position
        position = Position(
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=intent.stop_loss,
            target=intent.target,
            status=PositionStatus.OPEN,
            entry_fees=entry_fees,
            mode=TradingMode.PAPER,
        )
        self.positions[position.position_id] = position

        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def get_open_positions(self) -> list[Position]:
        return [p for p in self.positions.values() if p.status == PositionStatus.OPEN]

    def close_position(
        self, position_id: str, exit_price: float, reason: str = "TARGET_OR_STOP"
    ) -> Position:
        """Closes an active position, applies exit slippage, and updates ledger with statutory costs."""
        pos = self.positions.get(position_id)
        if not pos or pos.status != PositionStatus.OPEN:
            raise ValueError(f"Position {position_id} is not open.")

        # Model exit slippage
        slippage_amount = round(exit_price * self.slippage_rate, 2)
        if pos.direction == SignalDirection.BUY:
            actual_exit = round(exit_price - slippage_amount, 2)  # Adverse exit on sell
            gross_pnl = round((actual_exit - pos.entry_price) * pos.quantity, 2)
        else:
            actual_exit = round(exit_price + slippage_amount, 2)  # Adverse exit on buy-to-cover
            gross_pnl = round((pos.entry_price - actual_exit) * pos.quantity, 2)

        # Calculate exit leg fees and total trade statutory fees
        exit_side = "SELL" if pos.direction == SignalDirection.BUY else "BUY"
        exit_fees = TransactionCostModel.calculate_leg_costs(
            quantity=pos.quantity,
            price=actual_exit,
            side=exit_side,
        )
        total_costs = round(pos.entry_fees + exit_fees, 2)
        net_pnl = round(gross_pnl - total_costs, 2)

        # Update position state
        pos.exit_price = actual_exit
        pos.exit_time = datetime.now(timezone.utc)
        pos.exit_reason = reason
        pos.status = PositionStatus.CLOSED
        pos.realized_pnl = net_pnl
        pos.unrealized_pnl = 0.0

        # Update account ledger: cash returned is deployed capital + gross profit - exit leg fees
        returned_cash = (pos.quantity * pos.entry_price) + gross_pnl - exit_fees
        self.account.cash_balance += returned_cash
        self.account.deployed_margin -= (pos.quantity * pos.entry_price)
        self.account.realized_pnl_today += net_pnl
        self.account.trades_count_today += 1

        # Check daily loss circuit breaker
        if (
            self.account.realized_pnl_today < 0
            and abs(self.account.realized_pnl_today) >= self.account.max_daily_loss_budget
        ):
            self.account.is_daily_loss_breached = True

        return pos

    def revert_position_to_open(self, position_id: str) -> None:
        """Rollback a closed position back to OPEN if persistence fails, keeping ledger synchronized."""
        pos = self.positions.get(position_id)
        if not pos or pos.status != PositionStatus.CLOSED:
            return

        exit_side = "SELL" if pos.direction == SignalDirection.BUY else "BUY"
        exit_fees = TransactionCostModel.calculate_leg_costs(
            quantity=pos.quantity,
            price=pos.exit_price or pos.entry_price,
            side=exit_side,
        )
        gross_pnl = (
            round((pos.exit_price - pos.entry_price) * pos.quantity, 2)
            if pos.direction == SignalDirection.BUY
            else round((pos.entry_price - pos.exit_price) * pos.quantity, 2)
        )
        returned_cash = (pos.quantity * pos.entry_price) + gross_pnl - exit_fees
        net_pnl = round(gross_pnl - (pos.entry_fees + exit_fees), 2)

        self.account.cash_balance -= returned_cash
        self.account.deployed_margin += (pos.quantity * pos.entry_price)
        self.account.realized_pnl_today -= net_pnl
        self.account.trades_count_today -= 1
        self.account.is_daily_loss_breached = False

        pos.status = PositionStatus.OPEN
        pos.exit_price = None
        pos.exit_time = None
        pos.exit_reason = None
        pos.realized_pnl = 0.0

    def get_account_state(self) -> AccountState:
        return self.account


def order_id_suffix(val: str) -> str:
    return val[-6:] if len(val) >= 6 else "000001"

