import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  CandlestickChart,
  Globe,
  LineChart,
  ShieldAlert,
  Settings,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  ShieldX,
} from 'lucide-react';
import { CLEAN_PAPER_ACCOUNT_ID } from '../../lib/constants';

const navLinks = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/trading', label: 'Trading', icon: CandlestickChart },
  { path: '/research', label: 'Research', icon: Globe },
  { path: '/analytics', label: 'Analytics', icon: LineChart },
  { path: '/risk', label: 'Risk & Activity', icon: ShieldAlert },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  return (
    <aside
      className={`hidden md:flex flex-col bg-white border-r border-surface-200 transition-all duration-300 relative z-30 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand & Logo Header */}
      <div className="h-16 flex items-center px-4 border-b border-surface-200 justify-between">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-primary-600 text-white flex items-center justify-center font-bold shadow-sm flex-shrink-0">
            <TrendingUp className="w-5 h-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-tight text-slate-900 leading-tight">
                INTRADAY-BOT
              </span>
              <span className="text-[10px] text-primary-600 font-semibold tracking-wider uppercase">
                Paper Trading
              </span>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={onToggle}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-surface-100 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav List */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navLinks.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-primary-50 text-primary-700 font-semibold shadow-xs'
                    : 'text-slate-600 hover:bg-surface-50 hover:text-slate-900'
                }`
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Safety Notice & Target Account Footer */}
      {!collapsed ? (
        <div className="p-3 m-3 bg-surface-50 border border-surface-200 rounded-xl space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-rose-700 font-semibold">
            <ShieldX className="w-4 h-4 text-rose-600" />
            <span>Live Trading Disabled</span>
          </div>
          <div className="text-[11px] text-slate-500 font-mono leading-tight truncate">
            Acct: {CLEAN_PAPER_ACCOUNT_ID.slice(0, 8)}...
          </div>
          <div className="text-[10px] text-slate-400">
            Initial Capital: ₹10,000.00
          </div>
        </div>
      ) : (
        <div className="p-3 flex justify-center">
          <div
            className="w-8 h-8 rounded-lg bg-surface-100 text-rose-600 flex items-center justify-center"
            title="Paper Trading Only - Live Orders Disabled"
          >
            <ShieldX className="w-4 h-4" />
          </div>
        </div>
      )}
    </aside>
  );
};
