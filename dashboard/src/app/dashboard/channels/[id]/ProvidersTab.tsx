'use client';

import { useEffect, useState, useCallback } from 'react';
import { providersApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { ArrowUp, ArrowDown, X, Plus, RotateCw } from '@/lib/components/Icon';
import { confirmDialog } from '@/lib/components/ConfirmDialog';
import {
  Button,
  Switch,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/lib/ui';

interface ProvidersTabProps {
  channelId: string;
}

/**
 * Per-channel providers tab.
 *
 * Layout, top-down:
 *   1. Category selector (text input — workspace knows the universe of categories).
 *   2. Mode segmented control: All modes | short | long_form | ...
 *   3. Effective chain banner (read-only) — what the runtime will pick, with
 *      origin labels (`channel+mode`, `channel`, `workspace+mode`, etc).
 *   4. Channel override editor for the (mode, category) pair, with add/remove/reorder.
 *   5. "Clear override" button → DELETE row, falls through to next layer.
 */
export default function ProvidersTab({ channelId }: ProvidersTabProps) {
  const { showToast } = useToast();
  const [categories, setCategories] = useState<{ name: string }[]>([]);
  const [modes, setModes] = useState<{ name: string; label: string }[]>([]);
  const [category, setCategory] = useState<string>('llm.script');
  const [mode, setMode] = useState<string | null>(null);
  const [override, setOverride] = useState<any[]>([]);
  const [resolved, setResolved] = useState<any[]>([]);
  const [allCreds, setAllCreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    providersApi.categories().then(r => setCategories(r.data || [])).catch(() => {});
    providersApi.contentModes().then(r => setModes(r.data || [])).catch(() => {});
  }, []);

  const refresh = useCallback(() => {
    if (!category) return;
    setLoading(true);
    Promise.all([
      providersApi.chainsV2({ scope: 'channel', scope_id: channelId, content_mode: mode || undefined, category })
        .then(r => setOverride(r.data || []))
        .catch(() => setOverride([])),
      providersApi.resolved({ category, channel_id: channelId, content_mode: mode || undefined })
        .then(r => setResolved(r.data || []))
        .catch(() => setResolved([])),
      providersApi.credentials(category)
        .then(r => setAllCreds(r.data || []))
        .catch(() => setAllCreds([])),
    ]).finally(() => setLoading(false));
  }, [channelId, category, mode]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = (ids: number[]) =>
    providersApi.upsertChainV2({
      scope: 'channel',
      scope_id: channelId,
      content_mode: mode,
      category,
      credential_ids: ids,
    }).then(() => { refresh(); showToast('Override saved', 'success'); })
      .catch((e: any) => showToast(e?.message || 'Failed', 'error'));

  const clearOverride = async () => {
    const ok = await confirmDialog({
      title: `Clear ${mode ? mode + ' ' : ''}override for ${category}?`,
      description: 'This channel will inherit from the workspace-level configuration.',
      destructive: true,
      confirmLabel: 'Clear override',
    });
    if (!ok) return;
    try {
      await providersApi.deleteChainV2({
        scope: 'channel', scope_id: channelId,
        content_mode: mode || undefined, category,
      });
      showToast('Override cleared', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to clear', 'error');
    }
  };

  const move = (idx: number, dir: -1 | 1) => {
    const ids = override.map((c: any) => c.credential_id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    save(ids);
  };

  const overrideIds = new Set(override.map((c: any) => c.credential_id));
  const eligibleToAdd = allCreds.filter(c => c.enabled && !overrideIds.has(c.id));

  return (
    <div className="space-y-4">
      <div className="text-xs text-content-tertiary">
        Channel overrides take precedence over workspace defaults. Each layer
        appends-with-dedup so a partial override still inherits the rest of the
        workspace chain. Use the segmented control to override only a specific
        content mode (e.g. just Shorts).
      </div>

      {/* Category + mode controls */}
      <div className="flex items-end gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Category</div>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {categories.map((c: any) => (
                <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Content mode</div>
          <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
            {[{ name: null as string | null, label: 'All' }, ...modes].map((m: any) => (
              <Button
                key={m.name ?? '__all__'}
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setMode(m.name)}
                className={cn('h-7 px-2.5 text-[11px] font-medium',
                  mode === m.name
                    ? 'bg-surface-0 text-content-primary shadow-sm hover:bg-surface-0'
                    : 'text-content-tertiary hover:text-content-secondary')}
              >
                {m.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Effective chain (read-only) */}
      <section>
        <div className="text-[10px] uppercase text-content-tertiary mb-1.5">
          Effective chain (what the runtime will pick)
        </div>
        {resolved.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-1/40 px-3 py-3 text-xs text-content-tertiary text-center">
            No providers resolved. Configure a workspace chain or add channel overrides below.
          </div>
        ) : (
          <div className="rounded-md border border-border bg-surface-1/40 px-3 py-2 flex items-center gap-1.5 flex-wrap">
            {resolved.map((r: any, i: number) => (
              <span key={`${r.credential_id}-${r.origin}`}
                className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-surface-0 border border-border">
                <span className="text-content-tertiary">{i + 1}.</span>
                <span className="text-content-primary font-medium">{r.label}</span>
                {r.model && <span className="text-content-tertiary font-mono">· {r.model}</span>}
                <span className={cn('text-[9px] px-1 rounded',
                  r.origin === 'default' ? 'bg-status-warning/10 text-status-warning' :
                  r.origin.startsWith('channel') ? 'bg-accent/10 text-accent' :
                  r.origin.startsWith('workspace') ? 'bg-status-success/10 text-status-success' :
                  'bg-status-info/10 text-status-info')}>{r.origin}</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Channel override editor */}
      <section>
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[10px] uppercase text-content-tertiary">
            Channel override · {mode ? `mode: ${mode}` : 'all modes'}
          </div>
          {override.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={clearOverride}
              leftIcon={<RotateCw size={11} />}
              className="h-auto px-1 py-0 text-[11px] text-content-tertiary hover:text-status-error"
            >
              Clear override (inherit from workspace)
            </Button>
          )}
        </div>
        <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
          {loading ? (
            <div className="p-4 text-xs text-content-tertiary text-center">Loading…</div>
          ) : override.length === 0 ? (
            <div className="p-4 text-xs text-content-tertiary text-center">
              No channel override at this layer. Add credentials below to start overriding.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {override.map((c: any, i: number) => {
                const entryEnabled = c.is_enabled ?? true;
                const toggleEntry = async () => {
                  if (!c.id) {
                    showToast('Chain entry id missing — reload', 'error');
                    return;
                  }
                  try {
                    await providersApi.setChainEntryEnabled(c.id, !entryEnabled);
                    refresh();
                  } catch (e: any) {
                    showToast(e?.message || 'Toggle failed', 'error');
                  }
                };
                return (
                <div key={c.id ?? c.credential_id} className={cn(
                  'px-3 py-2 flex items-center gap-2',
                  !entryEnabled && 'opacity-60'
                )}>
                  <span className="text-[11px] text-content-tertiary w-5">{i + 1}.</span>
                  <span className={cn(
                    'text-sm text-content-primary flex-1',
                    !entryEnabled && 'line-through'
                  )}>{c.label}</span>
                  {c.model && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-secondary font-mono">{c.model}</span>
                  )}
                  <span className="text-[10px] text-content-tertiary font-mono">{c.provider_name}</span>
                  <Switch
                    checked={entryEnabled}
                    onCheckedChange={toggleEntry}
                    aria-label={entryEnabled ? 'Disable in this override' : 'Enable in this override'}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={() => move(i, -1)}
                    disabled={i === 0}
                    aria-label="Move up"
                    className="w-6 h-6"
                  >
                    <ArrowUp size={11} />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={() => move(i, 1)}
                    disabled={i === override.length - 1}
                    aria-label="Move down"
                    className="w-6 h-6"
                  >
                    <ArrowDown size={11} />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={() => save(override.map((x: any) => x.credential_id).filter((id: number) => id !== c.credential_id))}
                    aria-label="Remove from override"
                    className="w-6 h-6 text-status-error border-status-error/30 hover:bg-status-error/10"
                  >
                    <X size={11} />
                  </Button>
                </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Add credentials to the override */}
        {eligibleToAdd.length > 0 && (
          <div className="mt-2">
            <div className="text-[10px] uppercase text-content-tertiary mb-1.5">Add to override</div>
            <div className="flex flex-wrap gap-1.5">
              {eligibleToAdd.map((c: any) => (
                <Button
                  key={c.id}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => save([...override.map((x: any) => x.credential_id), c.id])}
                  leftIcon={<Plus size={11} />}
                  className="h-7 text-[11px] text-accent border-accent/40 hover:bg-accent/10"
                >
                  {c.label}
                  {c.model && <span className="text-content-tertiary font-mono ml-1">· {c.model}</span>}
                </Button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
