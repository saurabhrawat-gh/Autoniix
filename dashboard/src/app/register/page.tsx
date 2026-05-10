'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi, setV2Tokens } from '@/lib/api-v2';

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await authApi.register(email, password, name || undefined);
      const r = await authApi.login(email, password);
      setV2Tokens(r.access_token, r.refresh_token);
      router.push('/dashboard');
    } catch (e: any) {
      setErr(e?.message || 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 p-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 space-y-4">
        <h1 className="text-xl font-semibold">Create account</h1>
        <p className="text-xs opacity-70">The first account becomes Owner. Subsequent accounts are Viewer until promoted.</p>
        <label className="block">
          <div className="text-xs uppercase opacity-70 mb-1">Email</div>
          <input className="w-full px-3 py-2 rounded-md bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-sm" type="email" required value={email} onChange={e => setEmail(e.target.value)} />
        </label>
        <label className="block">
          <div className="text-xs uppercase opacity-70 mb-1">Display name (optional)</div>
          <input className="w-full px-3 py-2 rounded-md bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-sm" value={name} onChange={e => setName(e.target.value)} />
        </label>
        <label className="block">
          <div className="text-xs uppercase opacity-70 mb-1">Password</div>
          <input className="w-full px-3 py-2 rounded-md bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-sm" type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} />
        </label>
        {err && <div className="text-sm text-red-500">{err}</div>}
        <button disabled={busy} className="w-full px-3 py-2 rounded-md bg-indigo-500 text-white text-sm hover:bg-indigo-600 disabled:opacity-40">
          {busy ? 'Creating…' : 'Create account'}
        </button>
        <div className="text-xs text-center opacity-70">
          Have an account? <Link href="/login" className="underline">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
