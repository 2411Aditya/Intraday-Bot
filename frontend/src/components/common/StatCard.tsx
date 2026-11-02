import React from 'react';
import type { LucideIcon } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  badge?: React.ReactNode;
  hint?: string;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subValue,
  icon: Icon,
  trend,
  trendValue,
  badge,
  hint,
  className = '',
}) => {
  return (
    <div
      className={`bg-white rounded-xl border border-surface-200 p-4 shadow-sm hover:border-slate-300 transition-all ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider truncate">
          {title}
        </span>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {badge}
          {Icon && (
            <div className="p-1.5 rounded-lg bg-surface-50 text-slate-600 border border-surface-100">
              <Icon className="w-4 h-4" />
            </div>
          )}
        </div>
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <div className="text-xl md:text-2xl font-bold tracking-tight text-slate-900 font-mono">
          {value}
        </div>
        {trendValue && (
          <div
            className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
              trend === 'up'
                ? 'bg-emerald-50 text-emerald-700'
                : trend === 'down'
                ? 'bg-rose-50 text-rose-700'
                : 'bg-slate-50 text-slate-600'
            }`}
          >
            {trendValue}
          </div>
        )}
      </div>

      {(subValue || hint) && (
        <div className="mt-1 text-xs text-slate-400 truncate">
          {subValue || hint}
        </div>
      )}
    </div>
  );
};
