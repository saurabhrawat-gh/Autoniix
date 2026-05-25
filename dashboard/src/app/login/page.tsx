'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi, legacyLogin } from '@/lib/api-v2';
import { ThemeToggle } from '@/lib/theme';
import { Button, Input, Label, Card } from '@/lib/ui';

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
      .then(m => setMode(!m.v2_enabled && m.legacy_enabled ? 'legacy' : 'v2'))
      .catch(() => setMode('v2'));
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
        const data = await authApi.login(email, password);
        router.push((data as any).setup_required ? '/onboarding' : '/dashboard');
      } else {
        const data = await authApi.login(email, password, mfaCode);
        router.push((data as any).setup_required ? '/onboarding' : '/dashboard');
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
          <Card variant="elevated" padding="xl">
            <form onSubmit={handleLegacyLogin} className="space-y-8">
              <Logo />

              {error && (
                <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
              )}

              <div className="space-y-2">
                <Label htmlFor="legacy-pw">Password</Label>
                <Input
                  id="legacy-pw"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  autoFocus
                />
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={!password}
                loading={loading}
              >
                {loading ? 'Signing in…' : 'Sign In'}
              </Button>
            </form>
          </Card>
        ) : (
          <Card variant="elevated" padding="xl">
            <form onSubmit={handleV2Login} className="space-y-6">
              <Logo />

              {error && (
                <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
              )}

              {step === 'credentials' ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="email" required>Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      autoFocus
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password" required>Password</Label>
                      <Link href="/forgot-password" className="text-xs text-accent hover:underline">
                        Forgot password?
                      </Link>
                    </div>
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                    />
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    className="w-full"
                    disabled={!email || !password}
                    loading={loading}
                  >
                    {loading ? 'Signing in…' : 'Sign In'}
                  </Button>

                  <p className="text-center text-xs text-content-tertiary">
                    No account?{' '}
                    <Link href="/register" className="text-accent hover:underline">Create one</Link>
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-content-secondary text-center">
                    Enter the 6-digit code from your authenticator app.
                  </p>

                  <div className="space-y-2">
                    <Label htmlFor="mfa" required>MFA Code</Label>
                    <Input
                      id="mfa"
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]{6}"
                      maxLength={6}
                      value={mfaCode}
                      onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="000000"
                      autoFocus
                      required
                      className="text-center tracking-widest text-lg font-mono"
                    />
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    className="w-full"
                    disabled={mfaCode.length !== 6}
                    loading={loading}
                  >
                    {loading ? 'Verifying…' : 'Verify'}
                  </Button>

                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-full"
                    onClick={() => { setStep('credentials'); setMfaCode(''); setError(''); }}
                  >
                    ← Back
                  </Button>
                </>
              )}
            </form>
          </Card>
        )}

        <p className="text-center text-xs text-content-tertiary mt-6">
          YouTube Automation Dashboard v1.0
        </p>
      </div>
    </div>
  );
}
