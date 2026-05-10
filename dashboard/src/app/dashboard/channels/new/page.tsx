'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, ChevronLeft, ChevronRight, Check, Save, Wand2, X } from 'lucide-react';
import { channelsApi } from '@/lib/api-v2';

type Pillar = { name: string; description?: string; weight?: number; examples?: string[] };
type Rule = { kind: string; value: string };
type Reference = { kind: string; label?: string; uri?: string };

const STEPS = [
  { key: 'basics',     title: 'Basics',          hint: 'Name, platform, niche, language' },
  { key: 'strategy',   title: 'Strategy',        hint: 'What kind of channel is this?' },
  { key: 'pillars',    title: 'Mission & pillars', hint: 'Mission, vision, content pillars' },
  { key: 'voice',      title: 'Voice & style',   hint: 'TTS voice, tone, narration, music' },
  { key: 'visual',     title: 'Visual identity', hint: 'Thumbnails, colors, typography' },
  { key: 'references', title: 'References',      hint: 'Brand docs, scripts, inspiration' },
  { key: 'automation', title: 'Automation',      hint: 'Auto-publish, review, schedule' },
  { key: 'review',     title: 'Review',          hint: 'Confirm and create' },
] as const;

type FormState = {
  channel_name: string;
  niche: string;
  sub_niche: string;
  platform: string;
  handle: string;
  description: string;
  primary_language: string;
  geography: string;
  target_age_group: string;
  target_audience: string;
  content_mode: 'short' | 'long' | 'mixed';
  preset: string;
  content_type_tags: string[];

  mission: string;
  vision: string;
  brand_personality: string;
  tone: string;
  pillars: Pillar[];
  topic_rules: Rule[];

  narration_style: string;
  music_style: string;
  humor_style: string;
  pacing_style: string;
  elevenlabs_voice_id: string;
  voice_stability: number;
  voice_similarity: number;
  voice_style: number;
  emotion_intensity: number;

  thumbnail_style: string;
  primary_color: string;
  secondary_color: string;
  typography_preference: string;
  lut_preference: string;
  transition_preference: string;
  meme_intensity: number;

  references: Reference[];

  auto_upload: boolean;
  human_review_required: 'never' | 'first_10' | 'always';
  human_review_ratio: number;
  review_timeout_hours: number;
  max_daily_api_spend: number;
  videos_per_week_short: number;
  videos_per_week_long: number;
  short_form_duration: number;
  long_form_duration: number;
};

const initialState: FormState = {
  channel_name: '', niche: '', sub_niche: '', platform: 'youtube', handle: '', description: '',
  primary_language: 'en', geography: '', target_age_group: '', target_audience: '',
  content_mode: 'short', preset: '', content_type_tags: [],
  mission: '', vision: '', brand_personality: '', tone: '',
  pillars: [], topic_rules: [],
  narration_style: '', music_style: '', humor_style: '', pacing_style: '',
  elevenlabs_voice_id: '', voice_stability: 0.5, voice_similarity: 0.75, voice_style: 0.4,
  emotion_intensity: 5,
  thumbnail_style: '', primary_color: '#7c3aed', secondary_color: '#0ea5e9',
  typography_preference: '', lut_preference: '', transition_preference: '', meme_intensity: 3,
  references: [],
  auto_upload: false, human_review_required: 'first_10', human_review_ratio: 0.0,
  review_timeout_hours: 24, max_daily_api_spend: 5,
  videos_per_week_short: 7, videos_per_week_long: 1,
  short_form_duration: 60, long_form_duration: 600,
};

