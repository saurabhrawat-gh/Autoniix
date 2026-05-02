'use client';

import { useEffect, useState, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn, clearToken } from '@/lib/api';
import { cn, statusDot } from '@/lib/utils';
import { ThemeToggle } from '@/lib/theme';

type Tab = 'all' | 'active' | 'disabled' | 'archived';
type SortKey = 'name' | 'delivered' | 'status' | 'created';
type SortDir = 'asc' | 'desc';

function Tip({ text, children, pos = 'top' }: { text: string; children: React.ReactNode; pos?: 'top' | 'bottom' }) {
  return (
    <span className="has-tooltip inline-flex">
      {children}
      <span className={cn(
        'tooltip-text',
        pos === 'bottom' && '!bottom-auto !top-full !mt-1.5 !mb-0'
      )}>{text}</span>
    </span>
  );
}

const PINNED_KEY = 'yt_pinned_channels';
function loadPinned(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(PINNED_KEY) || '[]')); } catch { return new Set(); }
}
function savePinned(s: Set<string>) {
  localStorage.setItem(PINNED_KEY, JSON.stringify(Array.from(s)));
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<any>(null);
  const [allChannels, setAllChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pausedMap, setPausedMap] = useState<Record<string, boolean>>({});
  const [systemStopped, setSystemStopped] = useState(false);
  const [envMode, setEnvMode] = useState<string>('test');
  const [envSwitching, setEnvSwitching] = useState(false);
  const [showEnvConfirm, setShowEnvConfirm] = useState(false);
  const [actionMenu, setActionMenu] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState<string | null>(null);
  const [triggeringChannels, setTriggeringChannels] = useState<Set<string>>(new Set());
  const [busyChannels, setBusyChannels] = useState<Set<string>>(new Set());

  // New: tabs, search, sort, pin
  const [tab, setTab] = useState<Tab>('all');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [pinned, setPinned] = useState<Set<string>>(new Set());
  const [showSortMenu, setShowSortMenu] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout>();

  // Debounced search
  useEffect(() => {
    debounceRef.current && clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { debounceRef.current && clearTimeout(debounceRef.current); };
  }, [search]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    setPinned(loadPinned());
    loadData();
  }, [router]);

  async function loadData() {
    try {
      const [s, c] = await Promise.all([api.stats(), api.channels(true)]);
      setStats(s.data);
      setSystemStopped(s.data?.emergency_stop === true);
      setEnvMode(s.data?.environment_mode || 'test');
      setAllChannels(c.data || []);
      const paused: Record<string, boolean> = {};
      for (const ch of c.data || []) {
        if (ch.active_job) {
          try {
            const ws = await api.workflowStatus(ch.channel_id);
            paused[ch.channel_id] = ws.data?.is_paused || false;
          } catch { paused[ch.channel_id] = false; }
        }
      }
      setPausedMap(paused);
    } catch {}
    setLoading(false);
  }

  function togglePin(id: string) {
    setPinned(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      savePinned(next);
      return next;
    });
  }

  function cycleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  // Tab counts
  const tabCounts = useMemo(() => {
    const all = allChannels.length;
    const active = allChannels.filter(c => c.status === 'active').length;
    const disabled = allChannels.filter(c => c.status === 'disabled').length;
    const archived = allChannels.filter(c => c.status === 'archived').length;
    return { all, active, disabled, archived };
  }, [allChannels]);

  // Filtered + sorted channels
  const displayChannels = useMemo(() => {
    let list = [...allChannels];
    // Tab filter
    if (tab === 'active') list = list.filter(c => c.status === 'active');
    else if (tab === 'disabled') list = list.filter(c => c.status === 'disabled');
    else if (tab === 'archived') list = list.filter(c => c.status === 'archived');
    // Search filter
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase();
      list = list.filter(c =>
        c.channel_name?.toLowerCase().includes(q) ||
        c.channel_id?.toLowerCase().includes(q) ||
        c.niche?.toLowerCase().includes(q)
      );
    }
    // Sort
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = (a.channel_name || '').localeCompare(b.channel_name || '');
      else if (sortKey === 'delivered') cmp = (a.stats?.delivered || 0) - (b.stats?.delivered || 0);
      else if (sortKey === 'status') cmp = a.status.localeCompare(b.status);
      else if (sortKey === 'created') cmp = (a.created_at || '').localeCompare(b.created_at || '');
      return sortDir === 'desc' ? -cmp : cmp;
    });
    // Pinned on top
    const pinnedList = list.filter(c => pinned.has(c.channel_id));
    const unpinned = list.filter(c => !pinned.has(c.channel_id));
    return [...pinnedList, ...unpinned];
  }, [allChannels, tab, debouncedSearch, sortKey, sortDir, pinned]);

  async function switchEnvMode(target: string) {
    if (target === 'production') {
      setShowEnvConfirm(true);
      return;
    }
    setEnvSwitching(true);
    try {
      await api.switchEnvironment(target);
      setEnvMode(target);
      setShowEnvConfirm(false);
      loadData();
    } catch {}
    setEnvSwitching(false);
  }

  async function confirmProductionSwitch() {
    setEnvSwitching(true);
    try {
      await api.switchEnvironment('production', true);
      setEnvMode('production');
      setShowEnvConfirm(false);
      loadData();
    } catch {}
    setEnvSwitching(false);
  }

  async function toggleChannel(id: string, current: string) {
    try {
      if (current === 'active') await api.disableChannel(id);
      else await api.enableChannel(id);
      loadData();
    } catch {}
  }

  async function archiveChannel(id: string) {
    try { await api.archiveChannel(id); setConfirmArchive(null); loadData(); } catch {}
  }

  async function restoreChannel(id: string) {
    try { await api.restoreChannel(id); loadData(); } catch {}
  }

  async function cloneChannel(id: string) {
    try { await api.cloneChannel(id); setActionMenu(null); loadData(); } catch {}
  }

  async function exportChannel(id: string) {
    try {
      const res = await api.exportChannel(id);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `${id}-config.json`;
      a.click(); URL.revokeObjectURL(url);
      setActionMenu(null);
    } catch {}
  }

  async function triggerChannel(id: string, contentMode: string) {
    if (triggeringChannels.has(id)) return;
    setTriggeringChannels(prev => new Set(prev).add(id));
    try {
      await api.trigger(id, { content_mode: contentMode });
      await loadData();
    } catch {}
    setTriggeringChannels(prev => { const n = new Set(prev); n.delete(id); return n; });
  }

  async function togglePause(id: string) {
    if (busyChannels.has(id)) return;
    setBusyChannels(prev => new Set(prev).add(id));
    try {
      if (pausedMap[id]) {
        await api.resume(id);
        setPausedMap(prev => ({ ...prev, [id]: false }));
      } else {
        await api.pause(id);
        setPausedMap(prev => ({ ...prev, [id]: true }));
      }
    } catch {}
    setBusyChannels(prev => { const n = new Set(prev); n.delete(id); return n; });
  }

  async function stopChannel(id: string) {
    if (busyChannels.has(id)) return;
    setBusyChannels(prev => new Set(prev).add(id));
    try { await api.stop(id); await loadData(); } catch {}
    setBusyChannels(prev => { const n = new Set(prev); n.delete(id); return n; });
  }

  function getChannelState(ch: any): 'idle' | 'running' | 'paused' | 'pending_review' {
    if (triggeringChannels.has(ch.channel_id)) return 'running';
    if (!ch.active_job) return 'idle';
    if (pausedMap[ch.channel_id]) return 'paused';
    if (ch.active_job.status === 'pending_review') return 'pending_review';
    return 'running';
  }

  function getModes(ch: any): string[] {
    const raw = ch.content_mode || 'short';
    if (raw === 'both') return ['short', 'long_form'];
    return raw.split(',').map((m: string) => m.trim());
  }

  function isModeAtLimit(ch: any, mode: string): boolean {
    const u = ch.weekly_usage?.[mode];
    if (!u) return false;
    return u.used >= u.limit;
  }

  function isAllModesAtLimit(ch: any): boolean {
    return getModes(ch).every(m => isModeAtLimit(ch, m));
  }

  function getWeeklyLabel(ch: any): string | null {
    if (!ch.weekly_usage) return null;
    const parts: string[] = [];
    for (const m of getModes(ch)) {
      const u = ch.weekly_usage[m];
      if (!u) continue;
      const label = m === 'short' ? 'S' : 'L';
      parts.push(`${u.used}/${u.limit}${label}`);
    }
    return parts.join(' · ');
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'active', label: 'Active' },
    { key: 'disabled', label: 'Inactive' },
    { key: 'archived', label: 'Archived' },
  ];

  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: 'name', label: 'Name' },
    { key: 'delivered', label: 'Videos' },
    { key: 'status', label: 'Status' },
    { key: 'created', label: 'Created' },
  ];

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
    </div>
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* ── Fixed Header ── */}
      <header className="shrink-0 bg-surface-0 border-b border-border px-6 py-3">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between">
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
            <Tip text={envMode === 'test' ? 'Test mode: free/mock providers, no uploads' : 'Production mode: paid APIs, YouTube uploads'} pos="bottom">
              <div className="flex items-center gap-2">
                <span className={cn('text-xs font-semibold', envMode === 'test' ? 'text-amber-400' : 'text-content-tertiary')}>TEST</span>
                <button onClick={() => switchEnvMode(envMode === 'test' ? 'production' : 'test')} disabled={envSwitching}
                  className={cn('relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                    envMode === 'production' ? 'bg-emerald-500' : 'bg-amber-500', envSwitching && 'opacity-50 cursor-wait')}
                  role="switch" aria-checked={envMode === 'production'}>
                  <span className={cn('inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform',
                    envMode === 'production' ? 'translate-x-[18px]' : 'translate-x-[3px]')} />
                </button>
                <span className={cn('text-xs font-semibold', envMode === 'production' ? 'text-emerald-400' : 'text-content-tertiary')}>PROD</span>
              </div>
            </Tip>
            <ThemeToggle />
            <Tip text="View all running & failed jobs" pos="bottom">
              <Link href="/dashboard/progress" className="btn-secondary !py-2 !text-xs">Progress</Link>
            </Tip>
            <Tip text="System configuration & emergency stop" pos="bottom">
              <Link href="/dashboard/settings" className="btn-secondary !py-2 !text-xs">Settings</Link>
            </Tip>
            {systemStopped ? (
              <Tip text="Resume system from Settings to add channels" pos="bottom">
                <span className="btn-primary !py-2 !text-xs opacity-50 cursor-not-allowed">+ Add Channel</span>
              </Tip>
            ) : (
              <Tip text="Create a new YouTube channel entry" pos="bottom">
                <Link href="/dashboard/channels/new" className="btn-primary !py-2 !text-xs">+ Add Channel</Link>
              </Tip>
            )}
            <button onClick={() => { clearToken(); router.push('/login'); }} className="btn-ghost !text-xs" title="Sign out">Logout</button>
          </div>
        </div>
      </header>

      {/* ── Fixed Banners ── */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6">
        {showEnvConfirm && (
          <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-red-400">Switch to Production Mode?</h3>
                <p className="text-xs text-content-tertiary mt-1">
                  This will use <span className="text-red-400 font-medium">paid APIs</span>. Estimated cost: <span className="text-red-400 font-medium">$0.12–$0.35 per video</span>.
                </p>
              </div>
              <div className="flex gap-2 ml-4">
                <button onClick={() => setShowEnvConfirm(false)} className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-surface-2 transition-colors">Cancel</button>
                <button onClick={confirmProductionSwitch} disabled={envSwitching}
                  className="px-3 py-1.5 text-xs font-semibold bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50">
                  {envSwitching ? 'Switching…' : 'Confirm Production'}
                </button>
              </div>
            </div>
          </div>
        )}
        {envMode === 'test' && !systemStopped && (
          <div className="mt-4 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/15">
            <div className="flex items-center gap-2 text-xs text-amber-400">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span className="font-medium">Test Mode</span>
              <span className="text-content-tertiary">— Free/mock providers. No YouTube uploads.</span>
            </div>
          </div>
        )}
        {envMode === 'production' && !systemStopped && (
          <div className="mt-4 p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
            <div className="flex items-center gap-2 text-xs text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="font-medium">Production Mode</span>
              <span className="text-content-tertiary">— Paid APIs active. Videos uploaded to YouTube.</span>
            </div>
          </div>
        )}
        {systemStopped && (
          <div className="mt-4 p-3 rounded-lg bg-status-error/10 border border-status-error/20">
            <div className="flex items-center gap-3">
              <span className="text-status-error text-lg">■</span>
              <div>
                <h3 className="text-sm font-semibold text-status-error">System Inactive</h3>
                <p className="text-xs text-content-tertiary mt-0.5">
                  All operations frozen. <Link href="/dashboard/settings" className="text-accent hover:underline font-medium">Settings</Link> to resume.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Fixed Stats Row ── */}
      {stats && (
        <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Active Channels" value={stats.channels.active}
              sub={`${stats.channels.disabled} disabled · ${stats.channels.archived || 0} archived`}
              tooltip="Channels currently enabled for production" icon="channels" />
            <StatCard label="Videos Today" value={stats.today.videos_total}
              sub={`${stats.today.delivered} delivered · ${stats.today.in_progress} in progress`}
              tooltip="Videos created today across all channels" icon="videos" />
            <StatCard label="Cost Today" value={`$${stats.today.cost.toFixed(2)}`}
              sub={`Limit $${stats.budget.daily_limit}`}
              tooltip="Total API cost incurred today" icon="cost" />
            <StatCard label="System Status"
              value={stats.emergency_stop ? 'Stopped' : 'Active'}
              variant={stats.emergency_stop ? 'error' : 'success'}
              tooltip={stats.emergency_stop ? 'System frozen — Settings to resume' : 'All systems operational'} icon="system" />
          </div>
        </div>
      )}

      {/* ── Fixed Toolbar: Tabs + Search + Sort ── */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-4 pb-2">
        <div className="flex items-center justify-between gap-4">
          {/* Tabs */}
          <div className="flex items-center gap-1 bg-surface-1 rounded-lg p-0.5">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-all',
                  tab === t.key
                    ? 'bg-surface-0 text-content-primary shadow-sm'
                    : 'text-content-tertiary hover:text-content-secondary'
                )}>
                {t.label}
                <span className={cn('ml-1.5 text-[16px]', tab === t.key ? 'text-accent' : 'text-content-tertiary')}>
                  {tabCounts[t.key]}
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 flex-1 justify-end">
            {/* Search */}
            <div className="relative w-full max-w-sm">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search by name, ID, or niche…"
                className="w-full pl-9 pr-8 py-1.5 text-xs bg-surface-1 border border-border rounded-md text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30"
              />
              {search && (
                <button onClick={() => setSearch('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-primary text-xs">✕</button>
              )}
            </div>

            {/* Sort dropdown */}
            <div className="relative flex items-center gap-2">
              <span className="text-[14px] text-content-tertiary font-medium">Sort:</span>
              <button onClick={() => setShowSortMenu(!showSortMenu)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-1 border border-border rounded-md text-content-secondary hover:text-content-primary hover:border-border transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 3v18" /><path d="m3 7 4-4 4 4" />
                  <path d="M17 21V3" /><path d="m21 17-4 4-4-4" />
                </svg>
                <span>{SORT_OPTIONS.find(s => s.key === sortKey)?.label}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
                  {sortDir === 'asc'
                    ? <path d="M18 15l-6-6-6 6" />
                    : <path d="M6 9l6 6 6-6" />}
                </svg>
              </button>
              {showSortMenu && (
                <>
                  <div className="fixed inset-0 z-20" onClick={() => setShowSortMenu(false)} />
                  <div className="absolute right-0 top-9 z-30 w-40 bg-surface-0 border border-border rounded-md shadow-elevated py-1">
                    {SORT_OPTIONS.map(s => (
                      <button key={s.key}
                        onClick={() => { cycleSort(s.key); setShowSortMenu(false); }}
                        className={cn(
                          'w-full text-left px-3 py-2 text-xs transition-colors flex items-center justify-between',
                          sortKey === s.key
                            ? 'text-accent bg-accent/5 font-medium'
                            : 'text-content-secondary hover:bg-surface-1'
                        )}>
                        <span>{s.label}</span>
                        {sortKey === s.key && (
                          <span className="text-accent text-[10px] font-semibold">{sortDir === 'asc' ? '↑ Asc' : '↓ Desc'}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Scrollable Channel Table ── */}
      <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 pb-4">
        <div className={cn('card h-full flex flex-col overflow-hidden', systemStopped && 'lockdown-frost')}>
          {/* Table header */}
          <div className="shrink-0 px-4 py-2.5 flex items-center bg-surface-1/50 text-[11px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
            <span className="w-9"></span>
            <span className="flex-1 min-w-0">Channel</span>
            <span className="w-24 text-center">Status</span>
            <span className="w-20 text-center">Delivered</span>
            <span className="w-20 text-center">In Prog</span>
            <span className="w-24 text-center">Weekly</span>
            <span className="w-16 text-center">Enabled</span>
            <span className="w-64 text-right">Actions</span>
          </div>

          {/* Table body — scrollable */}
          <div className="flex-1 overflow-y-auto divide-y divide-border">
            {displayChannels.map((ch: any) => {
              const state = getChannelState(ch);
              const isDisabled = ch.status !== 'active';
              const isArchived = ch.status === 'archived';
              const allLimitReached = isAllModesAtLimit(ch);
              const weeklyLabel = getWeeklyLabel(ch);
              const modes = getModes(ch);
              const runningMode = ch.active_job?.content_mode;
              const isPinned = pinned.has(ch.channel_id);

              return (
                <div key={ch.channel_id} className={cn(
                  'px-4 py-3 flex items-start transition-colors group',
                  isArchived ? 'bg-surface-1/20 opacity-60' : isDisabled ? 'bg-surface-1/30' : 'hover:bg-surface-1/50',
                  isPinned && 'border-l-2 border-l-accent'
                )}>
                  {/* Pin */}
                  <button onClick={() => togglePin(ch.channel_id)} title={isPinned ? 'Unpin channel' : 'Pin to top'}
                    className={cn('w-9 shrink-0 flex items-center justify-center mt-1.5 text-content-tertiary hover:text-accent transition-colors',
                      isPinned && 'text-accent')}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 17v5" />
                      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z" />
                    </svg>
                  </button>

                  {/* Channel info */}
                  <div className="flex-1 min-w-0">
                    <Link href={`/dashboard/channels/${ch.channel_id}`} className="block">
                      <div className="flex items-center gap-2">
                        <span className={cn('w-2 h-2 rounded-full shrink-0', statusDot(ch.status))} />
                        <span className="font-medium text-sm text-content-primary truncate">{ch.channel_name}</span>
                        <span className="badge bg-surface-2 text-content-tertiary text-[10px]">{ch.niche}</span>
                        {modes.map((m: string) => (
                          <span key={m} className="badge bg-surface-2 text-content-tertiary text-[10px]">
                            {m === 'short' ? 'Short' : 'Long'}
                          </span>
                        ))}
                        {ch.auto_upload && <span className="badge bg-accent/10 text-accent text-[10px]">Auto-upload</span>}
                        {isDisabled && !isArchived ? (
                          ch.schedule_enabled ? null : null
                        ) : isArchived ? (
                          <span className="badge bg-surface-3 text-content-tertiary text-[10px]">Archived</span>
                        ) : ch.schedule_enabled ? (
                          <span className="badge bg-blue-500/10 text-blue-400 text-[10px]">Cron</span>
                        ) : null}
                      </div>
                      <div className="text-[10px] text-content-tertiary mt-0.5 ml-4">{ch.channel_id}</div>
                    </Link>
                  </div>

                  {/* Status */}
                  <div className="w-24 text-center self-center">
                    <span className={cn('text-xs font-medium',
                      ch.status === 'active' ? 'text-status-success' : ch.status === 'archived' ? 'text-content-tertiary' : 'text-status-warning'
                    )}>
                      {ch.status === 'active' ? 'Active' : ch.status === 'archived' ? 'Archived' : 'Disabled'}
                    </span>
                  </div>

                  {/* Delivered */}
                  <div className="w-20 text-center text-sm text-content-primary font-medium self-center">{ch.stats?.delivered || 0}</div>

                  {/* In Progress */}
                  <div className="w-20 text-center text-sm text-content-tertiary self-center">{ch.stats?.in_progress || 0}</div>

                  {/* Weekly */}
                  <div className="w-24 text-center text-sm text-content-tertiary self-center">{weeklyLabel || '—'}</div>

                  {/* Toggle */}
                  <div className="w-16 flex justify-center self-center">
                    {isArchived ? (
                      <span className="text-[10px] text-content-tertiary">—</span>
                    ) : (
                      <Toggle checked={ch.status === 'active'} onChange={() => toggleChannel(ch.channel_id, ch.status)} disabled={systemStopped} />
                    )}
                  </div>

                  {/* Actions */}
                  <div className="w-64 flex justify-end items-center gap-1.5 self-center">
                    {isArchived ? (
                      <>
                        <Tip text="Restore to disabled state">
                          <button onClick={() => restoreChannel(ch.channel_id)}
                            className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-accent bg-accent/5 border-accent/15 hover:bg-accent/10 transition-all">
                            Restore
                          </button>
                        </Tip>
                        <Tip text="View channel history">
                          <Link href={`/dashboard/channels/${ch.channel_id}`}
                            className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-content-tertiary bg-surface-1 border-border hover:bg-surface-2 transition-all">
                            View
                          </Link>
                        </Tip>
                      </>
                    ) : (
                      <>
                        {/* Trigger / Progress */}
                        {state === 'idle' ? (
                          modes.length > 1 ? (
                            modes.map((m: string) => {
                              const atLimit = isModeAtLimit(ch, m);
                              const canTrigger = !isDisabled && !systemStopped && !atLimit;
                              return (
                                <button key={m} onClick={() => triggerChannel(ch.channel_id, m)} disabled={!canTrigger}
                                  className={cn('px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                    canTrigger ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                      : 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50')}>
                                  {atLimit ? `${m === 'short' ? 'S' : 'L'} Limit` : `▶ ${m === 'short' ? 'Short' : 'Long'}`}
                                </button>
                              );
                            })
                          ) : (
                            <button onClick={() => triggerChannel(ch.channel_id, modes[0])} disabled={isDisabled || systemStopped || allLimitReached}
                              className={cn('px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all',
                                !isDisabled && !systemStopped && !allLimitReached
                                  ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                  : 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50')}>
                              {allLimitReached ? 'Limit' : 'Trigger'}
                            </button>
                          )
                        ) : state === 'pending_review' ? (
                          <Link href={`/dashboard/jobs/${ch.active_job?.content_id}`}
                            className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10 transition-all">
                            Review
                          </Link>
                        ) : (
                          <div className="flex items-center gap-1.5">
                            <ProgressRing paused={state === 'paused'} />
                            <span className="text-[10px] text-content-tertiary font-medium">
                              {state === 'paused' ? 'Paused' : 'Running'}
                              {runningMode && ` (${runningMode === 'short' ? 'S' : 'L'})`}
                            </span>
                          </div>
                        )}

                        {(state === 'running' || state === 'paused') && (
                          <button onClick={() => togglePause(ch.channel_id)} disabled={isDisabled || busyChannels.has(ch.channel_id)}
                            className={cn('px-2.5 py-1 border rounded-md text-[11px] font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed',
                              pausedMap[ch.channel_id]
                                ? 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
                                : 'text-status-warning bg-status-warning/5 border-status-warning/15 hover:bg-status-warning/10')}>
                            {busyChannels.has(ch.channel_id) ? '...' : (pausedMap[ch.channel_id] ? 'Resume' : 'Pause')}
                          </button>
                        )}
                        {(state === 'running' || state === 'paused') && (
                          <button onClick={() => stopChannel(ch.channel_id)} disabled={isDisabled || busyChannels.has(ch.channel_id)}
                            className="px-2.5 py-1 border rounded-md text-[11px] font-medium text-status-error bg-status-error/5 border-status-error/15 hover:bg-status-error/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                            {busyChannels.has(ch.channel_id) ? '...' : 'Stop'}
                          </button>
                        )}

                        {/* Settings gear */}
                        <Link href={`/dashboard/channels/${ch.channel_id}/settings`}
                          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-2 transition-all text-content-tertiary hover:text-accent"
                          title="Channel settings">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="3" />
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                          </svg>
                        </Link>

                        {/* More actions */}
                        <div className="relative">
                          <button onClick={() => setActionMenu(actionMenu === ch.channel_id ? null : ch.channel_id)}
                            className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-2 transition-all text-content-tertiary hover:text-content-primary"
                            title="More actions">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                              <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" />
                            </svg>
                          </button>
                          {actionMenu === ch.channel_id && (
                            <div className="absolute right-0 top-8 z-30 w-44 bg-surface-0 border border-border rounded-lg shadow-elevated py-1">
                              <button onClick={() => cloneChannel(ch.channel_id)}
                                className="w-full text-left px-3 py-2 text-xs text-content-secondary hover:bg-surface-1 transition-colors">Duplicate Channel</button>
                              <button onClick={() => exportChannel(ch.channel_id)}
                                className="w-full text-left px-3 py-2 text-xs text-content-secondary hover:bg-surface-1 transition-colors">Export Config (JSON)</button>
                              <div className="border-t border-border my-1" />
                              <button onClick={() => { setConfirmArchive(ch.channel_id); setActionMenu(null); }}
                                className="w-full text-left px-3 py-2 text-xs text-status-warning hover:bg-status-warning/5 transition-colors">Archive Channel</button>
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
              <div className="text-center py-16 text-content-tertiary text-sm">
                {debouncedSearch ? (
                  <>No channels match &ldquo;{debouncedSearch}&rdquo;</>
                ) : tab === 'archived' ? (
                  'No archived channels.'
                ) : (
                  <>No channels yet. <Link href="/dashboard/channels/new" className="text-accent hover:underline font-medium">Add your first channel</Link></>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Modals ── */}
      {confirmArchive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="card p-6 max-w-md w-full mx-4">
            <h3 className="text-sm font-semibold text-content-primary mb-2">Archive Channel?</h3>
            <p className="text-xs text-content-tertiary mb-4">
              <span className="font-medium text-content-secondary">{confirmArchive}</span> will be removed from the active list. Configuration and history preserved.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmArchive(null)} className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-surface-2 transition-colors">Cancel</button>
              <button onClick={() => archiveChannel(confirmArchive)} className="px-3 py-1.5 text-xs font-semibold bg-status-warning text-white rounded-lg hover:opacity-90 transition-colors">Archive</button>
            </div>
          </div>
        </div>
      )}
      {actionMenu && <div className="fixed inset-0 z-20" onClick={() => setActionMenu(null)} />}
    </div>
  );
}

/* ── Helper Components ─────────────────────────────────── */

function ProgressRing({ paused }: { paused?: boolean }) {
  const r = 10;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative w-6 h-6">
      <svg className={cn('w-6 h-6', !paused && 'animate-spin')} style={{ animationDuration: '2s' }} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor" className="text-surface-3" strokeWidth="2.5" />
        <circle cx="12" cy="12" r={r} fill="none" stroke="currentColor"
          className={paused ? 'text-status-warning' : 'text-accent'}
          strokeWidth="2.5" strokeDasharray={c} strokeDashoffset={c * 0.3} strokeLinecap="round" />
      </svg>
      {paused && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex gap-0.5">
            <div className="w-0.5 h-2 bg-status-warning rounded-sm" />
            <div className="w-0.5 h-2 bg-status-warning rounded-sm" />
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, variant, icon, tooltip }: {
  label: string; value: string | number; sub?: string; variant?: 'success' | 'error'; icon: string; tooltip?: string;
}) {
  const icons: Record<string, React.ReactNode> = {
    channels: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>,
    videos: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
    cost: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
    system: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  };
  return (
    <div className="card p-4" title={tooltip}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-medium text-content-tertiary uppercase tracking-wider">{label}</span>
        <span className="text-content-tertiary/50">{icons[icon]}</span>
      </div>
      <div className={cn('text-xl font-semibold',
        variant === 'error' ? 'text-status-error' : variant === 'success' ? 'text-status-success' : 'text-content-primary'
      )}>{value}</div>
      {sub && <div className="text-[10px] text-content-tertiary mt-1">{sub}</div>}
    </div>
  );
}

function Toggle({ checked, onChange, disabled, tooltip }: { checked: boolean; onChange: () => void; disabled?: boolean; tooltip?: string }) {
  const btn = (
    <button onClick={disabled ? undefined : onChange} disabled={disabled}
      className={cn('relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none',
        checked ? 'bg-accent' : 'bg-surface-3', disabled && 'opacity-50 cursor-not-allowed')}>
      <span className={cn('inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform',
        checked ? 'translate-x-[18px]' : 'translate-x-[2px]')} />
    </button>
  );
  if (tooltip) return <Tip text={tooltip}>{btn}</Tip>;
  return btn;
}
