import React, { useState, useEffect } from 'react';
import {
  Settings,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Database,
  Clock,
  Info,
  Layers,
  Key,
  Server,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { pingSupabase } from '../lib/supabase';
import {
  CLEAN_PAPER_ACCOUNT_ID,
  CLEAN_PAPER_USER_ID,
  STARTING_CAPITAL_INR,
  STRATEGY_DETAILS,
  RISK_LIMITS,
} from '../lib/constants';
import { useAuth } from '../context/AuthContext';
import { formatINR } from '../lib/formatters';

export const SettingsPage: React.FC = () => {
  const [pingResult, setPingResult] = useState<{ ok: boolean; latencyMs: number; error?: string } | null>(null);
  const [pinging, setPinging] = useState(false);
  const { user, isOperator, operatorRole, linkOperatorAccess } = useAuth();
  const [linkStatus, setLinkStatus] = useState<string | null>(null);

  const testConnection = async () => {
    setPinging(true);
    const res = await pingSupabase();
    setPingResult(res);
    setPinging(false);
  };

  useEffect(() => {
    testConnection();
  }, []);

  const handleClaimOperator = async () => {
    setLinkStatus('Claiming access...');
    const res = await linkOperatorAccess();
    if (res.success) {
      setLinkStatus('Successfully linked as authorized operator!');
    } else {
      setLinkStatus(`Failed: ${res.error}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-surface-200 pb-4">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">System & Settings</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Authoritative environment configuration, database telemetry, and security parameters.
        </p>
      </div>

      {/* Safety & Environment Notice Banner */}
      <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 text-blue-950 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <div className="font-bold uppercase tracking-wider text-blue-900">
            Paper-Trading Only Operating Environment
          </div>
          <p className="text-blue-800 leading-relaxed">
            All trades, orders, and P&L allocations are strictly executed in simulated paper mode with realistic exchange slippage (0.05%) and statutory charges. Live broker order placement is hard-disabled at the architecture level.
          </p>
        </div>
      </div>

      {/* Grid: Account Configuration & Connectivity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account Details Card */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Key className="w-4 h-4 text-slate-500" />
              <span>Target Account Configuration</span>
            </h2>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 uppercase">
              Paper Ledger
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Trading Account ID:</span>
              <span className="font-mono text-slate-800 bg-surface-50 px-2 py-0.5 rounded">
                {CLEAN_PAPER_ACCOUNT_ID}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Bot User UUID:</span>
              <span className="font-mono text-slate-800 bg-surface-50 px-2 py-0.5 rounded">
                {CLEAN_PAPER_USER_ID}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Starting Capital:</span>
              <span className="font-mono font-bold text-slate-900">
                {formatINR(STARTING_CAPITAL_INR)}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Live Trading Status:</span>
              <span className="font-bold text-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                HARD-DISABLED
              </span>
            </div>

            <div className="flex items-center justify-between py-1">
              <span className="text-slate-500 font-medium">Market Timezone:</span>
              <span className="font-mono text-slate-800">
                Asia/Kolkata (IST, UTC+05:30)
              </span>
            </div>
          </div>
        </div>

        {/* Database & Supabase Connectivity */}
        <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-surface-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Database className="w-4 h-4 text-slate-500" />
              <span>Supabase Database Connectivity</span>
            </h2>
            <button
              onClick={testConnection}
              disabled={pinging}
              className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1 font-semibold"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${pinging ? 'animate-spin' : ''}`} />
              Ping Test
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Connection Status:</span>
              {pingResult ? (
                pingResult.ok ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    CONNECTED ({pingResult.latencyMs}ms)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                    <XCircle className="w-3.5 h-3.5 text-rose-600" />
                    ERROR: {pingResult.error}
                  </span>
                )
              ) : (
                <span className="text-slate-400">Testing connection...</span>
              )}
            </div>

            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Security Access Mode:</span>
              <span className="font-mono text-slate-700 bg-surface-50 px-2 py-0.5 rounded">
                Client Anon Key (Zero Privileged Secrets)
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-surface-50">
              <span className="text-slate-500 font-medium">Row Level Security (RLS):</span>
              <span className="text-emerald-700 font-bold">
                ENFORCED (Migrations 0001–0007)
              </span>
            </div>

            {/* Operator Auth Status */}
            <div className="pt-2 border-t border-surface-100 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-medium">Operator Session:</span>
                <span className="text-slate-800 font-semibold">
                  {user ? user.email : 'Not signed in'}
                </span>
              </div>
              {user && !isOperator && (
                <div className="mt-1">
                  <button
                    onClick={handleClaimOperator}
                    className="w-full py-1.5 px-3 rounded-lg bg-primary-50 text-primary-700 border border-primary-200 font-semibold hover:bg-primary-100 transition-colors"
                  >
                    Register as Authorized Account Viewer
                  </button>
                  {linkStatus && (
                    <div className="text-[11px] text-slate-500 mt-1 text-center">{linkStatus}</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Read-Only Strategy v1 Specifications */}
      <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-xs space-y-4">
        <div className="border-b border-surface-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary-600" />
            <span>Strategy v1 Specification (Read-Only)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Deterministic technical indicator rules and strict risk execution invariants.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
          {/* Indicators */}
          <div className="space-y-2">
            <div className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
              Active Indicators
            </div>
            <ul className="space-y-1.5 text-slate-600">
              {STRATEGY_DETAILS.indicators.map((ind, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-primary-600 font-bold">•</span>
                  <span>{ind}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Risk Rules */}
          <div className="space-y-2">
            <div className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
              Risk Control Rules
            </div>
            <ul className="space-y-1.5 text-slate-600">
              {STRATEGY_DETAILS.riskRules.map((rule, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-emerald-600 font-bold">•</span>
                  <span>{rule}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Execution Cost Model */}
          <div className="space-y-2">
            <div className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
              Realistic Cost Model
            </div>
            <ul className="space-y-1.5 text-slate-600">
              {STRATEGY_DETAILS.executionCosts.map((cost, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-slate-400 font-bold">•</span>
                  <span>{cost}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Software Metadata Footer */}
      <div className="p-4 rounded-xl bg-surface-50 border border-surface-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
        <div>
          <strong>Intraday-Bot UI:</strong> v1.0.0 (Production Release) • React 19 • Vite • Tailwind CSS
        </div>
        <div>
          Hosting Target: <strong>Vercel Free Tier</strong> • Framework: SPA
        </div>
      </div>
    </div>
  );
};

