'use client';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, token, type User, type Wallet } from './api';

type Auth = { user: User | null; wallet: Wallet | null; ready: boolean; refresh: () => Promise<void>; signIn: (t: string) => Promise<void>; signOut: () => void };
const Ctx = createContext<Auth>({ user: null, wallet: null, ready: false, refresh: async () => {}, signIn: async () => {}, signOut: () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    if (!token.get()) { setUser(null); setWallet(null); setReady(true); return }
    try { const [u, w] = await Promise.all([api.me(), api.wallet()]); setUser(u); setWallet(w) } catch { setUser(null); setWallet(null) }
    setReady(true);
  }, []);
  useEffect(() => { refresh() }, [refresh]);
  const signIn = async (t: string) => { token.set(t); await refresh() };
  const signOut = () => { token.clear(); setUser(null); setWallet(null) };
  return <Ctx.Provider value={{ user, wallet, ready, refresh, signIn, signOut }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

/** Redirects to /login?next=… when not signed in. Returns true once the user is available. */
export function useRequireAuth() {
  const { user, ready } = useAuth();
  useEffect(() => {
    if (ready && !user) window.location.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }, [ready, user]);
  return ready && !!user;
}
