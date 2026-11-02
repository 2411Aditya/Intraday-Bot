import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Activity,
  FileText,
  XCircle,
  CheckCircle2,
  Lock,
} from 'lucide-react';
import { useTradingAccount } from '../hooks/useTradingAccount';
import { usePositions } from '../hooks/usePositions';
import { useAuditLogs } from '../hooks/useAuditLogs';
import { useResearch } from '../hooks/useResearch';
import { StatCard } from '../components/common/StatCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import {
  formatINR,
  formatSignedINR,
  formatISTDateTime,
  formatISTTime,
  timeAgo,
} from '../lib/formatters';
import { RISK_LIMITS, STARTING_CAPITAL_INR } from '../lib/constants';

export const RiskActivityPage: React.FC = () => {
  const { realizedPnL, loading: acctLoading } = useTradingAccount();
  const { openPositions, closedPositions } = usePositions();
  const { auditLogs, rejections, workerState, loading: logsLoading } = useAuditLogs();
  const { latestSnapshot, isLatestFresh } = useResearch();

  const [activeTab, setActiveTab] = useState<'rejections' | 'audit' | 'worker'>('rejections');

  // Compute daily loss utilization (negative realized PnL today)
  const todayStr = new Date().toISOString().split('T')[0];
  const todayClosed = closedPositions.filter((p) => p.close_timestamp && p.close_timestamp.startsWith(todayStr));
  const todayRealizedLoss = Math.abs(
    todayClosed
      .filter((p) => Number(p.realized_pnl) < 0)
      .reduce((sum, p) => sum + Number(p.realized_pnl), 0)
  );
  const lossUtilizationPct = (todayRealizedLoss / RISK_LIMITS.dailyLossLimitINR) * 100;

  const todayTradesCount = todayClosed.length + openPositions.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Risk & Activity Oversight</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time capital protection guards, rejection logs, and worker execution telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Risk Engine: ENFORCING
          </span>
        </div>
      </div>

      {/* Risk Limits Dashboard Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Daily Loss Limit */}
        <StatCard
          title="Daily Loss Limit"
          value={formatINR(RISK_LIMITS.dailyLossLimitINR)}
          subValue={`Utilized: ${formatINR(todayRealizedLoss)} (${lossUtilizationPct.toFixed(1)}%)`}
          icon={ShieldAlert}
          badge={
            lossUtilizationPct >= 100 ? (
              <span className="text-xs text-rose-600 font-bold">BREACHED</span>
            ) : undefined
          }
        />

        {/* Risk Per Trade */}
        <StatCard
          title="Risk Per Trade"
          value={formatINR(RISK_LIMITS.riskPerTradeINR)}
          subValue="1.0% max capital risk per entry"
          icon={Lock}
        />

        {/* Max Daily Trades */}
        <StatCard
          title="Daily Trades Limit"
          value={`${todayTradesCount} / ${RISK_LIMITS.maxDailyTrades}`}
          subValue="Enforces max 3 entries per session"
          icon={Activity}
          trend={todayTradesCount >= RISK_LIMITS.maxDailyTrades ? 'down' : 'neutral'}
        />

        {/* Active Open Positions */}
        <StatCard
          title="Open Position Limit"
          value={`${openPositions.length} / ${RISK_LIMITS.maxOpenPositions}`}
          subValue="1 max position concurrency"
          icon={CheckCircle2}
        />
      </div>

      {/* Safety Gating Policies Overview */}
      <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2 border-b border-surface-100 pb-3">
          <ShieldCheck className="w-4 h-4 text-primary-600" />
          Automated Safety Gating Rules
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {/* Research Gating */}
          <div className="p-3.5 rounded-xl bg-surface-50 border border-surface-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Pre-Market Research Gating</span>
              <StatusBadge status={isLatestFresh ? 'ACTIVE' : 'FAIL-CLOSED'} />
            </div>
            <p className="text-slate-600 leading-relaxed">
              New trade entries are strictly blocked if today's pre-market research is missing, stale (&gt;6h), or indicates <code>HIGH_RISK</code> outlook.
            </p>
          </div>

          {/* Time Gating */}
          <div className="p-3.5 rounded-xl bg-surface-50 border border-surface-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Session Entry Cutoff</span>
              <span className="font-mono font-semibold text-slate-700">14:45 IST</span>
            </div>
            <p className="text-slate-600 leading-relaxed">
              No new trade signals may be accepted after 14:45 IST to prevent entering high-risk late-session market volatility.
            </p>
          </div>

          {/* Square-off Gating */}
          <div className="p-3.5 rounded-xl bg-surface-50 border border-surface-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Compulsory Square-Off</span>
              <span className="font-mono font-semibold text-rose-700">15:15 IST</span>
            </div>
            <p className="text-slate-600 leading-relaxed">
              All open paper positions are forcefully exited at 15:15 IST with realistic 0.05% slippage and standard NSE exchange fees applied.
            </p>
          </div>
        </div>
      </div>

      {/* Tabbed Activity & Audit Ledger */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b border-surface-200 pb-2">
          <button
            onClick={() => setActiveTab('rejections')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'rejections'
                ? 'bg-white text-slate-900 border border-surface-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Rejected Signals ({rejections.length})
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'audit'
                ? 'bg-white text-slate-900 border border-surface-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Audit Log Ledger ({auditLogs.length})
          </button>
          <button
            onClick={() => setActiveTab('worker')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'worker'
                ? 'bg-white text-slate-900 border border-surface-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Worker Telemetry ({workerState.length})
          </button>
        </div>

        {/* Tab 1: REJECTIONS */}
        {activeTab === 'rejections' && (
          <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
            {logsLoading ? (
              <div className="p-6">
                <LoadingSkeleton rows={4} height="h-10" />
              </div>
            ) : rejections.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                    <tr>
                      <th className="py-3 px-4">Time</th>
                      <th className="py-3 px-4">Decision</th>
                      <th className="py-3 px-4">Rejection Reason</th>
                      <th className="py-3 px-4">Signal ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {rejections.map((rej) => (
                      <tr key={rej.id} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 text-slate-600 font-mono">
                          {formatISTDateTime(rej.created_at)}
                        </td>
                        <td className="py-3.5 px-4">
                          <StatusBadge status="REJECTED" />
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {rej.reason || 'Blocked by risk parameters'}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                          {rej.signal_id?.slice(0, 8)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No Rejected Signals Recorded"
                description="Signals blocked by daily loss limits, cost drag, or session hours will be cataloged here."
                className="m-4"
              />
            )}
          </div>
        )}

        {/* Tab 2: AUDIT LOGS */}
        {activeTab === 'audit' && (
          <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
            {logsLoading ? (
              <div className="p-6">
                <LoadingSkeleton rows={4} height="h-10" />
              </div>
            ) : auditLogs.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                    <tr>
                      <th className="py-3 px-4">Logged At</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Table</th>
                      <th className="py-3 px-4">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 text-slate-600 font-mono">
                          {formatISTDateTime(log.logged_at)}
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {log.action}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-slate-600">
                          {log.table_name}
                        </td>
                        <td className="py-3.5 px-4 text-[11px] text-slate-500 font-mono truncate max-w-sm">
                          {log.details ? JSON.stringify(log.details) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No Audit Logs Found"
                description="Immutable write-once audit events from trade reservations and state transitions."
                className="m-4"
              />
            )}
          </div>
        )}

        {/* Tab 3: WORKER TELEMETRY */}
        {activeTab === 'worker' && (
          <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
            {logsLoading ? (
              <div className="p-6">
                <LoadingSkeleton rows={4} height="h-10" />
              </div>
            ) : workerState.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                    <tr>
                      <th className="py-3 px-4">Symbol</th>
                      <th className="py-3 px-4">Trading Date</th>
                      <th className="py-3 px-4">Last Processed Candle (IST)</th>
                      <th className="py-3 px-4">Age</th>
                      <th className="py-3 px-4">Last Evaluated Signal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {workerState.map((ws, i) => (
                      <tr key={i} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                          {ws.symbol}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-slate-600">
                          {ws.trading_date}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-slate-800">
                          {formatISTDateTime(ws.last_processed_candle_ts)}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500">
                          {timeAgo(ws.last_processed_candle_ts)}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                          {ws.last_evaluated_signal_id ? `${ws.last_evaluated_signal_id.slice(0, 8)}...` : 'None'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No Worker Candle Telemetry"
                description="Worker state records persist completed 5-minute candle timestamps during market sessions."
                className="m-4"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
