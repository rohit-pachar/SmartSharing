'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Plus, Upload, Trash2, Loader2, ExternalLink, FileArchive, Eye, EyeOff, X } from 'lucide-react';
import { api, errMsg, mediaUrl, type StudioAsset } from '../../lib/api';
import { bytes, CATEGORIES, credits } from '../../lib/market';
import { Empty } from '../../ui';

export function ListingsTab({ startNew }: { startNew: boolean }) {
  const [items, setItems] = useState<StudioAsset[] | null>(null);
  const [edit, setEdit] = useState<StudioAsset | null>(null);
  const [creating, setCreating] = useState(startNew);
  const load = () => api.studioAssets().then(r => { setItems(r.items); if (edit) setEdit(r.items.find(x => x.id === edit.id) || null) }).catch(() => setItems([]));
  useEffect(() => { load() }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <div className="tab-head"><div><h1>Listings</h1><p className="muted">Create, upload files, price and publish.</p></div><button className="btn btn-primary" onClick={() => { setCreating(true); setEdit(null) }}><Plus size={16} />New listing</button></div>
      {creating && <NewListing onDone={async a => { setCreating(false); if (!a) return; const r = await api.studioAssets().catch(() => null); if (r) { setItems(r.items); setEdit(r.items.find(x => x.id === a.id) || null) } }} />}
      {edit && <EditListing a={edit} onChange={load} onClose={() => setEdit(null)} />}
      {items === null ? <div className="skel-block" /> : items.length === 0 && !creating ? <Empty icon={<FileArchive size={22} />} title="No listings yet" text="Upload a pack, set a price and publish. Buyers download instantly." action={<button className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={16} />Create your first listing</button>} />
        : <div className="panel flush"><table className="tbl tbl-list"><thead><tr><th>Listing</th><th>Status</th><th>Price</th><th>Files</th><th className="num">Sales</th><th className="num">Revenue</th><th /></tr></thead><tbody>
          {(items || []).map(a => <tr key={a.id} className="clickable" onClick={() => { setEdit(a); setCreating(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>
            <td><span className="tbl-asset"><img src={mediaUrl(a.image)} alt="" /><span><strong>{a.name}</strong><small>{a.category}</small></span></span></td>
            <td><span className={'status ' + a.status}>{a.status === 'published' ? 'Live' : 'Draft'}</span></td>
            <td>{credits(a.price)}</td><td>{a.files?.length ?? 0}</td><td className="num">{a.stats?.sales ?? 0}</td><td className="num">{credits(a.stats?.revenue ?? 0)}</td>
            <td><Link href={`/p/${a.id}`} onClick={e => e.stopPropagation()} className="icon-btn" aria-label="View public page"><ExternalLink size={14} /></Link></td></tr>)}
        </tbody></table></div>}
    </>
  );
}

function NewListing({ onDone }: { onDone: (a?: StudioAsset) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const [kind, setKind] = useState('file');
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setErr('');
    try {
      const a = await api.createAsset({ name: String(f.get('name')), category: String(f.get('category')), description: String(f.get('description')), price: Number(f.get('price')), kind, format: String(f.get('format') || ''), includes: String(f.get('includes') || '').split('\n').map(s => s.trim()).filter(Boolean).slice(0, 12) });
      onDone(a);
    } catch (x) { setErr(errMsg(x)); setBusy(false) }
  }
  return (
    <div className="panel editor"><div className="panel-head"><h3>New listing</h3><button className="icon-btn" onClick={() => onDone()} aria-label="Close"><X size={16} /></button></div>
      <form className="form grid-form" onSubmit={submit}>
        <label className="span2">Title<input name="name" required minLength={3} maxLength={70} placeholder="e.g. Wedding Film LUTs Vol. 2" /></label>
        <label>Category<select name="category" defaultValue="Templates">{CATEGORIES.slice(1).map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Type<select value={kind} onChange={e => setKind(e.target.value)}><option value="file">Downloadable files</option><option value="hosted">Hosted tool / pass</option></select></label>
        <label>Base price (credits)<input name="price" type="number" min={0} max={100000} defaultValue={299} required /><small>0 = free. Commercial = 2×, Studio = 4× automatically.</small></label>
        <label>Format line<input name="format" maxLength={60} placeholder="e.g. CUBE · 12 LUTs" /></label>
        <label className="span2">Description<textarea name="description" required minLength={10} maxLength={2000} rows={4} placeholder="What does it do, who is it for, what software does it work with?" /></label>
        <label className="span2">What’s included (one per line)<textarea name="includes" rows={3} placeholder={'12 .cube LUTs\nInstall guide\nBefore/after previews'} /></label>
        {err && <p className="form-error span2">{err}</p>}
        <div className="span2 form-actions"><span className="muted small">{kind === 'file' ? 'Saved as a draft — upload files next, then publish.' : 'Hosted listings publish immediately.'}</span><button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : 'Create listing'}</button></div>
      </form>
    </div>
  );
}

function EditListing({ a, onChange, onClose }: { a: StudioAsset; onChange: () => void; onClose: () => void }) {
  const [busy, setBusy] = useState(''); const [err, setErr] = useState(''); const [msg, setMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy('save'); setErr(''); setMsg('');
    try { await api.updateAsset(a.id, { name: f.get('name'), description: f.get('description'), price: Number(f.get('price')), format: f.get('format'), affiliate_pct: Number(f.get('affiliate_pct') || 0) }); setMsg('Saved'); onChange() } catch (x) { setErr(errMsg(x)) } finally { setBusy('') }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return; setErr(''); setBusy('upload');
    try { for (const f of Array.from(files)) await api.uploadFile(a.id, f); onChange() } catch (x) { setErr(errMsg(x)) } finally { setBusy('') }
  }
  async function status(s: 'published' | 'draft') { setBusy('status'); setErr(''); try { await api.updateAsset(a.id, { status: s }); onChange() } catch (x) { setErr(errMsg(x)) } finally { setBusy('') } }
  return (
    <div className="panel editor">
      <div className="panel-head"><h3>{a.name} <span className={'status ' + a.status}>{a.status === 'published' ? 'Live' : 'Draft'}</span></h3>
        <div className="row-gap">{a.status === 'draft' ? <button className="btn btn-primary btn-sm" onClick={() => status('published')} disabled={!!busy}><Eye size={15} />Publish</button> : <button className="btn btn-ghost btn-sm" onClick={() => status('draft')} disabled={!!busy}><EyeOff size={15} />Unpublish</button>}
          <Link href={`/p/${a.id}`} className="btn btn-ghost btn-sm"><ExternalLink size={15} />View</Link><button className="icon-btn" onClick={onClose} aria-label="Close"><X size={16} /></button></div></div>
      <div className="editor-grid">
        <form className="form" onSubmit={save} key={a.id}>
          <label>Title<input name="name" defaultValue={a.name} required minLength={3} maxLength={70} /></label>
          <label>Description<textarea name="description" defaultValue={a.description} rows={5} maxLength={2000} /></label>
          <div className="grid-form">
            <label>Base price (credits)<input name="price" type="number" min={0} max={100000} defaultValue={a.price} /></label>
            <label>Format line<input name="format" defaultValue={a.format} maxLength={60} /></label>
            <label>Affiliate commission %<input name="affiliate_pct" type="number" min={0} max={50} defaultValue={a.affiliate_pct || 0} /><small>Paid from your share when someone sells via their link.</small></label>
          </div>
          {err && <p className="form-error">{err}</p>}{msg && <p className="form-ok">{msg}</p>}
          <button className="btn btn-primary" disabled={busy === 'save'}>{busy === 'save' ? <Loader2 size={16} className="spin" /> : 'Save changes'}</button>
        </form>
        <div>
          <h4 className="sub">Deliverable files</h4>
          <div className={'drop' + (drag ? ' over' : '')} onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files) }} onClick={() => fileRef.current?.click()}>
            {busy === 'upload' ? <Loader2 className="spin" /> : <Upload />}<strong>Drop files or click to upload</strong><small>ZIP, PDF, PNG, CUBE, XLSX, DOCX, MP4… up to 50 MB each</small>
            <input ref={fileRef} type="file" multiple hidden onChange={e => upload(e.target.files)} />
          </div>
          <ul className="files">{(a.files || []).map(f => <li key={f.idx}><FileArchive size={16} />{f.name}<span>{bytes(f.size)}</span><button className="icon-btn" aria-label={`Delete ${f.name}`} onClick={async () => { await api.deleteFile(a.id, f.idx); onChange() }}><Trash2 size={14} /></button></li>)}</ul>
          {!(a.files?.length) && a.kind === 'file' && <p className="muted small">Upload at least one file to publish.</p>}
        </div>
      </div>
    </div>
  );
}
