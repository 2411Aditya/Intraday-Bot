# Fee Schedule and Versioned Charges for Angel One SmartAPI
"""
This module defines a configurable, versioned fee schedule used by the
TransactionCostModel.  By keeping the charges in a separate data class we can
easily update them when Angel One changes its pricing without touching the
cost‑calculation logic.

The schedule can be overridden via environment variables (e.g. for testing
different fee regimes) and is versioned so that historic back‑tests can retain the
exact parameters that were in effect at the time.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass(frozen=True)
class FeeSchedule:
    """Container for all fee‑related constants.

    The default values reflect Angel One's publicly documented rates as of
    2026‑10‑30.
    """

    version: str = "v1.0"
    # Brokerage – flat ₹20 OR 0.03% of turnover whichever is lower
    max_brokerage_per_order: float = 20.0
    brokerage_rate: float = 0.0003  # 0.03%
    # Statutory charges
    stt_sell_rate: float = 0.00025  # 0.025% on sell side only
    exchange_turnover_rate: float = 0.0000297  # 0.00297% both legs
    sebi_turnover_rate: float = 0.000001  # ₹10 per crore (0.0001%)
    stamp_duty_buy_rate: float = 0.00003  # 0.003% on buy side only
    gst_rate: float = 0.18  # 18% on (brokerage + exchange + SEBI)
    default_slippage_rate: float = 0.0005  # 0.05% conservative slippage
    # Economic viability threshold (max cost‑to‑reward ratio)
    max_acceptable_cost_drag_ratio: float = 0.15

    @staticmethod
    def load_from_env() -> "FeeSchedule":
        """Load overrides from environment variables if present.

        This is useful for testing alternative fee regimes without modifying the
        source code.
        """
        return FeeSchedule(
            version=os.getenv("FEE_SCHEDULE_VERSION", "v1.0"),
            max_brokerage_per_order=float(os.getenv("FEE_MAX_BROKERAGE", "20.0")),
            brokerage_rate=float(os.getenv("FEE_BROKERAGE_RATE", "0.0003")),
            stt_sell_rate=float(os.getenv("FEE_STT_SELL_RATE", "0.00025")),
            exchange_turnover_rate=float(os.getenv("FEE_EXCHANGE_TURNOVER_RATE", "0.0000297")),
            sebi_turnover_rate=float(os.getenv("FEE_SEBI_TURNOVER_RATE", "0.000001")),
            stamp_duty_buy_rate=float(os.getenv("FEE_STAMP_DUTY_BUY_RATE", "0.00003")),
            gst_rate=float(os.getenv("FEE_GST_RATE", "0.18")),
            default_slippage_rate=float(os.getenv("FEE_SLIPPAGE_RATE", "0.0005")),
            max_acceptable_cost_drag_ratio=float(os.getenv("FEE_MAX_COST_DRAG", "0.15")),
        )

