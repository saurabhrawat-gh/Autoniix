'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { Save, Trash2 } from 'lucide-react';
import { channelsApi, authApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { Skeleton } from '@/lib/components/Skeleton';
import { AlertTriangle, ChevronLeft, RefreshCw } from '@/lib/components/Icon';
import {
  Button,
  Input,
  Textarea,
  Checkbox,
  Label as FieldLabel,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/lib/ui';
import { cn } from '@/lib/utils';

import ProvidersTab from './ProvidersTab';

const TABS = ['Basics', 'Strategy', 'Voice', 'Visual', 'Pillars', 'References', 'Providers', 'Automation', 'Memory'] as const;

export default function ChannelDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { showToast } = useToast();
  const [tab, setTab] = useState<typeof TABS[number]>('Basics');
  const [data, setData] = useState<any>(null);
  const [draft, setDraft] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // AE-290 — Owner-gated Danger Zone state
  const [myRole, setMyRole] = useState<string>('viewer');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, me] = await Promise.all([
        channelsApi.get(id),
        authApi.me().catch(() => null),
      ]);
      setData(r.data);
      setDraft({});
      setMyRole((me as any)?.data?.role || 'viewer');
    } catch (e: any) {
      setError(e?.message || 'Failed to load channel');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);

  const closeDeleteModal = () => {
    if (deleteBusy) return;
    setShowDeleteModal(false);
    setDeleteConfirm('');
    setDeletePassword('');
    setDeleteErr(null);
  };

  const handleDelete = async () => {
    if (deleteConfirm !== 'delete' || !deletePassword) return;
    setDeleteBusy(true);
    setDeleteErr(null);
    try {
      await channelsApi.delete(id, { confirmation: 'delete', password: deletePassword });
      showToast('Channel deleted', 'success');
      router.push('/dashboard/channels');
    } catch (e: any) {
      // Server returns {detail: {code, message?}} for 4xx; api wrapper may surface as e.message
      const code = e?.detail?.code || e?.code;
      const msg =
        code === 'wrong_password'   ? 'Incorrect password.' :
        code === 'has_videos'       ? (e?.detail?.message || 'Cannot delete a channel that has published videos. Archive instead.') :
        code === 'channel_not_found'? 'Channel not found in your workspace.' :
        (e?.message || 'Failed to delete channel');
      setDeleteErr(msg);
      setDeleteBusy(false);
    }
  };

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
      <div className="max-w-md mx-auto mt-12 rounded-md border border-status-error/30 bg-status-error/5 p-6 text-center">
        <AlertTriangle size={28} className="mx-auto text-status-error mb-3" />
        <h2 className="text-base font-semibold text-content-primary mb-1">Failed to load channel</h2>
        <p className="text-sm text-content-tertiary mb-4">{error || `Channel "${id}" was not found or the backend returned an error.`}</p>
        <div className="flex gap-2 justify-center">
          <Button size="sm" onClick={refresh} leftIcon={<RefreshCw size={12} />}>Retry</Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/dashboard/channels">Back to channels</Link>
          </Button>
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
          <Button
            key={t}
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setTab(t)}
            className={cn(
              'px-3 py-2 text-sm border-b-2 -mb-px rounded-none h-auto',
              tab === t
                ? 'border-accent text-accent hover:text-accent'
                : 'border-transparent opacity-70 hover:opacity-100',
            )}
          >
            {t}
          </Button>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-surface-0 p-6 space-y-4">
        {tab === 'Basics' && (
          <Grid>
            <Inp label="Name"     value={get('channel_name')} onChange={(v: any) => set('channel_name', v)} />
            <Inp label="Niche"    value={get('niche')}        onChange={(v: any) => set('niche', v)} />
            <Inp label="Sub-niche" value={get('sub_niche')}    onChange={(v: any) => set('sub_niche', v)} />
            <div className="block">
              <FieldLabel className="text-xs uppercase tracking-wide opacity-70 mb-1 block">Platform</FieldLabel>
              <div className="inline-flex items-center gap-1.5 h-9 px-3 rounded-md border border-border bg-surface-2 text-sm font-medium">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#FF0000' }} aria-hidden />
                YouTube
              </div>
              <p className="text-xs opacity-60 mt-1">Autoniix v1 supports YouTube only.</p>
            </div>
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
        {tab === 'Providers' && (
          <ProvidersTab channelId={id} />
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
            <Button variant="ghost" size="sm" onClick={() => setDraft({})}>Discard</Button>
            <Button onClick={save} disabled={saving} loading={saving} leftIcon={<Save size={14} />} className="ml-auto">
              {saving ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        )}
      </div>

      {/* AE-290 — Danger Zone (owner only) */}
      {myRole === 'owner' && (
        <section className="mt-6 border border-status-error/30 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3 bg-status-error/5">
            <Trash2 size={15} className="text-status-error" />
            <h2 className="text-sm font-semibold text-status-error">Danger Zone</h2>
          </div>
          <div className="px-5 py-4 space-y-3">
            <p className="text-sm text-content-secondary">
              <strong>Permanently delete this channel.</strong> This removes the channel
              along with its pillars, references, topic rules, memory entries, projects,
              series, and unlinks any provider credentials. Published videos are kept and
              detached. <strong>This action cannot be undone.</strong>
            </p>
            <Button
              variant="outline"
              className="text-status-error border-status-error/40 hover:bg-status-error/10"
              onClick={() => setShowDeleteModal(true)}
              leftIcon={<Trash2 size={14} />}
            >
              Delete channel permanently
            </Button>
          </div>
        </section>
      )}
    </div>

    {/* Delete confirmation modal */}
    {showDeleteModal && (
      <div
        className="fixed inset-0 z-[200] bg-black/60 flex items-center justify-center px-4"
        onClick={closeDeleteModal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-channel-title"
      >
        <div
          className="bg-surface-0 border border-border rounded-xl shadow-elevated max-w-md w-full p-6 space-y-4"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex items-center gap-2">
            <Trash2 size={18} className="text-status-error" />
            <h3 id="delete-channel-title" className="text-base font-semibold text-status-error">
              Delete channel
            </h3>
          </div>
          <div className="text-sm text-content-secondary space-y-2">
            <p>
              You are about to <strong>permanently delete</strong>{' '}
              <span className="font-mono text-content-primary">{data?.channel?.channel_name || id}</span>.
            </p>
            <p>The following will be deleted:</p>
            <ul className="list-disc list-inside text-xs space-y-0.5 pl-1">
              <li>Channel record + brand profile + pillars + references</li>
              <li>Topic rules + memory entries</li>
              <li>Projects + series tied to this channel</li>
              <li>Provider credential channel scope (set to workspace)</li>
            </ul>
            <p className="text-xs">
              Published videos will <strong>not</strong> be deleted. You must archive videos
              or migrate them before this delete will succeed.
            </p>
          </div>
          {deleteErr && (
            <div className="text-sm text-status-error bg-status-error/10 border border-status-error/20 rounded-lg px-3 py-2">
              {deleteErr}
            </div>
          )}
          {/*
            AE-290 bug fix — block browser/password-manager autofill on this
            destructive form. Hidden decoy username+password inputs sit BEFORE
            the real fields so 1Password/LastPass/Chrome consume them instead
            of filling the real ones. Real fields use obscure names + ignore
            attrs + autoComplete=new-password.
          */}
          <input
            type="text"
            name="username"
            autoComplete="username"
            tabIndex={-1}
            aria-hidden="true"
            style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
            readOnly
          />
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            tabIndex={-1}
            aria-hidden="true"
            style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
            readOnly
          />
          <div className="space-y-1.5">
            <FieldLabel htmlFor="delete-confirm-input" className="text-xs">
              Type <span className="font-mono font-semibold">delete</span> to confirm
            </FieldLabel>
            <Input
              id="delete-confirm-input"
              name="delete-confirmation-phrase"
              autoComplete="off"
              data-1p-ignore="true"
              data-lpignore="true"
              data-form-type="other"
              value={deleteConfirm}
              onChange={e => setDeleteConfirm(e.target.value)}
              placeholder="delete"
              disabled={deleteBusy}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel htmlFor="delete-pw-input" className="text-xs">
              Enter your account password
            </FieldLabel>
            <Input
              id="delete-pw-input"
              name="delete-channel-verify"
              type="password"
              autoComplete="new-password"
              data-1p-ignore="true"
              data-lpignore="true"
              data-form-type="other"
              value={deletePassword}
              onChange={e => setDeletePassword(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleDelete(); }}
              disabled={deleteBusy}
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={closeDeleteModal} disabled={deleteBusy}>
              Cancel
            </Button>
            <Button
              variant="outline"
              className="text-status-error border-status-error/40 hover:bg-status-error/10"
              onClick={handleDelete}
              disabled={deleteConfirm !== 'delete' || !deletePassword || deleteBusy}
              loading={deleteBusy}
              leftIcon={<Trash2 size={14} />}
            >
              {deleteBusy ? 'Deleting…' : 'Delete forever'}
            </Button>
          </div>
        </div>
      </div>
    )}
    </main>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>;
}

function Inp({ label, value, onChange, type = 'text', wide, multiline }: any) {
  return (
    <div className={'block ' + (wide ? 'md:col-span-2' : '')}>
      <FieldLabel className="text-xs uppercase tracking-wide opacity-70 mb-1 block">{label}</FieldLabel>
      {type === 'checkbox' ? (
        <Checkbox checked={!!value} onCheckedChange={(v) => onChange(!!v)} />
      ) : multiline ? (
        <Textarea value={value ?? ''} onChange={e => onChange(e.target.value)} className="min-h-[80px]" />
      ) : (
        <Input type={type} value={value ?? ''} onChange={e => onChange(e.target.value)} />
      )}
    </div>
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
            <Button variant="ghost" size="sm" className="text-status-error hover:text-status-error"
              onClick={() => channelsApi.deletePillar(channel_id, p.id).then(onChange)}
            >Remove</Button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Input placeholder="Pillar name" value={draftName} onChange={e => setDraftName(e.target.value)} className="max-w-xs" />
        <Input placeholder="Description" value={draftDesc} onChange={e => setDraftDesc(e.target.value)} className="flex-1" />
        <Button onClick={async () => {
          if (!draftName) return;
          await channelsApi.addPillar(channel_id, { name: draftName, description: draftDesc, weight: 1, examples: [], position: 0 });
          setDraftName(''); setDraftDesc(''); onChange();
        }}>Add</Button>
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
            <Button variant="ghost" size="sm" className="text-status-error hover:text-status-error"
              onClick={() => channelsApi.deleteReference(channel_id, r.id).then(onChange)}
            >Remove</Button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <div className="min-w-[140px]">
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {['url','pdf','video','gdrive','notion','asset_pack','logo','lut','sfx','music'].map(k => (
                <SelectItem key={k} value={k}>{k}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Input placeholder="Label" value={label} onChange={e => setLabel(e.target.value)} className="max-w-[160px]" />
        <Input placeholder="URL or s3 key" value={uri} onChange={e => setUri(e.target.value)} className="flex-1" />
        <Button onClick={async () => {
          if (!uri) return;
          await channelsApi.addReference(channel_id, { kind, label, uri });
          setLabel(''); setUri(''); onChange();
        }}>Add</Button>
      </div>
    </div>
  );
}
