'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api-v2';
import { ThemeToggle } from '@/lib/theme';
import { Button, Input, Label, Card } from '@/lib/ui';

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await authApi.register(email, password, workspaceName, name || undefined);
      await authApi.login(email, password);
      router.push('/onboarding');
    } catch (e: any) {
      setErr(e?.message || 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen relative">
      <div className="absolute top-5 right-5"><ThemeToggle /></div>

      <div className="w-full max-w-md px-6">
        <Card variant="elevated" padding="xl">
          <form onSubmit={submit} className="space-y-5">
            <div className="text-center space-y-1">
              <h1 className="text-xl font-semibold text-content-primary">Create your workspace</h1>
              <p className="text-content-tertiary text-xs">
                You'll be the owner. Invite teammates after setup.
              </p>
            </div>

            {err && (
              <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{err}</div>
            )}

            <div className="space-y-2">
              <Label htmlFor="r-ws" required>Workspace name</Label>
              <Input
                id="r-ws"
                required
                minLength={2}
                maxLength={60}
                value={workspaceName}
                onChange={e => setWorkspaceName(e.target.value)}
                placeholder="Acme Studios"
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="r-email" required>Email</Label>
              <Input
                id="r-email"
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="r-name">Display name <span className="text-content-tertiary font-normal">(optional)</span></Label>
              <Input
                id="r-name"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Saurabh"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="r-pw" required>Password</Label>
              <Input
                id="r-pw"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="At least 8 characters"
              />
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={!email || password.length < 8 || workspaceName.length < 2}
              loading={busy}
            >
              {busy ? 'Creating…' : 'Create workspace'}
            </Button>

            <p className="text-center text-xs text-content-tertiary">
              Have an account?{' '}
              <Link href="/login" className="text-accent hover:underline">Sign in</Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  );
}
