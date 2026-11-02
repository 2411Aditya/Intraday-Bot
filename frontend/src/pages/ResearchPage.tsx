import React, { useState } from 'react';
import {
  Globe,
  Clock,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  Info,
  Calendar,
  FileText,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
} from 'lucide-react';
import { useResearch } from '../hooks/useResearch';
import { StatusBadge } from '../components/common/StatusBadge';
import { FreshnessIndicator } from '../components/common/FreshnessIndicator';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { formatISTDateTime, formatISTTime, formatPct, timeAgo } from '../lib/formatters';

export const ResearchPage: React.FC = () => {
  const {
    latestSnapshot,
    overnightSnapshot,
    premarketSnapshot,
    snapshotsList,
    isLatestFresh,
    loading,
  } = useResearch();

  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);

  // Active snapshot to inspect (defaults to latest)
  const activeSnapshot = selectedSnapshotId
    ? snapshotsList.find((s) => s.id === selectedSnapshotId) || latestSnapshot
    : latestSnapshot;

  if (loading && !latestSnapshot) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={4} height="h-28" />
      </div>
    );
  }

  if (!activeSnapshot) {
    return (
      <EmptyState
        title="No Research Snapshots Available"
        description="The research engine produces automated snapshots at 23:00 IST (overnight), 08:30 IST (pre-market), and 16:00 IST (post-market)."
      />
    );
  }

  const snapData = activeSnapshot.snapshot_json || {};
  const globalIndices = snapData.global_indices || {};
  const fxCommodities = snapData.fx_commodities || {};
  const giftNifty = snapData.gift_nifty || {};
  const fiiDii = snapData.institutional_flows || {};
  const economicEvents = snapData.economic_events || {};
  const nseAnnouncements = snapData.nse_announcements || {};
  const riskWarnings = snapData.risk_warnings || [];

  const createdTime = new Date(activeSnapshot.created_at).getTime();
  const isStale = (Date.now() - createdTime) >= 6 * 3600 * 1000;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Market Intelligence Workspace</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-700 font-semibold uppercase">
              {activeSnapshot.session_type.replace('_', ' ')}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated multi-asset macro research, risk gating, and constituent sentiment.
          </p>
        </div>

        {/* Snapshot selector */}
        {snapshotsList.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Session:</span>
            <select
              value={activeSnapshot.id}
              onChange={(e) => setSelectedSnapshotId(e.target.value)}
              className="bg-white border border-surface-200 text-xs text-slate-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500 font-mono shadow-xs"
            >
              {snapshotsList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.session_type.toUpperCase()} • {s.trading_date} ({formatISTTime(s.created_at)})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Staleness / Gating Warning Banner */}
      {isStale && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <div className="font-bold uppercase tracking-wider text-amber-800">
              Snapshot is Stale (&gt;6 Hours Old)
            </div>
            <p className="text-amber-700">
              This snapshot was generated on {formatISTDateTime(activeSnapshot.created_at)}. Strategy v1 strictly suspends new trade entries when pre-market research is stale.
            </p>
          </div>
        </div>
      )}

      {/* Outlook & Overview Banner */}
      <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-surface-50 border border-surface-200">
              <Globe className="w-6 h-6 text-primary-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 font-medium">Synthesized Outlook:</span>
                <StatusBadge status={activeSnapshot.market_outlook} size="md" />
              </div>
              <div className="text-sm font-bold text-slate-900 mt-0.5 font-mono">
                Trading Date: {activeSnapshot.trading_date} • Session: {activeSnapshot.session_type.toUpperCase()}
              </div>
            </div>
          </div>

          <FreshnessIndicator
            timestamp={activeSnapshot.created_at}
            isFresh={!isStale}
            label="Created"
          />
        </div>

        {/* Risk Warnings List */}
        {riskWarnings.length > 0 && (
          <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 space-y-2">
            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-600" />
              Active Risk Factors & Warnings ({riskWarnings.length})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-700">
              {riskWarnings.map((w, idx) => (
                <div key={idx} className="flex items-start gap-1.5">
                  <span className="text-amber-500 font-bold">•</span>
                  <span>{w}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Grid 1: US & Asian Markets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* US Markets Card */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4 border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>US Markets (Wall Street Close)</span>
              <span className="text-xs text-slate-400 font-normal">Overnight sentiment</span>
            </h2>
            <StatusBadge status="yfinance" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { key: 'SP500', name: 'S&P 500', ticker: '^GSPC' },
              { key: 'NASDAQ', name: 'Nasdaq 100', ticker: '^IXIC' },
              { key: 'DOW', name: 'Dow Jones', ticker: '^DJI' },
            ].map(({ key, name, ticker }) => {
              const item = globalIndices[key] || {};
              const chg = item.change_pct;
              const isBlocked = item.status === 'BLOCKED' || !item.close;

              return (
                <div key={key} className="p-3 rounded-lg bg-surface-50 border border-surface-100">
                  <div className="text-xs font-semibold text-slate-600">{name}</div>
                  <div className="text-[10px] text-slate-400 font-mono">{ticker}</div>
                  {isBlocked ? (
                    <div className="text-xs font-medium text-amber-600 mt-2">Unavailable</div>
                  ) : (
                    <>
                      <div className="text-base font-bold font-mono text-slate-900 mt-1">
                        {item.close?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </div>
                      <div
                        className={`text-xs font-bold font-mono mt-0.5 ${
                          (chg || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                        }`}
                      >
                        {formatPct(chg)}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Asian / Global Indices Card */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4 border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>Asian & Pacific Indices</span>
              <span className="text-xs text-slate-400 font-normal">Morning trends</span>
            </h2>
            <StatusBadge status="yfinance" />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { key: 'NIKKEI', name: 'Nikkei 225', ticker: '^N225' },
              { key: 'HANGSENG', name: 'Hang Seng', ticker: '^HSI' },
              { key: 'KOSPI', name: 'KOSPI', ticker: '^KS11' },
              { key: 'ASX200', name: 'ASX 200', ticker: '^AXJO' },
            ].map(({ key, name, ticker }) => {
              const item = globalIndices[key] || {};
              const chg = item.change_pct;
              const isBlocked = item.status === 'BLOCKED' || !item.close;

              return (
                <div key={key} className="p-2.5 rounded-lg bg-surface-50 border border-surface-100">
                  <div className="text-xs font-semibold text-slate-600 truncate">{name}</div>
                  <div className="text-[10px] text-slate-400 font-mono">{ticker}</div>
                  {isBlocked ? (
                    <div className="text-xs font-medium text-amber-600 mt-2">Unavailable</div>
                  ) : (
                    <>
                      <div className="text-sm font-bold font-mono text-slate-900 mt-1 truncate">
                        {item.close?.toLocaleString('en-US', { minimumFractionDigits: 1 })}
                      </div>
                      <div
                        className={`text-xs font-bold font-mono mt-0.5 ${
                          (chg || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                        }`}
                      >
                        {formatPct(chg)}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Grid 2: FX, Commodities, India VIX & GIFT Nifty */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* FX, Commodities & Volatility */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4 border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900">FX, Commodities & Volatility</h2>
            <span className="text-xs text-slate-400 font-mono">USD/INR • Crude • VIX</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {/* USD/INR */}
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-100">
              <div className="text-xs font-semibold text-slate-600">USD / INR</div>
              <div className="text-[10px] text-slate-400 font-mono">USDINR=X</div>
              <div className="text-base font-bold font-mono text-slate-900 mt-1">
                ₹{fxCommodities['USDINR']?.close?.toFixed(2) || '—'}
              </div>
              <div
                className={`text-xs font-bold font-mono mt-0.5 ${
                  (fxCommodities['USDINR']?.change_pct || 0) > 0 ? 'text-rose-600' : 'text-emerald-600'
                }`}
              >
                {formatPct(fxCommodities['USDINR']?.change_pct)}
              </div>
            </div>

            {/* WTI Crude */}
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-100">
              <div className="text-xs font-semibold text-slate-600">WTI Crude Oil</div>
              <div className="text-[10px] text-slate-400 font-mono">CL=F</div>
              <div className="text-base font-bold font-mono text-slate-900 mt-1">
                ${fxCommodities['WTI_CRUDE']?.close?.toFixed(2) || '—'}
              </div>
              <div
                className={`text-xs font-bold font-mono mt-0.5 ${
                  (fxCommodities['WTI_CRUDE']?.change_pct || 0) > 0 ? 'text-amber-600' : 'text-slate-600'
                }`}
              >
                {formatPct(fxCommodities['WTI_CRUDE']?.change_pct)}
              </div>
            </div>

            {/* India VIX */}
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-100">
              <div className="text-xs font-semibold text-slate-600">India VIX</div>
              <div className="text-[10px] text-slate-400 font-mono">^INDIAVIX</div>
              <div className="text-base font-bold font-mono text-slate-900 mt-1">
                {fxCommodities['INDIA_VIX']?.close?.toFixed(2) || fxCommodities['CBOE_VIX']?.close?.toFixed(2) || '—'}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {Number(fxCommodities['INDIA_VIX']?.close || 0) > 20 ? (
                  <span className="text-rose-600 font-bold">High Volatility</span>
                ) : (
                  <span className="text-emerald-600 font-medium">Normal Range</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* GIFT Nifty & FII/DII Flows */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900">GIFT Nifty & Institutional Flows</h2>
            <StatusBadge status={giftNifty.status === 'OK' ? 'PROXY ACTIVE' : 'UNAVAILABLE'} />
          </div>

          {/* GIFT Nifty Provenance Box */}
          <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">GIFT Nifty Status:</span>
              <span className="text-xs font-mono font-bold text-slate-900">
                LTP: {giftNifty.ltp ? `₹${giftNifty.ltp}` : 'Unavailable'}
              </span>
            </div>
            <div className="text-[11px] text-slate-500 leading-relaxed bg-amber-50/70 p-2 rounded border border-amber-100 text-amber-900">
              <strong>Source Provenance Note:</strong> {giftNifty.note || 'NSE IFSC GIFT City direct feed is not accessible on retail Angel One accounts; fallback proxy from NSE/NFO closing is utilized.'}
            </div>
          </div>

          {/* FII / DII Flows */}
          <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">FII / DII Institutional Flows:</span>
              {fiiDii.fii_net_buy_sell !== undefined && fiiDii.fii_net_buy_sell !== null ? (
                <span className="text-xs font-mono font-bold text-slate-900">
                  Net: {fiiDii.fii_net_buy_sell} Cr
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                  NSE API Blocked (Headless Challenge)
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500">
              When NSE public web API blocks datacenter requests, the adapter flags <code>BLOCKED</code> and does NOT fabricate synthetic flow values.
            </p>
          </div>
        </div>
      </div>

      {/* Grid 3: Macro Events & NSE Announcements */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Economic Events */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-500" />
              <span>Federal Reserve & RBI Events</span>
            </h2>
            <span className="text-xs text-slate-400">Official RSS/XML</span>
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {economicEvents.fed_events && economicEvents.fed_events.length > 0 ? (
              economicEvents.fed_events.slice(0, 5).map((ev, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-surface-50 border border-surface-100 text-xs">
                  <div className="font-semibold text-slate-800">{ev.title}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{ev.date} • {ev.source}</div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-400 p-3 text-center">No upcoming Fed calendar events</div>
            )}

            <div className="text-[11px] text-slate-500 p-2 rounded bg-slate-50 border border-slate-200">
              <strong>RBI Calendar:</strong> {economicEvents.rbi_note || 'rbi.org.in blocks automated requests; manual check required for MPC dates.'}
            </div>
          </div>
        </div>

        {/* Corporate Announcements */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-500" />
              <span>NSE Corporate Announcements</span>
            </h2>
            <span className="text-xs text-slate-400 font-mono">
              {nseAnnouncements.announcements?.length || 0} items
            </span>
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {nseAnnouncements.announcements && nseAnnouncements.announcements.length > 0 ? (
              nseAnnouncements.announcements.slice(0, 5).map((ann, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-surface-50 border border-surface-100 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold font-mono text-slate-900">{ann.symbol}</span>
                    <span className="text-[10px] text-slate-400">{ann.dt || ''}</span>
                  </div>
                  <div className="text-slate-600 mt-1 line-clamp-2">{ann.desc || 'Corporate filing'}</div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-400 p-3 text-center">No corporate announcements for this period</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
