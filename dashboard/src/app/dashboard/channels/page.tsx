'use client';

import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { channelsApi, dashboardApi } from '@/lib/api-v2';
import { isLoggedIn, wsEvents } from '@/lib/api-v2';
import { cn, statusDot } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { Skeleton, SkeletonCard } from '@/lib/components/Skeleton';
import { EmptyState } from '@/lib/components/EmptyState';
import {
  Plus, ChevronUp, ChevronDown, Tv, Search, X,
  Settings, Layers, Boxes, Play, RotateCw,
} from '@/lib/components/Icon';
import {
  Button,
  Input,
  Switch,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseButton,
  DialogTitle,
  DialogDescription,
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  SimpleTooltip,
  TooltipProvider,
} from '@/lib/ui';
import { useUrlState } from '@/lib/hooks/useUrlState';
import { motion, useMotionValue, useSpring, useReducedMotion, AnimatePresence } from 'framer-motion';

type Tab = 'all' | 'active' | 'disabled' | 'archived';
type SortKey = 'name' | 'delivered' | 'status' | 'created';
type SortDir = 'asc' | 'desc';

const PINNED_KEY = 'yt_pinned_channels';
function loadPinned(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(PINNED_KEY) || '[]')); } catch { return new Set(); }
}
function savePinned(s: Set<string>) {
  localStorage.setItem(PINNED_KEY, JSON.stringify(Array.from(s)));
}