export default function ChannelWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<FormState>(initialState);
  const [presets, setPresets] = useState<any[]>([]);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    channelsApi.presets().then(r => setPresets(r.data || []));
  }, []);

  // Autosave draft (debounced).
  useEffect(() => {
    const t = setTimeout(async () => {
      if (!state.channel_name) return;
      setSavingDraft(true);
      try {
        if (draftId === null) {
          const r = await channelsApi.draftCreate(step + 1, state);
          setDraftId(r.id);
        } else {
          await channelsApi.draftSave(draftId, step + 1, state);
        }
      } catch {
        // best-effort
      } finally {
        setSavingDraft(false);
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [state, step, draftId]);

  const update = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setState(s => ({ ...s, [k]: v }));

  const next = () => setStep(s => Math.min(s + 1, STEPS.length - 1));
  const prev = () => setStep(s => Math.max(s - 1, 0));

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const r = await channelsApi.create(state);
      router.push(`/dashboard/channels/${r.channel_id}`);
    } catch (e: any) {
      setError(e?.message || 'Failed to create channel');
    } finally {
      setSubmitting(false);
    }
  };

  const completeness = useMemo(() => {
    const filled = [
      state.channel_name, state.niche, state.mission, state.tone, state.brand_personality,
      state.narration_style, state.music_style, state.thumbnail_style,
      state.pillars.length > 0,
    ].filter(Boolean).length;
    return Math.round((filled / 9) * 100);
  }, [state]);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
    <div className="max-w-5xl mx-auto">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">New channel</h1>
          <p className="text-sm opacity-70 mt-1">
            Seed everything our AI pipeline needs. You can revisit any field later from settings.
          </p>
        </div>
        <div className="text-right text-xs">
          <div className="opacity-60">Profile completeness</div>
          <div className="text-lg font-semibold">{completeness}%</div>
          {savingDraft && <div className="opacity-60 inline-flex gap-1 items-center"><Save size={10}/> autosaving</div>}
        </div>
      </div>

      {/* Step rail */}
      <ol className="grid grid-cols-8 gap-1 mb-6">
        {STEPS.map((s, i) => (
          <li key={s.key} className="text-[10px]">
            <button
              onClick={() => setStep(i)}
              className={
                'block w-full text-left px-2 py-1.5 rounded-md border transition ' +
                (i === step
                  ? 'border-accent bg-accent/10'
                  : i < step
                    ? 'border-emerald-500/50 bg-emerald-500/5'
                    : 'border-border hover:bg-surface-2/60')
              }>
              <div className="font-medium">{i + 1}. {s.title}</div>
              <div className="opacity-60 truncate">{s.hint}</div>
            </button>
          </li>
        ))}
      </ol>

      <div className="rounded-xl border border-border bg-surface-0 p-6 min-h-[420px]">
        {STEPS[step].key === 'basics' && (
          <BasicsStep state={state} update={update} />
        )}
        {STEPS[step].key === 'strategy' && (
          <StrategyStep state={state} update={update} presets={presets} />
        )}
        {STEPS[step].key === 'pillars' && (
          <PillarsStep state={state} update={update} />
        )}
        {STEPS[step].key === 'voice' && (
          <VoiceStep state={state} update={update} />
        )}
        {STEPS[step].key === 'visual' && (
          <VisualStep state={state} update={update} />
        )}
        {STEPS[step].key === 'references' && (
          <ReferencesStep state={state} update={update} />
        )}
        {STEPS[step].key === 'automation' && (
          <AutomationStep state={state} update={update} />
        )}
        {STEPS[step].key === 'review' && (
          <ReviewStep state={state} />
        )}
        {error && <div className="mt-4 text-sm text-red-500">{error}</div>}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={prev} disabled={step === 0}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-border disabled:opacity-40">
          <ChevronLeft size={14} /> Back
        </button>
        {step < STEPS.length - 1 ? (
          <button onClick={next}
            className="inline-flex items-center gap-1 px-4 py-1.5 rounded-md bg-accent text-white text-sm hover:bg-accent">
            Next <ChevronRight size={14} />
          </button>
        ) : (
          <button onClick={submit} disabled={submitting || !state.channel_name || !state.niche}
            className="inline-flex items-center gap-1 px-4 py-1.5 rounded-md bg-emerald-500 text-white text-sm hover:bg-emerald-600 disabled:opacity-40">
            <Check size={14} /> {submitting ? 'Creating…' : 'Create channel'}
          </button>
        )}
      </div>
    </div>
    </main>
  );
}

