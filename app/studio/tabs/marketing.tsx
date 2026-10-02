'use client';
import { useEffect, useState } from 'react';
import { BadgePercent, Copy, Check, Link2, QrCode, Trash2, Loader2 } from 'lucide-react';
import { api, API_URL, errMsg, type Discount, type StudioAsset } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { timeAgo } from '../../lib/market';

export function MarketingTab() {
  const { user } = useAuth();
  const [discs, setDiscs] = useState<Discount[] | null>(null);
  const [assets, setAssets] = useState<StudioAsset[]>([]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const [copied, setCopied] = useState('');
  const [utm, setUtm] = useState({ asset: '', source: 'instagram', campaign: 'launch', code: '' });
  const load = () => api.discounts().then(r => setDiscs(r.items)).catch(() => setDiscs([]));
  useEffect(() => { load(); api.studioAssets().then(r => { setAssets(r.items); if (r.items[0]) setUtm(u => ({ ...u, asset: r.items[0].id })) }).catch(() => {}) }, []);
  const origin = typeof window !== 'undefined' ? window.location.origin : 'https://smartsharing.in';
  const link = utm.asset ? `${origin}/p/${utm.asset}?utm_source=${encodeURIComponent(utm.source)}&utm_campaign=${encodeURIComponent(utm.campaign)}${utm.code ? `&code=${encodeURIComponent(utm.code)}` : ''}` : '';
  const copy = (t: string) => navigator.clipboard.writeText(t).then(() => { setCopied(t); setTimeout(() => setCopied(''), 1500) });

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setErr('');
    try {
      const target = String(f.get('asset'));
      await api.createDiscount({ code: String(f.get('code')), pct_off: Number(f.get('pct')), asset_ids: target ? [target] : [], max_uses: f.get('max') ? Number(f.get('max')) : null, expires_in_days: f.get('days') ? Number(f.get('days')) : null });
      (e.target as HTMLFormElement).reset(); load();
    } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <>
      <div className="tab-head"><div><h1>Marketing</h1><p className="muted">Discount codes, tracked links and QR codes for every post, story and bio.</p></div></div>
      <div className="two-col">
        <div className="panel"><div className="panel-head"><h3><BadgePercent size={16} />Discount codes</h3></div>
          <form className="form grid-form" onSubmit={create}>
            <label>Code<input name="code" required pattern="[A-Za-z0-9_-]{3,24}" placeholder="DIWALI25" style={{ textTransform: 'uppercase' }} /></label>
            <label>% off<input name="pct" type="number" min={1} max={90} defaultValue={20} required /></label>
            <label>Applies to<select name="asset" defaultValue=""><option value="">All my listings</option>{assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
            <label>Max uses<input name="max" type="number" min={1} placeholder="Unlimited" /></label>
            <label>Expires in (days)<input name="days" type="number" min={1} max={365} placeholder="Never" /></label>
            <div className="form-actions"><button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : 'Create code'}</button></div>
            {err && <p className="form-error span2">{err}</p>}
          </form>
          {discs && discs.length > 0 && <table className="tbl"><thead><tr><th>Code</th><th>Off</th><th>Used</th><th>Status</th><th /></tr></thead><tbody>{discs.map(d => <tr key={d.id}>
            <td><code>{d.code}</code><small>{d.asset_ids.length ? `${d.asset_ids.length} listing` : 'All listings'} · {timeAgo(d.created_at)}</small></td><td>{d.pct_off}%</td><td>{d.uses}{d.max_uses ? ` / ${d.max_uses}` : ''}</td>
            <td><span className={'status ' + (d.active && (!d.expires_at || new Date(d.expires_at) > new Date()) ? 'published' : 'draft')}>{!d.active ? 'Disabled' : d.expires_at && new Date(d.expires_at) < new Date() ? 'Expired' : 'Active'}</span></td>
            <td>{d.active && <button className="icon-btn" aria-label="Disable code" onClick={async () => { await api.disableDiscount(d.id); load() }}><Trash2 size={14} /></button>}</td></tr>)}</tbody></table>}
        </div>
        <div className="panel"><div className="panel-head"><h3><Link2 size={16} />Link builder</h3></div>
          <p className="muted small">Tag every link with where you posted it — the Overview tab shows which source drives views and sales.</p>
          <div className="form grid-form">
            <label className="span2">Listing<select value={utm.asset} onChange={e => setUtm({ ...utm, asset: e.target.value })}>{assets.length === 0 && <option value="">Create a listing first</option>}{assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
            <label>Source<select value={utm.source} onChange={e => setUtm({ ...utm, source: e.target.value })}>{['instagram', 'youtube', 'whatsapp', 'linkedin', 'x', 'telegram', 'newsletter', 'discord'].map(s => <option key={s}>{s}</option>)}</select></label>
            <label>Campaign<input value={utm.campaign} onChange={e => setUtm({ ...utm, campaign: e.target.value.replace(/\s+/g, '-').toLowerCase() })} /></label>
            <label className="span2">Auto-apply code (optional)<select value={utm.code} onChange={e => setUtm({ ...utm, code: e.target.value })}><option value="">None</option>{(discs || []).filter(d => d.active).map(d => <option key={d.id}>{d.code}</option>)}</select></label>
          </div>
          {link && <><div className="share-row"><input readOnly value={link} /><button className="icon-btn" onClick={() => copy(link)} aria-label="Copy">{copied === link ? <Check size={15} /> : <Copy size={15} />}</button></div>
            <div className="qr-block"><img className="qr" src={`${API_URL}/api/qr?data=${encodeURIComponent(link)}`} alt="QR code" /><div><strong><QrCode size={15} /> QR for stories & print</strong><p className="muted small">Right-click → save image, or open the SVG for print quality.</p><a className="link" href={`${API_URL}/api/qr?data=${encodeURIComponent(link)}&scale=16`} target="_blank" rel="noreferrer">Open SVG</a></div></div></>}
          {user && <><h4 className="sub">Your storefront link</h4><div className="share-row"><input readOnly value={`${origin}/u/${user.handle}`} /><button className="icon-btn" onClick={() => copy(`${origin}/u/${user.handle}`)} aria-label="Copy">{copied === `${origin}/u/${user.handle}` ? <Check size={15} /> : <Copy size={15} />}</button></div><p className="muted small">Put this in your Instagram / YouTube bio.</p></>}
        </div>
      </div>
    </>
  );
}
