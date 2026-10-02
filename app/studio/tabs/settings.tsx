'use client';
import Link from 'next/link';
import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api, errMsg } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const LINKS = ['Instagram', 'YouTube', 'LinkedIn', 'X', 'Behance', 'Dribbble'];

export function SettingsTab() {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  if (!user) return null;
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setMsg(''); setErr('');
    const links: Record<string, string> = {}; LINKS.forEach(l => { const v = String(f.get('link_' + l) || '').trim(); if (v) links[l] = v.startsWith('http') ? v : 'https://' + v });
    const website = String(f.get('website') || '').trim();
    try { await api.updateMe({ full_name: String(f.get('full_name')), role: String(f.get('role')), bio: String(f.get('bio')), city: String(f.get('city')), website: website ? (website.startsWith('http') ? website : 'https://' + website) : '', links }); await refresh(); setMsg('Profile saved') } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <>
      <div className="tab-head"><div><h1>Profile & settings</h1><p className="muted">This is what buyers see on <Link className="link" href={`/u/${user.handle}`}>your storefront</Link>.</p></div></div>
      <div className="panel"><form className="form grid-form" onSubmit={save}>
        <label>Display name<input name="full_name" defaultValue={user.full_name} required minLength={2} maxLength={80} /></label>
        <label>What you do<input name="role" defaultValue={user.role || ''} maxLength={40} placeholder="Colourist · Motion designer" /></label>
        <label className="span2">Bio<textarea name="bio" rows={3} maxLength={400} defaultValue={user.bio || ''} placeholder="One or two lines about your work and who it’s for." /></label>
        <label>City<input name="city" defaultValue={user.city || ''} maxLength={40} /></label>
        <label>Website<input name="website" defaultValue={user.website || ''} maxLength={120} placeholder="yourstudio.in" /></label>
        {LINKS.map(l => <label key={l}>{l}<input name={'link_' + l} defaultValue={user.links?.[l] || ''} placeholder={`https://${l.toLowerCase()}.com/you`} /></label>)}
        {err && <p className="form-error span2">{err}</p>}{msg && <p className="form-ok span2">{msg}</p>}
        <div className="span2 form-actions"><span className="muted small">Handle @{user.handle} · {user.email}</span><button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : 'Save profile'}</button></div>
      </form></div>
    </>
  );
}
