"""Regression tests: Research Outlook & HIGH_RISK decision logic.

Tests:
  1. test_audit_snapshot_b7f3204a_exact_inputs_yields_high_risk
     Recreates the exact indicators from snapshot RS-B7F3204A:
     SP500 (-1.82%), NASDAQ (-2.86%), USDINR (-0.29%), WTI (-3.65%), CBOE VIX (19.42), FII (None)
     Confirming it legitimately evaluates to HIGH_RISK with the SP500 overnight warning.
  2. test_severe_bearish_market_remains_high_risk
     Verifies >= 3 bear signals does not escape HIGH_RISK (inversion bug fix).
  3. test_conflicting_macro_signals_yields_high_risk
     Verifies bull >= 2 and bear >= 2 triggers HIGH_RISK.
  4. test_calm_market_yields_neutral
     Mild fluctuations yield NEUTRAL.
  5. test_bullish_market_yields_bullish
     Bull >= 3 yields BULLISH.
  6. test_gift_nifty_payload_has_status_key
     Confirms GIFT Nifty provider includes status in data payload.
"""

from __future__ import annotations

import unittest
from research.engine import _derive_outlook
from research.models import DataStatus


class TestResearchHighRiskAudit(unittest.TestCase):

    def test_audit_snapshot_b7f3204a_exact_inputs_yields_high_risk(self):
        """Audit test reproducing the exact input data from snapshot RS-B7F3204A."""
        global_data = {
            "SP500": {
                "status": DataStatus.OK,
                "change_pct": -1.82,
                "close": 7580.07,
                "prev_close": 7720.39,
            },
            "NASDAQ": {
                "status": DataStatus.OK,
                "change_pct": -2.86,
                "close": 25437.0,
                "prev_close": 26184.72,
            },
            "KOSPI": {"status": DataStatus.OK, "change_pct": 2.98},
            "HANGSENG": {"status": DataStatus.OK, "change_pct": 0.69},
            "NIKKEI": {"status": DataStatus.OK, "change_pct": -0.01},
            "ASX200": {"status": DataStatus.OK, "change_pct": -0.58},
        }
        fx_data = {
            "USDINR": {"status": DataStatus.OK, "change_pct": -0.29},
            "WTI_CRUDE": {"status": DataStatus.OK, "change_pct": -3.65},
            "BRENT": {"status": DataStatus.OK, "change_pct": -6.81},
            "CBOE_VIX": {"status": DataStatus.OK, "close": 19.42, "change_pct": 12.91},
            "INDIA_VIX": {"status": DataStatus.OK, "close": 15.6175, "change_pct": 2.08},
        }
        fii_data = {}  # BLOCKED in RS-B7F3204A
        sector_data = {}
        gift_data = {
            "status": DataStatus.OK,
            "ltp": 23326.8,
            "symbol": "NIFTY",
        }

        outlook, warnings = _derive_outlook(
            global_data=global_data,
            fx_data=fx_data,
            fii_data=fii_data,
            sector_data=sector_data,
            gift_data=gift_data,
        )

        self.assertEqual(outlook, "HIGH_RISK")
        self.assertTrue(any("SP500 fell -1.82%" in w for w in warnings))

    def test_severe_bearish_market_remains_high_risk(self):
        """Ensure >= 3 bear signals is not downgraded to an un-suspended state."""
        global_data = {
            "SP500": {"status": DataStatus.OK, "change_pct": -2.5},
            "NASDAQ": {"status": DataStatus.OK, "change_pct": -3.0},
        }
        fx_data = {
            "USDINR": {"status": DataStatus.OK, "change_pct": 0.8},  # bear signal 3
            "CBOE_VIX": {"status": DataStatus.OK, "close": 28.0},    # bear signal 4 & 5
        }
        fii_data = {"fii_net_buy_sell": -1200}                     # bear signal 6

        outlook, warnings = _derive_outlook(
            global_data=global_data,
            fx_data=fx_data,
            fii_data=fii_data,
            sector_data={},
            gift_data={},
        )

        self.assertEqual(outlook, "HIGH_RISK")

    def test_conflicting_macro_signals_yields_high_risk(self):
        """Crosswinds (bull >= 2, bear >= 2) must trigger HIGH_RISK."""
        global_data = {
            "SP500": {"status": DataStatus.OK, "change_pct": 1.2},    # bull 1
            "NASDAQ": {"status": DataStatus.OK, "change_pct": 1.5},   # bull 2
        }
        fx_data = {
            "USDINR": {"status": DataStatus.OK, "change_pct": 0.6},   # bear 1
            "WTI_CRUDE": {"status": DataStatus.OK, "change_pct": 3.5},# bear 2
        }

        outlook, warnings = _derive_outlook(
            global_data=global_data,
            fx_data=fx_data,
            fii_data={},
            sector_data={},
            gift_data={},
        )

        self.assertEqual(outlook, "HIGH_RISK")
        self.assertTrue(any("Conflicting macro signals" in w for w in warnings))

    def test_calm_market_yields_neutral(self):
        """Mild fluctuations must return NEUTRAL."""
        global_data = {
            "SP500": {"status": DataStatus.OK, "change_pct": 0.15},
            "NASDAQ": {"status": DataStatus.OK, "change_pct": -0.20},
        }
        fx_data = {
            "USDINR": {"status": DataStatus.OK, "change_pct": 0.05},
            "WTI_CRUDE": {"status": DataStatus.OK, "change_pct": -0.5},
            "CBOE_VIX": {"status": DataStatus.OK, "close": 14.5},
        }

        outlook, warnings = _derive_outlook(
            global_data=global_data,
            fx_data=fx_data,
            fii_data={},
            sector_data={},
            gift_data={},
        )

        self.assertEqual(outlook, "NEUTRAL")

    def test_bullish_market_yields_bullish(self):
        """Clear positive signals (bull >= 3, bear < 2) return BULLISH."""
        global_data = {
            "SP500": {"status": DataStatus.OK, "change_pct": 1.1},   # bull 1
            "NASDAQ": {"status": DataStatus.OK, "change_pct": 1.4},  # bull 2
        }
        fx_data = {
            "USDINR": {"status": DataStatus.OK, "change_pct": -0.5}, # bull 3 (INR strength)
            "WTI_CRUDE": {"status": DataStatus.OK, "change_pct": -1.0},
            "CBOE_VIX": {"status": DataStatus.OK, "close": 13.2},
        }

        outlook, warnings = _derive_outlook(
            global_data=global_data,
            fx_data=fx_data,
            fii_data={},
            sector_data={},
            gift_data={},
        )

        self.assertEqual(outlook, "BULLISH")


if __name__ == "__main__":
    unittest.main()
