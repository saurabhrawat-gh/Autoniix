'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { motion, useMotionValue, useSpring, useReducedMotion, useAnimate } from 'framer-motion';
import confetti from 'canvas-confetti';
import { reviewApi, channelsApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Search, X, ClipboardCheck, ChevronRight, RotateCw,
  Inbox, ThumbsUp, ThumbsDown,
} from '@/lib/components/Icon';
import { Button, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';

const STATE_TABS = [
  { key: 'pending',     label: 'Pending',     color: 'text-status-warning', bg: 'bg-status-warning/10 text-status-warning' },
  { key: 'needs_edits', label: 'Needs edits', color: 'text-status-warning', bg: 'bg-status-warning/10 text-status-warning' },
  { key: 'approved',    label: 'Approved',    color: 'text-status-success', bg: 'bg-status-success/10 text-status-success' },
  { key: 'rejected',    label: 'Rejected',    color: 'text-status-error',   bg: 'bg-status-error/10 text-status-error' },
  { key: 'regenerating',label: 'Regenerating',color: 'text-accent',         bg: 'bg-accent/10 text-accent' },
];

const PRIORITY_MAP: Record<string, { label: string; color: string }> = {
  approved:     { label: 'Done',       color: 'text-status-success' },
  rejected:     { label: 'Rejected',   color: 'text-status-error' },
  needs_edits:  { label: 'Edits',      color: 'text-status-warning' },
  pending:      { label: 'Pending',    color: 'text-status-warning' },
  regenerating: { label: 'Regen…',     color: 'text-accent' },
};

export default function ReviewQueuePage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState('pending');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [channels, setChannels] = useState<any[]>([]);
  const [selChannel, setSelChannel] = useState('');
  const [q, setQ] = useState('');
  const [counts, setCounts] = useState<Record<string, number>>({});

  const load = useCallback(async (state: string) => {
    setLoading(true);
    try {
      const r = await reviewApi.queue(state, selChannel || undefined, 200);
      setItems((r as any).data?.data || r.data || []);
    } finally { setLoading(false); }
  }, [selChannel]);

  useEffect(() => { channelsApi.list(false).then(r => setChannels(r.data || [])); }, []);
  useEffect(() => { load(tab); }, [tab, selChannel, load]);

  useEffect(() => {
    Promise.all(
      STATE_TABS.map(t =>
        reviewApi.queue(t.key, undefined, 200)
          .then(r => ({ key: t.key, count: ((r as any).data?.data || r.data || []).length }))
          .catch(() => ({ key: t.key, count: 0 }))
      )
    ).then(results => {
      const map: Record<string, number> = {};
      results.forEach(r => { map[r.key] = r.count; });
      setCounts(map);
    });
  }, []);

  const filtered = useMemo(() => {
    if (!q) return items;
    const lq = q.toLowerCase();
    return items.filter(v =>
      (v.title || v.topic || v.content_id || '').toLowerCase().includes(lq) ||
      (v.channel_name || v.channel_id || '').toLowerCase().includes(lq)
    );
  }, [items, q]);

  const channelName = (v: any) =>
    channels.find(c => c.channel_id === v.channel_id)?.channel_name || v.channel_id || '—';

  const quickDecide = async (v: any, decision: 'approved' | 'rejected') => {
    try {
      await reviewApi.decide(v.content_id, decision);
      const label = decision === 'approved' ? 'Approved' : 'Rejected';
      showToast(`${label}: ${v.title || v.content_id}`, 'success');
      load(tab);
    } catch (e: any) { showToast(e?.message || 'Failed', 'error'); }
  };

  return (
    <main className="flex-1 flex flex-col min-h-0 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <ClipboardCheck size={18} className="text-accent" /> Review Queue
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Human review gate — approve, reject, or request edits before videos are delivered.
          </p>
        </div>
        <Button variant="outline" size="icon-sm" onClick={() => load(tab)} disabled={loading} aria-label="Refresh">
          <RotateCw size={13} className={cn(loading && 'animate-spin')} />
        </Button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
        {STATE_TABS.map(t => (
          <Button
            key={t.key}
            type="button"
            variant="ghost"
            onClick={() => setTab(t.key)}
            className={cn(
              'rounded-lg border px-3 py-2 h-auto justify-start text-left transition-all',
              tab === t.key ? 'border-accent/40 bg-accent/5 shadow-sm hover:bg-accent/5' : 'border-border bg-surface-0 hover:bg-surface-1'
            )}>
            <div>
              <div className={cn('text-xl font-bold tabular-nums leading-none', t.color)}>
                {counts[t.key] ?? '—'}
              </div>
              <div className="text-[10px] text-content-tertiary mt-0.5">{t.label}</div>
            </div>
          </Button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {/* State tabs */}
        <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
          {STATE_TABS.map(t => (
            <Button
              key={t.key}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setTab(t.key)}
              className={cn(
                'h-7 px-3 text-xs',
                tab === t.key
                  ? 'bg-surface-0 text-content-primary shadow-sm'
                  : 'text-content-tertiary hover:text-content-secondary'
              )}>
              {t.label}
              {counts[t.key] != null && counts[t.key] > 0 && (
                <span className={cn('ml-1.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold', t.bg)}>
                  {counts[t.key]}
                </span>
              )}
            </Button>
          ))}
        </div>

        {/* Channel filter */}
        <div className="min-w-[160px]">
          <Select value={selChannel || '__all__'} onValueChange={(v: string) => setSelChannel(v === '__all__' ? '' : v)}>
            <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="All channels" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All channels</SelectItem>
              {channels.map(c => <SelectItem key={c.channel_id} value={c.channel_id}>{c.channel_name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Search */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search title or channel…"
            leftIcon={<Search size={12} />}
            className="h-8 text-xs pr-7"
          />
          {q && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setQ('')}
              aria-label="Clear search"
              className="absolute right-1 top-1/2 -translate-y-1/2 w-5 h-5 text-content-tertiary hover:text-content-primary"
            >
              <X size={10} />
            </Button>
          )}
        </div>

        <span className="text-xs text-content-tertiary ml-auto whitespace-nowrap">
          {filtered.length} item{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Queue list */}
      <div className="flex-1 min-h-0 rounded-xl border border-border bg-surface-0 overflow-hidden flex flex-col">
        {/* Column headers */}
        <div className="shrink-0 grid grid-cols-[1fr_140px_90px_80px_120px] px-4 py-2.5 border-b border-border bg-surface-1/50 text-[10px] font-semibold uppercase tracking-wider text-content-tertiary">
          <span>Title / Channel</span>
          <span className="text-center">Status</span>
          <span className="text-center hidden sm:block">Mode</span>
          <span className="text-center hidden md:block">Score</span>
          <span className="text-right pr-1">Actions</span>
        </div>

        {/* Rows */}
        <div className="flex-1 overflow-y-auto divide-y divide-border">
          {loading && items.length === 0 ? (
            <div className="divide-y divide-border">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="px-4 py-3 flex items-center gap-3 animate-pulse">
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 w-2/3 bg-surface-2 rounded" />
                    <div className="h-2 w-1/3 bg-surface-2 rounded" />
                  </div>
                  <div className="w-20 h-5 bg-surface-2 rounded" />
                  <div className="w-24 h-6 bg-surface-2 rounded" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Inbox size={36} className="text-content-tertiary opacity-30" />
              <div className="text-sm font-medium text-content-primary">
                {tab === 'pending' ? 'Queue is empty' : `No ${tab.replace('_', ' ')} items`}
              </div>
              <div className="text-xs text-content-tertiary">
                {tab === 'pending'
                  ? 'No videos are waiting for human review right now.'
                  : 'Nothing in this state at the moment.'}
              </div>
            </div>
          ) : (
            filtered.map((v: any) => (
              <ReviewRow
                key={v.content_id}
                v={v}
                channelName={channelName(v)}
                tab={tab}
                onApprove={() => quickDecide(v, 'approved')}
                onReject={() => quickDecide(v, 'rejected')}
              />
            ))
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 px-4 py-2 border-t border-border bg-surface-1/30 text-[10px] text-content-tertiary">
          {filtered.length} of {items.length} items shown
          {tab === 'pending' && items.length > 0 && (
            <span className="ml-2 text-status-warning font-medium">● {items.length} awaiting decision</span>
          )}
        </div>
      </div>
    </main>
  );
}

function ReviewRow({
  v, channelName, tab, onApprove, onReject,
}: {
  v: any;
  channelName: string;
  tab: string;
  onApprove: () => void;
  onReject: () => void;
}) {
  const isPending = tab === 'pending' || tab === 'needs_edits';
  const stateInfo = PRIORITY_MAP[v.review_state] || PRIORITY_MAP[tab];
  const score = v.authenticity_score != null ? Number(v.authenticity_score).toFixed(2) : null;

  const reduce = useReducedMotion();
  const cardRef = useRef<HTMLDivElement>(null);
  const [approveScope, animateApprove] = useAnimate();
  const [rejectScope, animateReject] = useAnimate();
  const [bloom, setBloom] = useState(false);
  const [spotX, setSpotX] = useState('50%');
  const [spotY, setSpotY] = useState('50%');

  const rotX = useSpring(0, { stiffness: 400, damping: 30 });
  const rotY = useSpring(0, { stiffness: 400, damping: 30 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduce || !cardRef.current) return;
    const r = cardRef.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    rotX.set((0.5 - y) * 20);
    rotY.set((x - 0.5) * 20);
    setSpotX(`${x * 100}%`);
    setSpotY(`${y * 100}%`);
  };
  const handleMouseLeave = () => { rotX.set(0); rotY.set(0); };

  const handleApprove = async () => {
    if (!reduce && approveScope.current) {
      await animateApprove(approveScope.current, { scale: [1, 0.95, 1.08, 1] }, { duration: 0.3 });
    }
    setBloom(true);
    setTimeout(() => setBloom(false), 450);
    if (!reduce) {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#3d5c1a', '#fcffe1', '#5a8c3a', '#a3c97a'],
        disableForReducedMotion: true,
      });
    }
    onApprove();
  };

  const handleReject = async () => {
    if (!reduce && rejectScope.current) {
      await animateReject(rejectScope.current, { x: [0, 6, -6, 4, -4, 0] }, { duration: 0.32 });
    }
    onReject();
  };

  return (
    <motion.div
      ref={cardRef}
      style={{ rotateX: rotX, rotateY: rotY, transformPerspective: 800, position: 'relative' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="grid grid-cols-[1fr_140px_90px_80px_120px] items-center px-4 py-3 hover:bg-surface-1/60 transition-colors group"
    >
      {/* Spotlight */}
      {!reduce && (
        <span
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(circle 180px at ${spotX} ${spotY}, rgb(255 255 255 / 0.04), transparent)`,
          }}
        />
      )}

      {/* Title + channel */}
      <div className="min-w-0 pr-3">
        <Link href={`/dashboard/review/${v.content_id}`}
          className="text-sm font-medium text-content-primary hover:text-accent hover:underline truncate block">
          {v.title || v.topic || v.content_id}
        </Link>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-content-tertiary truncate">{channelName}</span>
          {v.created_at && (
            <>
              <span className="text-content-tertiary opacity-40">·</span>
              <span className="text-[10px] text-content-tertiary whitespace-nowrap">
                {new Date(v.created_at).toLocaleDateString()}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Review state */}
      <div className="flex justify-center">
        <span className={cn(
          'text-[10px] font-medium px-2 py-0.5 rounded-full',
          stateInfo?.color || 'text-content-tertiary',
          'bg-current/10'
        )}>
          {(v.review_state || tab).replace('_', ' ')}
        </span>
      </div>

      {/* Mode */}
      <div className="hidden sm:flex justify-center">
        <span className={cn(
          'text-[10px] font-medium px-2 py-0.5 rounded',
          v.content_mode === 'short'
            ? 'bg-accent/10 text-accent'
            : 'bg-status-info/10 text-status-info'
        )}>
          {v.content_mode === 'short' ? 'Short' : 'Long'}
        </span>
      </div>

      {/* Score */}
      <div className="hidden md:flex justify-center">
        {score ? (
          <span className={cn(
            'text-xs font-mono',
            Number(score) >= 8 ? 'text-status-success' :
            Number(score) >= 6 ? 'text-status-warning' : 'text-status-error'
          )}>
            {score}
          </span>
        ) : (
          <span className="text-[11px] text-content-tertiary">—</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-1 pr-1 relative">
        {bloom && (
          <motion.span
            className="absolute inset-0 rounded-full bg-status-success/30 pointer-events-none"
            initial={{ scale: 1, opacity: 0.6 }}
            animate={{ scale: 3, opacity: 0 }}
            transition={{ duration: 0.4 }}
          />
        )}
        {isPending && (
          <>
            <div ref={approveScope}>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={handleApprove}
                title="Quick approve"
                aria-label="Quick approve"
                className="w-7 h-7 text-content-tertiary hover:text-status-success hover:bg-status-success/10"
              >
                <ThumbsUp size={13} />
              </Button>
            </div>
            <div ref={rejectScope}>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={handleReject}
                title="Quick reject"
                aria-label="Quick reject"
                className="w-7 h-7 text-content-tertiary hover:text-status-error hover:bg-status-error/10"
              >
                <ThumbsDown size={13} />
              </Button>
            </div>
          </>
        )}
        <Link href={`/dashboard/review/${v.content_id}`} title="Open review"
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-accent/10 text-content-tertiary hover:text-accent transition-colors">
          <ChevronRight size={14} />
        </Link>
      </div>
    </motion.div>
  );
}
