'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { reviewApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import {
  Check, X, RotateCw, Send, Wand2, FileText, ImageIcon, Type,
  Save, ArrowLeft, Mic, Layers, Film,
} from '@/lib/components/Icon';

const ARTIFACTS = [
  { key: 'script',    label: 'Script',    icon: FileText },
  { key: 'thumbnail', label: 'Thumbnail', icon: ImageIcon },
  { key: 'title',     label: 'Title / SEO', icon: Type },
] as const;

const SCRIPT_VARIANTS = [
  { key: 'full',      label: 'Full Script', icon: FileText },
  { key: 'voiceover', label: 'Voiceover',   icon: Mic },
  { key: 'assets',    label: 'Assets',      icon: Layers },
  { key: 'direction', label: 'Direction',   icon: Film },
] as const;

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [tab, setTab] = useState<typeof ARTIFACTS[number]['key']>('script');
  const [scriptVariant, setScriptVariant] = useState('full');
  const [comment, setComment] = useState('');
  const [decisionModal, setDecisionModal] = useState<{open: boolean; decision: string}>({open: false, decision: ''});
  const [decisionNote, setDecisionNote] = useState('');
  const [savingDecision, setSavingDecision] = useState(false);
  const { showToast } = useToast();

  const refresh = () => {
    setLoadState(prev => prev === 'ready' ? 'ready' : 'loading');
    return reviewApi.get(id)
      .then(r => { setData(r.data); setLoadState('ready'); })
      .catch(err => {
        setData(null);
        setErrorMsg(err?.message || 'Failed to load review');
        setLoadState('error');
      });
  };
  useEffect(() => { refresh(); }, [id]);

  const openDecision = (decision: string) => {
    setDecisionNote('');
    setDecisionModal({open: true, decision});
  };

  const confirmDecision = async () => {
    setSavingDecision(true);
    try {
      if (!data?.session) await reviewApi.open(id);
      await reviewApi.decide(id, decisionModal.decision, decisionNote || undefined);
      setDecisionModal({open: false, decision: ''});
      refresh();
      showToast(`Marked as ${decisionModal.decision}`, 'success');
    } catch (e: any) {
      showToast(e.message || 'Failed to save decision', 'error');
    } finally {
      setSavingDecision(false);
    }
  };

  const sendComment = async () => {
    if (!comment.trim()) return;
    if (!data?.session) await reviewApi.open(id);
    await reviewApi.comment(id, { artifact: tab, body: comment });
    setComment('');
    refresh();
  };

  if (loadState === 'loading') return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="mb-4">
        <Link href="/dashboard/content" className="text-xs text-content-tertiary hover:text-accent flex items-center gap-1 transition-colors">
          <ArrowLeft size={12} /> Back to content
        </Link>
      </div>
      <div className="text-content-tertiary text-sm">Loading…</div>
    </main>
  );

  if (loadState === 'error' || !data) return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="mb-4">
        <Link href="/dashboard/content" className="text-xs text-content-tertiary hover:text-accent flex items-center gap-1 transition-colors">
          <ArrowLeft size={12} /> Back to content
        </Link>
      </div>
      <div className="rounded-xl border border-border bg-surface-0 p-8 text-center">
        <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-red-500/10 text-red-500 flex items-center justify-center">
          <X size={20} />
        </div>
        <h2 className="text-base font-semibold text-content-primary mb-1">Review not available</h2>
        <p className="text-sm text-content-tertiary mb-4">
          {errorMsg.includes('not found') || errorMsg.includes('404')
            ? `Video "${id}" no longer exists. The underlying record may have been deleted.`
            : errorMsg}
        </p>
        <div className="flex items-center justify-center gap-2">
          <button onClick={refresh} className="btn-secondary">Retry</button>
          <Link href="/dashboard/content" className="btn-primary">Back to content</Link>
        </div>
      </div>
    </main>
  );

  const v = data.video;
  const session = data.session;

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1500px] mx-auto w-full">
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link href="/dashboard/content" className="text-xs text-content-tertiary hover:text-accent flex items-center gap-1 transition-colors">
          <ArrowLeft size={12} /> Back to content
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_300px] gap-4">
        {/* Left rail — artifacts (mirrors sidebar nav active state) */}
        <aside className="rounded-xl border border-border bg-surface-0 p-3 flex flex-col">
          <div className="px-2.5 mb-2 text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">Artifacts</div>
          <ul className="space-y-0.5">
            {ARTIFACTS.map(a => (
              <li key={a.key}>
                <button onClick={() => setTab(a.key)}
                  className={cn('w-full text-left flex items-center gap-3 px-2.5 py-2 rounded-md text-sm font-medium transition-colors',
                    tab === a.key
                      ? 'bg-accent/10 text-accent'
                      : 'text-content-secondary hover:bg-surface-2 hover:text-content-primary')}>
                  <a.icon size={16} className="shrink-0" />{a.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-auto pt-3 border-t border-border text-[11px] text-content-tertiary">
            {data.script_versions.length} script version{data.script_versions.length !== 1 ? 's' : ''} · {data.thumbnail_versions.length} thumbnail{data.thumbnail_versions.length !== 1 ? 's' : ''}
          </div>
        </aside>

        {/* Center — main editor */}
        <div className="rounded-xl border border-border bg-surface-0 p-5 min-h-[640px] flex flex-col">
          {/* Header */}
          <div className="flex items-start gap-3 mb-5 pb-4 border-b border-border">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className={v.content_mode === 'short' ? 'chip-short' : 'chip-long'}>
                  {v.content_mode === 'short' ? 'Short' : 'Long'}
                </span>
                <span className="text-[11px] text-content-tertiary">{v.content_id}</span>
              </div>
              <h1 className="font-semibold text-lg text-content-primary truncate">{v.title || v.topic || v.content_id}</h1>
              <div className="text-xs text-content-tertiary truncate mt-0.5">
                {v.channel_id} · {v.status}
                {v.authenticity_score != null && ` · Score ${Number(v.authenticity_score).toFixed(2)}`}
              </div>
            </div>
            {session?.state && (
              <span className={cn('text-[10px] uppercase px-2.5 py-1 rounded-md font-medium shrink-0',
                session.state === 'approved' ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' :
                session.state === 'rejected' ? 'bg-red-500/15 text-red-600 dark:text-red-400' :
                session.state === 'needs_edits' ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400' :
                'bg-accent/15 text-accent'
              )}>
                {session.state}
              </span>
            )}
          </div>

          {/* Content pane */}
          <div className="flex-1 min-h-0">
            {tab === 'script' && (
              <ScriptPane data={data} videoId={id} variant={scriptVariant}
                onVariantChange={setScriptVariant} onChange={refresh} />
            )}
            {tab === 'thumbnail' && <ThumbPane data={data} videoId={id} onChange={refresh} />}
            {tab === 'title' && <TitlePane data={data} videoId={id} onChange={refresh} />}
          </div>

          {/* Action buttons — match nav menu style: rounded-md, tonal backgrounds */}
          <div className="mt-6 pt-4 border-t border-border flex items-center justify-end gap-2">
            <DecisionButton onClick={() => openDecision('rejected')} icon={X} label="Reject" tone="red" />
            <DecisionButton onClick={() => openDecision('needs_edits')} icon={RotateCw} label="Request edits" tone="amber" />
            <DecisionButton onClick={() => openDecision('approved')} icon={Check} label="Approve" tone="accent" primary />
          </div>
        </div>

        {/* Right — comments */}
        <aside className="rounded-xl border border-border bg-surface-0 p-4 flex flex-col h-full max-h-[calc(100vh-160px)]">
          <div className="text-[11px] uppercase tracking-wider text-content-tertiary font-semibold mb-3">Comments ({data.comments.length})</div>
          <div className="flex-1 overflow-y-auto scrollbar-hide space-y-3 mb-3 pr-1">
            {data.comments.length === 0 && <div className="text-xs text-content-tertiary py-4 text-center">No comments yet.</div>}
            {data.comments.map((c: any) => (
              <div key={c.id} className="text-xs bg-surface-1 rounded p-3 border border-border/50">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium uppercase',
                    c.artifact === 'script' ? 'bg-accent/10 text-accent' :
                    c.artifact === 'thumbnail' ? 'bg-secondary/10 text-secondary' :
                    'bg-surface-2 text-content-tertiary'
                  )}>{c.artifact}</span>
                  <span className="text-content-tertiary text-[10px] ml-auto">{new Date(c.created_at).toLocaleString()}</span>
                </div>
                <div className="text-content-secondary leading-relaxed">{c.body}</div>
              </div>
            ))}
          </div>
          <div className="shrink-0 flex gap-1.5 pt-3 border-t border-border">
            <input value={comment} onChange={e => setComment(e.target.value)} placeholder={`Comment on ${tab}…`}
              className="flex-1 px-3 py-2 rounded-md bg-surface-1 border border-border text-xs text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent/50"
              onKeyDown={e => e.key === 'Enter' && sendComment()} />
            <button onClick={sendComment} disabled={!comment.trim()}
              className="w-9 h-9 shrink-0 inline-flex items-center justify-center rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Send comment">
              <Send size={13}/>
            </button>
          </div>
        </aside>
      </div>

      {/* Decision Modal */}
      {decisionModal.open && (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in" onClick={() => setDecisionModal({open: false, decision: ''})}>
          <div className="w-full max-w-md bg-surface-0 border border-border rounded-xl shadow-elevated p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-2">
              <div className={cn('w-9 h-9 rounded-md flex items-center justify-center shrink-0',
                decisionModal.decision === 'approved' ? 'bg-emerald-500/10 text-emerald-500' :
                decisionModal.decision === 'rejected' ? 'bg-red-500/10 text-red-500' :
                'bg-amber-500/10 text-amber-500'
              )}>
                {decisionModal.decision === 'approved' ? <Check size={16} /> :
                 decisionModal.decision === 'rejected' ? <X size={16} /> : <RotateCw size={16} />}
              </div>
              <h3 className="text-base font-semibold text-content-primary">
                {decisionModal.decision === 'approved' ? 'Approve content' :
                 decisionModal.decision === 'needs_edits' ? 'Request edits' : 'Reject content'}
              </h3>
            </div>
            <p className="text-xs text-content-tertiary mb-4 ml-12">
              {decisionModal.decision === 'approved' ? 'This content will be marked as approved and queued for delivery.' :
               decisionModal.decision === 'needs_edits' ? 'Add a note describing what needs to be changed.' : 'This content will be marked as rejected and archived.'}
            </p>
            <textarea
              value={decisionNote}
              onChange={e => setDecisionNote(e.target.value)}
              placeholder={decisionModal.decision === 'needs_edits' ? 'What needs to change?' : 'Optional note…'}
              className="w-full h-24 px-3 py-2 rounded-md bg-surface-1 border border-border text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent/50 resize-none mb-4"
            />
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setDecisionModal({open: false, decision: ''})} className="btn-ghost">Cancel</button>
              <button onClick={confirmDecision} disabled={savingDecision}
                className={cn('inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium text-white transition-colors disabled:opacity-50',
                  decisionModal.decision === 'approved' ? 'bg-emerald-500 hover:bg-emerald-600' :
                  decisionModal.decision === 'rejected' ? 'bg-red-500 hover:bg-red-600' :
                  'bg-amber-500 hover:bg-amber-600'
                )}>
                {savingDecision ? 'Saving…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function DecisionButton({ onClick, icon: Icon, label, tone, primary }: { onClick: () => void; icon: any; label: string; tone: 'accent' | 'amber' | 'red'; primary?: boolean }) {
  const toneMap: Record<string, string> = {
    accent: primary
      ? 'bg-accent text-white hover:bg-accent-hover'
      : 'bg-accent/10 text-accent hover:bg-accent/15',
    amber:  'bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/20',
    red:    'bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-500/20',
  };
  return (
    <button onClick={onClick}
      className={cn('inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40', toneMap[tone])}>
      <Icon size={14}/>{label}
    </button>
  );
}

function ScriptPane({ data, videoId, variant, onVariantChange, onChange }: any) {
  const versions = data.script_versions;
  const latest = versions[0];
  const [body, setBody] = useState<string>(() => latest ? JSON.stringify(latest.content, null, 2) : '');
  const [kind, setKind] = useState<'full'|'section'|'hook'|'shorten'|'expand'|'tone'>('full');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await reviewApi.editScript(videoId, { kind, body, variant });
      onChange();
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3 h-full flex flex-col">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="inline-flex items-center bg-surface-1 rounded-md p-1">
          {SCRIPT_VARIANTS.map(sv => (
            <button key={sv.key} onClick={() => onVariantChange(sv.key)}
              className={cn('inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                variant === sv.key
                  ? 'bg-accent/10 text-accent'
                  : 'text-content-tertiary hover:text-content-primary')}>
              <sv.icon size={12} />{sv.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs font-mono text-content-tertiary">v{latest?.version || 1}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-content-tertiary">Edit kind</span>
        <select value={kind} onChange={e => setKind(e.target.value as any)}
          className="px-2 py-1 text-xs rounded border border-border bg-surface-1 text-content-primary focus:outline-none focus:border-accent/50">
          {['full','section','hook','shorten','expand','tone','emotion','repetition'].map(k => <option key={k}>{k}</option>)}
        </select>
      </div>
      <textarea value={body} onChange={e => setBody(e.target.value)}
        className="flex-1 min-h-0 w-full px-3 py-2 rounded bg-surface-1 border border-border font-mono text-xs resize-none focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30" />
      <div className="flex gap-2 pt-2">
        <button onClick={submit} disabled={busy} className="btn-primary">
          <Wand2 size={13}/> {busy ? 'Saving…' : 'Save as new version'}
        </button>
      </div>
      {versions.length > 1 && (
        <div className="mt-2 pt-2 border-t border-border">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2">Version history</div>
          <ul className="space-y-1">
            {versions.map((v: any) => (
              <li key={v.id} className="text-xs flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-1 transition-colors">
                <span className="font-mono text-content-tertiary">v{v.version}</span>
                <span className="text-content-secondary">{v.source}</span>
                <span className="text-content-tertiary ml-auto">{new Date(v.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ThumbPane({ data, videoId, onChange }: any) {
  const [nudge, setNudge] = useState('');
  const regen = async () => {
    await reviewApi.regenThumb(videoId, nudge || undefined);
    onChange();
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {(data.thumbnail_versions || []).map((t: any) => (
          <div key={t.id} className="rounded border border-border p-2 hover:border-accent/30 transition-colors cursor-pointer">
            <div className="aspect-video bg-surface-2 rounded mb-1.5 flex items-center justify-center">
              <span className="text-[10px] text-content-tertiary">v{t.version}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-content-tertiary">v{t.version}</span>
              {t.ctr_pred && <span className="font-mono text-accent">CTR {Number(t.ctr_pred).toFixed(2)}</span>}
            </div>
          </div>
        ))}
        {data.thumbnail_versions?.length === 0 && <div className="text-xs text-content-tertiary col-span-full">No thumbnail variants yet.</div>}
      </div>
      <div className="flex gap-2 pt-2 border-t border-border">
        <input value={nudge} onChange={e => setNudge(e.target.value)} placeholder="Optional prompt nudge…"
          className="flex-1 px-3 py-1.5 rounded bg-surface-1 border border-border text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30" />
        <button onClick={regen}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-accent text-white text-sm font-medium hover:opacity-90 transition-opacity">
          <Wand2 size={12}/> Regenerate
        </button>
      </div>
    </div>
  );
}

function TitlePane({ data, videoId, onChange }: any) {
  const v = data.video;
  const { showToast } = useToast();
  const [title, setTitle] = useState(v.title || '');
  const [hook, setHook] = useState(v.selected_hook || '');
  const [topic, setTopic] = useState(v.topic || '');
  const [saving, setSaving] = useState(false);

  const hasChanges = title !== (v.title || '') || hook !== (v.selected_hook || '') || topic !== (v.topic || '');

  const save = async () => {
    if (!hasChanges) return;
    setSaving(true);
    try {
      await reviewApi.updateTitle(videoId, { title, hook, topic });
      showToast('Title updated', 'success');
      onChange();
    } catch (e: any) {
      showToast(e.message || 'Failed to update title', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Title</label>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          className="w-full px-3 py-2.5 rounded bg-surface-1 border border-border text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30"
        />
      </div>
      <div>
        <label className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Hook</label>
        <input
          value={hook}
          onChange={e => setHook(e.target.value)}
          className="w-full px-3 py-2.5 rounded bg-surface-1 border border-border text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30"
        />
      </div>
      <div>
        <label className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Topic</label>
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          className="w-full px-3 py-2.5 rounded bg-surface-1 border border-border text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent/30"
        />
      </div>
      <div className="pt-2">
        <button onClick={save} disabled={!hasChanges || saving}
          className={cn(hasChanges && !saving ? 'btn-primary' : 'btn-secondary cursor-not-allowed opacity-60')}>
          <Save size={14} /> {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  );
}