// ── Field primitive ──────────────────────────────────────
function Field({
  label, hint, children, suggest,
}: { label: string; hint?: string; children: React.ReactNode; suggest?: () => void }) {
  return (
    <label className="block">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</span>
        {suggest && (
          <button onClick={suggest} className="text-[10px] inline-flex items-center gap-1 opacity-60 hover:opacity-100">
            <Wand2 size={10} /> AI suggest
          </button>
        )}
      </div>
      {children}
      {hint && <div className="text-[11px] opacity-60 mt-1">{hint}</div>}
    </label>
  );
}

const inputClass =
  'w-full px-3 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:border-accent outline-none';

async function aiSuggest(field: string, context: any, set: (v: string) => void) {
  try {
    const r = await channelsApi.fieldSuggest(field, context);
    set(r.data.suggestion);
  } catch {/* ignore */}
}

// ── Step components ──────────────────────────────────────
function BasicsStep({ state, update }: { state: FormState; update: any }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Channel name" hint="Public-facing name. You can change this later.">
        <input className={inputClass} value={state.channel_name}
          onChange={e => update('channel_name', e.target.value)} placeholder="The Curious Engineer" />
      </Field>
      <Field label="Platform" hint="Primary distribution platform.">
        <select className={inputClass} value={state.platform} onChange={e => update('platform', e.target.value)}>
          {['youtube','tiktok','instagram','facebook','twitter','linkedin','multi'].map(p => <option key={p}>{p}</option>)}
        </select>
      </Field>
      <Field label="Handle (optional)" hint="@thecuriousengineer">
        <input className={inputClass} value={state.handle} onChange={e => update('handle', e.target.value)} placeholder="@yourhandle" />
      </Field>
      <Field label="Niche" hint="The 1-2 word category. Used by research + topic generation.">
        <input className={inputClass} value={state.niche} onChange={e => update('niche', e.target.value)} placeholder="science explainer" />
      </Field>
      <Field label="Sub-niche">
        <input className={inputClass} value={state.sub_niche} onChange={e => update('sub_niche', e.target.value)} placeholder="quantum mechanics for hobbyists" />
      </Field>
      <Field label="Primary language">
        <select className={inputClass} value={state.primary_language} onChange={e => update('primary_language', e.target.value)}>
          {['en','es','hi','fr','de','pt','it','ja','ko','zh'].map(l => <option key={l}>{l}</option>)}
        </select>
      </Field>
      <Field label="Geography" hint="Where most viewers should be.">
        <input className={inputClass} value={state.geography} onChange={e => update('geography', e.target.value)} placeholder="US / Global / EU" />
      </Field>
      <Field label="Target age group">
        <input className={inputClass} value={state.target_age_group} onChange={e => update('target_age_group', e.target.value)} placeholder="18-34" />
      </Field>
      <div className="md:col-span-2">
        <Field label="Target audience" hint="One sentence on who this channel is for. Drives hook + tone choices."
          suggest={() => aiSuggest('target_audience', { niche: state.niche, sub_niche: state.sub_niche, channel_name: state.channel_name }, v => update('target_audience', v))}>
          <input className={inputClass} value={state.target_audience} onChange={e => update('target_audience', e.target.value)}
            placeholder="Curious 25-34yo professionals who prefer 4-min reads over textbooks." />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Description"
          suggest={() => aiSuggest('description', { niche: state.niche, channel_name: state.channel_name }, v => update('description', v))}>
          <textarea className={inputClass + ' h-20'} value={state.description}
            onChange={e => update('description', e.target.value)} />
        </Field>
      </div>
    </div>
  );
}

