'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { providersApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import {
  Plus, Activity, Trash2, ArrowUp, ArrowDown, X, Check, ChevronLeft,
  ShieldCheck, AlertTriangle, HelpCircle, Loader2, Eye, EyeOff, RotateCw,
  Terminal, SlidersHorizontal, Play, Star,
} from '@/lib/components/Icon';

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
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      title={title}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        'relative inline-flex h-4 w-7 shrink-0 items-center rounded-full border transition-colors',
        checked
          ? 'bg-status-success/80 border-status-success/80'
          : 'bg-surface-2 border-border',
        disabled && 'opacity-40 cursor-not-allowed'
      )}
    >
      <span className={cn(
        'inline-block h-3 w-3 rounded-full bg-white shadow transition-transform',
        checked ? 'translate-x-3.5' : 'translate-x-0.5'
      )} />
    </button>
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
    if (!confirm('Delete this credential? This cannot be undone.')) return;
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
          <button onClick={refresh} disabled={loading}
            className="w-8 h-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
            <Plus size={13} /> Add credential
          </button>
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
                  <button key={m.name ?? '__all__'} onClick={() => setSelectedMode(m.name)}
                    className={cn('px-2.5 py-1 text-[11px] font-medium rounded transition-all',
                      selectedMode === m.name
                        ? 'bg-surface-0 text-content-primary shadow-sm'
                        : 'text-content-tertiary hover:text-content-secondary')}>
                    {m.label}
                  </button>
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
                          <button onClick={() => moveChain(i, -1)} disabled={i === 0}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary disabled:opacity-30 transition-colors">
                            <ArrowUp size={13} />
                          </button>
                          <button onClick={() => moveChain(i, 1)} disabled={i === chain.length - 1}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary disabled:opacity-30 transition-colors">
                            <ArrowDown size={13} />
                          </button>
                          <button onClick={() => removeFromChain(c.credential_id)}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-status-error/10 text-content-tertiary hover:text-status-error transition-colors">
                            <X size={13} />
                          </button>
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
                  <button onClick={() => setShowAdd(true)} className="text-accent hover:underline">Add one →</button>
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
                            <button onClick={() => toggleDefaultFallback(c)}
                              title={c.is_default_fallback ? 'Clear default fallback' : 'Set as default fallback (always tried last)'}
                              className={cn('w-7 h-7 flex items-center justify-center rounded transition-colors',
                                c.is_default_fallback
                                  ? 'bg-status-warning/15 text-status-warning hover:bg-status-warning/25'
                                  : 'border border-border text-content-tertiary hover:bg-surface-2')}>
                              <Star size={12} />
                            </button>
                            <button onClick={() => testCredential(c.id)} disabled={isTesting}
                              className="flex items-center gap-1 px-2.5 py-1 rounded border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors disabled:opacity-50">
                              {isTesting ? <Loader2 size={11} className="animate-spin" /> : <Activity size={11} />}
                              {isTesting ? 'Testing…' : 'Test'}
                            </button>
                            {!inChain ? (
                              <button onClick={() => addToChain(c.id)}
                                className="flex items-center gap-1 px-2.5 py-1 rounded border border-accent/40 text-xs text-accent hover:bg-accent/10 transition-colors">
                                <Plus size={11} /> Add to chain
                              </button>
                            ) : (
                              <button onClick={() => removeFromChain(c.id)}
                                className="flex items-center gap-1 px-2.5 py-1 rounded border border-border text-xs text-content-tertiary hover:text-content-secondary hover:bg-surface-2 transition-colors">
                                <X size={11} /> Remove
                              </button>
                            )}
                            <button onClick={() => deleteCredential(c.id)}
                              className="w-7 h-7 flex items-center justify-center rounded hover:bg-status-error/10 text-content-tertiary hover:text-status-error transition-colors">
                              <Trash2 size={13} />
                            </button>
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
                  <button key={opt.value} onClick={() => setSelectedPolicy(opt.value)}
                    className={cn('text-left rounded-md border px-3 py-2.5 transition-all',
                      selectedPolicy === opt.value
                        ? 'border-accent/50 bg-accent/5 text-content-primary'
                        : 'border-border text-content-tertiary hover:border-border hover:bg-surface-1')}>
                    <div className="text-xs font-semibold">{opt.label}</div>
                    <div className="text-[10px] text-content-tertiary mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
              {creds.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase text-content-tertiary mb-1">Primary credential (optional)</div>
                  <select value={primaryCredId ?? ''} onChange={e => setPrimaryCredId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full sm:w-72 px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
                    <option value="">Auto (from chain)</option>
                    {creds.filter(c => c.enabled).map((c: any) => (
                      <option key={c.id} value={c.id}>{c.label} ({c.provider_name})</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex items-center gap-2 pt-1">
                <button onClick={saveRoute} disabled={savingRoute}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-white text-xs font-medium disabled:opacity-40 hover:opacity-90 transition-opacity">
                  {savingRoute ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                  Save policy
                </button>
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
                    <select value={sandboxCredId ?? ''} onChange={e => setSandboxCredId(e.target.value ? Number(e.target.value) : null)}
                      className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
                      <option value="">Select…</option>
                      {creds.map((c: any) => (
                        <option key={c.id} value={c.id}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase text-content-tertiary mb-1">Capability</div>
                    <select value={sandboxCapability} onChange={e => setSandboxCapability(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
                      <option value="text-gen">text-gen</option>
                      <option value="tts-standard">tts-standard</option>
                      <option value="image-gen">image-gen</option>
                      <option value="health">health-check</option>
                    </select>
                  </div>
                  <div className="flex items-end">
                    <button onClick={runSandbox} disabled={!sandboxCredId || sandboxRunning}
                      className="flex items-center gap-1.5 w-full h-[34px] px-3 rounded-md bg-accent text-white text-xs font-medium disabled:opacity-40 hover:opacity-90 transition-opacity justify-center">
                      {sandboxRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                      Run
                    </button>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-content-tertiary mb-1">
                    {sandboxCapability === 'tts-standard' ? 'Text to speak' : 'Prompt'}
                  </div>
                  <textarea
                    value={sandboxPrompt}
                    onChange={e => setSandboxPrompt(e.target.value)}
                    placeholder={sandboxCapability === 'tts-standard'
                      ? 'Hello, this is a voice test.'
                      : sandboxCapability === 'image-gen'
                      ? 'A colorful sunset over mountains'
                      : 'Say hello in one sentence.'}
                    className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm h-16 font-mono resize-none focus:outline-none focus:border-accent/50"
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
          onAdded={() => { setShowAdd(false); refresh(); showToast('Credential added', 'success'); }}
        />
      )}
    </main>
  );
}

function AddCredentialDialog({ category, onClose, onAdded }: any) {
  const { showToast } = useToast();
  const [providerName, setProviderName] = useState('');
  const [label, setLabel] = useState('');
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [model, setModel] = useState('');
  const [supportedModels, setSupportedModels] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [providerRegistered, setProviderRegistered] = useState<boolean | null>(null);
  const [extra, setExtra] = useState('{}');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Registered providers for this category — populated once on open.
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

  // Load registered provider classes for this category on mount.
  // If the list is empty, the worker fleet isn't running providers for
  // this category (e.g. fresh image build) — surface that, don't let
  // the user type garbage.
  useEffect(() => {
    setRegisteredLoading(true);
    providersApi.registeredProviders(category)
      .then(r => {
        setRegistered(r.data || []);
        // Auto-select the first registered provider so the model
        // dropdown can populate immediately.
        if ((r.data || []).length > 0 && !providerName) {
          const first = r.data[0];
          setProviderName(first.provider_name);
          setSupportedModels(first.supported_models);
          setDefaultModel(first.default_model);
          setProviderRegistered(true);
          if (first.default_model) setModel(first.default_model);
        }
      })
      .catch(() => setRegistered([]))
      .finally(() => setRegisteredLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  // When the user changes the selected provider, hydrate model dropdown.
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
      if (!model && match.default_model) setModel(match.default_model);
    } else {
      setProviderRegistered(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerName, registered]);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      let extra_config = {};
      try { extra_config = JSON.parse(extra || '{}'); } catch { setErr('Extra config must be valid JSON'); setBusy(false); return; }
      await providersApi.createCredential({
        category, provider_name: providerName, label,
        secret_value: secret, secret_key: 'api_key',
        model: model || null,
        extra_config,
      });
      onAdded();
    } catch (e: any) { setErr(e?.message || 'Failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="rounded-xl bg-surface-0 max-w-md w-full p-5 border border-border shadow-elevated space-y-3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-content-primary">Add credential — {category}</h3>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary"><X size={14} /></button>
        </div>

        {/* Provider — dropdown of classes registered in-process. We
            deliberately don't allow free-text: any name the resolver
            can't instantiate is dead weight. */}
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Provider</div>
          {registeredLoading ? (
            <div className="px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-xs text-content-tertiary">
              Loading registered providers…
            </div>
          ) : registered.length === 0 ? (
            <div className="rounded-md border border-status-warning/40 bg-status-warning/5 px-2.5 py-2 text-xs text-status-warning">
              No providers registered for <span className="font-mono">{category}</span>.
              The BFF didn't import any provider classes for this category.
              Check <span className="font-mono">src/providers/boot.py</span>.
            </div>
          ) : (
            <select value={providerName} onChange={e => setProviderName(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
              {registered.map(r => (
                <option key={r.provider_name} value={r.provider_name}>
                  {r.display_name}
                  {r.has_free_tier ? '  ·  free tier' : ''}
                  {' '}({r.provider_name})
                </option>
              ))}
            </select>
          )}
          <div className="text-[10px] text-content-tertiary mt-1 flex items-center gap-2">
            <span>Pick the upstream API. Only providers registered in this build are shown.</span>
            {(() => {
              const sel = registered.find(r => r.provider_name === providerName);
              return sel?.website_url ? (
                <a href={sel.website_url} target="_blank" rel="noreferrer"
                  className="text-accent hover:underline">docs ↗</a>
              ) : null;
            })()}
          </div>
        </div>
        {/* Label — free text but with suggested presets via datalist. */}
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Label</div>
          <input
            list="cred-label-suggestions"
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="e.g. Primary, Backup, Personal account"
            className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50"
          />
          <datalist id="cred-label-suggestions">
            <option value="Primary" />
            <option value="Backup" />
            <option value="Personal account" />
            <option value="Team account" />
            <option value="Production" />
            <option value="Staging" />
            <option value="Development" />
            <option value="High-volume" />
            <option value="Low-cost" />
            {(() => {
              const sel = registered.find(r => r.provider_name === providerName);
              return sel ? (
                <>
                  <option value={`${sel.display_name} — Primary`} />
                  <option value={`${sel.display_name} — Backup`} />
                </>
              ) : null;
            })()}
          </datalist>
          <div className="text-[10px] text-content-tertiary mt-1">
            Friendly display name shown in chains and logs. Free-text — pick from suggestions or type your own.
          </div>
        </div>

        {/* Secret field with show/hide */}
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">API key</div>
          <div className="flex items-center gap-1.5">
            <input
              type={showSecret ? 'text' : 'password'}
              value={secret}
              onChange={e => setSecret(e.target.value)}
              placeholder="sk-…"
              className="flex-1 px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm font-mono focus:outline-none focus:border-accent/50"
            />
            <button onClick={() => setShowSecret(v => !v)}
              className="w-8 h-8 flex items-center justify-center rounded border border-border text-content-tertiary hover:bg-surface-2 transition-colors">
              {showSecret ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          </div>
          <div className="text-[10px] text-content-tertiary mt-1">Stored securely in Vault. Never logged.</div>
        </div>

        {/* Model — populated from supported_models() once provider is known */}
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1 flex items-center gap-2">
            <span>Model</span>
            {providerRegistered === false && providerName.trim() && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-status-warning/10 text-status-warning">
                Provider not registered — type model name manually
              </span>
            )}
            {defaultModel && (
              <span className="text-[9px] text-content-tertiary">default: {defaultModel}</span>
            )}
          </div>
          {supportedModels.length > 0 ? (
            <select value={model} onChange={e => setModel(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
              <option value="">Use provider default ({defaultModel || 'auto'})</option>
              {supportedModels.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          ) : (
            <input value={model} onChange={e => setModel(e.target.value)}
              placeholder={defaultModel || 'e.g. claude-sonnet-4-20250514'}
              className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm font-mono focus:outline-none focus:border-accent/50" />
          )}
          <div className="text-[10px] text-content-tertiary mt-1">
            Each credential pins one model. Add a second credential to use the same vendor key with a different model.
          </div>
        </div>

        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Extra config (JSON, optional)</div>
          <textarea className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-xs h-20 font-mono focus:outline-none focus:border-accent/50"
            value={extra} onChange={e => setExtra(e.target.value)} />
          <div className="text-[10px] text-content-tertiary mt-1">Provider-specific config (model, base_url, etc.)</div>
        </div>

        {err && <div className="text-sm text-status-error">{err}</div>}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-3 py-1.5 rounded-md border border-border text-sm text-content-secondary hover:bg-surface-2 transition-colors">
            Cancel
          </button>
          <button onClick={submit} disabled={busy || !providerName || !label || !secret}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition-opacity">
            <Check size={13} /> {busy ? 'Saving…' : 'Save to Vault'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Inp({ label, hint, value, onChange, placeholder, type = 'text' }: any) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase text-content-tertiary mb-1">{label}</div>
      <input className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50"
        type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
      {hint && <div className="text-[10px] text-content-tertiary mt-1">{hint}</div>}
    </label>
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
