# Strategy Specification: VWAP + ORB + EMA + Volume Confirmation

- **Strategy Name:** VWAP + Opening Range Breakout + EMA + Volume Confirmation
- **Strategy Code:** `VWAP_ORB_EMA_VOL`
- **Version:** `1.0.0`
- **Target Market:** National Stock Exchange of India (NSE) — Cash Equity Segment
- **Target Universe:** Dynamic Nifty 50 constituents (3–5 screened daily candidates)
- **Timeframes:**
  - Daily: Market context & major support/resistance pivots
  - 15-Minute: Trend alignment & Opening Range definition (09:15–09:30 IST)
  - 5-Minute: Signal detection & execution confirmation
- **Trading Timezone:** `Asia/Kolkata` (IST)

---

## 1. Indicator Definitions & Mathematical Formulas

### 1.1 First 15-Minute Opening Range (ORB)
Between 09:15:00 and 09:29:59 IST, the market discovers its opening equilibrium across three initial 5-minute candles ($C_1, C_2, C_3$).
- **Opening Range High ($ORB_{High}$):**
  $$ORB_{High} = \max(High_{C1}, High_{C2}, High_{C3})$$
- **Opening Range Low ($ORB_{Low}$):**
  $$ORB_{Low} = \min(Low_{C1}, Low_{C2}, Low_{C3})$$
- **Opening Range Span:**
  $$\Delta_{ORB} = ORB_{High} - ORB_{Low}$$
- *Constraint:* If $\Delta_{ORB} > 3.0 \times ATR(14)$, the opening range is flagged as overly extended, increasing mean-reversion risk; breakout signals for the session are suspended.

### 1.2 Session Volume Weighted Average Price (VWAP)
VWAP calculates the volume-weighted average price from the session open (09:15 IST) up to the current 5-minute completed candle $t$:
$$VWAP_t = \frac{\sum_{i=1}^{t} (TypicalPrice_i \times Volume_i)}{\sum_{i=1}^{t} Volume_i}$$
where $TypicalPrice_i = \frac{High_i + Low_i + Close_i}{3}$.

### 1.3 20-Period Exponential Moving Average (EMA-20)
Computed on completed 5-minute closing prices:
$$EMA_{t} = \left(Close_t \times \frac{2}{20 + 1}\right) + \left(EMA_{t-1} \times \left(1 - \frac{2}{20 + 1}\right)\right)$$

### 1.4 Average True Range (ATR-14)
Measures true session volatility over 14 completed 5-minute candles:
$$TR_t = \max(High_t - Low_t, |High_t - Close_{t-1}|, |Low_t - Close_{t-1}|)$$
$$ATR_t = \frac{ATR_{t-1} \times 13 + TR_t}{14}$$

### 1.5 10-Period Volume Simple Moving Average & Relative Volume
$$SMA\_Vol_{10, t} = \frac{1}{10} \sum_{k=0}^{9} Volume_{t-k}$$
$$RVol_t = \frac{Volume_t}{SMA\_Vol_{10, t}}$$

### 1.6 Candlestick Body Ratio
Measures the directional conviction of the completed candle:
$$BodyRatio_t = \frac{|Close_t - Open_t|}{High_t - Low_t}$$

---

## 2. Long Entry Rules (Buy Setup)

All of the following 18 conditions must evaluate to `TRUE` on a completed 5-minute candle $t$ ($t \ge 4$, i.e. 09:30 IST or later):

1. **Market Session Active:** Current time is within the primary entry window (09:30:00 to 11:30:00 IST).
2. **Data Feed Healthy:** Last tick timestamp is $< 15$ seconds old; no missing 5-minute candles.
3. **Completed Candle:** Candle $t$ is fully closed; all computations use confirmed bar close data.
4. **Benchmark Index Alignment:** Nifty 50 Index current price is strictly above its own session VWAP ($Close_{Nifty} > VWAP_{Nifty}$).
5. **Market Regime Bullish:** Daily market regime engine classifies broad market as `TRENDING_BULLISH` or `MODERATE_BULLISH`.
6. **Stock Above VWAP:** Stock closing price is strictly above session VWAP ($Close_t > VWAP_t$).
7. **Stock Above EMA-20:** Stock closing price is strictly above 20 EMA ($Close_t > EMA20_t$) with $EMA20_t \ge EMA20_{t-1}$.
8. **Confirmed Breakout Level:** Candle $t$ achieves a decisive breakout above the 15-minute high ($High_t > ORB_{High}$).
9. **Breakout Close:** The completed 5-minute candle closes strictly above the breakout level ($Close_t > ORB_{High}$).
10. **Volume Surge Confirmation:** Volume of candle $t$ is at least 1.5 times the 10-period volume SMA ($RVol_t \ge 1.50$).
11. **Decisive Candle Body:** Candle body ratio is at least 50% ($BodyRatio_t \ge 0.50$), confirming buying conviction over rejection wicks.
12. **Acceptable Volatility:** Spread is $\le 0.10 \times ATR(14)_t$ and $ATR(14)_t$ is within normal operating bounds.
13. **Liquidity Check:** Average 5-minute candle volume over the previous hour exceeds ₹25,00,000 turnover.
14. **Corporate/Economic Event Blackout Clear:** Stock has no scheduled earnings, board meeting, or macro announcement within $\pm 24$ hours.
15. **Sufficient Room to Resistance:** Distance to the nearest major daily pivot resistance ($R_1$ or Previous Day High) is $\ge 1.5 \times$ the planned stop distance.
16. **Favorable Reward-to-Risk Ratio:** Planned gross reward-to-risk ratio is at least 2.0:1 ($RRR \ge 2.00$).
17. **Capital & Position Sizing Approved:** Calculated position quantity $Q \ge 1$ based on available cash and risk budget.
18. **Independent Risk Check Passed:** Daily loss limit, max trade count, and max open position checks all pass.

