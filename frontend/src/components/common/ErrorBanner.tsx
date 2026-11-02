import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title = 'Data Fetch Error',
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3 ${className}`}
    >
      <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1 text-sm">
        <h4 className="font-semibold text-rose-900">{title}</h4>
        <p className="mt-0.5 text-xs text-rose-700">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-2.5 py-1 text-xs font-medium bg-white text-rose-800 rounded-lg border border-rose-200 hover:bg-rose-100 flex items-center gap-1.5 transition-colors shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  );
};
