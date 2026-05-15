'use client';

import { useEffect, useState, useCallback } from 'react';
import { providersApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { ArrowUp, ArrowDown, X, Plus, RotateCw } from '@/lib/components/Icon';

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

  // Load category + content-mode catalogs once.
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
    if (!confirm(`Clear ${mode ? mode + ' ' : ''}override for ${category}? Channel will inherit from workspace.`)) return;
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
          <select value={category} onChange={e => setCategory(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-md bg-surface-1 border border-border text-sm focus:outline-none focus:border-accent/50">
            {categories.map((c: any) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <div className="text-[10px] uppercase text-content-tertiary mb-1">Content mode</div>
          <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5">
            {[{ name: null as string | null, label: 'All' }, ...modes].map((m: any) => (
              <button key={m.name ?? '__all__'} onClick={() => setMode(m.name)}
                className={cn('px-2.5 py-1 text-[11px] font-medium rounded transition-all',
                  mode === m.name
                    ? 'bg-surface-0 text-content-primary shadow-sm'
                    : 'text-content-tertiary hover:text-content-secondary')}>
                {m.label}
              </button>
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
                  r.origin === 'default' ? 'bg-amber-500/10 text-amber-500' :
                  r.origin.startsWith('channel') ? 'bg-violet-500/10 text-violet-500' :
                  r.origin.startsWith('workspace') ? 'bg-emerald-500/10 text-emerald-500' :
                  'bg-blue-500/10 text-blue-500')}>{r.origin}</span>
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
            <button onClick={clearOverride}
              className="text-[11px] text-content-tertiary hover:text-red-500 flex items-center gap-1">
              <RotateCw size={11} /> Clear override (inherit from workspace)
            </button>
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
                  <button onClick={toggleEntry}
                    title={entryEnabled ? 'Disable in this override' : 'Enable in this override'}
                    className={cn(
                      'relative inline-flex h-4 w-7 shrink-0 items-center rounded-full border transition-colors',
                      entryEnabled ? 'bg-emerald-500/80 border-emerald-500/80' : 'bg-surface-2 border-border'
                    )}>
                    <span className={cn(
                      'inline-block h-3 w-3 rounded-full bg-white shadow transition-transform',
                      entryEnabled ? 'translate-x-3.5' : 'translate-x-0.5'
                    )} />
                  </button>
                  <button onClick={() => move(i, -1)} disabled={i === 0}
                    className="w-6 h-6 flex items-center justify-center rounded border border-border text-content-tertiary hover:bg-surface-2 disabled:opacity-30">
                    <ArrowUp size={11} />
                  </button>
                  <button onClick={() => move(i, 1)} disabled={i === override.length - 1}
                    className="w-6 h-6 flex items-center justify-center rounded border border-border text-content-tertiary hover:bg-surface-2 disabled:opacity-30">
                    <ArrowDown size={11} />
                  </button>
                  <button onClick={() => save(override.map((x: any) => x.credential_id).filter((id: number) => id !== c.credential_id))}
                    className="w-6 h-6 flex items-center justify-center rounded border border-border text-red-500 hover:bg-red-500/10">
                    <X size={11} />
                  </button>
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
                <button key={c.id}
                  onClick={() => save([...override.map((x: any) => x.credential_id), c.id])}
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-accent/40 text-accent hover:bg-accent/10">
                  <Plus size={11} /> {c.label}
                  {c.model && <span className="text-content-tertiary font-mono">· {c.model}</span>}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
