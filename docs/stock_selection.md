# Dynamic Stock Selection Engine Specification

## 1. Overview and Core Philosophy
The platform strictly rejects the concept of a static, hardcoded list of trading tickers. In intraday trading, liquidity, institutional participation, and daily volatility shift continually across sectors and equities. 

The **Dynamic Stock Selection Engine** runs automated screening every morning between **08:00 and 08:45 IST** using the verified constituent universe of the **Nifty 50 Index**, synchronized directly with Angel One's instrument master.

---

## 2. Universe Definition & Synchronization

1. **Benchmark Universe:** Nifty 50 constituents. Representing the top 50 highly capitalized, blue-chip Indian equities traded on the National Stock Exchange (NSE).
2. **Instrument Token Mapping:** Synchronized daily from Angel One's official scrip master (`OpenAPIScripMaster.json`), verifying:
   - `exch_seg == "NSE"`
   - `instrumenttype == ""` (Equity Cash)
   - `symbol` ends in `-EQ` (e.g. `RELIANCE-EQ`, `INFY-EQ`, `HDFCBANK-EQ`)
   - Unique Angel One `symboltoken` mapped to internal database ID.
3. **Corporate Actions & Index Rebalancing:** Constituents are validated against official NSE index circulars and refreshed bi-weekly.

---

## 3. Daily 14-Step Screening Pipeline (08:00–08:45 IST)

```
+-------------------------------------------------------------+
| Step 1: Ingest 50 Active Nifty 50 Equities                  |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 2: Verify Active Trading & Angel One Token Mapping     |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 3: Fetch Past 30 Days Daily & 15-Minute Candle History |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 4: Liquidity Filter: 30-Day Avg Daily Volume >= 1.5M   |
|         and Daily Turnover >= ₹100 Crores                   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 5: Volatility Filter: Daily ATR% between 1.2% and 3.5% |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 6: Spread Filter: Bid-Ask Spread <= 0.05% of CMP       |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 7: Technical Structure: Clean Previous Day Range (PDH/L)|
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 8: Corporate Action & News Blackout Check              |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 9: Sector Relative Strength Ranking (Top 2 & Bottom 2) |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 10: Multi-Factor Composite Scoring (0 to 100)          |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 11: Capital Affordability Filter (Can buy >= 1 share   |
|          under risk budget without leverage?)               |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 12: Shortlist Top 3 to 5 Primary Watchlist Candidates  |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 13: Subscribe Real-Time WebSocket 2.0 Feeds (09:00 IST)|
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 14: Await 09:15–09:30 ORB Formation & Strategy Check   |
+-------------------------------------------------------------+
```

---

## 4. Quantitative Filtering Metrics

### 4.1 Liquidity & Turnover Criteria
- **30-Day Average Daily Volume:** Must exceed $1,500,000$ shares.
- **30-Day Average Daily Turnover:** Must exceed $₹100\text{ Crores}$ ($₹1,00,00,00,000$).
- *Rationale:* Eliminates illiquid equities prone to high slippage, erratic tick jumps, or wide bid-ask spreads.

### 4.2 Volatility Range (ATR%)
- **ATR Percentage:**
  $$ATR\% = \frac{ATR(14)_{\text{Daily}}}{Close_{\text{Daily}}} \times 100$$
- **Target Band:** $1.20\% \le ATR\% \le 3.50\%$.
- *Rationale:* If $ATR\% < 1.20\%$, the stock lacks sufficient intraday movement to achieve a $2.0R$ target before 15:00 IST. If $ATR\% > 3.50\%$, the stock exhibits extreme volatility, causing wide stops that drastically reduce affordable position sizing.

### 4.3 Spread Viability
- **Average Bid-Ask Spread:** Must be $\le 0.05\%$ of Current Market Price (or $\le 1$ to 2 ticks).
- If quote depth shows a wide spread, the instrument is flagged as high-friction and removed.

### 4.4 Corporate Actions & Earnings Blackout
- The engine cross-references NSE corporate calendars.
- Stocks scheduled for quarterly earnings, board meetings, dividend ex-dates, or bonus splits within $\pm 24$ hours are filtered out to avoid unpredictable news shocks.

---

## 5. Composite Ranking Formula

Screened stocks meeting all baseline filters are scored on a 100-point composite scale:

$$Score = (0.35 \times Score_{\text{SectorRS}}) + (0.25 \times Score_{\text{VolumeMomentum}}) + (0.20 \times Score_{\text{Volatility}}) + (0.20 \times Score_{\text{Structure}})$$

Where:
- **$Score_{\text{SectorRS}}$ (35 pts):** Relative strength of the stock's sector index vs. Nifty 50 over the trailing 5 sessions.
- **$Score_{\text{VolumeMomentum}}$ (25 pts):** Ratio of previous day's volume to 20-day average volume.
- **$Score_{\text{Volatility}}$ (20 pts):** Proximity of $ATR\%$ to the optimal intraday sweet-spot ($1.8\% - 2.5\%$).
- **$Score_{\text{Structure}}$ (20 pts):** Cleanliness of previous day's price structure (clear trend vs. narrow overlapping consolidation).

---

## 6. Capital Affordability Check

Even a stock with a perfect 100-point score must be rejected if the configured capital cannot support it:
- Let $C$ be the available trading capital.
- Let $P$ be the estimated entry price.
- Let $R$ be the planned risk per share ($\approx 0.7\% \times P$).
- Quantity by Risk: $Q_{risk} = \lfloor (C \times 0.005) / R \rfloor$.
- Quantity by Cash: $Q_{cash} = \lfloor C / P \rfloor$.
- If $\min(Q_{risk}, Q_{cash}) < 1$, the stock is **ineligible** for this account's capital level.
- *Example:* For an account with ₹3,000 capital, stocks trading above ₹1,500 (such as TCS or Bajaj Auto) are automatically excluded in favor of high-volume, lower-denomination Nifty 50 names (such as SBIN, ICICIBANK, or TATASTEEL).

---

## 7. Explainability & Audit Trail
Every daily screening cycle generates an explainable JSON report saved to Supabase table `screening_results`:
- `ticker`: Symbol
- `composite_score`: 0–100
- `metrics`: Dictionary of calculated metrics ($ATR\%$, turnover, volume ratio, spread)
- `passed_filters`: Boolean
- `rejection_reasons`: List of explicit strings (e.g., `["EXCLUDED_EARNINGS_BLACKOUT", "CAPITAL_UNAFFORDABLE_FOR_RUPEES_5000"]`)
- `watchlist_rank`: Integer (1 to 5 for shortlisted names, null for rejected)
