'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Download, Library as LibIcon, Copy, Check, Loader2, KeyRound } from 'lucide-react';
import { api, API_URL, errMsg, mediaUrl, type LibraryItem } from '../lib/api';
import { useRequireAuth } from '../lib/auth';
import { bytes, creditsLong, timeAgo } from '../lib/market';
import { Empty, Footer, Header } from '../ui';

export default function LibraryPage() {
  const ok = useRequireAuth();
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [copied, setCopied] = useState('');
  useEffect(() => { if (ok) api.library().then(r => setItems(r.items)).catch(e => { setErr(errMsg(e)); setItems([]) }) }, [ok]);

  async function dl(o: LibraryItem, idx: number) {
    setBusy(o.id + idx); setErr('');
    try { const { url } = await api.downloadLink(o.id, idx); window.location.href = API_URL + url } catch (e) { setErr(errMsg(e)) } finally { setTimeout(() => setBusy(''), 800) }
  }
  const copy = (t: string) => navigator.clipboard.writeText(t).then(() => { setCopied(t); setTimeout(() => setCopied(''), 1500) });

  return (
    <>
      <Header active="library" />
      <main className="page">
        <div className="page-head"><div><p className="eyebrow">LIBRARY</p><h1>Everything you own</h1><p className="muted">Downloads, licence keys and receipts. Links are generated fresh each time and expire after 10 minutes.</p></div></div>
        {err && <p className="form-error">{err}</p>}
        {items === null ? <div className="lib-list">{[0, 1, 2].map(i => <div key={i} className="lib-row skel" />)}</div>
          : items.length === 0 ? <Empty icon={<LibIcon size={22} />} title="Your library is empty" text="Start with the free Content Calendar or Prompt Library." action={<Link href="/?price=free" className="btn btn-primary">Browse free resources</Link>} />
            : <div className="lib-list">{items.map(o => (
              <div key={o.id} className="lib-row">
                <Link href={`/p/${o.asset_id}`} className="lib-thumb"><img src={mediaUrl(o.image)} alt="" /></Link>
                <div className="lib-info">
                  <Link href={`/p/${o.asset_id}`}><strong>{o.asset_name}</strong></Link>
                  <small>{o.license_name} · {o.price ? creditsLong(o.price) : 'Free'} · {timeAgo(o.created_at)} · {o.receipt}</small>
                  {o.license_key && <span className="lib-key"><KeyRound size={13} /><code>{o.license_key}</code><button onClick={() => copy(o.license_key!)} aria-label="Copy licence key">{copied === o.license_key ? <Check size={13} /> : <Copy size={13} />}</button></span>}
                </div>
                <div className="lib-files">{o.files.length === 0 ? <span className="muted small">{o.kind === 'hosted' ? 'Hosted — access via creator' : 'Creator hasn’t uploaded files yet'}</span>
                  : o.files.map(f => <button key={f.idx} className="btn btn-primary btn-sm" onClick={() => dl(o, f.idx)} disabled={busy === o.id + f.idx}>{busy === o.id + f.idx ? <Loader2 size={15} className="spin" /> : <Download size={15} />}{f.name.length > 28 ? f.name.slice(0, 26) + '…' : f.name}<span className="btn-sub">{bytes(f.size)}</span></button>)}</div>
              </div>))}</div>}
      </main>
      <Footer />
    </>
  );
}
