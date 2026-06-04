'use client';

/**
 * Workspace (multi-tenant) management page.
 *
 * Sections:
 *   1. Workspace info  — name, plan, timezone, monthly budget, logo
 *   2. Members         — list, role change, remove (owner/admin only)
 *   3. Brands          — top-level brand entities under this workspace
 *
 * Backend: src/services/dashboard/v2/workspace.py
 */
import { useEffect, useState, useCallback } from 'react';
import {
  Boxes,
  Users,
  Palette,
  Save,
  Plus,
  RotateCw,
  ShieldCheck,
  Trash2,
  ExternalLink,
  Mail,
  Link2,
  Clock,
  Check,
} from '@/lib/components/Icon';
import {
  Button,
  Input,
  Label,
  Card,
  Badge,
  Skeleton,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/lib/ui';
import { workspaceApi, brandsApi, membersApi, invitesApi } from '@/lib/api-v2';
import { Bell } from '@/lib/components/Icon';
import { useToast } from '@/lib/toast';
import { confirmDialog, promptDialog } from '@/lib/components/ConfirmDialog';

type Workspace = {
  id: number;
  name: string;
  slug: string;
  plan: string;
  mode: 'solo' | 'teams';
  timezone: string;
  monthly_budget_usd: number | null;
  logo_url: string | null;
  billing_email: string | null;
};

type Member = {
  user_id: number;
  email: string;
  display_name: string | null;
  role: string;
  joined_at: string;
};

type Brand = {
  id: number;
  name: string;
  slug: string | null;
  description: string | null;
  primary_color: string | null;
  logo_url: string | null;
};

type Invite = {
  id: number;
  email: string;
  role: string;
  accepted_at: string | null;
  expires_at: string;
  created_at: string;
  invite_url?: string;
};

const ROLES = ['owner', 'member', 'viewer'] as const;
const INVITE_ROLES = ['member', 'viewer'] as const;
const roleLabel = (r: string) => r.charAt(0).toUpperCase() + r.slice(1);

// Mirror of backend plan seat limits (src/api/billing/plans.py).
// Update both sides if plan tiers change. AE-23 enforcement is deferred;
// this is informational only.
const PLAN_SEAT_LIMITS: Record<string, number | null> = {
  starter: 3,
  growth: 10,
  scale: null, // unlimited
};
const planLabel = (p: string) => p.charAt(0).toUpperCase() + p.slice(1);

const ROLE_BADGE: Record<string, 'neutral' | 'success' | 'warning' | 'info' | 'secondary'> = {
  owner: 'success',
  member: 'info',
  viewer: 'secondary',
};

export default function WorkspacePage() {
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [ws, setWs] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [inviting, setInviting] = useState(false);
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);

  // Editable workspace fields
  const [name, setName] = useState('');
  const [timezone, setTimezone] = useState('');
  const [monthlyBudget, setMonthlyBudget] = useState<string>('');
  const [logoUrl, setLogoUrl] = useState('');
  const [savingWs, setSavingWs] = useState(false);
  const [savingMode, setSavingMode] = useState(false);

  // Integrations
  const [slackWebhook, setSlackWebhook] = useState('');
  const [savingSlack, setSavingSlack] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [w, m, b, inv, intg] = await Promise.all([
        workspaceApi.get(),
        membersApi.list().catch(() => ({ data: [] as Member[] })),
        brandsApi.list().catch(() => ({ data: [] as Brand[] })),
        invitesApi.list().catch(() => ({ data: [] as Invite[] })),
        workspaceApi.getIntegrations().catch(() => ({ data: { slack_webhook_url: null } })),
      ]);
      const wd: Workspace | null = (w as any).data;
      setWs(wd);
      if (wd) {
        setName(wd.name || '');
        setTimezone(wd.timezone || '');
        setMonthlyBudget(wd.monthly_budget_usd != null ? String(wd.monthly_budget_usd) : '');
        setLogoUrl(wd.logo_url || '');
      }
      setMembers(((m as any).data || []) as Member[]);
      setBrands(((b as any).data || []) as Brand[]);
      setInvites(((inv as any).data || []) as Invite[]);
      setSlackWebhook((intg as any).data?.slack_webhook_url || '');
    } catch (e: any) {
      showToast(e?.message || 'Failed to load workspace', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { refresh(); }, [refresh]);

  // Workspace save
  const saveWorkspace = async () => {
    setSavingWs(true);
    try {
      const payload: any = {};
      if (name !== ws?.name) payload.name = name;
      if (timezone !== ws?.timezone) payload.timezone = timezone;
      if (logoUrl !== (ws?.logo_url || '')) payload.logo_url = logoUrl || null;
      const budgetNum = monthlyBudget ? Number(monthlyBudget) : null;
      if (budgetNum !== ws?.monthly_budget_usd) payload.monthly_budget_usd = budgetNum;
      if (Object.keys(payload).length === 0) {
        showToast('No changes to save', 'info');
        return;
      }
      await workspaceApi.update(payload);
      showToast('Workspace updated', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Save failed', 'error');
    } finally {
      setSavingWs(false);
    }
  };

  // Member actions
  const updateRole = async (userId: number, role: string) => {
    try {
      await membersApi.setRole(userId, role);
      showToast(`Role updated to ${role}`, 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to update role', 'error');
    }
  };

  const removeMember = async (m: Member) => {
    const ok = await confirmDialog({
      title: `Remove ${m.display_name || m.email}?`,
      description: 'They will lose access to this workspace immediately.',
      destructive: true,
      confirmLabel: 'Remove',
    });
    if (!ok) return;
    try {
      await membersApi.remove(m.user_id);
      showToast('Member removed', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to remove member', 'error');
    }
  };

  // Invite actions
  const sendInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setLastInviteUrl(null);
    try {
      const r = await invitesApi.create(inviteEmail.trim(), inviteRole);
      setLastInviteUrl((r as any).invite_url || null);
      showToast(`Invite sent to ${inviteEmail}`, 'success');
      setInviteEmail('');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to send invite', 'error');
    } finally {
      setInviting(false);
    }
  };

  const revokeInvite = async (inv: Invite) => {
    const ok = await confirmDialog({
      title: `Revoke invite for ${inv.email}?`,
      description: 'The invite link will stop working immediately.',
      destructive: true,
      confirmLabel: 'Revoke',
    });
    if (!ok) return;
    try {
      await invitesApi.revoke(inv.id);
      showToast('Invite revoked', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to revoke invite', 'error');
    }
  };

  const copyInviteUrl = (url: string) => {
    const full = `${window.location.origin}${url}`;
    navigator.clipboard.writeText(full).then(() => showToast('Invite link copied', 'success'));
  };

  // Slack integration
  const saveSlack = async () => {
    setSavingSlack(true);
    try {
      await workspaceApi.updateIntegrations({ slack_webhook_url: slackWebhook.trim() || null });
      showToast('Slack webhook saved', 'success');
    } catch (e: any) {
      showToast(e?.message || 'Failed to save webhook', 'error');
    } finally {
      setSavingSlack(false);
    }
  };

  // Brand actions
  const createBrand = async () => {
    const name = await promptDialog({
      title: 'Create new brand',
      description: 'A brand groups channels under one identity (logo, voice, palette).',
      label: 'Brand name',
      placeholder: 'e.g. Body Signals',
      confirmLabel: 'Create',
    });
    if (!name) return;
    try {
      await brandsApi.create({ name });
      showToast('Brand created', 'success');
      refresh();
    } catch (e: any) {
      showToast(e?.message || 'Failed to create brand', 'error');
    }
  };

  // Render
  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Boxes size={20} className="text-accent" />
            Workspace
          </h1>
          <p className="text-sm text-content-secondary mt-0.5">
            Manage workspace settings, members, and brands.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh} leftIcon={<RotateCw size={14} />}>
          Refresh
        </Button>
      </div>

      {/* Workspace info */}
      <Card variant="elevated" padding="lg" className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-content-primary">Workspace Info</h2>
            <p className="text-xs text-content-tertiary mt-0.5">Top-level identity, plan, and budget for this tenant.</p>
          </div>
          {ws && <Badge variant="info" size="sm">Plan: {ws.plan}</Badge>}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="ws-name">Name</Label>
            <Input id="ws-name" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ws-tz">Timezone</Label>
            <Input id="ws-tz" value={timezone} onChange={e => setTimezone(e.target.value)} placeholder="e.g. Asia/Kolkata" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ws-budget">Monthly Budget (USD)</Label>
            <Input
              id="ws-budget"
              type="number"
              value={monthlyBudget}
              onChange={e => setMonthlyBudget(e.target.value)}
              placeholder="0.00"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ws-logo">Logo URL</Label>
            <Input
              id="ws-logo"
              value={logoUrl}
              onChange={e => setLogoUrl(e.target.value)}
              placeholder="https://…"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={saveWorkspace} loading={savingWs} leftIcon={<Save size={14} />}>
            Save changes
          </Button>
        </div>
      </Card>

      {/* Members */}
      <Card variant="elevated" padding="lg" className="space-y-4">
        {(() => {
          const plan = ws?.plan ?? 'starter';
          const limit = plan in PLAN_SEAT_LIMITS ? PLAN_SEAT_LIMITS[plan] : PLAN_SEAT_LIMITS.starter;
          const pendingCount = invites.filter(i => !i.accepted_at).length;
          const used = members.length + pendingCount;
          const ratio = limit ? used / limit : 0;
          const nearLimit = limit !== null && ratio >= 0.8;
          const atLimit = limit !== null && used >= limit;
          return (
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <Users size={16} className="text-content-secondary" />
                <h2 className="text-sm font-semibold text-content-primary">Members</h2>
                <Badge variant="secondary" size="sm">
                  {planLabel(plan)} — {used}/{limit ?? '∞'} seats
                </Badge>
                <span className="text-xs text-content-tertiary">
                  ({members.length} member{members.length === 1 ? '' : 's'}
                  {pendingCount > 0 ? ` + ${pendingCount} pending` : ''})
                </span>
              </div>
              {nearLimit && (
                <Button
                  size="sm"
                  variant={atLimit ? 'primary' : 'outline'}
                  onClick={() => showToast('Billing upgrade flow is coming soon — contact support to upgrade today.', 'info')}
                >
                  {atLimit ? 'Upgrade plan' : 'Upgrade — seats almost full'}
                </Button>
              )}
            </div>
          );
        })()}

        {members.length === 0 ? (
          <p className="text-sm text-content-tertiary py-6 text-center">
            No members yet. Invite users from the Users page.
          </p>
        ) : (
          <div className="space-y-2">
            {members.map(m => (
              <div
                key={m.user_id}
                className="flex items-center justify-between gap-3 p-3 rounded-lg border border-border bg-surface-1"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm text-content-primary truncate">
                    {m.display_name || m.email}
                  </p>
                  <p className="text-xs text-content-tertiary truncate">{m.email}</p>
                </div>
                <Badge variant={ROLE_BADGE[m.role] || 'neutral'} size="sm">
                  <ShieldCheck size={10} className="mr-1" />
                  {roleLabel(m.role)}
                </Badge>
                <Select value={m.role} onValueChange={(role: string) => updateRole(m.user_id, role)}>
                  <SelectTrigger className="w-[120px] h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map(r => (
                      <SelectItem key={r} value={r}>{roleLabel(r)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {m.role !== 'owner' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => removeMember(m)}
                    leftIcon={<Trash2 size={12} />}
                  >
                    Remove
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Collaboration Mode + Invitations */}
      <Card variant="elevated" padding="lg" className="space-y-5">
        {/* Mode toggle header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-content-secondary" />
            <div>
              <h2 className="text-sm font-semibold text-content-primary">Team Collaboration</h2>
              <p className="text-xs text-content-tertiary mt-0.5">
                {ws?.mode === 'teams'
                  ? 'Teams mode is active — you can invite members.'
                  : 'Solo mode — enable Teams mode to invite collaborators.'}
              </p>
            </div>
          </div>
          {/* Solo / Teams segmented toggle */}
          <div className="flex shrink-0 rounded-lg border border-border overflow-hidden text-xs font-medium">
            <button
              className={`px-3 py-1.5 transition-colors ${
                (ws?.mode ?? 'solo') === 'solo'
                  ? 'bg-surface-2 text-content-primary'
                  : 'text-content-tertiary hover:text-content-secondary'
              }`}
              disabled={savingMode}
              onClick={async () => {
                if (ws?.mode === 'solo') return;
                setSavingMode(true);
                try {
                  await workspaceApi.setMode('solo');
                  setWs(w => w ? { ...w, mode: 'solo' } : w);
                  showToast('Switched to Solo mode', 'success');
                } catch (e: any) { showToast(e?.message || 'Failed', 'error'); }
                finally { setSavingMode(false); }
              }}
            >
              Solo
            </button>
            <button
              className={`px-3 py-1.5 transition-colors ${
                ws?.mode === 'teams'
                  ? 'bg-accent text-content-inverse'
                  : 'text-content-tertiary hover:text-content-secondary'
              }`}
              disabled={savingMode}
              onClick={async () => {
                if (ws?.mode === 'teams') return;
                setSavingMode(true);
                try {
                  await workspaceApi.setMode('teams');
                  setWs(w => w ? { ...w, mode: 'teams' } : w);
                  showToast('Switched to Teams mode — you can now invite members!', 'success');
                } catch (e: any) { showToast(e?.message || 'Failed', 'error'); }
                finally { setSavingMode(false); }
              }}
            >
              Teams
            </button>
          </div>
        </div>

        {ws?.mode !== 'teams' ? (
          /* Solo mode callout */
          <div className="rounded-lg border border-border bg-surface-1 p-4 text-sm text-content-secondary space-y-1">
            <p className="font-medium text-content-primary">You&apos;re in Solo mode</p>
            <p>Switch to <strong>Teams</strong> above to enable collaboration.</p>
          </div>
        ) : (
          /* Teams mode — direct user to the Teams page for invite management */
          <div className="rounded-lg border border-border bg-surface-1 p-4 flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-1">
              <p className="text-sm font-medium text-content-primary">Teams mode is active</p>
              <p className="text-sm text-content-secondary">
                Manage members and invitations on the Teams page.
              </p>
            </div>
            <a
              href="/dashboard/teams"
              className="shrink-0 text-xs font-medium text-accent hover:underline flex items-center gap-1"
            >
              Go to Teams <ExternalLink size={11} />
            </a>
          </div>
        )}
      </Card>

      {/* Integrations */}
      <Card variant="elevated" padding="lg" className="space-y-4">
        <div className="flex items-center gap-2">
          <Bell size={16} className="text-content-secondary" />
          <h2 className="text-sm font-semibold text-content-primary">Integrations</h2>
        </div>
        <p className="text-xs text-content-tertiary">
          Connect a Slack webhook to receive invite notifications, budget alerts, and video completion pings.
        </p>
        <div className="space-y-2">
          <Label htmlFor="slack-webhook">Slack Incoming Webhook URL</Label>
          <div className="flex gap-2">
            <Input
              id="slack-webhook"
              value={slackWebhook}
              onChange={e => setSlackWebhook(e.target.value)}
              placeholder="https://hooks.slack.com/services/…"
              className="flex-1"
            />
            <Button onClick={saveSlack} loading={savingSlack} leftIcon={<Save size={14} />}>
              Save
            </Button>
          </div>
          {slackWebhook && (
            <p className="text-xs text-status-success flex items-center gap-1">
              <Check size={11} /> Webhook configured
            </p>
          )}
        </div>
      </Card>

      {/* Brands */}
      <Card variant="elevated" padding="lg" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Palette size={16} className="text-content-secondary" />
            <h2 className="text-sm font-semibold text-content-primary">Brands</h2>
            <Badge variant="secondary" size="sm">{brands.length}</Badge>
          </div>
          <Button size="sm" variant="primary" onClick={createBrand} leftIcon={<Plus size={14} />}>
            New brand
          </Button>
        </div>

        {brands.length === 0 ? (
          <p className="text-sm text-content-tertiary py-6 text-center">
            No brands yet. Brands group channels under one visual + voice identity.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {brands.map(b => (
              <div
                key={b.id}
                className="p-3 rounded-lg border border-border bg-surface-1 flex items-center gap-3"
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-semibold shrink-0"
                  style={{ backgroundColor: b.primary_color || '#6366f1' }}
                >
                  {b.name.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm text-content-primary truncate">{b.name}</p>
                  <p className="text-xs text-content-tertiary truncate">
                    {b.description || b.slug || 'No description'}
                  </p>
                </div>
                <Button size="sm" variant="ghost" rightIcon={<ExternalLink size={12} />}>
                  Open
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
