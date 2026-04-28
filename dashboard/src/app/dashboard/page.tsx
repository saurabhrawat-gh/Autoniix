'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn, clearToken } from '@/lib/api';
import { cn, statusDot } from '@/lib/utils';
import { ThemeToggle } from '@/lib/theme';

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<any>(null);
  const [channels, setChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pausedMap, setPausedMap] = useState<Record<string, boolean>>({});
  const [systemStopped, setSystemStopped] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadData();
  }, [router]);

  async function loadData() {
    try {
      const [s, c] = await Promise.all([api.stats(), api.channels()]);
      setStats(s.data);
      setSystemStopped(s.data?.emergency_stop === true);
      setChannels(c.data);
      // Check pause state for channels with active jobs
      const paused: Record<string, boolean> = {};
      for (const ch of c.data) {
        if (ch.active_job) {
          try {
            const ws = await api.workflowStatus(ch.channel_id);
            paused[ch.channel_id] = ws.data?.is_paused || false;
          } catch { paused[ch.channel_id] = false; }
        }
      }
      setPausedMap(paused);
    } catch { /* redirect on 401 handled by api client */ }
    setLoading(false);
  }

  async function toggleChannel(id: string, current: string) {
    try {
      if (current === 'active') await api.disableChannel(id);
      else await api.enableChannel(id);
      loadData();
    } catch {}
  }

  async function triggerChannel(id: string) {
    try {
      await api.trigger(id);
      loadData();
    } catch {}
  }

  async function togglePause(id: string) {
    try {
      if (pausedMap[id]) {
        await api.resume(id);
        setPausedMap(prev => ({ ...prev, [id]: false }));
      } else {
        await api.pause(id);
        setPausedMap(prev => ({ ...prev, [id]: true }));
      }
    } catch {}
  }

  async function stopChannel(id: string) {
    try { await api.stop(id); loadData(); } catch {}
  }

  function getChannelState(ch: any): 'idle' | 'running' | 'paused' | 'pending_review' {
    if (!ch.active_job) return 'idle';
    if (pausedMap[ch.channel_id]) return 'paused';
    if (ch.active_job.status === 'pending_review') return 'pending_review';
    return 'running';
  }

  function isWeeklyLimitReached(ch: any): boolean {
    if (!ch.weekly_usage) return false;
    const modes = (ch.content_mode || 'short').split(',');
    for (const mode of modes) {
      const m = mode.trim();
      const usage = ch.weekly_usage[m];
      if (usage && usage.used >= usage.limit) continue;
      return false; // at least one mode still has capacity
    }
    return true;
  }

  function getWeeklyLabel(ch: any): string | null {
    if (!ch.weekly_usage) return null;
    const parts: string[] = [];
    const modes = (ch.content_mode || 'short').split(',');
    for (const mode of modes) {
      const m = mode.trim();
      const u = ch.weekly_usage[m];
      if (!u) continue;
      const label = m === 'short' ? 'S' : 'L';
      parts.push(`${u.used}/${u.limit}${label}`);
    }
    return parts.join(' · ');
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
    </div>
  );

  return (
    <div className="h-screen flex flex-col">
      {/* Fixed Header */}
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-accent">
                <path d="M23 7l-7 5 7 5V7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <rect x="1" y="5" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="2"/>
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-content-primary">YouTube Automation</h1>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link href="/dashboard/progress" className="btn-secondary !py-2 !text-xs">
              Progress
            </Link>
            <Link href="/dashboard/settings" className="btn-secondary !py-2 !text-xs">
              Settings
            </Link>
            {systemStopped ? (
              <span className="btn-primary !py-2 !text-xs opacity-50 cursor-not-allowed">+ Add Channel</span>
            ) : (
              <Link href="/dashboard/channels/new" className="btn-primary !py-2 !text-xs">
                + Add Channel
              </Link>
            )}
            <button onClick={() => { clearToken(); router.push('/login'); }} className="btn-ghost !text-xs">
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-6">
          {/* System Stopped Banner */}
          {systemStopped && (
            <div className="mb-6 p-4 rounded-lg bg-status-error/10 border border-status-error/20">
              <div className="flex items-center gap-3">
                <span className="text-status-error text-lg">■</span>
                <div>
                  <h3 className="text-sm font-semibold text-status-error">System Inactive</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">
                    All operations are frozen. Channels cannot be enabled, triggers are disabled, and no automation will run.
                    Go to <Link href="/dashboard/settings" className="text-accent hover:underline font-medium">Settings</Link> to resume the system.
                  </p>
                </div>
              </div>
            </div>
          )}
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <StatCard label="Active Channels" value={stats.channels.active} sub={`${stats.channels.total} total`} icon="channels" />
              <StatCard label="Videos Today" value={stats.today.videos_total}
                sub={`${stats.today.delivered} delivered · ${stats.today.in_progress} in progress`} icon="videos" />
              <StatCard label="Cost Today" value={`$${stats.today.cost.toFixed(2)}`}
                sub={`Limit $${stats.budget.daily_limit}`} icon="cost" />
              <StatCard label="System Status"
                value={stats.emergency_stop ? 'Stopped' : 'Active'}
                variant={stats.emergency_stop ? 'error' : 'success'} icon="system" />
            </div>
          )}

          {/* Channel List */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-content-primary">Channels</h2>
              <span className="text-xs text-content-tertiary">{channels.length} total</span>
            </div>

            <div className="card overflow-hidden divide-y divide-border">
              {/* Table header */}
              <div className="px-5 py-3 flex items-center bg-surface-1/50 text-xs font-medium text-content-tertiary">
                <span className="flex-1">Channel</span>
                <span className="w-20 text-center">Enabled</span>
                <span className="w-64 text-right">Actions</span>
              </div>

              {channels.map((ch: any) => {
                const state = getChannelState(ch);
                const disabled = ch.status !== 'active';
                const limitReached = isWeeklyLimitReached(ch);
                const weeklyLabel = getWeeklyLabel(ch);
                const canTrigger = !disabled && !systemStopped && state === 'idle' && !limitReached;

                return (
                  <div key={ch.channel_id} className="px-5 py-4 flex items-center hover:bg-surface-1/50 transition-colors">
                    {/* Channel info */}
                    <Link href={`/dashboard/channels/${ch.channel_id}`} className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className={cn('w-2 h-2 rounded-full shrink-0', statusDot(ch.status))} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm text-content-primary truncate">{ch.channel_name}</span>
                            <span className="badge bg-surface-2 text-content-tertiary">{ch.niche}</span>
                            <span className="badge bg-surface-2 text-content-tertiary">
                              {ch.content_mode === 'short' ? 'Short' : ch.content_mode === 'long_form' ? 'Long' : ch.content_mode}
                            </span>
                            {ch.auto_upload && (
                              <span className="badge bg-accent/10 text-accent">Auto-upload</span>
                            )}
                          </div>
                          <div className="mt-1 text-xs text-content-tertiary flex gap-3">
                            <span>{ch.stats.delivered} delivered</span>
                            <span>{ch.stats.in_progress} in progress</span>
                            {weeklyLabel && <span className="text-accent font-medium">{weeklyLabel} this week</span>}
                          </div>
                        </div>
                      </div>
                    </Link>

                    {/* Toggle */}
                    <div className="w-20 flex justify-center">
                      <Toggle
                        checked={ch.status === 'active'}
                        onChange={() => toggleChannel(ch.channel_id, ch.status)}
                        disabled={systemStopped}
                      />
                    </div>

                    {/* Actions */}
                    <div className="w-64 flex justify-end items-center gap-2">
                      {/* Trigger / Progress Ring */}
                      {state === 'idle' ? (
                        <button
                          onClick={() => triggerChannel(ch.channel_id)}
                          disabled={!canTrigger}
                          className={cn(
                            'px-3 py-1.5 border rounded-lg text-xs font-medium transition-all',
                            canTrigger
                              ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                              : 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                          )}
                        >
                          {limitReached ? 'Limit Reached' : 'Trigger'}
                        </button>
                      ) : state === 'pending_review' ? (
                        <Link href={`/dashboard/jobs/${ch.active_job?.content_id}`}
                          className="px-3 py-1.5 border rounded-lg text-xs font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all">
                          Review
                        </Link>
                      ) : (
                        <div className="flex items-center gap-2">
                          <ProgressRing paused={state === 'paused'} />
                          <span className="text-[10px] text-content-tertiary font-medium">
                            {state === 'paused' ? 'Paused' : 'Running'}
                          </span>
                        </div>
                      )}

                      {/* Pause / Resume (single toggle) */}
                      {(state === 'running' || state === 'paused') && (
                        <button
                          onClick={() => togglePause(ch.channel_id)}
                          disabled={disabled}
                          className={cn(
                            'px-3 py-1.5 border rounded-lg text-xs font-medium transition-all',
                            pausedMap[ch.channel_id]
                              ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                              : 'text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10'
                          )}
                        >
                          {pausedMap[ch.channel_id] ? 'Resume' : 'Pause'}
                        </button>
                      )}

                      {/* Stop */}
                      {(state === 'running' || state === 'paused') && (
                        <button
                          onClick={() => stopChannel(ch.channel_id)}
                          disabled={disabled}
                          className="px-3 py-1.5 border rounded-lg text-xs font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all"
                        >
                          Stop
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {channels.length === 0 && (
                <div className="text-center py-16 text-content-tertiary text-sm">
                  No channels yet.{' '}
                  <Link href="/dashboard/channels/new" className="text-accent hover:underline font-medium">Add your first channel</Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ── Netflix-style circular progress ring ──────────────── */
function ProgressRing({ paused }: { paused?: boolean }) {
  const r = 10;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative w-7 h-7">
      <svg className={cn('w-7 h-7', !paused && 'animate-spin')} style={{ animationDuration: '2s' }} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor"
          className="text-surface-3" strokeWidth="2.5" />
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor"
          className={paused ? 'text-status-warning' : 'text-accent'}
          strokeWidth="2.5" strokeDasharray={c} strokeDashoffset={c * 0.3}
          strokeLinecap="round" />
      </svg>
      {paused && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex gap-0.5">
            <div className="w-1 h-2.5 bg-status-warning rounded-sm" />
            <div className="w-1 h-2.5 bg-status-warning rounded-sm" />
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, variant, icon }: {
  label: string; value: string | number; sub?: string; variant?: 'success' | 'error'; icon: string;
}) {
  const icons: Record<string, React.ReactNode> = {
    channels: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>,
    videos: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
    cost: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
    system: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  };

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-content-tertiary">{label}</span>
        <span className="text-content-tertiary/50">{icons[icon]}</span>
      </div>
      <div className={cn(
        'text-2xl font-semibold',
        variant === 'error' ? 'text-status-error' : variant === 'success' ? 'text-status-success' : 'text-content-primary'
      )}>{value}</div>
      {sub && <div className="text-xs text-content-tertiary mt-1.5">{sub}</div>}
    </div>
  );
}

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button onClick={disabled ? undefined : onChange}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent/20',
        checked ? 'bg-accent' : 'bg-surface-3',
        disabled && 'opacity-50 cursor-not-allowed'
      )}>
      <span className={cn(
        'inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
        checked ? 'translate-x-[22px]' : 'translate-x-[3px]'
      )} />
    </button>
  );
}
