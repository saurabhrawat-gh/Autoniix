'use client';

import { useEffect, useState } from 'react';
import { membersApi, invitesApi, authApi, workspaceApi } from '@/lib/api-v2';
import {
  Button, Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogBody, DialogFooter, DialogCloseButton, DialogTitle, DialogDescription,
} from '@/lib/ui';
import { ExternalLink, Plus, ShieldCheck } from '@/lib/components/Icon';

const ROLE_OPTIONS = [
  { value: 'owner',  label: 'Owner',  desc: 'Full control — assign via Transfer Ownership', disabled: true  },
  { value: 'member', label: 'Member', desc: 'Create and manage content',                    disabled: false },
  { value: 'viewer', label: 'Viewer', desc: 'Read-only access',                             disabled: false },
] as const;
const ROLES = ROLE_OPTIONS.filter(o => !o.disabled).map(o => o.value);
const INVITE_ROLES = ROLE_OPTIONS.filter(o => !o.disabled).map(o => o.value);
const roleLabel = (r: string) => r.charAt(0).toUpperCase() + r.slice(1);
const roleBadge = (r: string) => {
  if (r === 'owner') return 'bg-accent/15 text-accent';
  if (r === 'member') return 'bg-status-success/15 text-status-success';
  return 'bg-surface-2 text-content-secondary';
};

