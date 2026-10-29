# Comprehensive Phased Development Plan & Milestone Roadmap

## 1. Project Philosophy & Guiding Principles
- **Safety Before Automation:** Every system transition and trade intent must be gated by independent risk verification.
- **₹0 Infrastructure Cost:** Strict adherence to verified free tiers (Oracle Always Free, Supabase Free, Vercel/Cloudflare Pages Free, Telegram Bot Free, Angel One Free Developer API).
- **Zero Laptop Dependency:** Cloud-hosted 24/7 autonomous worker.
- **Strict Mode Partitioning:** Virtual Paper Trading and Actual Live Trading are completely isolated. Actual trading remains locked behind hard gates until empirical validation.

---

## 2. Phased Development Roadmap

```
+--------------------------------------------------------------------------------------------------+
| PHASE 1: Research, Regulatory Verification & Complete Architectural Specification (COMPLETED)    |
| - Zerodha Varsity synthesis (docs/research/varsity_research.md)                                  |
| - System Architecture & Subsystems A-U (docs/architecture.md)                                    |
| - Strategy v1.0.0 (docs/strategy_specification.md) & Dynamic Screening (docs/stock_selection.md) |
| - Capital Management (docs/capital_management.md) & Risk Engine (docs/risk_management.md)         |
| - Mode Switching & Isolation (docs/mode_switching.md)                                            |
| - Cloud Infrastructure & Free-Tier Specifications (docs/supabase_setup.md, oracle_setup.md, etc.)|
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 2: Repository Scaffolding, Tooling & Dependency Configuration                              |
| - Python 3.11+ / FastAPI backend structure, virtual environment, and requirements.txt            |
| - React 18 + TypeScript + Vite + TailwindCSS frontend structure                                  |
| - Configuration management via Pydantic Settings & .env loading                                  |
| - Testing harness (pytest, pytest-asyncio, vitest)                                               |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 3: Supabase Cloud Database Architecture, Migrations & RLS Policies                         |
| - 36 normalized tables with foreign keys, check constraints, and UTC timestamps                 |
| - Mode partitioning: virtual_* vs live_* isolation                                              |
| - Row Level Security (RLS) policies and service role access                                      |
| - Automated 6-hour keep-alive heartbeat ping to prevent 7-day inactivity pausing                 |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 4: Angel One Market Data Engine (Quotes, Historical & SmartWebSocketV2)                    |
| - TOTP-assisted 2FA session manager (pyotp + SmartConnect)                                       |
| - Scrip master synchronization (Nifty 50 constituent token mapping)                              |
| - Historical candlestick data retrieval and caching                                              |
| - Resilient WebSocket 2.0 streaming with automatic reconnection & staleness watchdog            |
| - STRICT GUARD: Live order placement methods completely excluded/disabled                       |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 5: Technical Indicator Engine & Independent Unit Testing                                   |
| - Mathematically verified Python implementations:                                                |
|   * Session VWAP (09:15 IST daily anchor)                                                        |
|   * 20-Period Exponential Moving Average (EMA-20)                                                |
|   * 14-Period Average True Range (ATR-14)                                                        |
|   * First 15-Minute Opening Range (ORB High/Low)                                                 |
|   * 10-Period Rolling Volume SMA & Relative Volume (RVol)                                        |
|   * Candle Body Ratio (|Close - Open| / (High - Low))                                            |
| - 100% unit test coverage against synthetic benchmark fixtures                                  |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 6: Overnight Global Market Intelligence & Economic Event Engine                            |
| - Macro data collector: US markets (S&P 500, Nasdaq), Asian indices, Crude, USD/INR, FII/DII    |
| - Economic & corporate calendar ingestion (NSE announcements, RBI policy, earnings blackout)     |
| - Morning market sentiment synthesizer and caution flag emitter                                  |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 7: Dynamic Stock Screening & Ranking Engine                                                |
| - 14-step morning screening pipeline (08:00–08:45 IST)                                           |
| - 30-day average volume, turnover, ATR% volatility, and spread filters                           |
| - Sector relative strength scoring                                                               |
| - Capital affordability filter for configurable equity tiers (₹3k to ₹100k)                      |
| - Actionable 3–5 stock shortlist generation with explainable audit logs                          |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 8: Strategy Signal Engine (ORB + VWAP + EMA + Volume Confirmation v1.0.0)                  |
| - 18-point long entry checklist & 18-point short entry checklist                                 |
| - Completed 5-minute candle evaluation                                                           |
| - Structural stop-loss and 2.0R profit target calculation                                        |
| - Signal expiry watchdog (invalidation after 2 subsequent 5-minute candles)                      |
| - Explicit signal rejection logger                                                               |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 9: Independent Risk Management & Capital-Aware Position Sizing Engine                      |
| - Absolute veto authority over order placement                                                   |
| - Fixed 0.5% risk per trade & 1.0% daily realized loss limit                                     |
| - Position sizing formula: min(RiskBudget / RiskPerShare, Cash / Price)                          |
| - Comprehensive transaction cost modeling (STT, Exchange turnover, SEBI, Stamp, GST, Brokerage)  |
| - Economic viability filter (costs > 15% of gross profit triggers rejection)                     |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 10: Virtual Broker & Paper Execution Simulation Engine                                     |
| - Conservative simulated fills on completed candles with 0.05% slippage                          |
| - Dedicated virtual_accounts, virtual_orders, virtual_positions, and virtual_fills               |
| - Realized & unrealized P&L tracking, R-multiple accounting                                      |
| - ZERO communication with live broker transactional routes                                       |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 11: Modern React + TypeScript Trading Dashboard (Frontend)                                 |
| - High-contrast dark-mode design system with TailwindCSS & Lucide icons                          |
| - Segmented Mode Switcher (VIRTUAL TRADING vs ACTUAL TRADING with safety warnings)               |
| - 20 dedicated views: Overview, Live Watchlist, Screener, Signals, Positions, Orders, Capital    |
|   Settings, Risk Controls, Backtesting, Journal, Health Telemetry, etc.                          |
| - Interactive charts: Candlesticks, VWAP, EMA-20, ORB bands, Equity curves                       |
| - Clear PAPER vs ACTUAL visual badges on every trade and report                                  |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 12: Notifications, Telemetry & Operational Watchdog Engine                                 |
| - Telegram bot integration for real-time trade signals, fills, risk halts, and health pings     |
| - Structured JSON logging with rotating file handlers                                            |
| - Health check endpoints (/health) monitoring CPU, memory, DB latency, and tick freshness        |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 13: Reproducible Event-Driven Historical Backtesting Engine                                |
| - Multi-year historical replay on Nifty 50 cash equities with zero look-ahead bias               |
| - Walk-forward validation and capital tier experiments (₹3k, ₹5k, ₹10k, ₹25k, ₹50k, ₹100k)       |
| - Detailed performance metrics: Sharpe ratio, Max Drawdown, Expectancy, Win Rate, Profit Factor  |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 14: Cloud Deployment (Oracle Always Free VM & Static Frontend Host)                        |
| - Persistent backend worker containerized / managed via systemd on Oracle Cloud VM               |
| - Dedicated reserved static public IPv4 configured                                               |
| - Static frontend hosted on Vercel Free / Cloudflare Pages                                       |
| - Automated process restart recovery and zero-cost resilience verified                           |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 15: Forward Paper-Trading Execution Milestone                                              |
| - System runs live 24/7 during Indian market hours (09:15–15:30 IST)                             |
| - Collects and audits 50–100 forward paper trades across varied market regimes                   |
| - Verification of statistical expectancy, cost assumptions, and operational stability            |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 16: Angel One Live Broker Adapter (Behind Hard Multi-Step Authorization)                   |
| - REST transactional client: placeOrder, modifyOrder, cancelOrder                                |
| - Static IP whitelisting validation & Algo-ID tagging                                            |
| - Order reconciliation engine for timeouts, hanging orders, and position sync                    |
| - Live execution remains DISABLED (LIVE_TRADING_ENABLED=false) until explicit authorization       |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| PHASE 17: Live-Readiness Verification & Compliance Evaluation                                    |
| - Final regulatory checklist: SEBI retail algo circular, static IP binding, broker RMS funds     |
| - Pre-flight verification with zero live trades fired without explicit user override             |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Definition of Done for First Production Milestone
The **Cloud-Hosted Paper-Trading Platform** is complete and production-ready when:
1. The backend operates autonomously 24/7 on cloud compute without requiring the user's laptop.
2. Market data streams via Angel One SmartAPI WebSocket 2.0 with tick-staleness watchdog protection.
3. Morning dynamic stock screening scores and shortlists 3–5 Nifty 50 equities daily.
4. Strategy v1.0.0 evaluates completed 5-minute candles and generates explainable signals.
5. Independent Risk Engine enforces 0.5% risk, 1.0% daily loss cap, and transaction cost viability.
6. Virtual Broker simulates conservative limit fills with slippage, deducting exact statutory fees.
7. React dashboard renders real-time telemetry, charts, order book, and clear `PAPER` badges.
8. Real-time Telegram alerts notify the user of signals, fills, daily reports, and system state.
9. All automated unit, integration, and backtest suites pass with zero regressions.
10. Actual live trading remains securely locked (`LIVE_LOCKED`).
