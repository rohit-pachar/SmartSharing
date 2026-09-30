// SmartSharing API client. Base URL comes from NEXT_PUBLIC_API_URL (falls back to the production API).
import type { Asset } from './market-data';

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'https://api.smartsharing.in').replace(/\/$/, '');
const TOKEN_KEY = 'ss_token';

export type User = { id: string; handle: string; full_name: string; email?: string; role?: string | null; is_demo?: boolean };
export type Wallet = { balance: number; pending_out: number };
export type LedgerRow = { id: string; kind: string; amount: number; memo: string | null; created_at: string; counterparty_id: string | null };
export type Transfer = { id: string; from_user_id: string; to_user_id: string; amount: number; memo: string | null; status: string; created_at: string };
export type Order = { id: string; receipt: string; asset_id: string; asset_name: string; license_name: string; price: number; creator_amount: number; platform_fee: number; created_at: string; is_demo?: boolean };
export type Activity = { type: 'purchase' | 'transfer'; at: string; buyer?: string; asset?: string; asset_id?: string; license?: string; price?: number; from?: string; to?: string; amount?: number; is_demo: boolean };
export type Stats = { members: number; demo_members: number; creators: number; assets: number; orders: number; order_volume: number; transfers: number; transfer_volume: number };

export class ApiError extends Error { status: number; constructor(status: number, msg: string) { super(msg); this.status = status } }

export const token = {
  get: () => (typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => window.localStorage.setItem(TOKEN_KEY, t),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

async function req<T>(path: string, init: RequestInit & { auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token.get();
  if (init.auth && t) headers.Authorization = `Bearer ${t}`;
  const r = await fetch(`${API_URL}/api${path}`, { ...init, headers: { ...headers, ...(init.headers as Record<string, string> | undefined) } });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = (await r.json()) as { detail?: unknown }; const dt = j.detail; msg = typeof dt === 'string' ? dt : Array.isArray(dt) ? String(dt[0]?.msg ?? msg) : (dt as { message?: string } | undefined)?.message ?? msg } catch {}
    if (r.status === 401 && init.auth) token.clear();
    throw new ApiError(r.status, msg || 'Request failed');
  }
  return r.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown, auth = true) => req<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined, auth });

export const api = {
  assets: (p: { q?: string; category?: string; sort?: string; limit?: number } = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== '') s.set(k, String(v)) });
    return req<{ total: number; items: Asset[] }>(`/assets?${s}`);
  },
  activity: (limit = 12) => req<{ items: Activity[] }>(`/activity?limit=${limit}`),
  stats: () => req<Stats>('/stats'),
  register: (full_name: string, email: string, password: string) => post<{ access_token: string; user: User }>('/auth/register', { full_name, email, password }, false),
  login: (email: string, password: string) => post<{ access_token: string; user: User }>('/auth/login', { email, password }, false),
  me: () => req<User>('/auth/me', { auth: true }),
  wallet: () => req<Wallet>('/wallet', { auth: true }),
  ledger: () => req<{ items: LedgerRow[] }>('/wallet/ledger?limit=30', { auth: true }),
  transfers: (direction: 'in' | 'out' | 'all' = 'all', status?: string) => req<{ items: Transfer[] }>(`/transfers?direction=${direction}${status ? `&status=${status}` : ''}`, { auth: true }),
  send: (to: string, amount: number, memo?: string) => post<Transfer>('/transfers', { to, amount, memo, idempotency_key: crypto.randomUUID() }),
  acceptTransfer: (id: string) => post<Transfer>(`/transfers/${id}/accept`),
  rejectTransfer: (id: string) => post<Transfer>(`/transfers/${id}/reject`),
  buy: (asset_id: string, license_id: string) => post<Order>('/orders', { asset_id, license_id }),
  purchases: () => req<{ items: Order[] }>('/me/purchases', { auth: true }),
  createAsset: (a: { name: string; category: string; description: string; price: number; kind?: string }) => post<Asset>('/assets', a),
  myAssets: () => req<{ items: Asset[] }>('/me/assets', { auth: true }),
};
