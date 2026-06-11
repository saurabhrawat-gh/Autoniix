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
import {
  Button,
  Input,
  Textarea,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseButton,
  DialogTitle,
  DialogDescription,
  Label as FieldLabel,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/lib/ui';

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
        <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-status-error/10 text-status-error flex items-center justify-center">
          <X size={20} />
        </div>
        <h2 className="text-base font-semibold text-content-primary mb-1">Review not available</h2>
        <p className="text-sm text-content-tertiary mb-4">
          {errorMsg.includes('not found') || errorMsg.includes('404')
            ? `Video "${id}" no longer exists. The underlying record may have been deleted.`
            : errorMsg}
        </p>
        <div className="flex items-center justify-center gap-2">
          <Button variant="secondary" size="sm" onClick={refresh}>Retry</Button>
          <Button asChild size="sm">
            <Link href="/dashboard/content">Back to content</Link>
          </Button>
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
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setTab(a.key)}
                  className={cn('w-full justify-start gap-3 px-2.5 py-2 h-auto text-sm font-medium',
                    tab === a.key
                      ? 'bg-accent/10 text-accent hover:bg-accent/15'
                      : 'text-content-secondary hover:bg-surface-2 hover:text-content-primary')}>
                  <a.icon size={16} className="shrink-0" />{a.label}
                </Button>
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
                session.state === 'approved' ? 'bg-status-success/15 text-status-success' :
                session.state === 'rejected' ? 'bg-status-error/15 text-status-error' :
                session.state === 'needs_edits' ? 'bg-status-warning/15 text-status-warning' :
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
            <Input value={comment} onChange={e => setComment(e.target.value)} placeholder={`Comment on ${tab}…`}
              className="flex-1 text-xs"
              onKeyDown={e => e.key === 'Enter' && sendComment()} />
            <Button
              type="button"
              size="icon"
              onClick={sendComment}
              disabled={!comment.trim()}
              aria-label="Send comment"
              className="shrink-0"
            >
              <Send size={13}/>
            </Button>
          </div>
        </aside>
      </div>

      {/* Decision Modal */}
      <Dialog open={decisionModal.open} onOpenChange={(o) => { if (!o) setDecisionModal({open: false, decision: ''}); }}>
        <DialogContent size="sm">
          <DialogHeader>
            <div>
              <DialogTitle>
                {decisionModal.decision === 'approved' ? 'Approve content?' :
                 decisionModal.decision === 'needs_edits' ? 'Request edits' : 'Reject content'}
              </DialogTitle>
              <DialogDescription>
                {decisionModal.decision === 'approved' ? 'This content will be marked as approved and queued for delivery.' :
                 decisionModal.decision === 'needs_edits' ? 'Add a note describing what needs to be changed.' : 'This content will be marked as rejected and archived.'}
              </DialogDescription>
            </div>
            <DialogCloseButton onClick={() => setDecisionModal({open: false, decision: ''})} />
          </DialogHeader>
          <DialogBody>
            <Textarea
              value={decisionNote}
              onChange={e => setDecisionNote(e.target.value)}
              placeholder={decisionModal.decision === 'needs_edits' ? 'What needs to change?' : 'Optional note…'}
              className="min-h-[96px]"
            />
            <DialogFooter>
              <Button variant="ghost" size="sm" onClick={() => setDecisionModal({open: false, decision: ''})}>Cancel</Button>
              <Button
                size="sm"
                onClick={confirmDecision}
                disabled={savingDecision}
                loading={savingDecision}
                className={cn('text-content-inverse',
                  decisionModal.decision === 'approved' ? 'bg-status-success hover:bg-status-success/90' :
                  decisionModal.decision === 'rejected' ? 'bg-status-error hover:bg-status-error/90' :
                  'bg-status-warning hover:bg-status-warning/90'
                )}
              >
                {savingDecision ? 'Saving…' : 'Confirm'}
              </Button>
            </DialogFooter>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function DecisionButton({ onClick, icon: Icon, label, tone, primary }: { onClick: () => void; icon: any; label: string; tone: 'accent' | 'amber' | 'red'; primary?: boolean }) {
  const toneMap: Record<string, string> = {
    accent: primary
      ? 'bg-accent text-white hover:bg-accent-hover'
      : 'bg-accent/10 text-accent hover:bg-accent/15',
    amber:  'bg-status-warning/10 text-status-warning hover:bg-status-warning/20',
    red:    'bg-status-error/10 text-status-error hover:bg-status-error/20',
  };
  return (
    <Button
      type="button"
      variant="ghost"
      onClick={onClick}
      leftIcon={<Icon size={14}/>}
      className={cn(toneMap[tone])}
    >
      {label}
    </Button>
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
            <Button
              key={sv.key}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onVariantChange(sv.key)}
              leftIcon={<sv.icon size={12} />}
              className={cn('h-7 px-3 text-xs',
                variant === sv.key
                  ? 'bg-accent/10 text-accent hover:bg-accent/15'
                  : 'text-content-tertiary hover:text-content-primary')}
            >
              {sv.label}
            </Button>
          ))}
        </div>
        <span className="ml-auto text-xs font-mono text-content-tertiary">v{latest?.version || 1}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-content-tertiary">Edit kind</span>
        <div className="min-w-[140px]">
          <Select value={kind} onValueChange={(v: string) => setKind(v as any)}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {['full','section','hook','shorten','expand','tone','emotion','repetition'].map(k => (
                <SelectItem key={k} value={k}>{k}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <Textarea value={body} onChange={e => setBody(e.target.value)}
        className="flex-1 min-h-0 font-mono text-xs resize-none" />
      <div className="flex gap-2 pt-2">
        <Button onClick={submit} disabled={busy} loading={busy} leftIcon={<Wand2 size={13}/>}>
          {busy ? 'Saving…' : 'Save as new version'}
        </Button>
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
        <Input value={nudge} onChange={e => setNudge(e.target.value)} placeholder="Optional prompt nudge…" className="flex-1" />
        <Button onClick={regen} size="sm" leftIcon={<Wand2 size={12}/>}>
          Regenerate
        </Button>
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
        <FieldLabel className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Title</FieldLabel>
        <Input
          value={title}
          onChange={e => setTitle(e.target.value)}
        />
      </div>
      <div>
        <FieldLabel className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Hook</FieldLabel>
        <Input
          value={hook}
          onChange={e => setHook(e.target.value)}
        />
      </div>
      <div>
        <FieldLabel className="text-[11px] font-semibold uppercase tracking-wider text-content-tertiary mb-2 block">Topic</FieldLabel>
        <Input
          value={topic}
          onChange={e => setTopic(e.target.value)}
        />
      </div>
      <div className="pt-2">
        <Button
          onClick={save}
          disabled={!hasChanges || saving}
          loading={saving}
          leftIcon={<Save size={14} />}
          variant={hasChanges ? 'primary' : 'secondary'}
        >
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </div>
  );
}
