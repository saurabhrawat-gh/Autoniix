'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { contentApi, channelsApi } from '@/lib/api-v2';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, X, Play, Download, Link2, AlertTriangle,
  Wrench, Clock, ClipboardCheck,
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

/* ─── main ─── */
export default function ContentPage() {
  const [allItems, setAllItems] = useState<any[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [channels, setChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  /* search */
  const [q, setQ] = useState('');
  const [searchHits, setSearchHits] = useState<any[] | null>(null);

  /* filter drawer */
  const [drawerOpen, setDrawerOpen] = useState(false);

  /* filters */
  const [selChannels, setSelChannels] = useState<string[]>([]);
  const [selStatuses, setSelStatuses] = useState<string[]>([]);
  const [selReviews, setSelReviews] = useState<string[]>([]);
  const [selModes, setSelModes] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState('all');
  const [channelSearch, setChannelSearch] = useState('');

  /* sort */
  const [sortKey, setSortKey] = useState('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [showSort, setShowSort] = useState(false);

  /* preview */
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewMeta, setPreviewMeta] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const { showToast } = useToast();
  const searchParams = useSearchParams();

  // Seed filters from URL on first render — supports deep links like
  // /dashboard/content?review_state=pending from the Home dashboard.
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

  useEffect(() => { channelsApi.list(false).then(r => setChannels(r.data || [])); }, []);

  const fetchPage = async (replace = true) => {
    setLoading(true);
    try {
      const r = await contentApi.list({
        cursor: replace ? undefined : cursor || undefined,
        limit: 60,
      });
      setCursor(r.data.next_cursor);
      const fetched = (r.data.groups || []).flatMap((g: any) => g.items || []);
      setAllItems(prev => replace ? fetched : [...prev, ...fetched]);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchPage(true); }, []);

  useEffect(() => {
    if (q.length < 2) { setSearchHits(null); return; }
    const t = setTimeout(() => contentApi.search(q).then(r => setSearchHits(r.data)), 300);
    return () => clearTimeout(t);
  }, [q]);

  /* client-side filter + sort */
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
          case 'title':
            cmp = (a.title || a.topic || '').localeCompare(b.title || b.topic || '');
            break;
          case 'authenticity_score':
            cmp = (a.authenticity_score ?? 0) - (b.authenticity_score ?? 0);
            break;
          case 'status':
            cmp = (a.status || '').localeCompare(b.status || '');
            break;
          default:
            cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        }
        return sortDir === 'asc' ? cmp : -cmp;
      });
  }, [allItems, searchHits, selChannels, selStatuses, selReviews, selModes, dateRange, sortKey, sortDir]);

  const activeFilterCount = selChannels.length + selStatuses.length + selReviews.length + selModes.length + (dateRange !== 'all' ? 1 : 0);

  /* actions */
  const openPreview = async (contentId: string) => {
    setPreviewId(contentId);
    setPreviewLoading(true);
    try {
      const output = await api.jobOutput(contentId).catch(() => null);
      const meta = await api.jobMetadata(contentId).catch(() => null);
      setPreviewMeta(meta);
      setPreviewUrl(output?.url || output?.video_url || null);
    } catch {
      setPreviewUrl(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownload = async (v: any) => {
    try {
      const output = await api.jobOutput(v.content_id).catch(() => null);
      const url = output?.url || output?.video_url;
      if (!url) { showToast('Video not yet available', 'error'); return; }
      const a = document.createElement('a');
      a.href = url;
      a.download = `${v.title || v.content_id}.mp4`;
      a.target = '_blank';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    } catch { showToast('Download failed', 'error'); }
  };

  const handleExportDaVinci = (v: any) => {
    const payload = {
      title: v.title || v.topic || v.content_id,
      topic: v.topic,
      channel_id: v.channel_id,
      channel_name: channels.find(c => c.channel_id === v.channel_id)?.channel_name || v.channel_id,
      content_id: v.content_id,
      content_mode: v.content_mode,
      status: v.status,
      review_state: v.review_state,
      created_at: v.created_at,
      authenticity_score: v.authenticity_score,
      notes: 'Import into DaVinci Resolve Media Pool as clip metadata.',
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${v.content_id}_davinci.json`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('DaVinci Resolve metadata exported', 'success');
  };

  const clearFilters = () => {
    setSelChannels([]);
    setSelStatuses([]);
    setSelReviews([]);
    setSelModes([]);
    setDateRange('all');
    setChannelSearch('');
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* ── Toolbar ── */}
      <div className="shrink-0 max-w-[1400px] w-full mx-auto px-6 pt-5 pb-3">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-content-primary">Generated content</h1>
            <p className="text-xs text-content-tertiary mt-0.5">All videos created by your automation pipeline.</p>
          </div>
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative w-80">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-tertiary" />
              <input
                type="text"
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search title, hook, topic…"
                className="w-full pl-9 pr-8 py-2 text-xs bg-surface-0 border border-border rounded text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30 transition-shadow"
              />
              {q && (
                <button onClick={() => setQ('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-primary w-5 h-5 flex items-center justify-center rounded hover:bg-surface-2 transition-colors">
                  <X size={13} />
                </button>
              )}
            </div>

            {/* Sort */}
            <div className="relative">
              <button onClick={() => setShowSort(!showSort)}
                className="inline-flex items-center gap-2 px-2.5 py-2 rounded-md text-sm font-medium text-content-secondary hover:text-content-primary hover:bg-surface-2 transition-colors">
                <span className="hidden sm:inline">{SORT_OPTIONS.find(s => s.key === sortKey)?.label}</span>
                <span className="text-accent text-[10px] font-bold">{sortDir === 'asc' ? 'ASC' : 'DESC'}</span>
              </button>
              {showSort && (
                <>
                  <div className="fixed inset-0 z-20" onClick={() => setShowSort(false)} />
                  <div className="absolute right-0 top-10 z-30 w-44 bg-surface-0 border border-border rounded-md shadow-elevated py-1">
                    {SORT_OPTIONS.map(s => (
                      <button key={s.key} onClick={() => { setSortKey(s.key); setShowSort(false); }}
                        className={cn('w-full text-left px-3 py-2 text-sm transition-colors flex items-center justify-between',
                          sortKey === s.key ? 'text-accent bg-accent/10 font-medium' : 'text-content-secondary hover:bg-surface-2')}>
                        <span>{s.label}</span>
                        {sortKey === s.key && <span className="text-accent text-[10px] font-bold">{sortDir === 'asc' ? 'ASC' : 'DESC'}</span>}
                      </button>
                    ))}
                    <div className="border-t border-border my-1" />
                    <button onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
                      className="w-full text-left px-3 py-2 text-sm text-content-secondary hover:bg-surface-2 flex items-center gap-2">
                      Toggle direction
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Filter drawer trigger — matches nav active style when filters applied */}
            <button
              onClick={() => setDrawerOpen(true)}
              className={cn(
                'inline-flex items-center gap-2 px-2.5 py-2 rounded-md text-sm font-medium transition-colors',
                activeFilterCount > 0
                  ? 'bg-accent/10 text-accent hover:bg-accent/15'
                  : 'text-content-secondary hover:text-content-primary hover:bg-surface-2'
              )}
            >
              <Wrench size={14} />
              <span className="hidden sm:inline">Filters</span>
              {activeFilterCount > 0 && (
                <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-accent text-white text-[10px] flex items-center justify-center font-bold">{activeFilterCount}</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Table ── */}
      <div className="flex-1 min-h-0 max-w-[1400px] w-full mx-auto px-6 pb-4">
        <div className="h-full flex flex-col overflow-hidden border border-border bg-surface-0 rounded">
          {/* Header row */}
          <div className="shrink-0 px-4 py-3 flex items-center bg-surface-1/50 text-[11px] font-semibold text-content-tertiary uppercase tracking-wider border-b border-border">
            <span className="flex-1 min-w-0 pl-2">Title</span>
            <span className="w-20 shrink-0 text-center">Type</span>
            <span className="w-24 shrink-0 text-center hidden md:block">Status</span>
            <span className="w-24 shrink-0 text-center hidden md:block">Review</span>
            <span className="w-16 shrink-0 text-center hidden sm:block">Score</span>
            <span className="w-28 shrink-0 text-center hidden sm:block">Date</span>
            <span className="w-32 shrink-0 text-right pr-2">Actions</span>
          </div>

          {/* Rows */}
          <div className="flex-1 overflow-y-auto scrollbar-hide divide-y divide-border">
            {filtered.map((v: any) => (
              <ContentRow key={v.content_id} v={v} channels={channels}
                onPreview={openPreview} onDownload={handleDownload} onExport={handleExportDaVinci} />
            ))}
            {filtered.length === 0 && !loading && (
              <div className="py-20 text-center">
                {activeFilterCount > 0 || q ? (
                  <div className="text-sm text-content-tertiary">
                    <p className="font-medium text-content-secondary mb-1">No matches</p>
                    <p>Try adjusting your filters or search query.</p>
                    <button onClick={() => { clearFilters(); setQ(''); }}
                      className="mt-3 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded hover:opacity-90 transition-opacity">
                      Clear all
                    </button>
                  </div>
                ) : (
                  <div className="text-sm text-content-tertiary">No videos generated yet.</div>
                )}
              </div>
            )}
            {cursor && !q && !searchHits && (
              <button onClick={() => fetchPage(false)} disabled={loading}
                className="w-full py-2.5 border-t border-dashed border-border text-sm text-content-tertiary hover:bg-surface-1 hover:text-content-secondary transition-colors">
                {loading ? 'Loading…' : 'Load more'}
              </button>
            )}
          </div>

          {/* Footer count */}
          <div className="shrink-0 px-4 py-2 border-t border-border text-[11px] text-content-tertiary bg-surface-1/30">
            Showing {filtered.length} of {allItems.length} items
            {cursor && !q && !searchHits && ' — more available'}
          </div>
        </div>
      </div>

      {/* ── Filter Drawer ── */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-[28rem] sm:w-[32rem] bg-surface-0 border-l border-border shadow-elevated flex flex-col">
            {/* Drawer header */}
            <div className="shrink-0 px-5 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wrench size={16} className="text-accent" />
                <h2 className="text-sm font-semibold text-content-primary">Filters</h2>
              </div>
              <div className="flex items-center gap-2">
                {activeFilterCount > 0 && (
                  <button onClick={clearFilters}
                    className="text-[11px] font-medium text-content-tertiary hover:text-content-primary px-2 py-1 rounded hover:bg-surface-1 transition-colors">
                    Clear all
                  </button>
                )}
                <button onClick={() => setDrawerOpen(false)}
                  className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary hover:text-content-primary transition-colors">
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Drawer body */}
            <div className="flex-1 overflow-y-auto scrollbar-hide p-5 space-y-6">

              {/* Date Range */}
              <section>
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">
                  <Clock size={12} />
                  Date Range
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {DATE_RANGES.map(r => (
                    <FilterChip key={r.key} label={r.label} active={dateRange === r.key}
                      onClick={() => setDateRange(r.key)} />
                  ))}
                </div>
              </section>

              {/* Channels — searchable multi-select */}
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Channels</div>
                <div className="relative mb-2">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary" />
                  <input
                    type="text"
                    value={channelSearch}
                    onChange={e => setChannelSearch(e.target.value)}
                    placeholder="Search channels…"
                    className="w-full pl-8 pr-7 py-1.5 text-xs bg-surface-1 border border-border rounded focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30"
                  />
                  {channelSearch && (
                    <button onClick={() => setChannelSearch('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-primary">
                      <X size={12} />
                    </button>
                  )}
                </div>
                <div className="max-h-60 overflow-y-auto space-y-0.5 pr-1 -mx-1 px-1">
                  {channels
                    .filter(c => c.channel_name.toLowerCase().includes(channelSearch.toLowerCase()))
                    .map(c => {
                      const checked = selChannels.includes(c.channel_id);
                      return (
                        <label key={c.channel_id}
                          className={cn('flex items-center gap-3 px-3 py-2.5 rounded-md text-sm cursor-pointer transition-colors',
                            checked
                              ? 'bg-accent/10 text-accent'
                              : 'text-content-secondary hover:text-content-primary hover:bg-surface-2'
                          )}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleMulti(selChannels, setSelChannels, c.channel_id)}
                          />
                          <span className="truncate flex-1">{c.channel_name}</span>
                        </label>
                      );
                    })}
                  {channels.filter(c => c.channel_name.toLowerCase().includes(channelSearch.toLowerCase())).length === 0 && (
                    <span className="block text-xs text-content-tertiary px-3 py-3">No channels match</span>
                  )}
                </div>
                {selChannels.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {selChannels.map(cid => {
                      const c = channels.find(ch => ch.channel_id === cid);
                      return (
                        <span key={cid} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-accent/10 text-accent text-[10px] font-medium">
                          {c?.channel_name || cid}
                          <button onClick={() => toggleMulti(selChannels, setSelChannels, cid)} className="hover:text-content-primary"><X size={10} /></button>
                        </span>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* Status */}
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Status</div>
                <div className="grid grid-cols-2 gap-2">
                  {STATUS_OPTIONS.map(s => (
                    <FilterChip key={s} label={s} active={selStatuses.includes(s)}
                      onClick={() => toggleMulti(selStatuses, setSelStatuses, s)} />
                  ))}
                </div>
              </section>

              {/* Review */}
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Review</div>
                <div className="grid grid-cols-2 gap-2">
                  {REVIEW_OPTIONS.map(s => (
                    <FilterChip key={s} label={s.replace('_', ' ')} active={selReviews.includes(s)}
                      onClick={() => toggleMulti(selReviews, setSelReviews, s)} />
                  ))}
                </div>
              </section>

              {/* Mode */}
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-3">Content Mode</div>
                <div className="grid grid-cols-2 gap-2">
                  {MODE_OPTIONS.map(m => (
                    <FilterChip key={m} label={m === 'short' ? 'Short' : 'Long form'} active={selModes.includes(m)}
                      onClick={() => toggleMulti(selModes, setSelModes, m)} />
                  ))}
                </div>
              </section>
            </div>

            {/* Drawer footer — extra bottom padding keeps the Apply button clear of any dev-tools overlay */}
            <div className="shrink-0 px-5 pt-3 pb-12 border-t border-border bg-surface-0 z-10 flex items-center justify-end gap-2">
              <button onClick={() => setDrawerOpen(false)}
                className="btn-ghost">
                Cancel
              </button>
              <button onClick={() => setDrawerOpen(false)}
                className="btn-primary">
                Apply · {filtered.length}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Preview Modal ── */}
      {previewId && (
        <VideoPreviewModal
          contentId={previewId}
          videoUrl={previewUrl}
          meta={previewMeta}
          loading={previewLoading}
          onClose={() => { setPreviewId(null); setPreviewUrl(null); setPreviewMeta(null); }}
        />
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
  v, channels, onPreview, onDownload, onExport,
}: {
  v: any; channels: any[];
  onPreview: (id: string) => void;
  onDownload: (v: any) => void;
  onExport: (v: any) => void;
}) {
  const channel = channels.find(c => c.channel_id === v.channel_id);
  const channelName = channel?.channel_name || v.channel_id;
  // Manual review is required when the channel has it configured AND this video is in a reviewable state
  const reviewMode = channel?.human_review_required ?? 'never';
  const isReviewable = reviewMode !== 'never';
  const videoReady = ['completed', 'published', 'delivered'].includes(v.status);
  const titleHref = isReviewable ? `/dashboard/review/${v.content_id}` : null;

  return (
    <div className="flex items-center px-4 py-3 transition-colors hover:bg-surface-1/40">
      {/* Title + channel */}
      <div className="min-w-0 flex-1 pl-2 pr-3">
        {titleHref ? (
          <Link href={titleHref}
            className="text-sm font-medium truncate hover:underline hover:text-accent block text-content-primary">
            {v.title || v.topic || v.content_id}
          </Link>
        ) : (
          <span className="text-sm font-medium truncate block text-content-primary cursor-default">
            {v.title || v.topic || v.content_id}
          </span>
        )}
        <div className="text-[11px] text-content-tertiary truncate mt-0.5 flex items-center gap-1.5">
          <span className="text-content-secondary">{channelName}</span>
          {v.topic && <><span>·</span><span className="truncate">{v.topic}</span></>}
        </div>
      </div>

      {/* Type chip */}
      <div className="w-20 shrink-0 flex justify-center">
        <span className={v.content_mode === 'short' ? 'chip-short' : 'chip-long'}>
          {v.content_mode === 'short' ? 'Short' : 'Long'}
        </span>
      </div>

      {/* Status */}
      <div className="w-24 shrink-0 text-center hidden md:block">
        <span className={cn('text-[10px] uppercase px-2 py-1 rounded-md font-medium inline-block',
          STATUS_CHIP[v.status] ?? 'bg-surface-3 text-content-tertiary')}>
          {v.status}
        </span>
      </div>

      {/* Review — only show value when channel is reviewable */}
      <div className="w-24 shrink-0 text-center hidden md:block">
        {!isReviewable ? (
          <span className="text-[10px] text-content-tertiary italic">auto</span>
        ) : v.review_state ? (
          <span className={cn('text-[10px] uppercase px-2 py-1 rounded-md font-medium inline-block',
            REVIEW_CHIP[v.review_state] ?? 'bg-surface-3 text-content-tertiary')}>
            {v.review_state.replace('_', ' ')}
          </span>
        ) : (
          <span className="text-[10px] text-content-tertiary">—</span>
        )}
      </div>

      {/* Score */}
      <div className="w-16 shrink-0 text-center hidden sm:block">
        {v.authenticity_score != null ? (
          <span className="text-[11px] font-mono text-content-secondary">{Number(v.authenticity_score).toFixed(2)}</span>
        ) : (
          <span className="text-[11px] text-content-tertiary">—</span>
        )}
      </div>

      {/* Date */}
      <div className="w-28 shrink-0 text-center hidden sm:block">
        <span className="text-[11px] text-content-tertiary">{new Date(v.created_at).toLocaleDateString()}</span>
      </div>

      {/* Actions — Review (only when channel is reviewable) · Preview/Download/Export only when video is ready */}
      <div className="w-32 shrink-0 flex items-center justify-end gap-0.5 pr-1">
        {isReviewable && titleHref && (
          <Link href={titleHref}
            title="Open review"
            className="w-8 h-8 inline-flex items-center justify-center rounded-md text-content-tertiary hover:text-accent hover:bg-accent/10 transition-colors">
            <ClipboardCheck size={14} />
          </Link>
        )}
        {videoReady ? (
          <>
            <ActionButton onClick={() => onPreview(v.content_id)} title="Preview" icon={Play} />
            <ActionButton onClick={() => onDownload(v)} title="Download" icon={Download} />
            <ActionButton onClick={() => onExport(v)} title="Export to DaVinci" icon={Link2} />
          </>
        ) : (
          <span className="text-[10px] text-content-tertiary italic pr-1">in&nbsp;progress</span>
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
