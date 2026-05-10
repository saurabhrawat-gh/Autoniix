'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { providersApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import {
  Plus, Activity, Trash2, ArrowUp, ArrowDown, X, Check, ChevronLeft,
  ShieldCheck, AlertTriangle, HelpCircle, Loader2, Eye, EyeOff, RotateCw
} from '@/lib/components/Icon';

type HealthStatus = 'healthy' | 'failing' | 'untested';
function getHealth(c: any): HealthStatus {
  if (c.last_health_ok === true) return 'healthy';
  if (c.last_health_ok === false) return 'failing';
  return 'untested';
}
const HEALTH_CHIP: Record<HealthStatus, string> = {
  healthy:  'bg-emerald-500/15 text-emerald-500',
  failing:  'bg-red-500/15 text-red-500',
  untested: 'bg-surface-2 text-content-tertiary',
};
const HEALTH_ICON: Record<HealthStatus, React.ReactNode> = {
  healthy:  <ShieldCheck size={11} className="text-emerald-500" />,
  failing:  <AlertTriangle size={11} className="text-red-500" />,
  untested: <HelpCircle size={11} className="text-content-tertiary" />,
};

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
  const [rotateId, setRotateId] = useState<number | null>(null);

  const refresh = () => {
    setLoading(true);
    Promise.all([
      providersApi.credentials(decoded).then(r => setCreds(r.data || [])),
      providersApi.chain(decoded).then(r => setChain(r.data || [])).catch(() => setChain([])),
    ]).finally(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, [decoded]);

  const moveChain = (idx: number, dir: -1 | 1) => {
    const ids = chain.map(c => c.credential_id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    providersApi.setChain(decoded, ids).then(refresh);
  };

  const addToChain = (credId: number) => {
    const ids = chain.map(c => c.credential_id);
    if (ids.includes(credId)) return;
    providersApi.setChain(decoded, [...ids, credId]).then(refresh);
  };

  const removeFromChain = (credId: number) => {
    const ids = chain.map(c => c.credential_id).filter(x => x !== credId);
    providersApi.setChain(decoded, ids).then(refresh);
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
            <div className="mb-2">
              <h2 className="text-sm font-semibold text-content-primary">Priority chain</h2>
              <p className="text-xs text-content-tertiary mt-0.5">
                Resolution order — the first healthy provider handles the call. On error it falls through to the next.
                {chain.length === 0 && ' Add credentials below, then drag them into the chain.'}
              </p>
            </div>
            <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
              {chain.length === 0 ? (
                <div className="p-5 text-sm text-content-tertiary text-center">
                  No chain configured yet. Use "Add to chain" on a credential below.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {chain.map((c: any, i: number) => {
                    const health = getHealth(c);
                    return (
                      <div key={c.credential_id} className="flex items-center gap-3 px-4 py-3">
                        <span className="text-xs font-mono text-content-tertiary w-5 shrink-0">{i + 1}.</span>
                        <div className="flex items-center gap-1.5">
                          {HEALTH_ICON[health]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-content-primary">{c.label}</div>
                          <div className="text-[11px] text-content-tertiary">{c.provider_name}</div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button onClick={() => moveChain(i, -1)} disabled={i === 0}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary disabled:opacity-30 transition-colors">
                            <ArrowUp size={13} />
                          </button>
                          <button onClick={() => moveChain(i, 1)} disabled={i === chain.length - 1}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary disabled:opacity-30 transition-colors">
                            <ArrowDown size={13} />
                          </button>
                          <button onClick={() => removeFromChain(c.credential_id)}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-red-500/10 text-content-tertiary hover:text-red-500 transition-colors">
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
                      <div key={c.id} className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-content-primary">{c.label}</span>
                              <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1', HEALTH_CHIP[health])}>
                                {HEALTH_ICON[health]}
                                {health}
                              </span>
                              {inChain && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent font-medium">in chain</span>
                              )}
                            </div>
                            <div className="text-[11px] text-content-tertiary font-mono mt-0.5">
                              {c.provider_name} · {c.vault_path}
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-1.5 shrink-0">
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
                              className="w-7 h-7 flex items-center justify-center rounded hover:bg-red-500/10 text-content-tertiary hover:text-red-500 transition-colors">
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>

                        {/* Test result inline */}
                        {testResult && (
                          <div className={cn(
                            'mt-2 text-xs rounded px-2.5 py-1.5 flex items-center gap-2',
                            testResult.ok ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'
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
  const [extra, setExtra] = useState('{}');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      let extra_config = {};
      try { extra_config = JSON.parse(extra || '{}'); } catch { setErr('Extra config must be valid JSON'); setBusy(false); return; }
      await providersApi.createCredential({ category, provider_name: providerName, label, secret_value: secret, secret_key: 'api_key', extra_config });
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

        <Inp label="Provider name" hint="Internal provider key: openai, elevenlabs, pexels, fishaudio, etc."
          value={providerName} onChange={setProviderName} placeholder="e.g. openai" />
        <Inp label="Label" hint="Friendly display name shown in chains and logs."
          value={label} onChange={setLabel} placeholder="e.g. OpenAI Primary" />

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

        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Extra config (JSON, optional)</div>
          <textarea className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-xs h-20 font-mono focus:outline-none focus:border-accent/50"
            value={extra} onChange={e => setExtra(e.target.value)} />
          <div className="text-[10px] text-content-tertiary mt-1">Provider-specific config (model, base_url, etc.)</div>
        </div>

        {err && <div className="text-sm text-red-500">{err}</div>}

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
