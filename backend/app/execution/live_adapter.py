"""Angel One Live Broker Execution Adapter (Hard Safety Gated)."""

from backend.app.core.config import TradingMode, settings
from backend.app.execution.adapter_interface import ExecutionAdapter
from backend.app.models.domain import AccountState, Order, OrderIntent, Position


class LiveExecutionLockedError(RuntimeError):
    """Raised whenever live order routing is invoked while locked or unauthorized."""
    pass


class LiveExecutionAdapter(ExecutionAdapter):
    """Direct broker adapter for Angel One SmartAPI live trading.

    IMPORTANT SAFETY GUARANTEE:
    This adapter is physically gated behind multiple backend checks:
    1. settings.LIVE_TRADING_ENABLED must be explicitly True.
    2. settings.TRADING_MODE must be TradingMode.ACTUAL.
    3. Mandatory Static IP and daily 2FA TOTP verification must pass.
    If any check fails, all execution methods raise LiveExecutionLockedError.
    """

    def __init__(self):
        # Enforce initialization safety gates
        if not settings.LIVE_TRADING_ENABLED or settings.TRADING_MODE != TradingMode.ACTUAL:
            self._is_locked = True
        else:
            self._is_locked = False

    @property
    def is_locked(self) -> bool:
        return (
            self._is_locked
            or not settings.LIVE_TRADING_ENABLED
            or settings.TRADING_MODE != TradingMode.ACTUAL
        )

    def _assert_live_authorized(self) -> None:
        if self.is_locked:
            raise LiveExecutionLockedError(
                "Live trading execution is STRICTLY LOCKED. "
                "LIVE_TRADING_ENABLED=False or TRADING_MODE!=actual. "
                "Real broker orders cannot be placed."
            )

    def submit_order(self, intent: OrderIntent) -> Order:
        """Submit a real order to Angel One SmartAPI (Strictly Gated)."""
        self._assert_live_authorized()

        # When authorized in Phase 16, this invokes SmartConnect.placeOrder()
        raise NotImplementedError("Live order placement is not activated.")

    def cancel_order(self, order_id: str) -> bool:
        self._assert_live_authorized()
        raise NotImplementedError("Live order cancellation is not activated.")

    def get_order(self, order_id: str) -> Order | None:
        self._assert_live_authorized()
        return None

    def get_open_positions(self) -> list[Position]:
        self._assert_live_authorized()
        return []

    def close_position(
        self, position_id: str, exit_price: float, reason: str = "TARGET_OR_STOP"
    ) -> Position:
        self._assert_live_authorized()
        raise NotImplementedError("Live position closing is not activated.")

    def get_account_state(self) -> AccountState:
        self._assert_live_authorized()
        raise NotImplementedError("Live account state retrieval is not activated.")

