'use client';

import { useState } from 'react';
import Link from 'next/link';
import { authApi } from '@/lib/api-v2';
import { Button, Input, Label, Card } from '@/lib/ui';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [stage, setStage] = useState<'request' | 'reset' | 'slack' | 'done'>('request');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await authApi.forgot(email);
      if (res.reset_token) {
        setResetToken(res.reset_token);
        setStage('reset');
      } else {
        setStage('slack');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await authApi.reset(resetToken, newPassword);
      setStage('done');
    } catch (err: any) {
      setError(err.message || 'Reset failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-full max-w-md px-6">
        <Card variant="elevated" padding="xl" className="space-y-6">
          <div className="text-center space-y-1">
            <h1 className="text-xl font-semibold text-content-primary">Reset password</h1>
            <p className="text-content-tertiary text-sm">
              {stage === 'request' && 'Enter your email to receive a reset link.'}
              {stage === 'slack' && 'Check your Slack DM for the reset link.'}
              {stage === 'reset' && 'Enter the reset token and your new password.'}
              {stage === 'done' && 'Password updated successfully.'}
            </p>
          </div>

          {error && (
            <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">{error}</div>
          )}

          {stage === 'request' && (
            <form onSubmit={handleRequest} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" required>Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={!email}
                loading={loading}
              >
                {loading ? 'Sending…' : 'Send reset link'}
              </Button>
            </form>
          )}

          {stage === 'reset' && (
            <form onSubmit={handleReset} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="token" required>Reset token</Label>
                <Input
                  id="token"
                  type="text"
                  value={resetToken}
                  onChange={e => setResetToken(e.target.value)}
                  placeholder="Paste token from email"
                  required
                  className="font-mono"
                />
              </div>
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
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={!resetToken || newPassword.length < 8}
                loading={loading}
              >
                {loading ? 'Updating…' : 'Set new password'}
              </Button>
            </form>
          )}

          {stage === 'slack' && (
            <Button asChild size="lg" className="w-full">
              <Link href="/login">Back to login</Link>
            </Button>
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
      </div>
    </div>
  );
}
