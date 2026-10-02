'use client';
import { useMemo, useState } from 'react';
import { Calculator, FileText, Hash, Receipt, Scissors, Type, Copy, Check, Printer } from 'lucide-react';

const TOOLS = [
  { id: 'pricing', label: 'Pricing calculator', icon: Calculator },
  { id: 'gst', label: 'GST & TDS calculator', icon: Receipt },
  { id: 'invoice', label: 'Quick invoice', icon: FileText },
  { id: 'caption', label: 'Caption & bio checker', icon: Type },
  { id: 'hashtags', label: 'Hashtag sets', icon: Hash },
  { id: 'safe', label: 'Safe zones & sizes', icon: Scissors },
] as const;

const inr = (n: number) => '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(isFinite(n) ? n : 0);

export function ToolkitTab() {
  const [t, setT] = useState<(typeof TOOLS)[number]['id']>('pricing');
  return (
    <>
      <div className="tab-head"><div><h1>Creator toolkit</h1><p className="muted">Everyday calculators and checkers — everything runs in your browser.</p></div></div>
      <div className="seg seg-wrap">{TOOLS.map(x => <button key={x.id} className={t === x.id ? 'on' : ''} onClick={() => setT(x.id)}><x.icon size={14} />{x.label}</button>)}</div>
      <div className="panel">{t === 'pricing' ? <Pricing /> : t === 'gst' ? <Gst /> : t === 'invoice' ? <Invoice /> : t === 'caption' ? <Caption /> : t === 'hashtags' ? <Hashtags /> : <Safe />}</div>
    </>
  );
}

function Pricing() {
  const [price, setPrice] = useState(499); const [goal, setGoal] = useState(50000); const [aff, setAff] = useState(0); const [disc, setDisc] = useState(0);
  const paid = price * (1 - disc / 100); const creator = paid * 0.88; const net = creator * (1 - aff / 100);
  return <div className="calc">
    <div className="form grid-form">
      <label>List price (credits ≈ ₹)<input type="number" value={price} min={0} onChange={e => setPrice(+e.target.value)} /></label>
      <label>Monthly income goal (₹)<input type="number" value={goal} min={0} onChange={e => setGoal(+e.target.value)} /></label>
      <label>Average discount %<input type="number" value={disc} min={0} max={90} onChange={e => setDisc(+e.target.value)} /></label>
      <label>Affiliate commission %<input type="number" value={aff} min={0} max={50} onChange={e => setAff(+e.target.value)} /></label>
    </div>
    <div className="calc-out">
      <div><small>Buyer pays</small><strong>{inr(paid)}</strong></div>
      <div><small>Platform fee (12%)</small><strong>−{inr(paid * 0.12)}</strong></div>
      {aff > 0 && <div><small>Affiliate</small><strong>−{inr(creator * aff / 100)}</strong></div>}
      <div className="hl"><small>You keep per sale</small><strong>{inr(net)}</strong></div>
      <div className="hl"><small>Sales needed / month</small><strong>{net > 0 ? Math.ceil(goal / net) : '—'}</strong></div>
      <div><small>≈ per day</small><strong>{net > 0 ? (Math.ceil(goal / net) / 30).toFixed(1) : '—'}</strong></div>
    </div>
    <p className="muted small">Commercial licences are 2× and Studio 4× the base price, so a mix of tiers usually needs fewer sales.</p>
  </div>;
}

function Gst() {
  const [amt, setAmt] = useState(25000); const [rate, setRate] = useState(18); const [inter, setInter] = useState(false); const [tds, setTds] = useState(10); const [incl, setIncl] = useState(false);
  const base = incl ? amt / (1 + rate / 100) : amt; const gst = base * rate / 100; const tdsAmt = base * tds / 100;
  return <div className="calc">
    <div className="form grid-form">
      <label>Amount (₹)<input type="number" value={amt} onChange={e => setAmt(+e.target.value)} /></label>
      <label>GST rate<select value={rate} onChange={e => setRate(+e.target.value)}>{[0, 5, 12, 18, 28].map(r => <option key={r} value={r}>{r}%</option>)}</select></label>
      <label>Supply<select value={inter ? '1' : '0'} onChange={e => setInter(e.target.value === '1')}><option value="0">Same state (CGST + SGST)</option><option value="1">Inter-state (IGST)</option></select></label>
      <label>TDS deducted by client<select value={tds} onChange={e => setTds(+e.target.value)}><option value={0}>None</option><option value={2}>2% (194C · contracts)</option><option value={10}>10% (194J · professional)</option></select></label>
      <label className="check"><input type="checkbox" checked={incl} onChange={e => setIncl(e.target.checked)} />Amount already includes GST</label>
    </div>
    <div className="calc-out">
      <div><small>Taxable value</small><strong>{inr(base)}</strong></div>
      {inter ? <div><small>IGST {rate}%</small><strong>{inr(gst)}</strong></div> : <><div><small>CGST {rate / 2}%</small><strong>{inr(gst / 2)}</strong></div><div><small>SGST {rate / 2}%</small><strong>{inr(gst / 2)}</strong></div></>}
      <div><small>Invoice total</small><strong>{inr(base + gst)}</strong></div>
      {tds > 0 && <div><small>TDS withheld</small><strong>−{inr(tdsAmt)}</strong></div>}
      <div className="hl"><small>Hits your bank</small><strong>{inr(base + gst - tdsAmt)}</strong></div>
    </div>
    <p className="muted small">TDS is on the pre-GST value and claimable against your income tax (check Form 26AS). Confirm rates with your CA.</p>
  </div>;
}

