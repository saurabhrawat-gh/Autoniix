'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { providersApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Plug, ChevronRight, CheckCircle2, AlertTriangle, HelpCircle, Cpu,
  Activity, RotateCw, Plus, Loader2, ShieldCheck, SlidersHorizontal,
  Gauge, Boxes, Network,
} from '@/lib/components/Icon';

const KIND_META: Record<string, { icon: string; desc: string; color: string }> = {
  llm:     { icon: '🧠', desc: 'LLMs for script, research & critique',      color: 'text-violet-500' },
  tts:     { icon: '🎙️', desc: 'Voice synthesis (TTS)',                     color: 'text-blue-500' },
  image:   { icon: '🖼️', desc: 'Image generation for thumbnails & assets',  color: 'text-pink-500' },
  search:  { icon: '🔍', desc: 'Web search & trend data',                   color: 'text-amber-500' },
  storage: { icon: '💾', desc: 'Object storage for media files',             color: 'text-emerald-500' },
};

type HealthStatus = 'healthy' | 'failing' | 'untested' | 'partial';

function getCategoryHealth(healthy: number, failing: number, total: number): HealthStatus {
  if (total === 0) return 'untested';
  if (failing === 0 && healthy > 0) return 'healthy';
  if (healthy === 0 && failing > 0) return 'failing';
  if (healthy > 0 && failing > 0) return 'partial';
  return 'untested';
}

const HEALTH_DOT: Record<HealthStatus, string> = {
  healthy:  'bg-emerald-500',
  failing:  'bg-red-500 animate-pulse',
  partial:  'bg-amber-500',
  untested: 'bg-surface-3',
};
const HEALTH_LABEL: Record<HealthStatus, string> = {
  healthy:  'All healthy',
  failing:  'Degraded',
  partial:  'Partial',
  untested: 'Unconfigured',
};