function StrategyStep({ state, update, presets }: any) {
  const tags = ['faceless', 'commentary', 'storytelling', 'documentary', 'kids', 'podcast', 'trend-based', 'evergreen', 'character', 'persona'];
  return (
    <div className="space-y-5">
      <Field label="Content mode" hint="Shorts, long-form, or both.">
        <div className="flex gap-2">
          {(['short','long','mixed'] as const).map(m => (
            <button key={m} onClick={() => update('content_mode', m)}
              className={'px-3 py-1.5 rounded-md text-sm border ' +
                (state.content_mode === m
                  ? 'bg-accent text-white border-accent'
                  : 'border-border hover:bg-surface-2')}>{m}</button>
          ))}
        </div>
      </Field>
      <Field label="Channel type tags" hint="Select all that apply. Drives prompt presets.">
        <div className="flex flex-wrap gap-1.5">
          {tags.map(t => {
            const active = state.content_type_tags.includes(t);
            return (
              <button key={t}
                onClick={() => update('content_type_tags',
                  active ? state.content_type_tags.filter((x: string) => x !== t) : [...state.content_type_tags, t])}
                className={'px-2.5 py-1 rounded-full text-xs border ' +
                  (active ? 'bg-accent text-white border-accent'
                          : 'border-border hover:bg-surface-2')}>
                {t}
              </button>
            );
          })}
        </div>
      </Field>
      <Field label="Preset" hint="Optional: pre-fill voice/style/pacing from a template.">
        <select className={inputClass} value={state.preset} onChange={e => update('preset', e.target.value)}>
          <option value="">— None —</option>
          {presets.map((p: any) => <option key={p.id} value={p.name}>{p.name} — {p.description}</option>)}
        </select>
      </Field>
    </div>
  );
}

