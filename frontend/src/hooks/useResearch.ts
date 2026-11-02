import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import type { ResearchSnapshot } from '../types';

export function useResearch() {
  const [latestSnapshot, setLatestSnapshot] = useState<ResearchSnapshot | null>(null);
  const [overnightSnapshot, setOvernightSnapshot] = useState<ResearchSnapshot | null>(null);
  const [premarketSnapshot, setPremarketSnapshot] = useState<ResearchSnapshot | null>(null);
  const [snapshotsList, setSnapshotsList] = useState<ResearchSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchResearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch latest 20 snapshots
      const { data, error: rsErr } = await supabase
        .from('research_snapshots')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(20);

      if (rsErr) {
        throw new Error(rsErr.message);
      }

      const list: ResearchSnapshot[] = data || [];
      setSnapshotsList(list);

      // Latest overall
      if (list.length > 0) {
        setLatestSnapshot(list[0]);
      }

      // Latest overnight
      const overnight = list.find((s) => s.session_type === 'overnight');
      setOvernightSnapshot(overnight || null);

      // Latest pre_market
      const premarket = list.find((s) => s.session_type === 'pre_market');
      setPremarketSnapshot(premarket || null);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch research data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResearch();
    const interval = setInterval(fetchResearch, 60000); // 1 minute refresh
    return () => clearInterval(interval);
  }, [fetchResearch]);

  // Freshness calculation (< 6 hours = fresh)
  const isFresh = (snapshot: ResearchSnapshot | null): boolean => {
    if (!snapshot) return false;
    const created = new Date(snapshot.created_at).getTime();
    const now = Date.now();
    return (now - created) < 6 * 3600 * 1000;
  };

  return {
    latestSnapshot,
    overnightSnapshot,
    premarketSnapshot,
    snapshotsList,
    isLatestFresh: isFresh(latestSnapshot),
    loading,
    error,
    refetch: fetchResearch,
  };
}

