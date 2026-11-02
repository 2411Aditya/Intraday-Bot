/**
 * System constants and strategy specifications for Intraday-Bot.
 */

export const CLEAN_PAPER_USER_ID = '00000000-0000-0000-0000-000000000002';
export const CLEAN_PAPER_ACCOUNT_ID = 'f8a6bf13-31e4-4429-98f5-5e2d4bc72d1b';
export const STARTING_CAPITAL_INR = 10000.0;

export const RISK_LIMITS = {
  startingCapital: STARTING_CAPITAL_INR,
  dailyLossLimitPct: 3.0, // 3% of capital = ₹300 max daily loss
  dailyLossLimitINR: 300.0,
  riskPerTradePct: 1.0,   // 1% of capital = ₹100 max risk per trade
  riskPerTradeINR: 100.0,
  maxDailyTrades: 3,
  maxOpenPositions: 1,
  minRiskRewardRatio: 1.5,
  entryCutoffIST: '14:45 IST',
  compulsorySquareOffIST: '15:15 IST',
  marketCloseIST: '15:30 IST',
  slippagePct: 0.05,      // 0.05% realistic paper slippage
};

export const STRATEGY_DETAILS = {
  name: 'Intraday Strategy v1',
  universe: 'NIFTY 50 Constituents',
  timeframe: '5-Minute Candles (Completed Closes Only)',
  indicators: [
    'VWAP (Volume-Weighted Average Price)',
    '15-Minute Opening Range Breakout (ORB: 09:15–09:30)',
    '9 EMA & 20 EMA Trend Alignment',
    'Volume > 1.2x 20-period Moving Average',
    'ATR (14) Volatility Bands for SL/TP',
  ],
  riskRules: [
    'Hard stop-loss derived from ATR and structural swing lows/highs',
    'Mandatory minimum 1:1.5 Risk-to-Reward ratio',
    'Strict fail-closed research gating before entries',
    'Single active position maximum (no multi-asset exposure overlap)',
    'Compulsory market-on-close square-off at 15:15 IST',
  ],
  executionCosts: [
    'NSE Equity Intraday Brokerage: 0.03% or ₹20/order (whichever lower)',
    'STT (Securities Transaction Tax): 0.025% on sell side',
    'Exchange Transaction Charges: 0.00345%',
    'SEBI Turnover Charges: 0.0001%',
    'Stamp Duty: 0.003% on buy side',
    'GST: 18% on brokerage and transaction charges',
    'Realistic Slippage: 0.05% on all entries and exits',
  ],
};

export const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: 'LayoutDashboard' },
  { path: '/trading', label: 'Trading', icon: 'CandlestickChart' },
  { path: '/research', label: 'Research', icon: 'Globe' },
  { path: '/analytics', label: 'Analytics', icon: 'LineChart' },
  { path: '/risk', label: 'Risk & Activity', icon: 'ShieldAlert' },
  { path: '/settings', label: 'Settings', icon: 'Settings' },
];
