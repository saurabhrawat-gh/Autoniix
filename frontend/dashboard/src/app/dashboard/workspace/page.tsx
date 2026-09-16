"use client";

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
import { useEffect, useState, useCallback } from "react";
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
  Bell,
  Lock,
  SlidersHorizontal,
} from "@/lib/components/Icon";
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
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/lib/ui";
import { workspaceApi, brandsApi, membersApi, invitesApi, workspaceEntitySettingsApi } from "@/lib/api-v2";
import { useToast } from "@/lib/toast";
import { confirmDialog, promptDialog } from "@/lib/components/ConfirmDialog";

type Workspace = {
  id: number;
  name: string;
  slug: string;
  plan: string;
  mode: "solo" | "teams";
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

const ROLES = ["owner", "member", "viewer"] as const;
const INVITE_ROLES = ["member", "viewer"] as const;
const roleLabel = (r: string) => r.charAt(0).toUpperCase() + r.slice(1);

const PLAN_SEAT_LIMITS: Record<string, number | null> = {
  starter: 3,
  growth: 10,
  scale: null,
};
const planLabel = (p: string) => p.charAt(0).toUpperCase() + p.slice(1);

const ROLE_BADGE: Record<string, "neutral" | "success" | "warning" | "info" | "secondary"> = {
  owner: "success",
  member: "info",
  viewer: "secondary",
};

type WsSettingSchema = {
  label: string;
  description: string;
  type: "select" | "number" | "toggle";
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
};
const WS_CONTENT_SCHEMA: Record<string, WsSettingSchema> = {
  "content.default_mode": {
    label: "Default Content Mode",
    description: "Default for all channels in this workspace unless overridden per-channel.",
    type: "select",
    options: [
      { value: "short", label: "Short-form" },
      { value: "long", label: "Long-form" },
      { value: "mixed", label: "Mixed" },
    ],
  },
  "content.quality_threshold": {
    label: "Quality Threshold",
    description: "Minimum quality score (0–1.0) required for a video to pass QA.",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
  },
  "content.human_review_required": {
    label: "Human Review Required",
    description: "Force all channels in this workspace through human review.",
    type: "toggle",
  },
  "content.auto_approve_threshold": {
    label: "Auto-Approve Threshold",
    description: "Quality score above which content auto-approves without human review.",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
  },
  "content.max_daily_videos": {
    label: "Max Daily Videos",
    description: "Cap on videos published per day across all channels in this workspace.",
    type: "number",
    min: 0,
    max: 9999,
    step: 1,
    unit: "videos/day",
  },
};
const WS_BUDGET_SCHEMA: Record<string, WsSettingSchema> = {
  "budget.per_video_usd": {
    label: "Per-Video Budget",
    description: "Maximum API and compute spend per video job in this workspace.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
  "budget.daily_limit_usd": {
    label: "Daily Cost Limit",
    description: "Hard ceiling on daily API/compute costs for this workspace.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
  "budget.monthly_limit_usd": {
    label: "Monthly Budget",
    description: "Soft monthly spend cap — triggers an alert when reached.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
};

export default function WorkspacePage() {
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [ws, setWs] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviting, setInviting] = useState(false);
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [monthlyBudget, setMonthlyBudget] = useState<string>("");
  const [logoUrl, setLogoUrl] = useState("");
  const [savingWs, setSavingWs] = useState(false);
  const [savingMode, setSavingMode] = useState(false);

  const [slackWebhook, setSlackWebhook] = useState("");
  const [savingSlack, setSavingSlack] = useState(false);

  const [entityMap, setEntityMap] = useState<Record<string, { value: unknown; locked: boolean }>>({});
  const [entityEdits, setEntityEdits] = useState<Record<string, unknown>>({});
  const [entityLocked, setEntityLocked] = useState<Record<string, boolean>>({});
  const [savingEntityKey, setSavingEntityKey] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [w, m, b, inv, intg, es] = await Promise.all([
        workspaceApi.get(),
        membersApi.list().catch(() => ({ data: [] as Member[] })),
        brandsApi.list().catch(() => ({ data: [] as Brand[] })),
        invitesApi.list().catch(() => ({ data: [] as Invite[] })),
        workspaceApi.getIntegrations().catch(() => ({ data: { slack_webhook_url: null } })),
        workspaceEntitySettingsApi.get().catch(() => ({ data: [] as any[] })),
      ]);
      const wd: Workspace | null = (w as any).data;
      setWs(wd);
      if (wd) {
        setName(wd.name || "");
        setTimezone(wd.timezone || "");
        setMonthlyBudget(wd.monthly_budget_usd != null ? String(wd.monthly_budget_usd) : "");
        setLogoUrl(wd.logo_url || "");
      }
      setMembers(((m as any).data || []) as Member[]);
      setBrands(((b as any).data || []) as Brand[]);
      setInvites(((inv as any).data || []) as Invite[]);
      setSlackWebhook((intg as any).data?.slack_webhook_url || "");
      const esMap: Record<string, { value: unknown; locked: boolean }> = {};
      for (const row of (es as any).data || []) esMap[row.key] = { value: row.value, locked: row.locked };
      setEntityMap(esMap);
    } catch (e: any) {
      showToast(e?.message || "Failed to load workspace", "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveWorkspace = async () => {
    setSavingWs(true);
    try {
      const payload: any = {};
      if (name !== ws?.name) payload.name = name;
      if (timezone !== ws?.timezone) payload.timezone = timezone;
      if (logoUrl !== (ws?.logo_url || "")) payload.logo_url = logoUrl || null;
      const budgetNum = monthlyBudget ? Number(monthlyBudget) : null;
      if (budgetNum !== ws?.monthly_budget_usd) payload.monthly_budget_usd = budgetNum;
      if (Object.keys(payload).length === 0) {
        showToast("No changes to save", "info");
        return;
      }
      await workspaceApi.update(payload);
      showToast("Workspace updated", "success");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Save failed", "error");
    } finally {
      setSavingWs(false);
    }
  };

  const updateRole = async (userId: number, role: string) => {
    try {
      await membersApi.setRole(userId, role);
      showToast(`Role updated to ${role}`, "success");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Failed to update role", "error");
    }
  };

  const removeMember = async (m: Member) => {
    const ok = await confirmDialog({
      title: `Remove ${m.display_name || m.email}?`,
      description: "They will lose access to this workspace immediately.",
      destructive: true,
      confirmLabel: "Remove",
    });
    if (!ok) return;
    try {
      await membersApi.remove(m.user_id);
      showToast("Member removed", "success");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Failed to remove member", "error");
    }
  };

  const sendInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setLastInviteUrl(null);
    try {
      const r = await invitesApi.create(inviteEmail.trim(), inviteRole);
      setLastInviteUrl((r as any).invite_url || null);
      showToast(`Invite sent to ${inviteEmail}`, "success");
      setInviteEmail("");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Failed to send invite", "error");
    } finally {
      setInviting(false);
    }
  };

  const revokeInvite = async (inv: Invite) => {
    const ok = await confirmDialog({
      title: `Revoke invite for ${inv.email}?`,
      description: "The invite link will stop working immediately.",
      destructive: true,
      confirmLabel: "Revoke",
    });
    if (!ok) return;
    try {
      await invitesApi.revoke(inv.id);
      showToast("Invite revoked", "success");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Failed to revoke invite", "error");
    }
  };

  const copyInviteUrl = (url: string) => {
    const full = `${window.location.origin}${url}`;
    navigator.clipboard.writeText(full).then(() => showToast("Invite link copied", "success"));
  };

  const saveSlack = async () => {
    setSavingSlack(true);
    try {
      await workspaceApi.updateIntegrations({ slack_webhook_url: slackWebhook.trim() || null });
      showToast("Slack webhook saved", "success");
    } catch (e: any) {
      showToast(e?.message || "Failed to save webhook", "error");
    } finally {
      setSavingSlack(false);
    }
  };

  const esVal = (key: string): unknown => (key in entityEdits ? entityEdits[key] : (entityMap[key]?.value ?? null));
  const esLocked = (key: string): boolean =>
    key in entityLocked ? entityLocked[key] : (entityMap[key]?.locked ?? false);
  const setEsVal = (key: string, val: unknown) => setEntityEdits((prev) => ({ ...prev, [key]: val }));
  const setEsLocked = (key: string, locked: boolean) => setEntityLocked((prev) => ({ ...prev, [key]: locked }));
  const saveEntitySetting = async (key: string) => {
    setSavingEntityKey(key);
    try {
      await workspaceEntitySettingsApi.set(key, esVal(key), esLocked(key));
      setEntityMap((prev) => ({ ...prev, [key]: { value: esVal(key), locked: esLocked(key) } }));
      setEntityEdits((prev) => {
        const n = { ...prev };
        delete n[key];
        return n;
      });
      setEntityLocked((prev) => {
        const n = { ...prev };
        delete n[key];
        return n;
      });
      showToast("Setting saved", "success");
    } catch (e: any) {
      showToast(e?.message || "Save failed", "error");
    } finally {
      setSavingEntityKey(null);
    }
  };

  const createBrand = async () => {
    const name = await promptDialog({
      title: "Create new brand",
      description: "A brand groups channels under one identity (logo, voice, palette).",
      label: "Brand name",
      placeholder: "e.g. Body Signals",
      confirmLabel: "Create",
    });
    if (!name) return;
    try {
      await brandsApi.create({ name });
      showToast("Brand created", "success");
      refresh();
    } catch (e: any) {
      showToast(e?.message || "Failed to create brand", "error");
    }
  };

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
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Boxes size={20} className="text-accent" />
            Workspace
          </h1>
          <p className="text-sm text-content-secondary mt-0.5">Manage workspace settings, members, and brands.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh} leftIcon={<RotateCw size={14} />}>
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="general">
        <TabsList className="mb-4">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="brands">Brands</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="defaults">
            <SlidersHorizontal size={13} className="mr-1.5" />
            Defaults
          </TabsTrigger>
        </TabsList>

        {/* ── General ─────────────────────────────────────────────── */}
        <TabsContent value="general">
          {/* Workspace info */}
          <Card variant="elevated" padding="lg" className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-content-primary">Workspace Info</h2>
                <p className="text-xs text-content-tertiary mt-0.5">
                  Top-level identity, plan, and budget for this tenant.
                </p>
              </div>
              {ws && (
                <Badge variant="info" size="sm">
                  Plan: {ws.plan}
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="ws-name">Name</Label>
                <Input id="ws-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ws-tz">Timezone</Label>
                <Input
                  id="ws-tz"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="e.g. Asia/Kolkata"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ws-budget">Monthly Budget (USD)</Label>
                <Input
                  id="ws-budget"
                  type="number"
                  value={monthlyBudget}
                  onChange={(e) => setMonthlyBudget(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ws-logo">Logo URL</Label>
                <Input
                  id="ws-logo"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
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
        </TabsContent>

        {/* ── Members ─────────────────────────────────────────────── */}
        <TabsContent value="members" className="space-y-4">
          {/* Members */}
          <Card variant="elevated" padding="lg" className="space-y-4">
            {(() => {
              const plan = ws?.plan ?? "starter";
              const limit = plan in PLAN_SEAT_LIMITS ? PLAN_SEAT_LIMITS[plan] : PLAN_SEAT_LIMITS.starter;
              const pendingCount = invites.filter((i) => !i.accepted_at).length;
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
                      {planLabel(plan)} — {used}/{limit ?? "∞"} seats
                    </Badge>
                    <span className="text-xs text-content-tertiary">
                      ({members.length} member{members.length === 1 ? "" : "s"}
                      {pendingCount > 0 ? ` + ${pendingCount} pending` : ""})
                    </span>
                  </div>
                  {nearLimit && (
                    <Button
                      size="sm"
                      variant={atLimit ? "primary" : "outline"}
                      onClick={() =>
                        showToast("Billing upgrade flow is coming soon — contact support to upgrade today.", "info")
                      }
                    >
                      {atLimit ? "Upgrade plan" : "Upgrade — seats almost full"}
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
                {members.map((m) => (
                  <div
                    key={m.user_id}
                    className="flex items-center justify-between gap-3 p-3 rounded-lg border border-border bg-surface-1"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm text-content-primary truncate">{m.display_name || m.email}</p>
                      <p className="text-xs text-content-tertiary truncate">{m.email}</p>
                    </div>
                    <Badge variant={ROLE_BADGE[m.role] || "neutral"} size="sm">
                      <ShieldCheck size={10} className="mr-1" />
                      {roleLabel(m.role)}
                    </Badge>
                    <Select value={m.role} onValueChange={(role: string) => updateRole(m.user_id, role)}>
                      <SelectTrigger className="w-[120px] h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {roleLabel(r)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {m.role !== "owner" && (
                      <Button size="sm" variant="ghost" onClick={() => removeMember(m)} leftIcon={<Trash2 size={12} />}>
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
                    {ws?.mode === "teams"
                      ? "Teams mode is active — you can invite members."
                      : "Solo mode — enable Teams mode to invite collaborators."}
                  </p>
                </div>
              </div>
              {/* Solo / Teams segmented toggle */}
              <div className="flex shrink-0 rounded-lg border border-border overflow-hidden text-xs font-medium">
                <button
                  className={`px-3 py-1.5 transition-colors ${
                    (ws?.mode ?? "solo") === "solo"
                      ? "bg-surface-2 text-content-primary"
                      : "text-content-tertiary hover:text-content-secondary"
                  }`}
                  disabled={savingMode}
                  onClick={async () => {
                    if (ws?.mode === "solo") return;
                    setSavingMode(true);
                    try {
                      await workspaceApi.setMode("solo");
                      setWs((w) => (w ? { ...w, mode: "solo" } : w));
                      showToast("Switched to Solo mode", "success");
                    } catch (e: any) {
                      showToast(e?.message || "Failed", "error");
                    } finally {
                      setSavingMode(false);
                    }
                  }}
                >
                  Solo
                </button>
                <button
                  className={`px-3 py-1.5 transition-colors ${
                    ws?.mode === "teams"
                      ? "bg-accent text-content-inverse"
                      : "text-content-tertiary hover:text-content-secondary"
                  }`}
                  disabled={savingMode}
                  onClick={async () => {
                    if (ws?.mode === "teams") return;
                    setSavingMode(true);
                    try {
                      await workspaceApi.setMode("teams");
                      setWs((w) => (w ? { ...w, mode: "teams" } : w));
                      showToast("Switched to Teams mode — you can now invite members!", "success");
                    } catch (e: any) {
                      showToast(e?.message || "Failed", "error");
                    } finally {
                      setSavingMode(false);
                    }
                  }}
                >
                  Teams
                </button>
              </div>
            </div>

            {ws?.mode !== "teams" ? (
              /* Solo mode callout */
              <div className="rounded-lg border border-border bg-surface-1 p-4 text-sm text-content-secondary space-y-1">
                <p className="font-medium text-content-primary">You&apos;re in Solo mode</p>
                <p>
                  Switch to <strong>Teams</strong> above to enable collaboration.
                </p>
              </div>
            ) : (
              /* Teams mode — direct user to the Teams page for invite management */
              <div className="rounded-lg border border-border bg-surface-1 p-4 flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm font-medium text-content-primary">Teams mode is active</p>
                  <p className="text-sm text-content-secondary">Manage members and invitations on the Teams page.</p>
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
        </TabsContent>

        {/* ── Integrations ────────────────────────────────────────── */}
        <TabsContent value="integrations">
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
                  onChange={(e) => setSlackWebhook(e.target.value)}
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
        </TabsContent>

        {/* ── Brands ──────────────────────────────────────────────── */}
        <TabsContent value="brands">
          {/* Brands */}
          <Card variant="elevated" padding="lg" className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Palette size={16} className="text-content-secondary" />
                <h2 className="text-sm font-semibold text-content-primary">Brands</h2>
                <Badge variant="secondary" size="sm">
                  {brands.length}
                </Badge>
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
                {brands.map((b) => (
                  <div key={b.id} className="p-3 rounded-lg border border-border bg-surface-1 flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-semibold shrink-0"
                      style={{ backgroundColor: b.primary_color || "#6366f1" }}
                    >
                      {b.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm text-content-primary truncate">{b.name}</p>
                      <p className="text-xs text-content-tertiary truncate">
                        {b.description || b.slug || "No description"}
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
        </TabsContent>

        {/* ── Defaults ────────────────────────────────────────────── */}
        <TabsContent value="defaults" className="space-y-6">
          <p className="text-sm text-content-secondary">
            Set workspace-level defaults for content and budget. These override system defaults and can themselves be
            overridden per-channel unless locked.{" "}
            <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
              <Lock size={11} /> Locking a setting blocks channel-level overrides.
            </span>
          </p>
          <div>
            <h2 className="text-xs font-semibold text-content-secondary mb-3">Content</h2>
            <div className="space-y-3">
              {Object.entries(WS_CONTENT_SCHEMA).map(([key, schema]) => (
                <WsEntitySettingRow
                  key={key}
                  esKey={key}
                  schema={schema}
                  value={esVal(key)}
                  locked={esLocked(key)}
                  saving={savingEntityKey === key}
                  onChange={(v) => setEsVal(key, v)}
                  onLockedChange={(l) => setEsLocked(key, l)}
                  onSave={() => saveEntitySetting(key)}
                />
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-xs font-semibold text-content-secondary mb-3">Budget</h2>
            <div className="space-y-3">
              {Object.entries(WS_BUDGET_SCHEMA).map(([key, schema]) => (
                <WsEntitySettingRow
                  key={key}
                  esKey={key}
                  schema={schema}
                  value={esVal(key)}
                  locked={esLocked(key)}
                  saving={savingEntityKey === key}
                  onChange={(v) => setEsVal(key, v)}
                  onLockedChange={(l) => setEsLocked(key, l)}
                  onSave={() => saveEntitySetting(key)}
                />
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function WsEntitySettingRow({
  esKey,
  schema,
  value,
  locked,
  saving,
  onChange,
  onLockedChange,
  onSave,
}: {
  esKey: string;
  schema: WsSettingSchema;
  value: unknown;
  locked: boolean;
  saving: boolean;
  onChange: (v: unknown) => void;
  onLockedChange: (locked: boolean) => void;
  onSave: () => void;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="text-sm font-medium text-content-primary">{schema.label}</div>
            {locked && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-status-warning bg-status-warning/10 px-1.5 py-0.5 rounded">
                <Lock size={9} />
                Locked
              </span>
            )}
          </div>
          <div className="text-xs text-content-tertiary">{schema.description}</div>
          <code className="text-[10px] text-content-tertiary/50 font-mono mt-1 block">{esKey}</code>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {schema.type === "toggle" ? (
            <Switch
              checked={value === true || value === "true"}
              onCheckedChange={(v) => onChange(v)}
              aria-label={schema.label}
            />
          ) : schema.type === "select" ? (
            <Select value={String(value ?? "")} onValueChange={(v) => onChange(v)}>
              <SelectTrigger className="w-40 h-8 text-xs">
                <SelectValue placeholder="Select…" />
              </SelectTrigger>
              <SelectContent>
                {schema.options?.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <div className="flex items-center gap-1.5">
              <Input
                type="number"
                value={value === null || value === undefined ? "" : String(value)}
                onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
                min={schema.min}
                max={schema.max}
                step={schema.step}
                className="w-28 h-8 text-xs"
              />
              {schema.unit && <span className="text-xs text-content-tertiary">{schema.unit}</span>}
            </div>
          )}
          <Button size="sm" onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
        <Switch
          checked={locked}
          onCheckedChange={onLockedChange}
          aria-label={`Lock ${schema.label}`}
          className="scale-75 origin-left"
        />
        <span className="text-xs text-content-tertiary">Lock — prevent channels from overriding this setting</span>
      </div>
    </div>
  );
}