export default function Teams() {
  const [members, setMembers]     = useState<any[]>([]);
  const [invites, setInvites]     = useState<any[]>([]);
  const [myRole, setMyRole]       = useState<string>('viewer');
  const [myId, setMyId]           = useState<number | null>(null);
  const [wsMode, setWsMode]       = useState<'solo' | 'teams'>('solo');
  const [loading, setLoading]     = useState(true);

  const [transferTarget, setTransferTarget] = useState<any | null>(null);
  const [transferPassword, setTransferPassword] = useState('');
  const [transferring, setTransferring] = useState(false);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole]   = useState('viewer');
  const [inviting, setInviting]       = useState(false);
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const [mRes, iRes, meRes, wsRes] = await Promise.all([
        membersApi.list(),
        invitesApi.list().catch(() => ({ data: [] })),
        authApi.me(),
        workspaceApi.get(),
      ]);
      setMembers(mRes.data || []);
      setInvites((iRes.data || []).filter((i: any) => !i.accepted_at));
      setMyRole(meRes?.data?.role || 'viewer');
      setMyId(meRes?.data?.user_id ?? null);
      setWsMode((wsRes as any)?.data?.mode ?? 'solo');
    } catch {
      setMembers([]);
      setInvites([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const isOwner  = myRole === 'owner';
  const isTeams  = wsMode === 'teams';

  const doTransferOwnership = async () => {
    if (!transferTarget || !transferPassword) return;
    setTransferring(true);
    try {
      await membersApi.transferOwnership(transferTarget.user_id, transferPassword);
      setTransferTarget(null);
      setTransferPassword('');
      refresh();
    } catch (e: any) {
      alert(e?.message || 'Transfer failed');
    } finally {
      setTransferring(false);
    }
  };

  const sendInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setLastInviteUrl(null);
    try {
      const r = await invitesApi.create(inviteEmail.trim(), inviteRole);
      setLastInviteUrl((r as any).invite_url || null);
      setInviteEmail('');
      refresh();
    } catch (e: any) {
      alert(e?.message || 'Failed to send invite');
    } finally {
      setInviting(false);
    }
  };

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full">
      <div className="space-y-6">
        {/* Transfer ownership dialog */}
        <Dialog open={!!transferTarget} onOpenChange={(o) => { if (!o) { setTransferTarget(null); setTransferPassword(''); } }}>
          <DialogContent size="sm">
            <DialogHeader>
              <div>
                <DialogTitle className="flex items-center gap-2">
                  <ShieldCheck size={14} className="text-status-warning shrink-0" />
                  Transfer Workspace Ownership?
                </DialogTitle>
                <DialogDescription>
                  You are about to make <strong>{transferTarget?.email}</strong> the new owner.
                  You will be demoted to <strong>member</strong>.
                </DialogDescription>
              </div>
              <DialogCloseButton onClick={() => { setTransferTarget(null); setTransferPassword(''); }} />
            </DialogHeader>
            <DialogBody>
              <div className="space-y-1.5">
                <Label htmlFor="transfer-pw" className="text-xs text-content-secondary">Confirm with your password</Label>
                <Input
                  id="transfer-pw"
                  type="password"
                  value={transferPassword}
                  onChange={e => setTransferPassword(e.target.value)}
                  autoFocus
                />
              </div>
              <DialogFooter>
                <Button size="sm" variant="ghost" onClick={() => { setTransferTarget(null); setTransferPassword(''); }}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="bg-status-warning hover:bg-status-warning/90 text-white"
                  onClick={doTransferOwnership}
                  disabled={transferring || !transferPassword}
                >
                  {transferring ? 'Transferring…' : 'Yes, transfer'}
                </Button>
              </DialogFooter>
            </DialogBody>
          </DialogContent>
        </Dialog>

        <div>
          <h1 className="text-2xl font-semibold">Teams</h1>
          <p className="text-sm opacity-70 mt-1">Workspace members and pending invitations.</p>
        </div>

        {/* Active members */}
        <section>
          <h2 className="text-sm font-medium mb-2 opacity-80">Active members</h2>
          <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
            {loading && (
              <div className="p-6 text-sm opacity-60 text-center">Loading…</div>
            )}
            {!loading && members.length === 0 && (
              <div className="p-6 text-sm opacity-60 text-center">No members found.</div>
            )}
            {members.map(m => (
              <div key={m.user_id} className="p-3 flex items-center gap-3">
                <div className="size-8 rounded-full bg-gradient-to-br from-violet-400 to-sky-400 text-white text-xs flex items-center justify-center shrink-0">
                  {(m.email || '?').slice(0, 1).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{m.email}</div>
                  <div className="text-xs opacity-60">
                    {m.display_name || '—'} · joined {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : 'unknown'}
                    {m.last_login_at ? ` · last login ${new Date(m.last_login_at).toLocaleString()}` : ''}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${roleBadge(m.role)}`}>
                  {roleLabel(m.role)}
                </span>
                {isOwner && m.user_id !== myId && (
                  <>
                    {/* Transfer ownership — only available on non-owner active members */}
                    {m.role !== 'owner' && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-status-warning border-status-warning/40 hover:bg-status-warning/10 flex items-center gap-1"
                        title="Transfer workspace ownership to this member"
                        onClick={() => setTransferTarget(m)}
                      >
                        <ShieldCheck size={13} />
                        Make Owner
                      </Button>
                    )}
                    {/* Role dropdown — member ↔ viewer only. Owner is set via Transfer. */}
                    {m.role !== 'owner' && (
                      <div className="min-w-[120px]">
                        <Select
                          value={m.role}
                          onValueChange={async (v: string) => {
                            try { await membersApi.setRole(m.user_id, v); refresh(); }
                            catch (e: any) { alert(e?.message || 'Failed to update role'); }
                          }}
                        >
                          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {ROLE_OPTIONS.map(o => (
                              <SelectItem key={o.value} value={o.value} disabled={o.disabled}>
                                <div>
                                  <div className="font-medium">{o.label}</div>
                                  <div className="text-[10px] opacity-60 mt-0.5">{o.desc}</div>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-status-error border-status-error/30 hover:bg-status-error/10"
                      onClick={async () => {
                        if (!confirm(`Remove ${m.email} from this workspace?`)) return;
                        try { await membersApi.remove(m.user_id); refresh(); }
                        catch (e: any) { alert(e?.message || 'Failed to remove member'); }
                      }}
                    >
                      Remove
                    </Button>
                  </>
                )}
                {isOwner && m.user_id === myId && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">you</span>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Solo callout / Invite form */}
        {isOwner && (
          !isTeams ? (
            <div className="rounded-xl border border-border bg-surface-1 p-5 flex items-start gap-4">
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-semibold text-content-primary">Your workspace is in Solo mode</p>
                <p className="text-sm text-content-secondary">
                  Enable <strong>Teams mode</strong> in Workspace Settings to invite collaborators.
                </p>
              </div>
              <a
                href="/dashboard/workspace"
                className="shrink-0 text-xs font-medium text-accent hover:underline flex items-center gap-1"
              >
                Workspace Settings <ExternalLink size={11} />
              </a>
            </div>
          ) : (
            <section className="space-y-3">
              <h2 className="text-sm font-medium opacity-80">Invite a new member</h2>
              <div className="rounded-xl border border-border bg-surface-0 p-4 space-y-4">
                <div className="flex gap-2 flex-wrap items-end">
                  <div className="flex-1 min-w-[180px] space-y-1.5">
                    <Label htmlFor="team-inv-email">Email address</Label>
                    <Input
                      id="team-inv-email"
                      type="email"
                      value={inviteEmail}
                      onChange={e => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.com"
                      onKeyDown={e => e.key === 'Enter' && sendInvite()}
                    />
                  </div>
                  <div className="w-[140px] space-y-1.5">
                    <Label>Role</Label>
                    <Select value={inviteRole} onValueChange={setInviteRole}>
                      <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map(o => (
                          <SelectItem key={o.value} value={o.value} disabled={o.disabled}>
                            <div>
                              <div className="font-medium">{o.label}</div>
                              <div className="text-[10px] opacity-60 mt-0.5">{o.desc}</div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button onClick={sendInvite} loading={inviting} leftIcon={<Plus size={14} />}>
                    Send invite
                  </Button>
                </div>
                {lastInviteUrl && (
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/5 border border-accent/20 text-xs">
                    <span className="text-content-secondary shrink-0">Invite link:</span>
                    <code className="flex-1 text-accent truncate">{typeof window !== 'undefined' ? window.location.origin : ''}{lastInviteUrl}</code>
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => {
                        const full = `${window.location.origin}${lastInviteUrl}`;
                        navigator.clipboard.writeText(full);
                      }}
                    >
                      Copy
                    </Button>
                  </div>
                )}
              </div>
            </section>
          )
        )}

        {/* Pending invites */}
        {(isOwner || invites.length > 0) && (
          <section>
            <h2 className="text-sm font-medium mb-2 opacity-80">Pending invitations</h2>
            <div className="rounded-xl border border-border bg-surface-0 divide-y divide-border">
              {invites.length === 0 && (
                <div className="p-6 text-sm opacity-60 text-center">No pending invitations.</div>
              )}
              {invites.map(inv => (
                <div key={inv.id} className="p-3 flex items-center gap-3">
                  <div className="size-8 rounded-full bg-surface-2 text-content-tertiary text-xs flex items-center justify-center shrink-0">
                    {(inv.email || '?').slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{inv.email}</div>
                    <div className="text-xs opacity-60">
                      Invited as {roleLabel(inv.role)} · expires {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : '—'}
                    </div>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-status-warning/15 text-status-warning">
                    Pending
                  </span>
                  {isOwner && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-status-error border-status-error/30 hover:bg-status-error/10"
                      onClick={async () => {
                        await invitesApi.revoke(inv.id);
                        refresh();
                      }}
                    >
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
