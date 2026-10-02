'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ArrowRight, Check, Link2, Loader2, Eye, EyeOff } from 'lucide-react';
import { api, errMsg } from './lib/api';
import { useAuth } from './lib/auth';

const PERKS = ['Sell templates, LUTs, presets and AI workflows', 'Keep 88% of every sale — paid to your wallet instantly',
  'Discount codes, affiliate links and licence keys built in', 'Sale alerts in Discord, Slack, Telegram or any webhook'];

export function AuthScreen({ mode }: { mode: 'login' | 'signup' }) {
  const { user, ready, signIn } = useAuth();
  const params = useSearchParams();
  const next = params.get('next') || (mode === 'signup' ? '/studio?welcome=1' : '/studio');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [show, setShow] = useState(false);
  useEffect(() => { if (ready && user) window.location.replace(next.startsWith('/') && !next.startsWith('//') ? next : '/studio') }, [ready, user, next]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setErr(''); setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      const email = String(f.get('email')).trim(), pw = String(f.get('password'));
      const r = mode === 'login' ? await api.login(email, pw) : await api.register(String(f.get('name')).trim(), email, pw);
      await signIn(r.access_token);
    } catch (x) { setErr(errMsg(x)); setBusy(false) }
  }

  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <Link href="/" className="brand"><Link2 />smartsharing<span>.in</span></Link>
        <div className="auth-pitch">
          <p className="eyebrow">THE CREATOR-TO-CREATOR EXCHANGE</p>
          <h1>{mode === 'signup' ? <>Your work.<br /><span>Your storefront.</span></> : <>Welcome<br /><span>back.</span></>}</h1>
          <ul>{PERKS.map(p => <li key={p}><Check size={16} />{p}</li>)}</ul>
        </div>
        <div className="auth-quote"><p>“Upload once, get paid every time someone uses it. The studio shows me exactly which post sent each sale.”</p><small>What we’re building for · early access</small></div>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <h2>{mode === 'login' ? 'Log in' : 'Create your account'}</h2>
          <p className="muted">{mode === 'login' ? 'Pick up where you left off.' : 'Free forever. 1,000 welcome credits to try the marketplace.'}</p>
          <form onSubmit={submit} className="form">
            {mode === 'signup' && <label>Full name<input name="name" required minLength={2} maxLength={80} autoComplete="name" placeholder="Priya Sharma" /></label>}
            <label>Email<input name="email" type="email" required autoComplete="email" placeholder="you@studio.in" /></label>
            <label>Password<span className="pw"><input name="password" type={show ? 'text' : 'password'} required minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} placeholder="At least 8 characters" />
              <button type="button" onClick={() => setShow(s => !s)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? <EyeOff size={16} /> : <Eye size={16} />}</button></span></label>
            {err && <p className="form-error" role="alert">{err}</p>}
            <button className="btn btn-primary btn-lg full" disabled={busy}>{busy ? <Loader2 className="spin" size={18} /> : <>{mode === 'login' ? 'Log in' : 'Create account'}<ArrowRight size={18} /></>}</button>
          </form>
          <p className="auth-switch">{mode === 'login' ? <>New to SmartSharing? <Link href={`/signup${params.get('next') ? `?next=${encodeURIComponent(params.get('next')!)}` : ''}`}>Create an account</Link></> : <>Already have an account? <Link href={`/login${params.get('next') ? `?next=${encodeURIComponent(params.get('next')!)}` : ''}`}>Log in</Link></>}</p>
          {mode === 'signup' && <p className="fine">By creating an account you agree to list only work you own or have rights to license.</p>}
        </div>
      </main>
    </div>
  );
}
