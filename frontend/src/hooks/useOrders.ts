import { useState, useEffect, useCallback } from 'react';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';
import type { Order } from '../types';

export function useOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Orders
      const { data: ordersData, error: ordersErr } = await supabase
        .from('orders')
        .select(`
          id,
          intent_id,
          account_id,
          mode,
          status,
          created_at,
          order_intents (
            id,
            risk_id,
            account_id,
            mode,
            symbol,
            quantity,
            side,
            limit_price,
            created_at
          ),
          order_fills (
            id,
            order_id,
            fill_execution_id,
            fill_price,
            fill_quantity,
            fill_timestamp,
            fees,
            created_at
          )
        `)
        .eq('account_id', TARGET_ACCOUNT_ID)
        .order('created_at', { ascending: false });

      if (ordersErr) {
        throw new Error(ordersErr.message);
      }

      // Map relation fields
      const formatted: Order[] = (ordersData || []).map((o: any) => ({
        id: o.id,
        intent_id: o.intent_id,
        account_id: o.account_id,
        mode: o.mode,
        status: o.status,
        created_at: o.created_at,
        intent: o.order_intents,
        fills: o.order_fills || [],
      }));

      setOrders(formatted);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch orders');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
    const interval = setInterval(fetchOrders, 30000);
    return () => clearInterval(interval);
  }, [fetchOrders]);

  return {
    orders,
    loading,
    error,
    refetch: fetchOrders,
  };
}
