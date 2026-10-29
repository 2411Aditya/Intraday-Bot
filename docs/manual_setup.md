# Manual Setup Guide: External Services (Phase 1)

This guide provides exact, step-by-step instructions for provisioning the external free-tier services required by the platform.

> [!IMPORTANT]
> **Zero Infrastructure Cost Guarantee:** None of the required external services require paid plans. All steps operate strictly within verified free tiers (Supabase Free, Angel One Free Developer API, Telegram Bot Free, Oracle Always Free).
> 
> **Security Reminder:** Never post sensitive credentials (passwords, API keys, TOTP seeds, or service role keys) into the chat. You will place them directly into your local `.env` file.

---

## Task 1: Create a Free Supabase Cloud Database Project

### 1. Task Name
Setup Supabase PostgreSQL Cloud Database & Retrieve Connection Keys.

### 2. Why It Is Necessary
Supabase provides the persistent cloud PostgreSQL database (36 normalized tables) that stores historical candles, computed indicators, screening watchlists, virtual trading accounts, orders, positions, and operational audit logs.

### 3. Official Website URL
https://supabase.com

### 4. Exact Dashboard Section
**Projects** $\rightarrow$ **New project** $\rightarrow$ **Project Settings** $\rightarrow$ **API** & **Database**.

### 5. Buttons and Menu Options to Select
1. Navigate to https://supabase.com and click **Sign In** (you can sign in with your GitHub account).
2. On the organization dashboard, click the green button: **+ New project**.
3. In the creation modal:
   - **Organization:** Select your default personal organization.
   - **Name:** Enter `intraday-trading-bot` (or your preferred name).
   - **Database Password:** Click **Generate a password** or create a strong, secure password. **Copy and save this password immediately.**
   - **Region:** Select **South Asia (Mumbai) - `ap-south-1`** (this minimizes latency to NSE/Angel One servers).
   - **Pricing Plan:** Ensure **Free - $0/month** is selected.
4. Click **Create new project**. Wait 1–2 minutes while Supabase provisions the PostgreSQL cluster.
5. Once provisioned, click the **Settings** (gear icon) in the bottom-left sidebar.
6. Click **API** under Project Settings:
   - Copy the **Project URL** (`https://<project-id>.supabase.co`).
   - Copy the `anon` / `public` key.
   - Under **Project API keys**, reveal and copy the `service_role` / `secret` key.
7. Click **Database** under Project Settings:
   - Scroll down to **Connection parameters** or **Connection string**.
   - Select the **URI** tab and choose **Connection Pooling (Port 6543, Transaction mode)**.
   - Copy the pooled URI string (replace `[YOUR-PASSWORD]` with your actual database password).

### 6. Values to Enter in Local `.env`
Open your local `.env` file (copied from `.env.example`) and fill in:
```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_public_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_secret_service_role_key
SUPABASE_DB_URL=postgresql://postgres.your-project-id:your-db-password@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

### 7. Which Values Are Secrets?
- `Database Password` is a **CRITICAL SECRET**.
- `SUPABASE_SERVICE_ROLE_KEY` is a **CRITICAL SECRET** (bypasses RLS).
- `SUPABASE_DB_URL` contains your password and is a **CRITICAL SECRET**.
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` are public identifiers.

### 8. Expected Successful Result
A running Supabase PostgreSQL database located in Mumbai (`ap-south-1`) with API access enabled.

### 9. Verification Procedure
Run our backend database ping test script (provided in Phase 3) to execute `SELECT 1;` and verify active connectivity.

### 10. Common Errors
- *Error:* `FATAL: password authentication failed for user "postgres"`
  - *Cause:* Special characters in the password not properly URL-encoded in the connection string, or typo in password.
- *Error:* `Connection refused on port 5432`
  - *Cause:* Direct IPv6 connection issues on some domestic ISPs. Use the **Supavisor Pooled connection on Port 6543** which handles IPv4 routing cleanly.

### 11. Troubleshooting Steps
- If you forgot your database password, go to **Settings** $\rightarrow$ **Database** $\rightarrow$ **Database Password** $\rightarrow$ click **Reset database password**.

### 12. Cost & Free-Tier Implications
- **₹0.00 / completely free.**
- Supabase Free includes 500 MB database storage, 50,000 monthly active users, and 5 GB egress.
- Note: Our scheduled heartbeat ping prevents the project from pausing after 7 days of inactivity.

### 13. What to Report Back
Report back: *"Supabase project created in Mumbai region, connection keys retrieved, and saved into .env."* (Do not paste the keys in the chat).

---

## Task 2: Create Angel One SmartAPI Developer Credentials

### 1. Task Name
Register Angel One SmartAPI Developer Account & Generate API Keys.

### 2. Why It Is Necessary
Provides programmatic access to Angel One's market data infrastructure: historical daily/5-minute candlestick candles, real-time WebSocket 2.0 streaming quotes, scrip master tokens, and broker funds.

### 3. Official Website URL
https://smartapi.angelone.in

### 4. Exact Dashboard Section
**SmartAPI Developer Portal** $\rightarrow$ **My Apps** $\rightarrow$ **Create an App**.

