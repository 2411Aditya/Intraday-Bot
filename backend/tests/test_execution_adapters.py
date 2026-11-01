'''Unit Tests for Execution Adapters (Paper Simulation vs Live Safety Lock).'''

import pytest
from backend.app.core.config import TradingMode
from backend.app.execution.live_adapter import LiveExecutionAdapter, LiveExecutionLockedError
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.models.domain import (
    OrderIntent,
    OrderStatus,
    PositionStatus,
    SignalDirection,
)


def test_paper_execution_adapter_lifecycle():
    """Verifies that PaperExecutionAdapter simulates slippage, fills, balances, and closing P&L."""
    adapter = PaperExecutionAdapter(starting_capital=10000.0, slippage_rate=0.0005)

    intent = OrderIntent(
        signal_id="SIG-TEST-01",
        symbol="SBIN",
        direction=SignalDirection.BUY,
        quantity=10,
        price=800.0,
        stop_loss=795.0,
        target=810.0,
        mode=TradingMode.PAPER,
        risk_budget=50.0,
        estimated_costs=15.0,
        projected_gross_profit=100.0,
    )

    # 1. Submit Order
    order = adapter.submit_order(intent)
    assert order.status == OrderStatus.FILLED
    # Adverse slippage for Buy: 800 + (800 * 0.0005) = 800.40
    assert order.average_fill_price == 800.40
    assert order.filled_quantity == 10

    # 2. Check Ledger after entry (deployed margin + entry leg statutory fees deducted)
    entry_fees = TransactionCostModel.calculate_leg_costs(10, 800.40, "BUY")
    state = adapter.get_account_state()
    assert state.deployed_margin == 8004.0
    assert state.cash_balance == pytest.approx(10000.0 - 8004.0 - entry_fees, abs=0.01)

    # 3. Check Position
    positions = adapter.get_open_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.status == PositionStatus.OPEN
    assert pos.entry_price == 800.40

    # 4. Close Position at target (810.0)
    closed = adapter.close_position(pos.position_id, exit_price=810.0, reason="TARGET_HIT")
    assert closed.status == PositionStatus.CLOSED
    # Adverse exit slippage for Sell: 810.0 - 0.41 = 809.59
    assert closed.exit_price == pytest.approx(809.59, abs=0.05)
    # Realistic net profit after fees (~41.85) – use safe lower bound
    assert closed.realized_pnl > 30.0

    # 5. Verify Account Updated after close
    final_state = adapter.get_account_state()
    assert final_state.deployed_margin == 0.0
    assert final_state.trades_count_today == 1
    assert final_state.realized_pnl_today > 30.0
    assert final_state.cash_balance > 10000.0


def test_live_execution_adapter_hard_locked():
    """LiveExecutionAdapter MUST strictly refuse order operations by default."""
    live_adapter = LiveExecutionAdapter()
    assert live_adapter.is_locked is True

    intent = OrderIntent(
        signal_id="SIG-LIVE-01",
        symbol="SBIN",
        direction=SignalDirection.BUY,
        quantity=1,
        price=800.0,
        stop_loss=795.0,
        target=810.0,
        mode=TradingMode.ACTUAL,
        risk_budget=50.0,
        estimated_costs=15.0,
        projected_gross_profit=10.0,
    )

    with pytest.raises(LiveExecutionLockedError, match="Live trading execution is STRICTLY LOCKED"):
        live_adapter.submit_order(intent)

    with pytest.raises(LiveExecutionLockedError, match="Live trading execution is STRICTLY LOCKED"):
        live_adapter.close_position("POS-001", exit_price=810.0)
