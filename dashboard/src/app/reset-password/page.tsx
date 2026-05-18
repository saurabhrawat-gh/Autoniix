'use client';

import { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/api-v2';
import { Button, Input, Label, Card } from '@/lib/ui';

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [stage, setStage] = useState<'form' | 'done'>('form');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirm) { setError('Passwords do not match'); return; }
    setLoading(true);
    setError('');
    try {
      await authApi.reset(token, newPassword);
      setStage('done');
    } catch (err: any) {
      setError(err.message || 'Reset failed — the link may have expired');
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <p className="text-status-error text-sm">Missing reset token. Request a new link.</p>
        <Link href="/forgot-password" className="text-accent hover:underline text-sm">Request new link</Link>
      </div>
    );
  }

  return (
    <Card variant="elevated" padding="xl" className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="text-xl font-semibold text-content-primary">Set new password</h1>
        <p className="text-content-tertiary text-sm">
          {stage === 'form' ? 'Choose a strong password for your account.' : 'Password updated successfully.'}
        </p>
      </div>

      {error && (
        <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
      )}

      {stage === 'form' && (
        <form onSubmit={handleReset} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-pw" required>New password</Label>
            <Input
              id="new-pw"
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="At least 8 characters"
              minLength={8}
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-pw" required>Confirm password</Label>
            <Input
              id="confirm-pw"
              type="password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              placeholder="Repeat your new password"
              minLength={8}
              required
            />
          </div>
          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={newPassword.length < 8 || confirm.length < 8}
            loading={loading}
          >
            {loading ? 'Updating…' : 'Set new password'}
          </Button>
        </form>
      )}

      {stage === 'done' && (
        <Button asChild size="lg" className="w-full">
          <Link href="/login">Back to login</Link>
        </Button>
      )}

      <p className="text-center text-xs text-content-tertiary">
        <Link href="/login" className="text-accent hover:underline">← Back to login</Link>
      </p>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-full max-w-md px-6">
        <Suspense fallback={<div className="flex justify-center"><span className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" /></div>}>
          <ResetPasswordContent />
        </Suspense>
      </div>
    </div>
  );
}
