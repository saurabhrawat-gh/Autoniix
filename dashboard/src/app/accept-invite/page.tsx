'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authApi, setV2Tokens } from '@/lib/api-v2';
import { Button, Input, Label, Card } from '@/lib/ui';
import { ShieldCheck, AlertCircle, CheckCircle2 } from '@/lib/components/Icon';

function AcceptInviteContent() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [needsAccount, setNeedsAccount] = useState<boolean | null>(null);

  useEffect(() => {
    if (!token) return;
    fetch(`/api/v2/auth/invite-info?token=${encodeURIComponent(token)}`)
      .then(r => r.json())
      .then(d => setNeedsAccount(!d.user_exists))
      .catch(() => setNeedsAccount(true));
  }, [token]);

  async function handleAccept(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (needsAccount) {
      if (password.length < 8) { setErr('Password must be at least 8 characters'); return; }
      if (password !== confirmPw) { setErr('Passwords do not match'); return; }
    }
    setBusy(true);
    try {
      const r = await authApi.acceptInvite(
        token,
        needsAccount ? password : undefined,
        needsAccount && displayName ? displayName : undefined,
      );
      setV2Tokens(r.access_token, r.refresh_token);
      setDone(true);
      setTimeout(() => router.push('/dashboard'), 1500);
    } catch (e: any) {
      setErr(e?.message || 'Failed to accept invite');
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl border border-status-danger/30 bg-status-danger/5">
        <AlertCircle size={18} className="text-status-danger shrink-0" />
        <p className="text-sm text-content-primary">Invalid invitation link — no token found.</p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-center">
        <CheckCircle2 size={40} className="text-status-success" />
        <p className="text-base font-medium text-content-primary">You&apos;re in! Redirecting…</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleAccept} className="space-y-4">
      {needsAccount && (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="ai-name">Display name (optional)</Label>
            <Input
              id="ai-name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Your name"
              autoComplete="name"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ai-pw">Create password</Label>
            <Input
              id="ai-pw"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ai-cpw">Confirm password</Label>
            <Input
              id="ai-cpw"
              type="password"
              value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)}
              placeholder="Repeat password"
              autoComplete="new-password"
              required
            />
          </div>
        </>
      )}

      {needsAccount === false && (
        <p className="text-sm text-content-secondary">
          You already have an account. Click below to join the workspace.
        </p>
      )}

      {err && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-status-danger/30 bg-status-danger/5">
          <AlertCircle size={14} className="text-status-danger shrink-0" />
          <p className="text-sm text-status-danger">{err}</p>
        </div>
      )}

      <Button
        type="submit"
        loading={busy}
        className="w-full"
        leftIcon={<ShieldCheck size={15} />}
      >
        {needsAccount ? 'Create account & join' : 'Accept invitation'}
      </Button>

      <p className="text-center text-xs text-content-tertiary">
        Already have an account?{' '}
        <Link href="/login" className="text-accent hover:underline">Sign in first</Link>
      </p>
    </form>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center mx-auto mb-3">
            <ShieldCheck size={22} className="text-accent" />
          </div>
          <h1 className="text-xl font-semibold text-content-primary">Workspace invitation</h1>
          <p className="text-sm text-content-secondary mt-1">Accept your invitation to join a workspace.</p>
        </div>

        <Card variant="elevated" padding="lg">
          <Suspense fallback={<p className="text-sm text-content-tertiary text-center py-4">Loading…</p>}>
            <AcceptInviteContent />
          </Suspense>
        </Card>
      </div>
    </div>
  );
}