export default function ChannelsPage() {
  const router = useRouter();
  const [allChannels, setAllChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [systemStopped, setSystemStopped] = useState(false);
  const [actionMenu, setActionMenu] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState<string | null>(null);
  const [triggeringKeys, setTriggeringKeys] = useState<Set<string>>(new Set());
  const [busyJobs, setBusyJobs] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const [channelListRef] = useAutoAnimate<HTMLDivElement>();

  const TAB_VALUES: Tab[] = ['all', 'active', 'disabled', 'archived'];
  const SORT_VALUES: SortKey[] = ['name', 'delivered', 'status', 'created'];
  const [tab, setTab] = useUrlState<Tab>('tab', {
    defaultValue: 'all',
    deserialize: (raw: string | null) => (raw && TAB_VALUES.includes(raw as Tab) ? (raw as Tab) : 'all'),
  });
  const [search, setSearch] = useUrlState<string>('q', {
    defaultValue: '',
    deserialize: (raw: string | null) => raw ?? '',
  });
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [sortKey, setSortKey] = useUrlState<SortKey>('sort', {
    defaultValue: 'name',
    deserialize: (raw: string | null) => (raw && SORT_VALUES.includes(raw as SortKey) ? (raw as SortKey) : 'name'),
  });
  const [sortDir, setSortDir] = useUrlState<SortDir>('dir', {
    defaultValue: 'asc',
    deserialize: (raw: string | null) => (raw === 'desc' ? 'desc' : 'asc'),
  });
  const [pinned, setPinned] = useState<Set<string>>(new Set());
  const [showSortMenu, setShowSortMenu] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');
  const debounceRef = useRef<NodeJS.Timeout>();

  const AVATAR_COLORS = [
    'bg-violet-500','bg-blue-500','bg-emerald-500','bg-amber-500',
    'bg-pink-500','bg-teal-500','bg-orange-500','bg-cyan-500',
  ];
  function platformLabel(platform: string | undefined) {
    const map: Record<string, string> = {
      youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok',
      x: 'X', linkedin: 'LinkedIn',
    };
    return map[platform || 'youtube'] ?? 'YouTube';
  }

  function avatarColor(id: string) {
    let hash = 0;
    for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
    return AVATAR_COLORS[hash % AVATAR_COLORS.length];
  }
  function avatarInitials(name: string) {
    return name ? name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() : '?';
  }

  useEffect(() => {
    debounceRef.current && clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { debounceRef.current && clearTimeout(debounceRef.current); };
  }, [search]);

  const loadData = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([channelsApi.list(true), dashboardApi.stats().catch(() => null)]);
      setAllChannels(c.data || []);
      setSystemStopped(s?.data?.emergency_stop === true);
    } catch (e: any) {
      showToast(e?.message || 'Failed to load data', 'error');
    }
    setLoading(false);
  }, [showToast]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    setPinned(loadPinned());
    loadData();
  }, [router, loadData]);

  useEffect(() => {
    if (!isLoggedIn()) return;
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout;
    function connectWs() {
      try {
        ws = wsEvents();
        ws.onmessage = (ev) => { try { if (JSON.parse(ev.data).type === 'job_update') loadData(); } catch {} };
        ws.onclose = () => { reconnectTimer = setTimeout(connectWs, 5000); };
        ws.onerror = () => { ws?.close(); };
      } catch {}
    }
    connectWs();
    const pollInterval = setInterval(loadData, 15000);
    return () => { ws?.close(); clearTimeout(reconnectTimer); clearInterval(pollInterval); };
  }, [loadData]);

  function togglePin(id: string) {
    setPinned(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      savePinned(next);
      return next;
    });
  }

  function cycleSort(key: SortKey) {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  const tabCounts = useMemo(() => ({
    all: allChannels.length,
    active: allChannels.filter(c => c.status === 'active').length,
    disabled: allChannels.filter(c => c.status === 'disabled').length,
    archived: allChannels.filter(c => c.status === 'archived').length,
  }), [allChannels]);

  const displayChannels = useMemo(() => {
    let list = [...allChannels];
    if (tab === 'active') list = list.filter(c => c.status === 'active');
    else if (tab === 'disabled') list = list.filter(c => c.status === 'disabled');
    else if (tab === 'archived') list = list.filter(c => c.status === 'archived');
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase();
      list = list.filter(c => c.channel_name?.toLowerCase().includes(q) || c.channel_id?.toLowerCase().includes(q) || c.niche?.toLowerCase().includes(q));
    }
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = (a.channel_name || '').localeCompare(b.channel_name || '');
      else if (sortKey === 'delivered') cmp = (a.stats?.delivered || 0) - (b.stats?.delivered || 0);
      else if (sortKey === 'status') cmp = a.status.localeCompare(b.status);
      else if (sortKey === 'created') cmp = (a.created_at || '').localeCompare(b.created_at || '');
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return [...list.filter(c => pinned.has(c.channel_id)), ...list.filter(c => !pinned.has(c.channel_id))];
  }, [allChannels, tab, debouncedSearch, sortKey, sortDir, pinned]);

  async function toggleChannel(id: string, current: string) {
    const next = current === 'active' ? 'disabled' : 'active';
    const snapshot = allChannels;
    setAllChannels(prev => prev.map(c => c.channel_id === id ? { ...c, status: next } : c));
    try {
      if (current === 'active') await channelsApi.disable(id);
      else await channelsApi.enable(id);
      loadData();
    } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Toggle failed', 'error'); }
  }

  async function archiveChannel(id: string) {
    const snapshot = allChannels;
    const name = allChannels.find(c => c.channel_id === id)?.channel_name || 'channel';
    setAllChannels(prev => prev.map(c => c.channel_id === id ? { ...c, status: 'archived' } : c));
    setConfirmArchive(null);
    try {
      await channelsApi.archive(id);
      showToast(`${name} archived`, { variant: 'info', duration: 6000, action: { label: 'Undo', onAct: async () => { await channelsApi.restore(id); loadData(); } } });
      loadData();
    } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Archive failed', 'error'); }
  }

  async function restoreChannel(id: string) {
    const snapshot = allChannels;
    setAllChannels(prev => prev.map(c => c.channel_id === id ? { ...c, status: 'disabled' } : c));
    try { await channelsApi.restore(id); loadData(); } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Restore failed', 'error'); }
  }

  async function cloneChannel(id: string) {
    try { await channelsApi.clone(id); setActionMenu(null); loadData(); } catch (e: any) { showToast(e?.message || 'Clone failed', 'error'); }
  }

  async function exportChannel(id: string) {
    try {
      const res = await channelsApi.export(id);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `${id}-config.json`; a.click(); URL.revokeObjectURL(url);
      setActionMenu(null);
    } catch (e: any) { showToast(e?.message || 'Export failed', 'error'); }
  }

  async function triggerChannel(id: string, contentMode: string) {
    const key = `${id}:${contentMode}`;
    if (triggeringKeys.has(key)) return;
    setTriggeringKeys(prev => new Set(prev).add(key));
    try { await channelsApi.trigger(id, { content_mode: contentMode }); await loadData(); } catch (e: any) { showToast(e?.message || 'Trigger failed', 'error'); }
    setTriggeringKeys(prev => { const n = new Set(prev); n.delete(key); return n; });
  }

  async function togglePauseJob(channelId: string, contentId: string, isPaused: boolean) {
    if (busyJobs.has(contentId)) return;
    setBusyJobs(prev => new Set(prev).add(contentId));
    try {
      if (isPaused) await channelsApi.resumeJob(channelId, contentId);
      else await channelsApi.pauseJob(channelId, contentId);
      await loadData();
    } catch (e: any) { showToast(e?.message || 'Action failed', 'error'); }
    setBusyJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
  }

  async function stopJob(channelId: string, contentId: string) {
    if (busyJobs.has(contentId)) return;
    setBusyJobs(prev => new Set(prev).add(contentId));
    try { await channelsApi.stopJob(channelId, contentId); await loadData(); } catch (e: any) { showToast(e?.message || 'Stop failed', 'error'); }
    setBusyJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
  }

  function getModeJob(ch: any, mode: string) { return (ch.active_jobs || []).find((j: any) => j.content_mode === mode) || null; }
  function getModeState(ch: any, mode: string): 'idle' | 'running' | 'paused' | 'pending_review' | 'stopped' {
    if (triggeringKeys.has(`${ch.channel_id}:${mode}`)) return 'running';
    const job = getModeJob(ch, mode);
    if (!job) return 'idle';
    if (job.status === 'stopped' || job.status === 'failed' || job.status === 'superseded') return 'idle';
    if (job.is_paused) return 'paused';
    if (job.status === 'pending_review') return 'pending_review';
    return 'running';
  }
  function getModes(ch: any): string[] {
    const raw = ch.content_mode || 'short';
    if (raw === 'mixed') return ['short', 'long_form'];
    return raw.split(',').map((m: string) => m.trim());
  }
  function isModeAtLimit(ch: any, mode: string): boolean {
    const u = ch.weekly_usage?.[mode]; return u ? u.used >= u.limit : false;
  }
  function getWeeklyLabel(ch: any): string | null {
    if (!ch.weekly_usage) return null;
    return getModes(ch).map((m: string) => { const u = ch.weekly_usage[m]; return u ? `${u.used}/${u.limit}${m === 'short' ? 'S' : 'L'}` : null; }).filter(Boolean).join(' · ');
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All' }, { key: 'active', label: 'Active' },
    { key: 'disabled', label: 'Inactive' }, { key: 'archived', label: 'Archived' },
  ];
  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: 'name', label: 'Name' }, { key: 'delivered', label: 'Videos' },
    { key: 'status', label: 'Status' }, { key: 'created', label: 'Created' },
  ];

  const totalRunning = allChannels.reduce((acc, ch) => acc + (ch.stats?.in_progress || 0), 0);

  if (loading) return (
    <div className="flex-1 flex flex-col">
      <div className="max-w-[1400px] mx-auto w-full px-6 py-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );

  return (
    <TooltipProvider delayDuration={250}>
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-5 pb-3">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
              <Tv size={18} className="text-accent" /> Channels
            </h1>
            <p className="text-xs text-content-tertiary mt-0.5">Manage and trigger your automation channels.</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="icon-sm" onClick={() => loadData()} aria-label="Refresh">
              <RotateCw size={13} />
            </Button>
            {/* View toggle */}
            <div className="flex items-center gap-0.5 bg-surface-1 border border-border rounded-md p-0.5">
              {(['table', 'grid'] as const).map(v => (
                <Button
                  key={v}
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setViewMode(v)}
                  aria-label={v === 'table' ? 'Table view' : 'Grid view'}
                  className={cn('w-7 h-7',
                    viewMode === v ? 'bg-surface-0 text-content-primary shadow-card hover:bg-surface-0' : 'text-content-tertiary hover:text-content-secondary')}
                >
                  {v === 'table' ? <Layers size={13} /> : <Boxes size={13} />}
                </Button>
              ))}
            </div>
            <Button asChild size="sm" leftIcon={<Plus size={13} />}>
              <Link href="/dashboard/channels/new">Add Channel</Link>
            </Button>
          </div>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          {[
            { label: 'Total',    value: tabCounts.all,      color: 'text-content-primary' },
            { label: 'Active',   value: tabCounts.active,   color: 'text-status-success' },
            { label: 'Running',  value: totalRunning,       color: 'text-accent' },
            { label: 'Disabled', value: tabCounts.disabled, color: 'text-content-tertiary' },
          ].map(s => (
            <div key={s.label} className="rounded-lg border border-border bg-surface-0 px-3 py-2">
              <div className={cn('text-xl font-bold tabular-nums leading-none', s.color)}>{s.value}</div>
              <div className="text-[10px] text-content-tertiary mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
            {TABS.map(t => (
              <Button
                key={t.key}
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setTab(t.key)}
                className={cn('h-7 px-3 text-xs',
                  tab === t.key ? 'bg-surface-0 text-content-primary shadow-card hover:bg-surface-0' : 'text-content-tertiary hover:text-content-secondary')}
              >
                {t.label}
                <span className={cn('ml-1', tab === t.key ? 'text-accent' : 'text-content-tertiary')}>
                  {tabCounts[t.key]}
                </span>
              </Button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[180px] max-w-sm ml-auto">
            <Input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search name, ID, niche…"
              leftIcon={<Search size={12} />}
              className="h-8 text-xs pr-7"
            />
            {search && (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => setSearch('')}
                aria-label="Clear search"
                className="absolute right-1 top-1/2 -translate-y-1/2 w-5 h-5 text-content-tertiary hover:text-content-primary"
              >
                <X size={10} />
              </Button>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary" size="sm" className="h-8"
                rightIcon={sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              >
                <span className="text-content-tertiary mr-1">Sort:</span>
                {SORT_OPTIONS.find(s => s.key === sortKey)?.label}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              {SORT_OPTIONS.map(s => (
                <DropdownMenuItem
                  key={s.key}
                  onClick={() => cycleSort(s.key)}
                  className={cn('justify-between', sortKey === s.key && 'text-accent bg-accent/5 font-medium')}
                >
                  {s.label}
                  {sortKey === s.key && (sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />)}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 pb-4 overflow-y-auto">
        {displayChannels.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-0 p-8">
            {debouncedSearch ? (
              <EmptyState title={`No channels match "${debouncedSearch}"`} body="Try a different search or clear filters." />
            ) : tab === 'archived' ? (
              <EmptyState title="No archived channels" body="Channels you archive will appear here." />
            ) : (
              <EmptyState icon={Plus} title="No channels yet" body="Create your first channel to start producing videos automatically."
                cta={{ label: 'Add your first channel', href: '/dashboard/channels/new' }} />
            )}
          </div>
        ) : viewMode === 'grid' ? (
          /* ── Grid View ── */
          <div className={cn('grid gap-3 sm:grid-cols-2 lg:grid-cols-3', systemStopped && 'lockdown-frost')}>
            {displayChannels.map((ch: any) => {
              const isDisabled = ch.status !== 'active';
              const isArchived = ch.status === 'archived';
              const modes = getModes(ch);
              const isPinned = pinned.has(ch.channel_id);
              const aColor = avatarColor(ch.channel_id);
              const initials = avatarInitials(ch.channel_name);
              return (
                <div key={ch.channel_id}
                  className={cn(
                    'rounded-xl border bg-surface-0 p-4 flex flex-col gap-3 transition-all hover:shadow-card',
                    isPinned ? 'border-accent/40' : 'border-border',
                    isArchived && 'opacity-60'
                  )}>
                  {/* Card header */}
                  <div className="flex items-start gap-3">
                    <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0', aColor)}>
                      {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                      <Link href={`/dashboard/channels/${ch.channel_id}`}
                        className="font-semibold text-sm text-content-primary hover:text-accent truncate block">
                        {ch.channel_name}
                      </Link>
                      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                        {ch.niche && <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">{ch.niche}</span>}
                        {modes.map((m: string) => (
                          <span key={m} className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium',
                            m === 'short' ? 'bg-violet-500/10 text-violet-500' : 'bg-blue-500/10 text-blue-500')}>
                            {m === 'short' ? 'Short' : 'Long'}
                          </span>
                        ))}
                        {ch.auto_upload && <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">Auto</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className={cn('w-1.5 h-1.5 rounded-full', statusDot(ch.status))} />
                      {!isArchived && (
                        <Toggle checked={ch.status === 'active'} onChange={() => toggleChannel(ch.channel_id, ch.status)} disabled={systemStopped} />
                      )}
                    </div>
                  </div>

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 border-t border-border pt-3">
                    {[
                      { label: 'Delivered', value: ch.stats?.delivered || 0, color: 'text-status-success' },
                      { label: 'Running',   value: ch.stats?.in_progress || 0, color: 'text-accent' },
                      { label: 'Weekly',    value: getWeeklyLabel(ch) || '—', color: 'text-content-tertiary' },
                    ].map(s => (
                      <div key={s.label} className="text-center">
                        <div className={cn('text-sm font-bold tabular-nums', s.color)}>{s.value}</div>
                        <div className="text-[9px] text-content-tertiary uppercase tracking-wide">{s.label}</div>
                      </div>
                    ))}
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1.5 flex-wrap border-t border-border pt-3">
                    {isArchived ? (
                      <>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => restoreChannel(ch.channel_id)}
                          className="flex-1 h-7 text-[11px] text-accent border-accent/30 bg-accent/5 hover:bg-accent/10"
                        >
                          Restore
                        </Button>
                        <Link href={`/dashboard/channels/${ch.channel_id}`}
                          className="flex-1 h-7 rounded-md border border-border bg-surface-1 text-content-tertiary text-[11px] font-medium hover:bg-surface-2 transition-colors flex items-center justify-center">
                          View
                        </Link>
                      </>
                    ) : (
                      <>
                        {modes.map((m: string) => {
                          const mState = getModeState(ch, m);
                          const mJob = getModeJob(ch, m);
                          const atLimit = isModeAtLimit(ch, m);
                          const canTrigger = !isDisabled && !systemStopped && !atLimit && mState === 'idle';
                          if (mState === 'idle') return (
                            <MagneticTriggerButton
                              key={m}
                              label={atLimit ? 'Limit' : m === 'short' ? 'Short' : 'Long'}
                              disabled={!canTrigger}
                              onClick={() => canTrigger && triggerChannel(ch.channel_id, m)}
                            />
                          );
                          if (mState === 'pending_review' && mJob) return (
                            <Link key={m} href={`/dashboard/jobs/${mJob.content_id}`}
                              className="flex-1 h-7 rounded-md border border-status-warning/30 bg-status-warning/5 text-status-warning text-[11px] font-medium flex items-center justify-center transition-all">
                              Review
                            </Link>
                          );
                          const isBusy = mJob && busyJobs.has(mJob.content_id);
                          return (
                            <div key={m} className="flex items-center gap-1 flex-1 justify-center">
                              <ProgressRing paused={mState === 'paused'} />
                              <span className="text-[10px] text-content-tertiary">{mState === 'paused' ? 'Paused' : 'Running'}</span>
                              {mJob && (
                                <>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => togglePauseJob(ch.channel_id, mJob.content_id, mJob.is_paused)}
                                    disabled={!!isBusy}
                                    aria-label={mJob.is_paused ? 'Resume' : 'Pause'}
                                    className="h-5 px-1.5 text-[10px] text-content-tertiary"
                                  >
                                    {isBusy ? '…' : mJob.is_paused ? '▶' : '⏸'}
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => stopJob(ch.channel_id, mJob.content_id)}
                                    disabled={!!isBusy}
                                    aria-label="Stop"
                                    className="h-5 px-1.5 text-[10px] text-status-error border-status-error/30 bg-status-error/5 hover:bg-status-error/10"
                                  >
                                    {isBusy ? '…' : '■'}
                                  </Button>
                                </>
                              )}
                            </div>
                          );
                        })}
                        <Link href={`/dashboard/channels/${ch.channel_id}`}
                          className="w-7 h-7 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary hover:text-accent transition-colors">
                          <Settings size={12} />
                        </Link>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="icon-sm" aria-label="More actions">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" /></svg>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-44">
                            <DropdownMenuItem onClick={() => cloneChannel(ch.channel_id)}>Duplicate</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => exportChannel(ch.channel_id)}>Export JSON</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setConfirmArchive(ch.channel_id)} className="text-status-warning focus:text-status-warning focus:bg-status-warning/5">Archive</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* ── Table View ── */
          <div className={cn('rounded-xl border border-border bg-surface-0 overflow-hidden', systemStopped && 'lockdown-frost')}>
            <div className="shrink-0 px-4 py-2.5 grid grid-cols-[44px_1fr_100px_72px_72px_100px_56px_260px] items-center bg-surface-1/50 text-[10px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
              <span />
              <span>Channel</span>
              <span className="text-center">Status</span>
              <span className="text-center">Done</span>
              <span className="text-center">Active</span>
              <span className="text-center">Weekly</span>
              <span className="text-center">On</span>
              <span className="text-right">Actions</span>
            </div>
            <div ref={channelListRef} className="divide-y divide-border">
              {displayChannels.map((ch: any) => {
                const isDisabled = ch.status !== 'active';
                const isArchived = ch.status === 'archived';
                const weeklyLabel = getWeeklyLabel(ch);
                const modes = getModes(ch);
                const isPinned = pinned.has(ch.channel_id);
                const aColor = avatarColor(ch.channel_id);
                const initials = avatarInitials(ch.channel_name);
                return (
                  <div key={ch.channel_id}
                    className={cn(
                      'px-4 py-3 grid grid-cols-[44px_1fr_100px_72px_72px_100px_56px_260px] items-center transition-colors group',
                      isArchived ? 'opacity-60 bg-surface-1/20' : isDisabled ? 'bg-surface-1/20' : 'hover:bg-surface-1/50',
                      isPinned && 'border-l-2 border-l-accent'
                    )}>
                    {/* Pin + avatar */}
                    <div className="flex items-center justify-start gap-1.5">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => togglePin(ch.channel_id)}
                        title={isPinned ? 'Unpin' : 'Pin'}
                        aria-label={isPinned ? 'Unpin channel' : 'Pin channel'}
                        className={cn('w-5 h-5 text-content-tertiary hover:text-accent', isPinned && 'text-accent')}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M12 17v5" /><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z" />
                        </svg>
                      </Button>
                    </div>

                    {/* Channel identity */}
                    <div className="flex items-center gap-2.5 min-w-0 pr-3">
                      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs shrink-0', aColor)}>
                        {initials}
                      </div>
                      <Link href={`/dashboard/channels/${ch.channel_id}`} className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-medium text-sm text-content-primary hover:text-accent truncate">{ch.channel_name}</span>
                          {ch.niche && <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">{ch.niche}</span>}
                          {modes.map((m: string) => (
                            <span key={m} className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium',
                              m === 'short' ? 'bg-violet-500/10 text-violet-500' : 'bg-blue-500/10 text-blue-500')}>
                              {m === 'short' ? 'S' : 'L'}
                            </span>
                          ))}
                          {ch.auto_upload && <span className="text-[10px] px-1 py-0.5 rounded bg-accent/10 text-accent">Auto</span>}
                          {isArchived && <span className="text-[10px] px-1 py-0.5 rounded bg-surface-3 text-content-tertiary">Archived</span>}
                        </div>
                        <div className="text-[10px] text-content-tertiary mt-0.5 font-mono truncate">{ch.channel_id}</div>
                      </Link>
                    </div>

                    {/* Status */}
                    <div className="text-center">
                      <span className={cn('text-xs font-medium',
                        ch.status === 'active' ? 'text-status-success' :
                        ch.status === 'archived' ? 'text-content-tertiary' : 'text-status-warning')}>
                        {ch.status === 'active' ? '● Active' : ch.status === 'archived' ? '⊘ Archived' : '○ Disabled'}
                      </span>
                    </div>

                    {/* Delivered */}
                    <div className="text-center text-sm font-semibold text-content-primary tabular-nums">{ch.stats?.delivered || 0}</div>

                    {/* In progress */}
                    <div className="text-center text-sm text-content-tertiary tabular-nums">{ch.stats?.in_progress || 0}</div>

                    {/* Weekly */}
                    <div className="text-center text-xs text-content-tertiary font-mono">{weeklyLabel || '—'}</div>

                    {/* Toggle */}
                    <div className="flex justify-center">
                      {isArchived ? <span className="text-[10px] text-content-tertiary">—</span> : (
                        <Toggle checked={ch.status === 'active'} onChange={() => toggleChannel(ch.channel_id, ch.status)} disabled={systemStopped} />
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-1.5">
                      {isArchived ? (
                        <>
                          <SimpleTooltip content="Restore to disabled">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => restoreChannel(ch.channel_id)}
                              className="h-7 px-2.5 text-[11px] text-accent bg-accent/5 border-accent/15 hover:bg-accent/10"
                            >
                              Restore
                            </Button>
                          </SimpleTooltip>
                          <Link href={`/dashboard/channels/${ch.channel_id}`}
                            className="h-7 px-2.5 border rounded-md text-[11px] font-medium text-content-tertiary bg-surface-1 border-border hover:bg-surface-2 transition-all flex items-center">
                            View
                          </Link>
                        </>
                      ) : (
                        <>
                          {(() => {
                            const hasRunning = modes.some((m: string) => ['running','paused'].includes(getModeState(ch, m)));
                            return (
                              <div className={cn('flex gap-1', hasRunning ? 'flex-col items-end' : 'items-center')}>
                                {modes.map((m: string) => {
                                  const mState = getModeState(ch, m);
                                  const mJob = getModeJob(ch, m);
                                  const atLimit = isModeAtLimit(ch, m);
                                  const mLabel = m === 'short' ? 'S' : 'L';
                                  if (mState === 'idle') {
                                    const canTrigger = !isDisabled && !systemStopped && !atLimit;
                                    return (
                                      <MagneticTriggerButton
                                        key={m}
                                        label={atLimit ? `${mLabel} Limit` : m === 'short' ? 'Short' : 'Long'}
                                        disabled={!canTrigger}
                                        onClick={() => triggerChannel(ch.channel_id, m)}
                                        compact
                                      />
                                    );
                                  }
                                  if (mState === 'pending_review' && mJob) return (
                                    <Link key={m} href={`/dashboard/jobs/${mJob.content_id}`}
                                      className="h-7 px-2.5 border rounded-md text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/30 hover:bg-status-warning/10 transition-all flex items-center">
                                      Review ({mLabel})
                                    </Link>
                                  );
                                  const isBusy = mJob && busyJobs.has(mJob.content_id);
                                  return (
                                    <div key={m} className="flex items-center gap-1">
                                      <ProgressRing paused={mState === 'paused'} />
                                      <span className="text-[10px] text-content-tertiary whitespace-nowrap">{mState === 'paused' ? 'Paused' : 'Running'} ({mLabel})</span>
                                      {mJob && (
                                        <>
                                          <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => togglePauseJob(ch.channel_id, mJob.content_id, mJob.is_paused)}
                                            disabled={!!isBusy}
                                            aria-label={mJob.is_paused ? 'Resume' : 'Pause'}
                                            className={cn('h-5 px-1.5 text-[10px]',
                                              mJob.is_paused ? 'text-accent border-accent/20 bg-accent/5' : 'text-status-warning border-status-warning/20 bg-status-warning/5')}
                                          >
                                            {isBusy ? '…' : mJob.is_paused ? '▶' : '⏸'}
                                          </Button>
                                          <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => stopJob(ch.channel_id, mJob.content_id)}
                                            disabled={!!isBusy}
                                            aria-label="Stop"
                                            className="h-5 px-1.5 text-[10px] text-status-error border-status-error/20 bg-status-error/5 hover:bg-status-error/10"
                                          >
                                            {isBusy ? '…' : '■'}
                                          </Button>
                                        </>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            );
                          })()}
                          <Link href={`/dashboard/channels/${ch.channel_id}`}
                            className="w-7 h-7 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary hover:text-accent transition-all">
                            <Settings size={12} />
                          </Link>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="outline" size="icon-sm" aria-label="More actions">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" /></svg>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-44">
                              <DropdownMenuItem onClick={() => cloneChannel(ch.channel_id)}>Duplicate Channel</DropdownMenuItem>
                              <DropdownMenuItem onClick={() => exportChannel(ch.channel_id)}>Export Config (JSON)</DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => setConfirmArchive(ch.channel_id)} className="text-status-warning focus:text-status-warning focus:bg-status-warning/5">Archive Channel</DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Archive confirm modal ── */}
      <Dialog open={!!confirmArchive} onOpenChange={(o) => { if (!o) setConfirmArchive(null); }}>
        <DialogContent size="sm">
          <DialogHeader>
            <div>
              <DialogTitle>Archive channel?</DialogTitle>
              <DialogDescription>
                <span className="font-medium text-content-secondary">{confirmArchive}</span> will be hidden from the active list.
                All configuration and history is preserved and can be restored.
              </DialogDescription>
            </div>
            <DialogCloseButton onClick={() => setConfirmArchive(null)} />
          </DialogHeader>
          <DialogBody>
            <DialogFooter>
              <Button variant="ghost" size="sm" onClick={() => setConfirmArchive(null)}>Cancel</Button>
              <Button
                size="sm"
                onClick={() => confirmArchive && archiveChannel(confirmArchive)}
                className="bg-status-warning hover:bg-status-warning/90 text-content-inverse"
              >
                Archive
              </Button>
            </DialogFooter>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
    </TooltipProvider>
  );
}

function ProgressRing({ paused }: { paused?: boolean }) {
  const r = 10; const c = 2 * Math.PI * r;
  return (
    <div className="relative w-6 h-6">
      <svg className={cn('w-6 h-6', !paused && 'animate-spin')} style={{ animationDuration: '2s' }} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor" className="text-surface-3" strokeWidth="2.5" />
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor" className={paused ? 'text-status-warning' : 'text-accent'} strokeWidth="2.5" strokeDasharray={c} strokeDashoffset={c * 0.3} strokeLinecap="round" />
      </svg>
      {paused && <div className="absolute inset-0 flex items-center justify-center"><div className="flex gap-0.5"><div className="w-0.5 h-2 bg-status-warning rounded-sm" /><div className="w-0.5 h-2 bg-status-warning rounded-sm" /></div></div>}
    </div>
  );
}

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <Switch
      checked={checked}
      onCheckedChange={disabled ? undefined : onChange}
      disabled={disabled}
      aria-label="Toggle channel"
    />
  );
}

function MagneticTriggerButton({
  label,
  disabled,
  onClick,
  compact = false,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  compact?: boolean;
}) {
  const reduce = useReducedMotion();
  const btnRef = useRef<HTMLDivElement>(null);
  const mx = useSpring(useMotionValue(0), { stiffness: 500, damping: 30 });
  const my = useSpring(useMotionValue(0), { stiffness: 500, damping: 30 });
  const [ripple, setRipple] = useState<{ x: number; y: number; id: number } | null>(null);

  const onMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduce || disabled || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    mx.set((e.clientX - (r.left + r.width / 2)) * 0.25);
    my.set((e.clientY - (r.top + r.height / 2)) * 0.25);
  };
  const onMouseLeave = () => { mx.set(0); my.set(0); };

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (!reduce) {
      const r = e.currentTarget.getBoundingClientRect();
      setRipple({ x: e.clientX - r.left, y: e.clientY - r.top, id: Date.now() });
      setTimeout(() => setRipple(null), 500);
    }
    onClick();
  };

  return (
    <motion.div
      ref={btnRef}
      className="flex-1"
      style={reduce ? undefined : { x: mx, y: my }}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
    >
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        className={cn(
          'relative overflow-hidden w-full h-7 text-[11px] font-medium rounded-md border px-2 flex items-center justify-center gap-1 transition-all select-none',
          disabled
            ? 'text-content-tertiary border-border bg-surface-2 cursor-not-allowed'
            : 'text-accent border-accent/30 bg-accent/5 hover:bg-accent/10 cursor-pointer',
        )}
      >
        <Play size={9} />
        {label}
        <AnimatePresence>
          {ripple && (
            <motion.span
              key={ripple.id}
              className="absolute rounded-full bg-accent/30 pointer-events-none"
              style={{ left: ripple.x, top: ripple.y, x: '-50%', y: '-50%', width: 8, height: 8 }}
              initial={{ scale: 0, opacity: 0.5 }}
              animate={{ scale: 12, opacity: 0 }}
              exit={{}}
              transition={{ duration: 0.45, ease: 'easeOut' }}
            />
          )}
        </AnimatePresence>
      </button>
    </motion.div>
  );
}
