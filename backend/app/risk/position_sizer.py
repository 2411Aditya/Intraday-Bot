"""Capital-Aware Position Sizing Engine."""

from pydantic import BaseModel


class SizingResult(BaseModel):
    """Position sizing outcome."""

    quantity: int
    risk_budget: float
    risk_per_share: float
    capital_deployed: float
    is_valid: bool
    rejection_reason: str | None = None


class PositionSizer:
    """Calculates conservative fixed-fractional position sizes adhering to 1:1 cash affordability."""

    @classmethod
    def calculate_size(
        cls,
        trading_equity: float,
        available_cash: float,
        entry_price: float,
        stop_loss: float,
        risk_pct: float = 0.5,
    ) -> SizingResult:
        """Determines quantity based on risk budget and 1:1 cash availability without leverage."""
        if trading_equity <= 0 or available_cash <= 0 or entry_price <= 0:
            return SizingResult(
                quantity=0,
                risk_budget=0.0,
                risk_per_share=0.0,
                capital_deployed=0.0,
                is_valid=False,
                rejection_reason="INVALID_ACCOUNT_EQUITY_OR_PRICE",
            )

        # 1. Dollar risk budget (e.g. 0.5% of total equity)
        risk_budget = round(trading_equity * (risk_pct / 100.0), 2)

        # 2. Structural risk per share
        risk_per_share = round(abs(entry_price - stop_loss), 2)
        if risk_per_share < 0.05:  # Less than 1 tick size
            return SizingResult(
                quantity=0,
                risk_budget=risk_budget,
                risk_per_share=risk_per_share,
                capital_deployed=0.0,
                is_valid=False,
                rejection_reason="STOP_DISTANCE_LESS_THAN_TICK_SIZE",
            )

        # 3. Constraint 1: Maximum quantity allowed by risk budget
        qty_by_risk = int(risk_budget // risk_per_share)

        # 4. Constraint 2: Maximum quantity allowed by available cash (1:1 cash allocation, no leverage)
        qty_by_cash = int(available_cash // entry_price)

        final_qty = min(qty_by_risk, qty_by_cash)

        if final_qty < 1:
            reason = (
                f"INSUFFICIENT_FUNDS_FOR_SINGLE_SHARE: CashQty={qty_by_cash}, RiskQty={qty_by_risk}"
            )
            return SizingResult(
                quantity=0,
                risk_budget=risk_budget,
                risk_per_share=risk_per_share,
                capital_deployed=0.0,
                is_valid=False,
                rejection_reason=reason,
            )

        capital_deployed = round(final_qty * entry_price, 2)

        return SizingResult(
            quantity=final_qty,
            risk_budget=risk_budget,
            risk_per_share=risk_per_share,
            capital_deployed=capital_deployed,
            is_valid=True,
            rejection_reason=None,
        )

