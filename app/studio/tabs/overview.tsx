'use client';
import { useEffect, useState } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowRight, Eye, IndianRupee, Percent, ShoppingBag, Users } from 'lucide-react';
import { api, type Overview } from '../../lib/api';
import { credits, timeAgo } from '../../lib/market';

export function OverviewTab({ go }: { go: (t: string, extra?: string) => void }) {
  const [days, setDays] = useState(30);
  const [o, setO] = useState<Overview | null>(null);
  useEffect(() => { setO(null); api.overview(days).then(setO).catch(() => {}) }, [days]);
  const kpis = o ? [
    { l: 'Earnings', v: credits(o.revenue), s: `${credits(o.gross)} gross`, i: IndianRupee },
    { l: 'Sales', v: String(o.sales), s: `${o.customers} customers`, i: ShoppingBag },
    { l: 'Views', v: o.views.toLocaleString('en-IN'), s: 'listing page views', i: Eye },
    { l: 'Conversion', v: `${o.conversion}%`, s: 'views → sales', i: Percent },
    { l: 'Affiliate', v: credits(o.affiliate_earnings), s: 'earned promoting others', i: Users },
  ] : [];
  return (
    <>
      <div className="tab-head"><div><h1>Overview</h1><p className="muted">How your storefront is doing.</p></div>
        <div className="seg">{[7, 30, 90].map(d => <button key={d} className={days === d ? 'on' : ''} onClick={() => setDays(d)}>{d}d</button>)}</div></div>
      {!o ? <div className="kpis">{[0, 1, 2, 3, 4].map(i => <div key={i} className="kpi skel" />)}</div> : <>
        <div className="kpis">{kpis.map(k => <div key={k.l} className="kpi"><span className="kpi-ic"><k.i size={16} /></span><small>{k.l}</small><strong>{k.v}</strong><em>{k.s}</em></div>)}</div>
        <div className="panel">
          <div className="panel-head"><h3>Earnings & views</h3><span className="muted small">Wallet {credits(o.balance)}</span></div>
          <div style={{ height: 260 }}>
            <ResponsiveContainer><AreaChart data={o.series} margin={{ left: -10, right: 8, top: 8 }}>
              <defs><linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#d6ff7f" stopOpacity={0.35} /><stop offset="1" stopColor="#d6ff7f" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid stroke="#1f2630" vertical={false} />
              <XAxis dataKey="day" tickFormatter={d => d.slice(5)} stroke="#6b7684" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
              <YAxis stroke="#6b7684" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#11161d', border: '1px solid #2a323d', borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="revenue" name="Earnings (cr)" stroke="#d6ff7f" fill="url(#gr)" strokeWidth={2} />
              <Area type="monotone" dataKey="views" name="Views" stroke="#7cc6fe" fill="transparent" strokeWidth={1.5} />
            </AreaChart></ResponsiveContainer>
          </div>
        </div>
        <div className="two-col">
          <div className="panel"><div className="panel-head"><h3>Recent sales</h3><button className="link" onClick={() => go('sales')}>All sales <ArrowRight size={13} /></button></div>
            {o.recent_sales.length === 0 ? <div className="first-steps">
              <p className="muted">No sales yet. Three things that get the first one:</p>
              <ol><li><button className="link" onClick={() => go('listings', '&new=1')}>Publish a listing with files</button></li><li><button className="link" onClick={() => go('marketing')}>Create a launch discount code</button></li><li><button className="link" onClick={() => go('integrations')}>Connect Discord or Telegram for sale alerts</button></li></ol>
            </div> : <table className="tbl"><tbody>{o.recent_sales.map(s => <tr key={s.receipt}><td><strong>{s.asset}</strong><small>{s.license} · {s.buyer}{s.discount_code ? ` · ${s.discount_code}` : ''}</small></td><td className="num">+{credits(s.amount)}</td><td className="muted small">{timeAgo(s.at)}</td></tr>)}</tbody></table>}
          </div>
          <div className="panel"><div className="panel-head"><h3>Top listings</h3><button className="link" onClick={() => go('listings')}>Manage <ArrowRight size={13} /></button></div>
            {o.top_assets.length === 0 ? <p className="muted small">Your best sellers will show here.</p> : <table className="tbl"><tbody>{o.top_assets.map(t => <tr key={t.asset_id}><td><strong>{t.name}</strong><small>{t.sales} sales</small></td><td className="num">{credits(t.revenue)}</td></tr>)}</tbody></table>}
            {o.sources.length > 0 && <><h4 className="sub">Traffic sources</h4><div className="bars">{o.sources.slice(0, 6).map(s => <div key={s.source} className="bar"><span>{s.source}</span><i style={{ width: `${Math.max(6, s.views / o.sources[0].views * 100)}%` }} /><b>{s.views}</b></div>)}</div></>}
          </div>
        </div>
      </>}
    </>
  );
}
