import React, { useState } from 'react';
import {
  LineChart as LineChartIcon,
  TrendingUp,
  TrendingDown,
  Percent,
  DollarSign,
  AlertCircle,
  BarChart3,
  Scale,
  Calendar,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from 'recharts';
import { useAnalytics } from '../hooks/useAnalytics';
import { StatCard } from '../components/common/StatCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import {
  formatINR,
  formatSignedINR,
  formatPct,
  formatISTDate,
  formatISTTime,
  formatISTDateTime,
} from '../lib/formatters';
import { STARTING_CAPITAL_INR } from '../lib/constants';

export const AnalyticsPage: React.FC = () => {
  const {
    snapshots,
    positions,
    equityCurve,
    symbolStats,
    hasEnoughData,
    closedCount,
    winRate,
    profitFactor,
    avgWin,
    avgLoss,
    avgRMultiple,
    totalFeesPaid,
    maxDrawdownINR,
    maxDrawdownPct,
    loading,
    error,
  } = useAnalytics();

  const [dateRange, setDateRange] = useState<'all' | '7d' | '30d'>('all');

  if (loading && snapshots.length === 0) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={4} height="h-28" />
      </div>
    );
  }

  // Fallback / initial baseline curve if snapshots are empty
  const chartData = equityCurve.length > 0 ? equityCurve : [
    { timestamp: new Date().toISOString(), equity: STARTING_CAPITAL_INR, realizedPnL: 0, drawdownINR: 0 }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Performance Analytics</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Verified paper trading metrics, equity curve progression, and mathematical ratios.
          </p>
        </div>

        {/* Date Filter */}
        <div className="flex items-center gap-1.5 bg-surface-100 p-1 rounded-xl text-xs font-medium self-start sm:self-auto">
          <Calendar className="w-3.5 h-3.5 text-slate-500 ml-1.5" />
          <button
            onClick={() => setDateRange('7d')}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              dateRange === '7d' ? 'bg-white text-slate-900 font-semibold shadow-xs' : 'text-slate-600'
            }`}
          >
            7D
          </button>
          <button
            onClick={() => setDateRange('30d')}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              dateRange === '30d' ? 'bg-white text-slate-900 font-semibold shadow-xs' : 'text-slate-600'
            }`}
          >
            30D
          </button>
          <button
            onClick={() => setDateRange('all')}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              dateRange === 'all' ? 'bg-white text-slate-900 font-semibold shadow-xs' : 'text-slate-600'
            }`}
          >
            All Time
          </button>
        </div>
      </div>

      {/* Primary Performance Ratios Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Win Rate */}
        <StatCard
          title="Win Rate"
          value={hasEnoughData && winRate !== null ? `${winRate.toFixed(1)}%` : 'Not enough data'}
          subValue={hasEnoughData ? `${positions.filter(p => Number(p.realized_pnl) > 0).length} of ${closedCount} closed trades` : 'Requires completed trades'}
          icon={Percent}
        />

        {/* Profit Factor */}
        <StatCard
          title="Profit Factor"
          value={hasEnoughData && profitFactor !== null ? profitFactor.toFixed(2) : 'Not enough data'}
          subValue={hasEnoughData ? 'Gross Profit / Gross Loss' : 'Baseline ratio'}
          icon={Scale}
        />

        {/* Realized R-Multiple */}
        <StatCard
          title="Avg Realized R"
          value={hasEnoughData && avgRMultiple !== null ? `${avgRMultiple.toFixed(2)}R` : 'Not enough data'}
          subValue="Target: ≥ 1.50R risk-to-reward"
          icon={TrendingUp}
        />

        {/* Max Drawdown */}
        <StatCard
          title="Maximum Drawdown"
          value={hasEnoughData ? formatINR(maxDrawdownINR) : '₹0.00'}
          subValue={hasEnoughData ? `${maxDrawdownPct.toFixed(2)}% of peak equity` : 'No drawdown recorded'}
          icon={TrendingDown}
          trend={maxDrawdownINR > 0 ? 'down' : 'neutral'}
        />
      </div>

      {/* Secondary Metrics: Avg Win/Loss & Execution Costs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-surface-200">
          <div className="text-xs font-semibold text-slate-500 uppercase">Average Winning Trade</div>
          <div className="text-xl font-bold font-mono text-emerald-600 mt-1">
            {hasEnoughData && avgWin !== null ? formatSignedINR(avgWin) : 'Not enough data'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Average profit on green exits</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-surface-200">
          <div className="text-xs font-semibold text-slate-500 uppercase">Average Losing Trade</div>
          <div className="text-xl font-bold font-mono text-rose-600 mt-1">
            {hasEnoughData && avgLoss !== null ? `-${formatINR(avgLoss)}` : 'Not enough data'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Hard-capped by 1% ATR stop loss</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-surface-200">
          <div className="text-xs font-semibold text-slate-500 uppercase">Total Execution Costs</div>
          <div className="text-xl font-bold font-mono text-slate-800 mt-1">
            {formatINR(totalFeesPaid)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">0.05% slippage + taxes + brokerage</div>
        </div>
      </div>

      {/* Equity Curve Chart */}
      <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4 border-b border-surface-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Account Equity Curve</h2>
            <p className="text-xs text-slate-400">Total portfolio valuation progression over time.</p>
          </div>
          <span className="text-xs font-mono font-semibold px-2 py-1 rounded bg-surface-50 border border-surface-200 text-slate-700">
            Initial Capital: ₹10,000.00
          </span>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(ts) => formatISTDate(ts)}
                tick={{ fontSize: 11, fill: '#64748B' }}
                axisLine={{ stroke: '#E2E8F0' }}
                tickLine={false}
              />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(val) => `₹${val.toLocaleString('en-IN')}`}
                tick={{ fontSize: 11, fill: '#64748B' }}
                axisLine={{ stroke: '#E2E8F0' }}
                tickLine={false}
                orientation="right"
              />
              <Tooltip
                formatter={(val: any) => [formatINR(val), 'Equity']}
                labelFormatter={(ts) => formatISTDateTime(ts as string)}
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  borderColor: '#E2E8F0',
                  borderRadius: '0.75rem',
                  fontSize: '12px',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                }}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="#2563EB"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#equityGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance by Symbol Table */}
      <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
        <div className="p-4 border-b border-surface-200">
          <h2 className="text-sm font-bold text-slate-900">Performance Breakdown by Symbol</h2>
          <p className="text-xs text-slate-400">Constituent trade count and net realized returns.</p>
        </div>

        {symbolStats.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                <tr>
                  <th className="py-3 px-4">Symbol</th>
                  <th className="py-3 px-4 text-right">Trades</th>
                  <th className="py-3 px-4 text-right">Wins</th>
                  <th className="py-3 px-4 text-right">Losses</th>
                  <th className="py-3 px-4 text-right">Win Rate</th>
                  <th className="py-3 px-4 text-right">Net Realized P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {symbolStats.map((stat) => (
                  <tr key={stat.symbol} className="hover:bg-surface-50/50 transition-colors">
                    <td className="py-3 px-4 font-bold font-mono text-slate-900">{stat.symbol}</td>
                    <td className="py-3 px-4 text-right font-mono">{stat.totalTrades}</td>
                    <td className="py-3 px-4 text-right font-mono text-emerald-600">{stat.winTrades}</td>
                    <td className="py-3 px-4 text-right font-mono text-rose-600">{stat.lossTrades}</td>
                    <td className="py-3 px-4 text-right font-mono font-medium">
                      {stat.winRate.toFixed(1)}%
                    </td>
                    <td
                      className={`py-3 px-4 text-right font-mono font-bold ${
                        stat.netPnL >= 0 ? 'text-emerald-600' : 'text-rose-600'
                      }`}
                    >
                      {formatSignedINR(stat.netPnL)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="Not Enough Data for Symbol Breakdown"
            description="Symbol performance metrics will automatically populate after paper trades are executed and closed."
            className="m-4"
          />
        )}
      </div>
    </div>
  );
};