type Line = { d: string; q: number; r: number };
function Invoice() {
  const [from, setFrom] = useState('Your Studio\nCity, State\nGSTIN: '); const [to, setTo] = useState('Client name\nAddress\nGSTIN: ');
  const [no, setNo] = useState('INV-' + new Date().getFullYear() + '-001'); const [rate, setRate] = useState(18); const [inter, setInter] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ d: 'Instagram Reel — concept, shoot & edit', q: 1, r: 12000 }]);
  const [upi, setUpi] = useState('');
  const sub = lines.reduce((s, l) => s + l.q * l.r, 0); const gst = sub * rate / 100;
  const upd = (i: number, k: keyof Line, v: string) => setLines(ls => ls.map((l, j) => j === i ? { ...l, [k]: k === 'd' ? v : +v } : l));
  return <div className="invoice-tool">
    <div className="form grid-form no-print">
      <label>From<textarea rows={3} value={from} onChange={e => setFrom(e.target.value)} /></label>
      <label>Bill to<textarea rows={3} value={to} onChange={e => setTo(e.target.value)} /></label>
      <label>Invoice #<input value={no} onChange={e => setNo(e.target.value)} /></label>
      <label>GST<select value={rate} onChange={e => setRate(+e.target.value)}>{[0, 5, 12, 18].map(r => <option key={r} value={r}>{r}%</option>)}</select></label>
      <label>Supply<select value={inter ? '1' : '0'} onChange={e => setInter(e.target.value === '1')}><option value="0">Same state</option><option value="1">Inter-state</option></select></label>
      <label>UPI ID (optional)<input value={upi} onChange={e => setUpi(e.target.value)} placeholder="name@bank" /></label>
    </div>
    <div className="invoice-sheet" id="invoice-print">
      <div className="inv-top"><div><h2>TAX INVOICE</h2><pre>{from}</pre></div><div className="inv-meta"><b>{no}</b><span>{new Date().toLocaleDateString('en-IN')}</span></div></div>
      <div className="inv-to"><small>BILL TO</small><pre>{to}</pre></div>
      <table className="tbl"><thead><tr><th>Description</th><th className="num">Qty</th><th className="num">Rate</th><th className="num">Amount</th><th className="no-print" /></tr></thead><tbody>
        {lines.map((l, i) => <tr key={i}><td><input className="cell" value={l.d} onChange={e => upd(i, 'd', e.target.value)} /></td><td className="num"><input className="cell num" type="number" value={l.q} onChange={e => upd(i, 'q', e.target.value)} /></td><td className="num"><input className="cell num" type="number" value={l.r} onChange={e => upd(i, 'r', e.target.value)} /></td><td className="num">{inr(l.q * l.r)}</td><td className="no-print"><button className="icon-btn" onClick={() => setLines(ls => ls.filter((_, j) => j !== i))} aria-label="Remove line">×</button></td></tr>)}
      </tbody></table>
      <button className="link no-print" onClick={() => setLines(ls => [...ls, { d: '', q: 1, r: 0 }])}>+ Add line</button>
      <div className="inv-totals"><div><span>Subtotal</span><b>{inr(sub)}</b></div>{inter ? <div><span>IGST {rate}%</span><b>{inr(gst)}</b></div> : <><div><span>CGST {rate / 2}%</span><b>{inr(gst / 2)}</b></div><div><span>SGST {rate / 2}%</span><b>{inr(gst / 2)}</b></div></>}<div className="grand"><span>Total</span><b>{inr(sub + gst)}</b></div></div>
      {upi && <p className="small">Pay via UPI: <b>{upi}</b></p>}
    </div>
    <div className="form-actions no-print"><span className="muted small">Want the full spreadsheet with a payment tracker? It’s in the Creator GST Invoice Kit.</span><button className="btn btn-primary" onClick={() => window.print()}><Printer size={16} />Print / save as PDF</button></div>
  </div>;
}

