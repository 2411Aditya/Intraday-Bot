import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  Download,
  CandlestickChart,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  Info,
} from 'lucide-react';
import { usePositions } from '../hooks/usePositions';
import { useOrders } from '../hooks/useOrders';
import { useSignals } from '../hooks/useSignals';
import { useResearch } from '../hooks/useResearch';
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

type TradingTab = 'open' | 'closed' | 'orders' | 'signals' | 'watchlist';

export const TradingPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TradingTab>('open');
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'long' | 'short'>('all');

  const { openPositions, closedPositions, loading: posLoading } = usePositions();
  const { orders, loading: ordersLoading } = useOrders();
  const { signals, loading: sigLoading } = useSignals();
  const { latestSnapshot, loading: resLoading } = useResearch();

  // Filtered & Searched Data
  const filteredOpenPositions = useMemo(() => {
    return openPositions.filter((p) => {
      const matchSearch = p.symbol.toLowerCase().includes(searchQuery.toLowerCase());
      const matchDir = directionFilter === 'all' || p.direction === directionFilter;
      return matchSearch && matchDir;
    });
  }, [openPositions, searchQuery, directionFilter]);

  const filteredClosedPositions = useMemo(() => {
    return closedPositions.filter((p) => {
      const matchSearch = p.symbol.toLowerCase().includes(searchQuery.toLowerCase());
      const matchDir = directionFilter === 'all' || p.direction === directionFilter;
      return matchSearch && matchDir;
    });
  }, [closedPositions, searchQuery, directionFilter]);

  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      const sym = o.intent?.symbol || '';
      return sym.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [orders, searchQuery]);

  const filteredSignals = useMemo(() => {
    return signals.filter((s) => {
      const matchSearch = s.symbol.toLowerCase().includes(searchQuery.toLowerCase());
      const matchDir = directionFilter === 'all' || s.direction === directionFilter;
      return matchSearch && matchDir;
    });
  }, [signals, searchQuery, directionFilter]);

  const watchlist = latestSnapshot?.snapshot_json?.watchlist || [];

  return (
    <div className="space-y-6">
      {/* Header & Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Trading Operations</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time paper trading ledger, executed orders, and strategy signals.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-1 bg-surface-100 p-1 rounded-xl self-start sm:self-auto overflow-x-auto max-w-full">
          <button
            onClick={() => setActiveTab('open')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'open'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Open Positions ({openPositions.length})
          </button>
          <button
            onClick={() => setActiveTab('closed')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'closed'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Closed ({closedPositions.length})
          </button>
          <button
            onClick={() => setActiveTab('orders')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'orders'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Orders ({orders.length})
          </button>
          <button
            onClick={() => setActiveTab('signals')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'signals'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Signals ({signals.length})
          </button>
          <button
            onClick={() => setActiveTab('watchlist')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'watchlist'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Watchlist ({watchlist.length})
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      {activeTab !== 'watchlist' && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-surface-200">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search symbol (e.g. SBIN)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-surface-50 border border-surface-200 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            {(activeTab === 'open' || activeTab === 'closed' || activeTab === 'signals') && (
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Filter className="w-3.5 h-3.5" />
                <select
                  value={directionFilter}
                  onChange={(e) => setDirectionFilter(e.target.value as any)}
                  className="bg-surface-50 border border-surface-200 rounded-lg px-2 py-1 text-xs text-slate-700 focus:outline-none"
                >
                  <option value="all">All Directions</option>
                  <option value="long">Long Only</option>
                  <option value="short">Short Only</option>
                </select>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab Content: OPEN POSITIONS */}
      {activeTab === 'open' && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
          {posLoading ? (
            <div className="p-6">
              <LoadingSkeleton rows={3} height="h-10" />
            </div>
          ) : filteredOpenPositions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                  <tr>
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4">Direction</th>
                    <th className="py-3 px-4 text-right">Quantity</th>
                    <th className="py-3 px-4 text-right">Avg Entry Price</th>
                    <th className="py-3 px-4 text-right">Realized P&L</th>
                    <th className="py-3 px-4">Entry Time</th>
                    <th className="py-3 px-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {filteredOpenPositions.map((pos) => (
                    <tr key={pos.id} className="hover:bg-surface-50/50 transition-colors">
                      <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                        {pos.symbol}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={pos.direction.toUpperCase()} />
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-medium">
                        {pos.quantity}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono">
                        {formatINR(pos.avg_entry_price)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold">
                        {formatSignedINR(pos.realized_pnl)}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">
                        {formatISTDateTime(pos.open_timestamp)}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <StatusBadge status="OPEN" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Active Paper Positions"
              description="No open trades found for the clean ₹10k paper account. New entries will trigger when strategy criteria align."
              className="m-4"
            />
          )}
        </div>
      )}

      {/* Tab Content: CLOSED POSITIONS */}
      {activeTab === 'closed' && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
          {posLoading ? (
            <div className="p-6">
              <LoadingSkeleton rows={4} height="h-10" />
            </div>
          ) : filteredClosedPositions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                  <tr>
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4">Direction</th>
                    <th className="py-3 px-4 text-right">Quantity</th>
                    <th className="py-3 px-4 text-right">Entry Price</th>
                    <th className="py-3 px-4 text-right">Realized Net P&L</th>
                    <th className="py-3 px-4">Open Time</th>
                    <th className="py-3 px-4">Close Time</th>
                    <th className="py-3 px-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {filteredClosedPositions.map((pos) => {
                    const pnl = Number(pos.realized_pnl);
                    return (
                      <tr key={pos.id} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                          {pos.symbol}
                        </td>
                        <td className="py-3.5 px-4">
                          <StatusBadge status={pos.direction.toUpperCase()} />
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-medium">
                          {pos.quantity}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono">
                          {formatINR(pos.avg_entry_price)}
                        </td>
                        <td
                          className={`py-3.5 px-4 text-right font-mono font-bold ${
                            pnl > 0 ? 'text-emerald-600' : pnl < 0 ? 'text-rose-600' : 'text-slate-700'
                          }`}
                        >
                          {formatSignedINR(pnl)}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500">
                          {formatISTTime(pos.open_timestamp)}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500">
                          {pos.close_timestamp ? formatISTTime(pos.close_timestamp) : '—'}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <StatusBadge status="CLOSED" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Closed Positions"
              description="No trade cycles have completed yet on this clean paper account. Historical audit records remain intact."
              className="m-4"
            />
          )}
        </div>
      )}

      {/* Tab Content: ORDERS */}
      {activeTab === 'orders' && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
          {ordersLoading ? (
            <div className="p-6">
              <LoadingSkeleton rows={4} height="h-10" />
            </div>
          ) : filteredOrders.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                  <tr>
                    <th className="py-3 px-4">Order ID</th>
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4">Side</th>
                    <th className="py-3 px-4 text-right">Quantity</th>
                    <th className="py-3 px-4 text-right">Fill Price</th>
                    <th className="py-3 px-4 text-right">Execution Fees</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {filteredOrders.map((o) => {
                    const fill = o.fills && o.fills.length > 0 ? o.fills[0] : null;
                    return (
                      <tr key={o.id} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500 truncate max-w-[100px]">
                          {o.id.slice(0, 8)}...
                        </td>
                        <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                          {o.intent?.symbol || '—'}
                        </td>
                        <td className="py-3.5 px-4">
                          <StatusBadge status={o.intent?.side?.toUpperCase() || 'BUY'} />
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-medium">
                          {fill ? fill.fill_quantity : o.intent?.quantity || '—'}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-semibold">
                          {fill ? formatINR(fill.fill_price) : 'Market'}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-slate-500">
                          {fill ? formatINR(fill.fees) : '₹0.00'}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <StatusBadge status={o.status.toUpperCase()} />
                        </td>
                        <td className="py-3.5 px-4 text-slate-500">
                          {formatISTDateTime(o.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Executed Paper Orders"
              description="Paper orders are placed after a strategy signal is approved by risk management."
              className="m-4"
            />
          )}
        </div>
      )}

      {/* Tab Content: SIGNALS */}
      {activeTab === 'signals' && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
          {sigLoading ? (
            <div className="p-6">
              <LoadingSkeleton rows={4} height="h-10" />
            </div>
          ) : filteredSignals.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                  <tr>
                    <th className="py-3 px-4">Signal Time</th>
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4">Direction</th>
                    <th className="py-3 px-4 text-right">Trigger Price</th>
                    <th className="py-3 px-4 text-center">Risk Decision</th>
                    <th className="py-3 px-4">Decision Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {filteredSignals.map((sig) => {
                    const dec = sig.risk_decision;
                    const isApproved = dec?.decision === 'approved';
                    return (
                      <tr key={sig.id} className="hover:bg-surface-50/50 transition-colors">
                        <td className="py-3.5 px-4 text-slate-600 font-mono">
                          {formatISTDateTime(sig.signal_time)}
                        </td>
                        <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                          {sig.symbol}
                        </td>
                        <td className="py-3.5 px-4">
                          <StatusBadge status={sig.direction.toUpperCase()} />
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-medium">
                          {formatINR(sig.price)}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {dec ? (
                            <StatusBadge status={dec.decision.toUpperCase()} />
                          ) : (
                            <span className="text-slate-400">Pending</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-slate-600 max-w-xs truncate" title={dec?.reason || ''}>
                          {dec?.reason || (isApproved ? 'Approved by risk engine' : '—')}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Strategy Signals"
              description="Signals generated by the 5-minute Strategy v1 worker will appear here."
              className="m-4"
            />
          )}
        </div>
      )}

      {/* Tab Content: WATCHLIST */}
      {activeTab === 'watchlist' && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-xs">
          {resLoading ? (
            <div className="p-6">
              <LoadingSkeleton rows={4} height="h-10" />
            </div>
          ) : watchlist.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 text-slate-500 uppercase font-semibold border-b border-surface-200">
                  <tr>
                    <th className="py-3 px-4">Rank</th>
                    <th className="py-3 px-4">Symbol</th>
                    <th className="py-3 px-4 text-right">1-Day Change</th>
                    <th className="py-3 px-4 text-right">Relative Strength Score</th>
                    <th className="py-3 px-4 text-center">Eligible for Entry</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {watchlist.map((item, idx) => (
                    <tr key={item.symbol} className="hover:bg-surface-50/50 transition-colors">
                      <td className="py-3.5 px-4 text-slate-400 font-mono">#{idx + 1}</td>
                      <td className="py-3.5 px-4 font-bold font-mono text-slate-900">
                        {item.symbol}
                      </td>
                      <td
                        className={`py-3.5 px-4 text-right font-mono font-medium ${
                          (item.change_pct_1d || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                        }`}
                      >
                        {(item.change_pct_1d || 0) >= 0 ? '+' : ''}
                        {(item.change_pct_1d || 0).toFixed(2)}%
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono">
                        {item.score !== undefined ? item.score.toFixed(2) : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <StatusBadge status="APPROVED" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No Watchlist In Snapshot"
              description="The pre-market research screening generates the top 10 ranked Nifty 50 watchlist every morning at 08:30 IST."
              className="m-4"
            />
          )}
        </div>
      )}
    </div>
  );
};

