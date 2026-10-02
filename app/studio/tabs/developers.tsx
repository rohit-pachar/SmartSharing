'use client';
import { useEffect, useState } from 'react';
import { KeyRound, Trash2, Copy, Check, Loader2 } from 'lucide-react';
import { api, API_URL, errMsg, type ApiKey } from '../../lib/api';
import { timeAgo } from '../../lib/market';

export function DevelopersTab() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [fresh, setFresh] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [copied, setCopied] = useState('');
  const load = () => api.apiKeys().then(r => setKeys(r.items)).catch(() => setKeys([]));
  useEffect(() => { load() }, []);
  const copy = (t: string) => navigator.clipboard.writeText(t).then(() => { setCopied(t); setTimeout(() => setCopied(''), 1500) });
  const verify = `curl -X POST ${API_URL}/api/licenses/verify \\\n  -H "Content-Type: application/json" \\\n  -d '{"asset_id":"YOUR-ASSET-ID","license_key":"ABCDE-FGHJK-LMNPQ-RSTUV"}'`;
  const list = `curl ${API_URL}/api/studio/overview?days=30 \\\n  -H "Authorization: Bearer ssk_your_key"`;
  const webhook = `import hmac, hashlib\n\ndef valid(raw_body: bytes, header: str, secret: str) -> bool:\n    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()\n    return hmac.compare_digest("sha256=" + sig, header)`;
  return (
    <>
      <div className="tab-head"><div><h1>Developers</h1><p className="muted">Licence-key verification for software you sell, plus an API for your own dashboards and automations.</p></div></div>
      <div className="two-col">
        <div className="panel"><div className="panel-head"><h3><KeyRound size={16} />API keys</h3></div>
          <form className="share-row" onSubmit={async e => { e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setErr(''); try { const r = await api.createApiKey(String(f.get('name'))); setFresh(r.key); (e.target as HTMLFormElement).reset(); load() } catch (x) { setErr(errMsg(x)) } finally { setBusy(false) } }}>
            <input name="name" required maxLength={40} placeholder="Key name, e.g. Notion sync" /><button className="btn btn-primary btn-sm" disabled={busy}>{busy ? <Loader2 size={14} className="spin" /> : 'Create key'}</button></form>
          {err && <p className="form-error">{err}</p>}
          {fresh && <div className="secret"><strong>Copy your key now — it won’t be shown again</strong><div className="share-row"><input readOnly value={fresh} /><button className="icon-btn" onClick={() => copy(fresh)} aria-label="Copy">{copied === fresh ? <Check size={15} /> : <Copy size={15} />}</button></div></div>}
          {keys && keys.length > 0 && <table className="tbl"><thead><tr><th>Name</th><th>Key</th><th>Last used</th><th /></tr></thead><tbody>{keys.map(k => <tr key={k.id}><td>{k.name}</td><td><code>{k.prefix}…</code></td><td className="muted small">{k.last_used_at ? timeAgo(k.last_used_at) : 'Never'}</td><td><button className="icon-btn" aria-label="Revoke" onClick={async () => { if (confirm('Revoke this key?')) { await api.revokeApiKey(k.id); load() } }}><Trash2 size={14} /></button></td></tr>)}</tbody></table>}
          <p className="muted small">Keys can read your studio data and manage listings, discounts and files. They can’t buy, send credits or create other keys.</p>
          <h4 className="sub">Read your stats</h4>
          <pre className="code"><button onClick={() => copy(list)} aria-label="Copy">{copied === list ? <Check size={13} /> : <Copy size={13} />}</button>{list}</pre>
          <p className="muted small">Also: <code>GET /api/studio/assets</code>, <code>/studio/customers</code>, <code>/studio/export/sales.csv</code>, <code>PATCH /studio/assets/:id</code>, <code>POST /studio/discounts</code>.</p>
        </div>
        <div className="panel"><div className="panel-head"><h3>Licence keys</h3></div>
          <p className="muted small">Every order gets a unique key (shown to the buyer in their library). Verify it from your plugin, app or script — no auth needed. Same response shape as Gumroad’s verify API, so existing code ports easily.</p>
          <pre className="code"><button onClick={() => copy(verify)} aria-label="Copy">{copied === verify ? <Check size={13} /> : <Copy size={13} />}</button>{verify}</pre>
          <p className="muted small">Response: <code>{'{ success, uses, purchase: { license, license_id, buyer_handle, created_at… } }'}</code>. Pass <code>increment_uses_count: false</code> to check without counting an activation.</p>
          <h4 className="sub">Verify webhook signatures</h4>
          <pre className="code"><button onClick={() => copy(webhook)} aria-label="Copy">{copied === webhook ? <Check size={13} /> : <Copy size={13} />}</button>{webhook}</pre>
          <p className="muted small">Events: <code>sale.completed</code>, <code>transfer.received</code>, <code>test.ping</code>. Full reference at <a className="link" href={`${API_URL}/docs`} target="_blank" rel="noreferrer">{API_URL.replace('https://', '')}/docs</a>.</p>
        </div>
      </div>
    </>
  );
}
