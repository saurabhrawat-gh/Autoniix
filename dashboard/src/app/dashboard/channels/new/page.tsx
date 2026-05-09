'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { PageHeader } from '@/lib/components/PageHeader';

const DNA_FIELDS: { key: string; label: string; hint: string; placeholder: string }[] = [
  { key: 'belief_territory', label: 'Belief Territory', hint: 'The misconception or idea you challenge', placeholder: 'sleep_is_just_rest' },
  { key: 'intellectual_lens', label: 'Intellectual Lens', hint: 'The discipline / angle of authority', placeholder: 'sleep_neuroscience' },
  { key: 'topic_domain', label: 'Topic Domain', hint: 'Subject area boundary', placeholder: 'health / sleep_recovery' },
  { key: 'brand_voice', label: 'Brand Voice', hint: 'Tone and personality', placeholder: 'calm_authoritative' },
  { key: 'narrative_rhythm', label: 'Narrative Rhythm', hint: 'Storytelling structure', placeholder: 'hook_payoff_loop' },
  { key: 'emotional_contract', label: 'Emotional Contract', hint: 'Promise to the viewer', placeholder: 'curiosity_to_clarity' },
  { key: 'target_audience', label: 'Target Audience', hint: 'Who this is for', placeholder: '25-45_health_curious' },
  { key: 'thumbnail_style', label: 'Thumbnail Style', hint: 'Visual approach for thumbnails', placeholder: 'high_contrast_text_overlay' },
  { key: 'primary_color', label: 'Primary Color', hint: 'Hex color for branding', placeholder: '#0EA5E9' },
  { key: 'forbidden_words', label: 'Forbidden Words', hint: 'Comma-separated AI tells to avoid', placeholder: 'literally,actually,basically' },
  { key: 'primary_format_long', label: 'Long Format', hint: 'Default format for long videos', placeholder: 'educational_explainer' },
  { key: 'primary_format_short', label: 'Short Format', hint: 'Default format for shorts', placeholder: 'hook_fact_payoff' },
];

