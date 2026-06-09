'use client';

import { useEffect, useState, useCallback, useRef, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { providersApi } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { usePermissions } from '@/lib/hooks/usePermissions';
import { confirmDialog, promptDialog } from '@/lib/components/ConfirmDialog'; // promptDialog kept for handleWipe (bulk-wipe only)
import { Input } from '@/lib/ui';
import { useToast } from '@/lib/toast';
import { Plug, Loader2, Trash2, Plus, ChevronRight, Edit2, Check, X } from '@/lib/components/Icon';

const STUB_KINDS = new Set(['lut', 'sfx', 'music']);

export default function ProvidersLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { showToast } = useToast();
  const { role } = usePermissions();

  const [cats, setCats] = useState<any[]>([]);
  const [kinds, setKinds] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [wiping, setWiping] = useState(false);
  const [deletingCat, setDeletingCat] = useState<string | null>(null);
  const [renamingCat, setRenamingCat] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.categories().then(r => setCats(r.data || [])),
      providersApi.kinds().then(r => setKinds(r.data || [])).catch(() => {}),
      providersApi.credentials().then(r => setCreds(r.data || [])),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    const handler = () => refresh();
    window.addEventListener('providers:refresh', handler);
    return () => window.removeEventListener('providers:refresh', handler);
  }, [refresh]);

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

  const startRename = (name: string, currentLabel: string) => {
    setRenamingCat(name);
    setRenameValue(currentLabel);
    setTimeout(() => renameInputRef.current?.select(), 30);
  };

  const commitRename = async (name: string) => {
    const trimmed = renameValue.trim();
    const currentLabel = cats.find(c => c.name === name)?.label || name;
    setRenamingCat(null);
    if (!trimmed || trimmed === currentLabel) return;
    try {
      await providersApi.updateCategory(name, trimmed);
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Rename failed', 'error');
    }
  };

  const handleDeleteCategory = async (name: string, label: string, isBuiltIn: boolean) => {
    const hint = isBuiltIn ? ' Restore defaults can bring it back.' : ' This cannot be undone.';
    const ok = await confirmDialog({
      title: `Delete "${label}"?`,
      description: `Removes the category and all its credentials.${hint}`,
      confirmLabel: 'Delete category',
      destructive: true,
    });
    if (!ok) return;
    setDeletingCat(name);
    try {
      await providersApi.deleteCategory(name);
      showToast(`Category "${label}" removed`, 'success');
      if (pathname.includes(encodeURIComponent(name))) {
        router.push('/dashboard/providers');
      }
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Delete failed', 'error');
    } finally {
      setDeletingCat(null);
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

  const activeCategoryLabel = activeCategory
    ? (cats.find(c => c.name === activeCategory)?.label || activeCategory)
    : null;

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* ── Category sidebar ── */}
      <aside
        aria-label="Provider categories"
        className="hidden lg:flex flex-col w-[220px] border-r border-border bg-surface-0 shrink-0 h-full overflow-hidden"
      >
        {/* Sidebar header */}
        <div className="h-12 px-3 flex items-center gap-2 border-b border-border shrink-0">
          <Plug size={14} className="text-accent shrink-0" />
          <span className="text-sm font-semibold text-content-primary">
            Providers
          </span>
        </div>

        {/* Nav content — scrolls independently */}
        <div className="flex-1 py-2 overflow-y-auto">
          {loading ? (
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
                  'mx-2 mb-2 flex items-center justify-between gap-2 px-2.5 py-2 rounded-md text-sm transition-colors',
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

              {/* Category groups — no emoji icons */}
              {Object.entries(grouped).map(([kind, categories]) => {
                const meta = kindsByKey[kind];
                const label = meta?.label || kind.replace(/_/g, ' ');
                return (
                  <div key={kind} className="mb-3">
                    {/* Section header — text only */}
                    <div className="mx-3 mb-0.5 select-none">
                      <span className="text-[10px] uppercase tracking-wider text-content-tertiary font-semibold">
                        {label}
                      </span>
                    </div>

                    {/* Category links with hover-reveal delete */}
                    {categories.map(cat => {
                      const count = connectedCount(cat.name);
                      const isActive = activeCategory === cat.name;
                      return (
                        <div key={cat.name} className="group/cat mx-2 mb-0.5">
                          {renamingCat === cat.name ? (
                            <div className="flex items-center gap-1 px-1">
                              <Input
                                ref={renameInputRef}
                                value={renameValue}
                                onChange={e => setRenameValue(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') commitRename(cat.name);
                                  if (e.key === 'Escape') setRenamingCat(null);
                                }}
                                onBlur={() => commitRename(cat.name)}
                                className="h-7 text-sm flex-1 min-w-0"
                                autoFocus
                              />
                              <button type="button" onMouseDown={e => { e.preventDefault(); commitRename(cat.name); }}
                                className="p-1 rounded text-status-success hover:bg-status-success/10">
                                <Check size={11} />
                              </button>
                              <button type="button" onMouseDown={e => { e.preventDefault(); setRenamingCat(null); }}
                                className="p-1 rounded text-content-tertiary hover:bg-surface-1">
                                <X size={11} />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-0.5">
                              <Link
                                href={`/dashboard/providers/${encodeURIComponent(cat.name)}`}
                                aria-current={isActive ? 'page' : undefined}
                                className={cn(
                                  'flex-1 flex items-center justify-between gap-2 px-2.5 py-2 rounded-md text-sm transition-colors min-w-0',
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
                              <button
                                type="button"
                                onClick={() => startRename(cat.name, cat.label)}
                                title={`Rename ${cat.label}`}
                                className="opacity-0 group-hover/cat:opacity-100 transition-opacity shrink-0 p-1 rounded text-content-tertiary hover:text-accent hover:bg-accent/10"
                              >
                                <Edit2 size={10} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteCategory(cat.name, cat.label, !cat.is_user_defined)}
                                disabled={deletingCat === cat.name}
                                title={`Delete ${cat.label}`}
                                className="opacity-0 group-hover/cat:opacity-100 transition-opacity shrink-0 p-1 rounded text-content-tertiary hover:text-status-error hover:bg-status-error/10 disabled:opacity-50"
                              >
                                {deletingCat === cat.name
                                  ? <Loader2 size={10} className="animate-spin" />
                                  : <Trash2 size={10} />}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </nav>
          )}
        </div>

        {/* Footer — Add category + Wipe all (always visible, never scrolls away) */}
        <div className="shrink-0 p-3 border-t border-border space-y-2">
          <button
            type="button"
            onClick={() => router.push('/dashboard/providers?addCategory=1')}
            className="w-full flex items-center justify-center gap-1.5 h-7 px-2 rounded-md text-[11px] text-content-secondary hover:bg-surface-1 hover:text-content-primary border border-border transition-colors"
          >
            <Plus size={11} /> Add category
          </button>
          {role === 'owner' && !loading && (
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
          )}
        </div>
      </aside>

      {/* ── Main content — scrolls independently from sidebar ── */}
      <div className="flex-1 min-w-0 overflow-y-auto flex flex-col">
        {/* Breadcrumb — only shown on category detail pages */}
        {activeCategory && (
          <nav className="px-4 sm:px-6 pt-4 pb-0 shrink-0" aria-label="Breadcrumb">
            <ol className="flex items-center gap-1.5 text-xs text-content-tertiary">
              <li>
                <Link
                  href="/dashboard/providers"
                  className="hover:text-content-primary transition-colors"
                >
                  Providers
                </Link>
              </li>
              <li aria-hidden="true"><ChevronRight size={10} /></li>
              <li className="text-content-primary font-medium truncate">{activeCategoryLabel}</li>
            </ol>
          </nav>
        )}
        {children}
      </div>
    </div>
  );
}
