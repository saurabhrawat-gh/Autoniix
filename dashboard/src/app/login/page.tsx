'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi, setV2Tokens, legacyLogin } from '@/lib/api-v2';
import { ThemeToggle } from '@/lib/theme';

type AuthMode = 'loading' | 'legacy' | 'v2';
type Step = 'credentials' | 'mfa';

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<AuthMode>('loading');
  const [step, setStep] = useState<Step>('credentials');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authApi.mode()
      .then(m => setMode(m.v2_enabled ? 'v2' : 'legacy'))
      .catch(() => setMode('legacy'));
  }, []);

  async function handleLegacyLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await legacyLogin(password);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleV2Login(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (step === 'credentials') {
        const res = await authApi.login(email, password);
        setV2Tokens(res.access_token, res.refresh_token);
        router.push('/dashboard');
      } else {
        const res = await authApi.login(email, password, mfaCode);
        setV2Tokens(res.access_token, res.refresh_token);
        router.push('/dashboard');
      }
    } catch (err: any) {
      const msg: string = err.message || 'Login failed';
      if (msg.toLowerCase().includes('mfa')) {
        setStep('mfa');
        setError('');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  const Logo = () => (
    <div className="flex flex-col items-center gap-3">
      <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-accent">
          <path d="M23 7l-7 5 7 5V7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="1" y="5" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="2"/>
        </svg>
      </div>
      <div className="text-center">
        <h1 className="text-xl font-semibold text-content-primary">YouTube Automation</h1>
        <p className="text-content-tertiary text-sm mt-1">Sign in to your dashboard</p>
      </div>
    </div>
  );

  const Spinner = () => (
    <span className="flex items-center justify-center gap-2">
      <span className="w-4 h-4 border-2 border-content-inverse/30 border-t-content-inverse rounded-full animate-spin" />
      Signing in…
    </span>
  );

  if (mode === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <span className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen relative">
      <div className="absolute top-5 right-5"><ThemeToggle /></div>

      <div className="w-full max-w-md px-6">
        {mode === 'legacy' ? (
          <form onSubmit={handleLegacyLogin} className="card-elevated p-8 space-y-8">
            <Logo />

            {error && (
              <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
            )}

            <div className="space-y-2">
              <label className="block text-sm font-medium text-content-primary">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter admin password"
                autoFocus
                className="!py-3"
              />
            </div>

            <button type="submit" disabled={loading || !password} className="w-full btn-primary !py-3">
              {loading ? <Spinner /> : 'Sign In'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleV2Login} className="card-elevated p-8 space-y-6">
            <Logo />

            {error && (
              <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
            )}

            {step === 'credentials' ? (
              <>
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-content-primary">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    autoFocus
                    required
                    className="!py-3"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-content-primary">Password</label>
                    <Link href="/forgot-password" className="text-xs text-accent hover:underline">
                      Forgot password?
                    </Link>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="!py-3"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !email || !password}
                  className="w-full btn-primary !py-3"
                >
                  {loading ? <Spinner /> : 'Sign In'}
                </button>

                <p className="text-center text-xs text-content-tertiary">
                  No account?{' '}
                  <Link href="/register" className="text-accent hover:underline">Create one</Link>
                </p>
              </>
            ) : (
              <>
                <div className="space-y-1">
                  <p className="text-sm text-content-secondary text-center">
                    Enter the 6-digit code from your authenticator app.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="block text-sm font-medium text-content-primary">MFA Code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    value={mfaCode}
                    onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="000000"
                    autoFocus
                    required
                    className="!py-3 text-center tracking-widest text-lg font-mono"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || mfaCode.length !== 6}
                  className="w-full btn-primary !py-3"
                >
                  {loading ? <Spinner /> : 'Verify'}
                </button>

                <button
                  type="button"
                  onClick={() => { setStep('credentials'); setMfaCode(''); setError(''); }}
                  className="w-full text-xs text-content-tertiary hover:text-content-secondary mt-1"
                >
                  ← Back
                </button>
              </>
            )}
          </form>
        )}

        <p className="text-center text-xs text-content-tertiary mt-6">
          YouTube Automation Dashboard v1.0
        </p>
      </div>
    </div>
  );
}
