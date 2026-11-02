import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { MobileNav } from './MobileNav';
import { useTradingAccount } from '../../hooks/useTradingAccount';

export const AppLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { refetch, loading, workerState } = useTradingAccount();

  const lastHeartbeat = workerState && workerState.length > 0
    ? workerState[0].last_processed_candle_ts
    : null;

  return (
    <div className="flex h-screen overflow-hidden bg-surface-50 text-slate-800">
      {/* Desktop Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <TopHeader
          onRefresh={refetch}
          isRefreshing={loading}
          lastHeartbeatTs={lastHeartbeat}
        />

        <main className="flex-1 overflow-y-auto px-4 md:px-8 py-6 pb-20 md:pb-8">
          <div className="max-w-7xl mx-auto space-y-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Touch-Friendly Mobile Bottom Nav */}
      <MobileNav />
    </div>
  );
};

