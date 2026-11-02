import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import type { StrategySignal } from '../types';

export function useSignals() {
  const [signals, setSignals] = useState<StrategySignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: sigData, error: sigErr } = await supabase
        .from('strategy_signals')
        .select(`
          id,
          user_id,
          symbol,
          signal_time,
          direction,
          price,
          created_at,
          risk_decisions (
            id,
            signal_id,
            account_id,
            decision,
            reason,
            created_at
          )
        `)
        .order('signal_time', { ascending: false })
        .limit(100);

      if (sigErr) {
        throw new Error(sigErr.message);
      }

      const formatted: StrategySignal[] = (sigData || []).map((s: any) => ({
        id: s.id,
        user_id: s.user_id,
        symbol: s.symbol,
        signal_time: s.signal_time,
        direction: s.direction,
        price: Number(s.price),
        created_at: s.created_at,
        risk_decision: Array.isArray(s.risk_decisions)
          ? s.risk_decisions.find((rd: any) => rd.account_id === TARGET_ACCOUNT_ID) || s.risk_decisions[0]
          : s.risk_decisions,
      }));

      setSignals(formatted);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch signals');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 30000);
    return () => clearInterval(interval);
  }, [fetchSignals]);

  return {
    signals,
    loading,
    error,
    refetch: fetchSignals,
  };
}
