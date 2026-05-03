'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn, PHASE_ORDER, PHASE_LABELS } from '@/lib/utils';
import { ThemeToggle, HomeLogo } from '@/lib/theme';
import { useToast } from '@/lib/toast';

/* ── Phase descriptions for the expanded timeline ─────── */
const PHASE_DESC: Record<string, string> = {
  researching: 'Researching topic, trends, and competitor data',
  brand_check: 'Loading brand identity profile',
  scripting: 'Generating and refining the script',
  generating_voice: 'Synthesizing TTS narration audio',
  generating_assets: 'Fetching stock footage, generating thumbnail & music',
  directing: 'Creating frame-accurate direction for each segment',
  post_production: 'Editor optimizations and final QC',
  rendering: 'Remotion video render + assembly',
  pending_review: 'Waiting for human review approval',
  delivering: 'Uploading to YouTube',
  analytics: 'Collecting performance analytics',
  delivered: 'Video published successfully',
};

export default function ProgressPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [systemStopped, setSystemStopped] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [timelines, setTimelines] = useState<Record<string, any[]>>({});
  const [busyJobs, setBusyJobs] = useState<Set<string>>(new Set());
  const [retryingJobs, setRetryingJobs] = useState<Set<string>>(new Set());
  const [restartingJobs, setRestartingJobs] = useState<Set<string>>(new Set());
  const [timelineLoaded, setTimelineLoaded] = useState<Set<string>>(new Set());
  const { showToast } = useToast();

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.activeJobs();
      setJobs(res.data || []);
    } catch (e: any) {
      showToast(e?.message || 'Failed to load jobs', 'error');
    }
    setLoading(false);
  }, [showToast]);

  // Smart polling: stop when all jobs are terminal
  const allTerminal = jobs.length > 0 && jobs.every(j =>
    ['failed', 'delivered', 'test_delivered', 'rejected'].includes(j.status)
  );

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadJobs();
    api.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
  }, [router, loadJobs]);

  useEffect(() => {
    if (allTerminal) return; // Don't poll when all jobs are terminal
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [allTerminal, loadJobs]);

  // Fetch timeline for the expanded job
  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    const cid = expanded;
    async function fetchTimeline() {
      try {
        const res = await api.jobProgress(cid);
        if (!cancelled) {
          setTimelines(prev => ({ ...prev, [cid]: res.data?.timeline || [] }));
          setTimelineLoaded(prev => new Set(prev).add(cid));
        }
      } catch {}
    }
    fetchTimeline();
    // Only poll timeline for non-terminal jobs
    const expandedJob = jobs.find(j => j.content_id === cid);
    const isTerminal = expandedJob && ['failed', 'delivered', 'test_delivered', 'rejected'].includes(expandedJob.status);
    if (isTerminal) return () => { cancelled = true; };
    const iv = setInterval(fetchTimeline, 5000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [expanded, jobs]);

  function toggleExpand(contentId: string) {
    setExpanded(prev => prev === contentId ? null : contentId);
  }

  function markBusy(contentId: string) {
    setBusyJobs(prev => new Set(prev).add(contentId));
  }
  function clearBusy(contentId: string) {
    setBusyJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
  }

  async function handlePause(contentId: string) {
    markBusy(contentId);
    try { await api.pauseJob(contentId); await loadJobs(); } catch (e: any) {
      showToast(e?.message || 'Pause failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleResume(contentId: string) {
    markBusy(contentId);
    try { await api.resumeJob(contentId); await loadJobs(); } catch (e: any) {
      showToast(e?.message || 'Resume failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleStop(contentId: string) {
    markBusy(contentId);
    try { await api.stopJob(contentId); await loadJobs(); } catch (e: any) {
      showToast(e?.message || 'Stop failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleRetry(contentId: string) {
    if (retryingJobs.has(contentId)) return;
    setRetryingJobs(prev => new Set(prev).add(contentId));
    try {
      await api.retryJob(contentId);
      showToast('New video started', 'success');
      await loadJobs();
    } catch (e: any) {
      showToast(e?.message || 'Retry failed', 'error');
    } finally {
      setRetryingJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
    }
  }

  async function handleRestart(contentId: string, checkpoint: string) {
    if (restartingJobs.has(contentId)) return;
    setRestartingJobs(prev => new Set(prev).add(contentId));
    try {
      await api.restartJob(contentId);
      showToast(`Restarting from ${PHASE_LABELS[checkpoint] || checkpoint}`, 'success');
      await loadJobs();
    } catch (e: any) {
      showToast(e?.message || 'Restart failed', 'error');
    } finally {
      setRestartingJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
    }
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
                      const isPaused = job.is_paused === true;
                      const isBusy = busyJobs.has(job.content_id);
                      const isRetrying = retryingJobs.has(job.content_id);
                      const isRestarting = restartingJobs.has(job.content_id);
                      const isSuperseded = job.is_superseded === true;
                      const isExpanded = expanded === job.content_id;
                      const timeline = timelines[job.content_id] || [];
                      const tlLoaded = timelineLoaded.has(job.content_id);

                      return (
                        <div key={job.content_id} className={cn(
                          'card overflow-hidden',
                          isFailed && !isSuperseded && 'border-status-error/30 bg-status-error/5',
                          isSuperseded && 'opacity-50 border-border',
                          isPaused && !isFailed && 'border-status-warning/30',
                          !isFailed && !isPaused && !isSuperseded && !systemStopped && 'card-in-progress',
                          systemStopped && !isFailed && 'lockdown-frost'
                        )}>
                          {/* ── Job Card Header ──────────────── */}
                          <div className="p-5">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                {/* Status dot */}
                                <span className={cn(
                                  'w-2.5 h-2.5 rounded-full shrink-0',
                                  isFailed ? 'bg-status-error' :
                                  isPaused ? 'bg-status-warning' :
                                  'bg-accent animate-pulse'
                                )} />
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <Link href={`/dashboard/jobs/${job.content_id}`}
                                      className="text-sm font-medium text-content-primary hover:text-accent transition-colors truncate">
                                      {job.title || job.content_id}
                                    </Link>
                                    <span className={cn(
                                      'badge text-[10px] shrink-0',
                                      job.content_mode === 'short'
                                        ? 'bg-blue-500/10 text-blue-400'
                                        : 'bg-purple-500/10 text-purple-400'
                                    )}>
                                      {job.content_mode === 'short' ? 'Short' : 'Long'}
                                    </span>
                                    {isFailed && <span className="badge bg-status-error/10 text-status-error text-[10px] shrink-0">Failed</span>}
                                    {isSuperseded && <span className="badge bg-surface-3 text-content-tertiary text-[10px] shrink-0">Superseded</span>}
                                    {isPaused && !isFailed && <span className="badge bg-status-warning/10 text-status-warning text-[10px] shrink-0">Paused</span>}
                                  </div>
                                  <div className="text-xs text-content-tertiary mt-0.5">
                                    Started {new Date(job.created_at).toLocaleString()}
                                    {job.current_phase && !isFailed && (
                                      <> · <span className="text-content-secondary">{PHASE_LABELS[job.current_phase] || job.current_phase}</span></>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0 ml-3">
                                <span className="text-xs text-content-tertiary">${(job.total_cost || 0).toFixed(2)}</span>
                                {isFailed ? (
                                  isSuperseded ? (
                                    <span className="text-[10px] text-content-tertiary">Superseded</span>
                                  ) : (
                                    <button onClick={() => handleRetry(job.content_id)}
                                      disabled={isRetrying}
                                      title="Start a fresh new video"
                                      className={cn(
                                        'px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                        isRetrying
                                          ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                          : 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                      )}>
                                      {isRetrying ? 'Retrying...' : 'Retry'}
                                    </button>
                                  )
                                ) : (
                                  <>
                                    {isPaused ? (
                                      <button onClick={() => handleResume(job.content_id)} disabled={isBusy}
                                        className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10 transition-all disabled:opacity-50">
                                        {isBusy ? '...' : 'Resume'}
                                      </button>
                                    ) : (
                                      <button onClick={() => handlePause(job.content_id)} disabled={isBusy}
                                        className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all disabled:opacity-50">
                                        {isBusy ? '...' : 'Pause'}
                                      </button>
                                    )}
                                    <button onClick={() => handleStop(job.content_id)} disabled={isBusy}
                                      className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all disabled:opacity-50">
                                      {isBusy ? '...' : 'Stop'}
                                    </button>
                                  </>
                                )}
                                {/* Expand/collapse chevron */}
                                <button onClick={() => toggleExpand(job.content_id)}
                                  className="ml-1 p-1 rounded hover:bg-surface-2 transition-colors text-content-tertiary">
                                  <svg className={cn('w-4 h-4 transition-transform', isExpanded && 'rotate-180')}
                                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                                  </svg>
                                </button>
                              </div>
                            </div>

                            {/* Error message for failed jobs */}
                            {isFailed && job.error_message && (
                              <div className="mt-3 px-3 py-2 rounded bg-status-error/10 text-xs text-status-error font-mono truncate">
                                {job.error_message}
                              </div>
                            )}

                            {/* Mini Stepper (always visible) */}
                            <div className="flex items-center gap-0.5 mt-4">
                              {PHASE_ORDER.map((phase, idx) => {
                                const isCurrent = job.current_phase === phase;
                                const currentIdx = PHASE_ORDER.indexOf(job.current_phase || '');
                                const isCompleted = currentIdx > idx;
                                const isPhaseFailed = isCurrent && (job.phase_status === 'failed' || isFailed);
                                const isPhasePaused = isCurrent && isPaused;

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
                                        isPhasePaused ? 'bg-status-warning text-white' :
                                        isCompleted ? 'bg-status-success text-white' :
                                        isCurrent ? 'bg-accent text-white ring-2 ring-accent/20 animate-pulse' :
                                        'bg-surface-3 text-content-tertiary'
                                      )}>
                                        {isPhaseFailed ? '✕' : isPhasePaused ? '❚❚' : isCompleted ? '✓' : ''}
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
                                      isPhasePaused ? 'text-status-warning' :
                                      isCurrent ? 'text-accent' : isCompleted ? 'text-status-success' : 'text-content-tertiary/50'
                                    )}>
                                      {PHASE_LABELS[phase]}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* ── Expanded Timeline ─────────────── */}
                          {isExpanded && (
                            <div className="border-t border-border bg-surface-1/50 px-5 py-4">
                              {timeline.length === 0 && !tlLoaded ? (
                                <div className="text-xs text-content-tertiary text-center py-3">
                                  Loading timeline...
                                </div>
                              ) : timeline.length === 0 && tlLoaded ? (
                                <div className="text-xs text-content-tertiary text-center py-3">
                                  No events recorded for this job.
                                </div>
                              ) : (
                                <div className="space-y-0">
                                  {PHASE_ORDER.map((phase) => {
                                    // Find events for this phase
                                    const phaseEvents = timeline.filter((ev: any) => ev.phase === phase);
                                    const started = phaseEvents.find((ev: any) => ev.status === 'started');
                                    const completed = phaseEvents.find((ev: any) => ev.status === 'completed');
                                    const failed = phaseEvents.find((ev: any) => ev.status === 'failed');

                                    const hasStarted = !!started;
                                    const isComplete = !!completed;
                                    const hasFailed = !!failed;
                                    const isCurPhase = job.current_phase === phase && !isComplete && !hasFailed;

                                    // Compute duration
                                    let durationStr = '';
                                    if (started && completed) {
                                      const ms = new Date(completed.timestamp).getTime() - new Date(started.timestamp).getTime();
                                      durationStr = ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`;
                                    }

                                    // Compute cost
                                    const cost = phaseEvents.reduce((sum: number, ev: any) => sum + (ev.cost_usd || 0), 0);

                                    // Detail text
                                    const detail = completed?.detail || failed?.detail || {};
                                    let detailText = '';
                                    if (detail.topic) detailText = `Topic: ${detail.topic}`;
                                    else if (detail.segments) detailText = `${detail.segments} segments`;
                                    else if (detail.duration_s) detailText = `${detail.duration_s}s audio`;
                                    else if (detail.thumb_score) detailText = `Thumb score: ${detail.thumb_score}`;
                                    else if (detail.score) detailText = `Score: ${detail.score}`;
                                    else if (detail.video_url) detailText = 'Render complete';
                                    else if (detail.youtube_id) detailText = `YT: ${detail.youtube_id}`;
                                    else if (detail.error) detailText = detail.error;

                                    if (!hasStarted && !isCurPhase) {
                                      // Pending phase
                                      return (
                                        <div key={phase} className="flex items-start gap-3 py-2">
                                          <div className="flex flex-col items-center">
                                            <div className="w-5 h-5 rounded-full bg-surface-3 flex items-center justify-center">
                                              <span className="text-[9px] text-content-tertiary">○</span>
                                            </div>
                                            <div className="w-px h-4 bg-surface-3" />
                                          </div>
                                          <div className="flex-1 min-w-0 pt-0.5">
                                            <div className="text-xs text-content-tertiary/50">{PHASE_LABELS[phase] || phase}</div>
                                          </div>
                                        </div>
                                      );
                                    }

                                    return (
                                      <div key={phase} className="flex items-start gap-3 py-2">
                                        <div className="flex flex-col items-center">
                                          <div className={cn(
                                            'w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold',
                                            hasFailed ? 'bg-status-error text-white' :
                                            isComplete ? 'bg-status-success text-white' :
                                            isCurPhase && isPaused ? 'bg-status-warning text-white' :
                                            isCurPhase ? 'bg-accent text-white animate-pulse' :
                                            'bg-surface-3 text-content-tertiary'
                                          )}>
                                            {hasFailed ? '✕' : isComplete ? '✓' : isCurPhase ? '●' : '○'}
                                          </div>
                                          <div className={cn(
                                            'w-px h-4',
                                            isComplete ? 'bg-status-success/30' : 'bg-surface-3'
                                          )} />
                                        </div>
                                        <div className="flex-1 min-w-0 pt-0.5">
                                          <div className="flex items-center justify-between gap-2">
                                            <div className="flex items-center gap-2 min-w-0">
                                              <span className={cn(
                                                'text-xs font-medium',
                                                hasFailed ? 'text-status-error' :
                                                isCurPhase ? 'text-accent' :
                                                isComplete ? 'text-content-primary' : 'text-content-tertiary'
                                              )}>
                                                {PHASE_LABELS[phase] || phase}
                                              </span>
                                              {isCurPhase && isPaused && (
                                                <span className="text-[10px] text-status-warning font-medium">Paused</span>
                                              )}
                                              {isCurPhase && !isPaused && !hasFailed && (
                                                <span className="text-[10px] text-accent animate-pulse">Running</span>
                                              )}
                                            </div>
                                            <div className="flex items-center gap-3 shrink-0 text-[10px] text-content-tertiary">
                                              {durationStr && <span>{durationStr}</span>}
                                              {cost > 0 && <span>${cost.toFixed(3)}</span>}
                                            </div>
                                          </div>
                                          {/* Description */}
                                          <div className="text-[11px] text-content-tertiary mt-0.5">
                                            {detailText || (isCurPhase ? PHASE_DESC[phase] || 'Processing...' : PHASE_DESC[phase] || '')}
                                          </div>
                                          {/* Error detail */}
                                          {hasFailed && detail.error && (
                                            <div className="mt-1 text-[10px] text-status-error font-mono bg-status-error/5 px-2 py-1 rounded truncate">
                                              {detail.error}
                                            </div>
                                          )}
                                          {/* Restart from Phase action — only in failed timeline step with checkpoint */}
                                          {hasFailed && job.checkpoint && job.status === 'failed' && !isSuperseded && (
                                            <button
                                              onClick={() => handleRestart(job.content_id, job.checkpoint)}
                                              disabled={isRestarting}
                                              className={cn(
                                                'mt-1.5 px-2 py-0.5 border rounded text-[10px] font-medium transition-all',
                                                isRestarting
                                                  ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                                  : 'text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10'
                                              )}>
                                              {isRestarting ? 'Restarting...' : `Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                            </button>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}
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
