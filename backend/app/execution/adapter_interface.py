"""Execution Adapter Interface."""

from abc import ABC, abstractmethod
from backend.app.models.domain import AccountState, Order, OrderIntent, Position


class ExecutionAdapter(ABC):
    """Abstract interface defining uniform execution methods for Paper and Live trading."""

    @abstractmethod
    def submit_order(self, intent: OrderIntent) -> Order:
        """Submit an order for execution."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Retrieve order status."""
        pass

    @abstractmethod
    def get_open_positions(self) -> list[Position]:
        """Retrieve all currently active open positions."""
        pass

    @abstractmethod
    def close_position(
        self, position_id: str, exit_price: float, reason: str = "TARGET_OR_STOP"
    ) -> Position:
        """Close an active position."""
        pass

    @abstractmethod
    def get_account_state(self) -> AccountState:
        """Retrieve current account equity, cash balance, and risk utilization."""
        pass

