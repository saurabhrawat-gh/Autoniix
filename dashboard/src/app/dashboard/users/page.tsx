'use client';

import { useEffect, useState } from 'react';
import { usersApi, authApi } from '@/lib/api-v2';
import { Button } from '@/lib/ui';
import { Trash2, ChevronDown, ChevronRight, ShieldCheck } from '@/lib/components/Icon';
import { usePermissions } from '@/lib/hooks/usePermissions';

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
  const [rows, setRows]         = useState<any[]>([]);
  const [myId, setMyId]         = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loading, setLoading]   = useState(true);
  const [transferTarget, setTransferTarget] = useState<any | null>(null);
  const [transferring, setTransferring]     = useState(false);
  const { globalRole, loading: permsLoading } = usePermissions();

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

  const iAmSuperadmin = rows.find(r => r.id === myId)?.global_role === 'superadmin';

  const toggle = (id: number) =>
    setExpanded(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const doTransfer = async () => {
    if (!transferTarget) return;
    setTransferring(true);
    try {
      await usersApi.transferSuperadmin(transferTarget.id);
      setTransferTarget(null);
      refresh();
    } catch (e: any) {
      alert(e?.message || 'Transfer failed');
    } finally {
      setTransferring(false);
    }
  };

  if (!permsLoading && globalRole !== 'superadmin') {
    return (
      <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
        <div className="rounded-xl border border-border bg-surface-0 p-10 text-center space-y-2">
          <h1 className="text-xl font-semibold">Not authorized</h1>
          <p className="text-sm opacity-70">This page is only accessible to the superadmin.</p>
        </div>
      </main>
    );
  }

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

        {/* Transfer confirmation dialog */}
        {transferTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-surface-0 border border-border rounded-xl p-6 max-w-sm w-full space-y-4 shadow-xl">
              <div className="flex items-center gap-3">
                <ShieldCheck size={20} className="text-status-error shrink-0" />
                <h2 className="text-base font-semibold">Transfer Superadmin?</h2>
              </div>
              <p className="text-sm opacity-75">
                You are about to transfer the <strong>superadmin</strong> seat to{' '}
                <strong>{transferTarget.email}</strong>.
              </p>
              <p className="text-sm opacity-75">
                <strong>You will immediately lose platform admin access.</strong> This action
                takes effect on your next page load.
              </p>
              <div className="flex gap-2 justify-end">
                <Button size="sm" variant="outline" onClick={() => setTransferTarget(null)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="bg-status-error hover:bg-status-error/90 text-white"
                  onClick={doTransfer}
                  disabled={transferring}
                >
                  {transferring ? 'Transferring…' : 'Yes, transfer'}
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
          {loading && <div className="p-6 text-sm opacity-60 text-center">Loading…</div>}
          {!loading && rows.length === 0 && (
            <div className="p-6 text-sm opacity-60 text-center">No users yet (or you don&apos;t have permission).</div>
          )}
          {rows.map(u => {
            const workspaces: any[] = u.workspaces ?? [];
            const isExpanded = expanded.has(u.id);
            const isSelf = myId !== null && u.id === myId;
            const isSuperadmin = u.global_role === 'superadmin';
            const isDisabled = !!u.disabled;
            // Disabled users only show Enable. No other actions allowed until re-enabled.
            const canTransfer = iAmSuperadmin && !isSelf && !isSuperadmin && !isDisabled;
            const canDisable  = iAmSuperadmin && !isSelf && !isSuperadmin && !isDisabled;
            const canDelete   = iAmSuperadmin && !isSelf && !isSuperadmin && !isDisabled;
            const canEnable   = iAmSuperadmin && !isSelf && !isSuperadmin && isDisabled;
            return (
              <div key={u.id} className="divide-y divide-border/50">
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
                    ${isSuperadmin
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

                  {/* Global role badge (read-only) */}
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${GLOBAL_BADGE[u.global_role] ?? GLOBAL_BADGE.user}`}>
                    {isSuperadmin ? 'superadmin' : 'user'}
                  </span>

                  {/* Transfer superadmin — amber accent, clearly NOT delete */}
                  {canTransfer && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-amber-500 border-amber-500/40 hover:bg-amber-500/10 shrink-0 flex items-center gap-1"
                      title="Hand off the superadmin seat to this user"
                      onClick={() => setTransferTarget(u)}
                    >
                      <ShieldCheck size={13} />
                      Make Superadmin
                    </Button>
                  )}

                  {/* Enable (only when disabled) */}
                  {canEnable && (
                    <Button
                      size="sm"
                      className="bg-status-success hover:bg-status-success/90 text-content-inverse shrink-0"
                      onClick={async () => { await usersApi.enable(u.id); refresh(); }}
                    >
                      Enable
                    </Button>
                  )}

                  {/* Disable (only when active) */}
                  {canDisable && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      onClick={async () => {
                        try { await usersApi.disable(u.id); refresh(); }
                        catch (e: any) { alert(e?.message || 'Action failed'); }
                      }}
                    >
                      Disable
                    </Button>
                  )}

                  {/* Delete — only on active, non-superadmin, non-self users */}
                  {canDelete && (
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
          <strong>Superadmin</strong>: single platform-wide seat · full admin access · use Transfer to hand off ownership.<br />
          <strong>User</strong>: workspace-only access · role set per workspace on the Teams page.
        </p>
      </div>
    </main>
  );
}
