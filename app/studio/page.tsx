'use client';
import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { LayoutDashboard, Package, Receipt, Megaphone, Wrench, Plug, Code2, Wallet as WalletIcon, Settings, Sparkles } from 'lucide-react';
import { useAuth, useRequireAuth } from '../lib/auth';
import { Header } from '../ui';
import { OverviewTab } from './tabs/overview';
import { ListingsTab } from './tabs/listings';
import { SalesTab } from './tabs/sales';
import { MarketingTab } from './tabs/marketing';
import { ToolkitTab } from './tabs/toolkit';
import { IntegrationsTab } from './tabs/integrations';
import { DevelopersTab } from './tabs/developers';
import { WalletTab } from './tabs/wallet';
import { SettingsTab } from './tabs/settings';

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'listings', label: 'Listings', icon: Package },
  { id: 'sales', label: 'Sales & customers', icon: Receipt },
  { id: 'marketing', label: 'Marketing', icon: Megaphone },
  { id: 'toolkit', label: 'Creator toolkit', icon: Wrench },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'developers', label: 'Developers', icon: Code2 },
  { id: 'wallet', label: 'Wallet', icon: WalletIcon },
  { id: 'settings', label: 'Profile & settings', icon: Settings },
] as const;

function Studio() {
  const ok = useRequireAuth();
  const { user } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const tab = (params.get('tab') || 'overview') as (typeof TABS)[number]['id'];
  const go = (t: string, extra = '') => router.push(`/studio?tab=${t}${extra}`, { scroll: false });
  const [welcome, setWelcome] = useState(false);
  useEffect(() => { if (params.get('welcome')) setWelcome(true) }, [params]);
  if (!ok || !user) return <><Header active="studio" /><main className="page"><div className="skel-block" /></main></>;
  return (
    <>
      <Header active="studio" />
      <div className="studio">
        <aside className="studio-nav">
          <div className="studio-me"><span className="av">{user.full_name.split(' ').map(p => p[0]).slice(0, 2).join('')}</span><div><strong>{user.full_name}</strong><Link href={`/u/${user.handle}`}>@{user.handle}</Link></div></div>
          <nav>{TABS.map(t => <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => go(t.id)}><t.icon size={16} />{t.label}</button>)}</nav>
        </aside>
        <main className="studio-main">
          {welcome && <div className="welcome"><Sparkles size={18} /><div><strong>Welcome to your studio, {user.full_name.split(' ')[0]}.</strong><p>You have 1,000 welcome credits. Grab the free Content Calendar, then create your first listing — it takes two minutes.</p></div>
            <div className="welcome-actions"><Link className="btn btn-ghost btn-sm" href="/?price=free">Free resources</Link><button className="btn btn-primary btn-sm" onClick={() => { setWelcome(false); go('listings', '&new=1') }}>Create a listing</button><button className="x" onClick={() => setWelcome(false)} aria-label="Dismiss">×</button></div></div>}
          {tab === 'overview' && <OverviewTab go={go} />}
          {tab === 'listings' && <ListingsTab startNew={params.get('new') === '1'} />}
          {tab === 'sales' && <SalesTab />}
          {tab === 'marketing' && <MarketingTab />}
          {tab === 'toolkit' && <ToolkitTab />}
          {tab === 'integrations' && <IntegrationsTab />}
          {tab === 'developers' && <DevelopersTab />}
          {tab === 'wallet' && <WalletTab />}
          {tab === 'settings' && <SettingsTab />}
        </main>
      </div>
    </>
  );
}

export default function Page() { return <Suspense><Studio /></Suspense> }
