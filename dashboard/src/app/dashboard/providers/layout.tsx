'use client';

import { useEffect, useState, useCallback, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { providersApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { usePermissions } from '@/lib/hooks/usePermissions';
import { promptDialog } from '@/lib/components/ConfirmDialog';
import { useToast } from '@/lib/toast';
import { Plug, Loader2, Trash2 } from '@/lib/components/Icon';

const KIND_ICON: Record<string, string> = {
  llm: '🧠',
  tts: '🎙️',
  image: '🖼️',
  search: '🔍',
  storage: '💾',
  stock_footage: '🎬',
};

const STUB_KINDS = new Set(['lut', 'sfx', 'music']);

export default function ProvidersLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { showToast } = useToast();
  const { role } = usePermissions();

  const [cats, setCats] = useState<any[]>([]);
  const [kinds, setKinds] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [wiping, setWiping] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.categories().then(r => setCats(r.data || [])),
      providersApi.kinds().then(r => setKinds(r.data || [])).catch(() => {}),
      providersApi.credentials().then(r => setCreds(r.data || [])),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleWipe = async () => {
    const phrase = await promptDialog({
      title: 'Wipe all provider data?',
      description:
        'This will DELETE every credential and chain in the database. ' +
        'This cannot be undone.',
      label: 'Type WIPE to confirm',
      placeholder: 'WIPE',
      match: 'WIPE',
      confirmLabel: 'Wipe everything',
      destructive: true,
    });
    if (phrase === null) return;
    setWiping(true);
    try {
      await providersApi.cleanSlate();
      showToast('All provider data wiped', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Wipe failed', 'error');
    } finally {
      setWiping(false);
    }
  };

  const grouped: Record<string, any[]> = cats.reduce((acc, c) => {
    if (STUB_KINDS.has(c.kind)) return acc;
    (acc[c.kind] ||= []).push(c);
    return acc;
  }, {} as Record<string, any[]>);

  const kindsByKey: Record<string, any> = kinds.reduce(
    (acc, k) => { acc[k.kind] = k; return acc; },
    {} as Record<string, any>,
  );

  const connectedCount = (catName: string) =>
    creds.filter(cr => cr.category === catName).length;

  const activeCategory = pathname.startsWith('/dashboard/providers/')
    ? decodeURIComponent(pathname.replace('/dashboard/providers/', '').split('?')[0])
    : null;

  return (
    <div className="flex flex-1 min-h-0">
      {/* ── Category sidebar — hidden on mobile / tablet ── */}
      <aside
        aria-label="Provider categories"
        className="hidden lg:flex flex-col w-52 xl:w-60 border-r border-border bg-surface-0 shrink-0"
      >
        {/* Sidebar header */}
        <div className="px-3 py-3 flex items-center gap-2 border-b border-border shrink-0">
          <Plug size={14} className="text-accent shrink-0" />
          <span className="text-xs font-semibold text-content-primary tracking-tight">
            Providers
          </span>
        </div>

        {/* Nav content */}
        <div className="flex-1 py-2 overflow-y-auto">
          {loading ? (
            /* Loading skeleton */
            <div className="px-3 space-y-4 mt-1" aria-busy="true" aria-label="Loading categories">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="h-2.5 w-16 rounded bg-surface-2 animate-pulse" />
                  {Array.from({ length: i === 0 ? 3 : 2 }).map((_, j) => (
                    <div key={j} className="h-7 rounded-md bg-surface-1 animate-pulse" />
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <nav aria-label="Provider category navigation">
              {/* Overview link */}
              <Link
                href="/dashboard/providers"
                className={cn(
                  'mx-2 mb-2 flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors',
                  !activeCategory
                    ? 'bg-accent/10 text-accent font-semibold'
                    : 'text-content-secondary hover:bg-surface-1 hover:text-content-primary',
                )}
              >
                <span>Overview</span>
                {creds.length > 0 && (
                  <span className={cn(
                    'text-[10px] px-1.5 py-0.5 rounded-full tabular-nums',
                    !activeCategory
                      ? 'bg-accent/20 text-accent'
                      : 'bg-surface-2 text-content-tertiary',
                  )}>
                    {creds.length}
                  </span>
                )}
              </Link>

              {/* Category groups */}
              {Object.entries(grouped).map(([kind, categories]) => {
                const meta = kindsByKey[kind];
                const icon = meta?.icon || KIND_ICON[kind] || '🔌';
                const label = meta?.label || kind.replace(/_/g, ' ');
                return (
                  <div key={kind} className="mb-3">
                    {/* Section header */}
                    <div className="mx-3 mb-0.5 flex items-center gap-1.5 select-none">
                      <span className="text-[10px]" aria-hidden="true">{icon}</span>
                      <span className="text-[10px] uppercase tracking-wider text-content-tertiary font-semibold">
                        {label}
                      </span>
                    </div>

                    {/* Category links */}
                    {categories.map(cat => {
                      const count = connectedCount(cat.name);
                      const isActive = activeCategory === cat.name;
                      return (
                        <Link
                          key={cat.name}
                          href={`/dashboard/providers/${encodeURIComponent(cat.name)}`}
                          aria-current={isActive ? 'page' : undefined}
                          className={cn(
                            'mx-2 mb-0.5 flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors',
                            isActive
                              ? 'bg-accent/10 text-accent font-semibold'
                              : 'text-content-secondary hover:bg-surface-1 hover:text-content-primary',
                          )}
                        >
                          <span className="truncate leading-tight">{cat.label}</span>
                          {count > 0 && (
                            <span className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded-full shrink-0 tabular-nums',
                              isActive
                                ? 'bg-accent/20 text-accent'
                                : 'bg-surface-2 text-content-tertiary',
                            )}>
                              {count}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                );
              })}
            </nav>
          )}
        </div>

        {/* Wipe all — owner role only */}
        {role === 'owner' && !loading && (
          <div className="shrink-0 p-3 border-t border-border">
            <button
              type="button"
              onClick={handleWipe}
              disabled={wiping}
              className="w-full flex items-center justify-center gap-1.5 h-7 px-2 rounded-md text-[11px] text-status-error hover:bg-status-error/10 border border-status-error/30 transition-colors disabled:opacity-50"
            >
              {wiping
                ? <Loader2 size={11} className="animate-spin" />
                : <Trash2 size={11} />}
              {wiping ? 'Wiping…' : 'Wipe all'}
            </button>
          </div>
        )}
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}
