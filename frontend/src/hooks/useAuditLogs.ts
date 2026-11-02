import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import type { AuditLog, RiskDecision, WorkerCandleState } from '../types';

export function useAuditLogs() {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [rejections, setRejections] = useState<RiskDecision[]>([]);
  const [workerState, setWorkerState] = useState<WorkerCandleState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Audit logs
      const { data: logsData } = await supabase
        .from('audit_logs')
        .select('*')
        .order('logged_at', { ascending: false })
        .limit(50);

      setAuditLogs(logsData || []);

      // 2. Risk decisions that were rejected
      const { data: rejData } = await supabase
        .from('risk_decisions')
        .select('*')
        .eq('account_id', TARGET_ACCOUNT_ID)
        .eq('decision', 'rejected')
        .order('created_at', { ascending: false })
        .limit(50);

      setRejections(rejData || []);

      // 3. Worker Candle State
      const { data: wsData } = await supabase
        .from('worker_candle_state')
        .select('*')
        .order('last_processed_candle_ts', { ascending: false })
        .limit(20);

      setWorkerState(wsData || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch audit logs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return {
    auditLogs,
    rejections,
    workerState,
    loading,
    error,
    refetch: fetchLogs,
  };
}
