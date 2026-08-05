'use client';

import { useState, useEffect, Suspense } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api-v2';
import { Button, Input, Card } from '@/lib/ui';
import { ShieldCheck, AlertCircle, CheckCircle2 } from '@/lib/components/Icon';
import { FormField } from '@/lib/components/FormField';
import { acceptInviteSchema, type AcceptInviteValues } from '@/lib/schemas/auth';

function AcceptInviteContent() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get('token') || '';

  const [serverError, setServerError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [needsAccount, setNeedsAccount] = useState<boolean | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<AcceptInviteValues>({
    resolver: zodResolver(acceptInviteSchema),
  });

  useEffect(() => {
    if (!token) return;
    fetch(`/api/v2/auth/invite-info?token=${encodeURIComponent(token)}`)
      .then(r => r.json())
      .then(d => setNeedsAccount(!d.user_exists))
      .catch(() => setNeedsAccount(true));
  }, [token]);

  async function onSubmit(values: AcceptInviteValues) {
    setServerError(null);
    try {
      await authApi.acceptInvite(
        token,
        needsAccount ? values.password : undefined,
        needsAccount && values.name ? values.name : undefined,
      );
      setDone(true);
      setTimeout(() => router.push('/dashboard'), 1500);
    } catch (e: any) {
      setServerError(e?.message || 'Failed to accept invite');
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
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {needsAccount && (
        <>
          <FormField id="ai-name" label="Display name" hint="Optional" error={errors.name}>
            <Input id="ai-name" placeholder="Your name" autoComplete="name" {...register('name')} />
          </FormField>
          <FormField id="ai-pw" label="Create password" required error={errors.password}>
            <Input id="ai-pw" type="password" placeholder="At least 8 characters" autoComplete="new-password" {...register('password')} />
          </FormField>
          <FormField id="ai-cpw" label="Confirm password" required error={errors.confirm}>
            <Input id="ai-cpw" type="password" placeholder="Repeat password" autoComplete="new-password" {...register('confirm')} />
          </FormField>
        </>
      )}

      {needsAccount === false && (
        <p className="text-sm text-content-secondary">
          You already have an account. Click below to join the workspace.
        </p>
      )}

      {serverError && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-status-danger/30 bg-status-danger/5">
          <AlertCircle size={14} className="text-status-danger shrink-0" />
          <p className="text-sm text-status-danger">{serverError}</p>
        </div>
      )}

      <Button
        type="submit"
        loading={isSubmitting}
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
