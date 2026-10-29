# Supabase Database Architecture & Setup Guide

## 1. Overview and Free-Tier Sizing Strategy

The platform utilizes **Supabase PostgreSQL** as its primary cloud database. Supabase provides a managed, high-performance PostgreSQL 15+ database with built-in Auth, Row Level Security (RLS), and PostgREST APIs.

### Free-Tier Operating Constraints & Mitigations
- **Storage Limit:** 500 MB database disk storage.
  - *Mitigation:* We **never** store un-aggregated raw market ticks in PostgreSQL. Raw ticks are processed in memory and aggregated into completed 5-minute candles. Historical 5-minute candles are archived or aggregated into daily summaries after 60 days.
- **Project Inactivity Pausing:** Supabase pauses free projects after 7 consecutive days of zero database query activity.
  - *Mitigation:* The 24/7 cloud worker executes multiple scheduled operations daily (overnight macro collection, pre-market preparation, post-market reporting). Additionally, an automated lightweight keep-alive heartbeat ping (`SELECT 1 FROM system_health LIMIT 1`) runs every 6 hours, ensuring the project remains active 365 days a year without manual intervention.
- **Connection Limits:** Default 60 direct client connections.
  - *Mitigation:* The FastAPI backend uses connection pooling via Supavisor (Port 6543, Transaction mode) and maintains a pool of 5–10 connections.

---

## 2. Complete 36-Table Schema Architecture

```
                                  [users]
                                     |
       +-----------------------------+-----------------------------+
       |                             |                             |
[user_settings]             [broker_connections]          [strategy_configs]
                                                                   |
                                                          [strategy_versions]

   [instruments] <---------- [index_constituents]
         |
         +---------> [historical_candles]
         |
         +---------> [live_candles]
         |
         +---------> [indicator_snapshots]

[global_market_observations]   [economic_events]   [corporate_events]
                                     |
                          [daily_market_context]
                                     |
                          [sector_rankings]
                                     |
                          [screening_results]
                                     |
                          [stock_watchlists]
                                     |
                          [trading_checklists]
                                     |
                          [trade_signals] ---------> [signal_rejections]
                                     |
          +--------------------------+--------------------------+
          |                                                     |
  (PAPER MODE)                                           (ACTUAL MODE)
          v                                                     v
  [virtual_accounts]                                     [live_orders]
          |                                                     |
  [virtual_orders]                                       [live_fills]
          |                                                     |
  [virtual_fills]                                        [live_positions]
          |
  [virtual_positions]

[risk_state] <----> [risk_events]
[trade_journal] <----> [daily_performance]
[backtest_runs] <----> [backtest_trades]
[notifications]
[system_health]
[scheduled_jobs]
[audit_logs]
```

---

## 3. Data Tables Specification

### Identity & Settings
1. `users`: System administrative operator ID, email, role, created_at.
2. `user_settings`: User preferences, active trading mode (`PAPER` or `ACTUAL`), capital allocation preferences, dark mode setting.
3. `broker_connections`: Angel One connection status, client code, last authenticated timestamp, static IP registered, session expiry. (No plaintext secrets; secrets are stored in `.env`).
4. `strategy_configs`: Configurable strategy parameters (ORB window, EMA periods, RVol multiplier, RRR target).
5. `strategy_versions`: Immutable version registry (`1.0.0`, `1.0.1`, git commit hash, checksum).

### Market Context & Universe
6. `market_sessions`: NSE trading calendar, trading holidays, session opening/closing timestamps, session status.
7. `instruments`: NSE cash scrip master (symbol, token, lot size, tick size, freeze limits).
8. `index_constituents`: Nifty 50 constituent tracking, weightages, inclusion dates.
9. `historical_candles`: Daily and 15-minute historical candles for warm-up.
10. `live_candles`: Completed 5-minute session candles for active watchlist.
11. `global_market_observations`: Overnight index values (S&P 500, Nasdaq, Asian markets, Crude, USD/INR, FII flows).
12. `economic_events`: Scheduled RBI policies, CPI/GDP releases, macroeconomic blackout dates.
13. `corporate_events`: Quarterly earnings, dividend ex-dates, stock splits, board meetings.
14. `daily_market_context`: Aggregated daily regime classification, market breadth, India VIX snapshot.
15. `sector_rankings`: Relative strength ranking of NSE sectoral indices.
16. `screening_results`: Morning screening scores, metrics, passed/failed status, rejection reasons.
17. `stock_watchlists`: Final 3–5 daily candidate stocks monitored for active signals.

### Technical & Signals
18. `indicator_snapshots`: Computed indicators (VWAP, EMA-20, ATR-14, $ORB_{High}$, $ORB_{Low}$, $RVol$) for each 5-minute bar.
19. `trading_checklists`: Comprehensive 18-point checklist verification records for each evaluated candidate.
20. `trade_signals`: Verified signal candidates ready for sizing and execution dispatch.
21. `signal_rejections`: Discarded signals with explicit rejection tags (e.g. `INSUFFICIENT_VOLUME`, `UNECONOMICAL_COSTS`).

### Virtual Execution Regime (Paper Trading)
22. `virtual_accounts`: Simulated cash balance, margin used, realized P&L, unrealized P&L, starting capital, audit ledger.
23. `virtual_orders`: Simulated orders (order ID, symbol, direction, order type, price, trigger price, status).
24. `virtual_fills`: Simulated order fill records with slippage and exact timestamp.
25. `virtual_positions`: Active and closed virtual positions with realized R multiples.

### Live Execution Regime (Actual Trading — Hard Partitioned)
26. `live_orders`: Real Angel One SmartAPI orders, exchange order ID, broker correlation ID, order variety.
27. `live_fills`: Confirmed broker fill executions, filled quantity, fill price, exchange transaction time.
28. `live_positions`: Active live broker positions reconciled with Angel One position book.

### Risk, Analytics, Operations
29. `risk_state`: Real-time daily loss tracking, active trade count, circuit breaker status.
30. `risk_events`: Breaches of risk rules (e.g. max daily loss hit, spread limit exceeded, emergency stops).
31. `trade_journal`: Detailed post-trade reflection, technical context snapshot, charts, outcome tags.
32. `daily_performance`: End-of-day P&L, win rate, profit factor, fees paid, Sharpe ratio.
33. `backtest_runs`: Metadata of historical backtests (strategy version, date range, parameters, metrics).
34. `backtest_trades`: Individual simulated trades generated during backtests.
35. `notifications`: Audit log of sent Telegram alerts and delivery confirmations.
36. `system_health`: Cloud worker heartbeats, memory usage, CPU load, WebSocket latency, API ping times.
37. `scheduled_jobs`: APScheduler execution history, job run times, success/failure status.
38. `audit_logs`: Cryptographic audit trail of all mode transitions, parameter modifications, and admin actions.

---

## 4. Row Level Security (RLS) & Protection Rules

1. **Service Role Exclusivity:** The backend Python worker connects using the `SUPABASE_SERVICE_ROLE_KEY` (kept securely on the server), allowing it full transactional read/write access.
2. **Anon Key Read-Only Views:** The frontend connects using the `SUPABASE_ANON_KEY` combined with user authentication tokens. RLS policies restrict anonymous users from directly inserting or modifying orders or risk states.
3. **Mode Partitioning:** RLS policies prevent paper accounts from querying or modifying live tables.
