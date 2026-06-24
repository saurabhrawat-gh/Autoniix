'use client';

import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi, legacyLogin } from '@/lib/api-v2';
import { ThemeToggle } from '@/lib/theme';
import { Button, Input, Card } from '@/lib/ui';
import { FormField } from '@/lib/components/FormField';
import {
  loginSchema, mfaSchema, legacyLoginSchema,
  type LoginValues, type MfaValues, type LegacyLoginValues,
} from '@/lib/schemas/auth';

type AuthMode = 'loading' | 'legacy' | 'v2';
type Step = 'credentials' | 'mfa';

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<AuthMode>('loading');
  const [step, setStep] = useState<Step>('credentials');
  const [serverError, setServerError] = useState('');

  const credForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });
  const mfaForm = useForm<MfaValues>({ resolver: zodResolver(mfaSchema) });
  const legacyForm = useForm<LegacyLoginValues>({ resolver: zodResolver(legacyLoginSchema) });

  useEffect(() => {
    authApi.mode()
      .then(m => setMode(!m.v2_enabled && m.legacy_enabled ? 'legacy' : 'v2'))
      .catch(() => setMode('v2'));
    if (typeof window !== 'undefined') {
      const r = new URLSearchParams(window.location.search).get('reason');
      if (r === 'no_workspace_access') {
        setServerError('Your workspace access was revoked. Contact your superadmin to be re-invited.');
      }
    }
  }, []);

  async function handleLegacyLogin(values: LegacyLoginValues) {
    setServerError('');
    try {
      await legacyLogin(values.password);
      router.push('/dashboard');
    } catch (err: any) {
      setServerError(err.message || 'Login failed');
    }
  }

  async function handleCredentials(values: LoginValues) {
    setServerError('');
    try {
      const data = await authApi.login(values.email, values.password);
      router.push((data as any).setup_required ? '/onboarding' : '/dashboard');
    } catch (err: any) {
      const msg: string = err.message || 'Login failed';
      if (msg.toLowerCase().includes('mfa')) { setStep('mfa'); }
      else { setServerError(msg); }
    }
  }

  async function handleMfa(values: MfaValues) {
    setServerError('');
    const { email, password } = credForm.getValues();
    try {
      const data = await authApi.login(email, password, values.code);
      router.push((data as any).setup_required ? '/onboarding' : '/dashboard');
    } catch (err: any) {
      setServerError(err.message || 'Verification failed');
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
            <form onSubmit={legacyForm.handleSubmit(handleLegacyLogin)} className="space-y-8">
              <Logo />
              {serverError && (
                <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
              )}
              <FormField id="legacy-pw" label="Password" error={legacyForm.formState.errors.password}>
                <Input
                  id="legacy-pw"
                  type="password"
                  placeholder="Enter admin password"
                  autoFocus
                  {...legacyForm.register('password')}
                />
              </FormField>
              <Button type="submit" size="lg" className="w-full" loading={legacyForm.formState.isSubmitting}>
                {legacyForm.formState.isSubmitting ? 'Signing in…' : 'Sign In'}
              </Button>
            </form>
          </Card>
        ) : (
          <Card variant="elevated" padding="xl">
            {step === 'credentials' ? (
              <form onSubmit={credForm.handleSubmit(handleCredentials)} className="space-y-6">
                <Logo />
                {serverError && (
                  <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
                )}
                <FormField id="email" label="Email" required error={credForm.formState.errors.email}>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    autoFocus
                    {...credForm.register('email')}
                  />
                </FormField>
                <FormField id="password" label="Password" required error={credForm.formState.errors.password}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span />
                    <Link href="/forgot-password" className="text-xs text-accent hover:underline">Forgot password?</Link>
                  </div>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    {...credForm.register('password')}
                  />
                </FormField>
                <Button type="submit" size="lg" className="w-full" loading={credForm.formState.isSubmitting}>
                  {credForm.formState.isSubmitting ? 'Signing in…' : 'Sign In'}
                </Button>
                <p className="text-center text-xs text-content-tertiary">
                  No account?{' '}
                  <Link href="/register" className="text-accent hover:underline">Create one</Link>
                </p>
              </form>
            ) : (
              <form onSubmit={mfaForm.handleSubmit(handleMfa)} className="space-y-6">
                <Logo />
                {serverError && (
                  <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{serverError}</div>
                )}
                <p className="text-sm text-content-secondary text-center">
                  Enter the 6-digit code from your authenticator app.
                </p>
                <FormField id="mfa" label="MFA Code" required error={mfaForm.formState.errors.code}>
                  <Input
                    id="mfa"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    autoFocus
                    className="text-center tracking-widest text-lg font-mono"
                    {...mfaForm.register('code')}
                  />
                </FormField>
                <Button type="submit" size="lg" className="w-full" loading={mfaForm.formState.isSubmitting}>
                  {mfaForm.formState.isSubmitting ? 'Verifying…' : 'Verify'}
                </Button>
                <Button type="button" variant="ghost" size="sm" className="w-full"
                  onClick={() => { setStep('credentials'); mfaForm.reset(); setServerError(''); }}>
                  ← Back
                </Button>
              </form>
            )}
          </Card>
        )}

        <p className="text-center text-xs text-content-tertiary mt-6">
          YouTube Automation Dashboard v1.0
        </p>
      </div>
    </div>
  );
}
