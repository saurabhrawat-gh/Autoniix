'use client';

import { useEffect, useState } from 'react';
import { experimentsApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Zap, Plus, Trash2, RotateCw, X, Check, Loader2,
  TrendingUp, TrendingDown, ChevronDown, ChevronRight,
  BarChart3, AlertCircle, FlaskConical, Target, Sparkles,
  Activity, Gauge, SlidersHorizontal, Play,
  Users, Crosshair, Pause, CheckCircle2,
} from '@/lib/components/Icon';

const EXP_TEMPLATES = [
  {
    id: 'hook_style',
    title: 'Hook Style',
    icon: '🎯',
    desc: 'Compare hook styles: question vs. bold claim vs. stat-first',
    arms: ['question_hook', 'bold_claim', 'stat_first'],
    metric: 'ctr',
    color: 'border-violet-500/30 bg-violet-500/5',
    accentColor: 'text-violet-500',
  },
  {
    id: 'pacing_strategy',
    title: 'Pacing Strategy',
    icon: '⚡',
    desc: 'Test fast-cut vs. measured pacing vs. cinematic style',
    arms: ['fast_cut', 'measured', 'cinematic'],
    metric: 'retention',
    color: 'border-blue-500/30 bg-blue-500/5',
    accentColor: 'text-blue-500',
  },
  {
    id: 'thumbnail_style',
    title: 'Thumbnail Style',
    icon: '🖼️',
    desc: 'Face vs. text-overlay vs. abstract visual thumbnails',
    arms: ['face_close_up', 'bold_text', 'abstract_visual'],
    metric: 'ctr',
    color: 'border-pink-500/30 bg-pink-500/5',
    accentColor: 'text-pink-500',
  },
  {
    id: 'title_format',
    title: 'Title Format',
    icon: '📝',
    desc: 'Compare numbered lists vs. how-to vs. curiosity-gap titles',
    arms: ['numbered_list', 'how_to', 'curiosity_gap'],
    metric: 'ctr',
    color: 'border-amber-500/30 bg-amber-500/5',
    accentColor: 'text-amber-500',
  },
  {
    id: 'content_length',
    title: 'Content Length',
    icon: '⏱️',
    desc: 'Short (< 3 min) vs. mid (5–8 min) vs. long (10–15 min)',
    arms: ['short', 'mid', 'long'],
    metric: 'watch_time',
    color: 'border-emerald-500/30 bg-emerald-500/5',
    accentColor: 'text-emerald-500',
  },
  {
    id: 'voice_style',
    title: 'Voice Style',
    icon: '🎙️',
    desc: 'Authoritative vs. conversational vs. storytelling narration',
    arms: ['authoritative', 'conversational', 'storytelling'],
    metric: 'retention',
    color: 'border-teal-500/30 bg-teal-500/5',
    accentColor: 'text-teal-500',
  },
];

const STATUS_CHIP: Record<string, string> = {
  active:    'bg-emerald-500/15 text-emerald-500',
  paused:    'bg-amber-500/15 text-amber-500',
  completed: 'bg-accent/15 text-accent',
  draft:     'bg-surface-3 text-content-tertiary',
};

