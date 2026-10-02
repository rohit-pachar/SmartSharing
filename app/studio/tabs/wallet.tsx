'use client';
import { useEffect, useState } from 'react';
import { ArrowDownLeft, ArrowUpRight, Download, Loader2, Send } from 'lucide-react';
import { api, downloadCsv, errMsg, type LedgerRow, type Transfer } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { creditsLong, LEDGER_LABEL, timeAgo } from '../../lib/market';

export function WalletTab() {
  const { wallet, refresh } = useAuth();
  const [ledger, setLedger] = useState<LedgerRow[] | null>(null);
  const [incoming, setIncoming] = useState<Transfer[]>([]);
  const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  const load = () => { api.ledger().then(r => setLedger(r.items)).catch(() => setLedger([])); api.transfers('in', 'pending').then(r => setIncoming(r.items)).catch(() => {}); refresh() };
  useEffect(() => { load() }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const f = new FormData(form); setBusy(true); setMsg('');
    try { const t = await api.send(String(f.get('to')).trim().replace(/^@/, ''), Number(f.get('amount')), String(f.get('memo') || '') || undefined); setMsg(`Sent ${creditsLong(t.amount)} — it lands once they accept.`); form.reset(); load() } catch (x) { setMsg(errMsg(x)) } finally { setBusy(false) }
  }
  return (
    <>
      <div className="tab-head"><div><h1>Wallet</h1><p className="muted">Sales, purchases, commissions and transfers — every credit accounted for.</p></div><button className="btn btn-ghost" onClick={() => downloadCsv('ledger')}><Download size={16} />Export CSV</button></div>
      <div className="kpis kpis-3">
        <div className="kpi"><small>Available</small><strong>{wallet ? creditsLong(wallet.balance) : '—'}</strong></div>
        <div className="kpi"><small>Sent, awaiting accept</small><strong>{wallet ? creditsLong(wallet.pending_out) : '—'}</strong></div>
        <div className="kpi"><small>Incoming to accept</small><strong>{incoming.length}</strong></div>
      </div>
      <div className="two-col">
        <div className="panel"><div className="panel-head"><h3>History</h3></div>
          {ledger === null ? <div className="skel-block" /> : ledger.length === 0 ? <p className="muted small">No activity yet.</p>
            : <table className="tbl"><tbody>{ledger.map(l => <tr key={l.id}><td><span className={'dir ' + (l.amount >= 0 ? 'in' : 'out')}>{l.amount >= 0 ? <ArrowDownLeft size={14} /> : <ArrowUpRight size={14} />}</span></td><td><strong>{LEDGER_LABEL[l.kind] || l.kind}</strong><small>{l.memo || ''}</small></td><td className={'num ' + (l.amount >= 0 ? 'pos' : '')}>{l.amount > 0 ? '+' : ''}{l.amount !== 0 ? creditsLong(l.amount) : '—'}</td><td className="muted small">{timeAgo(l.created_at)}</td></tr>)}</tbody></table>}
        </div>
        <div>
          {incoming.length > 0 && <div className="panel"><div className="panel-head"><h3>Incoming</h3></div>{incoming.map(t => <div key={t.id} className="incoming"><div><strong>{creditsLong(t.amount)}</strong><small>{t.memo || 'Credit transfer'} · {timeAgo(t.created_at)}</small></div><div className="row-gap"><button className="btn btn-primary btn-sm" onClick={async () => { await api.acceptTransfer(t.id); load() }}>Accept</button><button className="btn btn-ghost btn-sm" onClick={async () => { await api.rejectTransfer(t.id); load() }}>Decline</button></div></div>)}</div>}
          <div className="panel"><div className="panel-head"><h3><Send size={15} />Send credits</h3></div>
            <p className="muted small">Pay a collaborator, split a client project or tip a creator.</p>
            <form className="form" onSubmit={send}><label>To (handle)<input name="to" required placeholder="@priya.sharma" /></label><label>Amount<input name="amount" type="number" min={1} max={wallet?.balance} required /></label><label>Note<input name="memo" maxLength={140} placeholder="For the thumbnail pack" /></label>
              {msg && <p className="form-note">{msg}</p>}<button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : 'Send'}</button></form>
          </div>
        </div>
      </div>
    </>
  );
}
