/**
 * Core domain types for Intraday-Bot Frontend.
 * authoritatively mapped from Supabase PostgreSQL schema and ResearchEngine models.
 */

export type TradingMode = 'paper' | 'live';

export type PositionStatus = 'open' | 'closed';

export type OrderStatus = 'pending' | 'filled' | 'partial' | 'canceled';

export type Direction = 'long' | 'short';

export type Side = 'buy' | 'sell';

export type RiskDecisionStatus = 'approved' | 'rejected';

export type MarketOutlook = 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'HIGH_RISK';

export type SessionType = 'overnight' | 'pre_market' | 'post_market';

export interface TradingAccount {
  id: string;
  user_id: string;
  mode: TradingMode;
  cash_balance: number;
  reserved_margin: number;
  deployed_margin: number;
  created_at: string;
  updated_at: string;
}

export interface AccountSnapshot {
  id: string;
  account_id: string;
  snapshot_ts: string;
  cash_balance: number;
  reserved_margin: number;
  deployed_margin: number;
  position_market_value: number;
  total_equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  created_at: string;
}

export interface Position {
  id: string;
  account_id: string;
  symbol: string;
  direction: Direction;
  quantity: number;
  avg_entry_price: number;
  open_timestamp: string;
  close_timestamp: string | null;
  realized_pnl: number;
  status: PositionStatus;
  created_at: string;
  // Optional enriched fields
  current_price?: number;
  unrealized_pnl?: number;
  stop_loss?: number;
  target?: number;
}

export interface OrderIntent {
  id: string;
  risk_id: string;
  account_id: string;
  mode: TradingMode;
  symbol: string;
  quantity: number;
  side: Side;
  limit_price: number | null;
  created_at: string;
}

export interface Order {
  id: string;
  intent_id: string;
  account_id: string;
  mode: TradingMode;
  status: OrderStatus;
  created_at: string;
  // Joined intent & fill fields
  intent?: OrderIntent;
  fills?: OrderFill[];
}

export interface OrderFill {
  id: string;
  order_id: string;
  fill_execution_id: string;
  fill_price: number;
  fill_quantity: number;
  fill_timestamp: string;
  fees: number;
  created_at: string;
}

export interface StrategySignal {
  id: string;
  user_id: string;
  symbol: string;
  signal_time: string;
  direction: Direction;
  price: number;
  created_at: string;
  // Joined risk decision
  risk_decision?: RiskDecision;
}

export interface RiskDecision {
  id: string;
  signal_id: string;
  account_id: string;
  decision: RiskDecisionStatus;
  reason: string | null;
  created_at: string;
}

export interface ResearchSnapshot {
  id: string;
  snapshot_id: string;
  session_type: SessionType;
  trading_date: string;
  created_at: string;
  snapshot_json: ResearchSnapshotData;
  market_outlook: MarketOutlook;
  is_tradeable_session: boolean;
}

export interface ResearchSnapshotData {
  global_indices?: Record<string, IndexItem>;
  gift_nifty?: GiftNiftyItem;
  fx_commodities?: Record<string, CommodityItem>;
  institutional_flows?: InstitutionalFlowsItem;
  economic_events?: EconomicEventsItem;
  nse_announcements?: NseAnnouncementsItem;
  market_outlook?: MarketOutlook;
  risk_warnings?: string[];
  allowed_symbols?: string[];
  watchlist?: WatchlistItem[];
  sector_scores?: Record<string, number>;
  provider_statuses?: Record<string, string>;
  is_tradeable_session?: boolean;
  no_trade_reason?: string | null;
}

export interface IndexItem {
  ticker?: string;
  close?: number;
  prev_close?: number;
  change_pct?: number;
  timestamp?: string;
  status?: string;
  reason?: string;
}

export interface GiftNiftyItem {
  status?: string;
  exchange?: string;
  symbol?: string;
  token?: string;
  ltp?: number;
  note?: string;
  error?: string;
}

export interface CommodityItem {
  ticker?: string;
  close?: number;
  change_pct?: number;
  timestamp?: string;
  status?: string;
  reason?: string;
}

export interface InstitutionalFlowsItem {
  date?: string;
  fii_net_buy_sell?: number | string | null;
  dii_net_buy_sell?: number | string | null;
  raw?: any;
}

export interface EconomicEventsItem {
  fed_events?: Array<{ title: string; date: string; link: string; source: string }>;
  rbi_events?: any[];
  rbi_note?: string;
}

export interface NseAnnouncementsItem {
  announcements?: Array<{ symbol: string; desc: string; dt: string; [key: string]: any }>;
  earnings?: Array<{ symbol: string; [key: string]: any }>;
}

export interface WatchlistItem {
  symbol: string;
  score?: number;
  change_pct_1d?: number;
}

export interface WorkerCandleState {
  symbol: string;
  trading_date: string;
  last_processed_candle_ts: string;
  last_evaluated_signal_id: string | null;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  table_name: string;
  record_id: string;
  details: Record<string, any> | null;
  logged_at: string;
}

export interface BotOperator {
  id: string;
  user_id: string;
  target_account_id: string;
  role: string;
  created_at: string;
}

