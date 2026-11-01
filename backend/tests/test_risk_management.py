"""Unit Tests for Independent Risk Management and Position Sizing."""

from datetime import datetime, timedelta
import zoneinfo
from backend.app.core.config import TradingMode
from backend.app.models.domain import (
    AccountState,
    IndicatorSnapshot,
    MarketTick,
    Position,
    PositionStatus,
    Signal,
    SignalDirection,
)
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.risk.engine import RiskEngine
from backend.app.risk.position_sizer import PositionSizer


def test_position_sizing_cash_and_risk_budget():
    """Test that sizing respects 0.5% risk and 1:1 cash affordability."""
    # ₹10,000 equity, ₹10,000 cash, Entry 1000, Stop 990 (Risk per share = 10)
    # Risk budget = 10,000 * 0.005 = 50. Qty by risk = 50 / 10 = 5.
    # Qty by cash = 10,000 / 1000 = 10.
    # Final = min(5, 10) = 5 shares.
    res = PositionSizer.calculate_size(
        trading_equity=10000.0,
        available_cash=10000.0,
        entry_price=1000.0,
        stop_loss=990.0,
        risk_pct=0.5,
    )
    assert res.is_valid is True
    assert res.quantity == 5
    assert res.risk_budget == 50.0
    assert res.capital_deployed == 5000.0


def test_position_sizing_cash_constrained():
    """Test that sizing limits quantity when cash is smaller than risk-allowed quantity."""
    # ₹10,000 equity, but only ₹2,000 cash available. Entry 1000, Stop 995 (Risk = 5).
    # Qty by risk = 50 / 5 = 10.
    # Qty by cash = 2000 / 1000 = 2.
    # Final = 2.
    res = PositionSizer.calculate_size(
        trading_equity=10000.0,
        available_cash=2000.0,
        entry_price=1000.0,
        stop_loss=995.0,
        risk_pct=0.5,
    )
    assert res.is_valid is True
    assert res.quantity == 2


def test_economic_cost_drag_rejection():
    """Test that trades where statutory costs exceed 15% of gross profit are vetoed."""
    # 1 share with entry 100, target 102 (gross profit = ₹2.0)
    # Round-trip brokerage + taxes will be ~₹40. Cost drag is huge.
    costs = TransactionCostModel.calculate_roundtrip_costs(
        quantity=1,
        entry_price=100.0,
        exit_price=102.0,
    )
    is_viable, reason = TransactionCostModel.is_economically_viable(costs)
    assert is_viable is False
    assert "EXCEEDS_15PCT" in reason


def test_risk_engine_daily_loss_limit():
    """Risk engine must reject entries if daily loss reaches 1.0%."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime(2026, 10, 29, 10, 0, tzinfo=ist)

    ind = IndicatorSnapshot(
        symbol="SBIN",
        timestamp=now_ist,
        vwap=800.0,
        ema_20=800.0,
        atr_14=6.0,
        orb_high=805.0,
        orb_low=795.0,
        volume_sma_10=10000,
        relative_volume=2.0,
        body_ratio=0.6,
    )
    sig = Signal(
        symbol="SBIN",
        direction=SignalDirection.BUY,
        entry_price=806.0,
        stop_loss=802.0,
        target_price=814.0,
        planned_rrr=2.0,
        timestamp=now_ist,
        expiry_time=now_ist + timedelta(minutes=10),
        indicators=ind,
        checklist_passed={},
    )
    quote = MarketTick(symbol="SBIN", ltp=806.0, bid=805.95, ask=806.05, volume=50000, timestamp=now_ist)

    account = AccountState(
        mode=TradingMode.PAPER,
        starting_capital=10000.0,
        cash_balance=9890.0,
        realized_pnl_today=-110.0,  # 1.1% loss (exceeds 1.0% cap)
        trades_count_today=1,
        max_daily_loss_budget=100.0,
        is_daily_loss_breached=True,
    )

    risk_engine = RiskEngine()
    decision = risk_engine.evaluate_signal(sig, account, quote, [], current_execution_time=now_ist)
    assert decision.approved is False
    assert "DAILY_LOSS_LIMIT_BREACHED" in decision.rejection_reason


def test_risk_engine_max_trades_limit():
    """Risk engine must reject entries if 2 trades have already completed today."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = datetime(2026, 10, 29, 10, 0, tzinfo=ist)
    ind = IndicatorSnapshot(
        symbol="SBIN",
        timestamp=now_ist,
        vwap=800.0,
        ema_20=800.0,
        atr_14=6.0,
        orb_high=805.0,
        orb_low=795.0,
        volume_sma_10=10000,
        relative_volume=2.0,
        body_ratio=0.6,
    )
    sig = Signal(
        symbol="SBIN",
        direction=SignalDirection.BUY,
        entry_price=806.0,
        stop_loss=802.0,
        target_price=814.0,
        planned_rrr=2.0,
        timestamp=now_ist,
        expiry_time=now_ist + timedelta(minutes=10),
        indicators=ind,
        checklist_passed={},
    )
    quote = MarketTick(symbol="SBIN", ltp=806.0, bid=805.95, ask=806.05, volume=50000, timestamp=now_ist)

    account = AccountState(
        mode=TradingMode.PAPER,
        starting_capital=10000.0,
        cash_balance=10000.0,
        realized_pnl_today=50.0,
        trades_count_today=2,  # Already executed 2 trades today
        max_daily_loss_budget=100.0,
    )

    risk_engine = RiskEngine()
    decision = risk_engine.evaluate_signal(sig, account, quote, [], current_execution_time=now_ist)
    assert decision.approved is False
    assert "MAX_DAILY_TRADES_EXCEEDED" in decision.rejection_reason

