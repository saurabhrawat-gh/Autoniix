'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { isLoggedIn, wsEvents } from '@/lib/api';
import { dashboardApi, contentApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { Skeleton } from '@/lib/components/Skeleton';
import { AnimatedNumber } from '@/lib/components/AnimatedNumber';
import {
  Tv, Film, Activity, Settings, RefreshCw,
  AlertTriangle, CheckCircle2, Clock, ClipboardCheck, ShieldCheck, ShieldAlert,
  TrendingUp, Archive, FlaskConical, LayoutDashboard, Users,
} from '@/lib/components/Icon';

const JOB_STATUS_ICON: Record<string, React.ReactNode> = {
  delivered:      <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />,
  test_delivered: <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />,
  failed:         <AlertTriangle size={13} className="text-red-500 shrink-0" />,
  stopped:        <AlertTriangle size={13} className="text-orange-400 shrink-0" />,
  pending_review: <Clock size={13} className="text-amber-400 shrink-0" />,
};

function jobStatusIcon(status: string) {
  return JOB_STATUS_ICON[status] ?? <Activity size={13} className="text-accent shrink-0" />;
}

export default function DashboardPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [stats, setStats] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [envMode, setEnvMode] = useState<string>('test');
  const [systemStopped, setSystemStopped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [s, j] = await Promise.all([
        dashboardApi.stats(),
        contentApi.list({ limit: 30 }).catch(() => null),
      ]);
      const d = s.data;
      setStats(d);
      setSystemStopped(!!d.emergency_stop);
      setEnvMode(d.environment_mode || 'test');
      const items = j ? (j.data.groups ?? []).flatMap((g: any) => g.items ?? []) : [];
      setJobs(items);
    } catch (e: any) {
      showToast(e?.message || 'Failed to load', 'error');
    }
    setLoading(false);
  }, [showToast]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadData();
  }, [router, loadData]);

  // WS for live job updates
  useEffect(() => {
    if (!isLoggedIn()) return;
    let ws: WebSocket | null = null;
    let alive = true;
    let retry: any;
    const connect = () => {
      try {
        ws = wsEvents();
        ws.onmessage = (ev) => {
          try { if (JSON.parse(ev.data)?.type === 'job_update') loadData(); } catch {}
        };
        ws.onclose = () => { if (alive) retry = setTimeout(connect, 5000); };
        ws.onerror = () => ws?.close();
      } catch {}
    };
    connect();
    return () => { alive = false; clearTimeout(retry); ws?.close(); };
  }, [loadData]);

  async function refresh() {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }

  const activeCount  = stats?.channels?.active ?? 0;
  const totalVideos  = stats?.today?.videos_total ?? 0;
  const delivered    = stats?.today?.delivered ?? 0;
  const costToday    = stats?.today?.cost ?? 0;
  const dailyLimit   = stats?.budget?.daily_limit ?? 0;
  const totalChannels = stats?.channels?.total ?? 0;

  const runningJobs  = jobs.filter(j => !['failed','stopped','superseded','delivered','test_delivered','rejected'].includes(j.status));
  const pendingReview = jobs.filter(j => j.status === 'pending_review');
  const failedJobs   = jobs.filter(j => j.status === 'failed' || j.status === 'stopped');
  const recentJobs   = [...jobs].slice(0, 20);

  // Derived metrics
  const successRate = totalVideos > 0 ? Math.round((delivered / totalVideos) * 100) : null;
  const budgetPct   = dailyLimit > 0 ? Math.min(100, Math.round((costToday / dailyLimit) * 100)) : null;
  const systemHealthy = !systemStopped && failedJobs.length === 0;

  const quickActions = [
    { label: 'Channels',    href: '/dashboard/channels',    icon: <Tv size={14} />,           color: 'text-accent' },
    { label: 'Content',     href: '/dashboard/content',     icon: <Film size={14} />,          color: 'text-blue-500' },
    { label: 'Review',      href: '/dashboard/review',      icon: <ClipboardCheck size={14} />, color: 'text-amber-500', badge: pendingReview.length || undefined },
    { label: 'Library',     href: '/dashboard/library',     icon: <Archive size={14} />,       color: 'text-violet-500' },
    { label: 'Experiments', href: '/dashboard/experiments', icon: <FlaskConical size={14} />,  color: 'text-pink-500' },
    { label: 'Queue',       href: '/dashboard/queue',       icon: <Activity size={14} />,      color: 'text-emerald-500', badge: runningJobs.length || undefined },
    { label: 'Team',        href: '/dashboard/users',       icon: <Users size={14} />,         color: 'text-teal-500' },
    { label: 'Settings',    href: '/dashboard/settings',    icon: <Settings size={14} />,      color: 'text-content-tertiary' },
  ];

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full space-y-5">
      {/* ── Page header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <LayoutDashboard size={18} className="text-accent" /> Mission Control
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">Live pipeline overview — real-time stats and activity feed.</p>
        </div>
        <button onClick={refresh} disabled={refreshing}
          className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* ── Quick actions ── */}
      <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
        {quickActions.map(a => (
          <Link key={a.href} href={a.href}
            className="relative flex flex-col items-center gap-1.5 rounded-xl border border-border bg-surface-0 px-2 py-3 hover:bg-surface-1 hover:border-border-hover transition-all text-center group">
            <span className={cn('transition-colors group-hover:scale-110 transform transition-transform', a.color)}>{a.icon}</span>
            <span className="text-[10px] text-content-tertiary group-hover:text-content-secondary leading-none">{a.label}</span>
            {a.badge != null && a.badge > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent text-white text-[9px] font-bold flex items-center justify-center">
                {a.badge}
              </span>
            )}
          </Link>
        ))}
      </div>

      {/* ── Env / system banners ── */}
      {systemStopped && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 flex items-center gap-3">
          <AlertTriangle size={16} className="text-red-500 shrink-0" />
          <div className="text-sm">
            <span className="font-semibold text-red-500">System stopped</span>
            <span className="text-content-tertiary ml-2">All operations frozen.</span>
            <Link href="/dashboard/settings" className="ml-2 text-accent hover:underline text-xs font-medium">
              Go to Settings →
            </Link>
          </div>
        </div>
      )}
      {!systemStopped && envMode === 'test' && (
        <div className="p-2.5 rounded-md bg-amber-500/5 border border-amber-500/15 flex items-center gap-2 text-xs text-amber-400">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
          <span className="font-medium">Test Mode</span>
          <span className="text-content-tertiary">— Mock providers. No real YouTube uploads.</span>
        </div>
      )}
      {!systemStopped && envMode === 'production' && (
        <div className="p-2.5 rounded-md bg-emerald-500/5 border border-emerald-500/15 flex items-center gap-2 text-xs text-emerald-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          <span className="font-medium">Production Mode</span>
          <span className="text-content-tertiary">— Paid APIs active. Videos publish to YouTube.</span>
        </div>
      )}

      {/* ── Primary stats row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 !mt-4">
        {loading ? Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-md" />
        )) : (<>
          <StatCard label="Active Channels" value={activeCount}
            sub={`${totalChannels} total · ${stats?.channels?.disabled ?? 0} disabled`}
            icon={<Tv size={14} />} color="accent" href="/dashboard/channels" />
          <StatCard label="Videos Today" value={totalVideos}
            sub={`${delivered} delivered · ${runningJobs.length} in progress`}
            icon={<Film size={14} />} color="emerald" href="/dashboard/content" />
          <StatCard label="Cost Today" value={`$${costToday.toFixed(2)}`}
            sub={dailyLimit ? `of $${dailyLimit} limit` : 'no limit set'}
            progress={budgetPct ?? undefined}
            progressColor={budgetPct != null && budgetPct > 80 ? 'red' : 'blue'}
            icon={<TrendingUp size={14} />} color="blue" href="/dashboard/settings" />
          <StatCard label="Active Jobs" value={runningJobs.length}
            sub={pendingReview.length > 0 ? `${pendingReview.length} need review` : 'all clear'}
            icon={<Activity size={14} />}
            color={pendingReview.length > 0 ? 'amber' : 'emerald'}
            href="/dashboard/progress" />
        </>)}
      </div>

      {/* ── Secondary derived stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {loading ? Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-md" />
        )) : (<>
          <StatCard
            label="Success Rate"
            value={successRate != null ? `${successRate}%` : '—'}
            sub={successRate != null ? `${delivered} of ${totalVideos} delivered` : 'no videos today'}
            icon={<CheckCircle2 size={14} />}
            progress={successRate ?? undefined}
            progressColor={successRate != null && successRate >= 80 ? 'emerald' : successRate != null && successRate >= 50 ? 'amber' : 'red'}
            color="emerald"
          />
          <StatCard
            label="Pending Review"
            value={pendingReview.length}
            sub={pendingReview.length > 0 ? 'awaiting approval' : 'queue empty'}
            icon={<ClipboardCheck size={14} />}
            color={pendingReview.length > 0 ? 'amber' : 'muted'}
            href="/dashboard/content?review_state=pending"
          />
          <StatCard
            label="Failed Today"
            value={failedJobs.length}
            sub={failedJobs.length > 0 ? 'review & retry' : 'no failures'}
            icon={<AlertTriangle size={14} />}
            color={failedJobs.length > 0 ? 'red' : 'muted'}
            href="/dashboard/progress"
          />
          <StatCard
            label="System Health"
            value={systemHealthy ? 'Healthy' : systemStopped ? 'Stopped' : 'Warnings'}
            sub={systemStopped ? 'all ops frozen' : failedJobs.length > 0 ? `${failedJobs.length} failed jobs` : 'all systems go'}
            icon={systemHealthy ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
            color={systemHealthy ? 'emerald' : systemStopped ? 'red' : 'amber'}
            href="/dashboard/settings"
          />
        </>)}
      </div>

      {/* ── Pending review banner (compact) ── */}
      {pendingReview.length > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-md border border-amber-500/20 bg-amber-500/5">
          <ClipboardCheck size={16} className="text-amber-400 shrink-0" />
          <div className="flex-1 text-sm">
            <span className="font-semibold text-amber-400">{pendingReview.length} video{pendingReview.length > 1 ? 's' : ''} pending review</span>
            <span className="text-content-tertiary ml-2">Approve or reject before upload.</span>
          </div>
          <Link href="/dashboard/review"
            className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md bg-amber-500 text-white text-xs font-medium hover:opacity-90 transition-opacity shrink-0">
            Review now →
          </Link>
        </div>
      )}

      {/* ── Live activity ── */}
      <div className="rounded-xl border border-border bg-surface-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-content-primary">Live activity</h2>
          <button onClick={refresh} disabled={refreshing}
            className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-2 text-content-tertiary">
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
        {loading ? (
          <div className="divide-y divide-border">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-4 py-3 flex items-center gap-3">
                <Skeleton className="w-4 h-4 rounded-full" />
                <Skeleton className="h-3 flex-1 rounded" />
                <Skeleton className="h-3 w-16 rounded" />
              </div>
            ))}
          </div>
        ) : recentJobs.length === 0 ? (
          <div className="py-16 text-center text-sm text-content-tertiary">
            No active jobs. <Link href="/dashboard/channels" className="text-accent hover:underline">Trigger a channel →</Link>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {recentJobs.map(j => (
              <Link key={j.content_id} href={`/dashboard/jobs/${j.content_id}`}
                className="px-4 py-3 flex items-center gap-3 hover:bg-surface-1 transition-colors">
                {jobStatusIcon(j.status)}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{j.title || j.topic || j.content_id}</div>
                  <div className="text-[11px] text-content-tertiary truncate">
                    {j.channel_id} · {j.content_mode} · {j.current_phase || j.status}
                  </div>
                </div>
                {j.progress_pct != null && (
                  <span className="text-xs text-content-tertiary font-mono shrink-0">
                    {Math.round(j.progress_pct)}%
                  </span>
                )}
                <span className={cn(
                  'text-[10px] uppercase px-1.5 py-0.5 rounded shrink-0',
                  j.status === 'failed' || j.status === 'stopped' ? 'bg-red-500/15 text-red-500'
                    : j.status === 'pending_review' ? 'bg-amber-500/15 text-amber-500'
                    : j.status === 'delivered' || j.status === 'test_delivered' ? 'bg-emerald-500/15 text-emerald-500'
                    : 'bg-accent/10 text-accent'
                )}>
                  {j.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function StatCard({
  label, value, sub, color, icon, href, progress, progressColor,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  icon?: React.ReactNode;
  href?: string;
  progress?: number;
  progressColor?: string;
}) {
  const iconWrapColor: Record<string, string> = {
    accent: 'bg-accent/10 text-accent',
    emerald: 'bg-emerald-500/10 text-emerald-500',
    blue: 'bg-blue-500/10 text-blue-400',
    amber: 'bg-amber-500/10 text-amber-400',
    red: 'bg-red-500/10 text-red-500',
    muted: 'bg-surface-2 text-content-tertiary',
  };
  const progressBarColor: Record<string, string> = {
    accent: 'bg-accent',
    emerald: 'bg-emerald-500',
    blue: 'bg-blue-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };

  const inner = (
    <>
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">{label}</div>
        {icon && (
          <div className={cn('w-7 h-7 rounded-md flex items-center justify-center shrink-0', iconWrapColor[color] || iconWrapColor.muted)}>
            {icon}
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-content-primary leading-tight">
        {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
      </div>
      {sub && <div className="text-xs text-content-tertiary mt-1">{sub}</div>}
      {progress != null && (
        <div className="mt-2.5 h-1 rounded-full bg-surface-2 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', progressBarColor[progressColor || color] || progressBarColor.accent)}
            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
          />
        </div>
      )}
    </>
  );

  const baseClass = 'rounded-xl border border-border bg-surface-0 p-4 transition-colors';
  if (href) {
    return (
      <Link href={href} className={cn(baseClass, 'block hover:border-accent/40 hover:bg-surface-1 hover:shadow-card')}>
        {inner}
      </Link>
    );
  }
  return <div className={baseClass}>{inner}</div>;
}
