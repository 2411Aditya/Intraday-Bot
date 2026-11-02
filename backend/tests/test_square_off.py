# Test compulsory intraday square‑off at 15:15 IST

import datetime
import zoneinfo
from unittest import mock

from backend.app.trading_engine import TradingEngine
from backend.app.execution.paper_adapter import PaperExecutionAdapter
from backend.app.market_data.mock_provider import MockMarketDataProvider
from backend.app.risk.engine import RiskEngine
from backend.app.risk.cost_model import TransactionCostModel
from backend.app.core.config import TradingMode
from backend.app.models.domain import SignalDirection, Position


def make_engine_with_open_position(current_time: datetime.datetime):
    # Mock market data to return a price for the symbol
    mock_md = MockMarketDataProvider()
    mock_md.get_current_quote = mock.Mock(return_value=type("MT", (), {"ltp": 100.0}))

    # Execution adapter with a single open BUY position
    exec_adapter = PaperExecutionAdapter()
    # Directly inject a Position with required fields into the adapter's store.
    pos = Position(
        position_id="pos-1",
        order_id="ord-1",
        symbol="TCS",
        direction=SignalDirection.BUY,
        entry_price=95.0,
        current_price=95.0,
        stop_loss=90.0,
        target=110.0,
        quantity=10,
        entry_time=current_time - datetime.timedelta(minutes=30),
        mode=TradingMode.PAPER,
    )
    exec_adapter.positions[pos.position_id] = pos

    # Risk engine (not used for square‑off)
    risk_engine = RiskEngine(TransactionCostModel())

    engine = TradingEngine(mock_md, risk_engine, exec_adapter)
    return engine, exec_adapter


def test_compulsory_square_off_at_1515_ist():
    # Simulate time just after 15:15 IST on a trading day
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    current_time = datetime.datetime(2026, 11, 2, 15, 16, 0, tzinfo=ist)

    engine, exec_adapter = make_engine_with_open_position(current_time)

    # Provide a quote dict matching the open position
    quotes = {"TCS": 100.0}

    closed = engine.evaluate_open_positions(quotes, current_time=current_time)

    # Exactly one position should be closed via square‑off
    assert len(closed) == 1
    closed_pos = closed[0]
    assert closed_pos.position_id == "pos-1"
    # Reason must be INTRADAY_SQUARE_OFF
    assert closed_pos.exit_reason == "INTRADAY_SQUARE_OFF"
    # Exit price should be the current quote supplied
    assert closed_pos.exit_price == 100.0

