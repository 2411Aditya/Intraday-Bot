// verify_rls.js
// Run with: node scripts/verify_rls.js
// This script checks that anonymous users cannot read private tables
// and that an authenticated operator can.

import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config({ path: '../../.env' });

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const anonKey = process.env.VITE_SUPABASE_ANON_KEY;
const serviceKey = process.env.VITE_SUPABASE_SERVICE_ROLE_KEY; // optional for admin checks

if (!supabaseUrl || !anonKey) {
  console.error('Missing Supabase config in .env');
  process.exit(1);
}

// Anonymous client
const anon = createClient(supabaseUrl, anonKey);

async function checkAnon() {
  const { data, error } = await anon.from('research_snapshots').select('id').limit(1);
  if (error) {
    console.log('✅ Anonymous access correctly denied:', error.message);
  } else if (data && data.length === 0) {
    console.log('✅ Anonymous access returns no rows as expected.');
  } else {
    console.warn('⚠️ Anonymous access returned data unexpectedly:', data);
  }
}

// Authenticated operator – replace with real credentials or use service role for test
async function checkAuth() {
  // For simplicity use service role key which has full access
  if (!process.env.VITE_SUPABASE_SERVICE_ROLE_KEY) {
    console.warn('No service role key provided; skipping auth check');
    return;
  }
  const admin = createClient(supabaseUrl, process.env.VITE_SUPABASE_SERVICE_ROLE_KEY);
  const { data, error } = await admin.from('research_snapshots').select('id').limit(1);
  if (error) {
    console.error('❌ Authenticated admin could not read data:', error.message);
  } else if (data && data.length > 0) {
    console.log('✅ Authenticated admin read succeeded, rows count:', data.length);
  } else {
    console.warn('⚠️ Authenticated admin read returned no rows.');
  }
}

(async () => {
  await checkAnon();
  await checkAuth();
})();
