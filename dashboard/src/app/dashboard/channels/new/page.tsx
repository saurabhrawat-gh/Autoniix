'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, ChevronLeft, ChevronRight, Check, Save, Wand2, X, AlertCircle, CheckCircle2 } from 'lucide-react';
import { channelsApi } from '@/lib/api-v2';
import {
  validateStep,
  computeAllValidity,
  type StepKey,
  type WizardErrors,
} from './_validation';
import {
  Button,
  Switch,
  Input,
  Textarea,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/lib/ui';
import { cn } from '@/lib/utils';

type Pillar = { name: string; description?: string; weight?: number; examples?: string[] };
type Rule = { kind: string; value: string };
type Reference = { kind: string; label?: string; uri?: string };

const STEPS = [
  { key: 'basics',     title: 'Basics',          hint: 'Name, niche, language' },
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

  // AE-291 — per-step validation
  const [touchedSteps, setTouchedSteps] = useState<Set<number>>(new Set([0]));
  const allValidity = useMemo(() => computeAllValidity(state), [state]);
  const currentKey = STEPS[step].key as StepKey;
  const currentResult = useMemo(() => validateStep(currentKey, state), [currentKey, state]);
  const currentErrors: WizardErrors = currentResult.errors;
  const currentValid = currentResult.valid;
  // A step's previous steps must all be valid before it can be jumped-into.
  const canJumpTo = (idx: number): boolean => {
    if (idx <= step) return true;
    for (let i = 0; i < idx; i++) {
      const k = STEPS[i].key as StepKey;
      if (!allValidity[k]) return false;
    }
    return true;
  };
  const invalidSteps = STEPS
    .map((s, i) => ({ idx: i, key: s.key as StepKey, title: s.title }))
    .filter(s => s.key !== 'review' && !allValidity[s.key]);

  const next = () => {
    if (!currentValid) {
      setTouchedSteps(prev => new Set(prev).add(step));
      return;
    }
    setStep(s => {
      const n = Math.min(s + 1, STEPS.length - 1);
      setTouchedSteps(prev => new Set(prev).add(n));
      return n;
    });
  };
  const prev = () => setStep(s => Math.max(s - 1, 0));
  const jumpTo = (idx: number) => {
    if (!canJumpTo(idx)) return;
    setStep(idx);
    setTouchedSteps(prev => new Set(prev).add(idx));
  };

  const submit = async () => {
    if (invalidSteps.length > 0) {
      // Mark every step touched so all errors render.
      setTouchedSteps(new Set(STEPS.map((_, i) => i)));
      return;
    }
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
        {STEPS.map((s, i) => {
          const stepKey = s.key as StepKey;
          const reachable = canJumpTo(i);
          const stepValid = allValidity[stepKey];
          const wasTouched = touchedSteps.has(i);
          const showError = wasTouched && !stepValid && stepKey !== 'review';
          const showCheck = wasTouched && stepValid && stepKey !== 'review' && i !== step;
          return (
            <li key={s.key} className="text-[10px]">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => jumpTo(i)}
                disabled={!reachable}
                aria-current={i === step ? 'step' : undefined}
                className={cn(
                  'block w-full text-left h-auto px-2 py-1.5 rounded-md border transition justify-start',
                  i === step
                    ? 'border-accent bg-accent/10 text-content-primary hover:bg-accent/15'
                    : showError
                      ? 'border-status-error/50 bg-status-error/5 text-content-primary hover:bg-status-error/10'
                      : showCheck
                        ? 'border-status-success/50 bg-status-success/5 text-content-primary hover:bg-status-success/10'
                        : 'border-border hover:bg-surface-2/60',
                  !reachable && 'opacity-40 cursor-not-allowed',
                )}
              >
                <span className="block w-full">
                  <span className="font-medium flex items-center gap-1">
                    {showCheck && <CheckCircle2 size={11} className="text-status-success" />}
                    {showError && <AlertCircle  size={11} className="text-status-error" />}
                    <span>{i + 1}. {s.title}</span>
                  </span>
                  <span className="opacity-60 truncate block">{s.hint}</span>
                </span>
              </Button>
            </li>
          );
        })}
      </ol>

      <div className="rounded-xl border border-border bg-surface-0 p-6 min-h-[420px]">
        {STEPS[step].key === 'basics' && (
          <BasicsStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'strategy' && (
          <StrategyStep state={state} update={update} presets={presets} errors={currentErrors} />
        )}
        {STEPS[step].key === 'pillars' && (
          <PillarsStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'voice' && (
          <VoiceStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'visual' && (
          <VisualStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'references' && (
          <ReferencesStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'automation' && (
          <AutomationStep state={state} update={update} errors={currentErrors} />
        )}
        {STEPS[step].key === 'review' && (
          <ReviewStep state={state} invalidSteps={invalidSteps} onJump={jumpTo} />
        )}
        {error && <div className="mt-4 text-sm text-status-error">{error}</div>}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={prev} disabled={step === 0} leftIcon={<ChevronLeft size={14} />}>
          Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button
            onClick={next}
            variant={currentValid ? 'primary' : 'secondary'}
            disabled={!currentValid}
            rightIcon={<ChevronRight size={14} />}
            title={!currentValid ? 'Complete all required fields on this step first.' : undefined}
            className={!currentValid ? 'opacity-60' : undefined}
          >
            Next
          </Button>
        ) : (
          <Button
            onClick={submit}
            disabled={submitting || invalidSteps.length > 0}
            loading={submitting}
            leftIcon={<Check size={14} />}
            className="bg-status-success hover:bg-status-success/90 text-content-inverse"
            title={invalidSteps.length > 0 ? `Fix ${invalidSteps.length} step(s) before creating.` : undefined}
          >
            {submitting ? 'Creating…' : 'Create channel'}
          </Button>
        )}
      </div>
    </div>
    </main>
  );
}

// Field primitive
function Field({
  label, hint, children, suggest, error, required,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  suggest?: () => void;
  error?: string;
  required?: boolean;
}) {
  return (
    <label className={cn('block', error && 'wizard-field-error')}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium uppercase tracking-wide opacity-70">
          {label}{required && <span className="text-status-error ml-0.5">*</span>}
        </span>
        {suggest && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={suggest}
            className="h-auto px-1 py-0 text-[10px] opacity-60 hover:opacity-100"
            leftIcon={<Wand2 size={10} />}
          >
            AI suggest
          </Button>
        )}
      </div>
      <div className={cn(error && '[&_input]:border-status-error [&_textarea]:border-status-error [&_button]:border-status-error rounded-md')}>
        {children}
      </div>
      {error
        ? <div className="text-[11px] text-status-error mt-1 inline-flex items-center gap-1"><AlertCircle size={10}/> {error}</div>
        : hint && <div className="text-[11px] opacity-60 mt-1">{hint}</div>}
    </label>
  );
}

async function aiSuggest(field: string, context: any, set: (v: string) => void) {
  try {
    const r = await channelsApi.fieldSuggest(field, context);
    set(r.data.suggestion);
  } catch {/* ignore */}
}

// AE-240: platform registry — youtube is the only shipped platform
const PLATFORM_OPTIONS = [
  { value: 'youtube',   label: 'YouTube',     enabled: true  },
  { value: 'instagram', label: 'Instagram',   enabled: false },
  { value: 'tiktok',    label: 'TikTok',      enabled: false },
  { value: 'x',         label: 'X (Twitter)', enabled: false },
  { value: 'linkedin',  label: 'LinkedIn',    enabled: false },
];

// Step components
function BasicsStep({ state, update, errors }: { state: FormState; update: any; errors: WizardErrors }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Channel name" required hint="Public-facing name. You can change this later." error={errors.channel_name}>
        <Input value={state.channel_name}
          onChange={e => update('channel_name', e.target.value)} placeholder="The Curious Engineer" />
      </Field>
      <Field label="Platform" hint="More platforms coming soon.">
        <Select value={state.platform} onValueChange={(v: string) => update('platform', v)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {PLATFORM_OPTIONS.map(p => (
              <SelectItem key={p.value} value={p.value} disabled={!p.enabled}>
                <div className="flex items-center justify-between gap-4">
                  <span>{p.label}</span>
                  {!p.enabled && <span className="text-[10px] opacity-50">Coming soon</span>}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Handle (optional)" hint="@thecuriousengineer">
        <Input value={state.handle} onChange={e => update('handle', e.target.value)} placeholder="@yourhandle" />
      </Field>
      <Field label="Niche" required hint="The 1-2 word category. Used by research + topic generation." error={errors.niche}>
        <Input value={state.niche} onChange={e => update('niche', e.target.value)} placeholder="science explainer" />
      </Field>
      <Field label="Sub-niche">
        <Input value={state.sub_niche} onChange={e => update('sub_niche', e.target.value)} placeholder="quantum mechanics for hobbyists" />
      </Field>
      <Field label="Primary language" required error={errors.primary_language}>
        <Select value={state.primary_language} onValueChange={(v: string) => update('primary_language', v)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {['en','es','hi','fr','de','pt','it','ja','ko','zh'].map(l => (
              <SelectItem key={l} value={l}>{l}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Geography" hint="Where most viewers should be.">
        <Input value={state.geography} onChange={e => update('geography', e.target.value)} placeholder="US / Global / EU" />
      </Field>
      <Field label="Target age group">
        <Input value={state.target_age_group} onChange={e => update('target_age_group', e.target.value)} placeholder="18-34" />
      </Field>
      <div className="md:col-span-2">
        <Field label="Target audience" hint="One sentence on who this channel is for. Drives hook + tone choices."
          suggest={() => aiSuggest('target_audience', { niche: state.niche, sub_niche: state.sub_niche, channel_name: state.channel_name }, v => update('target_audience', v))}>
          <Input value={state.target_audience} onChange={e => update('target_audience', e.target.value)}
            placeholder="Curious 25-34yo professionals who prefer 4-min reads over textbooks." />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Description"
          suggest={() => aiSuggest('description', { niche: state.niche, channel_name: state.channel_name }, v => update('description', v))}>
          <Textarea className="h-20" value={state.description}
            onChange={e => update('description', e.target.value)} />
        </Field>
      </div>
    </div>
  );
}

function StrategyStep({ state, update, presets, errors }: any) {
  const tags = ['faceless', 'commentary', 'storytelling', 'documentary', 'kids', 'podcast', 'trend-based', 'evergreen', 'character', 'persona'];
  return (
    <div className="space-y-5">
      <Field label="Content mode" required hint="Shorts, long-form, or both." error={errors?.content_mode}>
        <div className="flex gap-2">
          {(['short','long','mixed'] as const).map(m => (
            <Button
              key={m}
              type="button"
              variant={state.content_mode === m ? 'primary' : 'outline'}
              size="sm"
              onClick={() => update('content_mode', m)}
            >
              {m}
            </Button>
          ))}
        </div>
      </Field>
      <Field label="Channel type tags" required hint="Select all that apply. Drives prompt presets." error={errors?.content_type_tags}>
        <div className="flex flex-wrap gap-1.5">
          {tags.map(t => {
            const active = state.content_type_tags.includes(t);
            return (
              <Button
                key={t}
                type="button"
                variant={active ? 'primary' : 'outline'}
                size="sm"
                onClick={() => update('content_type_tags',
                  active ? state.content_type_tags.filter((x: string) => x !== t) : [...state.content_type_tags, t])}
                className="h-7 px-2.5 rounded-full text-xs"
              >
                {t}
              </Button>
            );
          })}
        </div>
      </Field>
      <Field label="Preset" hint="Optional: pre-fill voice/style/pacing from a template.">
        <Select value={state.preset || '__none__'} onValueChange={(v: string) => update('preset', v === '__none__' ? '' : v)}>
          <SelectTrigger><SelectValue placeholder="— None —" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">— None —</SelectItem>
            {presets.map((p: any) => (
              <SelectItem key={p.id} value={p.name}>{p.name} — {p.description}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
    </div>
  );
}

function PillarsStep({ state, update, errors }: any) {
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
        <Field label="Mission" required hint="Why does this channel exist?" error={errors?.mission}
          suggest={() => aiSuggest('mission', { niche: state.niche, channel_name: state.channel_name }, v => update('mission', v))}>
          <Textarea className="h-20" value={state.mission} onChange={e => update('mission', e.target.value)} />
        </Field>
        <Field label="Vision" hint="Where do we want it in 12 months?"
          suggest={() => aiSuggest('vision', { niche: state.niche }, v => update('vision', v))}>
          <Textarea className="h-20" value={state.vision} onChange={e => update('vision', e.target.value)} />
        </Field>
        <Field label="Brand personality"
          suggest={() => aiSuggest('brand_personality', { niche: state.niche }, v => update('brand_personality', v))}>
          <Input value={state.brand_personality}
            onChange={e => update('brand_personality', e.target.value)} placeholder="Warm, sharply curious, occasionally playful" />
        </Field>
        <Field label="Tone"
          suggest={() => aiSuggest('tone', { niche: state.niche }, v => update('tone', v))}>
          <Input value={state.tone} onChange={e => update('tone', e.target.value)}
            placeholder="Direct, friendly, confident" />
        </Field>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium">
            Content pillars <span className="text-status-error">*</span>
          </h3>
          <Button type="button" variant="outline" size="sm" onClick={addPillar}>+ Add pillar</Button>
        </div>
        {errors?.pillars && (
          <div className="text-[11px] text-status-error mb-2 inline-flex items-center gap-1">
            <AlertCircle size={10}/> {errors.pillars}
          </div>
        )}
        <div className="space-y-2">
          {state.pillars.length === 0 && <div className="text-xs opacity-60">No pillars yet. Add at least 2 evergreen themes.</div>}
          {state.pillars.map((p: Pillar, i: number) => {
            const nameErr = errors?.[`pillars[${i}].name`];
            const descErr = errors?.[`pillars[${i}].description`];
            return (
              <div key={i} className="space-y-1">
                <div className="flex gap-2 items-start">
                  <Input
                    className={cn('max-w-xs', nameErr && 'border-status-error')}
                    placeholder="Pillar name"
                    value={p.name}
                    onChange={e => setPillar(i, 'name', e.target.value)}
                  />
                  <Input
                    className={cn('flex-1', descErr && 'border-status-error')}
                    placeholder="One-line description (10+ chars)"
                    value={p.description || ''}
                    onChange={e => setPillar(i, 'description', e.target.value)}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => removePillar(i)}
                    aria-label="Remove pillar"
                    className="text-status-error hover:bg-status-error/10"
                  >
                    <X size={14} />
                  </Button>
                </div>
                {(nameErr || descErr) && (
                  <div className="text-[11px] text-status-error pl-1">
                    {nameErr && <span className="mr-3">{nameErr}</span>}
                    {descErr && <span>{descErr}</span>}
                  </div>
                )}
              </div>
            );
          })}
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
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onAdd}
          className="h-auto px-1 py-0 text-[10px] opacity-60 hover:opacity-100"
        >
          + add
        </Button>
      </div>
      <div className="space-y-1">
        {filtered.length === 0 && <div className="text-[11px] opacity-50">{hint}</div>}
        {filtered.map(({ r, i }: any) => (
          <div key={i} className="flex gap-1">
            <Input value={r.value} onChange={e => onSet(i, e.target.value)} />
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => onRemove(i)}
              aria-label="Remove"
              className="text-status-error hover:bg-status-error/10"
            >
              <X size={12} />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceStep({ state, update, errors }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Narration style" required error={errors?.narration_style}
        suggest={() => aiSuggest('narration_style', { niche: state.niche, brand_personality: state.brand_personality }, v => update('narration_style', v))}>
        <Input value={state.narration_style} onChange={e => update('narration_style', e.target.value)} placeholder="Calm, authoritative, micro-pauses" />
      </Field>
      <Field label="Music style" required error={errors?.music_style}
        suggest={() => aiSuggest('music_style', { niche: state.niche }, v => update('music_style', v))}>
        <Input value={state.music_style} onChange={e => update('music_style', e.target.value)} placeholder="Cinematic minimal, soft pads" />
      </Field>
      <Field label="Humor style"
        suggest={() => aiSuggest('humor_style', { niche: state.niche }, v => update('humor_style', v))}>
        <Input value={state.humor_style} onChange={e => update('humor_style', e.target.value)} placeholder="Dry observational" />
      </Field>
      <Field label="Pacing"
        suggest={() => aiSuggest('pacing_style', { content_mode: state.content_mode }, v => update('pacing_style', v))}>
        <Select value={state.pacing_style || '__none__'} onValueChange={(v: string) => update('pacing_style', v === '__none__' ? '' : v)}>
          <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">—</SelectItem>
            {['very_slow','slow','medium_slow','medium','medium_fast','fast','very_fast'].map(o => (
              <SelectItem key={o} value={o}>{o}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="ElevenLabs voice id" hint="(Optional) Force a specific voice id.">
        <Input value={state.elevenlabs_voice_id} onChange={e => update('elevenlabs_voice_id', e.target.value)} />
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

function VisualStep({ state, update, errors }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Thumbnail style" required error={errors?.thumbnail_style}
        suggest={() => aiSuggest('thumbnail_style', { niche: state.niche }, v => update('thumbnail_style', v))}>
        <Input value={state.thumbnail_style} onChange={e => update('thumbnail_style', e.target.value)} placeholder="Bold subject, single contrast color, 3-word headline" />
      </Field>
      <Field label="Typography preference"
        suggest={() => aiSuggest('typography_preference', {}, v => update('typography_preference', v))}>
        <Input value={state.typography_preference} onChange={e => update('typography_preference', e.target.value)} placeholder="Inter / Geist; bold weights on emphasis" />
      </Field>
      <Field label="Primary color" required error={errors?.primary_color}>
        <input type="color" value={state.primary_color} onChange={e => update('primary_color', e.target.value)} className="h-10 w-20 rounded" />
      </Field>
      <Field label="Secondary color" required error={errors?.secondary_color}>
        <input type="color" value={state.secondary_color} onChange={e => update('secondary_color', e.target.value)} className="h-10 w-20 rounded" />
      </Field>
      <Field label="LUT preference"
        suggest={() => aiSuggest('lut_preference', { niche: state.niche }, v => update('lut_preference', v))}>
        <Input value={state.lut_preference} onChange={e => update('lut_preference', e.target.value)} placeholder="Cinematic teal-orange, mild contrast" />
      </Field>
      <Field label="Transition preference"
        suggest={() => aiSuggest('transition_preference', {}, v => update('transition_preference', v))}>
        <Input value={state.transition_preference} onChange={e => update('transition_preference', e.target.value)} placeholder="Whip-pan + match-cut; no stock fades" />
      </Field>
      <Field label="Meme intensity (0-10)">
        <input type="range" min={0} max={10} value={state.meme_intensity}
          onChange={e => update('meme_intensity', Number(e.target.value))} className="w-full" />
        <div className="text-xs opacity-60">{state.meme_intensity}</div>
      </Field>
    </div>
  );
}

function ReferencesStep({ state, update, errors }: any) {
  const add = () => update('references', [...state.references, { kind: 'url', label: '', uri: '' }]);
  const set = (i: number, k: keyof Reference, v: string) =>
    update('references', state.references.map((r: Reference, j: number) => j === i ? { ...r, [k]: v } : r));
  const remove = (i: number) => update('references', state.references.filter((_: any, j: number) => j !== i));

  return (
    <div className="space-y-3">
      <p className="text-sm opacity-70">
        Drop in inspiration: brand docs, scripts, viral-channel URLs, asset packs. Used for style transfer + memory seeding.
      </p>
      <Button type="button" variant="outline" size="sm" onClick={add}>+ Add reference</Button>
      {state.references.map((r: Reference, i: number) => (
        <div key={i} className="grid grid-cols-12 gap-2 items-start">
          <div className="col-span-2">
            <Select value={r.kind} onValueChange={(v: string) => set(i, 'kind', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {['url','pdf','video','gdrive','notion','asset_pack','logo','lut','sfx','music'].map(k => (
                  <SelectItem key={k} value={k}>{k}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Input className="col-span-3" placeholder="Label" value={r.label || ''} onChange={e => set(i, 'label', e.target.value)} />
          <Input className="col-span-6" placeholder="URL or s3 key"
            value={r.uri || ''} onChange={e => set(i, 'uri', e.target.value)} />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => remove(i)}
            aria-label="Remove reference"
            className="col-span-1 text-status-error hover:bg-status-error/10"
          >
            <X size={14} />
          </Button>
        </div>
      ))}
    </div>
  );
}

function AutomationStep({ state, update, errors }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      <Field label="Auto upload to platform" hint="If off, finished videos wait for manual publish.">
        <Toggle value={state.auto_upload} onChange={(v: boolean) => update('auto_upload', v)} />
      </Field>
      <Field label="Human review" required error={errors?.human_review_required} hint="When should the system pause for review?">
        <Select value={state.human_review_required} onValueChange={(v: string) => update('human_review_required', v as any)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {['never','first_10','always'].map(o => (
              <SelectItem key={o} value={o}>{o}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Forced review ratio" hint="0.0-1.0. Even when 'never', force review on this fraction.">
        <Input type="number" min={0} max={1} step={0.05}
          value={state.human_review_ratio} onChange={e => update('human_review_ratio', Number(e.target.value))} />
      </Field>
      <Field label="Review timeout (hours)">
        <Input type="number" min={1} max={168}
          value={state.review_timeout_hours} onChange={e => update('review_timeout_hours', Number(e.target.value))} />
      </Field>
      <Field label="Daily API spend cap ($)" required error={errors?.max_daily_api_spend}>
        <Input type="number" min={0} step={0.5}
          value={state.max_daily_api_spend} onChange={e => update('max_daily_api_spend', Number(e.target.value))} />
      </Field>
      <Field label="Videos per week (short)" error={errors?.videos_per_week_short}>
        <Input type="number" min={0} max={21}
          value={state.videos_per_week_short} onChange={e => update('videos_per_week_short', Number(e.target.value))} />
      </Field>
      <Field label="Videos per week (long)" error={errors?.videos_per_week_long}>
        <Input type="number" min={0} max={7}
          value={state.videos_per_week_long} onChange={e => update('videos_per_week_long', Number(e.target.value))} />
      </Field>
      <Field label="Short duration (s)">
        <Input type="number" min={5} max={180}
          value={state.short_form_duration} onChange={e => update('short_form_duration', Number(e.target.value))} />
      </Field>
      <Field label="Long duration (s)">
        <Input type="number" min={60} max={3600}
          value={state.long_form_duration} onChange={e => update('long_form_duration', Number(e.target.value))} />
      </Field>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return <Switch checked={value} onCheckedChange={onChange} />;
}

function ReviewStep({
  state, invalidSteps, onJump,
}: {
  state: FormState;
  invalidSteps: Array<{ idx: number; title: string }>;
  onJump: (idx: number) => void;
}) {
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
      {invalidSteps.length > 0 && (
        <div className="rounded-lg border border-status-error/40 bg-status-error/5 px-4 py-3 text-sm text-status-error">
          <div className="font-semibold flex items-center gap-1.5 mb-1">
            <AlertCircle size={14}/> Please complete:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {invalidSteps.map(s => (
              <Button
                key={s.idx}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onJump(s.idx)}
                className="h-auto px-2 py-0.5 text-xs border-status-error/40 text-status-error hover:bg-status-error/10"
              >
                Step {s.idx + 1}: {s.title}
              </Button>
            ))}
          </div>
        </div>
      )}
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
