'use client';

import React, { useEffect, useState, useMemo, useCallback, useDeferredValue } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { contentApi, channelsApi, jobsApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, X, Play, Download, Link2, AlertTriangle,
  Wrench, Clock, ClipboardCheck, Clapperboard, Layers,
  CalendarDays, BarChart2, ChevronLeft, ChevronRight,
  Loader2, CheckSquare, Zap, RotateCw,
  Film, ExternalLink, TrendingUp,
} from '@/lib/components/Icon';

const STATUS_CHIP: Record<string, string> = {
  completed:  'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  published:  'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  delivered:  'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  failed:     'bg-red-500/15 text-red-600 dark:text-red-400',
  stopped:    'bg-orange-500/15 text-orange-600 dark:text-orange-400',
  pending:    'bg-surface-3 text-content-tertiary',
  running:    'bg-accent/15 text-accent',
  archived:   'bg-surface-3 text-content-tertiary',
  superseded: 'bg-surface-3 text-content-tertiary',
};

const REVIEW_CHIP: Record<string, string> = {
  approved:       'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  rejected:       'bg-red-500/15 text-red-600 dark:text-red-400',
  needs_edits:    'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  pending:        'bg-amber-500/15 text-amber-500',
  regenerating:   'bg-accent/15 text-accent',
};

const STATUS_OPTIONS = ['pending','running','completed','failed','published','archived','stopped','superseded'];
const REVIEW_OPTIONS = ['pending','approved','needs_edits','rejected','regenerating'];
const MODE_OPTIONS   = ['short','long_form'];

const DATE_RANGES = [
  { key: 'all', label: 'All time' },
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'current_week', label: 'Current week' },
  { key: 'last_week', label: 'Last week' },
  { key: 'current_month', label: 'Current month' },
  { key: 'last_month', label: 'Last month' },
];

const SORT_OPTIONS = [
  { key: 'created_at', label: 'Created' },
  { key: 'title', label: 'Title' },
  { key: 'authenticity_score', label: 'Score' },
  { key: 'status', label: 'Status' },
];

/* ─── date helpers ─── */
function isInDateRange(dateStr: string, range: string): boolean {
  if (range === 'all') return true;
  const date = new Date(dateStr);
  const now = new Date();
  const sod = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  switch (range) {
    case 'today':
      return date >= sod;
    case 'yesterday': {
      const y = new Date(sod); y.setDate(y.getDate() - 1);
      return date >= y && date < sod;
    }
    case 'current_week': {
      const w = new Date(sod); w.setDate(w.getDate() - w.getDay());
      return date >= w;
    }
    case 'last_week': {
      const cw = new Date(sod); cw.setDate(cw.getDate() - cw.getDay());
      const lw = new Date(cw); lw.setDate(lw.getDate() - 7);
      return date >= lw && date < cw;
    }
    case 'current_month':
      return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
    case 'last_month': {
      const lm = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      return date.getMonth() === lm.getMonth() && date.getFullYear() === lm.getFullYear();
    }
    default:
      return true;
  }
}

type Tab = 'pipeline' | 'calendar' | 'stats';

