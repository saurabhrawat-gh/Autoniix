'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';

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
        ...form,
        content_mode: form.content_modes.join(','),
      });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to create channel');
    } finally { setLoading(false); }
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Link href="/dashboard" className="btn-ghost !px-2 !py-1 !text-xs">← Back</Link>
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

      <form onSubmit={handleSubmit} className={cn('card p-6 space-y-5', systemStopped && 'opacity-60 pointer-events-none')}>
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
