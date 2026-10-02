'use client';
import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { api, downloadCsv, type Customer, type Overview } from '../../lib/api';
import { credits, timeAgo } from '../../lib/market';
import { Empty } from '../../ui';

export function SalesTab() {
  const [o, setO] = useState<Overview | null>(null);
  const [c, setC] = useState<Customer[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.overview(90).then(setO).catch(() => {}); api.customers().then(r => setC(r.items)).catch(() => setC([])) }, []);
  return (
    <>
      <div className="tab-head"><div><h1>Sales & customers</h1><p className="muted">Every order, who bought, and what they paid.</p></div>
        <button className="btn btn-ghost" disabled={busy} onClick={async () => { setBusy(true); try { await downloadCsv('sales') } finally { setBusy(false) } }}>{busy ? <Loader2 size={16} className="spin" /> : <Download size={16} />}Export CSV</button></div>
      <div className="two-col">
        <div className="panel"><div className="panel-head"><h3>Recent orders (90 days)</h3>{o && <span className="muted small">{o.sales} orders · {credits(o.revenue)} earned</span>}</div>
          {!o ? <div className="skel-block" /> : o.recent_sales.length === 0 ? <Empty icon={<Download size={20} />} title="No orders yet" text="Orders appear here the moment they happen." />
            : <table className="tbl"><thead><tr><th>Item</th><th>Buyer</th><th className="num">You earned</th><th>When</th></tr></thead><tbody>{o.recent_sales.map(s => <tr key={s.receipt}><td><strong>{s.asset}</strong><small>{s.license} · {s.receipt}{s.discount_code ? ` · ${s.discount_code}` : ''}</small></td><td>{s.buyer}</td><td className="num">+{credits(s.amount)}</td><td className="muted small">{timeAgo(s.at)}</td></tr>)}</tbody></table>}
          <p className="muted small">Export includes list price, discount, platform fee (12%), affiliate commission and your earnings per order.</p>
        </div>
        <div className="panel"><div className="panel-head"><h3>Customers</h3>{c && <span className="muted small">{c.length}</span>}</div>
          {c === null ? <div className="skel-block" /> : c.length === 0 ? <p className="muted small">Your customer list builds itself as people buy.</p>
            : <table className="tbl"><thead><tr><th>Customer</th><th className="num">Orders</th><th className="num">Spent</th><th>Last</th></tr></thead><tbody>{c.map((x, i) => <tr key={i}><td><strong>{x.name}</strong><small>{x.handle ? '@' + x.handle : ''}</small></td><td className="num">{x.orders}</td><td className="num">{credits(x.spent)}</td><td className="muted small">{timeAgo(x.last_order)}</td></tr>)}</tbody></table>}
        </div>
      </div>
    </>
  );
}
