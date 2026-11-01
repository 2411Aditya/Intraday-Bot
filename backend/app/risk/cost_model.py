"""NSE Intraday Cash Equity Transaction Cost and Taxation Model."""

from pydantic import BaseModel


class TransactionCostBreakdown(BaseModel):
    """Detailed statutory and brokerage cost breakdown."""

    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    modeled_slippage: float
    total_costs: float
    cost_to_reward_ratio: float


class TransactionCostModel:
    """Calculates exact statutory taxes, exchange fees, and Angel One brokerage for NSE cash intraday."""

    # Angel One iTrade Prime: flat ₹20 or 0.03% per executed order (whichever is lower)
    MAX_BROKERAGE_PER_ORDER: float = 20.0
    BROKERAGE_RATE: float = 0.0003  # 0.03%

    # Statutory charges on NSE Cash Intraday
    STT_SELL_RATE: float = 0.00025          # 0.025% on Sell side only
    EXCHANGE_TURNOVER_RATE: float = 0.0000297 # 0.00297% on both Buy and Sell
    SEBI_TURNOVER_RATE: float = 0.000001     # ₹10 per crore (0.0001%)
    STAMP_DUTY_BUY_RATE: float = 0.00003     # 0.003% on Buy side only
    GST_RATE: float = 0.18                   # 18% on (Brokerage + Exchange + SEBI)
    DEFAULT_SLIPPAGE_RATE: float = 0.0005    # 0.05% conservative modeled slippage

    # Economic viability threshold
    MAX_ACCEPTABLE_COST_DRAG_RATIO: float = 0.15  # Max 15% of gross reward

    @classmethod
    def calculate_roundtrip_costs(
        cls,
        quantity: int,
        entry_price: float,
        exit_price: float,
        slippage_rate: float = DEFAULT_SLIPPAGE_RATE,
    ) -> TransactionCostBreakdown:
        """Calculates exact round-trip fees for a cash intraday trade."""
        if quantity <= 0 or entry_price <= 0 or exit_price <= 0:
            return TransactionCostBreakdown(
                brokerage=0.0,
                stt=0.0,
                exchange_charges=0.0,
                sebi_charges=0.0,
                stamp_duty=0.0,
                gst=0.0,
                modeled_slippage=0.0,
                total_costs=0.0,
                cost_to_reward_ratio=0.0,
            )

        buy_turnover = quantity * entry_price
        sell_turnover = quantity * exit_price
        total_turnover = buy_turnover + sell_turnover

        # 1. Brokerage (both legs)
        buy_brokerage = max(cls.MAX_BROKERAGE_PER_ORDER, buy_turnover * cls.BROKERAGE_RATE)
        sell_brokerage = max(cls.MAX_BROKERAGE_PER_ORDER, sell_turnover * cls.BROKERAGE_RATE)
        total_brokerage = round(buy_brokerage + sell_brokerage, 2)

        # 2. STT (Sell side only for equity intraday)
        stt = round(sell_turnover * cls.STT_SELL_RATE, 2)

        # 3. Exchange Turnover Charge
        exchange_charges = round(total_turnover * cls.EXCHANGE_TURNOVER_RATE, 2)

        # 4. SEBI Turnover Fee
        sebi_charges = round(total_turnover * cls.SEBI_TURNOVER_RATE, 2)

        # 5. Stamp Duty (Buy side only)
        stamp_duty = round(buy_turnover * cls.STAMP_DUTY_BUY_RATE, 2)

        # 6. GST (18% on Brokerage + Exchange + SEBI)
        taxable_services = total_brokerage + exchange_charges + sebi_charges
        gst = round(taxable_services * cls.GST_RATE, 2)

        # 7. Conservative Modeled Slippage
        slippage = round(total_turnover * slippage_rate, 2)

        total_costs = round(
            total_brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + slippage,
            2,
        )

        gross_profit = abs(exit_price - entry_price) * quantity
        crr = round(total_costs / gross_profit, 3) if gross_profit > 0 else 1.0

        return TransactionCostBreakdown(
            brokerage=total_brokerage,
            stt=stt,
            exchange_charges=exchange_charges,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            modeled_slippage=slippage,
            total_costs=total_costs,
            cost_to_reward_ratio=crr,
        )

    @classmethod
    def calculate_leg_costs(cls, quantity: int, price: float, side: str = "BUY") -> float:
        """Calculates exact statutory and brokerage costs for a single execution leg."""
        if quantity <= 0 or price <= 0:
            return 0.0
        turnover = quantity * price
        side = side.upper()

        # 1. Brokerage: flat ₹20 or 0.03% (whichever is lower)
        brokerage = max(cls.MAX_BROKERAGE_PER_ORDER, turnover * cls.BROKERAGE_RATE)

        # 2. Turnover charges
        exchange = turnover * cls.EXCHANGE_TURNOVER_RATE
        sebi = turnover * cls.SEBI_TURNOVER_RATE
        gst = (brokerage + exchange + sebi) * cls.GST_RATE

        # 3. Leg-specific taxes
        if side in ("BUY", "LONG"):
            stt = 0.0
            stamp_duty = turnover * cls.STAMP_DUTY_BUY_RATE
        else:
            stt = turnover * cls.STT_SELL_RATE
            stamp_duty = 0.0

        total = brokerage + exchange + sebi + gst + stt + stamp_duty
        return round(total, 2)

    @classmethod
    def is_economically_viable(cls, breakdown: TransactionCostBreakdown) -> tuple[bool, str]:
        """Validates that transaction costs do not consume more than 15% of the gross profit."""
        if breakdown.cost_to_reward_ratio > cls.MAX_ACCEPTABLE_COST_DRAG_RATIO:
            return (
                False,
                f"COST_DRAG_TOO_HIGH_{round(breakdown.cost_to_reward_ratio * 100, 1)}PCT_EXCEEDS_15PCT",
            )
        return True, "ECONOMICALLY_VIABLE"

