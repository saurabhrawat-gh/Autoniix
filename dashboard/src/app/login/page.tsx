'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken } from '@/lib/api';
import { ThemeToggle } from '@/lib/theme';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.login(password);
      setToken(res.token, res.expires_in);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen relative">
      {/* Theme toggle */}
      <div className="absolute top-5 right-5">
        <ThemeToggle />
      </div>

      {/* Login card */}
      <div className="w-full max-w-md px-6">
        <form onSubmit={handleLogin} className="card-elevated p-8 space-y-8">
          {/* Logo / Branding */}
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

          {error && (
            <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 text-center">
              {error}
            </div>
          )}

          {/* Password field */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-content-primary">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter admin password"
              autoFocus
              className="!py-3"
            />
          </div>

          <button type="submit" disabled={loading || !password} className="w-full btn-primary !py-3">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-content-inverse/30 border-t-content-inverse rounded-full animate-spin" />
                Signing in…
              </span>
            ) : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-xs text-content-tertiary mt-6">
          YouTube Automation Dashboard v1.0
        </p>
      </div>
    </div>
  );
}
