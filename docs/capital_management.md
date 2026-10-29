# Capital-Aware Trading & Position Sizing Engine Specification

## 1. Principles of Capital-Aware Trading

A critical flaw in standard retail trading bots is assuming infinite or invariant capital. In reality:
1. Available capital dictates the exact universe of affordable stocks.
2. Fixed-fee brokerages (e.g., ₹20 per trade) disproportionately erode small accounts.
3. Leverage/margin (MIS 5x) introduces liquidation hazards and varying peak-margin rules; our system **enforces 1:1 cash affordability** for conservative paper and validated live trading.
4. Position sizing must be strictly calculated from the stop-loss distance, never from gut feeling or arbitrarily chosen lot sizes.

---

## 2. Multi-Tier Capital Profiles

The platform natively supports configurable capital, with specialized pre-sets for empirical comparison:

| Capital Tier | Total Equity ($E$) | Max Risk Per Trade (0.5%) | Max Daily Loss Budget (1.0%) | Typical Affordable Share Price Range | Minimum Trade Value to Clear Costs |
|---|---|---|---|---|---|
| **Tier 1 (Micro)** | ₹3,000 | ₹15.00 | ₹30.00 | ₹100 – ₹600 (e.g. TATASTEEL, SBIN) | ₹1,500 |
| **Tier 2 (Starter)** | ₹5,000 | ₹25.00 | ₹50.00 | ₹100 – ₹1,200 (e.g. ICICIBANK, AXISBANK) | ₹2,500 |
| **Tier 3 (Standard Small)** | ₹10,000 | ₹50.00 | ₹100.00 | ₹100 – ₹2,500 (e.g. INFY, RELIANCE) | ₹4,000 |
| **Tier 4 (Intermediate)** | ₹25,000 | ₹125.00 | ₹250.00 | Full Nifty 50 Cash Universe | ₹8,000 |
| **Tier 5 (Advanced)** | ₹50,000 | ₹250.00 | ₹500.00 | Full Nifty 50 Cash Universe | ₹15,000 |
| **Tier 6 (Professional)** | ₹1,00,000 | ₹500.00 | ₹1,000.00 | Full Nifty 50 Cash Universe | ₹25,000 |

---

## 3. Position Sizing Mathematical Formulation

For any trade signal, the position sizing engine executes the following deterministic sequence:

### Step 1: Calculate Dollar Risk Budget
$$\text{RiskBudget} = \text{AvailableTradingEquity} \times 0.005 \quad (0.50\%)$$

### Step 2: Calculate Risk Per Share
$$\text{RiskPerShare} = |\text{PlannedEntryPrice} - \text{StopLossPrice}|$$

*Floor Check:* If $\text{RiskPerShare} < \text{TickSize}$ ($₹0.05$), reject signal.

### Step 3: Compute Quantities by Constraints
1. **Quantity Permitted by Risk Budget:**
   $$Q_{\text{risk}} = \left\lfloor \frac{\text{RiskBudget}}{\text{RiskPerShare}} \right\rfloor$$

2. **Quantity Permitted by Available Cash (1:1 Cash Deployment):**
   $$Q_{\text{cash}} = \left\lfloor \frac{\text{AvailableDeployableCash}}{\text{PlannedEntryPrice}} \right\rfloor$$

3. **Quantity Permitted by Market Liquidity:**
   $$Q_{\text{liquidity}} = \left\lfloor \frac{0.01 \times \text{Avg5MinCandleVolume}}{1} \right\rfloor$$

### Step 4: Determine Preliminary Sized Quantity
$$Q_{\text{preliminary}} = \min(Q_{\text{risk}}, Q_{\text{cash}}, Q_{\text{liquidity}})$$

If $Q_{\text{preliminary}} < 1$:
$$\text{Status} \rightarrow \text{REJECTED\_INSUFFICIENT\_CAPITAL}$$

---

## 4. Comprehensive Transaction Cost Modeling

To assess true economic viability before order placement, the engine calculates the exact round-trip fees on NSE cash equity intraday:

Let $EntryTurnover = Q \times EntryPrice$ and $ExitTurnover = Q \times TargetPrice$.
Total Turnover: $Turnover_{total} = EntryTurnover + ExitTurnover$.

| Fee Component | Statutory / Broker Rate | Computation |
|---|---|---|
| **Brokerage (Angel One)** | Flat ₹20 or 0.03% (whichever is lower) | $\min(20, 0.0003 \times EntryTurnover) + \min(20, 0.0003 \times ExitTurnover)$ |
| **Securities Transaction Tax (STT)** | 0.025% on Sell Turnover | $0.00025 \times ExitTurnover$ |
| **NSE Exchange Turnover Charge** | 0.00297% on Both Sides | $0.0000297 \times Turnover_{total}$ |
| **SEBI Turnover Fee** | ₹10 per crore (0.0001%) | $0.000001 \times Turnover_{total}$ |
| **Stamp Duty** | 0.003% on Buy Turnover only | $0.00003 \times EntryTurnover$ |
| **GST** | 18% on (Brokerage + Exchange + SEBI) | $0.18 \times (\text{Brokerage} + \text{ExchangeCharge} + \text{SEBIFee})$ |
| **Estimated Conservative Slippage** | 0.05% of Total Turnover | $0.0005 \times Turnover_{total}$ |

$$\text{TotalEstimatedCosts} = \text{Brokerage} + \text{STT} + \text{ExchangeCharge} + \text{SEBIFee} + \text{StampDuty} + \text{GST} + \text{Slippage}$$

---

## 5. Economic Viability Filter

For small capital tiers, fixed brokerage fees (e.g. ₹40 round-trip) can consume all potential profit:

1. **Expected Gross Profit at Target (2.0R):**
   $$\text{GrossProfit} = Q \times (\text{TargetPrice} - \text{EntryPrice})$$

2. **Cost-to-Reward Ratio ($CRR$):**
   $$CRR = \frac{\text{TotalEstimatedCosts}}{\text{GrossProfit}}$$

3. **Viability Threshold Rule:**
   - If $CRR > 0.15$ (i.e. transaction costs consume more than $15\%$ of the gross target profit), the trade is **VETOED**:
   $$\text{Status} \rightarrow \text{REJECTED\_UNECONOMICAL\_COST\_DRAG}$$

*Impact on Small Accounts:* On a ₹3,000 account, if a trade aims to make ₹30 gross, round-trip fees of ₹35 result in a guaranteed net loss. The engine automatically rejects such trades and explicitly advises that capital tier is sub-scale for individual low-volatility tickers.

---

## 6. Daily Loss Caps & Drawdown Circuit Breakers

1. **Maximum Daily Realized Loss:** $1.0\%$ of starting session equity. If reached, the system immediately suspends all trading for the day, cancels pending orders, and alerts via Telegram.
2. **Weekly Drawdown Review Trigger:** $3.0\%$ cumulative drawdown over a rolling 5-day period triggers a performance review alert.
3. **Strategy Suspension Trigger:** $6.0\%$ cumulative drawdown halts automated execution and reverts the system to `PAPER_PAUSED` pending quantitative diagnostic review.
