# Environment Variables Reference Guide

This document lists all environment variables required by the backend, worker, and frontend. 

A corresponding template file is provided at `.env.example`.

---

## 1. Environment Variable Reference

### A. Angel One SmartAPI Credentials
- `ANGELONE_API_KEY`: Developer API Key obtained from the SmartAPI developer console.
- `ANGELONE_CLIENT_ID`: Angel One 8-character client code (e.g. `A1234567`).
- `ANGELONE_PASSWORD`: Angel One 4-digit MPIN or trading password.
- `ANGELONE_TOTP_SECRET`: Base32 TOTP secret string (from Google Authenticator setup on Angel One).

### B. Supabase Cloud Database Credentials
- `SUPABASE_URL`: HTTPS URL of your Supabase project (e.g. `https://xyzproject.supabase.co`).
- `SUPABASE_ANON_KEY`: Public anonymous client key (safe for browser read-only queries with RLS).
- `SUPABASE_SERVICE_ROLE_KEY`: Administrative server key (MUST BE KEPT SECRET; used exclusively by backend worker).
- `SUPABASE_DB_URL`: Direct PostgreSQL connection string (e.g. `postgresql://postgres:password@db.xyzproject.supabase.co:5432/postgres` or port 6543 for Supavisor pooler).

### C. Telegram Bot Notifications
- `TELEGRAM_BOT_TOKEN`: API Token from @BotFather (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
- `TELEGRAM_CHAT_ID`: Your numerical Telegram user/chat ID (obtained via @userinfobot).

### D. Application Runtime Configuration
- `APP_ENV`: `development` or `production`.
- `TRADING_MODE`: `paper` (default) or `actual`.
- `LIVE_TRADING_ENABLED`: `false` (default) or `true`. (Hard gate: must be explicitly true for live execution).
- `TIMEZONE`: `Asia/Kolkata` (Default trading timezone).
- `API_PORT`: `8000` (FastAPI local bind port).
- `REGISTERED_STATIC_IP`: Outbound public IPv4 of the Oracle Cloud VM registered in Angel One console.

### E. Strategy & Risk Parameters
- `RISK_PER_TRADE_PCT`: `0.5` (Percentage of equity risked per trade).
- `MAX_DAILY_LOSS_PCT`: `1.0` (Percentage daily loss circuit breaker).
- `MAX_TRADES_PER_DAY`: `2` (Daily trade count cap).
- `MAX_OPEN_POSITIONS`: `1` (Concurrent open position cap).
- `DEFAULT_REWARD_RISK`: `2.0` (Minimum planned RRR).
- `VIRTUAL_STARTING_CAPITAL`: `10000` (Default virtual paper account cash balance in INR).
- `MAX_SLIPPAGE_PCT`: `0.05` (Modeled slippage on simulated fills).
