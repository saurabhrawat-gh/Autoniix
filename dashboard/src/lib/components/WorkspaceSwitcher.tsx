'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronsUpDown, Check, Building2, Plus } from 'lucide-react';
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

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase();
}

export function WorkspaceSwitcher({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

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
          'flex items-center gap-2 w-full rounded-md px-2 py-1.5',
          'text-sm font-medium text-content-primary',
          'hover:bg-surface-2 transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
          collapsed && 'justify-center px-0'
        )}
      >
        {/* Avatar */}
        <span className="w-6 h-6 rounded shrink-0 bg-accent/20 text-accent flex items-center justify-center text-[10px] font-bold">
          {initials(active.name)}
        </span>
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate text-xs">{active.name}</span>
            <ChevronsUpDown size={12} className="shrink-0 text-content-tertiary" />
          </>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />

          {/* Dropdown */}
          <div
            role="listbox"
            className={cn(
              'absolute z-20 mt-1 w-52 rounded-md border border-border',
              'bg-surface-1 shadow-lg py-1',
              collapsed ? 'left-full ml-2 top-0' : 'left-0 top-full'
            )}
          >
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
                  'flex items-center gap-2.5 w-full px-2 py-1.5 text-sm',
                  'hover:bg-surface-2 transition-colors text-left',
                  ws.active ? 'text-content-primary' : 'text-content-secondary'
                )}
              >
                <span className="w-5 h-5 rounded shrink-0 bg-accent/20 text-accent flex items-center justify-center text-[9px] font-bold">
                  {initials(ws.name)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="truncate text-xs font-medium">{ws.name}</div>
                  <div className="text-[10px] text-content-tertiary capitalize">{ws.role}</div>
                </div>
                {ws.active && <Check size={12} className="text-accent shrink-0" />}
              </button>
            ))}

            <div className="mx-2 my-1 h-px bg-border" />
            <button
              type="button"
              onClick={() => { setOpen(false); router.push('/register'); }}
              className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-content-tertiary hover:text-content-primary hover:bg-surface-2 transition-colors"
            >
              <Plus size={12} />
              Create workspace
            </button>
          </div>
        </>
      )}
    </div>
  );
}
