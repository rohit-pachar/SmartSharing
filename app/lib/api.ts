// SmartSharing API client. Base URL: NEXT_PUBLIC_API_URL (defaults to production).
import type { Asset } from './market';

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'https://api.smartsharing.in').replace(/\/$/, '');
const TOKEN_KEY = 'ss_token';

export type User = { id: string; handle: string; full_name: string; email?: string; role?: string | null; bio?: string | null; city?: string | null; website?: string | null; links?: Record<string, string>; is_creator?: boolean; is_demo?: boolean; is_official?: boolean; joined?: string };
export type Wallet = { balance: number; pending_out: number };
export type LedgerRow = { id: string; kind: string; amount: number; memo: string | null; created_at: string; balance_after: number };
export type Transfer = { id: string; from_user_id: string; to_user_id: string; amount: number; memo: string | null; status: string; created_at: string };
export type Order = { id: string; receipt: string; asset_id: string; asset_name: string; license_name: string; license_key?: string; price: number; list_price?: number; discount_code?: string | null; creator_amount: number; platform_fee: number; created_at: string };
export type LibraryItem = Order & { image?: string; creator?: string; kind?: string; downloads?: number; files: { idx: number; name: string; size: number }[] };
export type StudioAsset = Asset & { status: 'published' | 'draft'; affiliate_pct?: number; files: { idx: number; name: string; size: number; mime: string }[] };
export type Overview = { days: number; revenue: number; gross: number; sales: number; views: number; conversion: number; affiliate_earnings: number; customers: number; balance: number; listings: number;
  series: { day: string; revenue: number; sales: number; views: number }[]; top_assets: { asset_id: string; name: string; sales: number; revenue: number }[];
  sources: { source: string; views: number }[]; recent_sales: { receipt: string; asset: string; license: string; amount: number; discount_code: string | null; buyer: string; at: string }[] };
export type Discount = { id: string; code: string; pct_off: number; asset_ids: string[]; max_uses: number | null; uses: number; active: boolean; expires_at: string | null; created_at: string };
export type ApiKey = { id: string; name: string; prefix: string; created_at: string; last_used_at: string | null };
export type Integration = { id: string; type: 'webhook' | 'discord' | 'slack' | 'telegram'; name: string; events: string[]; active: boolean; config: Record<string, string>; last_delivery: { ok: boolean; status: number | null; at: string; event: string } | null; signing_secret?: string };
export type Customer = { handle: string | null; name: string; orders: number; spent: number; last_order: string };
export type Profile = User & { assets: Asset[]; sales: number };

export class ApiError extends Error { status: number; constructor(status: number, msg: string) { super(msg); this.status = status } }

