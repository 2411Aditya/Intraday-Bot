"""Dynamic Stock Screening and Candidate Ranking Engine."""

from pydantic import BaseModel
from backend.app.models.domain import Candle, Instrument, MarketTick


class ScreenerCandidateResult(BaseModel):
    """Detailed candidate screening diagnostic report."""

    symbol: str
    composite_score: float
    passed: bool
    rejection_reasons: list[str]
    atr_pct: float
    avg_turnover_cr: float
    bid_ask_spread_pct: float
    affordable_quantity: int


class DynamicStockScreener:
    """Executes the daily 14-step quantitative screening pipeline on Nifty 50 constituents."""

    # Baseline thresholds
    MIN_DAILY_TURNOVER_CR: float = 50.0  # ₹50 Crores turnover
    MIN_DAILY_VOLUME: int = 1_000_000     # 1M shares daily
    MIN_ATR_PCT: float = 1.0              # Min 1.0% ATR
    MAX_ATR_PCT: float = 4.0              # Max 4.0% ATR
    MAX_SPREAD_PCT: float = 0.10          # Max 0.10% spread

    @classmethod
    def evaluate_candidate(
        cls,
        instrument: Instrument,
        daily_candles: list[Candle],
        quote: MarketTick,
        account_capital: float,
        sector_score: float = 75.0,
    ) -> ScreenerCandidateResult:
        """Evaluates a single stock against all screening metrics and capital affordability."""
        rejection_reasons: list[str] = []

        if len(daily_candles) < 5:
            return ScreenerCandidateResult(
                symbol=instrument.symbol,
                composite_score=0.0,
                passed=False,
                rejection_reasons=["INSUFFICIENT_HISTORICAL_DATA"],
                atr_pct=0.0,
                avg_turnover_cr=0.0,
                bid_ask_spread_pct=0.0,
                affordable_quantity=0,
            )

        # 1. Turnover & Volume Metrics (trailing 20 days or available)
        avg_vol = sum(c.volume for c in daily_candles) / len(daily_candles)
        latest_close = daily_candles[-1].close
        avg_turnover_rs = avg_vol * latest_close
        avg_turnover_cr = round(avg_turnover_rs / 10_000_000.0, 2)

        if avg_vol < cls.MIN_DAILY_VOLUME:
            rejection_reasons.append(f"LOW_AVERAGE_VOLUME_{int(avg_vol)}")

        if avg_turnover_cr < cls.MIN_DAILY_TURNOVER_CR:
            rejection_reasons.append(f"LOW_DAILY_TURNOVER_{avg_turnover_cr}CR")

        # 2. Daily Volatility (ATR%)
        tr_list = [
            max(
                daily_candles[i].high - daily_candles[i].low,
                abs(daily_candles[i].high - daily_candles[i - 1].close),
                abs(daily_candles[i].low - daily_candles[i - 1].close),
            )
            for i in range(1, len(daily_candles))
        ]
        atr = sum(tr_list) / len(tr_list) if tr_list else 1.0
        atr_pct = round((atr / latest_close) * 100.0, 2)

        if atr_pct < cls.MIN_ATR_PCT:
            rejection_reasons.append(f"INSUFFICIENT_VOLATILITY_{atr_pct}PCT")
        elif atr_pct > cls.MAX_ATR_PCT:
            rejection_reasons.append(f"EXCESSIVE_VOLATILITY_{atr_pct}PCT")

        # 3. Bid-Ask Spread Viability
        spread_pct = round(quote.spread_pct, 3)
        if spread_pct > cls.MAX_SPREAD_PCT:
            rejection_reasons.append(f"WIDE_BID_ASK_SPREAD_{spread_pct}PCT")

        # 4. Capital Affordability Check (1:1 Cash Deployment)
        # Sizing formula: min(Cash / Price, (Capital * 0.005) / (Price * 0.007))
        risk_per_trade = account_capital * 0.005
        est_stop_distance = max(latest_close * 0.007, 0.05)
        qty_risk = int(risk_per_trade // est_stop_distance)
        qty_cash = int(account_capital // latest_close)
        affordable_qty = min(qty_risk, qty_cash)

        if affordable_qty < 1:
            rejection_reasons.append(
                f"UNAFFORDABLE_FOR_CAPITAL_{int(account_capital)}_PRICE_{latest_close}"
            )

        # 5. Composite Scoring (0 to 100)
        # 35% Sector RS, 25% Volume Turnover, 25% ATR sweetspot (1.8 - 2.5%), 15% Spread
        vol_score = min(avg_turnover_cr / 200.0, 1.0) * 100.0
        # Optimal ATR ~2.2%
        atr_score = max(0.0, 100.0 - (abs(atr_pct - 2.2) * 40.0))
        spread_score = max(0.0, 100.0 - (spread_pct * 1000.0))

        composite_score = round(
            (0.35 * sector_score)
            + (0.25 * vol_score)
            + (0.25 * atr_score)
            + (0.15 * spread_score),
            2,
        )

        passed = len(rejection_reasons) == 0

        return ScreenerCandidateResult(
            symbol=instrument.symbol,
            composite_score=composite_score if passed else 0.0,
            passed=passed,
            rejection_reasons=rejection_reasons,
            atr_pct=atr_pct,
            avg_turnover_cr=avg_turnover_cr,
            bid_ask_spread_pct=spread_pct,
            affordable_quantity=affordable_qty,
        )

    @classmethod
    def screen_universe(
        cls,
        universe: list[tuple[Instrument, list[Candle], MarketTick]],
        account_capital: float,
        target_count: int = 5,
    ) -> list[ScreenerCandidateResult]:
        """Screens all universe equities and returns top ranked candidates."""
        results: list[ScreenerCandidateResult] = []

        for inst, daily_candles, quote in universe:
            res = cls.evaluate_candidate(inst, daily_candles, quote, account_capital)
            results.append(res)

        # Sort: passed first, then by composite score descending
        results.sort(key=lambda r: (r.passed, r.composite_score), reverse=True)
        return results[:target_count]

