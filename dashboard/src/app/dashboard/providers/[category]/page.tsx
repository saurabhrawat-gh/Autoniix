'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { providersApi, channelsApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { confirmDialog } from '@/lib/components/ConfirmDialog';
import {
  Plus, Activity, Trash2, ArrowUp, ArrowDown, X, Check,
  ShieldCheck, AlertTriangle, HelpCircle, Loader2, Eye, EyeOff, RotateCw,
  Terminal, SlidersHorizontal, Play, Star, ExternalLink, GripVertical, ChevronDown,
} from '@/lib/components/Icon';
import {
  DndContext, closestCenter,
  PointerSensor, KeyboardSensor,
  useSensor, useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext, useSortable,
  verticalListSortingStrategy, arrayMove,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  Button,
  Input,
  Textarea,
  Switch as UISwitch,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Label,
} from '@/lib/ui';

// Normalise a value that *should* be an array but may arrive as a JSON
// string (JSONB columns with no asyncpg codec) or null. Prevents a stray
// `.filter`/`.map` from crashing the whole page via the error boundary.
function asArray<T = any>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? (parsed as T[]) : [];
    } catch {
      return [];
    }
  }
  return [];
}

type HealthStatus = 'healthy' | 'failing' | 'untested';
function getHealth(c: any): HealthStatus {
  if (c.last_health_ok === true) return 'healthy';
  if (c.last_health_ok === false) return 'failing';
  return 'untested';
}
const HEALTH_CHIP: Record<HealthStatus, string> = {
  healthy:  'bg-status-success/15 text-status-success',
  failing:  'bg-status-error/15 text-status-error',
  untested: 'bg-surface-2 text-content-tertiary',
};
const HEALTH_ICON: Record<HealthStatus, React.ReactNode> = {
  healthy:  <ShieldCheck size={11} className="text-status-success" />,
  failing:  <AlertTriangle size={11} className="text-status-error" />,
  untested: <HelpCircle size={11} className="text-content-tertiary" />,
};

function Switch({ checked, onChange, title, disabled }: {
  checked: boolean; onChange: () => void; title?: string; disabled?: boolean;
}) {
  return (
    <UISwitch
      checked={checked}
      onCheckedChange={() => !disabled && onChange()}
      disabled={disabled}
      aria-label={title}
    />
  );
}

const POLICY_OPTIONS = [
  { value: 'balanced',        label: 'Balanced',        desc: 'Cost + quality + speed tradeoff' },
  { value: 'cheapest',        label: 'Cheapest',        desc: 'Minimize cost per call' },
  { value: 'fastest',         label: 'Fastest',         desc: 'Minimize latency p95' },
  { value: 'highest_quality', label: 'Highest quality', desc: 'Maximize output quality score' },
];

