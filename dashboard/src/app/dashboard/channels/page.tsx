'use client';

import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { api, isLoggedIn, wsEvents } from '@/lib/api';
import { cn, statusDot } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { Skeleton, SkeletonCard } from '@/lib/components/Skeleton';
import { EmptyState } from '@/lib/components/EmptyState';
import { Tip } from '@/lib/components/Tooltip';
import { Plus, ChevronUp, ChevronDown } from '@/lib/components/Icon';
import { useUrlState } from '@/lib/hooks/useUrlState';

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
  const debounceRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    debounceRef.current && clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { debounceRef.current && clearTimeout(debounceRef.current); };
  }, [search]);

  const loadData = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.stats(), api.channels(true)]);
      setSystemStopped(s.data?.emergency_stop === true);
      setAllChannels(c.data || []);
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
      if (current === 'active') await api.disableChannel(id);
      else await api.enableChannel(id);
      loadData();
    } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Toggle failed', 'error'); }
  }

  async function archiveChannel(id: string) {
    const snapshot = allChannels;
    const name = allChannels.find(c => c.channel_id === id)?.channel_name || 'channel';
    setAllChannels(prev => prev.map(c => c.channel_id === id ? { ...c, status: 'archived' } : c));
    setConfirmArchive(null);
    try {
      await api.archiveChannel(id);
      showToast(`${name} archived`, { variant: 'info', duration: 6000, action: { label: 'Undo', onAct: async () => { await api.restoreChannel(id); loadData(); } } });
      loadData();
    } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Archive failed', 'error'); }
  }

  async function restoreChannel(id: string) {
    const snapshot = allChannels;
    setAllChannels(prev => prev.map(c => c.channel_id === id ? { ...c, status: 'disabled' } : c));
    try { await api.restoreChannel(id); loadData(); } catch (e: any) { setAllChannels(snapshot); showToast(e?.message || 'Restore failed', 'error'); }
  }

  async function cloneChannel(id: string) {
    try { await api.cloneChannel(id); setActionMenu(null); loadData(); } catch (e: any) { showToast(e?.message || 'Clone failed', 'error'); }
  }

  async function exportChannel(id: string) {
    try {
      const res = await api.exportChannel(id);
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
    try { await api.trigger(id, { content_mode: contentMode }); await loadData(); } catch (e: any) { showToast(e?.message || 'Trigger failed', 'error'); }
    setTriggeringKeys(prev => { const n = new Set(prev); n.delete(key); return n; });
  }

  async function togglePauseJob(contentId: string, isPaused: boolean) {
    if (busyJobs.has(contentId)) return;
    setBusyJobs(prev => new Set(prev).add(contentId));
    try { if (isPaused) await api.resumeJob(contentId); else await api.pauseJob(contentId); await loadData(); } catch (e: any) { showToast(e?.message || 'Action failed', 'error'); }
    setBusyJobs(prev => { const n = new Set(prev); n.delete(contentId); return n; });
  }

  async function stopJob(contentId: string) {
    if (busyJobs.has(contentId)) return;
    setBusyJobs(prev => new Set(prev).add(contentId));
    try { await api.stopJob(contentId); await loadData(); } catch (e: any) { showToast(e?.message || 'Stop failed', 'error'); }
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
    if (raw === 'both') return ['short', 'long_form'];
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

  if (loading) return (
    <div className="flex-1 flex flex-col">
      <div className="max-w-[1400px] mx-auto w-full px-6 py-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-5 pb-3">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-1 bg-surface-1 rounded-md p-0.5">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cn('px-3 py-1.5 text-sm font-medium rounded transition-all',
                  tab === t.key ? 'bg-surface-0 text-content-primary shadow-sm' : 'text-content-tertiary hover:text-content-secondary')}>
                {t.label}
                <span className={cn('ml-1.5 text-[11px]', tab === t.key ? 'text-accent' : 'text-content-tertiary')}>
                  {tabCounts[t.key]}
                </span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-80">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search by name, ID, niche…"
                className="w-full pl-9 pr-8 py-2 text-xs bg-surface-0 border border-border rounded-lg text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30 transition-shadow" />
              {search && <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-primary text-xs w-5 h-5 flex items-center justify-center rounded-md hover:bg-surface-2 transition-colors">✕</button>}
            </div>
            <div className="relative">
              <button onClick={() => setShowSortMenu(!showSortMenu)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium bg-surface-1 border border-border rounded-md text-content-secondary hover:text-content-primary transition-colors">
                <span className="text-content-tertiary">Sort</span>
                <span className="text-content-primary">{SORT_OPTIONS.find(s => s.key === sortKey)?.label}</span>
                <span className="text-accent">{sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
              </button>
              {showSortMenu && (
                <>
                  <div className="fixed inset-0 z-20" onClick={() => setShowSortMenu(false)} />
                  <div className="absolute right-0 top-9 z-30 w-40 bg-surface-0 border border-border rounded-md shadow-elevated py-1">
                    {SORT_OPTIONS.map(s => (
                      <button key={s.key} onClick={() => { cycleSort(s.key); setShowSortMenu(false); }}
                        className={cn('w-full text-left px-3 py-2 text-xs transition-colors flex items-center justify-between',
                          sortKey === s.key ? 'text-accent bg-accent/5 font-medium' : 'text-content-secondary hover:bg-surface-1')}>
                        <span>{s.label}</span>
                        {sortKey === s.key && <span className="text-accent flex items-center gap-0.5">{sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />} <span className="text-[10px] font-semibold">{sortDir === 'asc' ? 'Asc' : 'Desc'}</span></span>}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Channel table */}
      <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 pb-4">
        <div className={cn('card h-full flex flex-col overflow-hidden', systemStopped && 'lockdown-frost')}>
          <div className="shrink-0 px-4 py-2.5 flex items-center bg-surface-1/50 text-[11px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
            <span className="w-9"></span>
            <span className="flex-1 min-w-0">Channel</span>
            <span className="w-24 text-center">Status</span>
            <span className="w-20 text-center">Delivered</span>
            <span className="w-20 text-center">In Prog</span>
            <span className="w-24 text-center">Weekly</span>
            <span className="w-16 text-center">On</span>
            <span className="w-64 text-right">Actions</span>
          </div>

          <div ref={channelListRef} className="flex-1 overflow-y-auto divide-y divide-border">
            {displayChannels.map((ch: any) => {
              const isDisabled = ch.status !== 'active';
              const isArchived = ch.status === 'archived';
              const weeklyLabel = getWeeklyLabel(ch);
              const modes = getModes(ch);
              const isPinned = pinned.has(ch.channel_id);
              return (
                <div key={ch.channel_id} className={cn(
                  'px-4 py-3 flex items-start transition-colors group',
                  isArchived ? 'bg-surface-1/20 opacity-60' : isDisabled ? 'bg-surface-1/30' : 'hover:bg-surface-1/50',
                  isPinned && 'border-l-2 border-l-accent'
                )}>
                  <button onClick={() => togglePin(ch.channel_id)} title={isPinned ? 'Unpin' : 'Pin to top'}
                    className={cn('w-9 shrink-0 flex items-center justify-center mt-1.5 text-content-tertiary hover:text-accent transition-colors', isPinned && 'text-accent')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 17v5" /><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z" />
                    </svg>
                  </button>
                  <div className="flex-1 min-w-0">
                    <Link href={`/dashboard/channels/${ch.channel_id}`} className="block">
                      <div className="flex items-center gap-2">
                        <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', statusDot(ch.status))} />
                        <span className="font-medium text-sm text-content-primary truncate">{ch.channel_name}</span>
                        <span className="badge bg-surface-2 text-content-tertiary text-[10px]">{ch.niche}</span>
                        {modes.map((m: string) => <span key={m} className="badge bg-surface-2 text-content-tertiary text-[10px]">{m === 'short' ? 'Short' : 'Long'}</span>)}
                        {ch.auto_upload && <span className="badge bg-accent/10 text-accent text-[10px]">Auto</span>}
                        {isArchived && <span className="badge bg-surface-3 text-content-tertiary text-[10px]">Archived</span>}
                      </div>
                      <div className="text-[10px] text-content-tertiary mt-0.5 ml-3.5">{ch.channel_id}</div>
                    </Link>
                  </div>
                  <div className="w-24 text-center self-center">
                    <span className={cn('text-xs font-medium', ch.status === 'active' ? 'text-status-success' : ch.status === 'archived' ? 'text-content-tertiary' : 'text-status-warning')}>
                      {ch.status === 'active' ? 'Active' : ch.status === 'archived' ? 'Archived' : 'Disabled'}
                    </span>
                  </div>
                  <div className="w-20 text-center text-sm text-content-primary font-medium self-center">{ch.stats?.delivered || 0}</div>
                  <div className="w-20 text-center text-sm text-content-tertiary self-center">{ch.stats?.in_progress || 0}</div>
                  <div className="w-24 text-center text-xs text-content-tertiary self-center">{weeklyLabel || '—'}</div>
                  <div className="w-16 flex justify-center self-center">
                    {isArchived ? <span className="text-[10px] text-content-tertiary">—</span> : (
                      <Toggle checked={ch.status === 'active'} onChange={() => toggleChannel(ch.channel_id, ch.status)} disabled={systemStopped} />
                    )}
                  </div>
                  <div className="min-w-[16rem] flex justify-end items-start gap-1.5 self-center">
                    {isArchived ? (
                      <>
                        <Tip text="Restore to disabled"><button onClick={() => restoreChannel(ch.channel_id)} className="px-2.5 py-1 border rounded text-[11px] font-medium text-accent bg-accent/5 border-accent/15 hover:bg-accent/10 transition-all">Restore</button></Tip>
                        <Link href={`/dashboard/channels/${ch.channel_id}`} className="px-2.5 py-1 border rounded text-[11px] font-medium text-content-tertiary bg-surface-1 border-border hover:bg-surface-2 transition-all">View</Link>
                      </>
                    ) : (
                      <>
                        {(() => {
                          const hasRunning = modes.some((m: string) => ['running','paused'].includes(getModeState(ch, m)));
                          return (
                            <div className={cn('flex gap-1.5', hasRunning ? 'flex-col items-end' : 'items-center')}>
                              {modes.map((m: string) => {
                                const mState = getModeState(ch, m);
                                const mJob = getModeJob(ch, m);
                                const atLimit = isModeAtLimit(ch, m);
                                const mLabel = m === 'short' ? 'S' : 'L';
                                if (mState === 'idle') {
                                  const canTrigger = !isDisabled && !systemStopped && !atLimit;
                                  return <button key={m} onClick={() => triggerChannel(ch.channel_id, m)} disabled={!canTrigger}
                                    className={cn('px-2.5 py-1 border rounded text-[11px] font-medium transition-all',
                                      canTrigger ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10' : 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50')}>
                                    {atLimit ? `${mLabel} Limit` : `▶ ${m === 'short' ? 'Short' : 'Long'}`}
                                  </button>;
                                }
                                if (mState === 'pending_review' && mJob) return <Link key={m} href={`/dashboard/jobs/${mJob.content_id}`} className="px-2.5 py-1 border rounded text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all">Review ({mLabel})</Link>;
                                const isBusy = mJob && busyJobs.has(mJob.content_id);
                                return <div key={m} className="flex items-center gap-1">
                                  <ProgressRing paused={mState === 'paused'} />
                                  <span className="text-[10px] text-content-tertiary font-medium whitespace-nowrap">{mState === 'paused' ? 'Paused' : 'Running'} ({mLabel})</span>
                                  {mJob && <>
                                    <button onClick={() => togglePauseJob(mJob.content_id, mJob.is_paused)} disabled={isBusy as boolean}
                                      className={cn('px-1.5 py-0.5 border rounded text-[10px] font-medium transition-all disabled:opacity-50',
                                        mJob.is_paused ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10' : 'text-status-warning bg-status-warning/5 border-status-warning/15')}>
                                      {isBusy ? '...' : (mJob.is_paused ? '▶' : '⏸')}
                                    </button>
                                    <button onClick={() => stopJob(mJob.content_id)} disabled={isBusy as boolean}
                                      className="px-1.5 py-0.5 border rounded text-[10px] font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all disabled:opacity-50">
                                      {isBusy ? '...' : '■'}
                                    </button>
                                  </>}
                                </div>;
                              })}
                            </div>
                          );
                        })()}
                        <Link href={`/dashboard/channels/${ch.channel_id}`}
                          className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 transition-all text-content-tertiary hover:text-accent" title="Settings">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
                        </Link>
                        <div className="relative">
                          <button onClick={() => setActionMenu(actionMenu === ch.channel_id ? null : ch.channel_id)}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 transition-all text-content-tertiary hover:text-content-primary" title="More">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" /></svg>
                          </button>
                          {actionMenu === ch.channel_id && (
                            <div className="absolute right-0 top-8 z-30 w-44 bg-surface-0 border border-border rounded-md shadow-elevated py-1">
                              <button onClick={() => cloneChannel(ch.channel_id)} className="w-full text-left px-3 py-2 text-xs text-content-secondary hover:bg-surface-1">Duplicate Channel</button>
                              <button onClick={() => exportChannel(ch.channel_id)} className="w-full text-left px-3 py-2 text-xs text-content-secondary hover:bg-surface-1">Export Config (JSON)</button>
                              <div className="border-t border-border my-1" />
                              <button onClick={() => { setConfirmArchive(ch.channel_id); setActionMenu(null); }} className="w-full text-left px-3 py-2 text-xs text-status-warning hover:bg-status-warning/5">Archive Channel</button>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
            {displayChannels.length === 0 && (
              <div className="p-6">
                {debouncedSearch ? (
                  <EmptyState title={`No channels match "${debouncedSearch}"`} body="Try a different search or clear filters." />
                ) : tab === 'archived' ? (
                  <EmptyState title="No archived channels" body="Channels you archive will appear here." />
                ) : (
                  <EmptyState icon={Plus} title="No channels yet" body="Create your first YouTube channel to start producing videos automatically."
                    cta={{ label: 'Add your first channel', href: '/dashboard/channels/new' }} />
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {confirmArchive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="card p-6 max-w-md w-full mx-4">
            <h3 className="text-sm font-semibold text-content-primary mb-2">Archive Channel?</h3>
            <p className="text-xs text-content-tertiary mb-4"><span className="font-medium text-content-secondary">{confirmArchive}</span> will be removed from the active list. Configuration and history preserved.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmArchive(null)} className="px-3 py-1.5 text-xs font-medium border border-border rounded hover:bg-surface-2">Cancel</button>
              <button onClick={() => archiveChannel(confirmArchive)} className="px-3 py-1.5 text-xs font-semibold bg-status-warning text-white rounded hover:opacity-90">Archive</button>
            </div>
          </div>
        </div>
      )}
      {actionMenu && <div className="fixed inset-0 z-20" onClick={() => setActionMenu(null)} />}
    </div>
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
    <button onClick={disabled ? undefined : onChange} disabled={disabled}
      className={cn('relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none',
        checked ? 'bg-accent' : 'bg-surface-3', disabled && 'opacity-50 cursor-not-allowed')}>
      <span className={cn('inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform', checked ? 'translate-x-[18px]' : 'translate-x-[2px]')} />
    </button>
  );
}
