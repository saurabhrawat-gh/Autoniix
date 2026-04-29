'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { HomeLogo } from '@/lib/theme';

export default function NewChannelPage() {
  const router = useRouter();
  const [systemStopped, setSystemStopped] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    api.stats().then(res => setSystemStopped(res.data?.emergency_stop === true)).catch(() => {});
  }, [router]);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.channel_id || !form.channel_name || !form.niche) {
      setError('Channel ID, name, and niche are required'); return;
    }
    setLoading(true); setError('');
    try {
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
      });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to create channel');
    } finally { setLoading(false); }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center gap-3 mb-8">
        <HomeLogo />
        <div>
          <h1 className="text-lg font-semibold text-content-primary">Add Channel</h1>
          <p className="text-xs text-content-tertiary mt-0.5">Create a new YouTube channel entry</p>
        </div>
      </div>

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
        <Field label="Channel ID" placeholder="e.g., BS_SLEEP01" value={form.channel_id}
          onChange={(v) => setForm({ ...form, channel_id: v })} />
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

        <button type="submit" disabled={loading || systemStopped} className="w-full btn-primary !py-3 disabled:opacity-50 disabled:cursor-not-allowed">
          {systemStopped ? 'System Stopped' : loading ? 'Creating…' : 'Create Channel'}
        </button>
      </form>
    </div>
  );
}

function Field({ label, placeholder, value, onChange, optional }: {
  label: string; placeholder: string; value: string; onChange: (v: string) => void; optional?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-content-primary mb-1.5">
        {label}
        {optional && <span className="text-content-tertiary font-normal ml-1">(optional)</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
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
