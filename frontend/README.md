# Intraday-Bot Frontend

A high-performance, light-themed financial trading dashboard and macro research workspace for **Intraday-Bot**.

Built with React 19, TypeScript, Vite, Tailwind CSS, Recharts, and Supabase.

---

## 1. Operating Mode & Account Target

- **Trading Mode:** `PAPER ONLY` (Real-money live trading is hard-disabled).
- **Target Paper Account ID:** `f8a6bf13-31e4-4429-98f5-5e2d4bc72d1b`
- **User ID:** `00000000-0000-0000-0000-000000000002`
- **Initial Capital:** `₹10,000.00`
- **Timezone:** `Asia/Kolkata (IST, UTC+05:30)`

All read queries are executed directly against Supabase PostgreSQL via the client-side publishable key and Row Level Security (RLS). An always-on FastAPI server is **NOT** required for dashboard monitoring.

---

## 2. Application Architecture

```
frontend/
├── src/
│   ├── types/               # Authoritative TypeScript types mapped from Supabase schema
│   ├── lib/
│   │   ├── supabase.ts      # Supabase client with auth persistence & ping utility
│   │   ├── formatters.ts    # Currency (INR ₹), IST dates, percentages, market status
│   │   └── constants.ts     # Account IDs, Strategy v1 specs, risk limits, nav routes
│   ├── context/
│   │   └── AuthContext.tsx  # Supabase Auth session & operator authorization provider
│   ├── hooks/
│   │   ├── useTradingAccount.ts  # Account balance, equity, and worker heartbeat
│   │   ├── usePositions.ts       # Open and closed paper positions
│   │   ├── useOrders.ts          # Orders, intents, and fills
│   │   ├── useSignals.ts         # Strategy signals and risk decisions
│   │   ├── useResearch.ts        # Overnight, premarket, and postmarket research
│   │   ├── useAnalytics.ts       # Equity curve, win rate, profit factor, drawdown
│   │   └── useAuditLogs.ts       # Audit events, rejected signals, worker state
│   ├── components/
│   │   ├── common/          # StatCard, StatusBadge, FreshnessIndicator, EmptyState, etc.
│   │   └── layout/          # TopHeader, Sidebar (collapsible), MobileNav, AppLayout
│   └── pages/
│       ├── OverviewPage.tsx      # Command center KPIs, research outlook, quick signals
│       ├── TradingPage.tsx       # Open/closed positions, orders, signals, watchlist
│       ├── ResearchPage.tsx      # Multi-asset macro workspace & GIFT Nifty provenance
│       ├── AnalyticsPage.tsx     # Equity curve, P&L breakdown, and performance ratios
│       ├── RiskActivityPage.tsx  # Capital protection guards, rejections, worker telemetry
│       ├── SettingsPage.tsx      # Target account config, read-only Strategy v1, DB ping
│       └── LoginPage.tsx         # Operator authentication & viewer access
├── vercel.json              # Vercel SPA routing rewrite configuration
├── tailwind.config.js       # Light theme financial palette
└── package.json
```

---

## 3. Local Development

### Prerequisites
- Node.js `v20+` or `v24+`
- npm `v10+`

### Setup
1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Populate `.env` with your public Supabase URL and Anon Key:
   ```env
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
   VITE_TARGET_USER_ID=00000000-0000-0000-0000-000000000002
   VITE_TARGET_ACCOUNT_ID=f8a6bf13-31e4-4429-98f5-5e2d4bc72d1b
   VITE_APP_MODE=paper
   ```
4. Start the local Vite development server:
   ```bash
   npm run dev
   ```
5. Open `http://localhost:5173` in your browser.

---

## 4. Production Build & Verification

To verify TypeScript types and build the production bundle:
```bash
npm run build
```
The optimized static assets will be output to `frontend/dist/`.

---

## 5. Vercel Free-Tier Deployment

This frontend is fully configured for single-click deployment to **Vercel**:

1. In the Vercel Dashboard, import the repository `2411Aditya/Intraday-Bot`.
2. Set the **Root Directory** to `frontend`.
3. Framework Preset will auto-detect as **Vite**.
4. Configure the following **Environment Variables** in Vercel:
   - `VITE_SUPABASE_URL`: Your Supabase Project URL.
   - `VITE_SUPABASE_ANON_KEY`: Your Supabase Public Anon Key.
   - `VITE_TARGET_USER_ID`: `00000000-0000-0000-0000-000000000002`
   - `VITE_TARGET_ACCOUNT_ID`: `f8a6bf13-31e4-4429-98f5-5e2d4bc72d1b`
   - `VITE_APP_MODE`: `paper`
5. Click **Deploy**. Vercel will build and serve the application with SPA routing supported via [`vercel.json`](./vercel.json).

> [!IMPORTANT]
> **Zero Secrets Policy:** Never add `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, or Angel One API keys to Vercel environment variables or frontend code. The frontend operates strictly under Row Level Security using the publishable client key.
