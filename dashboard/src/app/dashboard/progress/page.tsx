'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn, PHASE_ORDER, PHASE_LABELS, statusColor } from '@/lib/utils';
import { ThemeToggle, HomeLogo } from '@/lib/theme';

export default function ProgressPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [systemStopped, setSystemStopped] = useState(false);

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.activeJobs();
      setJobs(res.data || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadJobs();
    api.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [router, loadJobs]);

  async function pauseJob(channelId: string) {
    try { await api.pause(channelId); loadJobs(); } catch {}
  }

  async function stopJob(channelId: string) {
    try { await api.stop(channelId); loadJobs(); } catch {}
  }

  async function retryJob(contentId: string) {
    try { await api.retryJob(contentId); loadJobs(); } catch {}
  }

  // Group jobs by channel
  const grouped = jobs.reduce((acc: Record<string, any[]>, job) => {
    const key = job.channel_id;
    if (!acc[key]) acc[key] = [];
    acc[key].push(job);
    return acc;
  }, {});

  const activeCount = jobs.filter(j => j.status !== 'failed').length;
  const failedCount = jobs.filter(j => j.status === 'failed').length;

  return (
    <div className="h-screen flex flex-col">
      {/* Fixed Header */}
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HomeLogo />
            <div>
              <h1 className="text-lg font-semibold text-content-primary">Active Jobs</h1>
              <p className="text-xs text-content-tertiary mt-0.5">
                {activeCount} in progress{failedCount > 0 && ` · ${failedCount} failed`} · Auto-refreshes every 5s
              </p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-20">
              <div className="text-content-tertiary text-sm">No active jobs right now.</div>
              <p className="text-xs text-content-tertiary mt-2">
                Trigger a channel from the{' '}
                <Link href="/dashboard" className="text-accent hover:underline font-medium">dashboard</Link>
                {' '}to see progress here.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {systemStopped && (
                <div className="p-4 rounded-lg bg-status-error/10 border border-status-error/20">
                  <div className="flex items-center gap-3">
                    <span className="text-status-error text-lg">■</span>
                    <div>
                      <h3 className="text-sm font-semibold text-status-error">System Stopped</h3>
                      <p className="text-xs text-content-tertiary mt-0.5">
                        All controls are frozen. Running jobs have been paused.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {Object.entries(grouped).map(([channelId, channelJobs]) => (
                <div key={channelId}>
                  {/* Channel group header */}
                  <div className="flex items-center gap-2 mb-3">
                    <Link href={`/dashboard/channels/${channelId}`}
                      className="text-sm font-semibold text-content-primary hover:text-accent transition-colors">
                      {channelJobs[0].channel_name}
                    </Link>
                    <span className="text-xs text-content-tertiary">
                      {channelJobs.length} job{channelJobs.length !== 1 ? 's' : ''}
                    </span>
                  </div>

                  <div className="space-y-3">
                    {channelJobs.map((job: any) => {
                      const isFailed = job.status === 'failed';
                      return (
                        <div key={job.content_id} className={cn(
                          'card p-5',
                          isFailed && 'border-status-error/30 bg-status-error/5',
                          systemStopped && !isFailed && 'lockdown-frost'
                        )}>
                          {/* Job header */}
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <span className={cn(
                                'w-2 h-2 rounded-full shrink-0',
                                isFailed ? 'bg-status-error' : 'bg-accent animate-pulse'
                              )} />
                              <div>
                                <div className="flex items-center gap-2">
                                  <Link href={`/dashboard/jobs/${job.content_id}`}
                                    className="text-sm font-medium text-content-primary hover:text-accent transition-colors">
                                    {job.title || job.content_id}
                                  </Link>
                                  <span className={cn(
                                    'badge text-[10px]',
                                    job.content_mode === 'short'
                                      ? 'bg-blue-500/10 text-blue-400'
                                      : 'bg-purple-500/10 text-purple-400'
                                  )}>
                                    {job.content_mode === 'short' ? 'Short' : 'Long'}
                                  </span>
                                  {isFailed && <span className="badge bg-status-error/10 text-status-error text-[10px]">Failed</span>}
                                </div>
                                <div className="text-xs text-content-tertiary mt-0.5">
                                  Started {new Date(job.created_at).toLocaleString()}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-content-tertiary">${job.total_cost.toFixed(2)}</span>
                              {isFailed ? (
                                <>
                                  <Link href={`/dashboard/channels/${job.channel_id}/settings`}
                                    title="Open channel settings to debug the failure"
                                    className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-content-tertiary bg-surface-1 border-border hover:bg-surface-2 transition-all">
                                    Settings
                                  </Link>
                                  <button onClick={() => retryJob(job.content_id)}
                                    title={job.checkpoint ? `Resume production from the '${job.checkpoint}' phase` : 'Restart the entire production workflow'}
                                    className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-accent bg-accent/5 border-accent/15 hover:bg-accent/10 transition-all">
                                    {job.checkpoint ? `Retry from ${job.checkpoint}` : 'Retry'}
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button onClick={() => pauseJob(job.channel_id)}
                                    title="Pause this workflow — it can be resumed later"
                                    className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all">
                                    Pause
                                  </button>
                                  <button onClick={() => stopJob(job.channel_id)}
                                    title="Terminate this workflow — cannot be resumed"
                                    className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all">
                                    Stop
                                  </button>
                                </>
                              )}
                            </div>
                          </div>

                          {/* Error message for failed jobs */}
                          {isFailed && job.error_message && (
                            <div className="mb-3 px-3 py-2 rounded bg-status-error/10 text-xs text-status-error font-mono truncate">
                              {job.error_message}
                            </div>
                          )}

                          {/* Mini Stepper */}
                          <div className="flex items-center gap-0.5">
                            {PHASE_ORDER.map((phase, idx) => {
                              const isCurrent = job.current_phase === phase;
                              const currentIdx = PHASE_ORDER.indexOf(job.current_phase || '');
                              const isCompleted = currentIdx > idx;
                              const isPhaseFailed = isCurrent && (job.phase_status === 'failed' || isFailed);

                              return (
                                <div key={phase} className="flex-1 flex flex-col items-center">
                                  <div className="flex items-center w-full">
                                    {idx > 0 && (
                                      <div className={cn(
                                        'flex-1 h-0.5',
                                        isCompleted ? 'bg-status-success' : 'bg-surface-3'
                                      )} />
                                    )}
                                    <div className={cn(
                                      'w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold shrink-0',
                                      isPhaseFailed ? 'bg-status-error text-white' :
                                      isCompleted ? 'bg-status-success text-white' :
                                      isCurrent ? 'bg-accent text-white ring-2 ring-accent/20 animate-pulse' :
                                      'bg-surface-3 text-content-tertiary'
                                    )}>
                                      {isPhaseFailed ? '✕' : isCompleted ? '✓' : ''}
                                    </div>
                                    {idx < PHASE_ORDER.length - 1 && (
                                      <div className={cn(
                                        'flex-1 h-0.5',
                                        isCompleted ? 'bg-status-success' : 'bg-surface-3'
                                      )} />
                                    )}
                                  </div>
                                  <span className={cn(
                                    'text-[8px] mt-1 font-medium text-center leading-tight',
                                    isPhaseFailed ? 'text-status-error' :
                                    isCurrent ? 'text-accent' : isCompleted ? 'text-status-success' : 'text-content-tertiary/50'
                                  )}>
                                    {PHASE_LABELS[phase]}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
