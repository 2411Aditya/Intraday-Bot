import React from 'react';

export interface StatusBadgeProps {
  status: string;
  variant?: 'solid' | 'subtle';
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'sm',
}) => {
  const norm = (status || '').toUpperCase();

  let colorClasses = 'bg-surface-100 text-slate-700 border-surface-200';

  if (norm === 'BULLISH' || norm === 'APPROVED' || norm === 'FILLED' || norm === 'OPEN' || norm === 'MARKET OPEN') {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (
    norm === 'BEARISH' ||
    norm === 'REJECTED' ||
    norm === 'HIGH_RISK' ||
    norm === 'SQUARE-OFF' ||
    norm === 'CANCELED' ||
    norm === 'ERROR' ||
    norm === 'BLOCKED'
  ) {
    colorClasses = 'bg-rose-50 text-rose-700 border-rose-200';
  } else if (
    norm === 'NEUTRAL' ||
    norm === 'PENDING' ||
    norm === 'PARTIAL' ||
    norm === 'STALE' ||
    norm === 'CAUTION' ||
    norm === 'EXIT ONLY'
  ) {
    colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
  } else if (norm === 'PAPER' || norm === 'OVERNIGHT' || norm === 'PRE_MARKET') {
    colorClasses = 'bg-blue-50 text-blue-700 border-blue-200';
  } else if (norm === 'CLOSED' || norm === 'MARKET CLOSED' || norm === 'POST_MARKET') {
    colorClasses = 'bg-slate-100 text-slate-600 border-slate-200';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-semibold';

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border ${sizeClasses} ${colorClasses}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
      {status}
    </span>
  );
};