export const token = {
  get: () => (typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => window.localStorage.setItem(TOKEN_KEY, t),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

export const mediaUrl = (p?: string | null) => (!p ? '' : p.startsWith('/media/') || p.startsWith('/api/') ? API_URL + p : p);

async function req<T>(path: string, init: RequestInit & { auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const t = token.get();
  if (init.auth && t) headers.Authorization = `Bearer ${t}`;
  const r = await fetch(`${API_URL}/api${path}`, { ...init, headers: { ...headers, ...(init.headers as Record<string, string> | undefined) } });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = (await r.json()) as { detail?: unknown }; const dt = j.detail; msg = typeof dt === 'string' ? dt : Array.isArray(dt) ? String(dt[0]?.msg ?? msg) : (dt as { message?: string } | undefined)?.message ?? msg } catch {}
    if (r.status === 401 && init.auth) token.clear();
    throw new ApiError(r.status, msg || 'Request failed');
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}
const get = <T,>(p: string, auth = true) => req<T>(p, { auth });
const send = <T,>(method: string, p: string, body?: unknown) => req<T>(p, { method, auth: true, body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body) });

export const api = {
  assets: (p: { q?: string; category?: string; sort?: string; source?: string; creator?: string; limit?: number } = {}) => {
    const s = new URLSearchParams(); Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== '') s.set(k, String(v)) });
    return get<{ total: number; items: Asset[] }>(`/assets?${s}`, false);
  },
  asset: (id: string) => get<Asset>(`/assets/${encodeURIComponent(id)}`, false),
  profile: (handle: string) => get<Profile>(`/users/${encodeURIComponent(handle)}`, false),
  view: (id: string, src?: string) => { fetch(`${API_URL}/api/assets/${encodeURIComponent(id)}/view${src ? `?src=${encodeURIComponent(src)}` : ''}`, { method: 'POST' }).catch(() => {}) },
  checkDiscount: (asset_id: string, code: string) => get<{ valid: boolean; message?: string; pct_off?: number; options?: { id: string; price: number; discounted: number }[] }>(`/discounts/check?asset_id=${encodeURIComponent(asset_id)}&code=${encodeURIComponent(code)}`, false),
  register: (full_name: string, email: string, password: string) => req<{ access_token: string; user: User }>('/auth/register', { method: 'POST', body: JSON.stringify({ full_name, email, password }) }),
  login: (email: string, password: string) => req<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => get<User>('/auth/me'),
  updateMe: (b: Partial<User>) => send<User>('PATCH', '/me', b),
  wallet: () => get<Wallet>('/wallet'),
  ledger: () => get<{ items: LedgerRow[] }>('/wallet/ledger?limit=50'),
  transfers: (direction: 'in' | 'out' | 'all' = 'all', status?: string) => get<{ items: Transfer[] }>(`/transfers?direction=${direction}${status ? `&status=${status}` : ''}`),
  send: (to: string, amount: number, memo?: string) => send<Transfer>('POST', '/transfers', { to, amount, memo, idempotency_key: crypto.randomUUID() }),
  acceptTransfer: (id: string) => send<Transfer>('POST', `/transfers/${id}/accept`),
  rejectTransfer: (id: string) => send<Transfer>('POST', `/transfers/${id}/reject`),
  buy: (asset_id: string, license_id: string, discount_code?: string, ref?: string) => send<Order>('POST', '/orders', { asset_id, license_id, discount_code: discount_code || undefined, ref: ref || undefined }),
  library: () => get<{ items: LibraryItem[] }>('/library'),
  downloadLink: (order_id: string, idx: number) => send<{ url: string }>('POST', `/library/${order_id}/files/${idx}/link`),
  overview: (days = 30) => get<Overview>(`/studio/overview?days=${days}`),
  studioAssets: () => get<{ items: StudioAsset[] }>('/studio/assets'),
  createAsset: (a: { name: string; category: string; description: string; price: number; kind: string; format?: string; includes?: string[] }) => send<StudioAsset>('POST', '/assets', a),
  updateAsset: (id: string, b: Record<string, unknown>) => send<StudioAsset>('PATCH', `/studio/assets/${id}`, b),
  uploadFile: (id: string, f: File) => { const fd = new FormData(); fd.append('file', f); return send<{ name: string; size: number }>('POST', `/studio/assets/${id}/files`, fd) },
  deleteFile: (id: string, idx: number) => send('DELETE', `/studio/assets/${id}/files/${idx}`),
  customers: () => get<{ items: Customer[] }>('/studio/customers'),
  discounts: () => get<{ items: Discount[] }>('/studio/discounts'),
  createDiscount: (b: { code: string; pct_off: number; asset_ids?: string[]; max_uses?: number | null; expires_in_days?: number | null }) => send<Discount>('POST', '/studio/discounts', b),
  disableDiscount: (id: string) => send('DELETE', `/studio/discounts/${id}`),
  apiKeys: () => get<{ items: ApiKey[] }>('/studio/api-keys'),
  createApiKey: (name: string) => send<{ id: string; key: string; name: string }>('POST', '/studio/api-keys', { name }),
  revokeApiKey: (id: string) => send('DELETE', `/studio/api-keys/${id}`),
  integrations: () => get<{ items: Integration[] }>('/studio/integrations'),
  createIntegration: (b: { type: string; name?: string; config: Record<string, string>; events: string[] }) => send<Integration>('POST', '/studio/integrations', b),
  testIntegration: (id: string) => send<{ ok: boolean; status: number | null; error: string | null }>('POST', `/studio/integrations/${id}/test`),
  toggleIntegration: (id: string, active: boolean) => send('PATCH', `/studio/integrations/${id}?active=${active}`),
  deleteIntegration: (id: string) => send('DELETE', `/studio/integrations/${id}`),
};

export async function downloadCsv(kind: 'sales' | 'ledger') {
  const r = await fetch(`${API_URL}/api/studio/export/${kind}.csv`, { headers: { Authorization: `Bearer ${token.get()}` } });
  if (!r.ok) throw new ApiError(r.status, 'Export failed');
  const blob = await r.blob(); const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = `smartsharing-${kind}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

export const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Could not reach SmartSharing. Please try again.');
