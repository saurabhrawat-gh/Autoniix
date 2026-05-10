'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { providersApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Plug, ChevronRight, AlertTriangle, HelpCircle, Cpu,
  Activity, RotateCw, Plus, Loader2, ShieldCheck,
  Gauge, Network, Store, CheckCircle2, ExternalLink, Zap,
} from '@/lib/components/Icon';

const KIND_META: Record<string, { icon: string; desc: string }> = {
  llm:           { icon: '🧠', desc: 'LLMs for script, research & critique' },
  tts:           { icon: '🎙️', desc: 'Voice synthesis (TTS)' },
  image:         { icon: '🖼️', desc: 'Image generation for thumbnails & assets' },
  search:        { icon: '🔍', desc: 'Web search & trend data' },
  storage:       { icon: '💾', desc: 'Object storage for media files' },
  stock_footage: { icon: '🎬', desc: 'Stock footage & video clips' },
  music:         { icon: '🎵', desc: 'Background music & audio' },
  lut:           { icon: '🎨', desc: 'Color grading LUTs' },
  sfx:           { icon: '🔊', desc: 'Sound effects library' },
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
  healthy: 'bg-emerald-500', failing: 'bg-red-500 animate-pulse',
  partial: 'bg-amber-500',   untested: 'bg-surface-3',
};
const HEALTH_LABEL: Record<HealthStatus, string> = {
  healthy: 'All healthy', failing: 'Degraded', partial: 'Partial', untested: 'Unconfigured',
};

const MODE_CHIP: Record<string, string> = {
  byok:      'bg-violet-500/10 text-violet-500',
  system:    'bg-emerald-500/10 text-emerald-500',
  marketplace: 'bg-blue-500/10 text-blue-500',
  internal:  'bg-amber-500/10 text-amber-500',
};

