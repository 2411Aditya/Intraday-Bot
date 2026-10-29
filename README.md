# Cloud-Based, Capital-Aware Automated Indian Intraday Trading Platform

[![Architecture](https://img.shields.io/badge/Architecture-Modular%20Event--Driven-blue.svg)](docs/architecture.md)
[![Trading Market](https://img.shields.io/badge/Market-NSE%20Cash%20Equities-orange.svg)](docs/strategy_specification.md)
[![Broker](https://img.shields.io/badge/Broker-Angel%20One%20SmartAPI-green.svg)](docs/angelone_setup.md)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg)](docs/supabase_setup.md)
[![Frontend](https://img.shields.io/badge/Frontend-React%2018%20%2B%20TypeScript%20%2B%20Vite-61DAFB.svg)](docs/frontend_deployment.md)
[![Cloud Worker](https://img.shields.io/badge/Cloud%20Compute-Oracle%20Always%20Free-F80000.svg)](docs/oracle_setup.md)
[![Infra Cost](https://img.shields.io/badge/Recurring%20Infra%20Cost-%E2%82%B90.00-success.svg)](docs/architecture.md)
[![Execution Mode](https://img.shields.io/badge/Default%20Mode-VIRTUAL%20PAPER%20TRADING-brightgreen.svg)](docs/mode_switching.md)

---

## 1. System Overview
An enterprise-grade, 24/7 cloud-hosted, capital-aware automated intraday trading platform built specifically for the Indian Equity Markets (NSE Cash Equities). 

Designed to operate entirely on **₹0 recurring cloud infrastructure**, the system runs autonomously on Oracle Cloud Always Free compute paired with Supabase PostgreSQL and a modern React/TypeScript dashboard hosted on Vercel Free / Cloudflare Pages.

### Key Highlights
- **Target Market:** National Stock Exchange of India (NSE) — Cash Equities (Nifty 50 screened universe). Long and Intraday Short positions. Zero overnight positions (15:00 IST mandatory square-off).
- **Core Strategy (`v1.0.0`):** Opening Range Breakout (ORB 15-min) + Session VWAP + 20-period EMA + Relative Volume (RVol $\ge 1.5$) + Candlestick Body Confirmation.
- **Capital-Aware Position Sizing:** Dynamically adapts share quantity and stock affordability to configured capital (₹3k, ₹5k, ₹10k, ₹25k, ₹50k, ₹100k) with real-world statutory fee modeling (STT, GST, Exchange charges, Stamp duty, Angel One brokerage). Rejects uneconomical trades.
- **Absolute Mode Isolation:** Virtual Paper Trading and Actual Live Trading are completely separated into dedicated schemas and execution pipelines. Live trading remains physically locked behind hard regulatory, static IP, and authorization gates.
- **Regulatory Compliance:** Compliant with SEBI's algorithmic trading circular (`SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013`) enforcing Static IP whitelisting, daily 2FA TOTP login, exchange order tagging, and price protection.

---

## 2. Technology Stack

| Layer | Technology | Infrastructure / Cost |
|---|---|---|
| **Backend & Trading Engine** | Python 3.11+, FastAPI, APScheduler, Uvicorn | Oracle Cloud Always Free VM (₹0) |
| **Market Data & Broker** | Angel One SmartAPI Python SDK & WebSocket 2.0 | Angel One Developer Portal (₹0) |
| **Database & Auth** | Supabase Managed PostgreSQL 15+, Supabase Auth, RLS | Supabase Free Tier (₹0) |
| **Frontend Dashboard** | React 18, TypeScript, Vite, TailwindCSS, Lightweight-Charts | Vercel Hobby / Cloudflare Pages (₹0) |
| **Notifications & Telemetry** | Telegram Bot API, Structured JSON logging, Health Watchdogs | Free Telegram Bot API (₹0) |
| **Data Processing & Analytics**| pandas, NumPy, custom event-driven backtester | Open Source (₹0) |

---

## 3. Repository Structure

```
Intraday-Bot/
├── .github/workflows/          # CI/CD & health verification workflows
├── backend/                    # Python FastAPI backend & 24/7 trading worker
│   ├── app/
│   │   ├── api/                # Versioned REST endpoints (OpenAPI)
│   │   ├── auth/               # JWT authentication & permission guards
│   │   ├── brokers/            # Execution adapters (paper/ vs angelone/)
│   │   ├── core/               # App configuration, security, event bus
│   │   ├── database/           # PostgreSQL connection & Supabase client
│   │   ├── global_intelligence/# Overnight macro & news collector
│   │   ├── indicators/         # Technical indicators (VWAP, EMA, ATR, ORB)
│   │   ├── market_data/        # Angel One SmartWebSocketV2 & tick aggregator
│   │   ├── monitoring/         # Telemetry, heartbeats, watchdogs
│   │   ├── notifications/      # Telegram notification service
│   │   ├── reconciliation/     # Order and position auditor
│   │   ├── risk/               # Independent risk engine & position sizer
│   │   ├── scheduling/         # APScheduler 24/7 daily workflow
│   │   ├── screening/          # Dynamic Nifty 50 morning stock screener
│   │   └── strategies/         # Strategy v1.0.0 implementation
│   ├── tests/                  # Automated pytest test suites
│   ├── Dockerfile              # Container definition for Oracle VM
│   └── requirements.txt        # Backend dependencies
├── frontend/                   # React 18 + TypeScript + Vite SPA
│   ├── src/
│   │   ├── charts/             # Financial charts (Candlesticks, VWAP, ORB)
│   │   ├── components/         # Reusable UI components & segmented mode switch
│   │   ├── contexts/           # App state, auth, and trading mode contexts
│   │   ├── pages/              # 20 required trading dashboard pages
│   │   └── services/           # Backend API clients & Supabase client
│   ├── package.json
│   └── vite.config.ts
├── supabase/
│   └── migrations/             # 36 normalized PostgreSQL tables with RLS
├── backtesting/                # Historical backtest engine & performance reports
├── deployment/                 # Oracle VM systemd service definitions & scripts
├── docs/                       # Comprehensive documentation suite
│   ├── architecture.md         # Full system architecture (Subsystems A-U)
│   ├── strategy_specification.md # Exact mathematical trading rules
│   ├── stock_selection.md      # Dynamic screening pipeline
│   ├── capital_management.md   # Position sizing & fee modeling
│   ├── mode_switching.md       # Virtual vs Actual state machine
│   ├── risk_management.md      # 12 independent risk veto gates
│   ├── manual_setup.md         # Manageable external service setup steps
│   ├── development_plan.md     # 17-phase implementation roadmap
│   └── research/
│       └── varsity_research.md # Zerodha Varsity & SEBI synthesis
├── .env.example                # Configuration template
└── README.md                   # This document
```

---

## 4. Current Milestone Status: Phase 1 Complete

- [x] **Phase 1: Research, Regulatory Verification & Complete Architecture**
  - Full Zerodha Varsity synthesis and hypotheses documented (`docs/research/varsity_research.md`).
  - SEBI algorithmic trading compliance framework analyzed (`docs/risk_management.md`).
  - Subsystems A through U specified (`docs/architecture.md`).
  - Strategy `v1.0.0` codified (`docs/strategy_specification.md`).
  - Dynamic screening and capital-aware sizing defined (`docs/stock_selection.md`, `docs/capital_management.md`).
  - First manual setup tasks prepared for the user (`docs/manual_setup.md`).
- [ ] **Phase 2: Repository Scaffolding, Tooling & Dependency Configuration** (Next)
- [ ] **Phase 3: Supabase Cloud Database Architecture, Migrations & RLS**
- [ ] **Phase 4: Angel One Market Data Engine & WebSocket 2.0**
- [ ] ...
- [ ] **Phase 15: Forward Paper-Trading Execution Milestone (Production Milestone 1)**
- [ ] **Phase 16-17: Angel One Live Broker Adapter & Live-Readiness Verification (Future Milestone)**

---

## 5. Getting Started (For the Operator)
Follow the step-by-step instructions in [`docs/manual_setup.md`](docs/manual_setup.md) to provision your free Supabase database, Angel One SmartAPI credentials, and Telegram Bot, then populate your local `.env`.
