'use client';
import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ArrowRight, Search, Sparkles, Zap, KeyRound, Webhook, BadgePercent, BarChart3, Download } from 'lucide-react';
import { api, type Profile } from './lib/api';
import { CATEGORIES, type Asset } from './lib/market';
import { AssetCard, Footer, Header, Empty } from './ui';
import { mediaUrl } from './lib/api';

const TOOLS = [
  { icon: <Download size={18} />, t: 'Instant delivery', d: 'Buyers download from their library the second they pay.' },
  { icon: <KeyRound size={18} />, t: 'Licence keys', d: 'Every sale gets a key your software can verify via API.' },
  { icon: <BadgePercent size={18} />, t: 'Discounts & affiliates', d: 'Launch codes, limited-use promos and referral commissions.' },
  { icon: <Webhook size={18} />, t: 'Integrations', d: 'Sale alerts to Discord, Slack, Telegram, Zapier, Make, n8n.' },
  { icon: <BarChart3 size={18} />, t: 'Analytics', d: 'Views, conversion and which link sent each sale.' },
  { icon: <Zap size={18} />, t: 'Creator API', d: 'Manage listings and read sales with your own API keys.' },
];

function Market() {
  const params = useSearchParams();
  const router = useRouter();
  const [q, setQ] = useState(params.get('q') || '');
  const [cat, setCat] = useState('All');
  const [source, setSource] = useState(params.get('source') || '');
  const [sort, setSort] = useState('popular');
  const [items, setItems] = useState<Asset[] | null>(null);
  const [official, setOfficial] = useState<Asset[]>([]);
  const [studio, setStudio] = useState<Profile | null>(null);
  const priceFree = params.get('price') === 'free';

  useEffect(() => { api.assets({ source: 'official', sort: 'popular', limit: 12 }).then(r => setOfficial(r.items)).catch(() => {}); api.profile('smartsharing.studio').then(setStudio).catch(() => {}) }, []);
  useEffect(() => { setQ(params.get('q') || ''); setSource(params.get('source') || '') }, [params]);
  useEffect(() => {
    const t = setTimeout(() => {
      api.assets({ q, category: cat === 'All' ? '' : cat, sort, source, limit: 60 })
        .then(r => setItems(priceFree ? r.items.filter(a => a.price === 0) : r.items)).catch(() => setItems([]));
    }, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [q, cat, sort, source, priceFree]);

  const browsing = !!(q || cat !== 'All' || source || priceFree);
  const free = official.filter(a => a.price === 0);

  return (
    <>
      <Header active="discover" />
      <main className="page">
        {!browsing && <section className="home-hero">
          <div className="home-hero-copy">
            <p className="eyebrow">THE CREATOR-TO-CREATOR EXCHANGE</p>
            <h1>Tools and assets<br />that <span>ship your work.</span></h1>
            <p className="lead">LUTs, templates, invoice kits and AI workflows made for Indian creators — downloadable the moment you buy. Or open your own storefront in two minutes.</p>
            <form className="hero-search" onSubmit={e => { e.preventDefault(); router.push(`/?q=${encodeURIComponent(q)}`) }}><Search size={18} /><input value={q} onChange={e => setQ(e.target.value)} placeholder="Try “LUT”, “GST invoice”, “Diwali”" aria-label="Search" /><button className="btn btn-primary">Search</button></form>
            <div className="hero-links"><span className="muted">Popular:</span>{['LUT', 'GST invoice', 'Diwali', 'Carousel'].map(t => <Link key={t} className="chip" href={`/?q=${encodeURIComponent(t)}`}>{t}</Link>)}</div>
          </div>
          <div className="home-hero-art">{official.slice(0, 5).map((a, i) => <Link key={a.id} href={`/p/${a.id}`} className={`collage c${i}`}><img src={mediaUrl(a.image)} alt={a.name} /><span>{a.name}<b>{a.price === 0 ? 'Free' : `${a.price} cr`}</b></span></Link>)}</div>
        </section>}

        {!browsing && official.length > 0 && <section className="shelf">
          <div className="shelf-head"><div><p className="eyebrow">MADE BY SMARTSHARING STUDIO</p><h2>Start with the essentials</h2></div><Link href="/?source=official" className="link">See all {studio ? studio.assets.length : ''} <ArrowRight size={14} /></Link></div>
          <div className="grid">{official.filter(a => a.price > 0).slice(0, 8).map(a => <AssetCard key={a.id} a={a} />)}</div>
        </section>}

        {!browsing && free.length > 0 && <section className="shelf free-shelf">
          <div className="shelf-head"><div><p className="eyebrow">FREE</p><h2>Free for every creator</h2></div></div>
          <div className="grid grid-2">{free.map(a => <AssetCard key={a.id} a={a} />)}</div>
        </section>}

        {!browsing && <section className="tools-band">
          <div className="tools-intro"><p className="eyebrow">FOR CREATORS</p><h2>A storefront with the tools already plugged in.</h2><p className="muted">Everything you’d normally stitch together from five apps — in one studio you open every day.</p><Link href="/signup" className="btn btn-primary">Open your studio <ArrowRight size={16} /></Link></div>
          <div className="tools-grid">{TOOLS.map(t => <div className="tool" key={t.t}><span className="tool-ic">{t.icon}</span><strong>{t.t}</strong><p>{t.d}</p></div>)}</div>
        </section>}

        <section className="shelf" id="browse">
          <div className="shelf-head"><div><p className="eyebrow">{browsing ? 'RESULTS' : 'BROWSE'}</p><h2>{q ? `“${q}”` : source === 'official' ? 'SmartSharing Studio originals' : priceFree ? 'Free resources' : 'All listings'}</h2></div>
            <select className="select" value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort"><option value="popular">Most popular</option><option value="new">Newest</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option></select></div>
          <div className="chips">
            {CATEGORIES.map(c => <button key={c} className={'chip' + (cat === c ? ' on' : '')} onClick={() => setCat(c)}>{c}</button>)}
            <span className="chip-sep" />
            <button className={'chip' + (source === 'official' ? ' on' : '')} onClick={() => setSource(s => s === 'official' ? '' : 'official')}><Sparkles size={13} />Studio originals</button>
            <button className={'chip' + (source === 'community' ? ' on' : '')} onClick={() => setSource(s => s === 'community' ? '' : 'community')}>Community</button>
            {browsing && <button className="chip chip-clear" onClick={() => { setQ(''); setCat('All'); setSource(''); router.push('/') }}>Clear</button>}
          </div>
          {items === null ? <div className="grid">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="card skel" />)}</div>
            : items.length === 0 ? <Empty icon={<Search size={22} />} title="Nothing matches yet" text="Try another word or category — or be the first to list it." action={<Link href="/signup" className="btn btn-ghost">List an asset</Link>} />
              : <div className="grid">{items.map(a => <AssetCard key={a.id} a={a} />)}</div>}
        </section>
      </main>
      <Footer />
    </>
  );
}

export default function Home() { return <Suspense><Market /></Suspense> }
