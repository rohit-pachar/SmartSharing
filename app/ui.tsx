'use client';
import Link from 'next/link';
import { useState } from 'react';
import { Link2, Search, Wallet, LayoutDashboard, Library, LogOut, Plus, ChevronDown, User as UserIcon, Menu, X } from 'lucide-react';
import { useAuth } from './lib/auth';
import { credits, type Asset, bytes } from './lib/market';
import { mediaUrl } from './lib/api';

export function Header({ active }: { active?: 'discover' | 'library' | 'studio' }) {
  const { user, wallet, ready, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href="/" className="brand" aria-label="SmartSharing home"><Link2 />smartsharing<span>.in</span></Link>
        <form className="header-search" action="/" role="search"><Search size={16} /><input name="q" placeholder="Search templates, LUTs, invoices…" aria-label="Search" /></form>
        <nav className={'app-nav' + (mobile ? ' open' : '')} aria-label="Main">
          <Link className={active === 'discover' ? 'on' : ''} href="/">Discover</Link>
          {user && <Link className={active === 'library' ? 'on' : ''} href="/library">Library</Link>}
          {user && <Link className={active === 'studio' ? 'on' : ''} href="/studio">Studio</Link>}
          <Link href="/research">Research</Link>
        </nav>
        <div className="header-actions">
          {!ready ? <span className="header-skel" /> : user ? <>
            <Link href="/studio?tab=wallet" className="wallet-chip" title="Wallet"><Wallet size={15} />{wallet ? credits(wallet.balance) : '—'}</Link>
            <Link href="/studio?tab=listings&new=1" className="btn btn-primary btn-sm hide-sm"><Plus size={15} />New listing</Link>
            <div className="menu">
              <button className="avatar-btn" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label="Account menu"><span className="av">{user.full_name.split(' ').map(p => p[0]).slice(0, 2).join('')}</span><ChevronDown size={14} /></button>
              {open && <div className="menu-pop" onMouseLeave={() => setOpen(false)}>
                <div className="menu-head"><strong>{user.full_name}</strong><small>@{user.handle}</small></div>
                <Link href={`/u/${user.handle}`}><UserIcon size={15} />Public profile</Link>
                <Link href="/studio"><LayoutDashboard size={15} />Creator studio</Link>
                <Link href="/library"><Library size={15} />My library</Link>
                <Link href="/studio?tab=wallet"><Wallet size={15} />Wallet</Link>
                <button onClick={() => { signOut(); window.location.href = '/' }}><LogOut size={15} />Log out</button>
              </div>}
            </div>
          </> : <>
            <Link href="/login" className="btn btn-ghost btn-sm">Log in</Link>
            <Link href="/signup" className="btn btn-primary btn-sm">Start selling</Link>
          </>}
          <button className="mobile-toggle" onClick={() => setMobile(m => !m)} aria-label="Menu">{mobile ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
    </header>
  );
}

export function AssetCard({ a }: { a: Asset }) {
  return (
    <Link href={`/p/${a.id}`} className="card">
      <div className="card-art"><img src={mediaUrl(a.image)} alt="" loading="lazy" />
        {a.is_official && <span className="pill pill-official">SmartSharing Studio</span>}
        {a.is_demo && <span className="pill pill-demo">Demo</span>}
        {a.price === 0 && <span className="pill pill-free">Free</span>}
      </div>
      <div className="card-body">
        <p className="card-cat">{a.category}</p>
        <h3>{a.name}</h3>
        <p className="card-meta">{a.format}{a.total_size ? ` · ${bytes(a.total_size)}` : ''}</p>
        <div className="card-foot"><span className="card-creator"><span className="av av-sm">{a.initials}</span>{a.creator}</span><strong>{a.price === 0 ? 'Free' : credits(a.price)}</strong></div>
      </div>
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="app-footer"><div className="app-footer-inner">
      <Link className="brand" href="/"><Link2 />smartsharing<span>.in</span></Link>
      <div className="foot-cols">
        <div><strong>Marketplace</strong><Link href="/">Discover</Link><Link href="/?source=official">Studio originals</Link><Link href="/?price=free">Free resources</Link></div>
        <div><strong>Creators</strong><Link href="/signup">Start selling</Link><Link href="/studio">Creator studio</Link><Link href="/studio?tab=developers">API & webhooks</Link></div>
        <div><strong>Company</strong><Link href="/research">Research</Link><a href="mailto:hello@smartsharing.in">hello@smartsharing.in</a></div>
      </div>
      <p className="foot-note">Early access · Prices in SmartSharing credits.</p>
    </div></footer>
  );
}

export function Empty({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <div className="empty"><div className="empty-ic">{icon}</div><h3>{title}</h3><p>{text}</p>{action}</div>;
}
