import React from 'react';
import { Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { timeAgo, formatISTTime } from '../../lib/formatters';

export interface FreshnessIndicatorProps {
  timestamp: string | null | undefined;
  isFresh?: boolean;
  label?: string;
  className?: string;
}

export const FreshnessIndicator: React.FC<FreshnessIndicatorProps> = ({
  timestamp,
  isFresh = true,
  label = 'Updated',
  className = '',
}) => {
  if (!timestamp) {
    return (
      <div className={`inline-flex items-center gap-1.5 text-xs text-slate-400 ${className}`}>
        <Clock className="w-3.5 h-3.5" />
        <span>No data timestamp</span>
      </div>
    );
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
        isFresh
          ? 'bg-slate-50 border-slate-200 text-slate-600'
          : 'bg-amber-50 border-amber-200 text-amber-700 font-medium'
      } ${className}`}
      title={`Exact: ${formatISTTime(timestamp)}`}
    >
      {isFresh ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
      ) : (
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
      )}
      <span>
        {label}: {timeAgo(timestamp)}
      </span>
      {!isFresh && <span className="text-[10px] uppercase font-bold tracking-wider">(STALE)</span>}
    </div>
  );
};
