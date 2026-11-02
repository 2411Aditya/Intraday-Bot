import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import type { TradingAccount, AccountSnapshot, WorkerCandleState } from '../types';
import { STARTING_CAPITAL_INR } from '../lib/constants';

export interface UseTradingAccountResult {
  account: TradingAccount | null;
  latestSnapshot: AccountSnapshot | null;
  workerState: WorkerCandleState[] | null;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
  refetch: () => Promise<void>;
  equity: number;
  cashBalance: number;
  realizedPnL: number;
  unrealizedPnL: number;
  totalPnL: number;
}

export function useTradingAccount(): UseTradingAccountResult {
  const [account, setAccount] = useState<TradingAccount | null>(null);
  const [latestSnapshot, setLatestSnapshot] = useState<AccountSnapshot | null>(null);
  const [workerState, setWorkerState] = useState<WorkerCandleState[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const { user } = useAuth();

  const fetchAccountData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Guard: ensure user is authenticated before fetching private data

  if (!user) {
    // Not logged in: clear data and stop loading
    setAccount(null);
    setLatestSnapshot(null);
    setWorkerState(null);
    setLoading(false);
    setError(null);
    return;
  }

  // 1. Fetch Trading Account
      const { data: acctData, error: acctErr } = await supabase
        .from('trading_accounts')
        .select('*')
        .eq('id', TARGET_ACCOUNT_ID)
        .maybeSingle();

      if (acctErr) {
        throw new Error(`Account fetch error: ${acctErr.message}`);
      }
      setAccount(acctData);

      // 2. Fetch Latest Account Snapshot
      const { data: snapData } = await supabase
        .from('account_snapshots')
        .select('*')
        .eq('account_id', TARGET_ACCOUNT_ID)
        .order('snapshot_ts', { ascending: false })
        .limit(1)
        .maybeSingle();

      setLatestSnapshot(snapData);

      // 3. Fetch Worker Candle State (Worker heartbeat)
      const { data: wsData } = await supabase
        .from('worker_candle_state')
        .select('*')
        .order('last_processed_candle_ts', { ascending: false })
        .limit(10);

      setWorkerState(wsData || []);
      setLastUpdated(new Date().toISOString());
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch account data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccountData();
    // Safe dashboard polling every 30 seconds
    const timer = setInterval(fetchAccountData, 30000);
    return () => clearInterval(timer);
  }, [fetchAccountData]);

  // Derived financial metrics
  const cashBalance = account?.cash_balance ? Number(account.cash_balance) : STARTING_CAPITAL_INR;
  const realizedPnL = latestSnapshot ? Number(latestSnapshot.realized_pnl) : 0;
  const unrealizedPnL = latestSnapshot ? Number(latestSnapshot.unrealized_pnl) : 0;
  const equity = latestSnapshot ? Number(latestSnapshot.total_equity) : cashBalance + unrealizedPnL;
  const totalPnL = equity - STARTING_CAPITAL_INR;

  return {
    account,
    latestSnapshot,
    workerState,
    loading,
    error,
    lastUpdated,
    refetch: fetchAccountData,
    equity,
    cashBalance,
    realizedPnL,
    unrealizedPnL,
    totalPnL,
  };
}

