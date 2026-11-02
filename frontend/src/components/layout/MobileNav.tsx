import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  CandlestickChart,
  Globe,
  LineChart,
  ShieldAlert,
  Settings,
} from 'lucide-react';

const mobileNavLinks = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/trading', label: 'Trading', icon: CandlestickChart },
  { path: '/research', label: 'Research', icon: Globe },
  { path: '/analytics', label: 'Analytics', icon: LineChart },
  { path: '/risk', label: 'Risk', icon: ShieldAlert },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const MobileNav: React.FC = () => {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-surface-200 px-2 py-1 flex items-center justify-around z-30 shadow-lg">
      {mobileNavLinks.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center py-1.5 px-2 rounded-lg text-[10px] font-medium transition-colors min-w-[50px] min-h-[44px] ${
                isActive
                  ? 'text-primary-600 font-semibold'
                  : 'text-slate-500 hover:text-slate-800'
              }`
            }
          >
            <Icon className="w-5 h-5 mb-0.5" />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
};
