# Complete System Architecture: 24/7 Cloud Automated Trading Platform

## 1. Architectural Overview

The platform is designed as a decoupled, resilient, event-driven trading system tailored for the Indian Equity Markets (NSE Cash Equities). It adheres to strict isolation boundaries between:
1. **Market Data Ingestion & Indicator Calculation**
2. **Strategy Signal Generation**
3. **Independent Risk Management**
4. **Execution Layer (Virtual Paper Engine vs. Live Angel One Broker Adapter)**
5. **Persistent Cloud Scheduling & Watchdog Monitoring**
6. **Web Dashboard & User Interface**

```
+---------------------------------------------------------------------------------------------------+
|                                      EXTERNAL DATA & BROKER APIS                                  |
|   +--------------------------+  +-------------------------------+  +--------------------------+   |
|   | Angel One WebSocket 2.0  |  | Angel One Historical / Quotes |  | Global Macro & News APIs |   |
|   +------------+-------------+  +---------------+---------------+  +------------+-------------+   |
+----------------|--------------------------------|-------------------------------|-----------------+
                 |                                |                               |
                 v                                v                               v
+---------------------------------------------------------------------------------------------------+
|                                  CLOUD WORKER (ORACLE ALWAYS FREE VM)                             |
|                                                                                                   |
|  +---------------------------+    +-----------------------------+    +-------------------------+  |
|  | [G] Live Market Data      |    | [F] Historical Data Engine  |    | [A,B] Global & News     |  |
|  | Engine (SmartWebSocketV2) |    | (Caches & Candlestick Sync) |    | Intelligence Engine     |  |
|  +-------------+-------------+    +--------------+--------------+    +------------+------------+  |
|                |                                 |                                |               |
|                +----------------+----------------+                                |               |
|                                 |                                                 |               |
|                                 v                                                 v               |
|  +--------------------------------------------------------------+    +-------------------------+  |
|  | [H] Technical Indicator Engine (VWAP, 20 EMA, ATR-14, ORB)   |    | [C,D,E] Regime & Dynamic|  |
|  +------------------------------+-------------------------------+    | Stock Screener Engine   |  |
|                                 |                                    +------------+------------+  |
|                                 v                                                 |               |
|  +--------------------------------------------------------------------------------+               |
|  | [I] Strategy Signal Engine (ORB + VWAP + EMA + Volume Confirmation v1.0.0)                     |
|  +------------------------------+-----------------------------------------------------------------+
|                                 | Signal Candidate                                                |
|                                 v                                                                 |
|  +----------------------------------------------------------------------------------------------+ |
|  | [K] Independent Risk Management Engine & [J] Capital-Aware Position Sizer                   | |
|  | - Evaluates Account Equity, Max Daily Loss (1%), Max Trades (2), Economic Viability          | |
|  | - Sizing = min(RiskBudget / RiskPerShare, Cash / Price)                                      | |
|  +------------------------------+---------------------------------------------------------------+ |
|                                 | Approved & Sized Order Intent                                   |
|                                 v                                                                 |
|  +----------------------------------------------------------------------------------------------+ |
|  | [O] Trading Mode Dispatcher & State Machine (Default: PAPER_ACTIVE | LIVE_LOCKED)             | |
|  +------------------------------+-------------------------------+-------------------------------+ |
|                                 |                               |                                 |
|          If TRADING_MODE==PAPER |                               | If TRADING_MODE==ACTUAL         |
|                                 v                               v (Locked by default)             |
|  +--------------------------------------------+   +--------------------------------------------+  |
|  | [L] Virtual Broker & Paper Execution Engine|   | [M] Angel One Live Broker Adapter          |  |
|  | - Simulates Limit/Stop fills with slippage |   | - Static IP Whitelisted                    |  |
|  | - Models STT, GST, Stamp, Turnover, Broker |   | - Order Tagging, Rate Limiting (10/sec)    |  |
|  | - Maintains Virtual Ledger & Positions     |   | - Live Order & Position Placement          |  |
|  +----------------------+---------------------+   +---------------------+----------------------+  |
|                         |                                               |                         |
|                         +-----------------------+-----------------------+                         |
|                                                 |                                                 |
|                                                 v                                                 |
|  +----------------------------------------------------------------------------------------------+ |
|  | [N] Order & Position Reconciliation Engine                                                   | |
|  | - Cross-checks pending orders, timeouts, unconfirmed states, and EOD square-off (15:00 IST)   | |
|  +----------------------------------------------+-----------------------------------------------+ |
|                                                 |                                                 |
|  +----------------------------------------------+-----------------------------------------------+ |
|  | [P] APScheduler (24/7 Workflow Automation)   | [T] Notifications & Monitoring (Telegram/Logs)| |
|  +----------------------------------------------------------------------------------------------+ |
+-------------------------------------------------|-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                 PERSISTENT CLOUD DATA LAYER (SUPABASE)                            |
|                                                                                                   |
|  - PostgreSQL 15+ (36 Normalized Tables with RLS & Foreign Keys)                                  |
|  - Supabase Auth (JWT verification for API access)                                                |
|  - Hard Mode Separation: virtual_* tables completely partitioned from live_* tables               |
|  - Heartbeat Watchdog Ping keeping project active within Free-Tier Limits                         |
+-------------------------------------------------+-------------------------------------------------+
                                                  ^
                                                  | Secure HTTPS REST / WSS
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                 CLIENT-FACING PRESENTATION LAYER                                  |
|                                                                                                   |
|  - React + TypeScript + Vite SPA (Hosted on Vercel Free / Cloudflare Pages)                       |
|  - High-Contrast Dark-Mode Design System (Lucide Icons, TailwindCSS, Lightweight-Charts)         |
|  - Visible Segmented Mode Switcher (VIRTUAL TRADING vs ACTUAL TRADING with Safety Warnings)        |
|  - Zero Direct Broker Credentials on Client: Only calls authenticated FastAPI backend             |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Comprehensive Subsystem Directory (A through U)

### Subsystem A: Global Market Intelligence Engine
- **Responsibility:** Ingests and aggregates macro financial data outside of domestic market hours: US markets (S&P 500, Nasdaq), Asian benchmarks (Nikkei, Hang Seng), Brent Crude, USD/INR, and Institutional FII/DII net flows.
- **Data Freshness & Integrity:** Tracks source timestamp, fetch timestamp, and confidence rating.
- **Rule:** Never directly fires a trade; outputs sentiment multipliers (`BULLISH`, `BEARISH`, `NEUTRAL`) utilized by candidate ranking.

### Subsystem B: Economic and Corporate News Engine
- **Responsibility:** Tracks RBI policy announcements, macro economic releases (CPI, GDP), corporate quarterly earnings, stock splits, bonuses, and regulatory ban lists.
- **Action:** Issues trade blackout triggers. Any stock scheduled for earnings release or regulatory actions within $\pm 24$ hours is automatically removed from the daily screening watchlist.

### Subsystem C: Daily Market Regime Engine
- **Responsibility:** Evaluates opening market breadth on Nifty 50 and India VIX between 09:15 and 09:30 IST.
- **States:** `TRENDING_BULLISH`, `TRENDING_BEARISH`, `CHOPPY_SIDEWAYS`, `HIGH_VOLATILITY_HAZARD`.
- **Constraint:** If India VIX $> 24.0$ or regime is `CHOPPY_SIDEWAYS`, new entries are restricted.

### Subsystem D: Sector Strength Analysis Engine
- **Responsibility:** Calculates relative performance of major NSE sectoral indices (Nifty Bank, Nifty IT, Nifty Auto, Nifty Metal, Nifty Pharma) against the Nifty 50 benchmark.
- **Action:** Gives preference to stocks belonging to top-2 outperforming sectors for long trades and bottom-2 sectors for short trades.

### Subsystem E: Dynamic Stock Selection Engine
- **Responsibility:** Screens the Nifty 50 constituent universe dynamically each morning (08:00–08:45 IST) based on 30-day average volume, ATR-14 percentage volatility, bid-ask spread viability, and capital affordability.
- **Output:** Selects an actionable shortlist of 3–5 candidate stocks for the day's active monitoring.

### Subsystem F: Historical Market Data Engine
- **Responsibility:** Communicates with Angel One Historical Candle API to retrieve and cache daily, 15-minute, and 5-minute OHLCV candles with local SQLite / PostgreSQL caching.
- **Validation:** Ensures zero missing candles and accounts for corporate action price adjustments.

### Subsystem G: Live Market Data Engine
- **Responsibility:** Establishes resilient WebSocket 2.0 streaming via Angel One's `SmartWebSocketV2`.
- **Resilience:** Auto-reconnect with exponential backoff, tick aggregation into 5-minute candles, and staleness watchdog (flags data as stale if no tick received for $> 15$ seconds during market hours).

### Subsystem H: Technical Indicator Engine
- **Responsibility:** Calculates deterministic intraday indicators with verified mathematical precision:
  - Cumulative Session VWAP (starting 09:15 IST)
  - 20-Period Exponential Moving Average (EMA)
  - 14-Period Average True Range (ATR)
  - First 15-Minute Opening Range ($ORB_{High}$, $ORB_{Low}$)
  - Rolling 10-period Volume SMA & Relative Volume ($RVol$)
  - Candle Body Ratio ($\frac{|Close - Open|}{High - Low}$)

### Subsystem I: Trading Signal Engine
- **Responsibility:** Evaluates strategy rules on completed 5-minute candles. Generates explicit candidate signal events containing:
  - Direction (`BUY` / `SELL`)
  - Target Entry Price (Limit or Stop-Limit)
  - Structural Stop-Loss Level
  - Target Price (minimum 2.0 RRR)
  - Expiry timestamp (invalidated after 2 subsequent 5-minute candles if unfilled)

### Subsystem J: Capital-Aware Position Sizing Engine
- **Responsibility:** Evaluates deployable capital (e.g. ₹3k, ₹5k, ₹10k, ₹25k, ₹50k, ₹100k) against the signal's risk per share.
- **Economic Viability:** Models exact transaction charges (STT, GST, stamp duty, turnover fees, Angel One brokerage). Rejects signal if costs $> 15\%$ of expected reward or if affordable quantity is 0.

### Subsystem K: Independent Risk Management Engine
- **Responsibility:** Operates strictly independent of strategy logic. Possesses absolute veto authority over order placement.
- **Hard Guardrails:**
  - Max risk per trade = 0.5% of equity
  - Max daily loss = 1.0% of equity (trading halts immediately if breached)
  - Max trades per day = 2
  - Max concurrent open positions = 1
  - Data staleness check & broker session check
  - Mandatory end-of-day square-off at 15:00 IST

### Subsystem L: Virtual Broker & Paper Execution Engine
- **Responsibility:** Realistic simulation of order placement, queueing, and fills without touching live broker endpoints.
- **Conservative Modeling:** Enforces limit price constraints, models 0.05% slippage, deducts exact statutory taxes and brokerage, and maintains dedicated `virtual_accounts`, `virtual_orders`, and `virtual_positions`.

### Subsystem M: Angel One Live Broker Adapter
- **Responsibility:** Low-latency, compliant interface with Angel One SmartAPI REST endpoints for live order operations.
- **Compliance Guardrails:**
  - Locked behind backend environment flag (`LIVE_TRADING_ENABLED=false`) and runtime multi-step authorization.
  - Enforces Angel One Static IP binding and daily TOTP 2FA.
  - Applies order rate limiting ($\le 10$ orders/sec) and exchange tagging.

### Subsystem N: Order and Position Reconciliation Engine
- **Responsibility:** Continuously audits open positions and orders against reported broker state.
- **Safety:** Resolves hanging orders, orphaned stop-losses, and timeout mismatches. Forces emergency square-off if discrepancies persist.

### Subsystem O: Trading Mode Management Engine
- **Responsibility:** Manages the system-wide execution state machine:
  `PAPER_ACTIVE` $\leftrightarrow$ `PAPER_PAUSED` | `LIVE_LOCKED` $\rightarrow$ `LIVE_READY` $\rightarrow$ `LIVE_ACTIVE` $\leftrightarrow$ `LIVE_PAUSED` | `EMERGENCY_STOP`.
- **Rule:** Rejects unsafe transitions. Paper positions can NEVER be migrated to live positions.

### Subsystem P: Scheduling & Workflow Engine
- **Responsibility:** Uses APScheduler within the 24/7 cloud worker to execute the daily timetable (00:00 macro collection, 07:30 data sync, 08:30 stock screening, 09:15 session open, 15:00 square-off, 15:20 reconciliation, 16:00 reporting).

### Subsystem Q: Backtesting & Strategy Validation Engine
- **Responsibility:** Event-driven historical simulation engine verifying strategy performance across multi-year data with zero look-ahead bias, realistic slippage, transaction cost deduction, and walk-forward analysis.

### Subsystem R: Trading Journal & Performance Analytics Engine
- **Responsibility:** Automatically records completed trades with full contextual snapshot (regime, overnight indicators, checklist scores, entry/exit charts, P&L, fees). Computes Sharpe ratio, Max Drawdown, Expectancy, and Win Rate.

### Subsystem S: React Trading Dashboard
- **Responsibility:** High-performance, clean, dark-mode SPA built with React 18, TypeScript, TailwindCSS, and Vite.
- **Features:** Segmented Mode Switcher (VIRTUAL vs ACTUAL), real-time portfolio metrics, candlestick charts, live watchlist, order book, risk controls, and system health status.

### Subsystem T: Notifications and Monitoring Engine
- **Responsibility:** Real-time Telegram alerts for lifecycle events (worker heartbeat, signal generated, order filled, stop hit, daily loss limit reached, critical exceptions) and structured JSON logging.

### Subsystem U: Cloud Deployment and Recovery Engine
- **Responsibility:** Systemd service definitions, Docker containerization, health check endpoints (`/health`), and automated restart recovery on Oracle Cloud Always Free VM.

---

## 3. Communication Protocols and Data Flow

1. **Market Data Feed:** WebSocket 2.0 binary/JSON stream received by Cloud Worker $\rightarrow$ parsed into structured `MarketTick` models $\rightarrow$ aggregated into completed 5-minute candles.
2. **Signal Pipeline:** Completed 5-min candle $\rightarrow$ Indicators calculated $\rightarrow$ Strategy rules checked $\rightarrow$ If valid, `SignalCandidate` event emitted.
3. **Risk Pipeline:** `SignalCandidate` passed to `RiskEngine.evaluate(signal, portfolio_state)` $\rightarrow$ If approved, position size calculated $\rightarrow$ `OrderIntent` created.
4. **Execution Pipeline:** Mode Dispatcher checks active mode:
   - If `PAPER`: passes `OrderIntent` to `VirtualBroker.submit_order()` $\rightarrow$ updates `virtual_*` tables in Supabase.
   - If `ACTUAL`: verifies hard authorization $\rightarrow$ passes to `AngelOneAdapter.place_order()` $\rightarrow$ updates `live_*` tables.
5. **Client Dashboard:** Frontend queries FastAPI REST endpoints with JWT authorization header $\rightarrow$ reads views from Supabase $\rightarrow$ receives real-time updates.

---

## 4. Hardware and Free-Tier Optimization Strategy

| Resource | Constraints | Optimization Strategy |
|---|---|---|
| **Laptop Development** | 8 GB RAM | Lightweight dev stack: FastAPI running in lightweight venv, Vite frontend with fast HMR, avoiding heavyweight Docker containers locally. |
| **Oracle Always Free VM** | 1–4 OCPU, 1–24 GB RAM | Single Python process running async FastAPI + APScheduler + WebSocket client in daemonized background thread. Memory footprint $< 350$ MB. |
| **Supabase PostgreSQL** | 500 MB DB storage | Retention policy: store 5-minute candles for active month, roll up older historical data into daily aggregates. Raw ticks are never stored permanently in DB. |
| **Supabase 7-Day Inactivity** | Pauses after 7 days idle | Scheduled lightweight heartbeat ping (`SELECT 1`) executed by Cloud Worker keeps DB active indefinitely. |
| **Vercel Frontend** | Non-commercial Hobby Tier | Pure static SPA deployment; all dynamic computation and secrets reside on persistent Oracle backend and Supabase. |
