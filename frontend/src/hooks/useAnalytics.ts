import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import type { AccountSnapshot, Position, OrderFill } from '../types';
import { STARTING_CAPITAL_INR } from '../lib/constants';

export interface SymbolStat {
  symbol: string;
  totalTrades: number;
  winTrades: number;
  lossTrades: number;
  winRate: number;
  grossPnL: number;
  netPnL: number;
}

export function useAnalytics() {
  const [snapshots, setSnapshots] = useState<AccountSnapshot[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [fills, setFills] = useState<OrderFill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalyticsData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Account Snapshots for equity curve
      const { data: snapData } = await supabase
        .from('account_snapshots')
        .select('*')
        .eq('account_id', TARGET_ACCOUNT_ID)
        .order('snapshot_ts', { ascending: true });

      setSnapshots(snapData || []);

      // 2. Closed positions for trade stats
      const { data: posData } = await supabase
        .from('positions')
        .select('*')
        .eq('account_id', TARGET_ACCOUNT_ID)
        .eq('status', 'closed')
        .order('close_timestamp', { ascending: true });

      setPositions(posData || []);

      // 3. Order fills for fees / trading costs
      const { data: fillsData } = await supabase
        .from('order_fills')
        .select(`
          id,
          order_id,
          fill_price,
          fill_quantity,
          fill_timestamp,
          fees,
          orders!inner (account_id)
        `)
        .eq('orders.account_id', TARGET_ACCOUNT_ID);

      setFills((fillsData as any) || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalyticsData();
  }, [fetchAnalyticsData]);

  // Calculations
  const closedCount = positions.length;
  const hasEnoughData = closedCount >= 1;

  const wins = positions.filter((p) => Number(p.realized_pnl) > 0);
  const losses = positions.filter((p) => Number(p.realized_pnl) < 0);

  const totalWinAmount = wins.reduce((sum, p) => sum + Number(p.realized_pnl), 0);
  const totalLossAmount = Math.abs(losses.reduce((sum, p) => sum + Number(p.realized_pnl), 0));

  const winRate = closedCount > 0 ? (wins.length / closedCount) * 100 : null;
  const profitFactor = totalLossAmount > 0 ? totalWinAmount / totalLossAmount : wins.length > 0 ? totalWinAmount : null;
  const avgWin = wins.length > 0 ? totalWinAmount / wins.length : null;
  const avgLoss = losses.length > 0 ? totalLossAmount / losses.length : null;

  // Realized R-Multiple (assuming 1R = ₹100 / 1% risk per trade)
  const avgRMultiple = closedCount > 0
    ? positions.reduce((sum, p) => sum + (Number(p.realized_pnl) / 100), 0) / closedCount
    : null;

  // Trading costs
  const totalFeesPaid = fills.reduce((sum, f) => sum + Number(f.fees || 0), 0);

  // Maximum Drawdown calculation from equity snapshots
  let maxDrawdownINR = 0;
  let maxDrawdownPct = 0;
  let peakEquity = STARTING_CAPITAL_INR;

  const equityCurve = snapshots.map((s) => {
    const eq = Number(s.total_equity);
    if (eq > peakEquity) peakEquity = eq;
    const ddINR = peakEquity - eq;
    const ddPct = peakEquity > 0 ? (ddINR / peakEquity) * 100 : 0;
    if (ddINR > maxDrawdownINR) maxDrawdownINR = ddINR;
    if (ddPct > maxDrawdownPct) maxDrawdownPct = ddPct;

    return {
      timestamp: s.snapshot_ts,
      equity: eq,
      realizedPnL: Number(s.realized_pnl),
      unrealizedPnL: Number(s.unrealized_pnl),
      drawdownINR: ddINR,
    };
  });

  // Performance by Symbol
  const symbolMap: Record<string, SymbolStat> = {};
  for (const pos of positions) {
    if (!symbolMap[pos.symbol]) {
      symbolMap[pos.symbol] = {
        symbol: pos.symbol,
        totalTrades: 0,
        winTrades: 0,
        lossTrades: 0,
        winRate: 0,
        grossPnL: 0,
        netPnL: 0,
      };
    }
    const stat = symbolMap[pos.symbol];
    stat.totalTrades += 1;
    const pnl = Number(pos.realized_pnl);
    stat.grossPnL += pnl;
    stat.netPnL += pnl; // net after fees
    if (pnl > 0) stat.winTrades += 1;
    if (pnl < 0) stat.lossTrades += 1;
    stat.winRate = (stat.winTrades / stat.totalTrades) * 100;
  }
  const symbolStats = Object.values(symbolMap);

  return {
    snapshots,
    positions,
    equityCurve,
    symbolStats,
    hasEnoughData,
    closedCount,
    winRate,
    profitFactor,
    avgWin,
    avgLoss,
    avgRMultiple,
    totalFeesPaid,
    maxDrawdownINR,
    maxDrawdownPct,
    loading,
    error,
    refetch: fetchAnalyticsData,
  };
}
