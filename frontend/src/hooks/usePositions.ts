import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import type { Position } from '../types';

export function usePositions() {
  const [openPositions, setOpenPositions] = useState<Position[]>([]);
  const [closedPositions, setClosedPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data, error: posErr } = await supabase
        .from('positions')
        .select('*')
        .eq('account_id', TARGET_ACCOUNT_ID)
        .order('open_timestamp', { ascending: false });

      if (posErr) {
        throw new Error(posErr.message);
      }

      const all = data || [];
      setOpenPositions(all.filter((p) => p.status === 'open'));
      setClosedPositions(all.filter((p) => p.status === 'closed'));
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch positions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 30000);
    return () => clearInterval(interval);
  }, [fetchPositions]);

  return {
    openPositions,
    closedPositions,
    allPositions: [...openPositions, ...closedPositions],
    loading,
    error,
    refetch: fetchPositions,
  };
}

