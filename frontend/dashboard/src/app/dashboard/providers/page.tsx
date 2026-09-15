"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  providersApi,
  changeRequestsApi,
  youtubeOAuthApi,
  type ChangeRequest,
  type YouTubeOAuthStatus,
} from "@/lib/api-v2";
import { cn } from "@/lib/utils";
import { useToast } from "@/lib/toast";
import {
  Plug,
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  HelpCircle,
  Cpu,
  Activity,
  RotateCw,
  Plus,
  Loader2,
  ShieldCheck,
  Gauge,
  Network,
  Store,
  CheckCircle2,
  ExternalLink,
  Zap,
  Trash2,
  ClipboardCheck,
  Check,
  X,
  Clock,
  Link2,
  AlertCircle,
  Tv,
} from "@/lib/components/Icon";
import { Button } from "@/lib/ui";
import { promptDialog, confirmDialog } from "@/lib/components/ConfirmDialog";
import { useUrlState } from "@/lib/hooks/useUrlState";

const STUB_KINDS = new Set(["lut", "sfx", "music"]);

const ONBOARDING_STEPS = [
  {
    kind: "llm",
    label: "AI Writing (LLM)",
    why: "Required for scripting, research, hooks, and quality scoring.",
    urgent: true,
  },
  { kind: "tts", label: "Voice (TTS)", why: "Required to generate spoken narration for every video.", urgent: true },
  { kind: "image", label: "Thumbnail Image", why: "Required to generate video thumbnail art.", urgent: true },
  { kind: "search", label: "Web Search", why: "Used during research to find trends and facts.", urgent: false },
  {
    kind: "stock_footage",
    label: "Stock Footage",
    why: "Fetches free b-roll clips from Pexels / Pixabay.",
    urgent: false,
  },
  {
    kind: "storage",
    label: "Object Storage",
    why: "MinIO is self-hosted and configured automatically.",
    urgent: false,
  },
];

const KIND_META: Record<string, { icon: string; desc: string }> = {
  llm: { icon: "🧠", desc: "LLMs for script, research & critique" },
  tts: { icon: "🎙️", desc: "Voice synthesis (TTS)" },
  image: { icon: "🖼️", desc: "Image generation for thumbnails & assets" },
  search: { icon: "🔍", desc: "Web search & trend data" },
  storage: { icon: "💾", desc: "Object storage for media files" },
  stock_footage: { icon: "🎬", desc: "Stock footage & video clips" },
  music: { icon: "🎵", desc: "Background music & audio" },
  lut: { icon: "🎨", desc: "Color grading LUTs" },
  sfx: { icon: "🔊", desc: "Sound effects library" },
};

type HealthStatus = "healthy" | "failing" | "untested" | "partial";
function getCategoryHealth(healthy: number, failing: number, total: number): HealthStatus {
  if (total === 0) return "untested";
  if (failing === 0 && healthy > 0) return "healthy";
  if (healthy === 0 && failing > 0) return "failing";
  if (healthy > 0 && failing > 0) return "partial";
  return "untested";
}
const HEALTH_DOT: Record<HealthStatus, string> = {
  healthy: "bg-status-success",
  failing: "bg-status-error animate-pulse",
  partial: "bg-status-warning",
  untested: "bg-surface-3",
};
const HEALTH_LABEL: Record<HealthStatus, string> = {
  healthy: "All healthy",
  failing: "Degraded",
  partial: "Partial",
  untested: "Unconfigured",
};

const MODE_CHIP: Record<string, string> = {
  byok: "bg-surface-2 text-content-tertiary",
  system: "bg-surface-2 text-content-tertiary",
  marketplace: "bg-surface-2 text-content-tertiary",
  internal: "bg-status-warning/10 text-status-warning",
};

