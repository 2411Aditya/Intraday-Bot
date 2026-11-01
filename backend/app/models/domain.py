"""Core Domain Models and Schemas for Trading Platform."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field

from backend.app.core.config import TradingMode


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Candle(BaseModel):
    """Represents a completed or forming OHLCV bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str = "5m"
    is_completed: bool = True

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    @property
    def range(self) -> float:
        return max(self.high - self.low, 0.0001)

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        return self.body_size / self.range


class MarketTick(BaseModel):
    """Real-time market depth / LTP tick."""

    symbol: str
    ltp: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def spread(self) -> float:
        return max(self.ask - self.bid, 0.0)

    @property
    def spread_pct(self) -> float:
        if self.ltp <= 0:
            return 0.0
        return (self.spread / self.ltp) * 100.0


class Instrument(BaseModel):
    """Trading instrument definition."""

    symbol: str
    token: str
    exchange: str = "NSE"
    lot_size: int = 1
    tick_size: float = 0.05
    freeze_limit: int = 100000


class IndicatorSnapshot(BaseModel):
    """Point-in-time technical indicator calculations."""

    symbol: str
    timestamp: datetime
    vwap: float
    ema_20: float
    atr_14: float
    orb_high: float
    orb_low: float
    volume_sma_10: float
    relative_volume: float
    body_ratio: float
    nifty_vwap: float | None = None
    nifty_close: float | None = None


class Signal(BaseModel):
    """Authoritative strategy trade recommendation."""

    signal_id: str = Field(default_factory=lambda: f"SIG-{uuid4().hex[:8].upper()}")
    symbol: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    target_price: float
    planned_rrr: float
    timestamp: datetime
    expiry_time: datetime
    indicators: IndicatorSnapshot
    checklist_passed: dict[str, bool]


class OrderIntent(BaseModel):
    """Approved and sized order intent ready for adapter dispatch."""

    intent_id: str = Field(default_factory=lambda: f"INT-{uuid4().hex[:8].upper()}")
    signal_id: str
    symbol: str
    direction: SignalDirection
    quantity: int
    order_type: str = "LIMIT"
    price: float
    trigger_price: float | None = None
    stop_loss: float
    target: float
    mode: TradingMode
    risk_budget: float
    estimated_costs: float
    projected_gross_profit: float


class Order(BaseModel):
    """Execution order tracking."""

    order_id: str = Field(default_factory=lambda: f"ORD-{uuid4().hex[:8].upper()}")
    intent_id: str
    symbol: str
    direction: SignalDirection
    quantity: int
    price: float
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_fill_price: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: datetime | None = None
    mode: TradingMode
    rejection_reason: str | None = None
    broker_order_id: str | None = None


class Position(BaseModel):
    """Tracked portfolio position."""

    position_id: str = Field(default_factory=lambda: f"POS-{uuid4().hex[:8].upper()}")
    order_id: str
    symbol: str
    direction: SignalDirection
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float
    target: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    entry_fees: float = 0.0
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None
    mode: TradingMode


class AccountState(BaseModel):
    """Current ledger account equity and risk headroom."""

    mode: TradingMode
    starting_capital: float
    cash_balance: float
    deployed_margin: float = 0.0
    realized_pnl_today: float = 0.0
    trades_count_today: int = 0
    max_daily_loss_budget: float
    is_daily_loss_breached: bool = False

    @property
    def total_equity(self) -> float:
        # Total equity should reflect available cash and margin used.
        # Realized P&L is already incorporated into cash_balance after a position closes,
        # so adding it again would double‑count profit. We therefore exclude it.
        return self.cash_balance + self.deployed_margin

    @property
    def daily_loss_pct(self) -> float:
        if self.starting_capital <= 0:
            return 0.0
        if self.realized_pnl_today >= 0:
            return 0.0
        return (abs(self.realized_pnl_today) / self.starting_capital) * 100.0


class AuditLogEntry(BaseModel):
    """Immutable audit trail event."""

    log_id: str = Field(default_factory=lambda: f"LOG-{uuid4().hex[:10].upper()}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    mode: TradingMode
    symbol: str | None = None
    details: dict

