export type LicenseOption = { id: string; name: string; detail: string; price: number };
export type Asset = { id: string; name: string; category: string; creator: string; creator_handle?: string; creator_id?: string; initials: string; role: string; price: number; image: string; format: string; description: string; includes: string[]; kind: 'file' | 'hosted'; tag: string; is_demo?: boolean; is_official?: boolean; affiliate_pct?: number; file_count?: number; file_names?: string[]; total_size?: number; stats?: { sales: number; revenue: number; views?: number }; license_options?: LicenseOption[]; created_at?: string };

export const CATEGORIES = ['All', 'Templates', 'Motion & video', '3D & design', 'Business & finance', 'AI workflows'];

export const credits = (v: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(v) + ' cr';
export const creditsLong = (v: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(v) + ' credits';
export const bytes = (n = 0) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

export function licenseOptions(a: Asset): LicenseOption[] {
  if (a.license_options?.length) return a.license_options;
  if (a.price === 0) return [{ id: 'free', name: 'Free licence', detail: 'Personal and commercial use', price: 0 }];
  return a.kind === 'hosted'
    ? [{ id: 'week', name: '7-day pass', detail: '50 runs · one user', price: a.price }, { id: 'month', name: '30-day pass', detail: '250 runs · one user', price: a.price * 3 }]
    : [{ id: 'personal', name: 'Personal', detail: 'One user · non-commercial projects', price: a.price }, { id: 'commercial', name: 'Commercial', detail: 'One user · client and commercial work', price: a.price * 2 }, { id: 'studio', name: 'Studio', detail: 'Up to 5 users · commercial work', price: a.price * 4 }];
}

export function timeAgo(iso: string) {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return 'just now'; const m = Math.round(s / 60); if (m < 60) return m + 'm ago';
  const h = Math.round(m / 60); if (h < 24) return h + 'h ago'; const d = Math.round(h / 24); if (d < 30) return d + 'd ago';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

export const LEDGER_LABEL: Record<string, string> = { grant: 'Welcome credits', admin_grant: 'Top-up', purchase: 'Purchase', sale: 'Sale', affiliate_commission: 'Affiliate commission', transfer_in: 'Received', transfer_out_pending: 'Sent · awaiting accept', transfer_out_settled: 'Transfer accepted', transfer_rejected_refund: 'Declined · refunded', transfer_cancelled_refund: 'Cancelled · refunded', transfer_expired_refund: 'Expired · refunded' };
