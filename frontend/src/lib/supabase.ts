import { createClient } from '@supabase/supabase-js';
import { CLEAN_PAPER_ACCOUNT_ID, CLEAN_PAPER_USER_ID } from './constants';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

export const TARGET_USER_ID = import.meta.env.VITE_TARGET_USER_ID || CLEAN_PAPER_USER_ID;
export const TARGET_ACCOUNT_ID = import.meta.env.VITE_TARGET_ACCOUNT_ID || CLEAN_PAPER_ACCOUNT_ID;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    '[SupabaseClient] Warning: VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY is not configured in environment.'
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: window.localStorage,
  },
});

export async function pingSupabase(): Promise<{ ok: boolean; latencyMs: number; error?: string }> {
  const start = performance.now();
  try {
    const { error } = await supabase.from('research_snapshots').select('id').limit(1);
    const latencyMs = Math.round(performance.now() - start);
    if (error) {
      return { ok: false, latencyMs, error: error.message };
    }
    return { ok: true, latencyMs };
  } catch (err: any) {
    const latencyMs = Math.round(performance.now() - start);
    return { ok: false, latencyMs, error: err?.message || 'Network error' };
  }
}