export default function ProvidersIndex() {
  const { showToast } = useToast();
  const [cats, setCats] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingAll, setTestingAll] = useState(false);

  const refresh = () => {
    setLoading(true);
    Promise.all([
      providersApi.categories().then(r => setCats(r.data || [])),
      providersApi.credentials().then(r => setCreds(r.data || [])),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const grouped: Record<string, any[]> = cats.reduce((acc: any, c: any) => {
    (acc[c.kind] ||= []).push(c);
    return acc;
  }, {});

  const credsByCategory = (catName: string) => creds.filter(cr => cr.category === catName);
  const countStatus = (catName: string) => {
    const mc = credsByCategory(catName);
    return {
      total:   mc.length,
      healthy: mc.filter(c => c.last_health_ok === true).length,
      failing: mc.filter(c => c.last_health_ok === false).length,
    };
  };

  const totalCreds   = creds.length;
  const totalHealthy = creds.filter(c => c.last_health_ok === true).length;
  const totalFailing = creds.filter(c => c.last_health_ok === false).length;
  const totalUntested = creds.filter(c => c.last_health_ok === null).length;

  const testAll = async () => {
    const ids = creds.map((c: any) => c.id);
    if (!ids.length) return;
    setTestingAll(true);
    let ok = 0, fail = 0;
    await Promise.allSettled(
      ids.map(id =>
        providersApi.testCredential(id)
          .then(r => { if (r.data?.ok) ok++; else fail++; })
          .catch(() => fail++)
      )
    );
    await refresh();
    setTestingAll(false);
    showToast(`Health check: ${ok} OK, ${fail} failed`, ok > 0 && fail === 0 ? 'success' : 'error');
  };

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Plug size={20} className="text-accent" /> Provider Operations
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Plug-in / plug-out provider chains with automatic health-based fallback.
            Secrets stored in Vault — never in your repo or database.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={refresh} disabled={loading}
            className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </button>
          <button onClick={testAll} disabled={testingAll || totalCreds === 0}
            className="flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors disabled:opacity-40">
            {testingAll ? <Loader2 size={12} className="animate-spin" /> : <Activity size={12} />}
            Test all
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Total credentials', value: totalCreds,    color: 'text-content-primary' },
          { label: 'Healthy',           value: totalHealthy,  color: 'text-emerald-500' },
          { label: 'Failing',           value: totalFailing,  color: 'text-red-500' },
          { label: 'Untested',          value: totalUntested, color: 'text-content-tertiary' },
        ].map(s => (
          <div key={s.label} className="rounded-md border border-border bg-surface-0 px-4 py-3">
            <div className={cn('text-2xl font-bold tabular-nums', s.color)}>{s.value}</div>
            <div className="text-[11px] text-content-tertiary mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-md border border-border bg-surface-0 p-4 animate-pulse h-32" />
          ))}
        </div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="py-20 text-center text-sm text-content-tertiary">
          <Cpu size={32} className="mx-auto mb-3 opacity-30" />
          No provider categories found. Ensure the backend is running.
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([kind, list]: any) => {
            const meta = KIND_META[kind] || { icon: '🔌', desc: 'Provider category', color: 'text-content-primary' };
            return (
              <section key={kind}>
                {/* Kind header */}
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-lg">{meta.icon}</span>
                  <div>
                    <h2 className="text-sm font-semibold text-content-primary capitalize">{kind.replace(/_/g, ' ')}</h2>
                    <p className="text-xs text-content-tertiary">{meta.desc}</p>
                  </div>
                  <div className="ml-auto text-xs text-content-tertiary">{list.length} categor{list.length !== 1 ? 'ies' : 'y'}</div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {list.map((cat: any) => {
                    const { total, healthy, failing } = countStatus(cat.name);
                    const health = getCategoryHealth(healthy, failing, total);
                    const inChain = creds.filter(c => c.category === cat.name && c.last_health_ok === true).length;

                    return (
                      <Link
                        key={cat.name}
                        href={`/dashboard/providers/${encodeURIComponent(cat.name)}`}
                        className="group rounded-xl border border-border bg-surface-0 p-4 hover:border-accent/40 hover:shadow-card transition-all"
                      >
                        {/* Card header */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={cn('w-2 h-2 rounded-full shrink-0', HEALTH_DOT[health])} />
                              <span className="text-sm font-semibold text-content-primary group-hover:text-accent transition-colors truncate">
                                {cat.label}
                              </span>
                            </div>
                            <div className="text-[10px] text-content-tertiary font-mono mt-1 ml-4">{cat.name}</div>
                          </div>
                          <ChevronRight size={14} className="text-content-tertiary group-hover:text-accent transition-colors shrink-0 mt-0.5" />
                        </div>

                        {/* Description */}
                        {cat.description && (
                          <p className="text-[11px] text-content-tertiary mb-3 line-clamp-2">{cat.description}</p>
                        )}

                        {/* Credential bar */}
                        {total === 0 ? (
                          <div className="flex items-center gap-1.5 text-xs text-content-tertiary">
                            <Plus size={11} />
                            <span>No credentials — click to add</span>
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            {/* Health bar */}
                            <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                              <div
                                className={cn('h-full rounded-full transition-all',
                                  health === 'healthy' ? 'bg-emerald-500' :
                                  health === 'failing' ? 'bg-red-500' :
                                  health === 'partial' ? 'bg-amber-500' : 'bg-surface-3'
                                )}
                                style={{ width: `${total > 0 ? (healthy / total) * 100 : 0}%` }}
                              />
                            </div>
                            {/* Stats row */}
                            <div className="flex items-center justify-between text-[10px]">
                              <span className={cn(
                                'font-medium',
                                health === 'healthy' ? 'text-emerald-500' :
                                health === 'failing' ? 'text-red-500' :
                                health === 'partial' ? 'text-amber-500' : 'text-content-tertiary'
                              )}>
                                {HEALTH_LABEL[health]}
                              </span>
                              <span className="text-content-tertiary">
                                {healthy}/{total} healthy
                              </span>
                            </div>
                          </div>
                        )}
                      </Link>
                    );
                  })}

                  {/* Quick-add placeholder card */}
                  <Link
                    href={`/dashboard/providers/${encodeURIComponent(list[0]?.name || kind)}`}
                    className="group rounded-xl border border-dashed border-border bg-transparent p-4 hover:border-accent/50 hover:bg-surface-0 transition-all flex flex-col items-center justify-center gap-2 min-h-[110px]"
                  >
                    <div className="w-8 h-8 rounded-full bg-surface-2 group-hover:bg-accent/10 flex items-center justify-center transition-colors">
                      <Plus size={14} className="text-content-tertiary group-hover:text-accent" />
                    </div>
                    <span className="text-xs text-content-tertiary group-hover:text-content-secondary transition-colors">
                      Configure {kind}
                    </span>
                  </Link>
                </div>
              </section>
            );
          })}
        </div>
      )}

      {/* Architecture note */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          {
            icon: <Network size={15} className="text-accent" />,
            title: 'Priority Chains',
            desc: 'Multiple credentials per category form a fallback chain. First healthy provider wins.',
          },
          {
            icon: <ShieldCheck size={15} className="text-emerald-500" />,
            title: 'Vault-Backed Secrets',
            desc: 'API keys are written to env/Vault — never stored in DB or repo.',
          },
          {
            icon: <Gauge size={15} className="text-amber-500" />,
            title: 'Live Health Checks',
            desc: 'Test any credential on demand. Results feed the priority chain resolver.',
          },
        ].map(tip => (
          <div key={tip.title} className="rounded-xl border border-border bg-surface-0 px-4 py-3 flex items-start gap-3">
            <div className="mt-0.5 shrink-0">{tip.icon}</div>
            <div>
              <div className="text-xs font-semibold text-content-primary mb-0.5">{tip.title}</div>
              <div className="text-[11px] text-content-tertiary leading-relaxed">{tip.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