### 5. Buttons and Menu Options to Select
1. Navigate to https://smartapi.angelone.in and click **Sign Up** (or **Login** using your registered Angel One client credentials).
2. In the top navigation bar, click **My Apps**.
3. Click the button: **+ Create an App**.
4. Fill out the application form:
   - **App Name:** `IntradayBot` (or your preferred name).
   - **App Type:** Select **Trading API** (or Market Data / Historical if separate).
   - **Client Code:** Enter your 8-character Angel One Client ID (e.g. `A1234567`).
   - **Redirect URL:** Enter `http://127.0.0.1:8000/callback` (or `https://localhost:8000`).
5. Click **Create App**.
6. On the **My Apps** dashboard:
   - Locate your created app.
   - Copy the **API Key** (e.g. an alphanumeric string).
7. Ensure Two-Factor Authentication (TOTP) is enabled on your Angel One trading account:
   - If not already enabled, open https://smartapi.angelone.in/enable-totp.
   - Enter your Client ID and Password/PIN.
   - Enter the OTP sent to your registered mobile/email.
   - A QR code and a **Base32 secret key** will be displayed. Copy and save this alphanumeric string (this is your `ANGELONE_TOTP_SECRET`).

### 6. Values to Enter in Local `.env`
```env
ANGELONE_API_KEY=your_api_key_from_smartapi_dashboard
ANGELONE_CLIENT_ID=your_angel_one_client_id
ANGELONE_PASSWORD=your_angel_one_mpin_or_trading_password
ANGELONE_TOTP_SECRET=your_base32_totp_secret_key
```

### 7. Which Values Are Secrets?
- `ANGELONE_PASSWORD` / MPIN is a **CRITICAL SECRET**.
- `ANGELONE_TOTP_SECRET` is a **CRITICAL SECRET** (generates one-time passwords).
- `ANGELONE_API_KEY` is a secret.

### 8. Expected Successful Result
An active SmartAPI App registered under your Angel One client code, with TOTP authentication configured.

### 9. Verification Procedure
Our automated connection test in Phase 4 executes `smart_api.generateSession()` and retrieves account details without placing any orders.

### 10. Common Errors
- *Error:* `Invalid TOTP` or `Session expired`
  - *Cause:* System clock skew on local machine. Ensure your system time is synchronized via NTP.
- *Error:* `Client code does not match`
  - *Cause:* Typo in client code (case sensitive).

### 11. Troubleshooting Steps
- Verify TOTP by generating a code at https://totp.danhersam.com using your secret and comparing it with Google Authenticator.

### 12. Cost & Free-Tier Implications
- **₹0.00 / completely free.**
- Angel One SmartAPI is free of charge for all Angel One trading account holders.

### 13. What to Report Back
Report back: *"Angel One SmartAPI credentials and TOTP secret generated and added to .env."*

---

## Task 3: Create a Free Telegram Notification Bot

### 1. Task Name
Setup Telegram Bot and Retrieve Bot Token & Chat ID.

### 2. Why It Is Necessary
Telegram provides instant, real-time mobile notifications for system heartbeats, pre-market candidate shortlists, paper trading signals, simulated fills, stop-loss triggers, daily loss cap alerts, and critical exceptions.

### 3. Official Website URL
https://web.telegram.org (or the Telegram mobile/desktop app).

### 4. Exact Dashboard Section
Chat with `@BotFather` and `@userinfobot`.

### 5. Buttons and Menu Options to Select
1. Open Telegram and search for `@BotFather` (ensure it has the official blue verification checkmark).
2. Click **Start** or send the command:
   ```text
   /newbot
   ```
3. BotFather will prompt: *Alright, a new bot. How are we going to call it? Please choose a name for your bot.*
   - Enter a display name, e.g.: `My Intraday Trading Bot`.
4. BotFather will prompt: *Good. Now let's choose a username for your bot. It must end in `bot`.*
   - Enter a unique username, e.g.: `aditya_intraday_bot` (or similar).
5. BotFather will reply with your new bot's URL and API token.
   - Copy the HTTP API token (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
6. Click the link to your new bot (e.g. `t.me/your_bot_username`) and click **Start** (or send `/start`) to initiate a conversation with it.
7. Now search for `@userinfobot` in Telegram and click **Start**.
   - It will reply with your personal Telegram numerical ID (e.g. `Id: 987654321`). Copy this number.

### 6. Values to Enter in Local `.env`
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321
```

### 7. Which Values Are Secrets?
- `TELEGRAM_BOT_TOKEN` is a secret (anyone with this token can send messages as your bot).

### 8. Expected Successful Result
A private Telegram bot ready to receive automated operational notifications.

### 9. Verification Procedure
A test curl or our Phase 12 notification test will dispatch: `Test alert from Intraday Trading Platform`.

### 10. Cost & Free-Tier Implications
- **₹0.00 / completely free.** Telegram Bot API has no subscription fees.

### 11. What to Report Back
Report back: *"Telegram bot created, token and chat ID added to .env."*
