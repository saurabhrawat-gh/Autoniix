'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn, statusColor, statusIcon, PHASE_LABELS } from '@/lib/utils';
import { ThemeToggle, HomeLogo } from '@/lib/theme';

export default function ChannelDetailPage() {
  const router = useRouter();
  const params = useParams();
  const channelId = params.id as string;
  const [tab, setTab] = useState<'long_form' | 'short'>('short');
  const [jobs, setJobs] = useState<any[]>([]);
  const [channel, setChannel] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [systemStopped, setSystemStopped] = useState(false);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsRes, chRes] = await Promise.all([
        api.jobs(channelId, tab),
        api.channels(),
      ]);
      setJobs(jobsRes.data || []);
      const ch = (chRes.data || []).find((c: any) => c.channel_id === channelId);
      if (ch && !channel) {
        const raw = ch.content_mode || 'short';
        const firstMode = raw === 'both' ? 'short' : raw.trim();
        if (firstMode !== tab) setTab(firstMode as 'short' | 'long_form');
      }
      setChannel(ch || null);
    } catch {}
    setLoading(false);
  }, [channelId, tab]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadJobs();
    api.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
  }, [router, loadJobs]);

  return (
    <div className="h-screen flex flex-col">
      {/* Fixed Header */}
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HomeLogo />
            <div>
              <h1 className="text-lg font-semibold text-content-primary">
                {channel?.channel_name || channelId}
              </h1>
              <p className="text-xs text-content-tertiary mt-0.5">Channel Detail</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
              <Link href={`/dashboard/channels/${channelId}/settings`}
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-surface-2 hover:bg-surface-3 transition-all text-content-secondary hover:text-accent"
                title="Channel Settings">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </Link>
              <ThemeToggle />
            </div>
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {/* Channel disabled banner */}
          {channel && channel.status !== 'active' && !systemStopped && (
            <div className="mb-6 p-4 rounded-lg bg-surface-2 border border-border">
              <div className="flex items-center gap-3">
                <span className="text-content-tertiary text-lg">○</span>
                <div>
                  <h3 className="text-sm font-semibold text-content-secondary">Channel Disabled</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">
                    Enable this channel from the dashboard to resume operations.
                  </p>
                </div>
              </div>
            </div>
          )}
          {/* Lockdown banner */}
          {systemStopped && (
            <div className="mb-6 p-4 rounded-lg bg-status-error/10 border border-status-error/20">
              <div className="flex items-center gap-3">
                <span className="text-status-error text-lg">■</span>
                <div>
                  <h3 className="text-sm font-semibold text-status-error">System Stopped</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">
                    All operations are frozen.
                  </p>
                </div>
              </div>
            </div>
          )}
          {/* Progress Summary Card */}
          {channel && (
            <div className={cn('card p-5 mb-6', (systemStopped || channel.status !== 'active') && 'lockdown-frost')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-6">
                  {/* Active job status */}
                  <div>
                    <div className="text-xs font-medium text-content-tertiary mb-1">Current Status</div>
                    {channel.active_job ? (
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                        <span className="text-sm font-medium text-content-primary">
                          {PHASE_LABELS[channel.active_job.status] || channel.active_job.status}
                        </span>
                      </div>
                    ) : (
                      <span className="text-sm text-content-tertiary">Idle</span>
                    )}
                  </div>
                  {/* Weekly usage */}
                  {channel.weekly_usage && (
                    <>
                      <div className="h-8 w-px bg-border" />
                      <div>
                        <div className="text-xs font-medium text-content-tertiary mb-1">Weekly Usage</div>
                        <div className="flex items-center gap-3">
                          {(() => {
                            const raw = channel.content_mode || 'short';
                            const modes = raw === 'both' ? ['short', 'long_form'] : raw.split(',').map((s: string) => s.trim());
                            return modes.map((m: string) => {
                              const u = channel.weekly_usage[m];
                              if (!u) return null;
                              return (
                                <span key={m} className={cn(
                                  'text-sm font-medium',
                                  m === (tab === 'short' ? 'short' : 'long_form') ? 'text-accent' : 'text-content-primary'
                                )}>
                                  {u.used}/{u.limit} {m === 'short' ? 'Shorts' : 'Long'}
                                </span>
                              );
                            });
                          })()}
                        </div>
                      </div>
                    </>
                  )}
                  {/* Automation indicator */}
                  <>
                    <div className="h-8 w-px bg-border" />
                    <div>
                      <div className="text-xs font-medium text-content-tertiary mb-1">Automation</div>
                      {channel.status !== 'active' ? (
                        <span className="text-sm font-medium text-content-tertiary">Cron Inactive</span>
                      ) : channel.schedule_enabled ? (
                        <span className="text-sm font-medium text-blue-400">Cron Active</span>
                      ) : (
                        <span className="text-sm font-medium text-content-tertiary">Cron Off</span>
                      )}
                    </div>
                  </>
                </div>
                <div className="flex items-center gap-3 text-xs text-content-tertiary">
                  <span>{channel.stats.delivered} delivered</span>
                  <span>{channel.stats.in_progress} in progress</span>
                  <span>{channel.stats.total} total</span>
                </div>
              </div>
            </div>
          )}

          {/* Content card */}
          <div className={cn('card overflow-hidden', (systemStopped || (channel && channel.status !== 'active')) && 'lockdown-frost')}>
            {/* Tabs — only show if channel supports multiple modes */}
            {(() => {
              const raw = channel?.content_mode || 'short';
              const modes = raw === 'both' ? ['short', 'long_form'] : [raw.trim()];
              return modes.length > 1 ? (
                <div className="flex border-b border-border px-5">
                  {modes.map((t) => (
                    <button key={t} onClick={() => setTab(t as 'short' | 'long_form')}
                      className={cn(
                        'px-4 py-3 text-sm font-medium transition-colors relative',
                        tab === t
                          ? 'text-accent'
                          : 'text-content-tertiary hover:text-content-primary'
                      )}>
                      {t === 'short' ? 'Short Form' : 'Long Form'}
                      {tab === t && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full" />}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="px-5 py-3 text-sm font-medium text-accent border-b border-border">
                  {modes[0] === 'short' ? 'Short Form' : 'Long Form'}
                </div>
              );
            })()}

            {/* Jobs */}
            {loading ? (
              <div className="flex justify-center py-16">
                <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-20">
                <div className="text-content-tertiary text-sm">No videos yet for this mode.</div>
                <p className="text-xs text-content-tertiary mt-2">
                  Go to the dashboard to trigger video production.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {jobs.map((job: any) => (
                  <Link key={job.content_id} href={`/dashboard/jobs/${job.content_id}`}
                    className="flex items-center px-5 py-4 hover:bg-surface-1/50 transition-colors">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span className={cn('text-sm font-medium', statusColor(job.status))}>{statusIcon(job.status)}</span>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-content-primary truncate">
                          {job.title || job.content_id}
                        </div>
                        <div className="text-xs text-content-tertiary mt-0.5">
                          {job.content_id} · {new Date(job.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <span className={cn('badge', statusColor(job.status), 'bg-current/5')}>
                        {PHASE_LABELS[job.status] || job.status}
                      </span>
                      {job.total_cost > 0 && (
                        <span className="text-xs text-content-tertiary">${job.total_cost.toFixed(2)}</span>
                      )}
                      {job.youtube_video_id && (
                        <a href={`https://youtu.be/${job.youtube_video_id}`} target="_blank" rel="noreferrer"
                          className="text-xs text-accent hover:underline font-medium" onClick={(e) => e.stopPropagation()}>
                          YouTube ↗
                        </a>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
