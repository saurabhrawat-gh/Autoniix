'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Save } from 'lucide-react';
import { channelsApi } from '@/lib/api-v2';
import { Skeleton } from '@/lib/components/Skeleton';
import { AlertTriangle, ChevronLeft, RefreshCw } from '@/lib/components/Icon';

const TABS = ['Basics', 'Strategy', 'Voice', 'Visual', 'Pillars', 'References', 'Automation', 'Memory'] as const;

export default function ChannelDetail() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<typeof TABS[number]>('Basics');
  const [data, setData] = useState<any>(null);
  const [draft, setDraft] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await channelsApi.get(id);
      setData(r.data);
      setDraft({});
    } catch (e: any) {
      setError(e?.message || 'Failed to load channel');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);

  const save = async () => {
    setSaving(true);
    try { await channelsApi.patch(id, draft); await refresh(); } finally { setSaving(false); }
  };

  if (loading && !data) return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="max-w-5xl space-y-4">
        <Skeleton className="h-8 w-64 rounded" />
        <Skeleton className="h-4 w-48 rounded" />
        <Skeleton className="h-10 w-full rounded mt-4" />
        <Skeleton className="h-64 w-full rounded" />
      </div>
    </main>
  );

  if (error || !data) return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <Link href="/dashboard/channels" className="inline-flex items-center gap-1 text-xs text-content-tertiary hover:text-content-primary mb-4">
        <ChevronLeft size={13} /> Back to channels
      </Link>
      <div className="max-w-md mx-auto mt-12 rounded-md border border-red-500/30 bg-red-500/5 p-6 text-center">
        <AlertTriangle size={28} className="mx-auto text-red-500 mb-3" />
        <h2 className="text-base font-semibold text-content-primary mb-1">Failed to load channel</h2>
        <p className="text-sm text-content-tertiary mb-4">{error || `Channel "${id}" was not found or the backend returned an error.`}</p>
        <div className="flex gap-2 justify-center">
          <button onClick={refresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-white text-xs font-medium hover:opacity-90">
            <RefreshCw size={12} /> Retry
          </button>
          <Link href="/dashboard/channels"
            className="inline-flex items-center px-3 py-1.5 rounded-md border border-border text-xs text-content-secondary hover:bg-surface-2">
            Back to channels
          </Link>
        </div>
      </div>
    </main>
  );
  const c = data.channel;
  const get = (k: string) => draft[k] !== undefined ? draft[k] : c[k];
  const set = (k: string, v: any) => setDraft((d: any) => ({ ...d, [k]: v }));

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
    <div className="max-w-5xl">
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-2xl font-semibold">{c.channel_name}</h1>
        <span className="text-xs opacity-60">{c.channel_id}</span>
        <span className="ml-auto text-xs px-2 py-0.5 rounded bg-surface-2">{c.status}</span>
      </div>
      <div className="flex items-center gap-2 mb-6">
        <p className="text-sm opacity-70">{c.niche} · {c.sub_niche}</p>
        {c.content_mode && (
          <div className="flex items-center gap-1">
            {(c.content_mode === 'both' || c.content_mode === 'mixed' || c.content_mode === 'short') && (
              <span className="chip-short">Short</span>
            )}
            {(c.content_mode === 'both' || c.content_mode === 'mixed' || c.content_mode === 'long' || c.content_mode === 'long_form') && (
              <span className="chip-long">Long</span>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-border mb-5 overflow-x-auto">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={'px-3 py-2 text-sm border-b-2 -mb-px ' +
              (tab === t ? 'border-accent text-accent' : 'border-transparent opacity-70 hover:opacity-100')}>
            {t}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-surface-0 p-6 space-y-4">
        {tab === 'Basics' && (
          <Grid>
            <Inp label="Name"     value={get('channel_name')} onChange={(v: any) => set('channel_name', v)} />
            <Inp label="Niche"    value={get('niche')}        onChange={(v: any) => set('niche', v)} />
            <Inp label="Sub-niche" value={get('sub_niche')}    onChange={(v: any) => set('sub_niche', v)} />
            <Inp label="Platform" value={get('platform') || ''} onChange={(v: any) => set('platform', v)} />
            <Inp label="Handle"   value={get('handle') || ''}  onChange={(v: any) => set('handle', v)} />
            <Inp label="Language" value={get('primary_language') || ''} onChange={(v: any) => set('primary_language', v)} />
            <Inp label="Geography" value={get('geography') || ''} onChange={(v: any) => set('geography', v)} />
            <Inp label="Age group" value={get('target_age_group') || ''} onChange={(v: any) => set('target_age_group', v)} />
            <Inp label="Audience" wide value={get('target_audience') || ''} onChange={(v: any) => set('target_audience', v)} />
            <Inp label="Description" wide multiline value={get('description') || ''} onChange={(v: any) => set('description', v)} />
          </Grid>
        )}
        {tab === 'Strategy' && (
          <Grid>
            <Inp label="Content mode" value={get('content_mode')} onChange={(v: any) => set('content_mode', v)} />
            <Inp label="Tone" value={get('tone') || ''} onChange={(v: any) => set('tone', v)} />
            <Inp label="Brand personality" wide value={get('brand_personality') || ''} onChange={(v: any) => set('brand_personality', v)} />
            <Inp label="Mission" wide multiline value={get('mission') || ''} onChange={(v: any) => set('mission', v)} />
            <Inp label="Vision" wide multiline value={get('vision') || ''} onChange={(v: any) => set('vision', v)} />
          </Grid>
        )}
        {tab === 'Voice' && (
          <Grid>
            <Inp label="Narration style" value={get('narration_style') || ''} onChange={(v: any) => set('narration_style', v)} />
            <Inp label="Music style" value={get('music_style') || ''} onChange={(v: any) => set('music_style', v)} />
            <Inp label="Humor style" value={get('humor_style') || ''} onChange={(v: any) => set('humor_style', v)} />
            <Inp label="Pacing" value={get('pacing_style') || ''} onChange={(v: any) => set('pacing_style', v)} />
            <Inp label="ElevenLabs voice id" value={get('elevenlabs_voice_id') || ''} onChange={(v: any) => set('elevenlabs_voice_id', v)} />
            <Inp label="Emotion intensity" type="number" value={get('emotion_intensity') ?? 0} onChange={(v: any) => set('emotion_intensity', Number(v))} />
            <Inp label="Voice stability" type="number" value={get('voice_stability') ?? 0} onChange={(v: any) => set('voice_stability', Number(v))} />
            <Inp label="Voice similarity" type="number" value={get('voice_similarity') ?? 0} onChange={(v: any) => set('voice_similarity', Number(v))} />
            <Inp label="Voice style" type="number" value={get('voice_style') ?? 0} onChange={(v: any) => set('voice_style', Number(v))} />
          </Grid>
        )}
        {tab === 'Visual' && (
          <Grid>
            <Inp label="Thumbnail style" wide value={get('thumbnail_style') || ''} onChange={(v: any) => set('thumbnail_style', v)} />
            <Inp label="Typography" value={get('typography_preference') || ''} onChange={(v: any) => set('typography_preference', v)} />
            <Inp label="LUT preference" value={get('lut_preference') || ''} onChange={(v: any) => set('lut_preference', v)} />
            <Inp label="Transitions" value={get('transition_preference') || ''} onChange={(v: any) => set('transition_preference', v)} />
            <Inp label="Primary color" value={get('primary_color') || ''} onChange={(v: any) => set('primary_color', v)} />
            <Inp label="Secondary color" value={get('secondary_color') || ''} onChange={(v: any) => set('secondary_color', v)} />
            <Inp label="Meme intensity" type="number" value={get('meme_intensity') ?? 0} onChange={(v: any) => set('meme_intensity', Number(v))} />
          </Grid>
        )}
        {tab === 'Pillars' && (
          <PillarsTab data={data} channel_id={id} onChange={refresh} />
        )}
        {tab === 'References' && (
          <ReferencesTab data={data} channel_id={id} onChange={refresh} />
        )}
        {tab === 'Automation' && (
          <Grid>
            <Inp label="Auto upload" type="checkbox" value={get('auto_upload') ? 'true' : ''} onChange={(v: any) => set('auto_upload', !!v)} />
            <Inp label="Human review" value={get('human_review_required') || ''} onChange={(v: any) => set('human_review_required', v)} />
            <Inp label="Forced review ratio" type="number" value={get('human_review_ratio') ?? 0} onChange={(v: any) => set('human_review_ratio', Number(v))} />
            <Inp label="Review timeout (h)" type="number" value={get('review_timeout_hours') ?? 24} onChange={(v: any) => set('review_timeout_hours', Number(v))} />
            <Inp label="Daily API spend cap" type="number" value={get('max_daily_api_spend') ?? 0} onChange={(v: any) => set('max_daily_api_spend', Number(v))} />
            <Inp label="Videos / week (short)" type="number" value={get('videos_per_week_short') ?? 0} onChange={(v: any) => set('videos_per_week_short', Number(v))} />
            <Inp label="Videos / week (long)" type="number" value={get('videos_per_week_long') ?? 0} onChange={(v: any) => set('videos_per_week_long', Number(v))} />
            <Inp label="Short duration (s)" type="number" value={get('short_form_duration') ?? 60} onChange={(v: any) => set('short_form_duration', Number(v))} />
            <Inp label="Long duration (s)" type="number" value={get('long_form_duration') ?? 600} onChange={(v: any) => set('long_form_duration', Number(v))} />
          </Grid>
        )}
        {tab === 'Memory' && (
          <div>
            <h3 className="text-sm font-medium mb-2">Recent memory ({data.memory.length})</h3>
            {data.memory.length === 0 && <div className="text-xs opacity-60">No memory yet. Reviews + outcomes will populate this.</div>}
            <ul className="space-y-2">
              {data.memory.map((m: any) => (
                <li key={m.id} className="text-xs rounded border border-border p-2">
                  <div className="font-mono opacity-60">{m.memory_type} · {new Date(m.created_at).toLocaleString()}</div>
                  <pre className="whitespace-pre-wrap mt-1">{JSON.stringify(m.content, null, 2)}</pre>
                </li>
              ))}
            </ul>
          </div>
        )}

        {Object.keys(draft).length > 0 && (
          <div className="pt-4 border-t border-border flex items-center gap-3">
            <span className="text-xs opacity-70">{Object.keys(draft).length} unsaved change(s)</span>
            <button onClick={() => setDraft({})} className="text-xs opacity-60 hover:opacity-100">Discard</button>
            <button onClick={save} disabled={saving}
              className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-white text-sm hover:bg-accent disabled:opacity-40">
              <Save size={14} /> {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        )}
      </div>
    </div>
    </main>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>;
}

function Inp({ label, value, onChange, type = 'text', wide, multiline }: any) {
  const cls = 'w-full px-3 py-1.5 rounded-md bg-surface-1 border border-border text-sm';
  return (
    <label className={'block ' + (wide ? 'md:col-span-2' : '')}>
      <div className="text-xs uppercase tracking-wide opacity-70 mb-1">{label}</div>
      {type === 'checkbox' ? (
        <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} />
      ) : multiline ? (
        <textarea className={cls + ' h-20'} value={value ?? ''} onChange={e => onChange(e.target.value)} />
      ) : (
        <input className={cls} type={type} value={value ?? ''} onChange={e => onChange(e.target.value)} />
      )}
    </label>
  );
}

function PillarsTab({ data, channel_id, onChange }: any) {
  const [draftName, setDraftName] = useState('');
  const [draftDesc, setDraftDesc] = useState('');
  return (
    <div>
      <h3 className="text-sm font-medium mb-2">Pillars ({data.pillars.length})</h3>
      <ul className="space-y-2 mb-4">
        {data.pillars.map((p: any) => (
          <li key={p.id} className="flex items-start gap-2 text-sm border border-border rounded p-2">
            <div className="flex-1">
              <div className="font-medium">{p.name}</div>
              <div className="text-xs opacity-60">{p.description}</div>
            </div>
            <button onClick={() => channelsApi.deletePillar(channel_id, p.id).then(onChange)}
              className="text-xs text-red-500 opacity-60 hover:opacity-100">Remove</button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <input className="px-2 py-1.5 rounded-md bg-surface-1 border border-border text-sm" placeholder="Pillar name" value={draftName} onChange={e => setDraftName(e.target.value)} />
        <input className="flex-1 px-2 py-1.5 rounded-md bg-surface-1 border border-border text-sm" placeholder="Description" value={draftDesc} onChange={e => setDraftDesc(e.target.value)} />
        <button onClick={async () => {
          if (!draftName) return;
          await channelsApi.addPillar(channel_id, { name: draftName, description: draftDesc, weight: 1, examples: [], position: 0 });
          setDraftName(''); setDraftDesc(''); onChange();
        }} className="px-3 py-1.5 rounded-md bg-accent text-white text-sm">Add</button>
      </div>
    </div>
  );
}

function ReferencesTab({ data, channel_id, onChange }: any) {
  const [kind, setKind] = useState('url');
  const [label, setLabel] = useState('');
  const [uri, setUri] = useState('');
  return (
    <div>
      <h3 className="text-sm font-medium mb-2">References ({data.references.length})</h3>
      <ul className="space-y-2 mb-4">
        {data.references.map((r: any) => (
          <li key={r.id} className="flex items-start gap-2 text-sm border border-border rounded p-2">
            <span className="text-[10px] uppercase opacity-60">{r.kind}</span>
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate">{r.label || r.uri}</div>
              <div className="text-xs opacity-60 truncate">{r.uri}</div>
            </div>
            <button onClick={() => channelsApi.deleteReference(channel_id, r.id).then(onChange)}
              className="text-xs text-red-500 opacity-60 hover:opacity-100">Remove</button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <select className="px-2 py-1.5 rounded-md bg-surface-1 border border-border text-sm" value={kind} onChange={e => setKind(e.target.value)}>
          {['url','pdf','video','gdrive','notion','asset_pack','logo','lut','sfx','music'].map(k => <option key={k}>{k}</option>)}
        </select>
        <input className="px-2 py-1.5 rounded-md bg-surface-1 border border-border text-sm" placeholder="Label" value={label} onChange={e => setLabel(e.target.value)} />
        <input className="flex-1 px-2 py-1.5 rounded-md bg-surface-1 border border-border text-sm" placeholder="URL or s3 key" value={uri} onChange={e => setUri(e.target.value)} />
        <button onClick={async () => {
          if (!uri) return;
          await channelsApi.addReference(channel_id, { kind, label, uri });
          setLabel(''); setUri(''); onChange();
        }} className="px-3 py-1.5 rounded-md bg-accent text-white text-sm">Add</button>
      </div>
    </div>
  );
}
