'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn, PHASE_ORDER, PHASE_LABELS, statusColor } from '@/lib/utils';
import { ThemeToggle } from '@/lib/theme';

export default function ProgressPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

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
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [router, loadJobs]);

  async function pauseJob(channelId: string) {
    try { await api.pause(channelId); loadJobs(); } catch {}
  }

  async function stopJob(channelId: string) {
    try { await api.stop(channelId); loadJobs(); } catch {}
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Fixed Header */}
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="btn-ghost !px-2 !py-1 !text-xs">← Back</Link>
            <div>
              <h1 className="text-lg font-semibold text-content-primary">Active Jobs</h1>
              <p className="text-xs text-content-tertiary mt-0.5">
                {jobs.length} job{jobs.length !== 1 ? 's' : ''} in progress · Auto-refreshes every 5s
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
            <div className="space-y-4">
              {jobs.map((job: any) => (
                <div key={job.content_id} className="card p-5">
                  {/* Job header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                      <div>
                        <Link href={`/dashboard/jobs/${job.content_id}`}
                          className="text-sm font-medium text-content-primary hover:text-accent transition-colors">
                          {job.title || job.content_id}
                        </Link>
                        <div className="text-xs text-content-tertiary mt-0.5">
                          {job.channel_name} · {job.content_mode === 'short' ? 'Short' : 'Long'} · Started {new Date(job.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-content-tertiary">${job.total_cost.toFixed(2)}</span>
                      <button onClick={() => pauseJob(job.channel_id)}
                        className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all">
                        Pause
                      </button>
                      <button onClick={() => stopJob(job.channel_id)}
                        className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all">
                        Stop
                      </button>
                    </div>
                  </div>

                  {/* Mini Stepper */}
                  <div className="flex items-center gap-0.5">
                    {PHASE_ORDER.map((phase, idx) => {
                      const isCurrent = job.current_phase === phase;
                      const currentIdx = PHASE_ORDER.indexOf(job.current_phase || '');
                      const isCompleted = currentIdx > idx;
                      const isFailed = isCurrent && job.phase_status === 'failed';

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
                              isFailed ? 'bg-status-error text-white' :
                              isCompleted ? 'bg-status-success text-white' :
                              isCurrent ? 'bg-accent text-white ring-2 ring-accent/20 animate-pulse' :
                              'bg-surface-3 text-content-tertiary'
                            )}>
                              {isFailed ? '✕' : isCompleted ? '✓' : ''}
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
                            isCurrent ? 'text-accent' : isCompleted ? 'text-status-success' : 'text-content-tertiary/50'
                          )}>
                            {PHASE_LABELS[phase]}
                          </span>
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
