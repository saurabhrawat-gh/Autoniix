'use client';

import { useEffect, useState } from 'react';
import { usersApi } from '@/lib/api-v2';
import { Button, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';

const ROLES = ['owner', 'admin', 'editor', 'reviewer', 'viewer'] as const;

export default function Users() {
  const [rows, setRows] = useState<any[]>([]);
  const refresh = () => { usersApi.list().then(r => setRows(r.data || [])).catch(() => setRows([])); };
  useEffect(() => { refresh(); }, []);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full"><div className="space-y-5">
      <h1 className="text-2xl font-semibold">Users</h1>
      <p className="text-sm opacity-70">Single-tenant. Owner can promote/demote and disable accounts. Self-serve registration is open at <code>/register</code>.</p>
      <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
        {rows.length === 0 && <div className="p-6 text-sm opacity-60 text-center">No users yet (or you don't have permission).</div>}
        {rows.map(u => (
          <div key={u.id} className="p-3 flex items-center gap-3">
            <div className="size-8 rounded-full bg-gradient-to-br from-indigo-400 to-fuchsia-400 text-white text-xs flex items-center justify-center">
              {(u.email || '?').slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium truncate">{u.email}</div>
              <div className="text-xs opacity-60">{u.display_name || '—'} · MFA: {u.mfa_enabled ? 'on' : 'off'} · last login {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'never'}</div>
            </div>
            <div className="min-w-[120px]">
              <Select value={u.role} onValueChange={async (v: string) => { await usersApi.setRole(u.id, v); refresh(); }}>
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              variant={u.disabled ? 'primary' : 'outline'}
              className={u.disabled ? 'bg-status-success hover:bg-status-success/90 text-content-inverse' : ''}
              onClick={async () => {
                if (u.disabled) await usersApi.enable(u.id); else await usersApi.disable(u.id);
                refresh();
              }}
            >
              {u.disabled ? 'enable' : 'disable'}
            </Button>
          </div>
        ))}
      </div>
    </div></main>
  );
}
