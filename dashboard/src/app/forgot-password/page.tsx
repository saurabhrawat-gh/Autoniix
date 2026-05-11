'use client';

import { useState } from 'react';
import Link from 'next/link';
import { authApi } from '@/lib/api-v2';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [stage, setStage] = useState<'request' | 'reset' | 'done'>('request');
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
      }
      setStage('reset');
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
        <div className="card-elevated p-8 space-y-6">
          <div className="text-center space-y-1">
            <h1 className="text-xl font-semibold text-content-primary">Reset password</h1>
            <p className="text-content-tertiary text-sm">
              {stage === 'request' && 'Enter your email to receive a reset token.'}
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
                <label className="block text-sm font-medium text-content-primary">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  className="!py-3"
                />
              </div>
              <button type="submit" disabled={loading || !email} className="w-full btn-primary !py-3">
                {loading ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
          )}

          {stage === 'reset' && (
            <form onSubmit={handleReset} className="space-y-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-content-primary">Reset token</label>
                <input
                  type="text"
                  value={resetToken}
                  onChange={e => setResetToken(e.target.value)}
                  placeholder="Paste token from email"
                  required
                  className="!py-3 font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-content-primary">New password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                  className="!py-3"
                />
              </div>
              <button type="submit" disabled={loading || !resetToken || newPassword.length < 8} className="w-full btn-primary !py-3">
                {loading ? 'Updating…' : 'Set new password'}
              </button>
            </form>
          )}

          {stage === 'done' && (
            <Link href="/login" className="block w-full btn-primary !py-3 text-center">
              Back to login
            </Link>
          )}

          <p className="text-center text-xs text-content-tertiary">
            <Link href="/login" className="text-accent hover:underline">← Back to login</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