export default function ProvidersIndex() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<'connected' | 'marketplace'>('connected');
  const [cats, setCats] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [market, setMarket] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [probingAll, setProbingAll] = useState(false);
  const [marketFilter, setMarketFilter] = useState<string>('all');

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.categories().then(r => setCats(r.data || [])),
      providersApi.credentials().then(r => setCreds(r.data || [])),
      providersApi.marketplace().then(r => setMarket(r.data || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

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

  const totalCreds    = creds.length;
  const totalHealthy  = creds.filter(c => c.last_health_ok === true).length;
  const totalFailing  = creds.filter(c => c.last_health_ok === false).length;
  const totalUntested = creds.filter(c => c.last_health_ok === null).length;
  const unconnectedCount = market.filter(m => !m.connected).length;

  const probeAll = async () => {
    if (!creds.length) return;
    setProbingAll(true);
    try {
      const r = await providersApi.probeAll();
      await refresh();
      const { ok, total } = r.summary;
      showToast(`Probe complete: ${ok}/${total} healthy`, ok === total ? 'success' : 'error');
    } catch (e: any) {
      showToast(e?.message || 'Probe failed', 'error');
    }
    setProbingAll(false);
  };

  const marketCategories = Array.from(new Set(market.map((m: any) => m.category as string))).sort();
  const filteredMarket = marketFilter === 'all' ? market : market.filter(m => m.category === marketFilter);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Plug size={18} className="text-accent" /> Provider Operations
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Plug-in / plug-out provider chains with health-based fallback. Secrets in Vault — never in DB.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={refresh} disabled={loading}
            className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </button>
          <button onClick={probeAll} disabled={probingAll || totalCreds === 0}
            className="flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors disabled:opacity-40">
            {probingAll ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            Probe all
          </button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { label: 'Connected',  value: totalCreds,    color: 'text-content-primary' },
          { label: 'Healthy',    value: totalHealthy,  color: 'text-emerald-500' },
          { label: 'Failing',    value: totalFailing,  color: 'text-red-500' },
          { label: 'Available',  value: unconnectedCount, color: 'text-blue-500' },
        ].map(s => (
          <div key={s.label} className="rounded-lg border border-border bg-surface-0 px-3 py-2">
            <div className={cn('text-xl font-bold tabular-nums leading-none', s.color)}>{s.value}</div>
            <div className="text-[10px] text-content-tertiary mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5 w-fit">
        {([['connected', 'Connected', totalCreds], ['marketplace', 'Marketplace', unconnectedCount]] as const).map(([key, label, count]) => (
          <button key={key} onClick={() => setTab(key)}
            className={cn('px-3 py-1.5 text-xs font-medium rounded transition-all flex items-center gap-1.5',
              tab === key ? 'bg-surface-0 text-content-primary shadow-sm' : 'text-content-tertiary hover:text-content-secondary')}>
            {key === 'connected' ? <Activity size={11} /> : <Store size={11} />}
            {label}
            {count > 0 && <span className={cn('text-[10px]', tab === key ? 'text-accent' : 'text-content-tertiary')}>{count}</span>}
          </button>
        ))}
      </div>

      {/* ── Connected tab ── */}
      {tab === 'connected' && (
        loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-surface-0 p-4 animate-pulse h-28" />
            ))}
          </div>
        ) : Object.keys(grouped).length === 0 ? (
          <div className="py-20 text-center text-sm text-content-tertiary">
            <Cpu size={32} className="mx-auto mb-3 opacity-30" />
            No provider categories found. Ensure the backend is running.
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(grouped).map(([kind, list]: any) => {
              const meta = KIND_META[kind] || { icon: '🔌', desc: 'Provider category' };
              return (
                <section key={kind}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-base">{meta.icon}</span>
                    <h2 className="text-sm font-semibold text-content-primary capitalize">{kind.replace(/_/g, ' ')}</h2>
                    <span className="text-[11px] text-content-tertiary">— {meta.desc}</span>
                    <span className="ml-auto text-[10px] text-content-tertiary">{list.length} categor{list.length !== 1 ? 'ies' : 'y'}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {list.map((cat: any) => {
                      const { total, healthy, failing } = countStatus(cat.name);
                      const health = getCategoryHealth(healthy, failing, total);
                      return (
                        <Link key={cat.name}
                          href={`/dashboard/providers/${encodeURIComponent(cat.name)}`}
                          className="group rounded-xl border border-border bg-surface-0 p-4 hover:border-accent/40 hover:shadow-card transition-all">
                          <div className="flex items-start justify-between mb-2">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className={cn('w-2 h-2 rounded-full shrink-0', HEALTH_DOT[health])} />
                                <span className="text-sm font-semibold text-content-primary group-hover:text-accent transition-colors truncate">
                                  {cat.label}
                                </span>
                              </div>
                              <div className="text-[10px] text-content-tertiary font-mono mt-0.5 ml-4">{cat.name}</div>
                            </div>
                            <ChevronRight size={13} className="text-content-tertiary group-hover:text-accent transition-colors shrink-0 mt-0.5" />
                          </div>
                          {cat.description && (
                            <p className="text-[11px] text-content-tertiary mb-2 line-clamp-1 ml-4">{cat.description}</p>
                          )}
                          {total === 0 ? (
                            <div className="flex items-center gap-1.5 text-xs text-content-tertiary ml-4">
                              <Plus size={10} /> No credentials — click to add
                            </div>
                          ) : (
                            <div className="ml-4 space-y-1">
                              <div className="h-1 rounded-full bg-surface-2 overflow-hidden">
                                <div className={cn('h-full rounded-full transition-all',
                                  health === 'healthy' ? 'bg-emerald-500' :
                                  health === 'failing' ? 'bg-red-500' :
                                  health === 'partial' ? 'bg-amber-500' : 'bg-surface-3')}
                                  style={{ width: `${total > 0 ? (healthy / total) * 100 : 0}%` }} />
                              </div>
                              <div className="flex items-center justify-between text-[10px]">
                                <span className={cn('font-medium',
                                  health === 'healthy' ? 'text-emerald-500' :
                                  health === 'failing' ? 'text-red-500' :
                                  health === 'partial' ? 'text-amber-500' : 'text-content-tertiary')}>
                                  {HEALTH_LABEL[health]}
                                </span>
                                <span className="text-content-tertiary">{healthy}/{total} healthy</span>
                              </div>
                            </div>
                          )}
                        </Link>
                      );
                    })}
                    <Link href={`/dashboard/providers/${encodeURIComponent(list[0]?.name || kind)}`}
                      className="group rounded-xl border border-dashed border-border bg-transparent p-4 hover:border-accent/50 hover:bg-surface-0 transition-all flex flex-col items-center justify-center gap-2 min-h-[100px]">
                      <div className="w-7 h-7 rounded-full bg-surface-2 group-hover:bg-accent/10 flex items-center justify-center transition-colors">
                        <Plus size={13} className="text-content-tertiary group-hover:text-accent" />
                      </div>
                      <span className="text-xs text-content-tertiary group-hover:text-content-secondary">Configure {kind}</span>
                    </Link>
                  </div>
                </section>
              );
            })}
          </div>
        )
      )}

      {/* ── Marketplace tab ── */}
      {tab === 'marketplace' && (
        <div className="space-y-4">
          {/* Category filter */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {(['all', ...marketCategories]).map(c => (
              <button key={c} onClick={() => setMarketFilter(c)}
                className={cn('px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  marketFilter === c
                    ? 'bg-accent/10 text-accent border border-accent/30'
                    : 'border border-border text-content-tertiary hover:bg-surface-2')}>
                {c === 'all' ? 'All' : c.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 9 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-border bg-surface-0 p-4 animate-pulse h-36" />
              ))}
            </div>
          ) : filteredMarket.length === 0 ? (
            <div className="py-20 text-center text-sm text-content-tertiary">
              <Store size={32} className="mx-auto mb-3 opacity-30" />
              No providers in this category.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredMarket.map((p: any) => (
                <div key={p.provider_key}
                  className={cn(
                    'rounded-xl border bg-surface-0 p-4 flex flex-col gap-3 transition-all',
                    p.connected ? 'border-emerald-500/30' : 'border-border',
                    p.featured && !p.connected && 'border-accent/30'
                  )}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm text-content-primary">{p.display_name}</span>
                        {p.connected && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 font-medium flex items-center gap-0.5">
                            <CheckCircle2 size={9} /> Connected
                          </span>
                        )}
                        {p.featured && !p.connected && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">Featured</span>
                        )}
                        {p.has_free_tier && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500">Free tier</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium', MODE_CHIP[p.mode] || 'bg-surface-2 text-content-tertiary')}>
                          {p.mode}
                        </span>
                        <span className="text-[10px] text-content-tertiary">{p.category}</span>
                      </div>
                    </div>
                  </div>

                  {p.description && (
                    <p className="text-[11px] text-content-tertiary line-clamp-2">{p.description}</p>
                  )}

                  {/* Capabilities */}
                  {p.capabilities?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {p.capabilities.slice(0, 4).map((cap: string) => (
                        <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary font-mono">{cap}</span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between mt-auto pt-1">
                    <span className="text-xs text-content-tertiary font-mono">{p.cost_unit || '—'}</span>
                    {p.connected ? (
                      <Link href={`/dashboard/providers/${encodeURIComponent(p.category)}`}
                        className="flex items-center gap-1 h-7 px-2.5 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors">
                        <ChevronRight size={11} /> Manage
                      </Link>
                    ) : (
                      <Link href={`/dashboard/providers/${encodeURIComponent(p.category)}`}
                        className="flex items-center gap-1 h-7 px-2.5 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
                        <Plus size={11} /> Connect
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Architecture tips (only on connected tab) */}
      {tab === 'connected' && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { icon: <Network size={14} className="text-accent" />, title: 'Priority Chains', desc: 'Multiple credentials per category form a fallback chain. First healthy provider wins.' },
            { icon: <ShieldCheck size={14} className="text-emerald-500" />, title: 'Vault-Backed Secrets', desc: 'API keys written to env/Vault — never stored in DB or repo.' },
            { icon: <Gauge size={14} className="text-amber-500" />, title: 'Live Health Probes', desc: 'Use "Probe all" for a fan-out health check across every enabled credential.' },
          ].map(t => (
            <div key={t.title} className="rounded-xl border border-border bg-surface-0 px-4 py-3 flex items-start gap-3">
              <div className="mt-0.5 shrink-0">{t.icon}</div>
              <div>
                <div className="text-xs font-semibold text-content-primary mb-0.5">{t.title}</div>
                <div className="text-[11px] text-content-tertiary leading-relaxed">{t.desc}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
