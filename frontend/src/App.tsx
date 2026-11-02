import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { OverviewPage } from './pages/OverviewPage';
import { TradingPage } from './pages/TradingPage';
import { ResearchPage } from './pages/ResearchPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { RiskActivityPage } from './pages/RiskActivityPage';
import { SettingsPage } from './pages/SettingsPage';
import { LoginPage } from './pages/LoginPage';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Main Dashboard Layout with Nested Routes */}
          <Route path="/" element={<AppLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="trading" element={<TradingPage />} />
            <Route path="research" element={<ResearchPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="risk" element={<RiskActivityPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          {/* Standalone Auth Screen */}
          <Route path="/login" element={<LoginPage />} />

          {/* Fallback to Overview */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