function PillarsStep({ state, update }: any) {
  const addPillar = () => update('pillars', [...state.pillars, { name: '', description: '', weight: 1 }]);
  const removePillar = (i: number) => update('pillars', state.pillars.filter((_: any, j: number) => j !== i));
  const setPillar = (i: number, k: keyof Pillar, v: any) =>
    update('pillars', state.pillars.map((p: Pillar, j: number) => j === i ? { ...p, [k]: v } : p));

  const addRule = (kind: string) => update('topic_rules', [...state.topic_rules, { kind, value: '' }]);
  const removeRule = (i: number) => update('topic_rules', state.topic_rules.filter((_: any, j: number) => j !== i));
  const setRule = (i: number, v: string) =>
    update('topic_rules', state.topic_rules.map((r: Rule, j: number) => j === i ? { ...r, value: v } : r));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Field label="Mission" hint="Why does this channel exist?"
          suggest={() => aiSuggest('mission', { niche: state.niche, channel_name: state.channel_name }, v => update('mission', v))}>
          <textarea className={inputClass + ' h-20'} value={state.mission} onChange={e => update('mission', e.target.value)} />
        </Field>
        <Field label="Vision" hint="Where do we want it in 12 months?"
          suggest={() => aiSuggest('vision', { niche: state.niche }, v => update('vision', v))}>
          <textarea className={inputClass + ' h-20'} value={state.vision} onChange={e => update('vision', e.target.value)} />
        </Field>
        <Field label="Brand personality"
          suggest={() => aiSuggest('brand_personality', { niche: state.niche }, v => update('brand_personality', v))}>
          <input className={inputClass} value={state.brand_personality}
            onChange={e => update('brand_personality', e.target.value)} placeholder="Warm, sharply curious, occasionally playful" />
        </Field>
        <Field label="Tone"
          suggest={() => aiSuggest('tone', { niche: state.niche }, v => update('tone', v))}>
          <input className={inputClass} value={state.tone} onChange={e => update('tone', e.target.value)}
            placeholder="Direct, friendly, confident" />
        </Field>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium">Content pillars</h3>
          <button onClick={addPillar} className="text-xs px-2 py-1 rounded border border-border">+ Add pillar</button>
        </div>
        <div className="space-y-2">
          {state.pillars.length === 0 && <div className="text-xs opacity-60">No pillars yet. Add 3-5 evergreen themes.</div>}
          {state.pillars.map((p: Pillar, i: number) => (
            <div key={i} className="flex gap-2 items-start">
              <input className={inputClass + ' max-w-xs'} placeholder="Pillar name" value={p.name}
                onChange={e => setPillar(i, 'name', e.target.value)} />
              <input className={inputClass + ' flex-1'} placeholder="One-line description"
                value={p.description || ''} onChange={e => setPillar(i, 'description', e.target.value)} />
              <button onClick={() => removePillar(i)} className="px-2 py-1.5 rounded-md hover:bg-red-500/10 text-red-500"><X size={14} /></button>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RuleList kind="avoid" label="Topics to avoid" hint="The AI will refuse these." rules={state.topic_rules}
          onAdd={() => addRule('avoid')} onRemove={removeRule} onSet={setRule} />
        <RuleList kind="core" label="Core topics" hint="Boost research weight on these." rules={state.topic_rules}
          onAdd={() => addRule('core')} onRemove={removeRule} onSet={setRule} />
        <RuleList kind="primary_competitor" label="Primary competitors" hint="Used by research for benchmarking." rules={state.topic_rules}
          onAdd={() => addRule('primary_competitor')} onRemove={removeRule} onSet={setRule} />
        <RuleList kind="inspiration_competitor" label="Inspiration channels" hint="Style references." rules={state.topic_rules}
          onAdd={() => addRule('inspiration_competitor')} onRemove={removeRule} onSet={setRule} />
      </div>
    </div>
  );
}

function RuleList({ kind, label, hint, rules, onAdd, onRemove, onSet }: any) {
  const filtered = rules.map((r: Rule, i: number) => ({ r, i })).filter((x: any) => x.r.kind === kind);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</span>
        <button onClick={onAdd} className="text-[10px] opacity-60 hover:opacity-100">+ add</button>
      </div>
      <div className="space-y-1">
        {filtered.length === 0 && <div className="text-[11px] opacity-50">{hint}</div>}
        {filtered.map(({ r, i }: any) => (
          <div key={i} className="flex gap-1">
            <input className={inputClass} value={r.value} onChange={e => onSet(i, e.target.value)} />
            <button onClick={() => onRemove(i)} className="px-2 hover:bg-red-500/10 rounded text-red-500"><X size={12} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceStep({ state, update }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Narration style"
        suggest={() => aiSuggest('narration_style', { niche: state.niche, brand_personality: state.brand_personality }, v => update('narration_style', v))}>
        <input className={inputClass} value={state.narration_style} onChange={e => update('narration_style', e.target.value)} placeholder="Calm, authoritative, micro-pauses" />
      </Field>
      <Field label="Music style"
        suggest={() => aiSuggest('music_style', { niche: state.niche }, v => update('music_style', v))}>
        <input className={inputClass} value={state.music_style} onChange={e => update('music_style', e.target.value)} placeholder="Cinematic minimal, soft pads" />
      </Field>
      <Field label="Humor style"
        suggest={() => aiSuggest('humor_style', { niche: state.niche }, v => update('humor_style', v))}>
        <input className={inputClass} value={state.humor_style} onChange={e => update('humor_style', e.target.value)} placeholder="Dry observational" />
      </Field>
      <Field label="Pacing"
        suggest={() => aiSuggest('pacing_style', { content_mode: state.content_mode }, v => update('pacing_style', v))}>
        <select className={inputClass} value={state.pacing_style} onChange={e => update('pacing_style', e.target.value)}>
          <option value="">—</option>
          {['very_slow','slow','medium_slow','medium','medium_fast','fast','very_fast'].map(o => <option key={o}>{o}</option>)}
        </select>
      </Field>
      <Field label="ElevenLabs voice id" hint="(Optional) Force a specific voice id.">
        <input className={inputClass} value={state.elevenlabs_voice_id} onChange={e => update('elevenlabs_voice_id', e.target.value)} />
      </Field>
      <Field label="Emotion intensity (0-10)">
        <input type="range" min={0} max={10} value={state.emotion_intensity}
          onChange={e => update('emotion_intensity', Number(e.target.value))} className="w-full" />
        <div className="text-xs opacity-60">Current: {state.emotion_intensity}</div>
      </Field>
      <Field label="Voice stability">
        <input type="range" min={0} max={1} step={0.05} value={state.voice_stability}
          onChange={e => update('voice_stability', Number(e.target.value))} className="w-full" />
        <div className="text-xs opacity-60">{state.voice_stability.toFixed(2)}</div>
      </Field>
      <Field label="Voice style">
        <input type="range" min={0} max={1} step={0.05} value={state.voice_style}
          onChange={e => update('voice_style', Number(e.target.value))} className="w-full" />
        <div className="text-xs opacity-60">{state.voice_style.toFixed(2)}</div>
      </Field>
    </div>
  );
}

function VisualStep({ state, update }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Thumbnail style"
        suggest={() => aiSuggest('thumbnail_style', { niche: state.niche }, v => update('thumbnail_style', v))}>
        <input className={inputClass} value={state.thumbnail_style} onChange={e => update('thumbnail_style', e.target.value)} placeholder="Bold subject, single contrast color, 3-word headline" />
      </Field>
      <Field label="Typography preference"
        suggest={() => aiSuggest('typography_preference', {}, v => update('typography_preference', v))}>
        <input className={inputClass} value={state.typography_preference} onChange={e => update('typography_preference', e.target.value)} placeholder="Inter / Geist; bold weights on emphasis" />
      </Field>
      <Field label="Primary color">
        <input type="color" value={state.primary_color} onChange={e => update('primary_color', e.target.value)} className="h-10 w-20 rounded" />
      </Field>
      <Field label="Secondary color">
        <input type="color" value={state.secondary_color} onChange={e => update('secondary_color', e.target.value)} className="h-10 w-20 rounded" />
      </Field>
      <Field label="LUT preference"
        suggest={() => aiSuggest('lut_preference', { niche: state.niche }, v => update('lut_preference', v))}>
        <input className={inputClass} value={state.lut_preference} onChange={e => update('lut_preference', e.target.value)} placeholder="Cinematic teal-orange, mild contrast" />
      </Field>
      <Field label="Transition preference"
        suggest={() => aiSuggest('transition_preference', {}, v => update('transition_preference', v))}>
        <input className={inputClass} value={state.transition_preference} onChange={e => update('transition_preference', e.target.value)} placeholder="Whip-pan + match-cut; no stock fades" />
      </Field>
      <Field label="Meme intensity (0-10)">
        <input type="range" min={0} max={10} value={state.meme_intensity}
          onChange={e => update('meme_intensity', Number(e.target.value))} className="w-full" />
        <div className="text-xs opacity-60">{state.meme_intensity}</div>
      </Field>
    </div>
  );
}

function ReferencesStep({ state, update }: any) {
  const add = () => update('references', [...state.references, { kind: 'url', label: '', uri: '' }]);
  const set = (i: number, k: keyof Reference, v: string) =>
    update('references', state.references.map((r: Reference, j: number) => j === i ? { ...r, [k]: v } : r));
  const remove = (i: number) => update('references', state.references.filter((_: any, j: number) => j !== i));

  return (
    <div className="space-y-3">
      <p className="text-sm opacity-70">
        Drop in inspiration: brand docs, scripts, viral-channel URLs, asset packs. Used for style transfer + memory seeding.
      </p>
      <button onClick={add} className="text-xs px-2 py-1 rounded border border-border">+ Add reference</button>
      {state.references.map((r: Reference, i: number) => (
        <div key={i} className="grid grid-cols-12 gap-2 items-start">
          <select className={inputClass + ' col-span-2'} value={r.kind} onChange={e => set(i, 'kind', e.target.value)}>
            {['url','pdf','video','gdrive','notion','asset_pack','logo','lut','sfx','music'].map(k => <option key={k}>{k}</option>)}
          </select>
          <input className={inputClass + ' col-span-3'} placeholder="Label" value={r.label || ''} onChange={e => set(i, 'label', e.target.value)} />
          <input className={inputClass + ' col-span-6'} placeholder="URL or s3 key"
            value={r.uri || ''} onChange={e => set(i, 'uri', e.target.value)} />
          <button onClick={() => remove(i)} className="col-span-1 px-2 py-1 hover:bg-red-500/10 rounded text-red-500"><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}

function AutomationStep({ state, update }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Auto upload to platform" hint="If off, finished videos wait for manual publish.">
        <Toggle value={state.auto_upload} onChange={(v: boolean) => update('auto_upload', v)} />
      </Field>
      <Field label="Human review" hint="When should the system pause for review?">
        <select className={inputClass} value={state.human_review_required}
          onChange={e => update('human_review_required', e.target.value as any)}>
          {['never','first_10','always'].map(o => <option key={o}>{o}</option>)}
        </select>
      </Field>
      <Field label="Forced review ratio" hint="0.0-1.0. Even when 'never', force review on this fraction.">
        <input type="number" min={0} max={1} step={0.05} className={inputClass}
          value={state.human_review_ratio} onChange={e => update('human_review_ratio', Number(e.target.value))} />
      </Field>
      <Field label="Review timeout (hours)">
        <input type="number" min={1} max={168} className={inputClass}
          value={state.review_timeout_hours} onChange={e => update('review_timeout_hours', Number(e.target.value))} />
      </Field>
      <Field label="Daily API spend cap ($)">
        <input type="number" min={0} step={0.5} className={inputClass}
          value={state.max_daily_api_spend} onChange={e => update('max_daily_api_spend', Number(e.target.value))} />
      </Field>
      <Field label="Videos per week (short)">
        <input type="number" min={0} max={21} className={inputClass}
          value={state.videos_per_week_short} onChange={e => update('videos_per_week_short', Number(e.target.value))} />
      </Field>
      <Field label="Videos per week (long)">
        <input type="number" min={0} max={7} className={inputClass}
          value={state.videos_per_week_long} onChange={e => update('videos_per_week_long', Number(e.target.value))} />
      </Field>
      <Field label="Short duration (s)">
        <input type="number" min={5} max={180} className={inputClass}
          value={state.short_form_duration} onChange={e => update('short_form_duration', Number(e.target.value))} />
      </Field>
      <Field label="Long duration (s)">
        <input type="number" min={60} max={3600} className={inputClass}
          value={state.long_form_duration} onChange={e => update('long_form_duration', Number(e.target.value))} />
      </Field>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)}
      className={'h-6 w-10 rounded-full transition relative ' + (value ? 'bg-accent' : 'bg-surface-3')}>
      <span className={'absolute top-0.5 size-5 rounded-full bg-white transition ' + (value ? 'left-[1.125rem]' : 'left-0.5')} />
    </button>
  );
}

function ReviewStep({ state }: { state: FormState }) {
  const sections: [string, any][] = [
    ['Basics', { name: state.channel_name, niche: state.niche, sub_niche: state.sub_niche, language: state.primary_language, mode: state.content_mode }],
    ['Identity', { mission: state.mission, vision: state.vision, tone: state.tone, brand_personality: state.brand_personality }],
    ['Pillars', state.pillars],
    ['Voice', { narration: state.narration_style, music: state.music_style, pacing: state.pacing_style, voice_id: state.elevenlabs_voice_id }],
    ['Visual', { thumb: state.thumbnail_style, typography: state.typography_preference, lut: state.lut_preference, transitions: state.transition_preference }],
    ['Automation', { auto_upload: state.auto_upload, review: state.human_review_required, ratio: state.human_review_ratio, daily_cap: state.max_daily_api_spend }],
  ];
  return (
    <div className="space-y-4">
      <div className="text-sm opacity-70">
        <Sparkles size={14} className="inline mr-1.5" />
        You can revisit any of these from the channel's Settings tab. Press <strong>Create channel</strong> to finalize.
      </div>
      {sections.map(([k, v]) => (
        <div key={k} className="rounded-md border border-border p-3">
          <div className="text-xs font-medium uppercase tracking-wide opacity-70 mb-1">{k}</div>
          <pre className="text-xs whitespace-pre-wrap break-words opacity-80">{JSON.stringify(v, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