export default function NewChannelPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [systemStopped, setSystemStopped] = useState(false);

  // Phase 5 — niche templates (starter presets)
  type NicheTemplate = {
    id: string; label: string; niche: string; sub_niche?: string;
    summary: string; starter_topics?: string[]; dna: Record<string, string>;
  };
  const [templates, setTemplates] = useState<NicheTemplate[]>([]);
  const [pickedTemplateId, setPickedTemplateId] = useState<string>('');
  // Starter topics from the picked template — seeded into the channel's
  // topics_queue on save so the very first scheduled run has ideas to chew on.
  const [starterTopics, setStarterTopics] = useState<string[]>([]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    api.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
    api.listNicheTemplates()
      .then(res => setTemplates(res?.data?.templates || []))
      .catch(() => {});
  }, [router]);

  function applyTemplate(t: NicheTemplate) {
    // Templates seed niche/sub_niche + DNA; user-chosen channel_id/name are
    // never overwritten so the picker is safe to use mid-edit.
    setPickedTemplateId(t.id);
    setForm(prev => ({
      ...prev,
      niche: t.niche || prev.niche,
      sub_niche: t.sub_niche || prev.sub_niche,
    }));
    setDna({ ...t.dna });
    setStarterTopics(t.starter_topics || []);
    setDnaSource('llm');  // visual: treated as a known-good preset
    const topicMsg = (t.starter_topics?.length || 0) > 0
      ? ` + ${t.starter_topics!.length} starter topics`
      : '';
    showToast(`Loaded preset: ${t.label}${topicMsg}`, 'success');
  }

  const [form, setForm] = useState({
    channel_id: '', channel_name: '', niche: '', sub_niche: '',
    content_modes: ['short'] as string[],
    auto_upload: false,
    videos_per_week_short: 7,
    videos_per_week_long: 1,
    short_form_duration: 60,
    long_form_duration: 600,
    schedule_enabled: true,
    human_review_required: 'first_10',
    max_daily_api_spend: 5.00,
  });
  const [dna, setDna] = useState<Record<string, string>>({});
  const [dnaSource, setDnaSource] = useState<'pristine' | 'llm' | 'fallback' | 'manual'>('pristine');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function toggleMode(mode: string) {
    setForm(prev => {
      const modes = prev.content_modes.includes(mode)
        ? prev.content_modes.filter(m => m !== mode)
        : [...prev.content_modes, mode];
      return { ...prev, content_modes: modes.length > 0 ? modes : prev.content_modes };
    });
  }

  async function generateDna() {
    if (!form.channel_name || !form.niche) {
      showToast('Channel Name and Niche are required to generate Brand DNA', 'error');
      return;
    }
    setGenerating(true);
    try {
      const res = await api.generateBrandDna({
        channel_name: form.channel_name,
        niche: form.niche,
        sub_niche: form.sub_niche,
        content_modes: form.content_modes,
      });
      const generatedDna = res?.data?.dna || {};
      setDna(generatedDna);
      const source = res?.data?.source || 'fallback';
      setDnaSource(source === 'llm' ? 'llm' : 'fallback');
      showToast(
        source === 'llm'
          ? `Brand DNA generated (${res?.data?.model || 'LLM'}, $${res?.data?.cost_usd ?? 0})`
          : 'LLM unavailable — using deterministic defaults you can edit',
        source === 'llm' ? 'success' : 'info'
      );
    } catch (err: any) {
      showToast(err?.message || 'Brand DNA generation failed', 'error');
    } finally {
      setGenerating(false);
    }
  }

  function updateDnaField(key: string, value: string) {
    setDna(prev => ({ ...prev, [key]: value }));
    if (dnaSource !== 'manual' && dnaSource !== 'pristine') setDnaSource('manual');
    if (dnaSource === 'pristine') setDnaSource('manual');
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.channel_id || !form.channel_name || !form.niche) {
      setError('Channel ID, name, and niche are required'); return;
    }
    setLoading(true); setError('');
    try {
      // Only send DNA fields that have values (backend treats null as "use default")
      const dnaPayload: Record<string, string> = {};
      for (const [k, v] of Object.entries(dna)) {
        if (v && v.trim()) dnaPayload[k] = v.trim();
      }
      await api.createChannel({
        channel_id: form.channel_id,
        channel_name: form.channel_name,
        niche: form.niche,
        sub_niche: form.sub_niche,
        content_mode: form.content_modes.length === 2 ? 'both' : form.content_modes[0],
        auto_upload: form.auto_upload,
        videos_per_week_short: form.videos_per_week_short,
        videos_per_week_long: form.videos_per_week_long,
        short_form_duration: form.short_form_duration,
        long_form_duration: form.long_form_duration,
        schedule_enabled: form.schedule_enabled,
        human_review_required: form.human_review_required,
        max_daily_api_spend: form.max_daily_api_spend,
        // Phase 5 — preset-derived starter topics seed the topics_queue.
        // Empty array when no preset chosen → backend stores empty string.
        starter_topics: starterTopics,
        ...dnaPayload,
      });
      showToast('Channel created', 'success');
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to create channel');
      showToast(err?.message || 'Failed to create channel', 'error');
    } finally { setLoading(false); }
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Add Channel"
        subtitle="Create a new YouTube channel entry"
        crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'New Channel' }]}
        containerClassName="max-w-3xl"
      />
      <main className="max-w-3xl mx-auto w-full px-6 py-8">

      {systemStopped && (
        <div className="mb-6 p-4 rounded-lg bg-status-error/10 border border-status-error/20">
          <div className="flex items-center gap-3">
            <span className="text-status-error text-lg">■</span>
            <div>
              <h3 className="text-sm font-semibold text-status-error">System Inactive</h3>
              <p className="text-xs text-content-tertiary mt-0.5">
                Channel creation is disabled while the system is stopped. Resume the system from Settings first.
              </p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-status-error/10 text-status-error text-sm rounded-lg p-3 mb-6">{error}</div>
      )}

      <form onSubmit={handleSubmit} className={cn('card p-6 space-y-5', systemStopped && 'lockdown-frost')}>
        {/* ── Niche template picker (optional starter) ───── */}
        {templates.length > 0 && (
          <div className="rounded-lg border border-border bg-surface-1 p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-content-primary">Start from a preset</h3>
                <p className="text-xs text-content-tertiary mt-0.5">
                  Optional. Pre-fills niche, sub-niche &amp; Brand DNA from a curated template — you can edit everything afterward.
                </p>
              </div>
              {pickedTemplateId && (
                <button type="button" onClick={() => setPickedTemplateId('')}
                  className="text-xs text-content-tertiary hover:text-content-primary">
                  clear
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {templates.map(t => {
                const picked = pickedTemplateId === t.id;
                return (
                  <button key={t.id} type="button" onClick={() => applyTemplate(t)}
                    className={cn(
                      'text-left rounded-md border-2 p-3 transition-all',
                      picked
                        ? 'border-accent bg-accent/5'
                        : 'border-border bg-surface-0 hover:border-border-hover'
                    )}>
                    <div className="flex items-center gap-2 mb-1">
                      {picked && <span className="text-accent text-xs">✓</span>}
                      <span className="text-xs font-semibold text-content-primary">{t.label}</span>
                    </div>
                    <p className="text-[11px] text-content-tertiary leading-snug line-clamp-2">{t.summary}</p>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <Field label="Channel ID" placeholder="e.g., BS_SLEEP01" value={form.channel_id}
          onChange={(v) => setForm({ ...form, channel_id: v })} hint="Unique identifier, used internally. Cannot be changed later." />
        <Field label="Channel Name" placeholder="e.g., Body Signals - Sleep" value={form.channel_name}
          onChange={(v) => setForm({ ...form, channel_name: v })} />
        <div className="grid grid-cols-2 gap-4">
          <Field label="Niche" placeholder="e.g., health" value={form.niche}
            onChange={(v) => setForm({ ...form, niche: v })} />
          <Field label="Sub-Niche" placeholder="e.g., sleep_recovery" value={form.sub_niche}
            onChange={(v) => setForm({ ...form, sub_niche: v })} optional />
        </div>

        <div>
          <label className="block text-sm font-medium text-content-primary mb-2">Content Modes</label>
          <div className="flex gap-3">
            {[{ key: 'short', label: 'Short Form' }, { key: 'long_form', label: 'Long Form' }].map(({ key, label }) => (
              <button key={key} type="button" onClick={() => toggleMode(key)}
                className={cn(
                  'flex-1 px-4 py-3 rounded-lg text-sm font-medium border-2 transition-all',
                  form.content_modes.includes(key)
                    ? 'bg-accent/5 text-accent border-accent shadow-sm'
                    : 'bg-surface-0 text-content-tertiary border-border hover:border-border-hover'
                )}>
                {form.content_modes.includes(key) && <span className="mr-1.5">✓</span>}
                {label}
              </button>
            ))}
          </div>
          <p className="text-xs text-content-tertiary mt-2">Select one or both content formats.</p>
        </div>

        {/* ── Brand DNA ──────────────────────────────────── */}
        <div className="border-t border-border pt-5 mt-2">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-content-primary">Brand DNA</h3>
              <p className="text-xs text-content-tertiary mt-0.5">
                What makes this channel distinct. Research, scripts &amp; thumbnails anchor on this.
              </p>
            </div>
            <button type="button" onClick={generateDna} disabled={generating || !form.channel_name || !form.niche}
              title="Auto-fill Brand DNA from niche + name using the configured LLM"
              className={cn(
                'px-3 py-1.5 border rounded-md text-xs font-medium transition-all whitespace-nowrap',
                generating
                  ? 'text-content-tertiary bg-surface-2 border-border cursor-wait'
                  : (!form.channel_name || !form.niche)
                    ? 'text-content-tertiary bg-surface-2 border-border cursor-not-allowed opacity-50'
                    : 'text-accent bg-accent/5 border-accent/15 hover:bg-accent/10'
              )}>
              {generating ? 'Generating…' : (Object.keys(dna).length > 0 ? '↻ Regenerate' : '✨ Generate Brand DNA')}
            </button>
          </div>

          {Object.keys(dna).length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-surface-1 px-4 py-6 text-center">
              <p className="text-xs text-content-tertiary mb-1">
                Optional but strongly recommended. A channel without Brand DNA will produce generic content.
              </p>
              <p className="text-[10px] text-content-tertiary">
                Fill <strong>Channel Name</strong> + <strong>Niche</strong> above, then click Generate. You can edit every field afterward.
              </p>
            </div>
          ) : (
            <>
              {dnaSource !== 'manual' && (
                <div className={cn(
                  'mb-3 px-3 py-2 rounded-md text-[11px] font-medium',
                  dnaSource === 'llm'
                    ? 'bg-status-success/5 text-status-success border border-status-success/15'
                    : 'bg-status-warning/5 text-status-warning border border-status-warning/15'
                )}>
                  {dnaSource === 'llm'
                    ? '✓ Generated by LLM — review and edit anything before saving'
                    : '⚠ LLM unavailable — using deterministic defaults you should customize'}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                {DNA_FIELDS.map(({ key, label, hint, placeholder }) => (
                  <div key={key} className={key === 'forbidden_words' ? 'col-span-2' : ''}>
                    <label className="block text-xs font-medium text-content-primary mb-1" title={hint}>
                      {label}
                    </label>
                    <input
                      type={key === 'primary_color' ? 'text' : 'text'}
                      value={dna[key] || ''}
                      onChange={(e) => updateDnaField(key, e.target.value)}
                      placeholder={placeholder}
                      className="!text-xs !py-2"
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Production Settings */}
        <div className="border-t border-border pt-5 mt-2">
          <h3 className="text-sm font-semibold text-content-primary mb-4">Production Settings</h3>
          <div className="grid grid-cols-2 gap-4">
            <NumField label="Shorts / Week" value={form.videos_per_week_short}
              onChange={(v) => setForm({ ...form, videos_per_week_short: v })} min={0} max={30} />
            <NumField label="Long Videos / Week" value={form.videos_per_week_long}
              onChange={(v) => setForm({ ...form, videos_per_week_long: v })} min={0} max={10} />
            <NumField label="Short Duration (sec)" value={form.short_form_duration}
              onChange={(v) => setForm({ ...form, short_form_duration: v })} min={15} max={120} />
            <NumField label="Long Duration (sec)" value={form.long_form_duration}
              onChange={(v) => setForm({ ...form, long_form_duration: v })} min={120} max={1800} />
            <NumField label="Max Daily Spend ($)" value={form.max_daily_api_spend}
              onChange={(v) => setForm({ ...form, max_daily_api_spend: v })} min={0.5} max={100} step={0.5} />
            <div>
              <label className="block text-sm font-medium text-content-primary mb-1.5">Human Review</label>
              <select value={form.human_review_required}
                onChange={(e) => setForm({ ...form, human_review_required: e.target.value })}
                className="input w-full">
                <option value="first_10">First 10 Videos</option>
                <option value="always">Always</option>
                <option value="never">Never</option>
              </select>
            </div>
          </div>
        </div>

        {/* Toggles */}
        <div className="border-t border-border pt-5 mt-2 space-y-3">
          <label className="flex items-center gap-3 cursor-pointer group p-3 rounded-lg bg-surface-1 hover:bg-surface-2 transition-colors">
            <div className={cn(
              'w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all',
              form.auto_upload ? 'bg-accent border-accent' : 'border-border group-hover:border-border-hover'
            )} onClick={() => setForm({ ...form, auto_upload: !form.auto_upload })}>
              {form.auto_upload && <span className="text-white text-xs font-bold">✓</span>}
            </div>
            <div>
              <span className="text-sm font-medium text-content-primary">Auto-upload to YouTube</span>
              <p className="text-xs text-content-tertiary">Automatically upload after render completes</p>
            </div>
          </label>
          <label className="flex items-center gap-3 cursor-pointer group p-3 rounded-lg bg-surface-1 hover:bg-surface-2 transition-colors">
            <div className={cn(
              'w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all',
              form.schedule_enabled ? 'bg-accent border-accent' : 'border-border group-hover:border-border-hover'
            )} onClick={() => setForm({ ...form, schedule_enabled: !form.schedule_enabled })}>
              {form.schedule_enabled && <span className="text-white text-xs font-bold">✓</span>}
            </div>
            <div>
              <span className="text-sm font-medium text-content-primary">Enable Cron Schedule</span>
              <p className="text-xs text-content-tertiary">Automatically trigger production on schedule</p>
            </div>
          </label>
        </div>

        <button type="submit" disabled={loading || systemStopped}
          title={systemStopped ? 'Resume the system from Settings to create channels' : 'Create a new channel with these settings'}
          className="w-full btn-primary !py-3 disabled:opacity-50 disabled:cursor-not-allowed">
          {systemStopped ? 'System Stopped' : loading ? 'Creating…' : 'Create Channel'}
        </button>
      </form>
      </main>
    </div>
  );
}

function Field({ label, placeholder, value, onChange, optional, hint }: {
  label: string; placeholder: string; value: string; onChange: (v: string) => void; optional?: boolean; hint?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-content-primary mb-1.5" title={hint}>
        {label}
        {optional && <span className="text-content-tertiary font-normal ml-1">(optional)</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {hint && <p className="text-[10px] text-content-tertiary mt-1">{hint}</p>}
    </div>
  );
}

function NumField({ label, value, onChange, min, max, step = 1 }: {
  label: string; value: number; onChange: (v: number) => void;
  min?: number; max?: number; step?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-content-primary mb-1.5">{label}</label>
      <input type="number" value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        min={min} max={max} step={step}
        className="input w-full" />
    </div>
  );
}
