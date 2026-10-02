'use client';
import { useEffect, useState } from 'react';
import { Loader2, Send, Trash2, Check, Copy, CircleCheck, CircleAlert } from 'lucide-react';
import { api, errMsg, type Integration } from '../../lib/api';
import { timeAgo } from '../../lib/market';

const KINDS = [
  { type: 'discord', name: 'Discord', hint: 'Server Settings → Integrations → Webhooks → New Webhook → Copy URL', field: 'url', ph: 'https://discord.com/api/webhooks/…' },
  { type: 'slack', name: 'Slack', hint: 'api.slack.com/apps → Create app → Incoming Webhooks → Add to channel → copy URL', field: 'url', ph: 'https://hooks.slack.com/services/…' },
  { type: 'telegram', name: 'Telegram', hint: 'Message @BotFather → /newbot → copy token. Add the bot to your chat, then get the chat id from @userinfobot (or the group id).', field: 'telegram', ph: '' },
  { type: 'webhook', name: 'Webhook · Zapier / Make / n8n / Pipedream', hint: 'Zapier: “Webhooks by Zapier → Catch Hook”. Make: “Custom webhook”. n8n: “Webhook” node. Paste the URL they give you. Bodies are JSON signed with HMAC-SHA256.', field: 'url', ph: 'https://hooks.zapier.com/hooks/catch/…' },
] as const;
const EVENTS = [{ id: 'sale.completed', label: 'New sale' }, { id: 'transfer.received', label: 'Credits received' }];

export function IntegrationsTab() {
  const [items, setItems] = useState<Integration[] | null>(null);
  const [kind, setKind] = useState<(typeof KINDS)[number]>(KINDS[0]);
  const [events, setEvents] = useState<string[]>(['sale.completed']);
  const [busy, setBusy] = useState(''); const [err, setErr] = useState('');
  const [secret, setSecret] = useState(''); const [copied, setCopied] = useState(false);
  const [test, setTest] = useState<Record<string, string>>({});
  const load = () => api.integrations().then(r => setItems(r.items)).catch(() => setItems([]));
  useEffect(() => { load() }, []);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy('add'); setErr(''); setSecret('');
    const config: Record<string, string> = kind.field === 'telegram' ? { bot_token: String(f.get('bot_token')), chat_id: String(f.get('chat_id')) } : { url: String(f.get('url')) };
    try { const r = await api.createIntegration({ type: kind.type, name: String(f.get('name') || ''), config, events }); if (r.signing_secret) setSecret(r.signing_secret); (e.target as HTMLFormElement).reset(); load() } catch (x) { setErr(errMsg(x)) } finally { setBusy('') }
  }
  async function runTest(id: string) { setBusy(id); try { const r = await api.testIntegration(id); setTest(t => ({ ...t, [id]: r.ok ? 'Delivered ✓' : `Failed${r.status ? ` (${r.status})` : ''}: ${r.error || ''}` })); load() } catch (x) { setTest(t => ({ ...t, [id]: errMsg(x) })) } finally { setBusy('') } }

  return (
    <>
      <div className="tab-head"><div><h1>Integrations</h1><p className="muted">Get a ping the moment you make a sale, or pipe orders into Sheets, Notion, your CRM or email list through Zapier, Make or n8n.</p></div></div>
      <div className="two-col">
        <div className="panel"><div className="panel-head"><h3>Connect</h3></div>
          <div className="kind-pick">{KINDS.map(k => <button key={k.type} className={'kind' + (kind.type === k.type ? ' on' : '')} onClick={() => setKind(k)}>{k.name}</button>)}</div>
          <p className="muted small hint">{kind.hint}</p>
          <form className="form" onSubmit={add} key={kind.type}>
            <label>Name (optional)<input name="name" maxLength={40} placeholder={`${kind.name.split(' ')[0]} sales alerts`} /></label>
            {kind.field === 'telegram' ? <div className="grid-form"><label>Bot token<input name="bot_token" required placeholder="123456:ABC-DEF…" /></label><label>Chat id<input name="chat_id" required placeholder="-1001234567890" /></label></div>
              : <label>Webhook URL<input name="url" type="url" required placeholder={kind.ph} /></label>}
            <fieldset className="evts"><legend>Send me</legend>{EVENTS.map(ev => <label key={ev.id} className="check"><input type="checkbox" checked={events.includes(ev.id)} onChange={e => setEvents(s => e.target.checked ? [...s, ev.id] : s.filter(x => x !== ev.id))} />{ev.label}</label>)}</fieldset>
            {err && <p className="form-error">{err}</p>}
            <button className="btn btn-primary" disabled={busy === 'add' || !events.length}>{busy === 'add' ? <Loader2 size={16} className="spin" /> : 'Connect'}</button>
          </form>
          {secret && <div className="secret"><strong>Signing secret — copy it now, it won’t be shown again</strong><div className="share-row"><input readOnly value={secret} /><button className="icon-btn" onClick={() => navigator.clipboard.writeText(secret).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })} aria-label="Copy">{copied ? <Check size={15} /> : <Copy size={15} />}</button></div><p className="muted small">Verify: HMAC-SHA256(secret, raw body) == header <code>X-SmartSharing-Signature</code> (after “sha256=”).</p></div>}
        </div>
        <div className="panel"><div className="panel-head"><h3>Connected</h3></div>
          {items === null ? <div className="skel-block" /> : items.length === 0 ? <p className="muted small">Nothing connected yet. Discord or Telegram takes under a minute.</p>
            : <ul className="integ-list">{items.map(i => <li key={i.id}>
              <div><strong>{i.name}</strong><small>{i.type} · {i.events.map(e => EVENTS.find(x => x.id === e)?.label || e).join(', ')} · <code>{i.config.url || i.config.chat_id}</code></small>
                {i.last_delivery && <small className={i.last_delivery.ok ? 'ok' : 'bad'}>{i.last_delivery.ok ? <CircleCheck size={12} /> : <CircleAlert size={12} />} Last {i.last_delivery.event} {timeAgo(i.last_delivery.at)}{i.last_delivery.status ? ` · ${i.last_delivery.status}` : ''}</small>}
                {test[i.id] && <small className="muted">{test[i.id]}</small>}</div>
              <div className="row-gap">
                <label className="switch" title={i.active ? 'Active' : 'Paused'}><input type="checkbox" checked={i.active} onChange={async e => { await api.toggleIntegration(i.id, e.target.checked); load() }} /><span /></label>
                <button className="btn btn-ghost btn-sm" onClick={() => runTest(i.id)} disabled={busy === i.id}>{busy === i.id ? <Loader2 size={14} className="spin" /> : <Send size={14} />}Test</button>
                <button className="icon-btn" aria-label="Remove" onClick={async () => { if (confirm('Remove this integration?')) { await api.deleteIntegration(i.id); load() } }}><Trash2 size={14} /></button>
              </div></li>)}</ul>}
          <h4 className="sub">Popular recipes</h4>
          <ul className="recipes"><li><b>Google Sheets sales log</b> — Webhook → Zapier “Catch Hook” → Sheets “Create row”.</li><li><b>Add buyers to your newsletter</b> — Webhook → Make → Mailchimp / ConvertKit / Brevo.</li><li><b>Notion order database</b> — Webhook → n8n Notion node.</li><li><b>Team ping</b> — Discord or Slack channel for every sale.</li></ul>
        </div>
      </div>
    </>
  );
}
