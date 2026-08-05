'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { jobsApi, dashboardApi } from '@/lib/api-v2';
import { isLoggedIn, wsEvents } from '@/lib/api-v2';
import { cn, PHASE_ORDER, PHASE_LABELS } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { PageHeader } from '@/lib/components/PageHeader';
import { SkeletonCard } from '@/lib/components/Skeleton';
import { EmptyState } from '@/lib/components/EmptyState';
import { PhaseStepper } from '@/lib/components/PhaseStepper';
import { BorderBeam } from '@/lib/components/BorderBeam';
import { AnimatedNumber } from '@/lib/components/AnimatedNumber';
import { ChevronDown, Inbox, RotateCcw } from '@/lib/components/Icon';
import { Button, Dialog, DialogContent, DialogHeader, DialogBody, DialogFooter, DialogCloseButton, DialogTitle, DialogDescription } from '@/lib/ui';

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
  const [retryConfirm, setRetryConfirm] = useState<string | null>(null);
  const { showToast } = useToast();

  const loadJobs = useCallback(async () => {
    try {
      const res = await jobsApi.active();
      setJobs(res.data || []);
    } catch (e: any) {
      showToast(e?.message || 'Failed to load jobs', 'error');
    }
    setLoading(false);
  }, [showToast]);

  const allTerminal = jobs.length > 0 && jobs.every(j =>
    ['failed', 'stopped', 'superseded', 'delivered', 'test_delivered', 'rejected'].includes(j.status)
  );

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadJobs();
    dashboardApi.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
  }, [router, loadJobs]);

  useEffect(() => {
    if (allTerminal) return;
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [allTerminal, loadJobs]);

  useEffect(() => {
    if (!isLoggedIn()) return;
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout;
    function connectWs() {
      try {
        ws = wsEvents();
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'clean_slate') { loadJobs(); return; }
            if (msg.type !== 'job_update') return;

            const cid: string = msg.content_id;
            const s: string = msg.status || '';
            if (cid && s) {
              setJobs(prev => prev.map(j => {
                if (j.content_id !== cid) return j;
                if (s === 'paused') return { ...j, is_paused: true };
                if (s === 'resumed') return { ...j, is_paused: false };
                if (s === 'stopped') return { ...j, status: 'stopped', is_paused: false };
                if (s === 'failed') return { ...j, status: 'failed' };
                const nextIdx = PHASE_ORDER.indexOf(s);
                const curIdx = j.current_phase ? PHASE_ORDER.indexOf(j.current_phase) : -1;
                if (nextIdx > curIdx) return { ...j, current_phase: s, is_paused: false };
                return j;
              }));
            }
            loadJobs();
          } catch {}
        };
        ws.onclose = () => { reconnectTimer = setTimeout(connectWs, 5000); };
        ws.onerror = () => { ws?.close(); };
      } catch {}
    }
    connectWs();
    return () => { ws?.close(); clearTimeout(reconnectTimer); };
  }, [loadJobs]);

  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    const cid = expanded;
    async function fetchTimeline() {
      try {
        const res = await jobsApi.progress(cid);
        if (!cancelled) {
          setTimelines(prev => ({ ...prev, [cid]: res.data?.timeline || [] }));
          setTimelineLoaded(prev => new Set(prev).add(cid));
        }
      } catch {}
    }
    fetchTimeline();
    const expandedJob = jobs.find(j => j.content_id === cid);
    const isTerminal = expandedJob && ['failed', 'stopped', 'superseded', 'delivered', 'test_delivered', 'rejected'].includes(expandedJob.status);
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

  /** Optimistically patch a job in local state and revert on error. */
  function patchJob(contentId: string, patch: Partial<any>) {
    setJobs(prev => prev.map(j => j.content_id === contentId ? { ...j, ...patch } : j));
  }

  async function handlePause(contentId: string) {
    const prev = jobs.find(j => j.content_id === contentId);
    markBusy(contentId);
    patchJob(contentId, { is_paused: true });
    try {
      await jobsApi.pause(contentId);
      await loadJobs();
    } catch (e: any) {
      if (prev) patchJob(contentId, { is_paused: prev.is_paused });
      showToast(e?.message || 'Pause failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleResume(contentId: string) {
    const prev = jobs.find(j => j.content_id === contentId);
    markBusy(contentId);
    patchJob(contentId, { is_paused: false });
    try {
      await jobsApi.resume(contentId);
      await loadJobs();
    } catch (e: any) {
      if (prev) patchJob(contentId, { is_paused: prev.is_paused });
      showToast(e?.message || 'Resume failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleStop(contentId: string) {
    const prev = jobs.find(j => j.content_id === contentId);
    markBusy(contentId);
    patchJob(contentId, { status: 'stopped', is_paused: false });
    try {
      await jobsApi.stop(contentId);
      await loadJobs();
    } catch (e: any) {
      if (prev) patchJob(contentId, { status: prev.status, is_paused: prev.is_paused });
      showToast(e?.message || 'Stop failed', 'error');
    }
    clearBusy(contentId);
  }

  async function handleRetry(contentId: string) {
    if (retryingJobs.has(contentId)) return;
    setRetryingJobs(prev => new Set(prev).add(contentId));
    try {
      await jobsApi.retry(contentId);
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
      await jobsApi.restart(contentId);
      showToast(`Restarting from ${PHASE_LABELS[checkpoint] || checkpoint}`, 'success');
      await loadJobs();
    } catch (e: any) {
      showToast(e?.message || 'Restart failed', 'error');
    } finally {
      setRestartingJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
    }
  }

  const grouped = jobs.reduce((acc: Record<string, any[]>, job) => {
    const key = job.channel_id;
    if (!acc[key]) acc[key] = [];
    acc[key].push(job);
    return acc;
  }, {});

  const activeCount = jobs.filter(j => !['failed', 'stopped', 'superseded'].includes(j.status)).length;
  const failedCount = jobs.filter(j => j.status === 'failed').length;
  const stoppedCount = jobs.filter(j => j.status === 'stopped').length;

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Active Jobs"
        subtitle={`${activeCount} in progress${stoppedCount > 0 ? ` · ${stoppedCount} stopped` : ''}${failedCount > 0 ? ` · ${failedCount} failed` : ''} · Auto-refreshes every 5s`}
        crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Progress' }]}
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {loading ? (
            <div className="space-y-4">
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : jobs.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No active jobs"
              body="Trigger a channel from the dashboard to start producing a video and watch its progress here in real time."
              cta={{ label: 'Go to Dashboard', href: '/dashboard' }}
            />
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
                      const isStopped = job.status === 'stopped';
                      const isPaused = job.is_paused === true;
                      const isBusy = busyJobs.has(job.content_id);
                      const isRetrying = retryingJobs.has(job.content_id);
                      const isRestarting = restartingJobs.has(job.content_id);
                      const isExpanded = expanded === job.content_id;
                      const timeline = timelines[job.content_id] || [];
                      const tlLoaded = timelineLoaded.has(job.content_id);

                      return (
                        <div key={job.content_id} className={cn(
                          'card overflow-hidden relative',
                          isFailed && 'border-status-error/30 bg-status-error/5',
                          isStopped && 'border-status-warning/30 bg-status-warning/5',
                          isPaused && !isFailed && !isStopped && 'border-status-warning/30',
                          systemStopped && !isFailed && !isStopped && 'lockdown-frost'
                        )}>
                          {!isFailed && !isStopped && !isPaused && !systemStopped && (
                            <BorderBeam duration={3} size={55} />
                          )}
                          {/* ── Job Card Header ──────────────── */}
                          <div className="p-5">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                {/* Status dot */}
                                <span className={cn(
                                  'w-2.5 h-2.5 rounded-full shrink-0',
                                  isFailed ? 'bg-status-error' :
                                  isStopped ? 'bg-status-warning' :
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
                                        ? 'bg-accent/10 text-accent'
                                        : 'bg-status-info/10 text-status-info'
                                    )}>
                                      {job.content_mode === 'short' ? 'Short' : 'Long'}
                                    </span>
                                    {isFailed && <span className="badge bg-status-error/10 text-status-error text-[10px] shrink-0">Failed</span>}
                                    {isStopped && <span className="badge bg-status-warning/10 text-status-warning text-[10px] shrink-0">Stopped</span>}
                                    {isPaused && !isFailed && !isStopped && <span className="badge bg-status-warning/10 text-status-warning text-[10px] shrink-0">Paused</span>}
                                  </div>
                                  <div className="text-xs text-content-tertiary mt-0.5">
                                    Started {new Date(job.created_at).toLocaleString()}
                                    {job.current_phase && !isFailed && !isStopped && (
                                      <> · <span className="text-content-secondary">{PHASE_LABELS[job.current_phase] || job.current_phase}</span></>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0 ml-3">
                                <span className="text-xs text-content-tertiary">
                                  <AnimatedNumber value={job.total_cost || 0} prefix="$" />
                                </span>
                                {isFailed ? (
                                  <div className="flex items-center gap-1.5">
                                    {job.checkpoint && (
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleRestart(job.content_id, job.checkpoint)}
                                        disabled={isRestarting}
                                        title={`Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                        className={cn(
                                          'px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                          isRestarting
                                            ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                            : 'text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10'
                                        )}>
                                        {isRestarting ? 'Restarting...' : `Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                      </Button>
                                    )}
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() => setRetryConfirm(job.content_id)}
                                      disabled={isRetrying}
                                      title="Start a fresh new video"
                                      className={cn(
                                        'px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                        isRetrying
                                          ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                          : 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                      )}>
                                      {isRetrying ? 'Retrying...' : 'Retry Fresh'}
                                    </Button>
                                  </div>
                                ) : isStopped ? (
                                  <div className="flex items-center gap-1.5">
                                    {job.checkpoint && (
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleRestart(job.content_id, job.checkpoint)}
                                        disabled={isRestarting}
                                        title={`Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                        className={cn(
                                          'px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                          isRestarting
                                            ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                            : 'text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10'
                                        )}>
                                        {isRestarting ? 'Restarting...' : `Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                      </Button>
                                    )}
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() => setRetryConfirm(job.content_id)}
                                      disabled={isRetrying}
                                      title="Start a fresh new video"
                                      className={cn(
                                        'px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                        isRetrying
                                          ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                          : 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                      )}>
                                      {isRetrying ? 'Retrying...' : 'Retry Fresh'}
                                    </Button>
                                  </div>
                                ) : (
                                  <>
                                    {isPaused ? (
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleResume(job.content_id)}
                                        disabled={isBusy}
                                        className="h-7 px-2.5 text-[11px] text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10"
                                      >
                                        {isBusy ? '...' : 'Resume'}
                                      </Button>
                                    ) : (
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handlePause(job.content_id)}
                                        disabled={isBusy}
                                        className="h-7 px-2.5 text-[11px] text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10"
                                      >
                                        {isBusy ? '...' : 'Pause'}
                                      </Button>
                                    )}
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleStop(job.content_id)}
                                      disabled={isBusy}
                                      className="h-7 px-2.5 text-[11px] text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10"
                                    >
                                      {isBusy ? '...' : 'Stop'}
                                    </Button>
                                  </>
                                )}
                                {/* Expand/collapse chevron */}
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => toggleExpand(job.content_id)}
                                  aria-label={isExpanded ? 'Collapse timeline' : 'Expand timeline'}
                                  className="ml-1 w-7 h-7 text-content-tertiary"
                                >
                                  <ChevronDown size={16} className={cn('transition-transform', isExpanded && 'rotate-180')} />
                                </Button>
                              </div>
                            </div>

                            {/* Error message for failed jobs */}
                            {(isFailed || isStopped) && job.error_message && (
                              <div className="mt-3 px-3 py-2 rounded bg-status-error/10 text-xs text-status-error font-mono truncate">
                                {job.error_message}
                              </div>
                            )}

                            {/* Animated Stepper */}
                            <PhaseStepper
                              jobId={job.content_id}
                              currentPhase={job.current_phase}
                              isFailed={isFailed}
                              isStopped={isStopped}
                              isPaused={isPaused}
                              phaseStatus={job.phase_status}
                            />
                          </div>

                          {/* ── Expanded Timeline (animated) ───── */}
                          <AnimatePresence initial={false}>
                          {isExpanded && (
                            <motion.div
                              key="timeline"
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.28, ease: 'easeOut' }}
                              className="overflow-hidden"
                            >
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
                                    const phaseEvents = timeline.filter((ev: any) => ev.phase === phase);
                                    const started = phaseEvents.find((ev: any) => ev.status === 'started');
                                    const completed = phaseEvents.find((ev: any) => ev.status === 'completed');
                                    const failed = phaseEvents.find((ev: any) => ev.status === 'failed');

                                    const hasStarted = !!started;
                                    const isComplete = !!completed;
                                    const hasFailed = !!failed;
                                    const isCurPhase = job.current_phase === phase && !isComplete && !hasFailed;

                                    let durationStr = '';
                                    if (started && completed) {
                                      const ms = new Date(completed.timestamp).getTime() - new Date(started.timestamp).getTime();
                                      durationStr = ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`;
                                    }

                                    const cost = phaseEvents.reduce((sum: number, ev: any) => sum + (ev.cost_usd || 0), 0);

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
                                          {hasFailed && job.checkpoint && (job.status === 'failed' || job.status === 'stopped') && (
                                            <Button
                                              type="button"
                                              variant="outline"
                                              size="sm"
                                              onClick={() => handleRestart(job.content_id, job.checkpoint)}
                                              disabled={isRestarting}
                                              className={cn(
                                                'mt-1.5 px-2 py-0.5 border rounded text-[10px] font-medium transition-all',
                                                isRestarting
                                                  ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                                                  : 'text-status-success bg-status-success/5 border-status-success/15 hover:bg-status-success/10'
                                              )}>
                                              {isRestarting ? 'Restarting...' : `Restart from ${PHASE_LABELS[job.checkpoint] || job.checkpoint}`}
                                            </Button>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                            </motion.div>
                          )}
                          </AnimatePresence>
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

      <Dialog open={!!retryConfirm} onOpenChange={(o) => { if (!o) setRetryConfirm(null); }}>
        <DialogContent size="sm">
          {(() => {
            if (!retryConfirm) return null;
            const job = jobs.find(j => j.content_id === retryConfirm);
            const checkpointPhase = job?.checkpoint;
            const checkpointLabel = checkpointPhase ? (PHASE_LABELS[checkpointPhase] || checkpointPhase) : null;
            const running = retryingJobs.has(retryConfirm);
            return (
              <>
                <DialogHeader>
                  <div>
                    <DialogTitle className="flex items-center gap-2">
                      <RotateCcw size={14} className="text-accent shrink-0" />
                      Start Fresh?
                    </DialogTitle>
                    <DialogDescription>A brand new job will begin from the very first step.</DialogDescription>
                  </div>
                  <DialogCloseButton onClick={() => setRetryConfirm(null)} />
                </DialogHeader>
                <DialogBody>
                  <p className="text-sm text-content-secondary leading-relaxed">
                    All the steps will start again from scratch.
                    {checkpointLabel ? (
                      <> If you only want to redo the later phases, open the timeline and hit <span className="text-status-success font-medium">Restart from {checkpointLabel}</span> instead.</>
                    ) : (
                      <> If you only want to redo the later phases, open the timeline and hit <span className="text-status-success font-medium">Restart from checkpoint</span> instead.</>
                    )}
                  </p>
                  <DialogFooter>
                    <Button variant="ghost" size="sm" onClick={() => setRetryConfirm(null)} disabled={running}>Cancel</Button>
                    <Button
                      size="sm"
                      onClick={async () => { await handleRetry(retryConfirm); setRetryConfirm(null); }}
                      disabled={running}
                      loading={running}
                    >
                      {running ? 'Starting…' : 'Yes, Retry Fresh'}
                    </Button>
                  </DialogFooter>
                </DialogBody>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
    </div>
  );
}
