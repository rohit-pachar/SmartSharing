'use client';
import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import { Check, Download, FileArchive, Loader2, Share2, Copy, BadgePercent, ShieldCheck, ArrowLeft, QrCode } from 'lucide-react';
import { api, errMsg, mediaUrl, API_URL, type Order } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { bytes, credits, creditsLong, licenseOptions, type Asset } from '../../lib/market';
import { AssetCard, Footer, Header } from '../../ui';

export default function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, wallet, refresh } = useAuth();
  const [a, setA] = useState<Asset | null>(null);
  const [missing, setMissing] = useState(false);
  const [more, setMore] = useState<Asset[]>([]);
  const [opt, setOpt] = useState('');
  const [code, setCode] = useState('');
  const [disc, setDisc] = useState<{ pct: number; code: string } | null>(null);
  const [discMsg, setDiscMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [order, setOrder] = useState<Order | null>(null);
  const [owned, setOwned] = useState<string[]>([]);
  const [copied, setCopied] = useState('');
  const [qr, setQr] = useState(false);
  const [ref, setRef] = useState<string | null>(null);

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const r = sp.get('ref'); if (r) { setRef(r); sessionStorage.setItem('ss_ref_' + id, r) } else setRef(sessionStorage.getItem('ss_ref_' + id));
    const c = sp.get('code'); if (c) setCode(c.toUpperCase());
    api.asset(id).then(x => { setA(x); setOpt(licenseOptions(x)[0].id); api.view(id, sp.get('utm_source') || (r ? 'affiliate' : document.referrer ? new URL(document.referrer).hostname.replace('www.', '').split('.')[0] : 'direct'));
      api.assets({ creator: x.creator_handle, limit: 5 }).then(r2 => setMore(r2.items.filter(y => y.id !== x.id).slice(0, 4))).catch(() => {}) }).catch(() => setMissing(true));
  }, [id]);
  useEffect(() => { if (user) api.library().then(r => setOwned(r.items.filter(o => o.asset_id === id).map(o => o.license_name))).catch(() => {}) }, [user, id, order]);
  useEffect(() => { if (a && code && !disc) applyCode(code) // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a]);

  const opts = useMemo(() => (a ? licenseOptions(a) : []), [a]);
  const sel = opts.find(o => o.id === opt) || opts[0];
  const price = sel ? (disc ? Math.max(1, Math.round(sel.price * (100 - disc.pct) / 100)) : sel.price) : 0;
  const shareUrl = typeof window !== 'undefined' ? `${window.location.origin}/p/${id}${user ? `?ref=${user.handle}` : ''}` : '';

  async function applyCode(c: string) {
    if (!a || !c.trim()) return; setDiscMsg('');
    try { const r = await api.checkDiscount(a.id, c.trim()); if (r.valid && r.pct_off) { setDisc({ pct: r.pct_off, code: c.trim().toUpperCase() }); setDiscMsg(`${r.pct_off}% off applied`) } else { setDisc(null); setDiscMsg(r.message || 'Invalid code') } } catch (e) { setDiscMsg(errMsg(e)) }
  }
  async function buy() {
    if (!a || !sel) return;
    if (!user) { window.location.href = `/login?next=${encodeURIComponent(`/p/${a.id}`)}`; return }
    setBusy(true); setErr('');
    try { const o = await api.buy(a.id, sel.id, disc?.code, ref || undefined); setOrder(o); refresh() } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  function copy(text: string, what: string) { navigator.clipboard.writeText(text).then(() => { setCopied(what); setTimeout(() => setCopied(''), 1500) }) }

  if (missing) return <><Header /><main className="page narrow"><h1>Listing not found</h1><p className="muted">It may have been unpublished.</p><Link href="/" className="btn btn-ghost"><ArrowLeft size={16} />Back to marketplace</Link></main></>;
  if (!a) return <><Header /><main className="page"><div className="pd skel-block" /></main></>;
  const mine = user && a.creator_id === user.id;
  const hasThis = sel && owned.includes(sel.name);

  return (
    <>
      <Header active="discover" />
      <main className="page">
        <nav className="crumbs"><Link href="/">Discover</Link><span>/</span><Link href={`/?q=${encodeURIComponent(a.category)}`}>{a.category}</Link></nav>
        <div className="pd">
          <div className="pd-media">
            <img src={mediaUrl(a.image)} alt={a.name} />
            <div className="pd-desc">
              <h2>About this {a.kind === 'hosted' ? 'workflow' : 'pack'}</h2>
              <p>{a.description}</p>
              {a.includes?.length > 0 && <><h3>What’s included</h3><ul className="checks">{a.includes.map(x => <li key={x}><Check size={16} />{x}</li>)}</ul></>}
              {!!a.file_names?.length && <><h3>Files</h3><ul className="files">{a.file_names.map(f => <li key={f}><FileArchive size={16} />{f}<span>{bytes(a.total_size)}</span></li>)}</ul></>}
              <h3>Licence</h3>
              <p className="muted small">{a.kind === 'hosted' ? 'A hosted pass ends when its duration or run allowance is used up.' : 'Use in unlimited projects under your licence tier. The creator keeps ownership. Source files can’t be resold, shared or bundled into other templates.'}</p>
            </div>
          </div>
          <aside className="pd-buy">
            <div className="buy-card">
              <p className="card-cat">{a.category}{a.is_official && <span className="pill pill-official inline">SmartSharing Studio</span>}{a.is_demo && <span className="pill pill-demo inline">Demo</span>}</p>
              <h1>{a.name}</h1>
              <Link href={`/u/${a.creator_handle}`} className="by"><span className="av av-sm">{a.initials}</span>{a.creator}<small>{a.role}</small></Link>
              <p className="pd-stats">{a.format}{a.stats?.sales ? ` · ${a.stats.sales} sold` : ''}</p>
              {!order ? <>
                <div className="opts" role="radiogroup">{opts.map(o => <button key={o.id} role="radio" aria-checked={opt === o.id} className={'opt' + (opt === o.id ? ' on' : '')} onClick={() => setOpt(o.id)}>
                  <span><strong>{o.name}{owned.includes(o.name) && <em> · owned</em>}</strong><small>{o.detail}</small></span><b>{o.price === 0 ? 'Free' : credits(disc ? Math.max(1, Math.round(o.price * (100 - disc.pct) / 100)) : o.price)}</b></button>)}</div>
                {a.price > 0 && <div className="code-row"><BadgePercent size={16} /><input value={code} onChange={e => { setCode(e.target.value.toUpperCase()); setDisc(null); setDiscMsg('') }} placeholder="Discount code" aria-label="Discount code" /><button className="btn btn-ghost btn-sm" onClick={() => applyCode(code)} disabled={!code}>Apply</button></div>}
                {discMsg && <p className={disc ? 'form-ok' : 'form-error'}>{discMsg}</p>}
                <div className="total"><span>Total</span><strong>{price === 0 ? 'Free' : creditsLong(price)}</strong></div>
                {user && wallet && price > 0 && <p className="muted small">Wallet balance: {creditsLong(wallet.balance)}{wallet.balance < price && ' — not enough credits'}</p>}
                {err && <p className="form-error">{err}</p>}
                {mine ? <Link href="/studio?tab=listings" className="btn btn-ghost btn-lg full">This is your listing · edit in studio</Link>
                  : hasThis ? <Link href="/library" className="btn btn-ghost btn-lg full"><Download size={18} />Open in library</Link>
                    : <button className="btn btn-primary btn-lg full" onClick={buy} disabled={busy || (!!user && !!wallet && wallet.balance < price)}>{busy ? <Loader2 className="spin" size={18} /> : !user ? 'Log in to get this' : price === 0 ? 'Get it free' : `Buy for ${creditsLong(price)}`}</button>}
                <p className="assure"><ShieldCheck size={15} />Instant download · licence key · receipt in your library</p>
              </> : <div className="bought">
                <Check size={28} /><h3>It’s yours.</h3><p>Receipt {order.receipt} · {order.license_name}{order.price ? ` · ${creditsLong(order.price)}` : ''}</p>
                {order.license_key && <div className="key-row"><code>{order.license_key}</code><button className="icon-btn" onClick={() => copy(order.license_key!, 'key')} aria-label="Copy licence key">{copied === 'key' ? <Check size={15} /> : <Copy size={15} />}</button></div>}
                <Link href="/library" className="btn btn-primary btn-lg full"><Download size={18} />Download now</Link>
              </div>}
            </div>
            <div className="share-card">
              <strong><Share2 size={15} />Share{a.affiliate_pct ? ` & earn ${a.affiliate_pct}%` : ''}</strong>
              {a.affiliate_pct && user && !mine ? <p className="muted small">Anyone who buys through your link earns you {a.affiliate_pct}% of the creator’s share.</p> : null}
              <div className="share-row"><input readOnly value={shareUrl} aria-label="Share link" /><button className="icon-btn" onClick={() => copy(shareUrl, 'link')} aria-label="Copy link">{copied === 'link' ? <Check size={15} /> : <Copy size={15} />}</button><button className="icon-btn" onClick={() => setQr(q => !q)} aria-label="QR code"><QrCode size={15} /></button></div>
              <div className="share-btns">
                <a target="_blank" rel="noreferrer" href={`https://wa.me/?text=${encodeURIComponent(`${a.name} on SmartSharing ${shareUrl}`)}`}>WhatsApp</a>
                <a target="_blank" rel="noreferrer" href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(a.name)}&url=${encodeURIComponent(shareUrl)}`}>X</a>
                <a target="_blank" rel="noreferrer" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`}>LinkedIn</a>
                <a target="_blank" rel="noreferrer" href={`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(a.name)}`}>Telegram</a>
              </div>
              {qr && <img className="qr" src={`${API_URL}/api/qr?data=${encodeURIComponent(shareUrl)}`} alt="QR code for this listing" />}
            </div>
          </aside>
        </div>
        {more.length > 0 && <section className="shelf"><div className="shelf-head"><h2>More from {a.creator}</h2><Link className="link" href={`/u/${a.creator_handle}`}>View profile</Link></div><div className="grid">{more.map(x => <AssetCard key={x.id} a={x} />)}</div></section>}
      </main>
      <Footer />
    </>
  );
}
