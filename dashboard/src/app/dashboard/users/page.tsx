'use client';

import { useEffect, useState } from 'react';
import { usersApi, authApi } from '@/lib/api-v2';
import { Button, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';
import { Trash2, ChevronDown, ChevronRight } from '@/lib/components/Icon';

const GLOBAL_ROLES = ['superadmin', 'user'] as const;
const WS_ROLE_BADGE: Record<string, string> = {
  owner:  'bg-accent/15 text-accent',
  member: 'bg-status-success/15 text-status-success',
  viewer: 'bg-surface-2 text-content-secondary',
};
const GLOBAL_BADGE: Record<string, string> = {
  superadmin: 'bg-status-error/15 text-status-error',
  user:       'bg-surface-2 text-content-secondary',
};

export default function Users() {
  const [rows, setRows]     = useState<any[]>([]);
  const [myId, setMyId]     = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loading, setLoading]   = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await usersApi.list();
      setRows(r.data || []);
    } catch { setRows([]); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    refresh();
    authApi.me().then((r: any) => setMyId(r?.data?.user_id ?? null)).catch(() => {});
  }, []);

  const toggle = (id: number) =>
    setExpanded(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-sm opacity-70 mt-1">
            Platform-wide accounts. <strong>Global role</strong> controls platform admin access.
            Each user&apos;s <strong>workspace role</strong> (owner / member / viewer) is shown per workspace below.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
          {loading && <div className="p-6 text-sm opacity-60 text-center">Loading…</div>}
          {!loading && rows.length === 0 && (
            <div className="p-6 text-sm opacity-60 text-center">No users yet (or you don&apos;t have permission).</div>
          )}
          {rows.map(u => {
            const workspaces: any[] = u.workspaces ?? [];
            const isExpanded = expanded.has(u.id);
            const isSelf = myId !== null && u.id === myId;
            return (
              <div key={u.id} className="divide-y divide-border/50">
                {/* User row */}
                <div className={`p-3 flex items-center gap-3 ${u.disabled ? 'opacity-50' : ''}`}>
                  {/* Expand toggle */}
                  <button
                    onClick={() => toggle(u.id)}
                    className="shrink-0 text-content-tertiary hover:text-content-secondary transition-colors"
                    aria-label={isExpanded ? 'Collapse workspaces' : 'Expand workspaces'}
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>

                  {/* Avatar */}
                  <div className={`size-8 rounded-full text-white text-xs flex items-center justify-center shrink-0
                    ${u.global_role === 'superadmin'
                      ? 'bg-gradient-to-br from-fuchsia-400 to-pink-400'
                      : 'bg-gradient-to-br from-indigo-400 to-fuchsia-400'}`}>
                    {(u.email || '?').slice(0, 1).toUpperCase()}
                  </div>

                  {/* Identity */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium truncate">{u.email}</span>
                      {isSelf && <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">you</span>}
                    </div>
                    <div className="text-xs opacity-60 mt-0.5">
                      {u.display_name || '—'} · MFA: {u.mfa_enabled ? 'on' : 'off'}
                      {u.last_login_at ? ` · last login ${new Date(u.last_login_at).toLocaleString()}` : ' · never logged in'}
                      {' · '}<span className="font-mono">{workspaces.length} workspace{workspaces.length !== 1 ? 's' : ''}</span>
                    </div>
                  </div>

                  {/* Global role badge + selector */}
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${GLOBAL_BADGE[u.global_role] ?? GLOBAL_BADGE.user}`}>
                    {u.global_role}
                  </span>
                  <div className="min-w-[110px] shrink-0">
                    <Select
                      value={u.global_role}
                      onValueChange={async (v: string) => { await usersApi.setRole(u.id, v); refresh(); }}
                    >
                      <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {GLOBAL_ROLES.map(r => (
                          <SelectItem key={r} value={r}>
                            {r === 'superadmin' ? 'Superadmin' : 'User'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Disable / enable */}
                  <Button
                    size="sm"
                    variant={u.disabled ? 'primary' : 'outline'}
                    className={u.disabled ? 'bg-status-success hover:bg-status-success/90 text-content-inverse shrink-0' : 'shrink-0'}
                    onClick={async () => {
                      if (u.disabled) await usersApi.enable(u.id); else await usersApi.disable(u.id);
                      refresh();
                    }}
                  >
                    {u.disabled ? 'Enable' : 'Disable'}
                  </Button>

                  {/* Delete (not self) */}
                  {!isSelf && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-status-error border-status-error/30 hover:bg-status-error/10 px-2 shrink-0"
                      title="Delete user"
                      onClick={async () => {
                        if (!confirm(`Permanently delete ${u.email}? This cannot be undone.`)) return;
                        try { await usersApi.delete(u.id); refresh(); }
                        catch (e: any) { alert(e?.message || 'Delete failed'); }
                      }}
                    >
                      <Trash2 size={14} />
                    </Button>
                  )}
                </div>

                {/* Workspace membership rows (expandable) */}
                {isExpanded && (
                  <div className="bg-surface-1/50">
                    {workspaces.length === 0 ? (
                      <div className="pl-12 py-2 text-xs opacity-50">No workspace memberships.</div>
                    ) : (
                      workspaces.map((ws: any) => (
                        <div key={ws.workspace_id} className="pl-12 pr-4 py-2 flex items-center gap-3 border-b border-border/30 last:border-0">
                          <div className="min-w-0 flex-1 text-xs text-content-secondary truncate">
                            <span className="font-medium text-content-primary">{ws.workspace_name}</span>
                            <span className="ml-2 opacity-60">#{ws.workspace_id}</span>
                          </div>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${WS_ROLE_BADGE[ws.workspace_role] ?? WS_ROLE_BADGE.viewer}`}>
                            {ws.workspace_role}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-xs text-content-tertiary">
          <strong>Global role</strong>: superadmin = platform admin access · user = workspace-only access.<br />
          <strong>Workspace role</strong>: set per workspace on the Teams page.
        </p>
      </div>
    </main>
  );
}