---

## 3. Short Entry Rules (Intraday Sell Setup)

For intraday shorting in the cash segment (MIS product type), all rules mirror the long setup:

1. **Market Session Active:** 09:30:00 to 11:30:00 IST.
2. **Data Feed Healthy:** Connection latency $< 15$ seconds.
3. **Completed Candle:** Closed 5-minute candle.
4. **Benchmark Index Alignment:** Nifty 50 Index is strictly below its own session VWAP ($Close_{Nifty} < VWAP_{Nifty}$).
5. **Market Regime Bearish:** Daily market regime is `TRENDING_BEARISH` or `MODERATE_BEARISH`.
6. **Stock Below VWAP:** Stock closing price is strictly below session VWAP ($Close_t < VWAP_t$).
7. **Stock Below EMA-20:** Stock closing price is strictly below 20 EMA ($Close_t < EMA20_t$) with $EMA20_t \le EMA20_{t-1}$.
8. **Confirmed Breakdown Level:** Candle $t$ achieves a decisive breakdown below the 15-minute low ($Low_t < ORB_{Low}$).
9. **Breakdown Close:** Candle $t$ closes strictly below the breakdown level ($Close_t < ORB_{Low}$).
10. **Volume Surge Confirmation:** $RVol_t \ge 1.50$.
11. **Decisive Candle Body:** Bearish candle body ratio $\ge 0.50$ ($Open_t > Close_t$).
12. **Acceptable Volatility:** Spread is $\le 0.10 \times ATR(14)_t$.
13. **Liquidity Check:** Stock turnover exceeds liquidity thresholds.
14. **Corporate Event Blackout Clear:** No conflicting announcements.
15. **Sufficient Room to Support:** Distance to nearest major daily pivot support ($S_1$ or Previous Day Low) is $\ge 1.5 \times$ stop distance.
16. **Favorable Reward-to-Risk:** $RRR \ge 2.00$.
17. **Capital & Short Eligibility Approved:** Broker cash segment intraday shorting permitted and quantity $Q \ge 1$.
18. **Independent Risk Check Passed:** All portfolio risk checks pass.

---

## 4. Stop-Loss & Target Rules

### 4.1 Stop-Loss Mechanics
- **Structural Long Stop:**
  $$StopLoss_{Long} = \min(Low_{SignalCandle}, ORB_{High} - 0.05\% \times EntryPrice)$$
  *Floor:* In no scenario can the stop distance exceed $1.5 \times ATR(14)$. If the structural stop requires a distance $> 1.5 \times ATR(14)$, the trade is rejected as having an unfavorable risk footprint.
- **Structural Short Stop:**
  $$StopLoss_{Short} = \max(High_{SignalCandle}, ORB_{Low} + 0.05\% \times EntryPrice)$$

### 4.2 Profit Target
- The initial planned profit target is mathematically fixed at exactly 2.0 times the initial risk distance ($2.0R$):
  - **Long Target:** $Target_{Long} = EntryPrice + 2.0 \times (EntryPrice - StopLoss_{Long})$
  - **Short Target:** $Target_{Short} = EntryPrice - 2.0 \times (StopLoss_{Short} - EntryPrice)$

---

## 5. Execution, Signal Expiry & Exit Policies

### 5.1 Order Type and Routing
- To avoid slippage and prevent market execution penalties, signals generate **STOP-LIMIT** orders for breakout triggers, or **LIMIT** orders with a price buffer equal to 1 tick size ($₹0.05$).
- Market orders without price protection are strictly prohibited.

### 5.2 Signal Expiry
- A signal candidate order that remains unfilled after **two subsequent completed 5-minute candles** (10 minutes total elapsed time) is automatically cancelled by the execution engine.

### 5.3 Time-Based Square-Off (EOD)
- **15:00:00 IST:** Controlled square-off begins. No new orders may be placed under any circumstance.
- **15:05:00 IST:** Active trailing stops are cancelled and open positions are closed using protective limit orders.
- **15:20:00 IST:** Post-market reconciliation verifies all positions are net zero.

---

## 6. Comprehensive No-Trade Conditions (Veto Triggers)

The system enforces a strict zero-trade policy under any of the following conditions:
1. **Time Outside Entry Window:** Time $< 09:30$ IST or $> 11:30$ IST.
2. **Missing Market Data:** Any gap $> 15$ seconds in streaming ticks or missing candle records.
3. **Nifty Indecision:** Nifty 50 fluctuating within $\pm 0.15\%$ of its session VWAP (choppy market).
4. **India VIX Anomaly:** India VIX $> 24.0$ (excessive market-wide shock volatility) or India VIX spiking $> 10\%$ intraday.
5. **Wide Bid-Ask Spread:** Current bid-ask spread on candidate stock $> 0.10\%$ of CMP.
6. **Risk Limits Breached:** Account has already executed 2 trades today, or daily loss $\ge 1.0\%$ of starting equity.
7. **Active Position Exists:** Current system already holds 1 open position (concurrency limit = 1).
8. **Economic Infeasibility:** Total calculated statutory and broker transaction fees exceed 15% of the projected gross profit.
9. **Unresolved Broker / Order State:** Prior order timed out, unconfirmed fill, or disconnected session.
