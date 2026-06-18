'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronDown, Check, Plus, ArrowLeft, Loader2 } from 'lucide-react';
import { cn } from '../utils';
import { authApi } from '../api-v2';

type Workspace = {
  id: number;
  name: string;
  slug: string;
  plan: string;
  role: string;
  active: boolean;
};

// ── Deterministic hash-gradient avatar ────────────────────────────────────────
// Each workspace name maps to a fixed gradient drawn from the §3.1 Spectrum
// Palette, so every workspace has a unique, memorable visual identity.

const GRADIENT_PAIRS: Array<[string, string]> = [
  ['#6EE7B7', '#7DD3FC'], // mint → sky
  ['#A78BFA', '#F472B6'], // violet → pink
  ['#7DD3FC', '#A78BFA'], // sky → violet
  ['#F472B6', '#FBBF24'], // pink → amber
  ['#FBBF24', '#6EE7B7'], // amber → mint
  ['#6EE7B7', '#A78BFA'], // mint → violet
  ['#F472B6', '#7DD3FC'], // pink → sky
  ['#FBBF24', '#F472B6'], // amber → pink
];

function hashName(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = ((h * 31) + name.charCodeAt(i)) >>> 0;
  return h;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? '?';
  const second = parts[1]?.[0] ?? '';
  return (first + second).toUpperCase();
}

export function WorkspaceAvatar({ name, size = 20 }: { name: string; size?: number }) {
  const [from, to] = GRADIENT_PAIRS[hashName(name) % GRADIENT_PAIRS.length];
  return (
    <span
      className="rounded-md shrink-0 grid place-items-center font-bold text-white"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(135deg, ${from}, ${to})`,
        fontSize: Math.max(9, Math.round(size * 0.48)),
        letterSpacing: '0.02em',
      }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

export function WorkspaceSwitcher({ collapsed }: { collapsed: boolean }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [createBusy, setCreateBusy] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await authApi.listWorkspaces();
      setWorkspaces(res.data);
    } catch {
      setWorkspaces([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const active = workspaces.find(w => w.active) ?? workspaces[0];

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed) return;
    setCreateBusy(true);
    setCreateErr(null);
    try {
      const res = await authApi.createWorkspace(trimmed);
      await authApi.switchWorkspace(res.workspace_id);
      window.location.href = '/dashboard';
    } catch (err: any) {
      setCreateErr(err?.message ?? 'Failed to create workspace');
      setCreateBusy(false);
    }
  }

  function openCreate() {
    setCreating(true);
    setNewName('');
    setCreateErr(null);
    setTimeout(() => nameInputRef.current?.focus(), 50);
  }

  function closeCreate() {
    setCreating(false);
    setNewName('');
    setCreateErr(null);
  }

  async function switchTo(ws: Workspace) {
    if (ws.active || switching) return;
    setSwitching(true);
    setOpen(false);
    try {
      await authApi.switchWorkspace(ws.id);
      window.location.href = '/dashboard';
    } catch {
      setSwitching(false);
    }
  }

  if (!active) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={cn(
          'flex items-center gap-2 w-full rounded-md px-2 py-1',
          'text-[12.5px] font-medium text-content-secondary',
          'hover:bg-surface-2 hover:text-content-primary transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
          collapsed && 'justify-center px-0'
        )}
      >
        <WorkspaceAvatar name={active.name} size={collapsed ? 20 : 16} />
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate">{active.name}</span>
            <ChevronDown size={10} className="shrink-0 text-content-tertiary" />
          </>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => { setOpen(false); closeCreate(); }} />

          {/* Dropdown */}
          <div
            role="listbox"
            className={cn(
              'absolute z-20 mt-1 w-52 rounded-md border border-border',
              'bg-surface-1 shadow-lg py-1',
              collapsed ? 'left-full ml-2 top-0' : 'left-0 top-full'
            )}
          >
            {!creating ? (
              <>
                <div className="px-2 py-1 text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">
                  Workspaces
                </div>
                {workspaces.map(ws => (
                  <button
                    key={ws.id}
                    role="option"
                    aria-selected={ws.active}
                    type="button"
                    onClick={() => switchTo(ws)}
                    disabled={switching}
                    className={cn(
                      'flex items-center gap-2.5 w-full px-2 py-1.5',
                      'hover:bg-surface-2 transition-colors text-left',
                      ws.active ? 'text-content-primary' : 'text-content-secondary'
                    )}
                  >
                    <WorkspaceAvatar name={ws.name} size={20} />
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-[13px] font-medium">{ws.name}</div>
                      <div className="text-[10px] text-content-tertiary capitalize">{ws.role}</div>
                    </div>
                    {ws.active && <Check size={12} className="text-accent shrink-0" />}
                  </button>
                ))}
                <div className="mx-2 my-1 h-px bg-border" />
                <button
                  type="button"
                  onClick={openCreate}
                  className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-content-tertiary hover:text-content-primary hover:bg-surface-2 transition-colors"
                >
                  <Plus size={12} />
                  Create workspace
                </button>
              </>
            ) : (
              <div className="px-2 pt-2 pb-2">
                <div className="flex items-center gap-1.5 mb-2.5">
                  <button
                    type="button"
                    onClick={closeCreate}
                    className="text-content-tertiary hover:text-content-primary transition-colors"
                  >
                    <ArrowLeft size={13} />
                  </button>
                  <span className="text-[10px] uppercase tracking-widest font-semibold text-content-tertiary">
                    New Workspace
                  </span>
                </div>
                <form onSubmit={handleCreate} className="space-y-2">
                  <input
                    ref={nameInputRef}
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    placeholder="Workspace name"
                    maxLength={60}
                    className="w-full rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-xs text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent/40"
                  />
                  {createErr && (
                    <p className="text-[10px] text-status-error leading-tight">{createErr}</p>
                  )}
                  <button
                    type="submit"
                    disabled={createBusy || !newName.trim()}
                    className="w-full rounded-md bg-accent py-1.5 text-xs font-medium text-white disabled:opacity-50 hover:bg-accent/90 transition-colors flex items-center justify-center gap-1.5"
                  >
                    {createBusy && <Loader2 size={11} className="animate-spin" />}
                    {createBusy ? 'Creating…' : 'Create workspace'}
                  </button>
                </form>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
