# Zerodha Varsity Research & Algorithmic Trading Systems Analysis

## 1. Executive Summary & Document Purpose
This document synthesizes core quantitative trading principles, technical analysis foundations, risk management frameworks, and execution mechanics extracted from **Zerodha Varsity** (India's premier financial education resource for market participants), alongside regulatory standards from the **Securities and Exchange Board of India (SEBI)** and the **National Stock Exchange of India (NSE)**.

The objective is to establish an academically grounded, mathematically rigorous, and compliance-adherent foundation for our cloud-based automated intraday trading platform. In accordance with sound quantitative engineering practices, concepts extracted from Varsity inform system architecture, risk parameters, and hypothesis formulation—they are never assumed to be inherently profitable without empirical out-of-sample backtesting and forward paper-trading validation.

---

## 2. Sources Reviewed

| Module / Resource | Official Title | Scope & Chapters Examined | Primary Focus for System Design | Source URL | Access Date |
|---|---|---|---|---|---|
| **Module 1** | *Introduction to Stock Markets* | Ch. 1–15: Market ecosystem, clearing corporations, trade lifecycle, circuit filters, market timing. | Settlement cycles (T+1), order types (LIMIT, STOP-LOSS), price bands, exchange mechanisms. | https://zerodha.com/varsity/module/introduction-to-stock-markets/ | 2026-10-29 |
| **Module 2** | *Technical Analysis* | Ch. 1–22: Candlestick patterns, Dow Theory, Support/Resistance, Moving Averages, Indicators (VWAP, ATR, RSI), Volume analysis. | 5-min & 15-min candle formation, VWAP benchmark, 20 EMA trend confirmation, breakout candle body ratios, RVol. | https://zerodha.com/varsity/module/technical-analysis/ | 2026-10-29 |
| **Module 3** | *Fundamental Analysis* | Ch. 1–16: Financial statements, corporate actions, earnings announcements. | Event blackouts: excluding stocks undergoing earnings releases, stock splits, or major corporate actions. | https://zerodha.com/varsity/module/fundamental-analysis/ | 2026-10-29 |
| **Module 4** | *Futures Trading* | Ch. 1–13: Leverage, margin requirements, open interest, intraday shorting mechanics. | Understanding intraday short selling mechanics in the cash segment (MIS product code, borrowing/settlement rules). | https://zerodha.com/varsity/module/futures-trading/ | 2026-10-29 |
| **Module 5** | *Options Theory* | Ch. 1–23: Options fundamentals, Greeks, volatility. | High-volatility regimes; India VIX implications on cash equity intraday movement. | https://zerodha.com/varsity/module/option-theory/ | 2026-10-29 |
| **Module 6** | *Risk Management & Trading Psychology* | Ch. 1–14: Risk per trade, Risk-to-Reward ratio (RRR), position sizing formulas, drawdown control, emotional biases. | Independent risk engine architecture, 0.5% risk cap per trade, 1.0% daily stop, RRR >= 2.0, trade limit caps. | https://zerodha.com/varsity/module/risk-management/ | 2026-10-29 |
| **Module 7** | *Trading Systems* | Ch. 1–10: Strategy design, backtesting methodologies, parameter optimization, curve fitting hazards, trade journaling. | Walk-forward validation, zero look-ahead bias, trade journaling, out-of-sample evaluation. | https://zerodha.com/varsity/module/trading-systems/ | 2026-10-29 |
| **Module 10** | *Markets & Taxation* | Ch. 1–9: Speculative business income (intraday equity), STT, GST, Exchange turnover fees, Stamp duty, SEBI turnover charges. | Accurate transaction cost calculation engine for cash intraday equity. | https://zerodha.com/varsity/module/markets-and-taxation/ | 2026-10-29 |
| **Varsity Video Series** | *Technical Analysis & Trading Checklists* | Video Lessons on Support/Resistance, Volume Spread Analysis, Trade Checklists. | Systematic pre-flight checklist verification before order placement. | https://zerodha.com/varsity/videos/ | 2026-10-29 |

---

## 3. Core Concepts Extracted & Architectural Mapping

### A. The Intraday Benchmark: Volume Weighted Average Price (VWAP)
- **Concept:** VWAP calculates the true cumulative average price of an asset weighted by the volume traded at each price point during the active trading session ($VWAP = \frac{\sum (Price \times Volume)}{\sum Volume}$). It resets daily at 09:15 IST.
- **Role in System:** Institutional intraday benchmark. When the current market price (CMP) is above VWAP, buyers are in aggregate control (bullish institutional bias); below VWAP, sellers dominate.
- **Architectural Implementation:** The `Technical Indicator Engine` computes cumulative intraday session VWAP starting precisely from the 09:15 IST opening tick. Long signals are strictly rejected if price is below session VWAP; short signals are strictly rejected if price is above session VWAP.

### B. Opening Range Breakout (ORB)
- **Concept:** Market opening (09:15–09:30 IST) is characterized by high volatility, price discovery, and overnight order digestion. The high and low formed during the first 15 minutes establish critical reference levels for the remainder of the session.
- **Role in System:** The high of the 09:15–09:30 range ($ORB_{High}$) serves as the primary resistance ceiling for long breakouts. The low ($ORB_{Low}$) serves as the primary support floor for short breakdowns.
- **Architectural Implementation:** The `Signal Engine` locks the 15-minute range at exactly 09:30:00 IST. No automated entry signals can be triggered before 09:30:00 IST. A breakout is only confirmed when a subsequent 5-minute candle closes decisively above $ORB_{High}$ (or below $ORB_{Low}$).

### C. Volume Confirmation & Relative Volume (RVol)
- **Concept:** Price movement without volume is statistically prone to false breakouts (whipsaws). High volume confirms genuine institutional commitment.
- **Role in System:** A breakout candle must have volume at least 1.5 times the 10-period Simple Moving Average of volume on 5-minute candles ($Volume_{signal} \ge 1.5 \times SMA(Volume_{10})$).
- **Architectural Implementation:** The indicator engine calculates rolling 10-period volume SMA. Breaches lacking volume confirmation are categorized as `REJECTED_INSUFFICIENT_VOLUME` and logged into the audit trail.

### D. Trend Dynamic Guide: 20-Period Exponential Moving Average (EMA)
- **Concept:** 20 EMA on a 5-minute timeframe captures short-term momentum. A healthy intraday trend respects the 20 EMA as dynamic support during pullbacks.
- **Role in System:** For long trades, price must remain above the 20 EMA at the time of breakout, and the 20 EMA slope must be non-negative. For short trades, price must be below the 20 EMA with a non-positive slope.

### E. Candlestick Anatomy: Body-to-Range Ratio
- **Concept:** Dojis, long upper wicks, or indecision candles indicate aggressive counter-pressure. Strong breakout candles have full, decisive bodies.
- **Role in System:** The signal candle must exhibit a body ratio of at least 50% ($\frac{|Close - Open|}{High - Low} \ge 0.50$). Whipsaw candles with long rejection shadows are automatically disqualified.

### F. Volatility Normalization: Average True Range (ATR-14)
- **Concept:** Fixed rupee stops fail because stock volatility varies across regimes and tickers. ATR measures true market volatility including gap risk.
- **Role in System:** ATR(14) on the 5-minute timeframe is used to evaluate spread viability, minimum stop distance, and volatility thresholds. If the spread exceeds 10% of the ATR or if ATR indicates extreme erratic behavior, the trade is rejected.

### G. Mathematical Position Sizing & Capital Preservation
- **Concept:** Trading survival depends on fixed-fractional risk per trade, strictly independent of market conviction.
- **Role in System:**
  $$\text{Risk Budget} = \text{Available Equity} \times 0.005 \quad (0.5\%)$$
  $$\text{Risk Per Share} = |\text{Planned Entry} - \text{Stop Loss}|$$
  $$\text{Quantity}_{\text{risk}} = \left\lfloor \frac{\text{Risk Budget}}{\text{Risk Per Share}} \right\rfloor$$
  $$\text{Quantity}_{\text{cash}} = \left\lfloor \frac{\text{Available Deployable Cash}}{\text{Entry Price}} \right\rfloor$$
  $$\text{Final Quantity} = \min(\text{Quantity}_{\text{risk}}, \text{Quantity}_{\text{cash}}, \text{Liquidity Caps})$$
- If `Final Quantity == 0`, the trade is rejected cleanly. Leverage is never assumed.

### H. Risk-to-Reward Ratio (RRR) and Expectancy
- **Concept:** Mathematical expectancy:
  $$E = (P_{win} \times \text{Avg Win}) - (P_{loss} \times \text{Avg Loss})$$
  With a minimum planned RRR of 2.0:1 ($Target = Entry + 2 \times (Entry - Stop)$ for longs), a system requires only a ~35% win rate to break even before costs.
- **Role in System:** Every signal must offer at least 2.0 RRR before encountering major daily pivot levels or previous-day extremes.

### I. Comprehensive Transaction Cost Modeling
- **Concept:** As detailed in Varsity Module 10 (Markets and Taxation), intraday equities incur multiple statutory and brokerage charges. For small capital accounts (e.g. ₹3,000–₹10,000), fixed brokerage can consume up to 30% of gross profits if unmanaged.
- **Statutory Charges (NSE Intraday Cash Segment):**
  1. **Securities Transaction Tax (STT):** 0.025% on Sell side for equity intraday.
  2. **NSE Exchange Turnover Charge:** 0.00297% (approx. ₹2.97 per lakh) on both Buy and Sell turnover.
  3. **SEBI Turnover Fee:** ₹10 per crore (0.0001%) on both Buy and Sell turnover.
  4. **Stamp Duty:** 0.003% (₹300 per crore) on Buy side only.
  5. **Brokerage (Angel One iTrade Prime):** ₹20 per executed order or 0.03% (whichever is lower).
  6. **GST:** 18% applied on (Brokerage + Exchange Turnover Charge + SEBI Fee).
  7. **Estimated Slippage:** Modeled as 0.05% of trade value (or half the tick/spread).
- **Economic Viability Filter:** If total round-trip estimated costs exceed 15% of the planned gross reward, the trade is rejected as uneconomical for the configured capital.

---

## 4. Concepts Excluded and Justification

| Excluded Concept | Rationale for Exclusion |
|---|---|
| **Multi-Leg Options Strategies** | The project scope specifically targets NSE Cash Equities. Options involve complex non-linear Greeks, time decay (theta), IV crush, and higher capital risk unsuitable for capital-aware beginner validation. |
| **Futures Leverage (Margin Intraday)** | High leverage increases liquidation risk on small accounts. Margin requirements can change intraday via exchange peak margin circulars. System enforces 1:1 cash affordability. |
| **Averaging Down (Martingale)** | Strictly forbidden. Adding to a losing position violates fundamental risk management and leads to catastrophic account drawdowns. |
| **Subjective Discretionary Patterns** | Chart patterns lacking unambiguous mathematical definitions (e.g., subjective trendlines, Elliot waves, complex head-and-shoulders necklines) are excluded in favor of deterministic price, level, and volume rules. |
| **Unconstrained Market Orders** | Market orders are vulnerable to slippage, spread shocks, and exchange fat-finger penalties. The system uses LIMIT and STOP-LIMIT orders with broker price protection. |

---

## 5. System Hypotheses Requiring Quantitative Backtesting

The following testable hypotheses are codified into the strategy engine:

1. **Hypothesis 1 (ORB Edge):** An opening range breakout above the 15-minute high supported by session VWAP and 20 EMA produces a positive mathematical expectancy ($E > 0.25R$) on Nifty 50 constituents over a 2-year backtest window.
2. **Hypothesis 2 (Volume Filter Effectiveness):** Requiring a breakout candle to have $Volume \ge 1.5 \times SMA(Volume_{10})$ reduces false breakout rates by at least 30% compared to an unfiltered ORB.
3. **Hypothesis 3 (Candle Body Strength):** Discarding breakout candles with body-to-range ratios $< 0.50$ improves the profit factor by filtering out rejection wicks and indecisive market participants.
4. **Hypothesis 4 (Macro Regime Alignment):** Conditioning individual stock entries on Nifty 50 index regime (Nifty above its session VWAP for longs, below for shorts) increases the trade win rate by $\ge 6$ percentage points.
5. **Hypothesis 5 (Capital Threshold Viability):** For accounts with trading capital $\le ₹5,000$, intraday cash equity trading under standard retail brokerage structures suffers negative net expectancy due to minimum ticket fees, whereas capital $\ge ₹25,000$ achieves cost efficiency ($Costs < 10\%$ of gross target).

---

## 6. Regulatory & Compliance Context

### SEBI Algorithmic Trading Framework (Circular 2025/2026)
- **Static IP Whitelisting:** Mandatory registration of a dedicated static IPv4 address with Angel One for all automated transactional order routing.
- **Daily Two-Factor Authentication (2FA):** Mandatory daily session initiation using TOTP; permanent unauthenticated sessions are prohibited.
- **Exchange Audit Trail:** All orders must be labeled with strategy identifiers and unique client-side correlation IDs.
- **Rate Limiting:** Adherence to Angel One's 10 orders/sec threshold to avoid automated throttling or exchange disconnection.
- **Separation of Paper and Live Execution:** Paper trading must run via a dedicated virtual simulator without calling broker transactional endpoints, ensuring zero inadvertent live execution during research.

---

## 7. Document Metadata
- **Author:** Antigravity Quantitative Trading Systems Team
- **Version:** 1.0.0
- **Status:** Approved for System Implementation
- **Repository Path:** `docs/research/varsity_research.md`