/* ─── main ─── */
export default function ContentPage() {
  // ── core ──────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>('pipeline');
  const [channels, setChannels] = useState<any[]>([]);
  const { showToast } = useToast();
  const searchParams = useSearchParams();

  // ── pipeline ───────────────────────────────────────────────────────────────
  const [allItems, setAllItems] = useState<any[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');
  const deferredQ = useDeferredValue(q);
  const [searchHits, setSearchHits] = useState<any[] | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selChannels, setSelChannels] = useState<string[]>([]);
  const [selStatuses, setSelStatuses] = useState<string[]>([]);
  const [selReviews, setSelReviews] = useState<string[]>([]);
  const [selModes, setSelModes] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState('all');
  const [channelSearch, setChannelSearch] = useState('');
  const [sortKey, setSortKey] = useState('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [showSort, setShowSort] = useState(false);

  // ── bulk selection ─────────────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // ── detail drawer ──────────────────────────────────────────────────────────
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ── preview modal ──────────────────────────────────────────────────────────
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewMeta, setPreviewMeta] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // ── calendar ───────────────────────────────────────────────────────────────
  const [calDate, setCalDate] = useState(() => {
    const d = new Date(); d.setDate(1); return d;
  });
  const [calData, setCalData] = useState<Record<string, any[]>>({});
  const [calLoading, setCalLoading] = useState(false);

  // ── stats ──────────────────────────────────────────────────────────────────
  const [statsData, setStatsData] = useState<{ buckets: any[]; by_channel: any[] } | null>(null);
  const [statsPeriod, setStatsPeriod] = useState<'day' | 'week' | 'month'>('week');
  const [statsLoading, setStatsLoading] = useState(false);

  // ── trigger modal ──────────────────────────────────────────────────────────
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [trigChannel, setTrigChannel] = useState('');
  const [trigMode, setTrigMode] = useState('long_form');
  const [trigTopic, setTrigTopic] = useState('');
  const [triggering, setTriggering] = useState(false);

  // ── bootstrap ─────────────────────────────────────────────────────────────
  useEffect(() => {
    channelsApi.list(false).then(r => {
      const chs = r.data || [];
      setChannels(chs);
      if (chs.length > 0) setTrigChannel(chs[0].channel_id);
    });
  }, []);

  useEffect(() => {
    if (!searchParams) return;
    const rs = searchParams.get('review_state');
    const st = searchParams.get('status');
    const cm = searchParams.get('content_mode');
    const ch = searchParams.get('channel_id');
    if (rs) setSelReviews(rs.split(',').filter(Boolean));
    if (st) setSelStatuses(st.split(',').filter(Boolean));
    if (cm) setSelModes(cm.split(',').filter(Boolean));
    if (ch) setSelChannels(ch.split(',').filter(Boolean));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── data loaders ───────────────────────────────────────────────────────────
  const fetchPage = useCallback(async (replace = true) => {
    setLoading(true);
    try {
      const r = await contentApi.list({ cursor: replace ? undefined : cursor || undefined, limit: 60 });
      setCursor(r.data.next_cursor);
      const fetched = (r.data.groups || []).flatMap((g: any) => g.items || []);
      setAllItems(prev => replace ? fetched : [...prev, ...fetched]);
    } finally { setLoading(false); }
  }, [cursor]);

  useEffect(() => { fetchPage(true); }, []); // eslint-disable-line

  useEffect(() => {
    if (deferredQ.length < 2) { setSearchHits(null); return; }
    const t = setTimeout(() => contentApi.search(deferredQ).then(r => setSearchHits(r.data)), 300);
    return () => clearTimeout(t);
  }, [deferredQ]);

  const loadCalendar = useCallback(async () => {
    setCalLoading(true);
    const y = calDate.getFullYear(), m = calDate.getMonth();
    const start = `${y}-${String(m + 1).padStart(2, '0')}-01`;
    const end   = new Date(y, m + 1, 1).toISOString().slice(0, 10);
    try {
      const r = await contentApi.calendar(start, end);
      setCalData(r.data || {});
    } catch { setCalData({}); }
    setCalLoading(false);
  }, [calDate]);

  useEffect(() => { if (activeTab === 'calendar') loadCalendar(); }, [activeTab, loadCalendar]);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const r = await contentApi.stats(undefined, statsPeriod);
      setStatsData(r.data);
    } catch { setStatsData(null); }
    setStatsLoading(false);
  }, [statsPeriod]);

  useEffect(() => { if (activeTab === 'stats') loadStats(); }, [activeTab, loadStats]);

  const openDetail = async (contentId: string) => {
    setDetailId(contentId);
    setDetailLoading(true);
    try {
      const r = await contentApi.detail(contentId);
      setDetailData(r.data);
    } catch { setDetailData(null); }
    setDetailLoading(false);
  };

  // ── pipeline derived state ─────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const base = searchHits ?? allItems;
    return base
      .filter((v: any) => {
        if (selChannels.length > 0 && !selChannels.includes(v.channel_id)) return false;
        if (selStatuses.length > 0 && !selStatuses.includes(v.status)) return false;
        if (selReviews.length > 0 && !selReviews.includes(v.review_state)) return false;
        if (selModes.length > 0 && !selModes.includes(v.content_mode)) return false;
        if (dateRange !== 'all' && !isInDateRange(v.created_at, dateRange)) return false;
        return true;
      })
      .sort((a: any, b: any) => {
        let cmp = 0;
        switch (sortKey) {
          case 'title':      cmp = (a.title || a.topic || '').localeCompare(b.title || b.topic || ''); break;
          case 'authenticity_score': cmp = (a.authenticity_score ?? 0) - (b.authenticity_score ?? 0); break;
          case 'status':     cmp = (a.status || '').localeCompare(b.status || ''); break;
          default:           cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        }
        return sortDir === 'asc' ? cmp : -cmp;
      });
  }, [allItems, searchHits, selChannels, selStatuses, selReviews, selModes, dateRange, sortKey, sortDir]);

  const activeFilterCount = selChannels.length + selStatuses.length + selReviews.length + selModes.length + (dateRange !== 'all' ? 1 : 0);

  const pipelineStats = useMemo(() => ({
    total:     allItems.length,
    running:   allItems.filter(v => v.status === 'running').length,
    pending:   allItems.filter(v => v.status === 'pending').length,
    review:    allItems.filter(v => v.review_state === 'pending').length,
    completed: allItems.filter(v => ['completed','published','delivered'].includes(v.status)).length,
    failed:    allItems.filter(v => v.status === 'failed').length,
  }), [allItems]);

  // ── actions ────────────────────────────────────────────────────────────────
  const openPreview = async (contentId: string) => {
    setPreviewId(contentId);
    setPreviewLoading(true);
    try {
      const output = await jobsApi.output(contentId).catch(() => null);
      const meta = await jobsApi.metadata(contentId).catch(() => null);
      setPreviewMeta(meta?.data ?? null);
      setPreviewUrl(output?.data?.video_url || null);
    } catch { setPreviewUrl(null); }
    finally { setPreviewLoading(false); }
  };

  const handleDownload = async (v: any) => {
    try {
      const output = await jobsApi.output(v.content_id).catch(() => null);
      const url = (output as any)?.data?.video_url || (output as any)?.url || (output as any)?.video_url;
      if (!url) { showToast('Video not yet available', 'error'); return; }
      const a = document.createElement('a');
      a.href = url; a.download = `${v.title || v.content_id}.mp4`; a.target = '_blank';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } catch { showToast('Download failed', 'error'); }
  };

  const handleExportDaVinci = (v: any) => {
    const payload = {
      title: v.title || v.topic || v.content_id, topic: v.topic,
      channel_id: v.channel_id,
      channel_name: channels.find(c => c.channel_id === v.channel_id)?.channel_name || v.channel_id,
      content_id: v.content_id, content_mode: v.content_mode,
      status: v.status, review_state: v.review_state,
      created_at: v.created_at, authenticity_score: v.authenticity_score,
      notes: 'Import into DaVinci Resolve Media Pool as clip metadata.',
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${v.content_id}_davinci.json`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('DaVinci Resolve metadata exported', 'success');
  };

  const clearFilters = () => {
    setSelChannels([]); setSelStatuses([]); setSelReviews([]); setSelModes([]);
    setDateRange('all'); setChannelSearch('');
  };

  const handleBulk = async (action: string) => {
    if (selectedIds.size === 0) return;
    try {
      const r = await contentApi.bulk(action, Array.from(selectedIds));
      showToast(`${action}: ${r.affected} item(s) updated`, 'success');
      setSelectedIds(new Set());
      fetchPage(true);
    } catch (e: any) { showToast(e?.message || `${action} failed`, 'error'); }
  };

  const handleTrigger = async () => {
    if (!trigChannel) { showToast('Select a channel', 'error'); return; }
    setTriggering(true);
    try {
      const r = await contentApi.trigger({ channel_id: trigChannel, content_mode: trigMode, topic_hint: trigTopic || undefined });
      showToast(r.status === 'ok' ? `Generation started · ${r.content_id}` : 'Queued (will start shortly)', 'success');
      setTriggerOpen(false);
      setTrigTopic('');
      setTimeout(() => fetchPage(true), 2000);
    } catch (e: any) { showToast(e?.message || 'Trigger failed', 'error'); }
    finally { setTriggering(false); }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set());
    else setSelectedIds(new Set<string>(filtered.map((v: any) => v.content_id as string)));
  };

  // ── calendar helpers ───────────────────────────────────────────────────────
  const calDays = useMemo(() => {
    const y = calDate.getFullYear(), m = calDate.getMonth();
    const first = new Date(y, m, 1).getDay();
    const days: Array<{ date: Date; iso: string } | null> = [];
    for (let i = 0; i < first; i++) days.push(null);
    const total = new Date(y, m + 1, 0).getDate();
    for (let d = 1; d <= total; d++) {
      const dt = new Date(y, m, d);
      days.push({ date: dt, iso: dt.toISOString().slice(0, 10) });
    }
    return days;
  }, [calDate]);

  const calMonthLabel = calDate.toLocaleString('default', { month: 'long', year: 'numeric' });

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex-1 flex flex-col overflow-hidden">

      {/* ── Toolbar ── */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-5 pb-0">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <div>
            <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
              <Clapperboard size={18} className="text-accent" /> Content Pipeline
            </h1>
            <p className="text-xs text-content-tertiary mt-0.5">Manage, review, and trigger video generation.</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setTriggerOpen(true)}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
              <Zap size={12} /> Generate
            </button>
            <button onClick={() => fetchPage(true)} disabled={loading}
              className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
              <RotateCw size={13} className={cn(loading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-border">
          {([
            { key: 'pipeline', label: 'Pipeline', icon: <Layers size={13} /> },
            { key: 'calendar', label: 'Calendar', icon: <CalendarDays size={13} /> },
            { key: 'stats',    label: 'Stats',    icon: <BarChart2 size={13} /> },
          ] as { key: Tab; label: string; icon: React.ReactNode }[]).map(t => (
            <button key={t.key} onClick={() => setActiveTab(t.key)}
              className={cn(
                'flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-colors -mb-px',
                activeTab === t.key
                  ? 'border-accent text-accent'
                  : 'border-transparent text-content-tertiary hover:text-content-secondary hover:border-border'
              )}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Pipeline tab ── */}
      {activeTab === 'pipeline' && (
        <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 py-4 flex flex-col gap-3">
          {/* Stats strip */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 shrink-0">
            {[
              { label: 'Total',   value: pipelineStats.total,     color: 'text-content-primary' },
              { label: 'Running', value: pipelineStats.running,   color: 'text-accent' },
              { label: 'Pending', value: pipelineStats.pending,   color: 'text-content-tertiary' },
              { label: 'Review',  value: pipelineStats.review,    color: 'text-amber-500' },
              { label: 'Done',    value: pipelineStats.completed, color: 'text-emerald-500' },
              { label: 'Failed',  value: pipelineStats.failed,    color: 'text-red-500' },
            ].map(s => (
              <div key={s.label} className="rounded-lg border border-border bg-surface-0 px-3 py-2">
                <div className={cn('text-lg font-bold tabular-nums leading-none', s.color)}>{s.value}</div>
                <div className="text-[10px] text-content-tertiary mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Search + filter bar */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Select all */}
            <button onClick={toggleSelectAll}
              className="w-8 h-8 flex items-center justify-center rounded border border-border text-content-tertiary hover:text-content-primary hover:bg-surface-2 transition-colors">
              {selectedIds.size > 0 && selectedIds.size === filtered.length
                ? <CheckSquare size={14} className="text-accent" />
                : <CheckSquare size={14} />}
            </button>
            <div className="relative flex-1">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary" />
              <input type="text" value={q} onChange={e => setQ(e.target.value)}
                placeholder="Search title, hook, topic…"
                className="w-full pl-9 pr-8 py-2 text-xs bg-surface-0 border border-border rounded text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 transition-shadow" />
              {q && (
                <button onClick={() => setQ('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-primary w-5 h-5 flex items-center justify-center rounded hover:bg-surface-2">
                  <X size={12} />
                </button>
              )}
            </div>
            {/* Sort */}
            <div className="relative">
              <button onClick={() => setShowSort(!showSort)}
                className="inline-flex items-center gap-1.5 px-2.5 py-2 rounded-md text-xs font-medium text-content-secondary hover:bg-surface-2 transition-colors">
                <span>{SORT_OPTIONS.find(s => s.key === sortKey)?.label}</span>
                <span className="text-accent font-bold">{sortDir === 'asc' ? '↑' : '↓'}</span>
              </button>
              {showSort && (
                <>
                  <div className="fixed inset-0 z-20" onClick={() => setShowSort(false)} />
                  <div className="absolute right-0 top-10 z-30 w-44 bg-surface-0 border border-border rounded-md shadow-elevated py-1">
                    {SORT_OPTIONS.map(s => (
                      <button key={s.key} onClick={() => { setSortKey(s.key); setShowSort(false); }}
                        className={cn('w-full text-left px-3 py-2 text-xs transition-colors flex items-center justify-between',
                          sortKey === s.key ? 'text-accent bg-accent/10 font-medium' : 'text-content-secondary hover:bg-surface-2')}>
                        {s.label}
                        {sortKey === s.key && <span className="text-accent font-bold">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                      </button>
                    ))}
                    <div className="border-t border-border my-1" />
                    <button onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
                      className="w-full text-left px-3 py-2 text-xs text-content-secondary hover:bg-surface-2">
                      Toggle direction
                    </button>
                  </div>
                </>
              )}
            </div>
            <button onClick={() => setDrawerOpen(true)}
              className={cn('inline-flex items-center gap-1.5 px-2.5 py-2 rounded-md text-xs font-medium transition-colors',
                activeFilterCount > 0 ? 'bg-accent/10 text-accent' : 'text-content-secondary hover:bg-surface-2')}>
              <Wrench size={13} />
              Filters
              {activeFilterCount > 0 && (
                <span className="min-w-[16px] h-4 px-1 rounded-full bg-accent text-white text-[9px] flex items-center justify-center font-bold">{activeFilterCount}</span>
              )}
            </button>
          </div>

          {/* Table */}
          <div className="flex-1 min-h-0 border border-border bg-surface-0 rounded overflow-hidden flex flex-col">
            <div className="shrink-0 px-4 py-2.5 flex items-center bg-surface-1/50 text-[10px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
              <span className="w-7 shrink-0" />
              <span className="flex-1 min-w-0 pl-2">Title</span>
              <span className="w-20 shrink-0 text-center">Type</span>
              <span className="w-24 shrink-0 text-center hidden md:block">Status</span>
              <span className="w-24 shrink-0 text-center hidden md:block">Review</span>
              <span className="w-14 shrink-0 text-center hidden sm:block">Score</span>
              <span className="w-28 shrink-0 text-center hidden sm:block">Date</span>
              <span className="w-32 shrink-0 text-right pr-2">Actions</span>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-hide divide-y divide-border">
              {filtered.map((v: any) => (
                <ContentRow key={v.content_id} v={v} channels={channels}
                  selected={selectedIds.has(v.content_id)}
                  onToggleSelect={() => toggleSelect(v.content_id)}
                  onPreview={openPreview} onDownload={handleDownload}
                  onExport={handleExportDaVinci}
                  onDetail={() => openDetail(v.content_id)} />
              ))}
              {filtered.length === 0 && !loading && (
                <div className="py-20 text-center">
                  {activeFilterCount > 0 || q ? (
                    <div className="text-sm text-content-tertiary">
                      <p className="font-medium text-content-secondary mb-1">No matches</p>
                      <button onClick={() => { clearFilters(); setQ(''); }}
                        className="mt-2 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded hover:opacity-90">
                        Clear all filters
                      </button>
                    </div>
                  ) : (
                    <div className="text-sm text-content-tertiary">
                      <p>No videos generated yet.</p>
                      <button onClick={() => setTriggerOpen(true)}
                        className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded hover:opacity-90">
                        <Zap size={11} /> Generate your first video
                      </button>
                    </div>
                  )}
                </div>
              )}
              {cursor && !q && !searchHits && (
                <button onClick={() => fetchPage(false)} disabled={loading}
                  className="w-full py-2.5 border-t border-dashed border-border text-xs text-content-tertiary hover:bg-surface-1 transition-colors">
                  {loading ? 'Loading…' : 'Load more'}
                </button>
              )}
            </div>
            <div className="shrink-0 px-4 py-1.5 border-t border-border text-[10px] text-content-tertiary bg-surface-1/30">
              {filtered.length} of {allItems.length} items{cursor && !q && !searchHits && ' — more available'}
              {selectedIds.size > 0 && <span className="ml-3 text-accent font-medium">{selectedIds.size} selected</span>}
            </div>
          </div>
        </div>
      )}

      {/* ── Calendar tab ── */}
      {activeTab === 'calendar' && (
        <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 py-4 flex flex-col gap-3">
          {/* Month nav */}
          <div className="flex items-center gap-3 shrink-0">
            <button onClick={() => setCalDate(d => new Date(d.getFullYear(), d.getMonth() - 1, 1))}
              className="w-8 h-8 flex items-center justify-center rounded border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
              <ChevronLeft size={14} />
            </button>
            <h2 className="text-sm font-semibold text-content-primary flex-1 text-center">{calMonthLabel}</h2>
            <button onClick={() => setCalDate(d => new Date(d.getFullYear(), d.getMonth() + 1, 1))}
              className="w-8 h-8 flex items-center justify-center rounded border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
              <ChevronRight size={14} />
            </button>
            <button onClick={loadCalendar} disabled={calLoading}
              className="w-8 h-8 flex items-center justify-center rounded border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
              <RotateCw size={13} className={cn(calLoading && 'animate-spin')} />
            </button>
          </div>
          {/* Day-of-week headers */}
          <div className="grid grid-cols-7 gap-1 shrink-0">
            {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
              <div key={d} className="text-center text-[10px] font-semibold text-content-tertiary uppercase py-1">{d}</div>
            ))}
          </div>
          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-1 flex-1 min-h-0 overflow-y-auto">
            {calLoading
              ? Array.from({ length: 35 }).map((_, i) => (
                  <div key={i} className="rounded-md bg-surface-2 animate-pulse min-h-[80px]" />
                ))
              : calDays.map((day, i) => {
                  if (!day) return <div key={i} />;
                  const events = calData[day.iso] || [];
                  const isToday = day.iso === new Date().toISOString().slice(0, 10);
                  return (
                    <div key={day.iso}
                      className={cn('rounded-md border p-1.5 min-h-[80px] flex flex-col gap-0.5 text-left',
                        isToday ? 'border-accent/50 bg-accent/5' : 'border-border bg-surface-0'
                      )}>
                      <span className={cn('text-[10px] font-semibold', isToday ? 'text-accent' : 'text-content-tertiary')}>
                        {day.date.getDate()}
                      </span>
                      {events.slice(0, 3).map((ev: any) => (
                        <button key={ev.content_id}
                          onClick={() => openDetail(ev.content_id)}
                          title={ev.title || ev.content_id}
                          className={cn('w-full text-left text-[9px] truncate rounded px-1 py-0.5 font-medium',
                            STATUS_CHIP[ev.status] || 'bg-surface-2 text-content-tertiary')}>
                          {ev.title || ev.content_id}
                        </button>
                      ))}
                      {events.length > 3 && (
                        <span className="text-[9px] text-content-tertiary">+{events.length - 3} more</span>
                      )}
                    </div>
                  );
                })
            }
          </div>
        </div>
      )}

      {/* ── Stats tab ── */}
      {activeTab === 'stats' && (
        <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 py-4 overflow-y-auto">
          {/* Period selector */}
          <div className="flex items-center gap-2 mb-4 shrink-0">
            {(['day','week','month'] as const).map(p => (
              <button key={p} onClick={() => setStatsPeriod(p)}
                className={cn('h-7 px-3 rounded-md border text-xs font-medium transition-all',
                  statsPeriod === p ? 'border-accent/40 bg-accent/5 text-accent' : 'border-border text-content-tertiary hover:bg-surface-1')}>
                {p === 'day' ? 'Daily' : p === 'week' ? 'Weekly' : 'Monthly'}
              </button>
            ))}
            <button onClick={loadStats} disabled={statsLoading}
              className="w-7 h-7 flex items-center justify-center rounded border border-border hover:bg-surface-2 text-content-tertiary transition-colors ml-auto">
              <RotateCw size={12} className={cn(statsLoading && 'animate-spin')} />
            </button>
          </div>

          {statsLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={20} className="animate-spin text-content-tertiary" />
            </div>
          )}

          {!statsLoading && statsData && (
            <div className="space-y-6">
              {/* By channel breakdown */}
              <div>
                <h3 className="text-xs font-semibold text-content-secondary mb-3 flex items-center gap-1.5">
                  <TrendingUp size={12} /> By Channel
                </h3>
                <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border overflow-hidden">
                  {(statsData.by_channel || []).length === 0 && (
                    <div className="py-8 text-center text-xs text-content-tertiary">No data yet</div>
                  )}
                  {(statsData.by_channel || []).map((ch: any) => {
                    const channel = channels.find(c => c.channel_id === ch.channel_id);
                    const total = (ch.done || 0) + (ch.running || 0) + (ch.failed || 0);
                    const doneRatio = total > 0 ? (ch.done || 0) / total : 0;
                    return (
                      <div key={ch.channel_id} className="flex items-center gap-4 px-4 py-3">
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium text-content-primary truncate">
                            {channel?.channel_name || ch.channel_id}
                          </div>
                          <div className="mt-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${doneRatio * 100}%` }} />
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 text-[11px]">
                          <span className="text-emerald-500">{ch.done} done</span>
                          {ch.running > 0 && <span className="text-accent">{ch.running} running</span>}
                          {ch.failed > 0 && <span className="text-red-500">{ch.failed} failed</span>}
                          {ch.total_cost != null && <span className="text-content-tertiary">${Number(ch.total_cost).toFixed(2)}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Bucket table */}
              <div>
                <h3 className="text-xs font-semibold text-content-secondary mb-3 flex items-center gap-1.5">
                  <BarChart2 size={12} /> Bucket breakdown
                </h3>
                <div className="rounded-xl border border-border bg-surface-0 overflow-hidden">
                  <div className="grid grid-cols-6 px-4 py-2 bg-surface-1/50 text-[10px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
                    <span className="col-span-2">Period</span>
                    <span>Status</span>
                    <span>Mode</span>
                    <span className="text-right">Count</span>
                    <span className="text-right">Avg cost</span>
                  </div>
                  <div className="divide-y divide-border max-h-72 overflow-y-auto">
                    {(statsData.buckets || []).slice(0, 50).map((b: any, i: number) => (
                      <div key={i} className="grid grid-cols-6 px-4 py-2 text-xs text-content-secondary hover:bg-surface-1 transition-colors">
                        <span className="col-span-2 text-content-tertiary font-mono">{b.bucket}</span>
                        <span>
                          <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                            STATUS_CHIP[b.status] || 'bg-surface-2 text-content-tertiary')}>
                            {b.status}
                          </span>
                        </span>
                        <span className="text-content-tertiary">{b.content_mode || '—'}</span>
                        <span className="text-right font-medium">{b.cnt}</span>
                        <span className="text-right text-content-tertiary">
                          {b.avg_cost != null ? `$${Number(b.avg_cost).toFixed(3)}` : '—'}
                        </span>
                      </div>
                    ))}
                    {(statsData.buckets || []).length === 0 && (
                      <div className="py-8 text-center text-xs text-content-tertiary">No data for this period</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Bulk action bar ── */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 px-4 py-2.5 bg-surface-0 border border-border rounded-xl shadow-elevated">
          <span className="text-xs font-medium text-content-primary mr-1">{selectedIds.size} selected</span>
          {[
            { action: 'approve',  label: 'Approve',  cls: 'text-emerald-600 hover:bg-emerald-500/10' },
            { action: 'reject',   label: 'Reject',   cls: 'text-red-500    hover:bg-red-500/10' },
            { action: 'retry',    label: 'Retry',    cls: 'text-accent     hover:bg-accent/10' },
            { action: 'archive',  label: 'Archive',  cls: 'text-content-tertiary hover:bg-surface-2' },
          ].map(b => (
            <button key={b.action} onClick={() => handleBulk(b.action)}
              className={cn('h-7 px-3 rounded-md text-xs font-medium transition-colors', b.cls)}>
              {b.label}
            </button>
          ))}
          <button onClick={() => setSelectedIds(new Set())}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary transition-colors ml-1">
            <X size={12} />
          </button>
        </div>
      )}

      {/* ── Detail drawer ── */}
      {detailId && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/30" onClick={() => { setDetailId(null); setDetailData(null); }} />
          <div className="absolute right-0 top-0 bottom-0 w-[380px] bg-surface-0 border-l border-border shadow-elevated flex flex-col">
            <div className="shrink-0 px-4 py-3 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Film size={14} className="text-accent" />
                <span className="text-sm font-semibold text-content-primary">Content Detail</span>
              </div>
              <button onClick={() => { setDetailId(null); setDetailData(null); }}
                className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary transition-colors">
                <X size={14} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {detailLoading && <div className="flex items-center justify-center py-12"><Loader2 size={18} className="animate-spin text-content-tertiary" /></div>}
              {!detailLoading && detailData && (
                <>
                  {/* Title */}
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">Title</div>
                    <div className="text-sm font-medium text-content-primary leading-snug">{detailData.title || detailData.topic || detailData.content_id}</div>
                  </div>
                  {/* Hook */}
                  {detailData.selected_hook && (
                    <div>
                      <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-1">Hook</div>
                      <div className="text-xs text-content-secondary italic">&ldquo;{detailData.selected_hook}&rdquo;</div>
                    </div>
                  )}
                  {/* Meta grid */}
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      ['Channel', channels.find(c => c.channel_id === detailData.channel_id)?.channel_name || detailData.channel_id],
                      ['Mode', detailData.content_mode],
                      ['Status', detailData.status],
                      ['Review', detailData.review_state || '—'],
                      ['Auth score', detailData.authenticity_score != null ? Number(detailData.authenticity_score).toFixed(2) : '—'],
                      ['Composite', detailData.final_composite_score != null ? Number(detailData.final_composite_score).toFixed(2) : '—'],
                      ['Cost', detailData.total_cost != null ? `$${Number(detailData.total_cost).toFixed(3)}` : '—'],
                      ['Created', new Date(detailData.created_at).toLocaleString()],
                    ].map(([l, v]) => (
                      <div key={l as string}>
                        <div className="text-[9px] uppercase tracking-wider text-content-tertiary">{l}</div>
                        <div className="text-xs text-content-primary truncate">{v || '—'}</div>
                      </div>
                    ))}
                  </div>
                  {/* Thumbnails */}
                  {detailData.thumbnail_variants_urls?.length > 0 && (
                    <div>
                      <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-2">Thumbnails</div>
                      <div className="grid grid-cols-3 gap-1">
                        {detailData.thumbnail_variants_urls.slice(0, 3).map((u: string, i: number) => (
                          <img key={i} src={u} alt={`Thumbnail ${i+1}`} className="rounded-md aspect-video object-cover bg-surface-2" />
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Phase timeline */}
                  {detailData.events?.length > 0 && (
                    <div>
                      <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-2">Pipeline Timeline</div>
                      <div className="space-y-1">
                        {detailData.events.map((ev: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-[11px]">
                            <span className={cn('w-2 h-2 rounded-full shrink-0',
                              ev.status === 'completed' ? 'bg-emerald-500' :
                              ev.status === 'failed'    ? 'bg-red-500' :
                              ev.status === 'running'   ? 'bg-accent animate-pulse' : 'bg-surface-3')} />
                            <span className="text-content-secondary capitalize">{ev.phase?.replace('_', ' ')}</span>
                            {ev.duration_ms && <span className="text-content-tertiary ml-auto">{(ev.duration_ms / 1000).toFixed(1)}s</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Review session */}
                  {detailData.review_session && (
                    <div>
                      <div className="text-[9px] uppercase tracking-wider text-content-tertiary mb-2">Review Session</div>
                      <div className="rounded-md bg-surface-1 border border-border p-3 space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-content-tertiary">State</span>
                          <span className="text-content-primary capitalize">{detailData.review_session.state}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-content-tertiary">Comments</span>
                          <span className="text-content-primary">{detailData.review_session.comment_count}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-content-tertiary">Approvals</span>
                          <span className="text-content-primary">{detailData.review_session.approval_count}</span>
                        </div>
                      </div>
                    </div>
                  )}
                  {/* Actions */}
                  <div className="flex flex-col gap-2 pt-1">
                    {['completed','published','delivered'].includes(detailData.status) && (
                      <button onClick={() => { setDetailId(null); openPreview(detailData.content_id); }}
                        className="flex items-center justify-center gap-1.5 h-8 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
                        <Play size={12} /> Preview video
                      </button>
                    )}
                    <Link href={`/dashboard/review/${detailData.content_id}`}
                      className="flex items-center justify-center gap-1.5 h-8 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors">
                      <ClipboardCheck size={12} /> Open review
                    </Link>
                    <Link href={`/dashboard/jobs/${detailData.content_id}`}
                      className="flex items-center justify-center gap-1.5 h-8 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors">
                      <ExternalLink size={12} /> Job detail
                    </Link>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Filter Drawer ── */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-[28rem] bg-surface-0 border-l border-border shadow-elevated flex flex-col">
            <div className="shrink-0 px-5 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2"><Wrench size={15} className="text-accent" /><h2 className="text-sm font-semibold text-content-primary">Filters</h2></div>
              <div className="flex items-center gap-2">
                {activeFilterCount > 0 && (
                  <button onClick={clearFilters} className="text-[11px] text-content-tertiary hover:text-content-primary px-2 py-1 rounded hover:bg-surface-1">Clear all</button>
                )}
                <button onClick={() => setDrawerOpen(false)} className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary"><X size={14} /></button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-hide p-5 space-y-6">
              <section>
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3"><Clock size={12} />Date Range</div>
                <div className="grid grid-cols-2 gap-2">
                  {DATE_RANGES.map(r => <FilterChip key={r.key} label={r.label} active={dateRange === r.key} onClick={() => setDateRange(r.key)} />)}
                </div>
              </section>
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Channels</div>
                <div className="relative mb-2">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary" />
                  <input type="text" value={channelSearch} onChange={e => setChannelSearch(e.target.value)} placeholder="Search channels…"
                    className="w-full pl-8 pr-7 py-1.5 text-xs bg-surface-1 border border-border rounded focus:outline-none focus:ring-1 focus:ring-accent/30" />
                </div>
                <div className="max-h-48 overflow-y-auto space-y-0.5">
                  {channels.filter(c => c.channel_name.toLowerCase().includes(channelSearch.toLowerCase())).map(c => {
                    const checked = selChannels.includes(c.channel_id);
                    return (
                      <label key={c.channel_id} className={cn('flex items-center gap-3 px-3 py-2 rounded-md text-xs cursor-pointer transition-colors', checked ? 'bg-accent/10 text-accent' : 'text-content-secondary hover:bg-surface-2')}>
                        <input type="checkbox" checked={checked} onChange={() => toggleMulti(selChannels, setSelChannels, c.channel_id)} />
                        <span className="truncate">{c.channel_name}</span>
                      </label>
                    );
                  })}
                </div>
              </section>
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Status</div>
                <div className="grid grid-cols-2 gap-2">{STATUS_OPTIONS.map(s => <FilterChip key={s} label={s} active={selStatuses.includes(s)} onClick={() => toggleMulti(selStatuses, setSelStatuses, s)} />)}</div>
              </section>
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Review</div>
                <div className="grid grid-cols-2 gap-2">{REVIEW_OPTIONS.map(s => <FilterChip key={s} label={s.replace('_',' ')} active={selReviews.includes(s)} onClick={() => toggleMulti(selReviews, setSelReviews, s)} />)}</div>
              </section>
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Content Mode</div>
                <div className="grid grid-cols-2 gap-2">{MODE_OPTIONS.map(m => <FilterChip key={m} label={m === 'short' ? 'Short' : 'Long form'} active={selModes.includes(m)} onClick={() => toggleMulti(selModes, setSelModes, m)} />)}</div>
              </section>
            </div>
            <div className="shrink-0 px-5 pt-3 pb-8 border-t border-border flex items-center justify-end gap-2">
              <button onClick={() => setDrawerOpen(false)} className="btn-ghost">Cancel</button>
              <button onClick={() => setDrawerOpen(false)} className="btn-primary">Apply · {filtered.length}</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Trigger Modal ── */}
      {triggerOpen && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={() => setTriggerOpen(false)}>
          <div className="w-full max-w-sm bg-surface-0 border border-border rounded-xl shadow-elevated" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2"><Zap size={15} className="text-accent" /><h2 className="text-sm font-semibold text-content-primary">Generate Video</h2></div>
              <button onClick={() => setTriggerOpen(false)} className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary"><X size={14} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-content-secondary mb-1.5">Channel</label>
                <select value={trigChannel} onChange={e => setTrigChannel(e.target.value)}
                  className="w-full h-9 px-3 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
                  {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.channel_name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-content-secondary mb-1.5">Content Mode</label>
                <div className="flex gap-2">
                  {[['long_form','Long form'],['short','Short']].map(([k, l]) => (
                    <button key={k} onClick={() => setTrigMode(k)}
                      className={cn('flex-1 h-9 rounded-md border text-xs font-medium transition-all',
                        trigMode === k ? 'border-accent/40 bg-accent/5 text-accent' : 'border-border text-content-tertiary hover:bg-surface-1')}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-content-secondary mb-1.5">Topic hint <span className="text-content-tertiary font-normal">(optional)</span></label>
                <input value={trigTopic} onChange={e => setTrigTopic(e.target.value)}
                  placeholder="e.g. Top 5 Python tricks for beginners"
                  className="w-full h-9 px-3 rounded-md bg-surface-1 border border-border text-sm placeholder:text-content-tertiary focus:outline-none focus:border-accent/50" />
              </div>
            </div>
            <div className="px-5 pb-5 flex gap-2 justify-end">
              <button onClick={() => setTriggerOpen(false)} className="btn-ghost">Cancel</button>
              <button onClick={handleTrigger} disabled={triggering || !trigChannel}
                className="inline-flex items-center gap-1.5 h-8 px-4 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
                {triggering ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
                {triggering ? 'Starting…' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Preview Modal ── */}
      {previewId && (
        <VideoPreviewModal contentId={previewId} videoUrl={previewUrl} meta={previewMeta} loading={previewLoading}
          onClose={() => { setPreviewId(null); setPreviewUrl(null); setPreviewMeta(null); }} />
      )}
    </div>
  );
}

/* ─── sub-components ─── */

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cn(
        'w-full px-3 py-2 rounded-md text-xs font-medium transition-colors text-left',
        active
          ? 'bg-accent/10 text-accent ring-1 ring-accent/20'
          : 'text-content-secondary hover:text-content-primary hover:bg-surface-2'
      )}>
      {label}
    </button>
  );
}

function toggleMulti<T>(arr: T[], setArr: (v: T[]) => void, val: T) {
  setArr(arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
}

function ContentRow({
  v, channels, selected, onToggleSelect, onPreview, onDownload, onExport, onDetail,
}: {
  v: any; channels: any[];
  selected: boolean;
  onToggleSelect: () => void;
  onPreview: (id: string) => void;
  onDownload: (v: any) => void;
  onExport: (v: any) => void;
  onDetail: () => void;
}) {
  const channel = channels.find(c => c.channel_id === v.channel_id);
  const channelName = channel?.channel_name || v.channel_id;
  const reviewMode = channel?.human_review_required ?? 'never';
  const isReviewable = reviewMode !== 'never';
  const videoReady = ['completed', 'published', 'delivered'].includes(v.status);
  const titleHref = isReviewable ? `/dashboard/review/${v.content_id}` : null;

  return (
    <div className={cn('flex items-center px-4 py-3 transition-colors hover:bg-surface-1/40', selected && 'bg-accent/5')}>
      {/* Checkbox */}
      <div className="w-7 shrink-0 flex items-center">
        <button onClick={e => { e.stopPropagation(); onToggleSelect(); }}
          className="w-5 h-5 flex items-center justify-center text-content-tertiary hover:text-accent transition-colors">
          {selected ? <CheckSquare size={13} className="text-accent" /> : <CheckSquare size={13} />}
        </button>
      </div>

      {/* Title + channel — click opens detail */}
      <button onClick={onDetail} className="min-w-0 flex-1 pl-2 pr-3 text-left">
        <span className="text-xs font-medium truncate block text-content-primary hover:text-accent transition-colors">
          {v.title || v.topic || v.content_id}
        </span>
        <div className="text-[10px] text-content-tertiary truncate mt-0.5 flex items-center gap-1.5">
          <span className="text-content-secondary">{channelName}</span>
          {v.topic && <><span>·</span><span className="truncate">{v.topic}</span></>}
        </div>
      </button>

      {/* Type chip */}
      <div className="w-20 shrink-0 flex justify-center">
        <span className={v.content_mode === 'short' ? 'chip-short' : 'chip-long'}>
          {v.content_mode === 'short' ? 'Short' : 'Long'}
        </span>
      </div>

      {/* Status */}
      <div className="w-24 shrink-0 text-center hidden md:block">
        <span className={cn('text-[10px] uppercase px-2 py-0.5 rounded font-medium inline-block',
          STATUS_CHIP[v.status] ?? 'bg-surface-3 text-content-tertiary')}>
          {v.status}
        </span>
      </div>

      {/* Review */}
      <div className="w-24 shrink-0 text-center hidden md:block">
        {!isReviewable ? (
          <span className="text-[10px] text-content-tertiary italic">auto</span>
        ) : v.review_state ? (
          <span className={cn('text-[10px] uppercase px-2 py-0.5 rounded font-medium inline-block',
            REVIEW_CHIP[v.review_state] ?? 'bg-surface-3 text-content-tertiary')}>
            {v.review_state.replace('_', ' ')}
          </span>
        ) : (
          <span className="text-[10px] text-content-tertiary">—</span>
        )}
      </div>

      {/* Score */}
      <div className="w-14 shrink-0 text-center hidden sm:block">
        {v.authenticity_score != null ? (
          <span className="text-[10px] font-mono text-content-secondary">{Number(v.authenticity_score).toFixed(1)}</span>
        ) : <span className="text-[10px] text-content-tertiary">—</span>}
      </div>

      {/* Date */}
      <div className="w-28 shrink-0 text-center hidden sm:block">
        <span className="text-[10px] text-content-tertiary">{new Date(v.created_at).toLocaleDateString()}</span>
      </div>

      {/* Actions */}
      <div className="w-32 shrink-0 flex items-center justify-end gap-0.5 pr-1">
        {isReviewable && titleHref && (
          <Link href={titleHref} title="Open review"
            className="w-7 h-7 inline-flex items-center justify-center rounded text-content-tertiary hover:text-accent hover:bg-accent/10 transition-colors">
            <ClipboardCheck size={13} />
          </Link>
        )}
        {videoReady ? (
          <>
            <ActionButton onClick={() => onPreview(v.content_id)} title="Preview" icon={Play} />
            <ActionButton onClick={() => onDownload(v)} title="Download" icon={Download} />
            <ActionButton onClick={() => onExport(v)} title="Export to DaVinci" icon={Link2} />
          </>
        ) : (
          <span className="text-[9px] text-content-tertiary italic pr-1">in&nbsp;progress</span>
        )}
      </div>
    </div>
  );
}

function ActionButton({ onClick, title, icon: Icon }: { onClick: () => void; title: string; icon: any }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-7 h-7 flex items-center justify-center rounded text-content-tertiary hover:text-accent hover:bg-accent/10 transition-colors"
    >
      <Icon size={13} />
    </button>
  );
}

function VideoPreviewModal({
  contentId, videoUrl, meta, loading, onClose,
}: {
  contentId: string;
  videoUrl: string | null;
  meta: any;
  loading: boolean;
  onClose: () => void;
}) {
  const isShort = meta?.content_mode === 'short';
  return (
    <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div
        className={cn(
          'w-full bg-surface-0 border border-border rounded shadow-elevated overflow-hidden flex flex-col max-h-[90vh]',
          isShort ? 'max-w-md' : 'max-w-3xl'
        )}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-content-primary truncate">{meta?.title || contentId}</h3>
            {meta?.channel_id && <p className="text-[11px] text-content-tertiary truncate">{meta.channel_id}</p>}
          </div>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary hover:text-content-primary transition-colors shrink-0 ml-2">
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 min-h-0 bg-black flex items-center justify-center">
          {loading ? (
            <div className="text-sm text-content-tertiary py-12">Loading preview…</div>
          ) : videoUrl ? (
            <video
              src={videoUrl}
              controls
              className={cn(
                isShort ? 'max-h-[70vh] w-auto' : 'max-w-full max-h-[60vh]'
              )}
            />
          ) : (
            <div className="text-center py-16 px-6">
              <AlertTriangle size={32} className="text-content-tertiary mx-auto mb-3 opacity-50" />
              <p className="text-sm text-content-tertiary">Video preview not available yet.</p>
              <p className="text-xs text-content-tertiary mt-1">The video may still be rendering or the output URL is not configured.</p>
            </div>
          )}
        </div>

        {meta && (
          <div className="shrink-0 px-4 py-3 border-t border-border bg-surface-1/30">
            <div className="flex items-center gap-4 flex-wrap text-[11px] text-content-secondary">
              {meta.topic && <span><span className="text-content-tertiary">Topic:</span> {meta.topic}</span>}
              {meta.content_mode && <span><span className="text-content-tertiary">Mode:</span> {meta.content_mode}</span>}
              {meta.status && <span><span className="text-content-tertiary">Status:</span> {meta.status}</span>}
              {meta.created_at && <span><span className="text-content-tertiary">Created:</span> {new Date(meta.created_at).toLocaleString()}</span>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