export default function ExperimentsPage() {
  const { showToast } = useToast();
  const [filter, setFilter] = useState('');
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [templateSeed, setTemplateSeed] = useState<(typeof EXP_TEMPLATES)[0] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);

  const refresh = () => {
    setLoading(true);
    experimentsApi.list(filter).then(r => setRows(r.data || [])).finally(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, [filter]);

  const runAction = async (fn: () => Promise<any>, label: string) => {
    try { await fn(); refresh(); showToast(`${label} done`, 'success'); }
    catch (e: any) { showToast(e?.message || `${label} failed`, 'error'); }
  };

  const openResults = async (name: string) => {
    setActive(name); setResults(null); setResultsLoading(true);
    try {
      const r = await experimentsApi.results(name);
      setResults(r.data);
    } catch (e: any) { setResults({ error: e?.message || 'failed' }); }
    setResultsLoading(false);
  };

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <FlaskConical size={20} className="text-accent" /> AI Innovation Lab
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Controlled A/B experiments across your pipeline. Traffic split by deterministic hash — same channel always gets the same variant.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={refresh} disabled={loading}
            className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-surface-2 text-content-tertiary transition-colors">
            <RotateCw size={13} className={cn(loading && 'animate-spin')} />
          </button>
          <button onClick={() => setShowTemplates(v => !v)}
            className={cn('flex items-center gap-1.5 h-8 px-3 rounded-md border text-xs font-medium transition-colors',
              showTemplates ? 'border-accent/40 bg-accent/5 text-accent' : 'border-border text-content-secondary hover:bg-surface-2')}>
            <Sparkles size={12} /> Templates
          </button>
          <button onClick={() => { setTemplateSeed(null); setShowNew(true); }}
            className="flex items-center gap-1.5 h-8 px-3 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
            <Plus size={13} /> New experiment
          </button>
        </div>
      </div>

      {/* Quick-start template gallery */}
      {showTemplates && (
        <div className="mb-5">
          <div className="text-xs font-semibold text-content-tertiary uppercase tracking-wider mb-2 flex items-center gap-2">
            <Sparkles size={11} /> Quick-start templates
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {EXP_TEMPLATES.map(t => (
              <button key={t.id} onClick={() => { setTemplateSeed(t); setShowNew(true); }}
                className={cn('rounded-xl border p-3 text-left hover:shadow-card transition-all group', t.color)}>
                <div className="text-xl mb-2">{t.icon}</div>
                <div className={cn('text-xs font-semibold mb-1', t.accentColor)}>{t.title}</div>
                <div className="text-[10px] text-content-tertiary leading-relaxed line-clamp-2">{t.desc}</div>
                <div className="mt-2 text-[9px] text-content-tertiary font-mono">{t.metric} metric · {t.arms.length} arms</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Summary stats */}
      {rows.length > 0 && (
        <div className="grid grid-cols-4 gap-2 mb-4">
          {[
            { label: 'Total',     value: rows.length, color: 'text-content-primary' },
            { label: 'Active',    value: rows.filter(r => r.status === 'active').length, color: 'text-emerald-500' },
            { label: 'Drafts',    value: rows.filter(r => r.status === 'draft').length, color: 'text-content-tertiary' },
            { label: 'Completed', value: rows.filter(r => r.status === 'completed').length, color: 'text-accent' },
          ].map(s => (
            <div key={s.label} className="rounded-lg border border-border bg-surface-0 px-3 py-2">
              <div className={cn('text-xl font-bold tabular-nums leading-none', s.color)}>{s.value}</div>
              <div className="text-[10px] text-content-tertiary mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
          {[
            { value: '', label: 'All' },
            { value: 'active',    label: 'Active' },
            { value: 'draft',     label: 'Drafts' },
            { value: 'paused',    label: 'Paused' },
            { value: 'completed', label: 'Completed' },
          ].map(o => (
            <button key={o.value} onClick={() => setFilter(o.value)}
              className={cn(
                'px-3 py-1.5 rounded text-xs font-medium transition-all',
                filter === o.value ? 'bg-surface-0 text-content-primary shadow-sm' : 'text-content-tertiary hover:text-content-secondary'
              )}>
              {o.label}
            </button>
          ))}
        </div>
        <span className="text-xs text-content-tertiary ml-1">{rows.length} experiment{rows.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-4 items-start">
        {/* Experiment list */}
        <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
          {loading && rows.length === 0 ? (
            <div className="divide-y divide-border">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="p-4 animate-pulse space-y-2">
                  <div className="h-3 w-48 bg-surface-2 rounded" />
                  <div className="h-2.5 w-64 bg-surface-2 rounded" />
                </div>
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="py-16 text-center">
              <FlaskConical size={32} className="mx-auto text-content-tertiary mb-3 opacity-40" />
              <div className="text-sm font-medium text-content-primary">No experiments</div>
              <div className="text-xs text-content-tertiary mt-1">Create one to start A/B-testing your pipeline configuration.</div>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {rows.map((exp: any) => (
                <div key={exp.experiment_name}
                  onClick={() => openResults(exp.experiment_name)}
                  className={cn(
                    'p-4 cursor-pointer transition-colors',
                    active === exp.experiment_name ? 'bg-accent/5 border-l-2 border-accent' : 'hover:bg-surface-1'
                  )}>
                  {/* Top row */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn('text-[10px] uppercase px-1.5 py-0.5 rounded font-medium',
                          STATUS_CHIP[exp.status] ?? 'bg-surface-3 text-content-tertiary')}>
                          {exp.status}
                        </span>
                        <span className="text-sm font-medium text-content-primary truncate">{exp.experiment_name}</span>
                        {exp.winning_variant && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-500">
                            winner: {exp.winning_variant}
                          </span>
                        )}
                      </div>
                      {exp.description && (
                        <p className="text-xs text-content-tertiary mt-1 truncate">{exp.description}</p>
                      )}
                    </div>
                  </div>

                  {/* Stats row */}
                  <div className="mt-2 flex items-center gap-4 text-[11px] text-content-tertiary">
                    <span className="flex items-center gap-1"><BarChart3 size={11} /> {exp.target_metric}</span>
                    <span className="flex items-center gap-1"><Users size={11} /> {(exp.variants || []).length} variants</span>
                    <span className="flex items-center gap-1"><Crosshair size={11} /> {exp.traffic_pct}% traffic</span>
                  </div>

                  {/* Action buttons */}
                  <div className="mt-3 flex gap-1.5" onClick={e => e.stopPropagation()}>
                    {exp.status === 'draft' && (
                      <button onClick={() => runAction(() => experimentsApi.activate(exp.experiment_name), 'Activate')}
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-500 text-white text-xs font-medium hover:opacity-90 transition-opacity">
                        <Play size={10} /> Activate
                      </button>
                    )}
                    {exp.status === 'active' && (
                      <button onClick={() => runAction(() => experimentsApi.pause(exp.experiment_name), 'Pause')}
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-amber-500/20 text-amber-500 border border-amber-500/30 text-xs font-medium hover:bg-amber-500/30 transition-colors">
                        <Pause size={10} /> Pause
                      </button>
                    )}
                    {exp.status !== 'completed' && (
                      <button onClick={() => {
                        const w = window.prompt('Winning variant name (leave blank if none)') ?? '';
                        runAction(() => experimentsApi.complete(exp.experiment_name, w), 'Complete');
                      }}
                        className="flex items-center gap-1 px-2.5 py-1 rounded border border-border text-xs text-content-secondary hover:bg-surface-2 transition-colors">
                        <CheckCircle2 size={10} /> Complete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Results panel */}
        <div className="rounded-md border border-border bg-surface-0 overflow-hidden sticky top-20">
          {!active ? (
            <div className="py-16 text-center">
              <BarChart3 size={28} className="mx-auto text-content-tertiary mb-3 opacity-40" />
              <div className="text-sm text-content-tertiary">Select an experiment to view results</div>
            </div>
          ) : resultsLoading ? (
            <div className="py-12 flex items-center justify-center gap-2 text-content-tertiary">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Loading results…</span>
            </div>
          ) : results?.error ? (
            <div className="p-4">
              <div className="text-sm text-red-500">{results.error}</div>
            </div>
          ) : results ? (
            <div className="p-4 space-y-4">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-content-tertiary mb-1">Experiment</div>
                <div className="font-semibold text-content-primary">{active}</div>
              </div>

              {/* Summary stats */}
              {results.summary && (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(results.summary).map(([k, v]: any) => (
                    <div key={k} className="rounded-md bg-surface-1 px-3 py-2">
                      <div className="text-[10px] text-content-tertiary capitalize">{k.replace(/_/g, ' ')}</div>
                      <div className="text-sm font-medium text-content-primary">{typeof v === 'number' ? v.toFixed(3) : String(v)}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Variants */}
              {results.variants && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-content-tertiary mb-2">Variants</div>
                  <div className="space-y-2">
                    {Object.entries(results.variants).map(([name, data]: any) => (
                      <div key={name} className="rounded-md border border-border p-2.5 text-xs">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-medium text-content-primary">{name}</span>
                          {data.n != null && <span className="text-content-tertiary">{data.n} samples</span>}
                        </div>
                        {data.mean != null && (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                              <div className="h-full bg-accent rounded-full" style={{ width: `${Math.min(100, data.mean * 100)}%` }} />
                            </div>
                            <span className="font-mono text-content-secondary">{Number(data.mean).toFixed(3)}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Significance */}
              {results.significant != null && (
                <div className={cn(
                  'rounded-md p-3 text-xs font-medium',
                  results.significant ? 'bg-emerald-500/10 text-emerald-500' : 'bg-surface-2 text-content-tertiary'
                )}>
                  {results.significant
                    ? '✓ Statistically significant (p < 0.05)'
                    : 'Not yet statistically significant — needs more data'}
                  {results.p_value != null && <span className="ml-2 font-mono">p={Number(results.p_value).toFixed(4)}</span>}
                </div>
              )}

              {/* Raw fallback */}
              {!results.summary && !results.variants && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-content-tertiary mb-1">Raw data</div>
                  <pre className="text-[10px] font-mono bg-surface-1 border border-border rounded p-2 overflow-auto max-h-64">
                    {JSON.stringify(results, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {showNew && (
        <NewExperimentDialog
          template={templateSeed}
          onClose={() => { setShowNew(false); setTemplateSeed(null); }}
          onCreated={() => { setShowNew(false); setTemplateSeed(null); refresh(); }}
        />
      )}
    </main>
  );
}

function NewExperimentDialog({ onClose, onCreated, template }: any) {
  const { showToast } = useToast();
  const [name, setName] = useState(template ? template.id + '_' + Date.now().toString(36) : '');
  const [description, setDescription] = useState(template ? template.desc : '');
  const [variantsRaw, setVariantsRaw] = useState(
    template
      ? JSON.stringify(template.arms.map((a: string) => ({ name: a })), null, 2)
      : '[\n  { "name": "control" },\n  { "name": "treatment" }\n]'
  );
  const [traffic, setTraffic] = useState(100);
  const [metric, setMetric] = useState(template ? template.metric : 'views');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const variants = JSON.parse(variantsRaw);
      await experimentsApi.create({ name, description, variants, traffic_pct: traffic, target_metric: metric });
      onCreated();
    } catch (e: any) { setErr(e?.message || 'Create failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="rounded-xl bg-surface-0 max-w-lg w-full p-5 border border-border shadow-elevated space-y-3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-content-primary">New experiment</h2>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded hover:bg-surface-2 text-content-tertiary"><X size={14} /></button>
        </div>
        <Field label="Name"><input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. script-v2-vs-v1" className={INP} /></Field>
        <Field label="Description" hint="What are you testing? Keep it brief.">
          <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Comparing GPT-4o vs Claude for hooks" className={INP} />
        </Field>
        <Field label="Variants (JSON)" hint='Each variant must have a "name" field. Add any extra config keys your workflow uses.'>
          <textarea value={variantsRaw} onChange={e => setVariantsRaw(e.target.value)} className={INP + ' h-28 font-mono text-xs'} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Traffic split %" hint="% of eligible jobs that enter this experiment">
            <input type="number" min={1} max={100} value={traffic} onChange={e => setTraffic(Number(e.target.value))} className={INP} />
          </Field>
          <Field label="Target metric" hint="Metric to compare between variants">
            <select value={metric} onChange={e => setMetric(e.target.value)} className={INP}>
              {['views','ctr','retention','likes','comments','authenticity_score'].map(m => <option key={m}>{m}</option>)}
            </select>
          </Field>
        </div>
        {err && <div className="text-sm text-red-500">{err}</div>}
        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-3 py-1.5 rounded-md border border-border text-sm text-content-secondary hover:bg-surface-2 transition-colors">Cancel</button>
          <button onClick={submit} disabled={busy || !name}
            className="px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition-opacity">
            {busy ? 'Creating…' : 'Create experiment'}
          </button>
        </div>
      </div>
    </div>
  );
}

const INP = 'w-full px-3 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50';
function Field({ label, hint, children }: any) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wide text-content-tertiary mb-1">{label}</div>
      {children}
      {hint && <div className="text-[10px] text-content-tertiary mt-1">{hint}</div>}
    </label>
  );
}