export default function ProvidersIndex() {
  const { showToast } = useToast();
  const PROVIDER_TABS = ["connected", "marketplace", "accounts"] as const;
  type ProvidersTab = (typeof PROVIDER_TABS)[number];
  const [tab, setTab] = useUrlState<ProvidersTab>("tab", {
    defaultValue: "connected",
    deserialize: (raw) => (PROVIDER_TABS.includes(raw as ProvidersTab) ? (raw as ProvidersTab) : "connected"),
  });
  const [cats, setCats] = useState<any[]>([]);
  const [kinds, setKinds] = useState<any[]>([]);
  const [creds, setCreds] = useState<any[]>([]);
  const [market, setMarket] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [addSectionFor, setAddSectionFor] = useState(false);
  const [addCategoryFor, setAddCategoryFor] = useState<string | null | false>(false);
  const [addProviderFor, setAddProviderFor] = useState<string | false>(false);
  const [restoring, setRestoring] = useState(false);
  const [probingAll, setProbingAll] = useState(false);
  const [marketFilter, setMarketFilter] = useState<string>("all");
  const [expandedKind, setExpandedKind] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [overdueRotations, setOverdueRotations] = useState<any[]>([]);
  const [showApprovals, setShowApprovals] = useState(false);
  const [approvals, setApprovals] = useState<ChangeRequest[]>([]);
  const [approvalsCount, setApprovalsCount] = useState(0);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [ytStatus, setYtStatus] = useState<YouTubeOAuthStatus | null>(null);
  const [ytLoading, setYtLoading] = useState(false);
  const [ytConnecting, setYtConnecting] = useState(false);
  const [ytDisconnecting, setYtDisconnecting] = useState(false);

  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (searchParams.get("addCategory") === "1") {
      setAddCategoryFor(null);
      const currentTab = searchParams.get("tab");
      const preserved = currentTab && currentTab !== "connected" ? `?tab=${currentTab}` : "";
      router.replace(`/dashboard/providers${preserved}`);
    }
  }, [searchParams, router]);

  const cleanSlate = async () => {
    const phrase = await promptDialog({
      title: "Wipe all provider data?",
      description: "This will DELETE every provider credential and chain in the database. " + "This cannot be undone.",
      label: "Type WIPE to confirm",
      placeholder: "WIPE",
      match: "WIPE",
      confirmLabel: "Wipe everything",
      destructive: true,
    });
    if (phrase === null) return;
    setResetting(true);
    try {
      const r = await providersApi.cleanSlate();
      showToast(`Wiped ${r.data.tables.length} table(s)`, "success");
      await refresh();
    } catch (e: any) {
      showToast(e?.message || "Reset failed", "error");
    } finally {
      setResetting(false);
    }
  };

  const restoreDefaults = async () => {
    setRestoring(true);
    try {
      await providersApi.restoreDefaults();
      showToast("Built-in sections & categories restored", "success");
      await refresh();
    } catch (e: any) {
      showToast(e?.message || "Restore failed", "error");
    } finally {
      setRestoring(false);
    }
  };

  const deleteSection = async (kind: string, label: string, isBuiltIn: boolean) => {
    const ok = isBuiltIn
      ? (await promptDialog({
          title: `Delete built-in section "${label}"?`,
          description:
            'This removes the section and ALL its categories, their credentials, and chains. Built-in sections can be brought back with "Restore defaults". This cannot be undone.',
          label: "Type DELETE to confirm",
          placeholder: "DELETE",
          match: "DELETE",
          confirmLabel: "Delete section",
          destructive: true,
        })) !== null
      : await confirmDialog({
          title: `Delete section "${label}"?`,
          description:
            "This removes the section and all its categories, credentials, and chains. This cannot be undone.",
          confirmLabel: "Delete section",
          destructive: true,
        });
    if (!ok) return;
    try {
      await providersApi.deleteKind(kind);
      showToast(`Section "${label}" removed`, "success");
      await refresh();
    } catch (e: any) {
      showToast(e?.message || "Delete failed", "error");
    }
  };

  const deleteCategory = async (name: string, label: string, isBuiltIn: boolean) => {
    const hint = isBuiltIn ? ' Use "Restore defaults" to bring it back.' : "";
    const ok = await confirmDialog({
      title: `Delete category "${label}"?`,
      description: `Removes the category and all its credentials and chains.${hint}`,
      confirmLabel: "Delete category",
      destructive: true,
    });
    if (!ok) return;
    try {
      await providersApi.deleteCategory(name);
      showToast(`Category "${label}" removed`, "success");
      await refresh();
    } catch (e: any) {
      showToast(e?.message || "Delete failed", "error");
    }
  };

  const deleteProvider = async (providerKey: string, displayName: string) => {
    const ok = await confirmDialog({
      title: `Remove "${displayName}" from the marketplace?`,
      description: "The provider card is removed. Existing credentials that already use it keep working.",
      confirmLabel: "Remove provider",
      destructive: true,
    });
    if (!ok) return;
    try {
      await providersApi.deleteMarketplaceProvider(providerKey);
      showToast(`"${displayName}" removed`, "success");
      await refresh();
    } catch (e: any) {
      showToast(e?.message || "Delete failed", "error");
    }
  };

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      providersApi.categories().then((r) => setCats(r.data || [])),
      providersApi
        .kinds()
        .then((r) => setKinds(r.data || []))
        .catch(() => {}),
      providersApi.credentials().then((r) => setCreds(r.data || [])),
      providersApi
        .marketplace()
        .then((r) => setMarket(r.data || []))
        .catch(() => {}),
      providersApi
        .allRotationStatus({ overdue_only: true })
        .then((r) => setOverdueRotations(r.data || []))
        .catch(() => {}),
      Promise.all([
        changeRequestsApi
          .list({ status: "pending_admin" })
          .then((r) => r.data.length)
          .catch(() => 0),
        changeRequestsApi
          .list({ status: "pending_owner" })
          .then((r) => r.data.length)
          .catch(() => 0),
      ])
        .then(([a, o]) => setApprovalsCount(a + o))
        .catch(() => setApprovalsCount(0)),
    ]).finally(() => {
      setLoading(false);
      window.dispatchEvent(new CustomEvent("providers:refresh"));
    });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const loadApprovals = async () => {
    setApprovalsLoading(true);
    try {
      const r = await changeRequestsApi.list({ status: "pending_admin" });
      const r2 = await changeRequestsApi.list({ status: "pending_owner" });
      const all = [...r.data, ...r2.data];
      setApprovals(all);
      setApprovalsCount(all.length);
    } catch {
      setApprovals([]);
    } finally {
      setApprovalsLoading(false);
    }
  };

  const openApprovals = () => {
    setShowApprovals(true);
    loadApprovals();
  };

  const doAdminReview = async (id: number, action: "approve_forward" | "reject") => {
    setReviewingId(id);
    try {
      await changeRequestsApi.adminReview(id, action, reviewNote || undefined);
      showToast(action === "approve_forward" ? "Forwarded to owner" : "Request rejected", "success");
      setReviewNote("");
      await loadApprovals();
    } catch (e: any) {
      showToast(e?.message || "Review failed", "error");
    } finally {
      setReviewingId(null);
    }
  };

  const doOwnerReview = async (id: number, action: "approve" | "reject") => {
    setReviewingId(id);
    try {
      await changeRequestsApi.ownerReview(id, action, reviewNote || undefined);
      showToast(action === "approve" ? "Change approved & applied" : "Request rejected", "success");
      setReviewNote("");
      await Promise.all([loadApprovals(), refresh()]);
    } catch (e: any) {
      showToast(e?.message || "Review failed", "error");
    } finally {
      setReviewingId(null);
    }
  };

  const loadYouTubeStatus = async () => {
    setYtLoading(true);
    try {
      const r = await youtubeOAuthApi.status();
      setYtStatus(r.data);
    } catch {
      setYtStatus(null);
    } finally {
      setYtLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "accounts") loadYouTubeStatus();
  }, [tab]);

  const connectYouTube = () => {
    setYtConnecting(true);
    const popup = window.open(youtubeOAuthApi.authUrl(), "youtube_oauth", "width=520,height=640,left=200,top=100");
    const onMsg = (e: MessageEvent) => {
      if (e.data?.type !== "youtube_oauth") return;
      window.removeEventListener("message", onMsg);
      setYtConnecting(false);
      if (e.data.ok) {
        showToast(`Connected: ${e.data.channel_name}`, "success");
        loadYouTubeStatus();
      } else {
        showToast(e.data.error || "OAuth failed", "error");
      }
      popup?.close();
    };
    window.addEventListener("message", onMsg);
  };

  const disconnectYouTube = async () => {
    setYtDisconnecting(true);
    try {
      await youtubeOAuthApi.disconnect();
      showToast("YouTube disconnected", "success");
      setYtStatus({ connected: false });
    } catch (e: any) {
      showToast(e?.message || "Disconnect failed", "error");
    } finally {
      setYtDisconnecting(false);
    }
  };

  const grouped: Record<string, any[]> = cats.reduce((acc: any, c: any) => {
    if (STUB_KINDS.has(c.kind)) return acc;
    (acc[c.kind] ||= []).push(c);
    return acc;
  }, {});

  const kindsByKey: Record<string, any> = kinds.reduce((acc: any, k: any) => {
    acc[k.kind] = k;
    return acc;
  }, {});
  const sectionMeta = (kind: string) => {
    const k = kindsByKey[kind];
    const fallback = KIND_META[kind] || { icon: "🔌", desc: "Provider category" };
    return {
      icon: k?.icon || fallback.icon,
      label: k?.label || kind.replace(/_/g, " "),
      desc: k?.description || fallback.desc,
      isBuiltIn: k ? !k.is_user_defined : true,
    };
  };

  const credsByCategory = (catName: string) => creds.filter((cr) => cr.category === catName);
  const countStatus = (catName: string) => {
    const mc = credsByCategory(catName);
    return {
      total: mc.length,
      healthy: mc.filter((c) => c.last_health_ok === true).length,
      failing: mc.filter((c) => c.last_health_ok === false).length,
    };
  };

  const totalCreds = creds.length;
  const totalHealthy = creds.filter((c) => c.last_health_ok === true).length;
  const totalFailing = creds.filter((c) => c.last_health_ok === false).length;
  const totalUntested = creds.filter((c) => c.last_health_ok === null).length;
  const unconnectedCount = market.filter((m) => !m.connected).length;

  const probeAll = async () => {
    if (!creds.length) return;
    setProbingAll(true);
    try {
      const r = await providersApi.probeAll();
      await refresh();
      const { ok, total } = r.summary;
      showToast(`Probe complete: ${ok}/${total} healthy`, ok === total ? "success" : "error");
    } catch (e: any) {
      showToast(e?.message || "Probe failed", "error");
    }
    setProbingAll(false);
  };

  const visibleMarket = market.filter((m: any) => !STUB_KINDS.has(m.category));
  const marketCategories = Array.from(new Set(visibleMarket.map((m: any) => m.category as string))).sort();
  const filteredMarket =
    marketFilter === "all" ? visibleMarket : visibleMarket.filter((m) => m.category === marketFilter);

  return (
    <main className="flex-1 px-4 sm:px-6 py-6 max-w-[1400px] mx-auto w-full space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-content-primary flex items-center gap-2">
            <Plug size={18} className="text-accent" /> Provider Operations
          </h1>
          <p className="text-xs text-content-tertiary mt-0.5">
            Plug-in / plug-out provider chains with health-based fallback. Secrets in Vault — never in DB.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="icon-sm" onClick={refresh} disabled={loading} aria-label="Refresh">
            <RotateCw size={13} className={cn(loading && "animate-spin")} />
          </Button>
          {approvalsCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={openApprovals}
              leftIcon={<ClipboardCheck size={12} />}
              title="Review provider changes requested by team members who don't have permission to apply them directly. As owner, you approve or reject each one here."
            >
              Approvals
              <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent font-semibold">
                {approvalsCount}
              </span>
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={probeAll}
            disabled={probingAll || totalCreds === 0}
            loading={probingAll}
            leftIcon={!probingAll ? <Zap size={12} /> : undefined}
          >
            Probe all
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={restoreDefaults}
            disabled={restoring}
            loading={restoring}
            leftIcon={!restoring ? <RotateCw size={12} /> : undefined}
            title="Recreate the built-in sections & categories if you deleted any by mistake. Does not touch your credentials."
          >
            Restore defaults
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={cleanSlate}
            disabled={resetting}
            loading={resetting}
            leftIcon={!resetting ? <Trash2 size={12} /> : undefined}
            title="Wipe ALL credentials, chains, routes (cannot be undone)"
            className="border-status-error/40 text-status-error hover:bg-status-error/10 hover:text-status-error"
          >
            Reset all
          </Button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { label: "Connected", value: totalCreds, color: "text-content-primary" },
          { label: "Healthy", value: totalHealthy, color: "text-status-success" },
          { label: "Failing", value: totalFailing, color: "text-status-error" },
          { label: "Available", value: unconnectedCount, color: "text-status-info" },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-border bg-surface-0 px-3 py-2">
            <div className={cn("text-xl font-bold tabular-nums leading-none", s.color)}>{s.value}</div>
            <div className="text-[10px] text-content-tertiary mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0.5 bg-surface-1 rounded-md p-0.5 w-fit">
        {(
          [
            ["connected", "Connected", totalCreds, <Activity key="i-c" size={11} />],
            ["marketplace", "Marketplace", unconnectedCount, <Store key="i-m" size={11} />],
            ["accounts", "Accounts", ytStatus?.connected ? 1 : 0, <Link2 key="i-a" size={11} />],
          ] as const
        ).map(([key, label, count, icon]) => (
          <Button
            key={key}
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setTab(key as any)}
            leftIcon={icon}
            className={cn(
              "h-7 px-3 text-xs",
              tab === key
                ? "bg-surface-0 text-content-primary shadow-sm hover:bg-surface-0"
                : "text-content-tertiary hover:text-content-secondary"
            )}
          >
            {label}
            {count > 0 && (
              <span className={cn("text-[10px]", tab === key ? "text-accent" : "text-content-tertiary")}>{count}</span>
            )}
          </Button>
        ))}
      </div>

      {/* ── Connected tab ── */}
      {tab === "connected" &&
        (loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-surface-0 p-4 animate-pulse h-28" />
            ))}
          </div>
        ) : Object.keys(grouped).length === 0 ? (
          <div className="py-20 text-center text-sm text-content-tertiary">
            <Cpu size={32} className="mx-auto mb-3 opacity-30" />
            No provider categories found. Ensure the backend is running.
          </div>
        ) : (
          <div className="space-y-6">
            {/* ── Rotation overdue banner ── */}
            {overdueRotations.length > 0 && (
              <div className="rounded-xl border border-status-error/30 bg-status-error/5 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={14} className="text-status-error" />
                  <span className="text-sm font-semibold text-status-error">
                    {overdueRotations.length} credential{overdueRotations.length !== 1 ? "s" : ""} with overdue key
                    rotation
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {overdueRotations.map((r: any) => (
                    <Link
                      key={r.id}
                      href={`/dashboard/providers/${encodeURIComponent(r.category)}`}
                      className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-surface-0 border border-status-error/30 text-status-error hover:bg-status-error/10 transition-colors"
                    >
                      {r.label} · {r.days_since_rotation}d
                    </Link>
                  ))}
                </div>
              </div>
            )}
            {/* ── Setup guide ── */}
            {(() => {
              const steps = ONBOARDING_STEPS.map((s) => {
                const catsForKind = grouped[s.kind] || [];
                const firstCat = catsForKind[0]?.name;
                const kindCreds = creds.filter(
                  (c: any) => cats.find((cc: any) => cc.name === c.category)?.kind === s.kind
                );
                return {
                  ...s,
                  catsForKind,
                  exists: catsForKind.length > 0,
                  target: firstCat
                    ? `/dashboard/providers/${encodeURIComponent(firstCat)}?add=1`
                    : "/dashboard/providers",
                  configured: kindCreds.length > 0,
                  healthy: kindCreds.some((c: any) => c.last_health_ok === true),
                };
              }).filter((s) => s.exists);
              if (steps.length === 0) return null;
              const requiredSteps = steps.filter((s) => s.urgent);
              const requiredDone = requiredSteps.filter((s) => s.configured).length;
              return (
                <div className="rounded-xl border border-border bg-surface-0 p-5">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full bg-accent/15 flex items-center justify-center shrink-0 mt-0.5">
                      <Plug size={14} className="text-accent" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-content-primary">⚡ Quick Setup</h3>
                        <span className="text-[11px] text-content-tertiary">
                          {requiredDone} of {requiredSteps.length} required complete
                        </span>
                      </div>
                      <p className="text-xs text-content-tertiary mt-0.5">
                        Connect at least one provider in each required category to start producing videos.
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {steps.map((step, i) => {
                      const isExpanded = expandedKind === step.kind;
                      return (
                        <div
                          key={step.kind}
                          className={cn("rounded-lg border border-border bg-surface-0 transition-all")}
                        >
                          <button
                            type="button"
                            onClick={() => setExpandedKind(isExpanded ? null : step.kind)}
                            className="flex items-center gap-3 w-full px-4 py-3 hover:bg-surface-1/50 transition-colors rounded-lg group text-left"
                          >
                            <div
                              className={cn(
                                "w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold",
                                step.configured
                                  ? "bg-status-success text-white"
                                  : "bg-surface-2 text-content-tertiary group-hover:bg-accent/15 group-hover:text-accent"
                              )}
                            >
                              {step.configured ? "✓" : i + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className={cn(
                                    "text-sm font-medium transition-colors",
                                    step.configured
                                      ? "text-content-secondary"
                                      : "text-content-primary group-hover:text-accent"
                                  )}
                                >
                                  {step.label}
                                </span>
                                {step.urgent && !step.configured && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-error/10 text-status-error font-medium">
                                    Required
                                  </span>
                                )}
                                {step.configured && step.healthy && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-success/10 text-status-success font-medium">
                                    Healthy
                                  </span>
                                )}
                                {step.configured && (
                                  <span className="text-[10px] text-content-tertiary">
                                    {step.catsForKind.filter((c: any) => countStatus(c.name).total > 0).length}/
                                    {step.catsForKind.length} categories
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-content-tertiary mt-0.5">{step.why}</p>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <ChevronDown
                                size={13}
                                className={cn(
                                  "text-content-tertiary transition-transform duration-200",
                                  isExpanded && "rotate-180"
                                )}
                              />
                            </div>
                          </button>
                          {isExpanded && (
                            <div className="px-4 pb-3 border-t border-border/40">
                              <p className="text-[10px] uppercase tracking-wide text-content-tertiary pt-2.5 pb-1.5">
                                Categories in this section
                              </p>
                              <div className="space-y-1.5">
                                {step.catsForKind.map((cat: any) => {
                                  const st = countStatus(cat.name);
                                  const catConfigured = st.total > 0;
                                  const catHealthy = st.healthy > 0;
                                  return (
                                    <div
                                      key={cat.name}
                                      className="flex items-center gap-3 rounded-md border border-border/60 bg-surface-0/80 px-3 py-2"
                                    >
                                      <span
                                        className={cn(
                                          "w-1.5 h-1.5 rounded-full shrink-0",
                                          catConfigured
                                            ? catHealthy
                                              ? "bg-status-success"
                                              : "bg-status-warning"
                                            : "bg-surface-3"
                                        )}
                                      />
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="text-[12px] font-medium text-content-primary">
                                            {cat.label}
                                          </span>
                                          <span className="text-[10px] font-mono text-content-tertiary">
                                            {cat.name}
                                          </span>
                                        </div>
                                        {st.total > 0 && (
                                          <p className="text-[10px] text-content-tertiary mt-0.5">
                                            {st.total} credential{st.total !== 1 ? "s" : ""}
                                            {st.healthy > 0 ? ` · ${st.healthy} healthy` : ""}
                                            {st.failing > 0 ? ` · ${st.failing} failing` : ""}
                                          </p>
                                        )}
                                      </div>
                                      <Link
                                        href={
                                          catConfigured
                                            ? `/dashboard/providers/${encodeURIComponent(cat.name)}`
                                            : `/dashboard/providers/${encodeURIComponent(cat.name)}?add=1`
                                        }
                                        className={cn(
                                          "shrink-0 flex items-center gap-1 text-[11px] h-7 px-2.5 rounded-full border transition-colors",
                                          catConfigured
                                            ? "border-border text-content-secondary hover:bg-surface-2"
                                            : "border-accent/40 text-accent bg-accent/5 hover:bg-accent/10"
                                        )}
                                      >
                                        {catConfigured ? (
                                          <>
                                            <ChevronRight size={11} /> Manage
                                          </>
                                        ) : (
                                          <>
                                            <Plus size={11} /> Connect
                                          </>
                                        )}
                                      </Link>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}
          </div>
        ))}

      {/* ── Marketplace tab ── */}
      {tab === "marketplace" && (
        <div className="space-y-4">
          {/* Category filter + taxonomy actions */}
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 flex-wrap">
              {["all", ...marketCategories].map((c) => (
                <Button
                  key={c}
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setMarketFilter(c)}
                  className={cn(
                    "h-7 px-2.5 text-xs",
                    marketFilter === c
                      ? "bg-accent/10 text-accent border border-accent/30 hover:bg-accent/15"
                      : "border border-border text-content-tertiary hover:bg-surface-2"
                  )}
                >
                  {c === "all" ? "All" : c.replace(/_/g, " ")}
                </Button>
              ))}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAddProviderFor(cats.find((c) => c.name === marketFilter)?.kind || "")}
                leftIcon={<Plus size={12} />}
              >
                Add provider
              </Button>
              <Button variant="outline" size="sm" onClick={() => setAddSectionFor(true)} leftIcon={<Plus size={12} />}>
                Add section
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 9 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-border bg-surface-0 p-4 animate-pulse h-36" />
              ))}
            </div>
          ) : filteredMarket.length === 0 ? (
            <div className="py-20 text-center text-sm text-content-tertiary">
              <Store size={32} className="mx-auto mb-3 opacity-30" />
              No providers in this category.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredMarket.map((p: any) => (
                <div
                  key={p.provider_key}
                  className="group relative rounded-xl border border-border bg-surface-0 p-4 flex flex-col gap-3 transition-all"
                >
                  {p.is_user_defined && (
                    <button
                      type="button"
                      onClick={() => deleteProvider(p.provider_key, p.display_name)}
                      title="Remove this custom provider"
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-content-tertiary hover:text-status-error p-1 rounded hover:bg-status-error/10 z-10"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm text-content-primary">{p.display_name}</span>
                        {p.connected && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-success/10 text-status-success font-medium flex items-center gap-0.5">
                            <CheckCircle2 size={9} /> Connected
                          </span>
                        )}
                        {p.featured && !p.connected && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">
                            Featured
                          </span>
                        )}
                        {p.has_free_tier && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">
                            Free tier
                          </span>
                        )}
                        {p.is_callable === false && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded bg-status-warning/10 text-status-warning"
                            title="You can save a key but the pipeline adapter isn't wired yet."
                          >
                            Catalog only
                          </span>
                        )}
                        {p.is_user_defined && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">
                            Custom
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span
                          className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded font-medium",
                            MODE_CHIP[p.mode] || "bg-surface-2 text-content-tertiary"
                          )}
                        >
                          {p.mode}
                        </span>
                        <span className="text-[10px] text-content-tertiary">{p.category}</span>
                      </div>
                    </div>
                  </div>

                  {/* Capabilities */}
                  {p.capabilities?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {p.capabilities.slice(0, 4).map((cap: string) => (
                        <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between mt-auto pt-1">
                    <span className="text-xs text-content-tertiary font-mono">{p.cost_unit || "—"}</span>
                    <div className="flex items-center gap-1.5">
                      {(p.credential_count ?? (p.connected ? 1 : 0)) > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-status-success/10 text-status-success font-medium border border-status-success/20">
                          {p.credential_count ?? 1} connected
                        </span>
                      )}
                      <Link
                        prefetch={false}
                        href={`/dashboard/providers/${encodeURIComponent(p.category)}?add=1&provider=${encodeURIComponent(p.provider_key)}`}
                        className="flex items-center gap-1 h-7 px-2.5 rounded-full bg-accent/10 text-accent text-xs font-semibold border border-accent/20 hover:bg-accent/20 transition-colors"
                      >
                        <Plus size={11} /> Connect
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Connected Accounts tab ── */}
      {tab === "accounts" && (
        <div className="space-y-4">
          <p className="text-xs text-content-tertiary">
            OAuth-based integrations — these use account authorization rather than API keys.
          </p>

          {/* YouTube card */}
          <div
            className={cn(
              "rounded-xl border bg-surface-0 p-5 flex items-start gap-4 transition-all",
              ytStatus?.connected ? "border-status-success/30" : "border-border"
            )}
          >
            <div className="w-10 h-10 rounded-xl bg-[#FF0000]/10 flex items-center justify-center shrink-0">
              <Tv size={20} className="text-[#FF0000]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-content-primary">YouTube</span>
                {ytStatus?.connected ? (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-success/10 text-status-success font-medium flex items-center gap-0.5">
                    <CheckCircle2 size={9} /> Connected
                  </span>
                ) : (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-content-tertiary">
                    Not connected
                  </span>
                )}
              </div>

              {ytLoading ? (
                <div className="mt-2">
                  <Loader2 size={13} className="animate-spin text-content-tertiary" />
                </div>
              ) : ytStatus?.connected ? (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2">
                    {ytStatus.channel_avatar && (
                      <img src={ytStatus.channel_avatar} alt="" className="w-5 h-5 rounded-full" />
                    )}
                    <span className="text-xs text-content-secondary font-medium">{ytStatus.channel_name}</span>
                    {ytStatus.channel_id && (
                      <span className="text-[10px] text-content-tertiary font-mono">{ytStatus.channel_id}</span>
                    )}
                  </div>
                  {ytStatus.missing_scopes && ytStatus.missing_scopes.length > 0 && (
                    <div className="flex items-center gap-1.5 text-[10px] text-status-warning">
                      <AlertCircle size={10} />
                      Missing upload scope — reconnect required
                    </div>
                  )}
                  {ytStatus.connected_at && (
                    <p className="text-[10px] text-content-tertiary">
                      Connected {new Date(ytStatus.connected_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-content-tertiary mt-1">
                  Connect your YouTube channel to enable automatic video uploads, thumbnail setting, and scheduled
                  publishing.
                </p>
              )}

              <div className="mt-3 text-[10px] text-content-tertiary space-y-0.5">
                <div>Scopes: youtube.upload · youtube · yt-analytics.readonly</div>
              </div>
            </div>

            <div className="shrink-0">
              {ytStatus?.connected ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={disconnectYouTube}
                  loading={ytDisconnecting}
                  leftIcon={!ytDisconnecting ? <X size={12} /> : undefined}
                  className="border-status-error/40 text-status-error hover:bg-status-error/10"
                >
                  Disconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={connectYouTube}
                  loading={ytConnecting}
                  leftIcon={!ytConnecting ? <Link2 size={12} /> : undefined}
                >
                  Connect with Google
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Architecture tips (only on connected tab) */}
      {tab === "connected" && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              icon: <Network size={14} className="text-accent" />,
              title: "Priority Chains",
              desc: "Multiple credentials per category form a fallback chain. First healthy provider wins.",
            },
            {
              icon: <ShieldCheck size={14} className="text-status-success" />,
              title: "Vault-Backed Secrets",
              desc: "API keys written to env/Vault — never stored in DB or repo.",
            },
            {
              icon: <Gauge size={14} className="text-status-warning" />,
              title: "Live Health Probes",
              desc: 'Use "Probe all" for a fan-out health check across every enabled credential.',
            },
          ].map((t) => (
            <div
              key={t.title}
              className="rounded-xl border border-border bg-surface-0 px-4 py-3 flex items-center gap-3"
            >
              <div className="shrink-0">{t.icon}</div>
              <div className="text-xs font-medium text-content-secondary">{t.title}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Approval Queue Sheet ── */}
      {showApprovals && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setShowApprovals(false)}>
          <div
            className="relative h-full w-full max-w-lg bg-surface-0 border-l border-border shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <ClipboardCheck size={15} className="text-accent" />
                <h2 className="text-sm font-semibold text-content-primary">Pending Approvals</h2>
                {approvals.length > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent font-semibold">
                    {approvals.length}
                  </span>
                )}
              </div>
              <button
                onClick={() => setShowApprovals(false)}
                className="p-1 rounded hover:bg-surface-2 text-content-tertiary hover:text-content-primary transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {approvalsLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 size={20} className="animate-spin text-content-tertiary" />
                </div>
              ) : approvals.length === 0 ? (
                <div className="py-16 text-center">
                  <Check size={28} className="mx-auto mb-3 text-status-success opacity-60" />
                  <p className="text-sm text-content-tertiary">No pending approvals</p>
                </div>
              ) : (
                approvals.map((req) => (
                  <div key={req.id} className="rounded-xl border border-border bg-surface-1 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-content-primary capitalize">
                          {req.request_type.replace(/_/g, " ")} — {req.category}
                          {req.provider_name && <span className="text-content-tertiary"> / {req.provider_name}</span>}
                        </div>
                        <div className="text-[10px] text-content-tertiary mt-0.5">
                          {req.requester_name || req.requester_email || `User #${req.requested_by}`}
                          {" · "}
                          <Clock size={9} className="inline" /> {new Date(req.requested_at).toLocaleDateString()}
                        </div>
                      </div>
                      <span
                        className={cn(
                          "text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0",
                          req.status === "pending_admin"
                            ? "bg-status-warning/10 text-status-warning"
                            : "bg-status-info/10 text-status-info"
                        )}
                      >
                        {req.status === "pending_admin" ? "Needs admin" : "Needs owner"}
                      </span>
                    </div>

                    <p className="text-[11px] text-content-secondary bg-surface-2 rounded-lg px-3 py-2 leading-relaxed">
                      {req.reason}
                    </p>

                    {req.admin_note && (
                      <p className="text-[10px] text-content-tertiary italic">Admin note: {req.admin_note}</p>
                    )}

                    <textarea
                      placeholder="Optional review note…"
                      value={reviewingId === req.id ? reviewNote : ""}
                      onChange={(e) => {
                        setReviewingId(req.id);
                        setReviewNote(e.target.value);
                      }}
                      className="w-full text-xs rounded-md border border-border bg-surface-0 px-3 py-2 resize-none h-14 focus:outline-none focus:ring-1 focus:ring-accent placeholder:text-content-quaternary"
                    />

                    <div className="flex gap-2">
                      {req.status === "pending_admin" ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 border-status-success/40 text-status-success hover:bg-status-success/10"
                            loading={reviewingId === req.id}
                            onClick={() => doAdminReview(req.id, "approve_forward")}
                          >
                            <Check size={11} className="mr-1" /> Forward to owner
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 border-status-error/40 text-status-error hover:bg-status-error/10"
                            loading={reviewingId === req.id}
                            onClick={() => doAdminReview(req.id, "reject")}
                          >
                            <X size={11} className="mr-1" /> Reject
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 border-status-success/40 text-status-success hover:bg-status-success/10"
                            loading={reviewingId === req.id}
                            onClick={() => doOwnerReview(req.id, "approve")}
                          >
                            <Check size={11} className="mr-1" /> Approve & apply
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 border-status-error/40 text-status-error hover:bg-status-error/10"
                            loading={reviewingId === req.id}
                            onClick={() => doOwnerReview(req.id, "reject")}
                          >
                            <X size={11} className="mr-1" /> Reject
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Taxonomy dialogs ── */}
      {addSectionFor && (
        <AddSectionDialog
          onClose={() => setAddSectionFor(false)}
          onAdded={async () => {
            setAddSectionFor(false);
            await refresh();
          }}
        />
      )}
      {addCategoryFor !== false && (
        <AddCategoryDialog
          prefillKind={addCategoryFor || null}
          kinds={kinds}
          onClose={() => setAddCategoryFor(false)}
          onAdded={async () => {
            setAddCategoryFor(false);
            await refresh();
          }}
        />
      )}
      {addProviderFor !== false && (
        <AddProviderDialog
          prefillKind={addProviderFor || ""}
          kinds={kinds}
          onClose={() => setAddProviderFor(false)}
          onAdded={async () => {
            setAddProviderFor(false);
            await refresh();
          }}
        />
      )}
    </main>
  );
}

function DialogShell({
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="rounded-xl bg-surface-0 max-w-md w-full border border-border shadow-elevated flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border">
          <div>
            <h3 className="font-semibold text-content-primary">{title}</h3>
            {subtitle && <p className="text-[11px] text-content-tertiary mt-0.5">{subtitle}</p>}
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close"
            className="w-7 h-7 text-content-tertiary"
          >
            <X size={14} />
          </Button>
        </div>
        <div className="px-5 py-4 space-y-3">{children}</div>
        <div className="flex items-center justify-end gap-2 px-5 pb-5 pt-1">{footer}</div>
      </div>
    </div>
  );
}

const fieldCls =
  "w-full h-9 px-3 rounded-md border border-border bg-surface-1 text-sm text-content-primary placeholder:text-content-tertiary focus:outline-none focus:ring-1 focus:ring-accent";
const labelCls = "block text-[11px] font-medium text-content-secondary mb-1";

function AddSectionDialog({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const { showToast } = useToast();
  const [label, setLabel] = useState("");
  const [icon, setIcon] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!label.trim()) return;
    setBusy(true);
    try {
      await providersApi.createKind({
        label: label.trim(),
        icon: icon.trim() || null,
        description: description.trim() || null,
      });
      showToast(`Section "${label.trim()}" created`, "success");
      onAdded();
    } catch (e: any) {
      showToast(e?.message || "Could not create section", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title="Add section"
      subtitle="A top-level group like Avatar Generation, Music, or Translation."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={submit} disabled={!label.trim() || busy} loading={busy}>
            Create section
          </Button>
        </>
      }
    >
      <div>
        <label className={labelCls}>Section name</label>
        <input
          className={fieldCls}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="e.g. Avatar Generation"
          autoFocus
        />
      </div>
      <div>
        <label className={labelCls}>Icon (emoji, optional)</label>
        <input
          className={fieldCls}
          value={icon}
          onChange={(e) => setIcon(e.target.value)}
          placeholder="🧑‍🎤"
          maxLength={4}
        />
      </div>
      <div>
        <label className={labelCls}>Description (optional)</label>
        <input
          className={fieldCls}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this section is for"
        />
      </div>
    </DialogShell>
  );
}

function AddCategoryDialog({
  prefillKind,
  kinds,
  onClose,
  onAdded,
}: {
  prefillKind: string | null;
  kinds: any[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const { showToast } = useToast();
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState(prefillKind || (kinds[0]?.kind ?? ""));
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!label.trim() || !kind) return;
    setBusy(true);
    try {
      await providersApi.createCategory({ label: label.trim(), kind, description: description.trim() || null });
      showToast(`Category "${label.trim()}" created`, "success");
      onAdded();
    } catch (e: any) {
      showToast(e?.message || "Could not create category", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title="Add category"
      subtitle="A use-case slot inside a section — e.g. 'Product demo avatars'."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={submit} disabled={!label.trim() || !kind || busy} loading={busy}>
            Create category
          </Button>
        </>
      }
    >
      <div>
        <label className={labelCls}>Category name</label>
        <input
          className={fieldCls}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="e.g. Product demo avatars"
          autoFocus
        />
      </div>
      <div>
        <label className={labelCls}>Section</label>
        <select className={fieldCls} value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.length === 0 && <option value="">No sections — create one first</option>}
          {kinds.map((k: any) => (
            <option key={k.kind} value={k.kind}>
              {k.icon ? `${k.icon} ` : ""}
              {k.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={labelCls}>Description (optional)</label>
        <input
          className={fieldCls}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this category is for"
        />
      </div>
    </DialogShell>
  );
}

function AddProviderDialog({
  prefillKind,
  kinds,
  onClose,
  onAdded,
}: {
  prefillKind: string;
  kinds: any[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const { showToast } = useToast();
  const [displayName, setDisplayName] = useState("");
  const [kind, setKind] = useState(prefillKind || (kinds[0]?.kind ?? ""));
  const [models, setModels] = useState("");
  const [description, setDescription] = useState("");
  const [hasFreeTier, setHasFreeTier] = useState(false);
  const [requiresApiKey, setRequiresApiKey] = useState(true);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!displayName.trim() || !kind) return;
    setBusy(true);
    try {
      await providersApi.createMarketplaceProvider({
        display_name: displayName.trim(),
        kind,
        description: description.trim() || null,
        supported_models: models
          .split(",")
          .map((m) => m.trim())
          .filter(Boolean),
        has_free_tier: hasFreeTier,
        requires_api_key: requiresApiKey,
      });
      showToast(`"${displayName.trim()}" added to marketplace`, "success");
      onAdded();
    } catch (e: any) {
      showToast(e?.message || "Could not add provider", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <DialogShell
      title="Add provider"
      subtitle="Add a third-party service (e.g. HeyGen) to a section's marketplace."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={submit} disabled={!displayName.trim() || !kind || busy} loading={busy}>
            Add provider
          </Button>
        </>
      }
    >
      <div>
        <label className={labelCls}>Provider name</label>
        <input
          className={fieldCls}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g. HeyGen"
          autoFocus
        />
      </div>
      <div>
        <label className={labelCls}>Section</label>
        <select className={fieldCls} value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.length === 0 && <option value="">No sections — create one first</option>}
          {kinds.map((k: any) => (
            <option key={k.kind} value={k.kind}>
              {k.icon ? `${k.icon} ` : ""}
              {k.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={labelCls}>Models (optional, comma-separated)</label>
        <input
          className={fieldCls}
          value={models}
          onChange={(e) => setModels(e.target.value)}
          placeholder="avatar-v3, avatar-realistic"
        />
      </div>
      <div>
        <label className={labelCls}>Description (optional)</label>
        <input
          className={fieldCls}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this provider does"
        />
      </div>
      <div className="flex items-center gap-4 pt-1">
        <label className="flex items-center gap-2 text-xs text-content-secondary cursor-pointer">
          <input type="checkbox" checked={requiresApiKey} onChange={(e) => setRequiresApiKey(e.target.checked)} /> Needs
          an API key
        </label>
        <label className="flex items-center gap-2 text-xs text-content-secondary cursor-pointer">
          <input type="checkbox" checked={hasFreeTier} onChange={(e) => setHasFreeTier(e.target.checked)} /> Has a free
          tier
        </label>
      </div>
      <p className="text-[11px] text-content-tertiary">
        Added as <span className="font-medium">catalog-only</span> — you can save a key and bind it to a category now;
        the pipeline can call it once an adapter is wired up.
      </p>
    </DialogShell>
  );
}
