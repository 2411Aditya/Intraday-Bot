import React from 'react';
import { RefreshCw, Activity, ShieldCheck, LogIn, LogOut, User as UserIcon } from 'lucide-react';
import { getMarketSessionStatus, timeAgo } from '../../lib/formatters';
import { useAuth } from '../../context/AuthContext';
import { Link } from 'react-router-dom';

export interface TopHeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
  lastHeartbeatTs?: string | null;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  onRefresh,
  isRefreshing,
  lastHeartbeatTs,
}) => {
  const sessionStatus = getMarketSessionStatus();
  const { user, isOperator, signOut } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-surface-200 px-4 md:px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Left side: Paper Trading Badge & Market Session Status */}
      <div className="flex items-center gap-2 md:gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold uppercase tracking-wider shadow-xs">
          <ShieldCheck className="w-4 h-4 text-blue-600" />
          <span>Paper Mode</span>
        </div>

        {/* Dynamic IST Market Status Pill */}
        <div
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium ${
            sessionStatus.badgeColor === 'emerald'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : sessionStatus.badgeColor === 'amber'
              ? 'bg-amber-50 text-amber-700 border-amber-200'
              : sessionStatus.badgeColor === 'rose'
              ? 'bg-rose-50 text-rose-700 border-rose-200'
              : 'bg-slate-50 text-slate-600 border-slate-200'
          }`}
          title={sessionStatus.nextEventText}
        >
          <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
          <span>{sessionStatus.statusText}</span>
        </div>

        {/* Worker Heartbeat */}
        {lastHeartbeatTs && (
          <div
            className="hidden lg:flex items-center gap-1.5 text-xs text-slate-500 bg-surface-50 border border-surface-200 px-2.5 py-1 rounded-md"
            title="Last completed 5-min candle processed by worker"
          >
            <Activity className="w-3.5 h-3.5 text-slate-400" />
            <span>Worker: {timeAgo(lastHeartbeatTs)}</span>
          </div>
        )}
      </div>

      {/* Right side: Actions, Refresh, Operator Status & Auth */}
      <div className="flex items-center gap-2 sm:gap-3">
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-surface-100 transition-colors border border-surface-200 disabled:opacity-50"
            title="Refresh dashboard data"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-primary-600' : ''}`} />
          </button>
        )}

        {/* Auth status */}
        {user ? (
          <div className="flex items-center gap-2">
            <div className="hidden md:flex flex-col text-right">
              <span className="text-xs font-medium text-slate-800 truncate max-w-[140px]">
                {user.email || 'Operator'}
              </span>
              <span className="text-[10px] text-slate-400">
                {isOperator ? 'Authorized Viewer' : 'Authenticated'}
              </span>
            </div>
            <button
              onClick={() => signOut()}
              className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors border border-surface-200"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-50 text-primary-700 border border-primary-200 hover:bg-primary-100 transition-colors shadow-xs"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </Link>
        )}
      </div>
    </header>
  );
};

