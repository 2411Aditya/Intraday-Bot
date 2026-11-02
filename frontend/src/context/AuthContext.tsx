import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, TARGET_ACCOUNT_ID } from '../lib/supabase';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  isOperator: boolean;
  operatorRole: string | null;
  signIn: (email: string, pass: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, pass: string) => Promise<{ error: Error | null }>;
  signOut: () => Promise<void>;
  linkOperatorAccess: () => Promise<{ success: boolean; error?: string }>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  loading: true,
  isOperator: false,
  operatorRole: null,
  signIn: async () => ({ error: null }),
  signUp: async () => ({ error: null }),
  signOut: async () => {},
  linkOperatorAccess: async () => ({ success: false }),
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOperator, setIsOperator] = useState(false);
  const [operatorRole, setOperatorRole] = useState<string | null>(null);

  const checkOperatorStatus = async (uid: string) => {
    try {
      const { data, error } = await supabase
        .from('bot_operators')
        .select('role')
        .eq('user_id', uid)
        .eq('target_account_id', TARGET_ACCOUNT_ID)
        .maybeSingle();

      if (!error && data) {
        setIsOperator(true);
        setOperatorRole(data.role);
      } else {
        setIsOperator(false);
        setOperatorRole(null);
      }
    } catch {
      setIsOperator(false);
    }
  };

  useEffect(() => {
    // 1. Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        checkOperatorStatus(session.user.id);
      }
      setLoading(false);
    });

    // 2. Auth state subscription
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        checkOperatorStatus(session.user.id);
      } else {
        setIsOperator(false);
        setOperatorRole(null);
      }
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async (email: string, pass: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password: pass,
    });
    return { error };
  };

  const signUp = async (email: string, pass: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password: pass,
    });
    return { error };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  const linkOperatorAccess = async () => {
    if (!user) {
      return { success: false, error: 'Must be logged in to claim operator access.' };
    }
    try {
      const { error } = await supabase.from('bot_operators').upsert({
        user_id: user.id,
        target_account_id: TARGET_ACCOUNT_ID,
        role: 'operator',
      });
      if (error) {
        return { success: false, error: error.message };
      }
      setIsOperator(true);
      setOperatorRole('operator');
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err?.message || 'Failed to claim access' };
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        isOperator,
        operatorRole,
        signIn,
        signUp,
        signOut,
        linkOperatorAccess,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
