'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { providersApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { confirmDialog } from '@/lib/components/ConfirmDialog';
import {
  Plus, Activity, Trash2, ArrowUp, ArrowDown, X, Check, ChevronLeft,
  ShieldCheck, AlertTriangle, HelpCircle, Loader2, Eye, EyeOff, RotateCw,
  Terminal, SlidersHorizontal, Play, Star,
} from '@/lib/components/Icon';
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

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.credentials(decoded).then(r => setCreds(r.data || [])),
      providersApi.chainsV2({ scope: 'workspace', content_mode: selectedMode || undefined, category: decoded })
        .then(r => setChain(r.data || []))
        .catch(() => setChain([])),
      providersApi.resolved({ category: decoded, content_mode: selectedMode || undefined })
        .then(r => setResolvedChain(r.data || []))
        .catch(() => setResolvedChain([])),
      providersApi.routes('workspace').then(r => {
        const found = (r.data || []).find((rt: any) => rt.category === decoded);
        if (found) {
          setRoute(found);
          setSelectedPolicy(found.policy || 'balanced');
          setPrimaryCredId(found.primary_credential_id || null);
        }
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [decoded, selectedMode]);

  // Load the content-mode catalog once.
  useEffect(() => {
    providersApi.contentModes()
      .then(r => setContentModes(r.data || []))
      .catch(() => setContentModes([]));
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

  const saveChain = (ids: number[]) =>
    providersApi.upsertChainV2({
      scope: 'workspace',
      scope_id: null,
      content_mode: selectedMode,
      category: decoded,
      credential_ids: ids,
    }).then(refresh);

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
    try {
      await providersApi.setCredentialEnabled(cred.id, next);
      showToast(next ? `${cred.label} enabled` : `${cred.label} disabled`, 'success');
      refresh();
    } catch (e: any) {
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
    try {
      await providersApi.deleteCredential(id);
      showToast('Credential deleted', 'success');
      refresh();
    } catch (e: any) { showToast(e?.message || 'Delete failed', 'error'); }
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
      {/* Breadcrumb + header */}
      <div className="flex items-center gap-2 text-xs text-content-tertiary mb-4">
        <Link href="/dashboard/providers" className="hover:text-content-primary transition-colors flex items-center gap-1">
          <ChevronLeft size={13} /> Providers
        </Link>
        <span>/</span>
        <span className="text-content-primary font-medium">{decoded}</span>
      </div>

      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-xl font-semibold text-content-primary">{decoded}</h1>
        <div className="ml-auto flex items-center gap-2">
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
            <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
              {chain.length === 0 ? (
                <div className="p-5 text-sm text-content-tertiary text-center">
                  No chain configured yet. Use "Add to chain" on a credential below.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {chain.map((c: any, i: number) => {
                    const health = getHealth(c);
                    const entryEnabled = c.is_enabled ?? true;
                    return (
                      <div key={c.id ?? c.credential_id} className={cn(
                        'flex items-center gap-3 px-4 py-3',
                        !entryEnabled && 'opacity-60'
                      )}>
                        <span className="text-xs font-mono text-content-tertiary w-5 shrink-0">{i + 1}.</span>
                        <div className="flex items-center gap-1.5">
                          {HEALTH_ICON[health]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className={cn(
                            'text-sm font-medium text-content-primary',
                            !entryEnabled && 'line-through'
                          )}>{c.label}</div>
                          <div className="text-[11px] text-content-tertiary">{c.provider_name}</div>
                        </div>
                        {!entryEnabled && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">
                            disabled
                          </span>
                        )}
                        <div className="flex items-center gap-2 shrink-0">
                          <Switch
                            checked={entryEnabled}
                            onChange={() => toggleChainEntryEnabled(c)}
                            title={entryEnabled ? 'Disable in this chain' : 'Enable in this chain'}
                          />
                          <Button type="button" variant="ghost" size="icon-sm" onClick={() => moveChain(i, -1)} disabled={i === 0} aria-label="Move up" className="w-7 h-7 text-content-tertiary">
                            <ArrowUp size={13} />
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" onClick={() => moveChain(i, 1)} disabled={i === chain.length - 1} aria-label="Move down" className="w-7 h-7 text-content-tertiary">
                            <ArrowDown size={13} />
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" onClick={() => removeFromChain(c.credential_id)} aria-label="Remove from chain" className="w-7 h-7 text-content-tertiary hover:text-status-error hover:bg-status-error/10">
                            <X size={13} />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
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
                      <div key={c.id} className={cn('px-4 py-3', !c.enabled && 'opacity-60')}>
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
          onClose={() => setShowAdd(false)}
          onAdded={(newCredId?: number) => {
            setShowAdd(false);
            if (newCredId) addToChain(newCredId); // auto-activate immediately
            else refresh();
            showToast('Credential saved and added to chain ✓', 'success');
          }}
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

function AddCredentialDialog({ category, onClose, onAdded }: any) {
  const { showToast } = useToast();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [providerName, setProviderName] = useState('');
  const [label, setLabel] = useState('');
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [model, setModel] = useState('');
  const [supportedModels, setSupportedModels] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [providerRegistered, setProviderRegistered] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [registered, setRegistered] = useState<{
    provider_name: string;
    display_name: string;
    logo_url: string | null;
    website_url: string | null;
    has_free_tier: boolean | null;
    default_model: string | null;
    supported_models: string[];
  }[]>([]);
  const [registeredLoading, setRegisteredLoading] = useState(true);

  useEffect(() => {
    setRegisteredLoading(true);
    providersApi.registeredProviders(category)
      .then(r => {
        // Filter out alias duplicates (fishaudio = same class as fish_audio)
        const deduped = (r.data || []).filter((p: any) => !PROVIDER_ALIASES_TO_HIDE.has(p.provider_name));
        setRegistered(deduped);
        if (deduped.length > 0 && !providerName) {
          const first = deduped[0];
          setProviderName(first.provider_name);
          setSupportedModels(first.supported_models);
          setDefaultModel(first.default_model);
          setProviderRegistered(true);
        }
      })
      .catch(() => setRegistered([]))
      .finally(() => setRegisteredLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  useEffect(() => {
    if (!providerName) {
      setSupportedModels([]); setDefaultModel(null); setProviderRegistered(null);
      return;
    }
    const match = registered.find(r => r.provider_name === providerName);
    if (match) {
      setSupportedModels(match.supported_models);
      setDefaultModel(match.default_model);
      setProviderRegistered(true);
      if (!label) setLabel(match.display_name + ' — Primary');
    } else {
      setProviderRegistered(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerName, registered]);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const effectiveSecret = NO_KEY_PROVIDERS.has(providerName) ? 'NO_KEY_REQUIRED' : secret;
      const result = await providersApi.createCredential({
        category, provider_name: providerName, label,
        secret_value: effectiveSecret, secret_key: 'api_key',
        model: model || null,
        extra_config: {},
      });
      onAdded(result?.id);
    } catch (e: any) { setErr(e?.message || 'Failed to save. Check your API key and try again.'); }
    finally { setBusy(false); }
  };

  const keyHint      = KEY_HINTS[providerName] || null;
  const voiceHint     = VOICE_HINTS[providerName] || null;
  const selProvider   = registered.find(r => r.provider_name === providerName);
  const noKeyNeeded   = NO_KEY_PROVIDERS.has(providerName);
  const modelLabel    = voiceHint?.fieldLabel || CATEGORY_MODEL_LABEL[category] || 'Model';
  const stepLabels    = ['Choose provider', noKeyNeeded ? 'No key needed ✔' : 'Enter API key', `${modelLabel} & save`] as const;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="rounded-xl bg-surface-0 max-w-lg w-full border border-border shadow-elevated" onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border">
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
        <div className="flex items-center px-5 py-3 border-b border-border">
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
        <div className="p-5 space-y-4">

          {/* Step 1 — Choose provider + nickname */}
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
                    The backend didn't load any provider classes. Check <span className="font-mono">src/providers/boot.py</span>.
                  </div>
                ) : (
                  <Select value={providerName} onValueChange={setProviderName}>
                    <SelectTrigger><SelectValue placeholder="Select a provider…" /></SelectTrigger>
                    <SelectContent>
                      {registered.map(r => (
                        <SelectItem key={r.provider_name} value={r.provider_name}>
                          {r.display_name}
                          {r.has_free_tier ? ' — Free tier available' : ''}
                          {NO_KEY_PROVIDERS.has(r.provider_name) ? ' — No API key needed' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {selProvider?.website_url && (
                  <div className="mt-1.5">
                    <a href={selProvider.website_url} target="_blank" rel="noreferrer"
                      className="text-[11px] text-accent hover:underline inline-flex items-center gap-1">
                      Visit {selProvider.display_name} to get your API key ↗
                    </a>
                  </div>
                )}
              </div>

              {/* Nickname — plain text, no datalist */}
              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Give it a nickname</div>
                <Input
                  type="text"
                  value={label}
                  onChange={e => setLabel(e.target.value)}
                  placeholder={selProvider ? `${selProvider.display_name} — Primary` : 'e.g. My OpenAI Key'}
                />
                <p className="text-[11px] text-content-tertiary mt-1.5">
                  Just a friendly name so <em>you</em> can tell your keys apart. Examples: “Main Account”, “Backup”, “High-volume”. Only you see this.
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={onClose}>Cancel</Button>
                <Button type="button" size="sm" onClick={() => noKeyNeeded ? setStep(3) : setStep(2)} disabled={!providerName || !label.trim()}>
                  {noKeyNeeded ? 'Skip to Voice →' : 'Next: Enter API key →'}
                </Button>
              </div>
            </div>
          )}

          {/* Step 2 — Enter API key (skipped for no-key providers) */}
          {step === 2 && (
            <div className="space-y-4">
              {keyHint && (
                <div className="rounded-lg border border-accent/20 bg-accent/5 px-3 py-2.5">
                  <p className="text-[12px] text-content-secondary">{keyHint.hint}</p>
                  <a href={keyHint.helpUrl} target="_blank" rel="noreferrer"
                    className="text-[11px] text-accent hover:underline mt-1 inline-block">
                    → Open {selProvider?.display_name || providerName} dashboard to copy your key
                  </a>
                </div>
              )}

              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">Paste your API key</div>
                <div className="flex items-center gap-2">
                  <Input
                    type={showSecret ? 'text' : 'password'}
                    value={secret}
                    onChange={e => setSecret(e.target.value)}
                    placeholder={keyHint?.prefix ? `Starts with ${keyHint.prefix}` : 'Paste here…'}
                    className="flex-1 font-mono"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setShowSecret(v => !v)}
                    aria-label={showSecret ? 'Hide secret' : 'Show secret'}
                    className="shrink-0 w-9 h-9"
                  >
                    {showSecret ? <EyeOff size={14} /> : <Eye size={14} />}
                  </Button>
                </div>
                <p className="text-[11px] text-content-tertiary mt-1.5">
                  Your key is saved securely in Vault — it is <strong>never</strong> written to the database, logs, or source code.
                </p>
              </div>

              <div className="flex justify-between gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={() => setStep(1)}>← Back</Button>
                <Button type="button" size="sm" onClick={() => setStep(3)} disabled={!secret.trim()}>
                  Next: Pick voice →
                </Button>
              </div>
            </div>
          )}

          {/* Step 3 — Voice/Model & save */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1.5">{modelLabel} (optional)</div>

                {/* Voice suggestions for TTS providers */}
                {voiceHint?.suggestions ? (
                  <div className="space-y-2">
                    <p className="text-[12px] text-content-secondary">{voiceHint.hint}</p>
                    <div className="grid gap-1.5">
                      {voiceHint.suggestions.map(s => {
                        const val = s.split(' — ')[0];
                        return (
                          <Button
                            key={val}
                            type="button"
                            variant="ghost"
                            onClick={() => setModel(val)}
                            className={cn(
                              'text-left justify-start px-3 py-2 rounded-lg border text-sm h-auto',
                              model === val
                                ? 'border-accent bg-accent/8 text-content-primary hover:bg-accent/15'
                                : 'border-border hover:border-accent/40 hover:bg-surface-1 text-content-secondary',
                            )}>
                            <span className="font-mono text-xs text-content-tertiary mr-2">{val}</span>
                            <span className="text-[11px]">{s.split(' — ')[1] || ''}</span>
                          </Button>
                        );
                      })}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setModel('')}
                      className="h-auto px-0 py-0 text-[11px] text-content-tertiary hover:text-accent mt-0.5 self-start"
                    >
                      {model ? 'Clear selection (use default)' : '✔ Using default voice (Aria)'}
                    </Button>
                  </div>
                ) : voiceHint ? (
                  <div className="space-y-2">
                    <div className="rounded-lg border border-border bg-surface-1/60 px-3 py-2.5">
                      <p className="text-[12px] text-content-secondary">{voiceHint.hint}</p>
                    </div>
                    <Input
                      type="text"
                      value={model}
                      onChange={e => setModel(e.target.value)}
                      placeholder={voiceHint.placeholder}
                    />
                  </div>
                ) : supportedModels.length > 0 ? (
                  <Select value={model || '__default__'} onValueChange={(v: string) => setModel(v === '__default__' ? '' : v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">Use provider default ({defaultModel || 'auto'})</SelectItem>
                      {supportedModels.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : (
                  <div className="space-y-2">
                    <Input
                      type="text"
                      value={model}
                      onChange={e => setModel(e.target.value)}
                      placeholder={defaultModel || 'Leave blank to use the provider’s default model'}
                    />
                    <p className="text-[11px] text-content-tertiary">
                      Optional. One credential = one model. Add a second credential later if you want the same API key with a different model.
                    </p>
                  </div>
                )}
              </div>

              {err && (
                <div className="rounded-lg border border-status-error/40 bg-status-error/5 px-3 py-2.5 text-sm text-status-error">
                  {err}
                </div>
              )}

              <div className="flex justify-between gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={() => noKeyNeeded ? setStep(1) : setStep(2)}>← Back</Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={submit}
                  disabled={busy}
                  loading={busy}
                  leftIcon={!busy ? <Check size={13} /> : undefined}
                >
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
