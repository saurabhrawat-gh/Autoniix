'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ThemeToggle, HomeLogo } from '@/lib/theme';

interface ChannelConfig {
  channel_name: string;
  niche: string;
  content_mode: string;
  auto_upload: boolean;
  videos_per_week_short: number;
  videos_per_week_long: number;
  short_form_duration: number;
  long_form_duration: number;
  schedule_enabled: boolean;
  human_review_required: string;
  max_daily_api_spend: number;
}

export default function ChannelSettingsPage() {
  const router = useRouter();
  const params = useParams();
  const channelId = params.id as string;
  const [channel, setChannel] = useState<any>(null);
  const [form, setForm] = useState<ChannelConfig | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [systemStopped, setSystemStopped] = useState(false);

  const loadChannel = useCallback(async () => {
    try {
      const res = await api.channels(true);
      const ch = (res.data || []).find((c: any) => c.channel_id === channelId);
      if (ch) {
        setChannel(ch);
        setForm({
          channel_name: ch.channel_name,
          niche: ch.niche,
          content_mode: ch.content_mode,
          auto_upload: ch.auto_upload,
          videos_per_week_short: ch.videos_per_week_short,
          videos_per_week_long: ch.videos_per_week_long,
          short_form_duration: ch.short_form_duration,
          long_form_duration: ch.long_form_duration,
          schedule_enabled: ch.schedule_enabled,
          human_review_required: ch.human_review_required,
          max_daily_api_spend: ch.max_daily_api_spend,
        });
      }
    } catch {}
    setLoading(false);
  }, [channelId]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadChannel();
    api.stats().then(res => {
      const stopped = res.data?.emergency_stop === true;
      setSystemStopped(stopped);
      if (stopped) setEditMode(false);
    }).catch(() => {});
  }, [router, loadChannel]);

  const channelDisabled = channel?.status !== 'active';
  const isArchived = channel?.status === 'archived';
  const locked = systemStopped || channelDisabled;

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    try {
      await api.updateChannel(channelId, form);
      setEditMode(false);
      loadChannel();
    } catch {}
    setSaving(false);
  }

  function handleCancel() {
    if (channel) {
      setForm({
        channel_name: channel.channel_name,
        niche: channel.niche,
        content_mode: channel.content_mode,
        auto_upload: channel.auto_upload,
        videos_per_week_short: channel.videos_per_week_short,
        videos_per_week_long: channel.videos_per_week_long,
        short_form_duration: channel.short_form_duration,
        long_form_duration: channel.long_form_duration,
        schedule_enabled: channel.schedule_enabled,
        human_review_required: channel.human_review_required,
        max_daily_api_spend: channel.max_daily_api_spend,
      });
    }
    setEditMode(false);
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
    </div>
  );

  if (!form) return (
    <div className="flex items-center justify-center min-h-screen text-content-tertiary text-sm">
      Channel not found.
    </div>
  );

  return (
    <div className="h-screen flex flex-col">
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HomeLogo />
            <div>
              <h1 className="text-lg font-semibold text-content-primary">{channel?.channel_name}</h1>
              <p className="text-xs text-content-tertiary mt-0.5">Channel Settings</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Edit Mode Toggle — matches global settings UI */}
            <label className="flex items-center gap-2 cursor-pointer">
              <span className={cn('text-xs font-medium', locked ? 'text-content-tertiary' : 'text-content-secondary')}
                title={locked ? (systemStopped ? 'System is stopped' : isArchived ? 'Channel is archived' : 'Channel is disabled') : 'Toggle to edit settings'}>
                Edit Mode{locked ? ' (locked)' : ''}
              </span>
              <button
                onClick={locked ? undefined : () => {
                  if (editMode) handleSave();
                  else setEditMode(true);
                }}
                disabled={locked}
                className={cn(
                  'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                  editMode && !locked ? 'bg-accent' : 'bg-surface-3',
                  locked && 'opacity-50 cursor-not-allowed'
                )}>
                <span className={cn(
                  'inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform',
                  editMode && !locked ? 'translate-x-[18px]' : 'translate-x-[2px]'
                )} />
              </button>
            </label>
            {editMode && (
              <button onClick={handleCancel} className="btn-ghost !py-1 !text-xs">Cancel</button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
          {/* Channel archived banner */}
          {isArchived && !systemStopped && (
            <div className="p-4 rounded-lg bg-surface-2 border border-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-content-tertiary text-lg">▣</span>
                  <div>
                    <h3 className="text-sm font-semibold text-content-secondary">Channel Archived</h3>
                    <p className="text-xs text-content-tertiary mt-0.5">
                      Settings are read-only while the channel is archived. Restore it to make changes.
                    </p>
                  </div>
                </div>
                <button
                  onClick={async () => { try { await api.restoreChannel(channelId); loadChannel(); } catch {} }}
                  className="px-3 py-1.5 border rounded-lg text-xs font-medium text-accent bg-accent/5 border-accent/15 hover:bg-accent/10 transition-all shrink-0"
                  title="Restore this channel to disabled state">
                  Restore
                </button>
              </div>
            </div>
          )}
          {/* Channel disabled banner */}
          {channelDisabled && !isArchived && !systemStopped && (
            <div className="p-4 rounded-lg bg-surface-2 border border-border">
              <div className="flex items-center gap-3">
                <span className="text-content-tertiary text-lg">○</span>
                <div>
                  <h3 className="text-sm font-semibold text-content-secondary">Channel Disabled</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">
                    Settings are read-only while the channel is disabled. Enable it from the dashboard first.
                  </p>
                </div>
              </div>
            </div>
          )}
          {/* Lockdown banner */}
          {systemStopped && (
            <div className="p-4 rounded-lg bg-status-error/10 border border-status-error/20">
              <div className="flex items-center gap-3">
                <span className="text-status-error text-lg">■</span>
                <div>
                  <h3 className="text-sm font-semibold text-status-error">System Stopped</h3>
                  <p className="text-xs text-content-tertiary mt-0.5">
                    Channel settings are locked during emergency stop.
                  </p>
                </div>
              </div>
            </div>
          )}
          {/* Basic Info */}
          <section className={cn('card p-5', locked && 'lockdown-frost')}>
            <h2 className="text-sm font-semibold text-content-primary mb-4">Basic Info</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Channel Name" value={form.channel_name}
                onChange={(v) => setForm({ ...form, channel_name: v })} disabled={!editMode} />
              <Field label="Niche" value={form.niche}
                onChange={(v) => setForm({ ...form, niche: v })} disabled={!editMode} />
              <div>
                <label className="block text-xs font-medium text-content-tertiary mb-1.5">Content Mode</label>
                <select
                  value={form.content_mode}
                  onChange={(e) => setForm({ ...form, content_mode: e.target.value })}
                  disabled={!editMode}
                  className="input w-full"
                >
                  <option value="short">Short Only</option>
                  <option value="long_form">Long Only</option>
                  <option value="both">Both</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-content-tertiary mb-1.5">Human Review</label>
                <select
                  value={form.human_review_required}
                  onChange={(e) => setForm({ ...form, human_review_required: e.target.value })}
                  disabled={!editMode}
                  className="input w-full"
                >
                  <option value="first_10">First 10 Videos</option>
                  <option value="always">Always</option>
                  <option value="never">Never</option>
                </select>
              </div>
            </div>
          </section>

          {/* Production Settings */}
          <section className={cn('card p-5', locked && 'lockdown-frost')}>
            <h2 className="text-sm font-semibold text-content-primary mb-4">Production Settings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <NumField label="Shorts / Week" value={form.videos_per_week_short}
                onChange={(v) => setForm({ ...form, videos_per_week_short: v })} disabled={!editMode} min={0} max={30} />
              <NumField label="Long Videos / Week" value={form.videos_per_week_long}
                onChange={(v) => setForm({ ...form, videos_per_week_long: v })} disabled={!editMode} min={0} max={10} />
              <NumField label="Short Duration (seconds)" value={form.short_form_duration}
                onChange={(v) => setForm({ ...form, short_form_duration: v })} disabled={!editMode} min={15} max={120} />
              <NumField label="Long Duration (seconds)" value={form.long_form_duration}
                onChange={(v) => setForm({ ...form, long_form_duration: v })} disabled={!editMode} min={120} max={1800} />
              <NumField label="Max Daily API Spend ($)" value={form.max_daily_api_spend}
                onChange={(v) => setForm({ ...form, max_daily_api_spend: v })} disabled={!editMode} min={0.5} max={100} step={0.5} />
            </div>
          </section>

          {/* Automation */}
          <section className={cn('card p-5', locked && 'lockdown-frost')}>
            <h2 className="text-sm font-semibold text-content-primary mb-4">Automation</h2>
            <div className="space-y-4">
              <ToggleField label="Auto-upload to YouTube" description="Automatically upload approved videos"
                checked={form.auto_upload} onChange={(v) => setForm({ ...form, auto_upload: v })} disabled={!editMode} />
              <ToggleField label="Cron Schedule" description="Automatically trigger production on schedule"
                checked={form.schedule_enabled} onChange={(v) => setForm({ ...form, schedule_enabled: v })} disabled={!editMode} />
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function Field({ label, value, onChange, disabled }: {
  label: string; value: string; onChange: (v: string) => void; disabled: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-content-tertiary mb-1.5">{label}</label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        disabled={disabled} className="input w-full" />
    </div>
  );
}

function NumField({ label, value, onChange, disabled, min, max, step = 1 }: {
  label: string; value: number; onChange: (v: number) => void; disabled: boolean;
  min?: number; max?: number; step?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-content-tertiary mb-1.5">{label}</label>
      <input type="number" value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        disabled={disabled} min={min} max={max} step={step}
        className="input w-full" />
    </div>
  );
}

function ToggleField({ label, description, checked, onChange, disabled }: {
  label: string; description: string; checked: boolean;
  onChange: (v: boolean) => void; disabled: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-content-primary">{label}</div>
        <div className="text-xs text-content-tertiary mt-0.5">{description}</div>
      </div>
      <button
        onClick={disabled ? undefined : () => onChange(!checked)}
        disabled={disabled}
        className={cn(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none',
          checked ? 'bg-accent' : 'bg-surface-3',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <span className={cn(
          'inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
          checked ? 'translate-x-[22px]' : 'translate-x-[3px]'
        )} />
      </button>
    </div>
  );
}
