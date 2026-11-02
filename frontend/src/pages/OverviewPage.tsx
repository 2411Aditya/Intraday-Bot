import React from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Layers,
  Activity,
  AlertCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTradingAccount } from '../hooks/useTradingAccount';
import { usePositions } from '../hooks/usePositions';
import { useSignals } from '../hooks/useSignals';
import { useResearch } from '../hooks/useResearch';
import { StatCard } from '../components/common/StatCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { FreshnessIndicator } from '../components/common/FreshnessIndicator';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { EmptyState } from '../components/common/EmptyState';
import {
  formatINR,
  formatSignedINR,
  formatISTTime,
  formatISTDateTime,
  getMarketSessionStatus,
  timeAgo,
} from '../lib/formatters';
import { STARTING_CAPITAL_INR, RISK_LIMITS } from '../lib/constants';

export const OverviewPage: React.FC = () => {
  const {
    account,
    equity,
    cashBalance,
    realizedPnL,
    unrealizedPnL,
    totalPnL,
    workerState,
    loading: acctLoading,
    error: acctError,
    lastUpdated,
  } = useTradingAccount();

  const { openPositions, closedPositions, loading: posLoading } = usePositions();
  const { signals, loading: sigLoading } = useSignals();
  const { latestSnapshot, isLatestFresh, loading: resLoading } = useResearch();

  const sessionStatus = getMarketSessionStatus();
  const lastCandleTs = workerState && workerState.length > 0 ? workerState[0].last_processed_candle_ts : null;

  const todayStr = new Date().toISOString().split('T')[0];
  const todaySignals = signals.filter((s) => s.signal_time.startsWith(todayStr));
  const todayTradesCount = closedPositions.filter((p) => p.open_timestamp.startsWith(todayStr)).length + openPositions.length;

  if (acctLoading && !account) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={4} height="h-24" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner: Status, Heartbeat, and Data Freshness */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-surface-200 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900">Paper Trading Command Center</h1>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                ₹10,000 Clean Account
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Session: {sessionStatus.statusText} • {sessionStatus.nextEventText}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <FreshnessIndicator timestamp={lastUpdated} label="Sync" />
          {lastCandleTs && (
            <span
              className="text-xs px-2.5 py-1 rounded-full bg-surface-50 border border-surface-200 text-slate-600 hidden md:inline-flex items-center gap-1"
              title={`Last completed 5m candle: ${formatISTDateTime(lastCandleTs)}`}
            >
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              Candle: {timeAgo(lastCandleTs)}
            </span>
          )}
        </div>
      </div>

      {acctError && <ErrorBanner message={acctError} />}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Account Equity */}
        <StatCard
          title="Account Equity"
          value={formatINR(equity)}
          subValue={`Capital: ${formatINR(STARTING_CAPITAL_INR)}`}
          icon={Wallet}
          trend={totalPnL >= 0 ? 'up' : 'down'}
          trendValue={formatSignedINR(totalPnL)}
        />

        {/* Available Cash Balance */}
        <StatCard
          title="Cash Balance"
          value={formatINR(cashBalance)}
          subValue={`Reserved: ${formatINR(account?.reserved_margin || 0)}`}
          icon={Layers}
        />

        {/* Realized & Unrealized P&L */}
        <StatCard
          title="Realized P&L"
          value={formatSignedINR(realizedPnL)}
          subValue={`Unrealized: ${formatSignedINR(unrealizedPnL)}`}
          icon={realizedPnL >= 0 ? TrendingUp : TrendingDown}
          trend={realizedPnL >= 0 ? 'up' : 'down'}
          trendValue={totalPnL !== 0 ? `${((totalPnL / STARTING_CAPITAL_INR) * 100).toFixed(2)}%` : undefined}
        />

        {/* Active Positions & Daily Trades */}
        <StatCard
          title="Open Positions"
          value={openPositions.length}
          subValue={`Today's Trades: ${todayTradesCount} / ${RISK_LIMITS.maxDailyTrades} max`}
          icon={Activity}
          badge={
            openPositions.length > 0 ? (
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            ) : undefined
          }
        />
      </div>

      {/* Market Research Outlook Card */}
      <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">
              Market Research Outlook
            </h2>
            {latestSnapshot ? (
              <StatusBadge status={latestSnapshot.market_outlook} size="md" />
            ) : (
              <span className="text-xs text-slate-400">Loading outlook...</span>
            )}
            {latestSnapshot && (
              <span className="text-xs px-2 py-0.5 rounded bg-surface-100 text-slate-600 font-mono">
                {latestSnapshot.session_type.toUpperCase()} ({latestSnapshot.trading_date})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {latestSnapshot && (
              <FreshnessIndicator
                timestamp={latestSnapshot.created_at}
                isFresh={isLatestFresh}
                label="Research"
              />
            )}
            <Link
              to="/research"
              className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1 transition-colors"
            >
              Full Workspace
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Warnings & Gating Information */}
        {latestSnapshot ? (
          <div className="space-y-2">
            {!latestSnapshot.is_tradeable_session && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>
                  <strong>Non-Tradeable Session:</strong>{' '}
                  {latestSnapshot.snapshot_json?.no_trade_reason || 'Exchange Closed'}
                </span>
              </div>
            )}

            {latestSnapshot.snapshot_json?.risk_warnings &&
            latestSnapshot.snapshot_json.risk_warnings.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                {latestSnapshot.snapshot_json.risk_warnings.slice(0, 4).map((warn, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-lg bg-surface-50 border border-surface-200 text-xs text-slate-700 flex items-start gap-2"
                  >
                    <span className="text-amber-500 font-bold">•</span>
                    <span className="truncate">{warn}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 p-2 rounded bg-surface-50 border border-surface-100">
                No active macro risk warnings for this session.
              </div>
            )}

            {/* Watchlist Preview */}
            {latestSnapshot.snapshot_json?.watchlist &&
              latestSnapshot.snapshot_json.watchlist.length > 0 && (
                <div className="mt-3 pt-3 border-t border-surface-100 flex items-center gap-2 flex-wrap text-xs text-slate-600">
                  <span className="font-semibold text-slate-500">Watchlist Top Stocks:</span>
                  {latestSnapshot.snapshot_json.watchlist.slice(0, 6).map((item, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-md bg-surface-100 border border-surface-200 font-mono font-medium text-slate-700"
                    >
                      {item.symbol}
                      {item.change_pct_1d !== undefined && (
                        <span
                          className={`ml-1 text-[11px] ${
                            item.change_pct_1d >= 0 ? 'text-emerald-600' : 'text-rose-600'
                          }`}
                        >
                          {item.change_pct_1d >= 0 ? '+' : ''}
                          {item.change_pct_1d}%
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              )}
          </div>
        ) : (
          <EmptyState
            title="No Research Snapshot Found"
            description="Run pre-market research at 08:30 IST or trigger research workflow manually to generate the daily snapshot."
          />
        )}
      </div>

      {/* Two Column Layout: Open Positions & Recent Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Open Positions Card */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>Active Paper Positions</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-surface-100 text-slate-600 font-mono">
                  {openPositions.length}
                </span>
              </h2>
              <Link
                to="/trading"
                className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1"
              >
                View Trading
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {openPositions.length > 0 ? (
              <div className="divide-y divide-surface-100">
                {openPositions.map((pos) => (
                  <div key={pos.id} className="py-3 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900 font-mono">
                          {pos.symbol}
                        </span>
                        <StatusBadge status={pos.direction.toUpperCase()} />
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        Qty: {pos.quantity} • Entry: {formatINR(pos.avg_entry_price)} •{' '}
                        {timeAgo(pos.open_timestamp)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold font-mono text-slate-900">
                        {formatSignedINR(pos.realized_pnl)}
                      </div>
                      <span className="text-[11px] text-slate-400">
                        Opened {formatISTTime(pos.open_timestamp)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No Open Positions"
                description="The bot is waiting for qualified completed 5-min candle signals meeting Strategy v1 criteria."
                className="my-2"
              />
            )}
          </div>

          <div className="pt-3 border-t border-surface-100 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Max concurrent open positions: 1</span>
            <span>Compulsory Square-off: 15:15 IST</span>
          </div>
        </div>

        {/* Recent Strategy Signals Card */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>Recent Strategy Signals</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-surface-100 text-slate-600 font-mono">
                  {signals.length}
                </span>
              </h2>
              <Link
                to="/trading"
                className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1"
              >
                All Signals
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {signals.length > 0 ? (
              <div className="divide-y divide-surface-100">
                {signals.slice(0, 4).map((sig) => {
                  const decision = sig.risk_decision?.decision;
                  const isApproved = decision === 'approved';
                  return (
                    <div key={sig.id} className="py-2.5 flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-slate-900 font-mono">
                            {sig.symbol}
                          </span>
                          <StatusBadge status={sig.direction.toUpperCase()} />
                          <span className="text-xs font-mono text-slate-600">
                            @{formatINR(sig.price)}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {formatISTDateTime(sig.signal_time)}
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 text-xs">
                        {decision ? (
                          <div className="flex items-center gap-1">
                            {isApproved ? (
                              <CheckCircle className="w-4 h-4 text-emerald-500" />
                            ) : (
                              <XCircle className="w-4 h-4 text-rose-500" />
                            )}
                            <StatusBadge status={decision.toUpperCase()} />
                          </div>
                        ) : (
                          <span className="text-slate-400 text-xs">Evaluating</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="No Signals Generated Yet"
                description="Signals will appear when the 5-minute worker evaluates market hours candles."
                className="my-2"
              />
            )}
          </div>

          <div className="pt-3 border-t border-surface-100 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Timeframe: 5m Completed Closes</span>
            <span>Strategy: VWAP + ORB + 9/20 EMA</span>
          </div>
        </div>
      </div>
    </div>
  );
};

