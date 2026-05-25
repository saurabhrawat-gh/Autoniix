'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Check, ChevronRight, Users, Youtube, Rocket, Building2 } from 'lucide-react';
import { workspaceApi, invitesApi, settingsApi, authApi, isLoggedIn } from '@/lib/api-v2';
import { Button, Input, Label } from '@/lib/ui';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/lib/theme';

const STEPS = [
  { id: 1, label: 'Your Workspace', icon: Building2 },
  { id: 2, label: 'Invite Team',    icon: Users },
  { id: 3, label: 'Connect YouTube', icon: Youtube },
  { id: 4, label: "You're all set",  icon: Rocket },
];

const ROLES = ['admin', 'producer', 'editor', 'viewer'];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep]               = useState(1);
  const [wsId, setWsId]               = useState<number | null>(null);
  const [wsName, setWsName]           = useState('');
  const [saving, setSaving]           = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole]   = useState('editor');
  const [inviting, setInviting]       = useState(false);
  const [inviteErr, setInviteErr]     = useState<string | null>(null);
  const [invitedEmails, setInvitedEmails] = useState<string[]>([]);
  const [loading, setLoading]         = useState(true);

  // Auth guard + load saved progress
  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    (async () => {
      try {
        const ws = await workspaceApi.get();
        const id: number = ws.data.id;
        setWsId(id);
        setWsName(ws.data.name ?? '');
        // Load saved onboarding step
        const settings = await settingsApi.get('workspace', String(id));
        const ob = settings.data.find(s => s.key === 'onboarding');
        if (ob?.value?.completed) { router.replace('/dashboard'); return; }
        if (ob?.value?.step) setStep(Number(ob.value.step));
      } catch { /* ignore */ } finally { setLoading(false); }
    })();
  }, [router]);

  const saveProgress = useCallback(async (s: number, completed = false) => {
    if (!wsId) return;
    try { await settingsApi.set('workspace', String(wsId), 'onboarding', { step: s, completed }); } catch {}
  }, [wsId]);

  async function goNext(nextStep: number) {
    setStep(nextStep);
    await saveProgress(nextStep);
  }

  // Step 1: confirm workspace name (create if none exists, update if renaming)
  async function saveWorkspaceName() {
    setSaving(true);
    try {
      if (!wsId) {
        const res = await authApi.createWorkspace(wsName.trim());
        setWsId(res.workspace_id);
      } else {
        await workspaceApi.update({ name: wsName.trim() });
      }
      await goNext(2);
    } finally { setSaving(false); }
  }

  // Step 2: invite
  async function sendInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true); setInviteErr(null);
    try {
      await invitesApi.create(inviteEmail, inviteRole);
      setInvitedEmails(prev => [...prev, inviteEmail]);
      setInviteEmail('');
    } catch (err: any) {
      setInviteErr(err?.message ?? 'Invite failed');
    } finally { setInviting(false); }
  }

  // Step 4: finish
  async function finish() {
    await saveProgress(4, true);
    router.push('/dashboard');
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin w-6 h-6 border-2 border-accent border-t-transparent rounded-full" />
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col">
      <div className="absolute top-5 right-5"><ThemeToggle /></div>

      {/* Progress bar header */}
      <header className="border-b border-border py-4 px-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center gap-0">
            {STEPS.map((s, i) => {
              const done = step > s.id;
              const active = step === s.id;
              const Icon = s.icon;
              return (
                <div key={s.id} className="flex items-center flex-1 last:flex-none">
                  <div className={cn(
                    'flex items-center gap-1.5 text-xs font-medium',
                    active ? 'text-accent' : done ? 'text-status-success' : 'text-content-tertiary'
                  )}>
                    <span className={cn(
                      'w-6 h-6 rounded-full flex items-center justify-center text-[10px] border',
                      active ? 'border-accent bg-accent text-white' :
                      done   ? 'border-status-success bg-status-success/10 text-status-success' :
                               'border-border bg-surface-1'
                    )}>
                      {done ? <Check size={10} /> : s.id}
                    </span>
                    <span className="hidden sm:inline truncate">{s.label}</span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className={cn(
                      'flex-1 h-px mx-2',
                      step > s.id ? 'bg-status-success/40' : 'bg-border'
                    )} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </header>

      {/* Step content */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md space-y-6">

          {/* Step 1 */}
          {step === 1 && (
            <div className="space-y-5">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-content-primary">Name your workspace</h1>
                <p className="text-sm text-content-tertiary">This is how your team will identify your workspace.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="ws-name" required>Workspace name</Label>
                <Input
                  id="ws-name" autoFocus required minLength={2} maxLength={60}
                  value={wsName} onChange={e => setWsName(e.target.value)}
                  placeholder="Acme Studios"
                />
              </div>
              <Button
                size="lg" className="w-full" loading={saving}
                disabled={wsName.trim().length < 2}
                onClick={saveWorkspaceName}
              >
                Continue <ChevronRight size={14} />
              </Button>
            </div>
          )}

          {/* Step 2 */}
          {step === 2 && (
            <div className="space-y-5">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-content-primary">Invite your team</h1>
                <p className="text-sm text-content-tertiary">Send invite links to your teammates. You can add more later.</p>
              </div>
              {invitedEmails.length > 0 && (
                <div className="space-y-1">
                  {invitedEmails.map(e => (
                    <div key={e} className="flex items-center gap-2 text-xs text-content-secondary">
                      <Check size={12} className="text-status-success" />{e}
                    </div>
                  ))}
                </div>
              )}
              <form onSubmit={sendInvite} className="space-y-3">
                {inviteErr && <p className="text-xs text-status-error">{inviteErr}</p>}
                <div className="space-y-2">
                  <Label htmlFor="inv-email">Email address</Label>
                  <Input
                    id="inv-email" type="email" required
                    value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
                    placeholder="teammate@example.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="inv-role">Role</Label>
                  <select
                    id="inv-role"
                    value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                    className="w-full rounded-md border border-border bg-surface-1 px-3 py-2 text-sm text-content-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
                  >
                    {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                  </select>
                </div>
                <Button type="submit" variant="secondary" className="w-full" loading={inviting} disabled={!inviteEmail}>
                  Send invite
                </Button>
              </form>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" className="flex-1 text-content-tertiary" onClick={() => goNext(3)}>
                  Skip for now
                </Button>
                {invitedEmails.length > 0 && (
                  <Button size="sm" className="flex-1" onClick={() => goNext(3)}>
                    Continue <ChevronRight size={14} />
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Step 3 */}
          {step === 3 && (
            <div className="space-y-5">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-content-primary">Connect a YouTube channel</h1>
                <p className="text-sm text-content-tertiary">Link your first channel to start automating content.</p>
              </div>
              <Button
                size="lg" className="w-full"
                onClick={() => router.push('/dashboard/channels?connect=1')}
              >
                <Youtube size={16} /> Connect with YouTube
              </Button>
              <Button variant="ghost" size="sm" className="w-full text-content-tertiary" onClick={() => goNext(4)}>
                Skip for now
              </Button>
            </div>
          )}

          {/* Step 4 */}
          {step === 4 && (
            <div className="space-y-5 text-center">
              <div className="w-14 h-14 rounded-full bg-status-success/10 flex items-center justify-center mx-auto">
                <Rocket size={28} className="text-status-success" />
              </div>
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-content-primary">You're all set!</h1>
                <p className="text-sm text-content-tertiary">
                  Your workspace <strong>{wsName}</strong> is ready. Let's start automating.
                </p>
              </div>
              {invitedEmails.length > 0 && (
                <p className="text-xs text-content-tertiary">
                  Invites sent to {invitedEmails.length} teammate{invitedEmails.length > 1 ? 's' : ''}.
                </p>
              )}
              <Button size="lg" className="w-full" onClick={finish}>
                Go to Dashboard <ChevronRight size={14} />
              </Button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