const LIMITS = [{ k: 'Instagram caption', n: 2200, fold: 125 }, { k: 'Instagram bio', n: 150 }, { k: 'YouTube title', n: 100, fold: 60 }, { k: 'YouTube description', n: 5000, fold: 157 }, { k: 'X post', n: 280 }, { k: 'LinkedIn post', n: 3000, fold: 210 }, { k: 'Threads', n: 500 }];
function Caption() {
  const [txt, setTxt] = useState('');
  const tags = (txt.match(/#[\p{L}\p{N}_]+/gu) || []).length; const words = txt.trim() ? txt.trim().split(/\s+/).length : 0;
  return <div className="calc">
    <label className="form">Paste your caption<textarea rows={7} value={txt} onChange={e => setTxt(e.target.value)} placeholder="Your hook goes in the first line…" /></label>
    <p className="muted small">{txt.length} characters · {words} words · {tags} hashtags{tags > 30 ? ' — Instagram allows max 30' : ''} · ~{Math.max(1, Math.round(words / 200 * 60))}s to read</p>
    <div className="limits">{LIMITS.map(l => { const pct = Math.min(100, txt.length / l.n * 100); return <div key={l.k} className={'limit' + (txt.length > l.n ? ' over' : '')}><span>{l.k}</span><i><em style={{ width: pct + '%' }} />{l.fold && <u style={{ left: Math.min(100, l.fold / l.n * 100) + '%' }} title="Truncation point" />}</i><b>{txt.length}/{l.n}</b></div> })}</div>
    {txt && <div className="preview-fold"><small>Shown before “…more” on Instagram:</small><p>{txt.slice(0, 125)}{txt.length > 125 && <span className="muted">… more</span>}</p></div>}
  </div>;
}

const SETS: Record<string, string[]> = {
  'Video editing': ['#videoediting', '#premierepro', '#davinciresolve', '#colorgrading', '#editorsofinstagram', '#filmmaking', '#cinematography', '#lut', '#reelsindia', '#videoeditor'],
  'Design': ['#graphicdesign', '#designinspiration', '#brandidentity', '#typography', '#figma', '#uidesign', '#designindia', '#logodesign', '#dribbble', '#behance'],
  'Freelancing India': ['#freelancerindia', '#freelancing', '#gst', '#smallbusinessindia', '#solopreneur', '#creatoreconomy', '#workfromhome', '#indianstartup', '#clientwork', '#sidehustle'],
  'Content creators': ['#contentcreator', '#creatortips', '#instagramgrowth', '#youtubeindia', '#reelsinstagram', '#socialmediatips', '#contentstrategy', '#creatorlife', '#personalbrand', '#growthhacks'],
  'Festive': ['#diwali', '#happydiwali', '#holi', '#festivevibes', '#navratri', '#eidmubarak', '#onam', '#pongal', '#indianfestival', '#festiveseason'],
  'AI tools': ['#aitools', '#chatgpt', '#promptengineering', '#aiart', '#automation', '#nocode', '#productivity', '#aiforcreators', '#genai', '#workflow'],
};
function Hashtags() {
  const [pick, setPick] = useState<string[]>(['Content creators']); const [copied, setCopied] = useState(false);
  const out = useMemo(() => Array.from(new Set(pick.flatMap(p => SETS[p]))).slice(0, 30).join(' '), [pick]);
  return <div className="calc">
    <div className="chips">{Object.keys(SETS).map(k => <button key={k} className={'chip' + (pick.includes(k) ? ' on' : '')} onClick={() => setPick(p => p.includes(k) ? p.filter(x => x !== k) : [...p, k])}>{k}</button>)}</div>
    <textarea className="tags-out" rows={4} readOnly value={out} />
    <div className="form-actions"><span className="muted small">{out.split(' ').filter(Boolean).length} tags (Instagram max 30). Mix 3–5 niche tags with 2–3 broad ones for best reach.</span><button className="btn btn-primary btn-sm" onClick={() => navigator.clipboard.writeText(out).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })}>{copied ? <Check size={15} /> : <Copy size={15} />}Copy</button></div>
  </div>;
}

const SIZES = [['Instagram post (portrait)', '1080 × 1350', '4:5'], ['Instagram square', '1080 × 1080', '1:1'], ['Reels / Stories / Shorts', '1080 × 1920', '9:16 · keep text 250px from top & 340px from bottom'],
  ['YouTube thumbnail', '1280 × 720', '16:9 · under 2 MB · avoid bottom-right (timestamp)'], ['YouTube banner', '2560 × 1440', 'Safe area 1546 × 423 centred'], ['LinkedIn post', '1200 × 1500', '4:5'],
  ['LinkedIn banner', '1584 × 396', '4:1'], ['X post image', '1600 × 900', '16:9'], ['WhatsApp status', '1080 × 1920', '9:16'], ['Podcast cover', '3000 × 3000', '1:1 · JPG/PNG']];
function Safe() {
  return <div><table className="tbl"><thead><tr><th>Format</th><th>Pixels</th><th>Ratio & safe zone</th></tr></thead><tbody>{SIZES.map(s => <tr key={s[0]}><td><strong>{s[0]}</strong></td><td><code>{s[1]}</code></td><td className="muted small">{s[2]}</td></tr>)}</tbody></table>
    <div className="safe-demo"><div className="phone"><span className="zone top">UI · 250px</span><span className="zone bottom">Caption & buttons · 340px</span><span className="zone mid">Safe for text</span></div><p className="muted small">9:16 safe zone for Reels, Shorts and Stories.</p></div></div>;
}
