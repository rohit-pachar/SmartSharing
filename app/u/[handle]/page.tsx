'use client';
import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { BadgeCheck, Globe, MapPin } from 'lucide-react';
import { api, type Profile } from '../../lib/api';
import { AssetCard, Empty, Footer, Header } from '../../ui';

export default function CreatorPage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = use(params);
  const [p, setP] = useState<Profile | null>(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => { api.profile(handle).then(setP).catch(() => setMissing(true)) }, [handle]);
  if (missing) return <><Header /><main className="page narrow"><h1>Creator not found</h1><Link href="/" className="btn btn-ghost">Back to marketplace</Link></main></>;
  if (!p) return <><Header /><main className="page"><div className="skel-block" /></main></>;
  const initials = p.full_name.split(' ').map(x => x[0]).slice(0, 2).join('');
  const published = p.assets;
  return (
    <>
      <Header />
      <main className="page">
        <section className="profile-head">
          <span className="av av-xl">{initials}</span>
          <div>
            <h1>{p.full_name}{p.is_official && <BadgeCheck size={22} className="verified" aria-label="Official" />}</h1>
            <p className="muted">@{p.handle}{p.role ? ` · ${p.role}` : ''}</p>
            {p.bio && <p className="bio">{p.bio}</p>}
            <div className="profile-meta">{p.city && <span><MapPin size={14} />{p.city}</span>}{p.website && <a href={p.website} target="_blank" rel="noreferrer"><Globe size={14} />{p.website.replace(/^https?:\/\//, '')}</a>}
              {Object.entries(p.links || {}).map(([k, v]) => <a key={k} href={v} target="_blank" rel="noreferrer">{k}</a>)}
              <span>{published.length} listings</span>{p.sales > 0 && <span>{p.sales} sales</span>}{p.is_demo && <span className="pill pill-demo inline">Demo account</span>}</div>
          </div>
        </section>
        {published.length === 0 ? <Empty icon={<Globe size={22} />} title="No listings yet" text="Check back soon." /> : <div className="grid">{published.map(a => <AssetCard key={a.id} a={a} />)}</div>}
      </main>
      <Footer />
    </>
  );
}
