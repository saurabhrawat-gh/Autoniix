'use client';

import { useState, useEffect } from 'react';
import { authApi } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { UserCircle, Lock, ShieldCheck, Eye, EyeOff, Check, Trash2, Monitor, Loader2, X } from '@/lib/components/Icon';
import { Button, Input, Label } from '@/lib/ui';

interface UserData {
  user_id: number | null;
  email: string | null;
  role: string;
  source: string;
  display_name: string | null;
  initials: string;
}

interface SessionItem {
  id: number;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
}

export default function ProfilePage() {
  const { showToast } = useToast();
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  const [displayName, setDisplayName] = useState('');
  const [nameBusy, setNameBusy] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwBusy, setPwBusy] = useState(false);
  const [pwErr, setPwErr] = useState<string | null>(null);

  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const [showDeleteZone, setShowDeleteZone] = useState(false);

  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);

  useEffect(() => {
    authApi.me().then((res: any) => {
      const d = res?.data ?? res;
      setUser(d);
      setDisplayName(d?.display_name ?? '');
    }).catch(() => {}).finally(() => setLoading(false));

    setSessionsLoading(true);
    authApi.listSessions().then((res: any) => {
      setSessions(res?.data ?? []);
    }).catch(() => {}).finally(() => setSessionsLoading(false));
  }, []);

  async function revokeSession(id: number) {
    setRevokingId(id);
    try {
      await authApi.revokeSession(id);
      setSessions(s => s.filter(x => x.id !== id));
      showToast('Session revoked', 'success');
    } catch (e: any) {
      showToast(e?.message || 'Failed to revoke session', 'error');
    } finally {
      setRevokingId(null);
    }
  }

  function formatRelative(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 2) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function parseUA(ua: string | null) {
    if (!ua) return 'Unknown device';
    if (/mobile/i.test(ua)) return 'Mobile browser';
    if (/chrome/i.test(ua)) return 'Chrome';
    if (/firefox/i.test(ua)) return 'Firefox';
    if (/safari/i.test(ua)) return 'Safari';
    if (/edge/i.test(ua)) return 'Edge';
    return 'Browser';
  }

  async function saveName() {
    if (!displayName.trim()) return;
    setNameBusy(true);
    try {
      await authApi.updateProfile({ display_name: displayName.trim() });
      setUser(u => u ? { ...u, display_name: displayName.trim() } : u);
      showToast('Display name updated', 'success');
    } catch (e: any) {
      showToast(e?.message || 'Failed to update name', 'error');
    } finally {
      setNameBusy(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleteErr(null);
    if (!deleteConfirm) { setDeleteErr('Enter your password to confirm'); return; }
    setDeleteBusy(true);
    try {
      await authApi.deleteAccount(deleteConfirm);
      window.location.href = '/login?reason=account_deleted';
    } catch (e: any) {
      setDeleteErr(e?.message || 'Failed to delete account');
    } finally {
      setDeleteBusy(false);
    }
  }

  async function changePassword() {
    setPwErr(null);
    if (!currentPw) { setPwErr('Enter your current password'); return; }
    if (newPw.length < 8) { setPwErr('New password must be at least 8 characters'); return; }
    if (newPw !== confirmPw) { setPwErr('Passwords do not match'); return; }
    if (newPw === currentPw) { setPwErr('New password must be different from current password'); return; }
    setPwBusy(true);
    try {
      await authApi.updateProfile({ current_password: currentPw, new_password: newPw });
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
      showToast('Password changed. All other sessions have been signed out.', 'success');
    } catch (e: any) {
      setPwErr(e?.message || 'Failed to change password');
    } finally {
      setPwBusy(false);
    }
  }

  const isLegacy = user?.source === 'legacy';
  const pwStrength = newPw.length === 0 ? null : newPw.length < 8 ? 'weak' : newPw.length < 12 ? 'fair' : 'strong';

  if (loading) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="h-8 w-48 bg-surface-2 rounded-md animate-pulse mb-6" />
        <div className="space-y-4">
          {[1,2,3].map(i => <div key={i} className="h-24 bg-surface-1 rounded-xl animate-pulse" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-content-primary">Profile & Security</h1>
        <p className="text-sm text-content-secondary mt-0.5">Manage your account information and password.</p>
      </div>

      {/* Avatar + account info */}
      <div className="bg-surface-1 border border-border rounded-xl p-5 flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-accent/15 flex items-center justify-center text-accent text-lg font-bold shrink-0 select-none">
          {user?.initials || <UserCircle size={22} />}
        </div>
        <div className="min-w-0">
          <p className="text-base font-semibold text-content-primary truncate">{user?.display_name || user?.email || '—'}</p>
          <p className="text-sm text-content-secondary truncate">{user?.email}</p>
          <span className={`inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
            user?.role === 'owner' ? 'bg-accent/10 text-accent' : 'bg-surface-3 text-content-tertiary'
          }`}>
            <ShieldCheck size={10} /> {user?.role ?? 'viewer'}
          </span>
        </div>
      </div>

      {/* Display name */}
      <section className="bg-surface-1 border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <UserCircle size={16} className="text-content-secondary" />
          <h2 className="text-sm font-semibold text-content-primary">Display Name</h2>
        </div>
        {isLegacy ? (
          <p className="text-sm text-content-secondary">Profile editing requires v2 auth. Enable it in Settings → Feature Flags.</p>
        ) : (
          <div className="flex gap-2">
            <Input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Your name"
              className="flex-1"
              onKeyDown={e => e.key === 'Enter' && saveName()}
            />
            <Button
              onClick={saveName}
              disabled={!displayName.trim() || displayName.trim() === (user?.display_name ?? '')}
              loading={nameBusy}
              leftIcon={<Check size={14} />}
            >
              Save
            </Button>
          </div>
        )}
        <p className="text-xs text-content-tertiary">This name is shown in the dashboard header. It is not visible to anyone else.</p>
      </section>

      {/* Change password */}
      <section className="bg-surface-1 border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Lock size={16} className="text-content-secondary" />
          <h2 className="text-sm font-semibold text-content-primary">Change Password</h2>
        </div>
        {isLegacy ? (
          <p className="text-sm text-content-secondary">Password management requires v2 auth. Enable it in Settings → Feature Flags.</p>
        ) : (
          <>
            {pwErr && (
              <div className="text-sm text-status-danger bg-status-danger/10 border border-status-danger/20 rounded-lg px-3 py-2">
                {pwErr}
              </div>
            )}
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="current-pw">Current password</Label>
                <div className="relative">
                  <Input
                    id="current-pw"
                    type={showCurrent ? 'text' : 'password'}
                    value={currentPw}
                    onChange={e => setCurrentPw(e.target.value)}
                    placeholder="••••••••"
                    className="pr-9"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setShowCurrent(v => !v)}
                    className="absolute right-1 top-1/2 -translate-y-1/2"
                    aria-label={showCurrent ? 'Hide password' : 'Show password'}
                  >
                    {showCurrent ? <EyeOff size={14} /> : <Eye size={14} />}
                  </Button>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new-pw">New password</Label>
                <div className="relative">
                  <Input
                    id="new-pw"
                    type={showNew ? 'text' : 'password'}
                    value={newPw}
                    onChange={e => setNewPw(e.target.value)}
                    placeholder="Min 8 characters"
                    className="pr-9"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setShowNew(v => !v)}
                    className="absolute right-1 top-1/2 -translate-y-1/2"
                    aria-label={showNew ? 'Hide password' : 'Show password'}
                  >
                    {showNew ? <EyeOff size={14} /> : <Eye size={14} />}
                  </Button>
                </div>
                {pwStrength && (
                  <div className="flex items-center gap-2 mt-1.5">
                    <div className="flex gap-1">
                      {['weak','fair','strong'].map((lvl, i) => (
                        <div key={lvl} className={`h-1 w-8 rounded-full transition-colors ${
                          (pwStrength === 'weak' && i === 0) ? 'bg-status-danger' :
                          (pwStrength === 'fair' && i <= 1) ? 'bg-status-warning' :
                          (pwStrength === 'strong') ? 'bg-status-success' :
                          'bg-surface-3'
                        }`} />
                      ))}
                    </div>
                    <span className={`text-xs ${pwStrength === 'weak' ? 'text-status-danger' : pwStrength === 'fair' ? 'text-status-warning' : 'text-status-success'}`}>
                      {pwStrength}
                    </span>
                  </div>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirm-pw">Confirm new password</Label>
                <Input
                  id="confirm-pw"
                  type="password"
                  value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)}
                  placeholder="Repeat new password"
                  className={confirmPw && confirmPw !== newPw ? 'border-status-danger' : ''}
                  onKeyDown={e => e.key === 'Enter' && changePassword()}
                />
              </div>
            </div>
            <Button
              onClick={changePassword}
              disabled={!currentPw || !newPw || !confirmPw}
              loading={pwBusy}
            >
              Change Password
            </Button>
            <p className="text-xs text-content-tertiary">Changing your password will sign you out of all other active sessions.</p>
          </>
        )}
      </section>

      {/* Active Sessions */}
      {!isLegacy && (
        <section className="bg-surface-1 border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Monitor size={16} className="text-content-secondary" />
              <h2 className="text-sm font-semibold text-content-primary">Active Sessions</h2>
            </div>
            {sessionsLoading && <Loader2 size={14} className="animate-spin text-content-tertiary" />}
          </div>
          {sessions.length === 0 && !sessionsLoading ? (
            <p className="text-sm text-content-secondary">No active sessions found.</p>
          ) : (
            <ul className="space-y-2">
              {sessions.map(s => (
                <li key={s.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-content-primary truncate">{parseUA(s.user_agent)}</p>
                    <p className="text-xs text-content-tertiary truncate">
                      {s.ip ?? 'unknown IP'} · last seen {formatRelative(s.last_seen_at)}
                    </p>
                  </div>
                  <button
                    onClick={() => revokeSession(s.id)}
                    disabled={revokingId === s.id}
                    className="shrink-0 p-1.5 rounded-md text-content-tertiary hover:text-status-danger hover:bg-status-danger/10 transition-colors disabled:opacity-40"
                    aria-label="Revoke session"
                  >
                    {revokingId === s.id ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-content-tertiary">Revoking a session signs that device out immediately.</p>
        </section>
      )}

      {/* Danger Zone */}
      {!isLegacy && (
        <section className="border border-status-error/30 rounded-xl overflow-hidden">
          <div
            className="flex items-center justify-between px-5 py-3 bg-status-error/5 cursor-pointer select-none"
            onClick={() => { setShowDeleteZone(v => !v); setDeleteErr(null); setDeleteConfirm(''); }}
          >
            <div className="flex items-center gap-2">
              <Trash2 size={15} className="text-status-error" />
              <h2 className="text-sm font-semibold text-status-error">Danger Zone</h2>
            </div>
            <span className="text-xs text-content-tertiary">{showDeleteZone ? 'collapse' : 'expand'}</span>
          </div>
          {showDeleteZone && (
            <div className="px-5 py-4 space-y-3">
              <p className="text-sm text-content-secondary">
                Deleting your account is <strong>permanent and cannot be undone</strong>. Your account will be anonymised, all sessions revoked, and workspace memberships removed. Content you created remains.
              </p>
              {deleteErr && (
                <div className="text-sm text-status-error bg-status-error/10 border border-status-error/20 rounded-lg px-3 py-2">{deleteErr}</div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="delete-pw">Confirm with your password</Label>
                <Input
                  id="delete-pw"
                  type="password"
                  value={deleteConfirm}
                  onChange={e => setDeleteConfirm(e.target.value)}
                  placeholder="Enter your password"
                  onKeyDown={e => e.key === 'Enter' && handleDeleteAccount()}
                />
              </div>
              <Button
                variant="outline"
                className="text-status-error border-status-error/40 hover:bg-status-error/10"
                onClick={handleDeleteAccount}
                disabled={!deleteConfirm}
                loading={deleteBusy}
                leftIcon={<Trash2 size={14} />}
              >
                Permanently delete my account
              </Button>
            </div>
          )}
        </section>
      )}

      {/* Account meta */}
      <section className="bg-surface-1 border border-border rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-content-primary">Account Details</h2>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-content-tertiary mb-0.5">Email</dt>
            <dd className="text-content-primary font-medium">{user?.email ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-content-tertiary mb-0.5">Role</dt>
            <dd className="text-content-primary font-medium capitalize">{user?.role ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-content-tertiary mb-0.5">Auth method</dt>
            <dd className="text-content-primary font-medium">{user?.source === 'v2_jwt' ? 'v2 JWT' : 'Legacy session'}</dd>
          </div>
          <div>
            <dt className="text-xs text-content-tertiary mb-0.5">User ID</dt>
            <dd className="text-content-primary font-medium">{user?.user_id ?? 'N/A (legacy)'}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