export default function ProviderCategoryPage() {
  const { category } = useParams<{ category: string }>();
  const decoded = decodeURIComponent(category);
  const searchParams = useSearchParams();
  const { showToast } = useToast();
  const [creds, setCreds] = useState<any[]>([]);
  const [chain, setChain] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, any>>({});
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  // Wave 2 — routing policy
  const [route, setRoute] = useState<any | null>(null);
  const [savingRoute, setSavingRoute] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState('balanced');
  const [primaryCredId, setPrimaryCredId] = useState<number | null>(null);
  // Wave 2 — sandbox runner
  const [sandboxCredId, setSandboxCredId] = useState<number | null>(null);
  const [sandboxCapability, setSandboxCapability] = useState('text-gen');
  const [sandboxPrompt, setSandboxPrompt] = useState('');
  const [sandboxRunning, setSandboxRunning] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<any | null>(null);
  // Wave 2 — health sparklines (last 20 per cred)
  const [healthHistory, setHealthHistory] = useState<Record<number, any[]>>({});

  // Wave 4 — content-mode aware chain editing
  // selectedMode === null means "All modes" (NULL row in DB)
  const [contentModes, setContentModes] = useState<{ name: string; label: string }[]>([]);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const [resolvedChain, setResolvedChain] = useState<any[]>([]);
  // AE-72 — rotation status
  const [rotationByCredId, setRotationByCredId] = useState<Record<number, any>>({});
  const [rotatingCred, setRotatingCred] = useState<any | null>(null);
  // AE-73 — context switcher
  const [scopeType, setScopeType] = useState<'workspace' | 'channel'>('workspace');
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [channels, setChannels] = useState<any[]>([]);
  const [scopeDropdownOpen, setScopeDropdownOpen] = useState(false);
  const scopeDropdownRef = useRef<HTMLDivElement>(null);
  // AE-73 — dnd sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.credentials(decoded).then(r => setCreds(r.data || [])),
      providersApi.chainsV2({
        scope: scopeType,
        scope_id: scopeId || undefined,
        content_mode: selectedMode || undefined,
        category: decoded,
      })
        .then(r => setChain(r.data || []))
        .catch(() => setChain([])),
      providersApi.resolved({
        category: decoded,
        channel_id: scopeType === 'channel' ? (scopeId || undefined) : undefined,
        content_mode: selectedMode || undefined,
      })
        .then(r => setResolvedChain(r.data || []))
        .catch(() => setResolvedChain([])),
      providersApi.allRotationStatus({ category: decoded })
        .then(r => {
          const map: Record<number, any> = {};
          (r.data || []).forEach((s: any) => { map[s.id] = s; });
          setRotationByCredId(map);
        })
        .catch(() => {}),
      providersApi.routes('workspace').then(r => {
        const found = (r.data || []).find((rt: any) => rt.category === decoded);
        if (found) {
          setRoute(found);
          setSelectedPolicy(found.policy || 'balanced');
          setPrimaryCredId(found.primary_credential_id || null);
        }
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [decoded, selectedMode, scopeType, scopeId]);

  // Load the content-mode catalog once.
  useEffect(() => {
    providersApi.contentModes()
      .then(r => setContentModes(r.data || []))
      .catch(() => setContentModes([]));
  }, []);

  // AE-73 — load channels list for context switcher
  useEffect(() => {
    channelsApi.list()
      .then(r => setChannels(r.data || []))
      .catch(() => {});
  }, []);

  // AE-73 — close scope dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (scopeDropdownRef.current && !scopeDropdownRef.current.contains(e.target as Node)) {
        setScopeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Auto-open add dialog when arriving via ?add=1 (from Marketplace / onboarding)
  useEffect(() => {
    if (searchParams.get('add') === '1') setShowAdd(true);
  }, [searchParams]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (creds.length > 0) {
      creds.forEach(c => loadHealthHistory(c.id));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [creds.length]);

  // AE-75 — real-time health badge updates via SSE
  useEffect(() => {
    const es = new EventSource(
      providersApi.healthStreamUrl(decoded),
      { withCredentials: true },
    );
    es.addEventListener('health_change', (e: MessageEvent) => {
      try {
        const evt = JSON.parse(e.data);
        setCreds(prev => prev.map((c: any) =>
          c.id === evt.credential_id
            ? { ...c, last_health_ok: evt.ok, last_health_at: evt.at }
            : c,
        ));
      } catch { /* ignore malformed event */ }
    });
    es.onerror = () => { /* auto-reconnects */ };
    return () => es.close();
  }, [decoded]);

  const saveChain = useCallback((ids: number[]) =>
    providersApi.upsertChainV2({
      scope: scopeType,
      scope_id: scopeId,
      content_mode: selectedMode,
      category: decoded,
      credential_ids: ids,
    }).then(refresh)
  , [decoded, selectedMode, scopeType, scopeId, refresh]);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = chain.findIndex(c => c.credential_id === active.id);
    const newIdx = chain.findIndex(c => c.credential_id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    const reordered = arrayMove(chain, oldIdx, newIdx);
    setChain(reordered); // optimistic
    providersApi.upsertChainV2({
      scope: scopeType, scope_id: scopeId,
      content_mode: selectedMode, category: decoded,
      credential_ids: reordered.map(c => c.credential_id),
    }).then(refresh).catch(() => {
      refresh();
      showToast('Reorder failed — reverted', 'error');
    });
  }, [chain, decoded, selectedMode, scopeType, scopeId, refresh, showToast]);

  const moveChain = (idx: number, dir: -1 | 1) => {
    const ids = chain.map(c => c.credential_id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    saveChain(ids);
  };

  const addToChain = (credId: number) => {
    const ids = chain.map(c => c.credential_id);
    if (ids.includes(credId)) return;
    saveChain([...ids, credId]);
  };

  const removeFromChain = (credId: number) => {
    const ids = chain.map(c => c.credential_id).filter(x => x !== credId);
    saveChain(ids);
  };

  const toggleCredentialEnabled = async (cred: any) => {
    const next = !cred.enabled;
    setCreds(prev => prev.map(c => c.id === cred.id ? { ...c, enabled: next } : c));
    try {
      await providersApi.setCredentialEnabled(cred.id, next);
      showToast(next ? `${cred.label} enabled` : `${cred.label} disabled`, 'success');
      refresh();
    } catch (e: any) {
      setCreds(prev => prev.map(c => c.id === cred.id ? { ...c, enabled: !next } : c));
      showToast(e?.message || 'Failed to toggle credential', 'error');
    }
  };

  const toggleChainEntryEnabled = async (entry: any) => {
    if (!entry?.id) {
      showToast('Chain entry id missing — reload the page', 'error');
      return;
    }
    const next = !(entry.is_enabled ?? true);
    try {
      await providersApi.setChainEntryEnabled(entry.id, next);
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to toggle chain entry', 'error');
    }
  };

  const toggleDefaultFallback = async (cred: any) => {
    try {
      if (cred.is_default_fallback) {
        await providersApi.clearDefaultFallback(cred.id);
        showToast('Default fallback cleared', 'success');
      } else {
        await providersApi.setDefaultFallback(cred.id);
        showToast(`${cred.label} is now the default fallback`, 'success');
      }
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to update default fallback', 'error');
    }
  };

  const testCredential = async (id: number) => {
    setTestingId(id);
    try {
      const r = await providersApi.testCredential(id);
      const result = r.data;
      setTestResults(prev => ({ ...prev, [id]: result }));
      if (result.ok) {
        showToast(`Connection OK · ${result.latency_ms}ms`, 'success');
      } else {
        showToast(`Test failed: ${result.error || 'unknown error'}`, 'error');
      }
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Test failed', 'error');
    }
    setTestingId(null);
  };

  const deleteCredential = async (id: number) => {
    const ok = await confirmDialog({
      title: 'Delete credential?',
      description: 'This cannot be undone. Any chains using this credential will need to be re-routed.',
      destructive: true,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setDeletingIds(prev => { const s = new Set(prev); s.add(id); return s; });
    try {
      await providersApi.deleteCredential(id);
      showToast('Credential deleted', 'success');
      setTimeout(() => {
        setCreds(prev => prev.filter(c => c.id !== id));
        setDeletingIds(prev => { const s = new Set(prev); s.delete(id); return s; });
        refresh();
      }, 300);
    } catch (e: any) {
      setDeletingIds(prev => { const s = new Set(prev); s.delete(id); return s; });
      showToast(e?.message || 'Delete failed', 'error');
    }
  };

  const loadHealthHistory = async (credId: number) => {
    try {
      const r = await providersApi.health(credId, 20);
      setHealthHistory(prev => ({ ...prev, [credId]: r.data || [] }));
    } catch {}
  };

  const saveRoute = async () => {
    setSavingRoute(true);
    try {
      await providersApi.upsertRoute(decoded, {
        policy: selectedPolicy, primary_credential_id: primaryCredId,
      });
      showToast('Routing policy saved', 'success');
      refresh();
    } catch (e: any) { showToast(e?.message || 'Save failed', 'error'); }
    setSavingRoute(false);
  };

  const runSandbox = async () => {
    if (!sandboxCredId) return;
    setSandboxRunning(true);
    setSandboxResult(null);
    try {
      const r = await providersApi.sandboxRun({
        credential_id: sandboxCredId,
        capability: sandboxCapability,
        prompt: sandboxPrompt || undefined,
        text: sandboxCapability.startsWith('tts') ? (sandboxPrompt || 'Hello, this is a test.') : undefined,
      });
      setSandboxResult(r.data);
    } catch (e: any) {
      setSandboxResult({ ok: false, error: e?.message || 'Run failed', latency_ms: 0, output: {} });
    }
    setSandboxRunning(false);
  };

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <h1 className="text-xl font-semibold text-content-primary">{decoded}</h1>
        {/* AE-73 Context Switcher */}
        <div className="relative" ref={scopeDropdownRef}>
          <button
            type="button"
            onClick={() => setScopeDropdownOpen(v => !v)}
            className="flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface-0 text-xs text-content-primary hover:border-accent/50 hover:bg-surface-1 transition-colors">
            <span className="font-medium">
              {scopeType === 'workspace'
                ? 'Workspace (default)'
                : (channels.find((c: any) => String(c.id) === scopeId)?.name || 'Channel')}
            </span>
            <ChevronDown size={11} className={cn('text-content-tertiary transition-transform', scopeDropdownOpen && 'rotate-180')} />
          </button>
          {scopeDropdownOpen && (
            <div className="absolute left-0 top-full mt-1 w-60 rounded-lg border border-border bg-surface-0 shadow-modal z-30 py-1.5 text-xs">
              {/* Workspace */}
              <div className="px-3 py-1 text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">Workspace</div>
              <button
                type="button"
                className={cn('flex w-full items-center gap-2 px-3 py-1.5 hover:bg-surface-1 transition-colors',
                  scopeType === 'workspace' ? 'text-accent font-semibold' : 'text-content-primary')}
                onClick={() => { setScopeType('workspace'); setScopeId(null); setScopeDropdownOpen(false); }}>
                {scopeType === 'workspace'
                  ? <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                  : <span className="w-1.5 h-1.5 rounded-full border border-border shrink-0" />}
                Default (all channels)
              </button>

              {/* Channels — only shown when at least one channel exists */}
              {channels.length > 0 && (
                <>
                  <div className="my-1 border-t border-border" />
                  <div className="px-3 py-1 text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">Channels</div>
                  {channels.map((ch: any) => {
                    const isActive = scopeType === 'channel' && scopeId === String(ch.id);
                    return (
                      <button
                        key={ch.id}
                        type="button"
                        className={cn('flex w-full items-center gap-2 px-3 py-1.5 hover:bg-surface-1 transition-colors',
                          isActive ? 'text-accent font-semibold' : 'text-content-primary')}
                        onClick={() => { setScopeType('channel'); setScopeId(String(ch.id)); setScopeDropdownOpen(false); }}>
                        {isActive
                          ? <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                          : <span className="w-1.5 h-1.5 rounded-full border border-border shrink-0" />}
                        {ch.name}
                      </button>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {scopeType === 'channel' && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs text-status-error hover:bg-status-error/10 hover:text-status-error h-8"
              onClick={async () => {
                await providersApi.deleteChainV2({ scope: 'channel', scope_id: scopeId || undefined, category: decoded });
                setScopeType('workspace');
                setScopeId(null);
                showToast('Channel override cleared', 'success');
              }}>
              Clear channel override
            </Button>
          )}
          <Button type="button" variant="outline" size="icon-sm" onClick={refresh} disabled={loading} aria-label="Refresh" className="w-8 h-8">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </Button>
          <Button type="button" size="sm" onClick={() => setShowAdd(true)} leftIcon={<Plus size={13} />}>
            Add credential
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 rounded-md bg-surface-2 animate-pulse" />)}
        </div>
      ) : (
        <div className="space-y-5">
          {/* ── Priority chain ──────────────────────────── */}
          <section>
            <div className="mb-2 flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h2 className="text-sm font-semibold text-content-primary">Priority chain</h2>
                <p className="text-xs text-content-tertiary mt-0.5">
                  Resolution order — the first healthy provider handles the call. On error it falls through to the next.
                  {chain.length === 0 && ' Add credentials below, then drag them into the chain.'}
                </p>
                <div className="mt-2 rounded-md border border-border/50 bg-surface-1/50 px-3 py-2 text-[11px] text-content-tertiary flex items-start gap-2">
                  <HelpCircle size={12} className="shrink-0 mt-px text-content-tertiary/60" />
                  <span>
                    <span className="font-medium text-content-secondary">Chain vs. Policy — </span>
                    The <em>chain</em> is your ordered fallback list (drag to reorder; top = highest priority).
                    The <em>routing policy</em> below controls how the runtime picks a provider when multiple are healthy —
                    e.g. &ldquo;Cheapest&rdquo; picks by cost, &ldquo;Balanced&rdquo; blends cost&thinsp;+&thinsp;quality.
                  </span>
                </div>
              </div>
              {/* Content-mode segmented control */}
              <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
                {[{ name: null as string | null, label: 'All modes' }, ...contentModes].map((m: any) => (
                  <Button
                    key={m.name ?? '__all__'}
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedMode(m.name)}
                    className={cn('h-7 px-2.5 text-[11px]',
                      selectedMode === m.name
                        ? 'bg-surface-0 text-content-primary shadow-sm hover:bg-surface-0'
                        : 'text-content-tertiary hover:text-content-secondary')}>
                    {m.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Effective chain banner (mirrors what the runtime will pick) */}
            {resolvedChain.length > 0 && (
              <div className="mb-2 rounded-md border border-border bg-surface-1/40 px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] uppercase tracking-wide text-content-tertiary">Effective chain</span>
                  <span className="text-[10px] text-content-tertiary">
                    {selectedMode ? `for mode ${selectedMode}` : '(any content mode)'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {resolvedChain.map((r: any, i: number) => (
                    <span key={`${r.credential_id}-${r.origin}`}
                      className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-surface-0 border border-border">
                      <span className="text-content-tertiary">{i + 1}.</span>
                      <span className="text-content-primary font-medium">{r.label}</span>
                      {r.model && <span className="text-content-tertiary font-mono">· {r.model}</span>}
                      <span className={cn('text-[9px] px-1 rounded',
                        r.origin === 'default' ? 'bg-status-warning/10 text-status-warning' :
                        r.origin.startsWith('channel') ? 'bg-accent/10 text-accent' :
                        r.origin.startsWith('workspace') ? 'bg-status-success/10 text-status-success' :
                        'bg-status-info/10 text-status-info')}>{r.origin}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
                {chain.length === 0 ? (
                  <div className="p-5 text-sm text-content-tertiary text-center">
                    No chain configured yet. Use "Add to chain" on a credential below.
                    {scopeType === 'channel' && (
                      <span className="ml-1 text-content-tertiary">
                        Channel inherits workspace chain by default.
                      </span>
                    )}
                  </div>
                ) : (
                  <SortableContext items={chain.map(c => c.credential_id)} strategy={verticalListSortingStrategy}>
                    <div className="divide-y divide-border">
                      {chain.map((c: any, i: number) => (
                        <SortableChainItem
                          key={c.id ?? c.credential_id}
                          entry={c}
                          index={i}
                          total={chain.length}
                          toggleChainEntryEnabled={toggleChainEntryEnabled}
                          moveChain={moveChain}
                          removeFromChain={removeFromChain}
                          inherited={scopeType === 'channel' && c.scope === 'workspace'}
                        />
                      ))}
                    </div>
                  </SortableContext>
                )}
              </div>
            </DndContext>
          </section>

          {/* ── Credentials ─────────────────────────────── */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-sm font-semibold text-content-primary">Credentials</h2>
                <p className="text-xs text-content-tertiary mt-0.5">Secrets are stored in Vault. Never written to your repo or database.</p>
              </div>
              <span className="text-xs text-content-tertiary">{creds.length} credential{creds.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
              {creds.length === 0 ? (
                <div className="p-8 text-sm text-content-tertiary text-center">
                  No credentials yet.{' '}
                  <Button type="button" variant="link" size="sm" onClick={() => setShowAdd(true)} className="h-auto p-0 text-accent">Add one →</Button>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {creds.map((c: any) => {
                    const health = getHealth(c);
                    const inChain = chain.some(x => x.credential_id === c.id);
                    const testResult = testResults[c.id];
                    const isTesting = testingId === c.id;
                    return (
                      <div key={c.id} className={cn('px-4 py-3 transition-opacity duration-300', !c.enabled && 'opacity-60', deletingIds.has(c.id) && 'opacity-0 pointer-events-none')}>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={cn(
                                'text-sm font-medium text-content-primary',
                                !c.enabled && 'line-through'
                              )}>{c.label}</span>
                              {!c.enabled && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary font-medium">disabled</span>
                              )}
                              <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1', HEALTH_CHIP[health])}>
                                {HEALTH_ICON[health]}
                                {health}
                              </span>
                              {inChain && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent font-medium">in chain</span>
                              )}
                              {c.is_default_fallback && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-warning/15 text-status-warning font-medium flex items-center gap-1">
                                  <Star size={9} /> Default fallback
                                </span>
                              )}
                              {c.model && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-secondary font-mono">{c.model}</span>
                              )}
                            </div>
                            <div className="text-[11px] text-content-tertiary font-mono mt-0.5">
                              {c.provider_name} · {c.vault_path}
                            </div>
                            {/* Rotation age badge */}
                            {rotationByCredId[c.id] != null && (() => {
                              const rs = rotationByCredId[c.id];
                              const days = rs.days_since_rotation;
                              if (days == null) return null;
                              const isRed = days >= 90;
                              const isAmber = days >= 60 && !isRed;
                              if (!isAmber && !isRed) return null;
                              return (
                                <span className={cn(
                                  'text-[10px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1 w-fit mt-0.5',
                                  isRed ? 'bg-status-error/15 text-status-error' : 'bg-status-warning/15 text-status-warning'
                                )}>
                                  <RotateCw size={9} />
                                  {isRed ? 'Key overdue' : 'Rotation due'} · {days}d
                                </span>
                              );
                            })()}
                            {/* Health sparkline */}
                            {healthHistory[c.id] && healthHistory[c.id].length > 0 && (
                              <div className="mt-1.5">
                                <HealthSparkline data={healthHistory[c.id]} />
                              </div>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-1.5 shrink-0">
                            <Switch
                              checked={!!c.enabled}
                              onChange={() => toggleCredentialEnabled(c)}
                              title={c.enabled ? 'Disable this credential everywhere' : 'Enable this credential'}
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="icon-sm"
                              onClick={() => toggleDefaultFallback(c)}
                              title={c.is_default_fallback ? 'Clear default fallback' : 'Set as default fallback (always tried last)'}
                              aria-label="Toggle default fallback"
                              className={cn('w-7 h-7',
                                c.is_default_fallback
                                  ? 'bg-status-warning/15 text-status-warning hover:bg-status-warning/25'
                                  : 'border-border text-content-tertiary')}>
                              <Star size={12} />
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setRotatingCred(c)}
                              leftIcon={<RotateCw size={11} />}
                              className="h-7 px-2.5 text-xs"
                              title="Rotate API key (safe-swap: tested before replacing)"
                            >
                              Rotate
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => testCredential(c.id)}
                              disabled={isTesting}
                              leftIcon={isTesting ? <Loader2 size={11} className="animate-spin" /> : <Activity size={11} />}
                              className="h-7 px-2.5 text-xs"
                            >
                              {isTesting ? 'Testing…' : 'Test'}
                            </Button>
                            {!inChain ? (
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => addToChain(c.id)}
                                leftIcon={<Plus size={11} />}
                                className="h-7 px-2.5 text-xs text-accent border-accent/40 hover:bg-accent/10"
                              >
                                Add to chain
                              </Button>
                            ) : (
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => removeFromChain(c.id)}
                                leftIcon={<X size={11} />}
                                className="h-7 px-2.5 text-xs"
                              >
                                Remove
                              </Button>
                            )}
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => deleteCredential(c.id)}
                              aria-label="Delete credential"
                              className="w-7 h-7 text-content-tertiary hover:text-status-error hover:bg-status-error/10"
                            >
                              <Trash2 size={13} />
                            </Button>
                          </div>
                        </div>

                        {/* Test result inline */}
                        {testResult && (
                          <div className={cn(
                            'mt-2 text-xs rounded px-2.5 py-1.5 flex items-center gap-2',
                            testResult.ok ? 'bg-status-success/10 text-status-success' : 'bg-status-error/10 text-status-error'
                          )}>
                            {testResult.ok ? <Check size={11} /> : <X size={11} />}
                            {testResult.ok
                              ? `Connection OK · ${testResult.latency_ms}ms`
                              : `Failed: ${testResult.error || 'unknown'}`}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
          {/* ── Routing policy ─────────────────────────── */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-sm font-semibold text-content-primary flex items-center gap-1.5">
                  <SlidersHorizontal size={13} className="text-accent" /> Routing policy
                </h2>
                <p className="text-xs text-content-tertiary mt-0.5">
                  How the runtime resolves which credential to use for this category.
                </p>
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface-0 p-4 space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {POLICY_OPTIONS.map(opt => (
                  <Button
                    key={opt.value}
                    type="button"
                    variant="ghost"
                    onClick={() => setSelectedPolicy(opt.value)}
                    className={cn('h-auto justify-start text-left rounded-md border px-3 py-2.5 flex-col items-start',
                      selectedPolicy === opt.value
                        ? 'border-accent/50 bg-accent/5 text-content-primary hover:bg-accent/10'
                        : 'border-border text-content-tertiary hover:border-border hover:bg-surface-1')}>
                    <div className="text-xs font-semibold">{opt.label}</div>
                    <div className="text-[10px] text-content-tertiary mt-0.5">{opt.desc}</div>
                  </Button>
                ))}
              </div>
              {creds.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase text-content-tertiary mb-1">Primary credential (optional)</div>
                  <div className="w-full sm:w-72">
                  <Select value={primaryCredId == null ? '__auto__' : String(primaryCredId)} onValueChange={(v: string) => setPrimaryCredId(v === '__auto__' ? null : Number(v))}>
                    <SelectTrigger><SelectValue placeholder="Auto (from chain)" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__auto__">Auto (from chain)</SelectItem>
                      {creds.filter(c => c.enabled).map((c: any) => (
                        <SelectItem key={c.id} value={String(c.id)}>{c.label} ({c.provider_name})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2 pt-1">
                <Button
                  type="button"
                  size="sm"
                  onClick={saveRoute}
                  disabled={savingRoute}
                  loading={savingRoute}
                  leftIcon={!savingRoute ? <Check size={11} /> : undefined}
                >
                  Save policy
                </Button>
                {route && (
                  <span className="text-[11px] text-content-tertiary">
                    Current: <span className="text-content-secondary font-medium">{route.policy}</span>
                  </span>
                )}
              </div>
            </div>
          </section>

          {/* ── Sandbox runner ──────────────────────────── */}
          {creds.length > 0 && (
            <section>
              <div className="mb-2">
                <h2 className="text-sm font-semibold text-content-primary flex items-center gap-1.5">
                  <Terminal size={13} className="text-accent" /> Sandbox runner
                </h2>
                <p className="text-xs text-content-tertiary mt-0.5">
                  Run a live test inference against a credential. Results are logged but never stored in production.
                </p>
              </div>
              <div className="rounded-md border border-border bg-surface-0 p-4 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <div className="text-[10px] uppercase text-content-tertiary mb-1">Credential</div>
                    <Select value={sandboxCredId == null ? '' : String(sandboxCredId)} onValueChange={(v: string) => setSandboxCredId(v ? Number(v) : null)}>
                      <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                      <SelectContent>
                        {creds.map((c: any) => (
                          <SelectItem key={c.id} value={String(c.id)}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase text-content-tertiary mb-1">Capability</div>
                    <Select value={sandboxCapability} onValueChange={setSandboxCapability}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="text-gen">text-gen</SelectItem>
                        <SelectItem value="tts-standard">tts-standard</SelectItem>
                        <SelectItem value="image-gen">image-gen</SelectItem>
                        <SelectItem value="health">health-check</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      onClick={runSandbox}
                      disabled={!sandboxCredId || sandboxRunning}
                      loading={sandboxRunning}
                      leftIcon={!sandboxRunning ? <Play size={12} /> : undefined}
                      className="w-full h-[34px]"
                    >
                      Run
                    </Button>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-content-tertiary mb-1">
                    {sandboxCapability === 'tts-standard' ? 'Text to speak' : 'Prompt'}
                  </div>
                  <Textarea
                    value={sandboxPrompt}
                    onChange={e => setSandboxPrompt(e.target.value)}
                    placeholder={sandboxCapability === 'tts-standard'
                      ? 'Hello, this is a voice test.'
                      : sandboxCapability === 'image-gen'
                      ? 'A colorful sunset over mountains'
                      : 'Say hello in one sentence.'}
                    className="h-16 font-mono resize-none"
                  />
                </div>
                {/* Result */}
                {sandboxResult && (
                  <div className={cn('rounded-md border px-3 py-2.5 text-xs space-y-1',
                    sandboxResult.ok ? 'border-status-success/30 bg-status-success/5' : 'border-status-error/30 bg-status-error/5')}>
                    <div className="flex items-center gap-2 font-semibold">
                      {sandboxResult.ok
                        ? <><Check size={11} className="text-status-success" /><span className="text-status-success">Success</span></>
                        : <><X size={11} className="text-status-error" /><span className="text-status-error">Error</span></>}
                      <span className="text-content-tertiary font-normal ml-auto">{sandboxResult.latency_ms}ms</span>
                      {sandboxResult.cost_usd != null && (
                        <span className="text-content-tertiary font-normal font-mono">${sandboxResult.cost_usd.toFixed(6)}</span>
                      )}
                    </div>
                    {sandboxResult.error && (
                      <div className="text-status-error font-mono text-[11px]">{sandboxResult.error}</div>
                    )}
                    {sandboxResult.output?.text && (
                      <div className="text-content-secondary bg-surface-1 rounded p-2 font-mono text-[11px] whitespace-pre-wrap">
                        {sandboxResult.output.text}
                      </div>
                    )}
                    {sandboxResult.output?.image_url && (
                      <a href={sandboxResult.output.image_url} target="_blank" rel="noopener noreferrer"
                        className="text-accent hover:underline font-mono text-[11px] flex items-center gap-1">
                        View generated image →
                      </a>
                    )}
                    {sandboxResult.output?.note && (
                      <div className="text-content-tertiary text-[11px]">{sandboxResult.output.note}</div>
                    )}
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      )}

      {showAdd && (
        <AddCredentialDialog
          category={decoded}
          initialProvider={searchParams.get('provider') ?? undefined}
          onClose={() => setShowAdd(false)}
          onAdded={(newCredId?: number) => {
            setShowAdd(false);
            if (newCredId) addToChain(newCredId); // auto-activate immediately
            else refresh();
            showToast('Credential saved and added to chain ✓', 'success');
          }}
        />
      )}
      {rotatingCred && (
        <RotateCredentialDialog
          cred={rotatingCred}
          onClose={() => setRotatingCred(null)}
          onRotated={() => { setRotatingCred(null); refresh(); showToast('Key rotated ✓', 'success'); }}
        />
      )}
    </main>
  );
}

// Provider display aliases to hide (duplicate backend registrations).
// fish_audio and fishaudio are the SAME class registered twice — show only fish_audio.
const PROVIDER_ALIASES_TO_HIDE = new Set(['fishaudio']);

// Providers that need NO API key (free, bundled services).
const NO_KEY_PROVIDERS = new Set(['edge_tts', 'mock_llm', 'placeholder', 'mock_search']);

// Hints shown in Step 2 below the API key field.
const KEY_HINTS: Record<string, { prefix: string; helpUrl: string; hint: string }> = {
  openai:       { prefix: 'sk-',       helpUrl: 'https://platform.openai.com/api-keys',          hint: 'Starts with sk- · Get it from platform.openai.com/api-keys' },
  anthropic:    { prefix: 'sk-ant-',   helpUrl: 'https://console.anthropic.com/settings/keys',   hint: 'Starts with sk-ant- · Get it from console.anthropic.com' },
  gemini:       { prefix: 'AIza',      helpUrl: 'https://aistudio.google.com/app/apikey',         hint: 'Starts with AIza · Get it from Google AI Studio' },
  groq:         { prefix: 'gsk_',      helpUrl: 'https://console.groq.com/keys',                  hint: 'Starts with gsk_ · Get it from console.groq.com' },
  fish_audio:   { prefix: '',          helpUrl: 'https://fish.audio/go-api/',                     hint: 'Get your API key at fish.audio → account → API Credentials' },
  elevenlabs:   { prefix: '',          helpUrl: 'https://elevenlabs.io/app/settings/api-keys',    hint: 'Get it from elevenlabs.io → Profile → API Keys' },
  openai_dalle: { prefix: 'sk-',       helpUrl: 'https://platform.openai.com/api-keys',          hint: 'Same key as your OpenAI account — DALL·E is included' },
  stability:    { prefix: 'sk-',       helpUrl: 'https://platform.stability.ai/account/keys',    hint: 'Get it from platform.stability.ai → API Keys' },
  fal_ai:       { prefix: '',          helpUrl: 'https://fal.ai/dashboard/keys',                  hint: 'Get it from fal.ai → Dashboard → Keys' },
  perplexity:   { prefix: 'pplx-',     helpUrl: 'https://www.perplexity.ai/settings/api',        hint: 'Starts with pplx- · Get it from perplexity.ai → Settings → API' },
  serper:       { prefix: '',          helpUrl: 'https://serper.dev/api-key',                     hint: 'Get it from serper.dev → API Key (2,500 free searches/month)' },
  serpapi:      { prefix: '',          helpUrl: 'https://serpapi.com/manage-api-key',              hint: 'Get it from serpapi.com → Dashboard → API Key' },
  tavily:       { prefix: 'tvly-',     helpUrl: 'https://app.tavily.com/home',                    hint: 'Starts with tvly- · Get it from app.tavily.com' },
  pexels:       { prefix: '',          helpUrl: 'https://www.pexels.com/api/',                    hint: 'Get it at pexels.com/api — completely free to sign up' },
  pixabay:      { prefix: '',          helpUrl: 'https://pixabay.com/api/docs/',                  hint: 'Get it at pixabay.com/api — completely free to sign up' },
};

// Per-provider voice/model hints shown in Step 3.
// For TTS the "model" is really a voice — explain that clearly.
const VOICE_HINTS: Record<string, {
  fieldLabel: string;
  placeholder: string;
  hint: string;
  suggestions?: string[];
}> = {
  edge_tts: {
    fieldLabel: 'Voice',
    placeholder: 'en-US-AriaNeural',
    hint: 'Which Microsoft voice should speak the narration? Leave blank for the default (Aria — American female). Pick from the list or type a voice name.',
    suggestions: [
      'en-US-AriaNeural — Female, American (default)',
      'en-US-GuyNeural — Male, American',
      'en-US-JennyNeural — Female, American (friendly)',
      'en-GB-SoniaNeural — Female, British',
      'en-GB-RyanNeural — Male, British',
      'en-AU-NatashaNeural — Female, Australian',
      'en-IN-NeerjaNeural — Female, Indian English',
    ],
  },
  elevenlabs: {
    fieldLabel: 'Voice ID',
    placeholder: '21m00Tcm4TlvDq8ikWAM',
    hint: 'The ID of the voice you want to use. Find it in ElevenLabs → Voices → click any voice → copy the Voice ID string shown below the name.',
  },
  fish_audio: {
    fieldLabel: 'Voice Reference ID',
    placeholder: 'Leave blank to use Fish Audio default voice',
    hint: 'Optional. Your Fish Audio voice reference ID. Find it in your Fish Audio dashboard under My Voices.',
  },
};

// Category-level field label override for Step 3
const CATEGORY_MODEL_LABEL: Record<string, string> = {
  tts: 'Voice',
};

type SchemaField = {
  name: string; type: string; label: string; required: boolean;
  hint?: string; placeholder?: string; options?: string[];
};

function CategoryMultiSelect({ allCats, selKind, selectedCats, setSelectedCats, pinnedCategory, loading }: {
  allCats: any[]; selKind: string | null;
  selectedCats: Set<string>; setSelectedCats: (s: Set<string>) => void;
  pinnedCategory: string; loading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const cats = allCats.filter((c: any) => c.kind === selKind);
  const filtered = cats.filter((c: any) =>
    !search ||
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.label || '').toLowerCase().includes(search.toLowerCase())
  );
  const selected = Array.from(selectedCats).filter(name => cats.some((c: any) => c.name === name));

  // AE-317: only 1 option → plain text, no dropdown
  if (cats.length <= 1) {
    const onlyCat = cats[0];
    return (
      <div>
        <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Apply to categories</div>
        <div className="min-h-9 px-2.5 py-1.5 rounded-lg border border-border bg-surface-0 flex items-center">
          <span className="text-xs text-content-primary">{onlyCat?.label || pinnedCategory}</span>
        </div>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Apply to categories</div>
      <div
        onClick={() => !loading && setOpen(v => !v)}
        className={cn(
          'min-h-9 px-2.5 py-1.5 rounded-lg border bg-surface-0 cursor-pointer flex flex-wrap gap-1.5 items-center transition-colors',
          open ? 'border-accent ring-2 ring-accent/10' : 'border-border hover:border-accent/50'
        )}
      >
        {loading ? (
          <span className="text-xs text-content-tertiary flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" /> Loading…
          </span>
        ) : selected.length === 0 ? (
          <span className="text-xs text-content-tertiary">Select categories…</span>
        ) : selected.length === 1 ? (
          <span className="text-xs text-content-primary">
            {cats.find((c: any) => c.name === selected[0])?.label || selected[0]}
          </span>
        ) : (
          selected.map(name => {
            const cat = cats.find((c: any) => c.name === name);
            const isPinned = name === pinnedCategory;
            return (
              <span key={name} className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-sm font-medium bg-accent/15 text-accent">
                {cat?.label || name}
                {!isPinned && (
                  <button
                    type="button"
                    onClick={e => {
                      e.stopPropagation();
                      const next = new Set(selectedCats);
                      next.delete(name);
                      setSelectedCats(next);
                    }}
                    className="hover:text-status-error ml-0.5"
                  >
                    <X size={9} />
                  </button>
                )}
              </span>
            );
          })
        )}
        <ChevronDown size={12} className={cn('ml-auto shrink-0 text-content-tertiary transition-transform', open && 'rotate-180')} />
      </div>

      {open && !loading && (
        <div className="absolute z-20 mt-1 w-full rounded-lg border border-border bg-surface-0 shadow-elevated">
          <div className="px-2.5 pt-2 pb-1.5 border-b border-border">
            <input
              autoFocus
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Filter categories…"
              onClick={e => e.stopPropagation()}
              className="w-full h-7 px-2 text-xs rounded-md border border-border bg-surface-1 text-content-primary placeholder:text-content-tertiary focus:outline-none focus:border-accent"
            />
          </div>
          <div className="max-h-44 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-xs text-content-tertiary">No categories found</div>
            ) : (
              filtered.map((c: any) => {
                const isPinned = c.name === pinnedCategory;
                const isChecked = selectedCats.has(c.name);
                return (
                  <label key={c.name} className={cn(
                    'flex items-center gap-2.5 px-3 py-1.5 text-xs cursor-pointer hover:bg-surface-1 transition-colors select-none',
                    isPinned && 'opacity-60 cursor-default'
                  )}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isPinned}
                      onChange={e => {
                        const next = new Set(selectedCats);
                        if (e.target.checked) next.add(c.name); else next.delete(c.name);
                        next.add(pinnedCategory);
                        setSelectedCats(next);
                      }}
                    />
                    <span className="flex-1 min-w-0">
                      <span className="font-medium text-content-primary">{c.label || c.name}</span>
                      <span className="text-content-tertiary font-mono ml-1.5 text-[10px]">{c.name}</span>
                    </span>
                    {isPinned && <span className="text-[10px] text-accent font-medium">current</span>}
                  </label>
                );
              })
            )}
          </div>
          <div className="px-3 py-1.5 border-t border-border text-[10px] text-content-tertiary">
            {selectedCats.size} selected · Same credentials saved for all
          </div>
        </div>
      )}
    </div>
  );
}

function AddCredentialDialog({ category, initialProvider, onClose, onAdded }: {
  category: string; initialProvider?: string;
  onClose: () => void; onAdded: (id?: number) => void;
}) {
  const { showToast } = useToast();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [providerName, setProviderName] = useState(initialProvider ?? '');
  const [label, setLabel] = useState('');
  const [fieldValues, setFieldValues] = useState<Record<string, string | boolean>>({});
  const [model, setModel] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [registered, setRegistered] = useState<(ReturnType<typeof providersApi.registeredProviders> extends Promise<{ data: (infer T)[] }> ? T : any)[]>([]);
  const [registeredLoading, setRegisteredLoading] = useState(true);
  const [lazyModels, setLazyModels] = useState<string[] | null>(null);
  const [lazyModelsLoading, setLazyModelsLoading] = useState(false);
  // Multi-category: always-visible combobox (no toggle)
  const [allCats, setAllCats] = useState<any[]>([]);
  const [catsLoading, setCatsLoading] = useState(false);
  const [selKind, setSelKind] = useState<string | null>(null);
  const [selectedCats, setSelectedCats] = useState<Set<string>>(() => new Set([category]));
  const [perCatModel, setPerCatModel] = useState<Record<string, string>>({});
  // Validation
  const [step1Attempted, setStep1Attempted] = useState(false);
  const [touchedLabel, setTouchedLabel] = useState(false);
  const [touched2, setTouched2] = useState<Record<string, boolean>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setRegisteredLoading(true);
    // Source providers from BOTH the live Python registry (built-ins, with
    // live model lists) and the marketplace catalog for this section (which
    // also includes user-added custom providers). Merge by key; registry wins
    // when both exist so live supported_models are preserved.
    Promise.all([
      providersApi.registeredProviders(category).then(r => r.data || []).catch(() => []),
      providersApi.catalogForCategory(category).then(r => r.data || []).catch(() => []),
    ])
      .then(([reg, catalog]) => {
        const byKey = new Map<string, any>();
        for (const c of catalog) {
          byKey.set(c.provider_key, {
            provider_name: c.provider_key,
            display_name: c.display_name,
            logo_url: c.logo_url ?? null,
            has_free_tier: c.has_free_tier ?? null,
            default_model: asArray<string>(c.supported_models)[0] ?? null,
            supported_models: asArray<string>(c.supported_models),
            config_schema: asArray<SchemaField>(c.config_schema),
            docs_url: c.docs_url ?? null,
            pricing_tier: c.pricing_tier ?? null,
            is_callable: c.is_callable ?? true,
          });
        }
        for (const r of reg) {
          // Only enrich catalog entries with live registry data (models, callable).
          // Registry-only providers not in the catalog are excluded (strict catalog filter).
          if (byKey.has(r.provider_name)) {
            byKey.set(r.provider_name, { ...byKey.get(r.provider_name), ...r, is_callable: true });
          }
        }
        const merged = Array.from(byKey.values())
          .filter((p: any) => !PROVIDER_ALIASES_TO_HIDE.has(p.provider_name));
        setRegistered(merged);
      })
      .catch(() => setRegistered([]))
      .finally(() => setRegisteredLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  // Load categories to enable multi-select targeting in this section
  useEffect(() => {
    setCatsLoading(true);
    providersApi.categories()
      .then(r => {
        const list = r.data || [];
        setAllCats(list);
        const curr = list.find((c: any) => c.name === category);
        setSelKind(curr?.kind || null);
      })
      .catch(() => { setAllCats([]); setSelKind(null); })
      .finally(() => setCatsLoading(false));
  }, [category]);

  const selProvider = (registered as any[]).find((r: any) => r.provider_name === providerName) ?? null;
  // config_schema / supported_models come from a JSONB column; guard against
  // the backend ever handing back a non-array so the dialog can't crash the page.
  const schema: SchemaField[] = asArray<SchemaField>(selProvider?.config_schema);
  const credFields = schema.filter(f => f.name !== 'model' && f.name !== 'model_id');
  // Use lazy-fetched live model list (GET /models) when available; fall back to
  // registered catalog's supported_models for providers that have no live endpoint.
  const effectiveModels: string[] = lazyModels !== null ? lazyModels : asArray<string>(selProvider?.supported_models);
  const modelField = schema.find(f => f.name === 'model' || f.name === 'model_id') ?? null;
  const noKeyNeeded = NO_KEY_PROVIDERS.has(providerName);
  const hasCredFields = credFields.length > 0;
  const voiceHint = VOICE_HINTS[providerName] || null;
  const modelLabel = voiceHint?.fieldLabel || CATEGORY_MODEL_LABEL[category] || 'Model';
  const supportedModels: string[] = asArray<string>(selProvider?.supported_models);
  const defaultModel: string | null = selProvider?.default_model ?? null;
  // Catalog-only providers (user-added with no runtime adapter) can store a key
  // but the pipeline cannot call them yet. Be explicit so the user isn't misled.
  const notCallable = selProvider?.is_callable === false;
  // Derived: multi-category when more than one category is selected
  const isMulti = selectedCats.size > 1;

  // ── Validation ──────────────────────────────────────────────────────────────
  const validateField2 = (field: SchemaField, val: string | boolean): string => {
    if (field.required && !val) return 'This field is required';
    if (typeof val === 'string' && val && field.hint) {
      const prefixMatch = field.hint.match(/^starts with ([^\s·]+)/i);
      if (prefixMatch && !val.startsWith(prefixMatch[1]))
        return `Expected format: starts with ${prefixMatch[1]}`;
    }
    if (typeof val === 'string' && val &&
        (field.name.toLowerCase().includes('url') || field.type === 'url')) {
      try { new URL(val); } catch { return 'Enter a valid URL'; }
    }
    return '';
  };

  const handleNextStep1 = () => {
    setStep1Attempted(true);
    if (!providerName || !label.trim()) return;
    noKeyNeeded && !hasCredFields ? setStep(3) : setStep(2);
  };

  const handleNextStep2 = () => {
    const newErrors: Record<string, string> = {};
    const newTouched: Record<string, boolean> = {};
    for (const field of credFields) {
      newTouched[field.name] = true;
      newErrors[field.name] = validateField2(field, fieldValues[field.name] ?? '');
    }
    setTouched2(newTouched);
    setFieldErrors(newErrors);
    if (credFields.some(f => f.required && !fieldValues[f.name])) return;
    setStep(3);
  };

  const handleBlurField2 = (field: SchemaField) => {
    const val = fieldValues[field.name] ?? '';
    setTouched2(prev => ({ ...prev, [field.name]: true }));
    setFieldErrors(prev => ({ ...prev, [field.name]: validateField2(field, val) }));
  };

  useEffect(() => {
    setFieldValues({});
    setModel('');
    setPerCatModel({});
    setErr(null);
    setTouched2({});
    setFieldErrors({});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerName]);

  useEffect(() => {
    if (!providerName) { setLazyModels(null); return; }
    setLazyModelsLoading(true);
    setLazyModels(null);
    providersApi.supportedModels(category, providerName)
      .then(r => setLazyModels(r.data || []))
      .catch(() => setLazyModels(null))
      .finally(() => setLazyModelsLoading(false));
  }, [category, providerName]);

  const setField = (name: string, val: string | boolean) =>
    setFieldValues(prev => ({ ...prev, [name]: val }));

  const step2Ready = noKeyNeeded || credFields.every(f => !f.required || fieldValues[f.name]);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      // Determine target categories
      const targets = isMulti && selKind
        ? Array.from(selectedCats).filter(n => {
            const c = allCats.find((x: any) => x.name === n);
            return c && c.kind === selKind;
          })
        : [category];

      const createOne = async (catName: string) => {
        const catModel = perCatModel[catName] ?? model;
        // AE-321 Bug B: source keeps the user's label; each other target gets the
        // category's own display name so the source nickname doesn't leak.
        const catInfo = allCats.find((c: any) => c.name === catName);
        const effectiveLabel = catName === category ? label : (catInfo?.label || catName);
        if (schema.length > 0) {
          const wf: Record<string, string | boolean> = { ...fieldValues };
          if (modelField && catModel) wf[modelField.name] = catModel;
          return providersApi.createCredentialFromWizard({
            category: catName,
            provider_key: providerName,
            label: effectiveLabel,
            wizard_fields: wf,
            model: catModel || null,
          });
        } else {
          const secretField = fieldValues['api_key'] as string || '';
          const effectiveSecret = noKeyNeeded ? 'NO_KEY_REQUIRED' : secretField;
          return providersApi.createCredential({
            category: catName,
            provider_name: providerName,
            label: effectiveLabel,
            secret_value: effectiveSecret,
            secret_key: 'api_key',
            model: catModel || null,
            extra_config: {},
          });
        }
      };

      const results = await Promise.all(targets.map(createOne));
      // AE-321 Bug A: addToChain must receive the SOURCE category's credential id,
      // not the last target's — otherwise a foreign-category credential ends up in
      // the source chain, causing duplicate/wrong entries.
      const sourceIdx = targets.indexOf(category);
      const sourceResult = (sourceIdx >= 0 ? results[sourceIdx] : results[0]) as any;
      const newId = sourceResult?.id ?? sourceResult?.data?.id;
      onAdded(newId);
    } catch (e: any) {
      setErr(e?.message || 'Failed to save. Check your credentials and try again.');
    } finally {
      setBusy(false);
    }
  };

  const stepLabels = [
    'Choose provider',
    noKeyNeeded ? 'No key needed ✔' : 'Enter credentials',
    `${modelLabel} & save`,
  ] as const;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="rounded-xl bg-surface-0 max-w-lg w-full border border-border shadow-elevated max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border shrink-0">
          <div>
            <h3 className="font-semibold text-content-primary">Add credential</h3>
            <p className="text-[11px] text-content-tertiary mt-0.5">
              Category: <span className="font-mono text-content-secondary">{category}</span>
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close" className="w-7 h-7 text-content-tertiary">
            <X size={14} />
          </Button>
        </div>

        {/* ── Step indicator ── */}
        <div className="flex items-center px-5 py-3 border-b border-border shrink-0">
          {stepLabels.map((s, i) => {
            const n = (i + 1) as 1 | 2 | 3;
            const active = step === n;
            const done = step > n;
            return (
              <div key={i} className="flex items-center flex-1">
                <div className="flex items-center gap-1.5 shrink-0">
                  <div className={cn(
                    'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold',
                    done ? 'bg-status-success text-white' :
                    active ? 'bg-accent text-white' : 'bg-surface-2 text-content-tertiary',
                  )}>
                    {done ? '✓' : n}
                  </div>
                  <span className={cn('text-[11px] font-medium hidden sm:block',
                    active ? 'text-content-primary' : 'text-content-tertiary')}>{s}</span>
                </div>
                {i < 2 && <div className={cn('h-px flex-1 mx-2', step > n ? 'bg-status-success' : 'bg-surface-2')} />}
              </div>
            );
          })}
        </div>

        {/* ── Step body ── */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">

          {/* Step 1 — Choose provider + nickname + (optional) multi-category */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Which service do you want to connect?</div>
                {registeredLoading ? (
                  <div className="px-3 py-2 rounded-lg bg-surface-1 border border-border text-xs text-content-tertiary flex items-center gap-2">
                    <Loader2 size={12} className="animate-spin" /> Loading available providers…
                  </div>
                ) : registered.length === 0 ? (
                  <div className="rounded-lg border border-status-warning/40 bg-status-warning/5 px-3 py-2.5 text-xs text-status-warning">
                    No providers are installed for the <strong>{category}</strong> category.
                    Check <span className="font-mono">src/providers/boot.py</span>.
                  </div>
                ) : (
                  <Select value={providerName} onValueChange={v => { setProviderName(v); setStep1Attempted(false); }}>
                    <SelectTrigger className={step1Attempted && !providerName ? 'border-status-error ring-1 ring-status-error/30' : ''}>
                      <SelectValue placeholder="Select a provider…" />
                    </SelectTrigger>
                    <SelectContent>
                      {(registered as any[]).map((r: any) => (
                        <SelectItem key={r.provider_name} value={r.provider_name}>
                          {r.display_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {step1Attempted && !providerName && !registeredLoading && registered.length > 0 && (
                  <p className="text-[11px] text-status-error mt-1">Please select a provider</p>
                )}
                {selProvider && (
                  <div className="mt-1.5 flex items-center gap-3 flex-wrap">
                    {selProvider.docs_url && (
                      <a href={selProvider.docs_url} target="_blank" rel="noreferrer"
                        className="text-[11px] text-accent hover:underline inline-flex items-center gap-1">
                        <ExternalLink size={10} /> Docs ↗
                      </a>
                    )}
                    {selProvider.website_url && (
                      <a href={selProvider.website_url} target="_blank" rel="noreferrer"
                        className="text-[11px] text-accent hover:underline inline-flex items-center gap-1">
                        Get API key ↗
                      </a>
                    )}
                    {selProvider.pricing_tier && (
                      <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium',
                        selProvider.pricing_tier === 'free' ? 'bg-status-success/10 text-status-success' :
                        selProvider.pricing_tier === 'paid' ? 'bg-status-warning/10 text-status-warning' :
                        'bg-surface-2 text-content-tertiary')}>
                        {selProvider.pricing_tier}
                      </span>
                    )}
                  </div>
                )}
                {notCallable && (
                  <div className="mt-2 rounded-lg border border-status-warning/40 bg-status-warning/5 px-3 py-2.5 text-[11px] text-content-secondary flex items-start gap-2">
                    <AlertTriangle size={13} className="text-status-warning shrink-0 mt-0.5" />
                    <span>
                      <strong className="text-status-warning">Catalog only.</strong> You can save a key for
                      this provider now, but the pipeline can&apos;t call it until an adapter is added in
                      code. It won&apos;t run in production yet.
                    </span>
                  </div>
                )}
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">
                  Give it a nickname <span className="text-status-error">*</span>
                </div>
                <Input
                  type="text"
                  value={label}
                  onChange={e => setLabel(e.target.value)}
                  onBlur={() => setTouchedLabel(true)}
                  placeholder={selProvider ? `${selProvider.display_name} — Primary` : 'e.g. My OpenAI Key'}
                  className={(touchedLabel || step1Attempted) && !label.trim() ? 'border-status-error ring-1 ring-status-error/30' : ''}
                />
                {(touchedLabel || step1Attempted) && !label.trim() && (
                  <p className="text-[11px] text-status-error mt-1">A nickname is required</p>
                )}
                <p className="text-[11px] text-content-tertiary mt-1.5">
                  A friendly name to tell your credentials apart. Only you see this.
                </p>
              </div>

              {/* Multi-category: always-visible combobox */}
              <CategoryMultiSelect
                allCats={allCats}
                selKind={selKind}
                selectedCats={selectedCats}
                setSelectedCats={setSelectedCats}
                pinnedCategory={category}
                loading={catsLoading}
              />

              <div className="flex justify-end gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancel</Button>
                <Button type="button" size="sm" onClick={handleNextStep1}
                  disabled={!providerName || !label.trim()}>
                  {noKeyNeeded && !hasCredFields ? 'Skip to model →' : 'Next: Credentials →'}
                </Button>
              </div>
            </div>
          )}

          {/* Step 2 — Schema-driven credential fields */}
          {step === 2 && (
            <div className="space-y-4">
              {selProvider?.docs_url && (
                <div className="rounded-lg border border-accent/20 bg-accent/5 px-3 py-2.5">
                  <a href={selProvider.docs_url} target="_blank" rel="noreferrer"
                    className="text-[11px] text-accent hover:underline flex items-center gap-1">
                    <ExternalLink size={10} /> How to get your {selProvider.display_name} credentials ↗
                  </a>
                </div>
              )}

              {credFields.length === 0 && !noKeyNeeded && (
                <div className="rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-xs text-content-tertiary">
                  No credential fields configured for this provider — using defaults.
                </div>
              )}

              {credFields.map(field => (
                <SchemaFieldInput
                  key={field.name}
                  field={field}
                  value={fieldValues[field.name] ?? ''}
                  onChange={val => { setField(field.name, val); if (touched2[field.name]) setFieldErrors(prev => ({ ...prev, [field.name]: validateField2(field, val) })); }}
                  onBlur={() => handleBlurField2(field)}
                  error={touched2[field.name] ? fieldErrors[field.name] : undefined}
                />
              ))}

              {noKeyNeeded && credFields.length === 0 && (
                <div className="rounded-lg border border-status-success/30 bg-status-success/5 px-3 py-2.5 text-xs text-status-success flex items-center gap-2">
                  <Check size={12} /> No API key required for {selProvider?.display_name ?? providerName}.
                </div>
              )}

              <p className="text-[11px] text-content-tertiary">
                Password fields are stored securely in Vault — <strong>never</strong> in the database or logs.
              </p>

              <div className="flex justify-between gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={() => setStep(1)}>← Back</Button>
                <Button type="button" size="sm" onClick={handleNextStep2} disabled={!step2Ready}>
                  Next: Model & save →
                </Button>
              </div>
            </div>
          )}

          {/* Step 3 — Model/voice + per-category overrides + final save */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">{modelLabel} (optional)</div>

                {voiceHint?.suggestions ? (
                  <div className="space-y-2">
                    <p className="text-[12px] text-content-secondary">{voiceHint.hint}</p>
                    <div className="grid gap-1.5">
                      {voiceHint.suggestions.map(s => {
                        const val = s.split(' — ')[0];
                        return (
                          <Button key={val} type="button" variant="ghost"
                            onClick={() => setModel(val)}
                            className={cn('text-left justify-start px-3 py-2 rounded-lg border text-sm h-auto',
                              model === val
                                ? 'border-accent bg-accent/8 text-content-primary hover:bg-accent/15'
                                : 'border-border hover:border-accent/40 hover:bg-surface-1 text-content-secondary')}>
                            <span className="font-mono text-xs text-content-tertiary mr-2">{val}</span>
                            <span className="text-[11px]">{s.split(' — ')[1] || ''}</span>
                          </Button>
                        );
                      })}
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => setModel('')}
                      className="h-auto px-0 py-0 text-[11px] text-content-tertiary hover:text-accent">
                      {model ? 'Clear selection (use default)' : '✔ Using default voice (Aria)'}
                    </Button>
                  </div>
                ) : voiceHint ? (
                  <div className="space-y-2">
                    <div className="rounded-lg border border-border bg-surface-1/60 px-3 py-2.5">
                      <p className="text-[12px] text-content-secondary">{voiceHint.hint}</p>
                    </div>
                    <Input type="text" value={model} onChange={e => setModel(e.target.value)}
                      placeholder={voiceHint.placeholder} />
                  </div>
                ) : modelField?.options?.length ? (
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger>
                      <SelectValue placeholder={`Use provider default${defaultModel ? ` (${defaultModel})` : ''}`} />
                    </SelectTrigger>
                    <SelectContent>
                      {modelField.options.map((m: string) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : lazyModelsLoading ? (
                  <div className="px-3 py-2 rounded-lg bg-surface-1 border border-border text-xs text-content-tertiary flex items-center gap-2">
                    <Loader2 size={11} className="animate-spin" /> Loading models…
                  </div>
                ) : effectiveModels.length > 0 ? (
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger>
                      <SelectValue placeholder={`Use provider default${defaultModel ? ` (${defaultModel})` : ''}`} />
                    </SelectTrigger>
                    <SelectContent>
                      {effectiveModels.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : (
                  <div className="space-y-2">
                    <Input type="text" value={model} onChange={e => setModel(e.target.value)}
                      placeholder={defaultModel || "Leave blank for provider default"} />
                    <p className="text-[11px] text-content-tertiary">
                      Optional. One credential = one model. Add a second credential later for a different model.
                    </p>
                  </div>
                )}
              </div>

              {/* Per-category model overrides when multiple categories are selected */}
              {isMulti && (
                <div className="space-y-2">
                  <div className="text-[10px] uppercase tracking-wide text-content-tertiary">Per-category {modelLabel.toLowerCase()} (override)</div>
                  {Array.from(selectedCats)
                    .filter(n => allCats.find((c: any) => c.name === n && c.kind === selKind))
                    .map(catName => {
                      const cat = allCats.find((c: any) => c.name === catName)!;
                      const val = perCatModel[catName] ?? '';
                      return (
                        <div key={catName} className="flex items-center gap-2">
                          <span className="min-w-[140px] text-[12px] text-content-secondary truncate">{cat.label}</span>
                          {voiceHint?.suggestions ? (
                            <Input type="text" value={val} onChange={e => setPerCatModel(prev => ({ ...prev, [catName]: e.target.value }))}
                              placeholder={voiceHint.placeholder || 'Use default'} className="flex-1" />
                          ) : (effectiveModels.length > 0 ? (
                            <Select value={val} onValueChange={(v: string) => setPerCatModel(prev => ({ ...prev, [catName]: v }))}>
                              <SelectTrigger className="flex-1">
                                <SelectValue placeholder={`Use provider default${defaultModel ? ` (${defaultModel})` : ''}`} />
                              </SelectTrigger>
                              <SelectContent>
                                {effectiveModels.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          ) : (
                            <Input type="text" value={val} onChange={e => setPerCatModel(prev => ({ ...prev, [catName]: e.target.value }))}
                              placeholder={defaultModel || 'Use default'} className="flex-1" />
                          ))}
                        </div>
                      );
                    })}
                  <p className="text-[10px] text-content-tertiary">If left blank, each category uses the selection above or the provider default.</p>
                </div>
              )}

              {err && (
                <div className="rounded-lg border border-status-error/40 bg-status-error/5 px-3 py-2.5 text-sm text-status-error">
                  {err}
                </div>
              )}

              <div className="flex justify-between gap-2 pt-1">
                <Button type="button" variant="outline" size="sm"
                  onClick={() => noKeyNeeded && !hasCredFields ? setStep(1) : setStep(2)}>
                  ← Back
                </Button>
                <Button type="button" size="sm" onClick={submit} disabled={busy} loading={busy}
                  leftIcon={!busy ? <Check size={13} /> : undefined}>
                  {busy ? 'Saving…' : 'Save & activate'}
                </Button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function SchemaFieldInput({ field, value, onChange, onBlur, error }: {
  field: SchemaField;
  value: string | boolean;
  onChange: (v: string | boolean) => void;
  onBlur?: () => void;
  error?: string;
}) {
  const [show, setShow] = useState(false);
  const hasError = !!error;
  const errorCls = hasError ? 'border-status-error ring-1 ring-status-error/30' : '';
  if (field.type === 'boolean') {
    return (
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-content-tertiary">{field.label}</div>
          {field.hint && <div className="text-[11px] text-content-tertiary mt-0.5">{field.hint}</div>}
        </div>
        <UISwitch checked={!!value} onCheckedChange={onChange} />
      </div>
    );
  }
  if (field.type === 'select' && field.options?.length) {
    return (
      <div>
        <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">
          {field.label}{field.required && <span className="text-status-error ml-0.5">*</span>}
        </div>
        <Select value={String(value || '')} onValueChange={v => { onChange(v); onBlur?.(); }}>
          <SelectTrigger className={errorCls}><SelectValue placeholder={field.placeholder || 'Select…'} /></SelectTrigger>
          <SelectContent>
            {!field.required && <SelectItem value="">None (use provider default)</SelectItem>}
            {field.options.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
          </SelectContent>
        </Select>
        {hasError
          ? <p className="text-[11px] text-status-error mt-1">{error}</p>
          : field.hint && <div className="text-[11px] text-content-tertiary mt-1">{field.hint}</div>}
      </div>
    );
  }
  if (field.type === 'password') {
    return (
      <div>
        <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">
          {field.label}{field.required && <span className="text-status-error ml-0.5">*</span>}
        </div>
        <div className="flex items-center gap-2">
          <Input type={show ? 'text' : 'password'} value={String(value || '')}
            onChange={e => onChange(e.target.value)}
            onBlur={onBlur}
            placeholder={field.placeholder || 'Paste here…'}
            className={cn('flex-1 font-mono', errorCls)} />
          <Button type="button" variant="outline" size="icon" onClick={() => setShow(v => !v)}
            aria-label={show ? 'Hide' : 'Show'} className="shrink-0 w-9 h-9">
            {show ? <EyeOff size={14} /> : <Eye size={14} />}
          </Button>
        </div>
        {hasError
          ? <p className="text-[11px] text-status-error mt-1">{error}</p>
          : field.hint && <div className="text-[11px] text-content-tertiary mt-1">{field.hint}</div>}
      </div>
    );
  }
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">
        {field.label}{field.required && <span className="text-status-error ml-0.5">*</span>}
      </div>
      <Input type="text" value={String(value || '')} onChange={e => onChange(e.target.value)}
        onBlur={onBlur} placeholder={field.placeholder || ''} className={errorCls} />
      {hasError
        ? <p className="text-[11px] text-status-error mt-1">{error}</p>
        : field.hint && <div className="text-[11px] text-content-tertiary mt-1">{field.hint}</div>}
    </div>
  );
}

function RotateCredentialDialog({ cred, onClose, onRotated }: { cred: any; onClose: () => void; onRotated: () => void }) {
  const { showToast } = useToast();
  const [newKey, setNewKey] = useState('');
  const [hint, setHint] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [rolledBack, setRolledBack] = useState(false);

  const submit = async () => {
    if (!newKey.trim()) return;
    setBusy(true); setErr(null); setRolledBack(false);
    try {
      await providersApi.rotateCredential(cred.id, newKey.trim(), 'api_key', hint.trim() || undefined);
      onRotated();
    } catch (e: any) {
      const msg = e?.message || 'Rotation failed';
      const isRollback = msg.toLowerCase().includes('rolled_back') || msg.toLowerCase().includes('rollback') || msg.toLowerCase().includes('422');
      setRolledBack(isRollback);
      setErr(msg);
      showToast(isRollback ? '❌ Rotation failed — old key restored automatically' : msg, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="rounded-xl bg-surface-0 max-w-md w-full border border-border shadow-elevated" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border">
          <div>
            <h3 className="font-semibold text-content-primary flex items-center gap-2">
              <RotateCw size={14} className="text-accent" /> Rotate API Key
            </h3>
            <p className="text-[11px] text-content-tertiary mt-0.5">{cred.label} · {cred.provider_name}</p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} className="w-7 h-7 text-content-tertiary">
            <X size={14} />
          </Button>
        </div>
        <div className="p-5 space-y-4">
          <div className="rounded-lg border border-accent/20 bg-accent/5 px-3 py-2.5 text-[12px] text-content-secondary">
            The old key is kept and automatically restored if the new key fails its health check.
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">New API Key<span className="text-status-error ml-0.5">*</span></div>
            <div className="flex items-center gap-2">
              <Input type={show ? 'text' : 'password'} value={newKey} onChange={e => setNewKey(e.target.value)}
                placeholder="Paste new key here…" className="flex-1 font-mono" />
              <Button type="button" variant="outline" size="icon" onClick={() => setShow(v => !v)}
                aria-label={show ? 'Hide' : 'Show'} className="shrink-0 w-9 h-9">
                {show ? <EyeOff size={14} /> : <Eye size={14} />}
              </Button>
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Hint (optional)</div>
            <Input type="text" value={hint} onChange={e => setHint(e.target.value)}
              placeholder="e.g. quarterly rotation" />
            <p className="text-[11px] text-content-tertiary mt-1">Stored in audit log to explain why this key was rotated.</p>
          </div>

          {err && (
            <div className={cn('rounded-lg border px-3 py-2.5 text-sm',
              rolledBack
                ? 'border-status-error/40 bg-status-error/5 text-status-error'
                : 'border-status-error/40 bg-status-error/5 text-status-error')}>
              {rolledBack && (
                <div className="font-semibold mb-1 flex items-center gap-1.5">
                  <AlertTriangle size={12} /> Old key restored automatically
                </div>
              )}
              {err}
            </div>
          )}

          <div className="flex justify-between gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="button" size="sm" onClick={submit} disabled={busy || !newKey.trim()}
              loading={busy}
              leftIcon={!busy ? <RotateCw size={12} /> : undefined}>
              {busy ? 'Testing new key…' : 'Test & Rotate →'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Inp({ label, hint, value, onChange, placeholder, type = 'text' }: any) {
  return (
    <div className="block">
      <Label className="text-[10px] uppercase text-content-tertiary mb-1 block">{label}</Label>
      <Input
        type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      />
      {hint && <div className="text-[10px] text-content-tertiary mt-1">{hint}</div>}
    </div>
  );
}

function HealthSparkline({ data }: { data: Array<{ ok: boolean; latency_ms: number | null; checked_at: string }> }) {
  const W = 80, H = 16, pad = 1;
  const sorted = [...data].reverse(); // oldest first
  const n = sorted.length;
  if (n === 0) return null;
  const latencies = sorted.map(d => d.latency_ms ?? 0).filter(v => v > 0);
  const maxL = latencies.length > 0 ? Math.max(...latencies) : 1;
  const xStep = (W - pad * 2) / Math.max(n - 1, 1);
  const points = sorted.map((d, i) => {
    const x = pad + i * xStep;
    const y = d.latency_ms && maxL > 0
      ? H - pad - ((d.latency_ms / maxL) * (H - pad * 2))
      : H / 2;
    return { x, y, ok: d.ok };
  });
  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  return (
    <div className="flex items-center gap-2">
      <svg width={W} height={H} className="shrink-0" viewBox={`0 0 ${W} ${H}`}>
        <path d={pathD} fill="none" stroke="currentColor"
          className="text-surface-3" strokeWidth="1" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x.toFixed(1)} cy={p.y.toFixed(1)} r="1.5"
            className={p.ok ? 'text-status-success' : 'text-status-error'}
            fill="currentColor" />
        ))}
      </svg>
      <span className="text-[9px] text-content-tertiary">{n} checks</span>
    </div>
  );
}

// AE-73 — sortable chain item with drag handle + keyboard arrow fallback
function SortableChainItem({
  entry, index, total,
  toggleChainEntryEnabled, moveChain, removeFromChain, inherited,
}: {
  entry: any;
  index: number;
  total: number;
  toggleChainEntryEnabled: (e: any) => void;
  moveChain: (i: number, dir: -1 | 1) => void;
  removeFromChain: (credId: number) => void;
  inherited: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: entry.credential_id, disabled: inherited });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : undefined,
  };
  const health = getHealth(entry);
  const entryEnabled = entry.is_enabled ?? true;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center gap-3 px-4 py-3 bg-surface-0',
        !entryEnabled && 'opacity-60',
        isDragging && 'shadow-lg bg-surface-1',
        inherited && 'bg-surface-1/50',
      )}>
      {/* Drag handle / inherited lock */}
      {inherited ? (
        <span className="text-content-tertiary shrink-0 cursor-not-allowed" title="Inherited from workspace">
          🔒
        </span>
      ) : (
        <button
          {...attributes}
          {...listeners}
          type="button"
          aria-label="Drag to reorder"
          className="cursor-grab active:cursor-grabbing text-content-tertiary hover:text-content-secondary shrink-0 touch-none">
          <GripVertical size={15} />
        </button>
      )}
      <span className="text-xs font-mono text-content-tertiary w-5 shrink-0">{index + 1}.</span>
      <div className="flex items-center gap-1.5">
        {HEALTH_ICON[health]}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn('text-sm font-medium text-content-primary', !entryEnabled && 'line-through')}>
            {entry.label}
          </span>
          {inherited && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary font-medium">
              ↳ from workspace
            </span>
          )}
          {!entryEnabled && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">disabled</span>
          )}
          {entry.chain_category_kind && entry.credential_kind &&
            entry.chain_category_kind !== entry.credential_kind && (
            <span
              title={`Kind mismatch: credential is ${entry.credential_kind}, chain expects ${entry.chain_category_kind}`}
              className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-amber-500/15 text-amber-600 border border-amber-500/30 font-medium"
            >
              <AlertTriangle size={10} />
              <span>wrong kind</span>
            </span>
          )}
        </div>
        <div className="text-[11px] text-content-tertiary">{entry.provider_name}</div>
      </div>
      {!inherited && (
        <div className="flex items-center gap-1.5 shrink-0">
          <Switch
            checked={entryEnabled}
            onChange={() => toggleChainEntryEnabled(entry)}
            title={entryEnabled ? 'Disable in this chain' : 'Enable in this chain'}
          />
          <Button type="button" variant="ghost" size="icon-sm"
            onClick={() => moveChain(index, -1)} disabled={index === 0}
            aria-label="Move up" className="w-7 h-7 text-content-tertiary">
            <ArrowUp size={13} />
          </Button>
          <Button type="button" variant="ghost" size="icon-sm"
            onClick={() => moveChain(index, 1)} disabled={index === total - 1}
            aria-label="Move down" className="w-7 h-7 text-content-tertiary">
            <ArrowDown size={13} />
          </Button>
          <Button type="button" variant="ghost" size="icon-sm"
            onClick={() => removeFromChain(entry.credential_id)}
            aria-label="Remove from chain"
            className="w-7 h-7 text-content-tertiary hover:text-status-error hover:bg-status-error/10">
            <X size={13} />
          </Button>
        </div>
      )}
    </div>
  );
}
