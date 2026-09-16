"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { systemApi, authApi } from "@/lib/api-v2";
import { isLoggedIn } from "@/lib/api-v2";
import { cn } from "@/lib/utils";
import { useToast } from "@/lib/toast";
import { PageHeader } from "@/lib/components/PageHeader";
import { Skeleton } from "@/lib/components/Skeleton";
import {
  Power,
  PowerOff,
  Flag,
  ChevronRight,
  Database,
  Bell,
  Lock,
  DollarSign,
  SlidersHorizontal,
} from "@/lib/components/Icon";
import { useAppState } from "@/lib/components/AppStateProvider";
import { useTheme } from "@/lib/theme";
import {
  Button,
  Input,
  Textarea,
  Label,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseButton,
  DialogTitle,
  DialogDescription,
} from "@/lib/ui";

const FRIENDLY_LABELS: Record<string, string> = {
  dashboard_admin_password: "Admin Password",
  dashboard_session_ttl_hours: "Session TTL (hours)",
  notify_daily_summary: "Daily Summary Notification",
  notify_on_complete: "Notify on Completion",
  notify_on_failure: "Notify on Failure",
  notify_on_review: "Notify on Review Needed",
  telegram_bot_token: "Telegram Bot Token",
  telegram_chat_id: "Telegram Chat ID",
  daily_budget_limit: "Daily Budget Limit",
  daily_budget_used: "Daily Budget Used",
  monthly_budget_usd: "Monthly Budget (USD)",
  daily_cost_limit_usd: "Daily Cost Limit (USD)",
  per_video_budget_usd: "Per-Video Budget (USD)",
  emergency_stop: "Emergency Stop",
  auto_approve_threshold: "Auto-Approve Threshold",
  max_daily_videos: "Max Daily Videos",
  default_content_mode: "Default Content Mode",
  human_review_required: "Human Review Required",
};

const SENSITIVE_KEYS = ["password", "token", "secret", "api_key"];

function friendlyName(key: string): string {
  if (FRIENDLY_LABELS[key]) return FRIENDLY_LABELS[key];
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function isSensitive(key: string): boolean {
  return SENSITIVE_KEYS.some((s) => key.toLowerCase().includes(s));
}
function isBooleanValue(val: string): boolean {
  return val === "true" || val === "false";
}
function isJsonObject(val: string): boolean {
  if (!val) return false;
  const t = val.trim();
  return t.startsWith("{") && t.endsWith("}");
}

type SettingSchema = {
  label: string;
  description: string;
  type: "select" | "number" | "toggle" | "text";
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
};

const CONTENT_SCHEMA: Record<string, SettingSchema> = {
  "content.default_mode": {
    label: "Default Content Mode",
    description: "Applied to all channels unless overridden at channel or content-mode scope.",
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
    description: "Force all generated content through human review before publishing.",
    type: "toggle",
  },
  "content.auto_approve_threshold": {
    label: "Auto-Approve Threshold",
    description: "Quality score above which content is auto-approved without human review.",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
  },
  "content.max_daily_videos": {
    label: "Max Daily Videos",
    description: "Hard cap on videos published per day across all channels system-wide.",
    type: "number",
    min: 0,
    max: 9999,
    step: 1,
    unit: "videos/day",
  },
};

const BUDGET_SCHEMA: Record<string, SettingSchema> = {
  "budget.per_video_usd": {
    label: "Per-Video Budget",
    description: "Default maximum API and compute spend per video job.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
  "budget.daily_limit_usd": {
    label: "Daily Cost Limit",
    description: "Hard ceiling on total daily API/compute costs. Jobs are blocked beyond this.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
  "budget.monthly_limit_usd": {
    label: "Monthly Budget",
    description: "Soft monthly spend cap — triggers an alert when reached but does not block jobs.",
    type: "number",
    min: 0,
    step: 0.01,
    unit: "USD",
  },
};

function isJsonArray(val: string): boolean {
  if (!val) return false;
  const t = val.trim();
  return t.startsWith("[") && t.endsWith("]");
}

export default function SettingsPage() {
  const router = useRouter();
  const { showToast } = useToast();

  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [emergency, setEmergency] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [chipInput, setChipInput] = useState("");
  const [jsonError, setJsonError] = useState("");
  const [cleanSlateOpen, setCleanSlateOpen] = useState(false);
  const [cleanSlateInput, setCleanSlateInput] = useState("");
  const [cleanSlateRunning, setCleanSlateRunning] = useState(false);

  const [entityMap, setEntityMap] = useState<Record<string, { value: unknown; locked: boolean }>>({});
  const [entityEdits, setEntityEdits] = useState<Record<string, unknown>>({});
  const [entityLocked, setEntityLocked] = useState<Record<string, boolean>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const systemStopped = emergency;

  const loadConfigs = useCallback(async () => {
    try {
      const res = await systemApi.config();
      const data = res.data ?? [];
      setConfigs(data);
      setConfigError(null);
      const stopped = data.some((c: any) => c.key === "emergency_stop" && c.value === "true");
      setEmergency(stopped);
      if (stopped) {
        setEditMode(false);
        setEditing(null);
      }
    } catch (e: any) {
      setConfigError(e?.message || "Failed to load config");
    }
  }, []);

  const loadEntitySettings = useCallback(async () => {
    try {
      const res = await systemApi.getEntitySettings();
      const map: Record<string, { value: unknown; locked: boolean }> = {};
      for (const row of res.data ?? []) map[row.key] = { value: row.value, locked: row.locked };
      setEntityMap(map);
    } catch {}
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    Promise.all([loadConfigs(), loadEntitySettings()]).finally(() => setLoading(false));
    authApi.me().catch(() => {});
  }, [router, loadConfigs, loadEntitySettings]);

  useEffect(() => {
    if (!editing) return;
    if (!isJsonObject(editValue) && !isJsonArray(editValue)) {
      setJsonError("");
      return;
    }
    try {
      JSON.parse(editValue);
      setJsonError("");
    } catch (e: any) {
      setJsonError((e?.message || "Invalid JSON").replace(/^JSON\.parse:\s*/, ""));
    }
  }, [editValue, editing]);

  async function saveConfig(key: string, value?: string) {
    const val = value !== undefined ? value : editValue;
    if (isJsonObject(val) || isJsonArray(val)) {
      try {
        JSON.parse(val);
      } catch {
        setJsonError("Invalid JSON");
        return;
      }
    }
    try {
      await systemApi.updateConfig(key, val);
      setEditing(null);
      setJsonError("");
      loadConfigs();
    } catch {}
  }

  async function toggleBool(key: string, currentValue: string) {
    await saveConfig(key, currentValue === "true" ? "false" : "true");
  }

  async function toggleEmergency() {
    try {
      if (emergency) await systemApi.emergencyResume();
      else await systemApi.emergencyStop();
      loadConfigs();
    } catch {}
  }

  function startEdit(key: string, value: string) {
    setEditing(key);
    setEditValue(value);
    setJsonError("");
    setChipInput("");
  }

  function addChip() {
    if (!chipInput.trim()) return;
    try {
      const arr = JSON.parse(editValue);
      if (Array.isArray(arr)) {
        arr.push(chipInput.trim());
        setEditValue(JSON.stringify(arr));
        setChipInput("");
      }
    } catch {}
  }

  function removeChip(index: number) {
    try {
      const arr = JSON.parse(editValue);
      if (Array.isArray(arr)) {
        arr.splice(index, 1);
        setEditValue(JSON.stringify(arr));
      }
    } catch {}
  }

  async function handleCleanSlate() {
    if (cleanSlateInput !== "RESET") return;
    setCleanSlateRunning(true);
    try {
      const res = await systemApi.cleanSlate();
      const d = (res as any)?.data || {};
      showToast(
        `Clean slate done: ${d.workflows_terminated || 0} workflow(s) terminated, ` +
          `${(d.tables_truncated || []).length} table(s) cleared`,
        "success"
      );
      setCleanSlateOpen(false);
      setCleanSlateInput("");
      setTimeout(() => router.push("/dashboard"), 500);
    } catch (err: any) {
      showToast(err?.message || "Clean slate failed", "error");
    } finally {
      setCleanSlateRunning(false);
    }
  }

  function esVal(key: string): unknown {
    return key in entityEdits ? entityEdits[key] : (entityMap[key]?.value ?? null);
  }
  function esLocked(key: string): boolean {
    return key in entityLocked ? entityLocked[key] : (entityMap[key]?.locked ?? false);
  }
  function setEsVal(key: string, val: unknown) {
    setEntityEdits((prev) => ({ ...prev, [key]: val }));
  }
  function setEsLocked(key: string, locked: boolean) {
    setEntityLocked((prev) => ({ ...prev, [key]: locked }));
  }
  async function saveEntitySetting(key: string) {
    setSavingKey(key);
    try {
      await systemApi.setEntitySetting(key, esVal(key), esLocked(key));
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
      setSavingKey(null);
    }
  }

  if (loading)
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader
          title="Settings"
          subtitle="Loading…"
          crumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Settings" }]}
          containerClassName="max-w-5xl"
        />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-6 space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </main>
      </div>
    );

  const sysOpsKeys = ["emergency_stop", "environment_mode", "dashboard_admin_password", "dashboard_session_ttl_hours"];
  const notifCfgs = configs.filter((c) => c.key.startsWith("notify_") || c.key.startsWith("telegram_"));
  const opsCfgs = configs.filter((c) => sysOpsKeys.includes(c.key));
  const otherCfgs = configs.filter(
    (c) => !sysOpsKeys.includes(c.key) && !c.key.startsWith("notify_") && !c.key.startsWith("telegram_")
  );

  const cfgRowProps = (cfg: any) => ({
    cfg,
    editMode,
    isEditing: editing === cfg.key,
    editValue,
    chipInput,
    jsonError,
    onStartEdit: () => startEdit(cfg.key, cfg.value),
    onEditValueChange: setEditValue,
    onChipInputChange: setChipInput,
    onAddChip: addChip,
    onRemoveChip: removeChip,
    onSave: () => saveConfig(cfg.key),
    onCancel: () => {
      setEditing(null);
      setJsonError("");
    },
    onToggleBool: () => toggleBool(cfg.key, cfg.value),
  });

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="System Settings"
        subtitle="Configure defaults for every workspace and all content pipelines."
        crumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Settings" }]}
        containerClassName="max-w-5xl"
        actions={
          <Button
            onClick={toggleEmergency}
            size="sm"
            leftIcon={emergency ? <Power size={14} /> : <PowerOff size={14} />}
            className={cn(
              emergency
                ? "bg-status-success hover:bg-status-success/90 text-content-inverse"
                : "bg-status-error hover:bg-status-error/90 text-content-inverse"
            )}
          >
            {emergency ? "Resume System" : "Emergency Stop"}
          </Button>
        }
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6">
          {configError && (
            <div className="mb-4 p-4 rounded-lg bg-status-error/10 border border-status-error/20 text-sm">
              <span className="font-semibold text-status-error">Config load failed: </span>
              <span className="text-content-secondary">{configError}</span>
              <Button variant="link" size="sm" onClick={loadConfigs} className="ml-3 h-auto p-0 text-xs">
                Retry
              </Button>
            </div>
          )}

          <Tabs defaultValue="system">
            <TabsList className="mb-6">
              <TabsTrigger value="system">System</TabsTrigger>
              <TabsTrigger value="content">Content Defaults</TabsTrigger>
              <TabsTrigger value="budget">Budget</TabsTrigger>
              <TabsTrigger value="notifications">Notifications</TabsTrigger>
              <TabsTrigger value="display">Display</TabsTrigger>
              <TabsTrigger value="directories">Directories</TabsTrigger>
            </TabsList>

            {/* ── System tab ─────────────────────────────────────────── */}
            <TabsContent value="system">
              {emergency && (
                <div className="mb-4 p-4 rounded-lg bg-status-error/10 border border-status-error/30 flex items-center gap-3">
                  <PowerOff size={16} className="text-status-error shrink-0" />
                  <div className="text-sm text-status-error font-medium">
                    System is stopped. All workflows are paused.
                  </div>
                </div>
              )}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-semibold text-content-secondary">Operations</h2>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-xs text-content-tertiary">Edit Mode</span>
                    <Switch
                      checked={editMode && !systemStopped}
                      onCheckedChange={(v) => !systemStopped && setEditMode(v)}
                      disabled={systemStopped}
                      aria-label="Toggle edit mode"
                    />
                  </label>
                </div>
                <div className={cn("card divide-y divide-border", systemStopped && "lockdown-frost")}>
                  {opsCfgs.length > 0 ? (
                    opsCfgs.map((cfg: any) => <ConfigRow key={cfg.key} {...cfgRowProps(cfg)} />)
                  ) : (
                    <div className="px-5 py-4 text-sm text-content-tertiary">No operations keys in system_config.</div>
                  )}
                </div>
              </div>
              {otherCfgs.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-xs font-semibold text-content-secondary mb-3">Other</h2>
                  <div className={cn("card divide-y divide-border", systemStopped && "lockdown-frost")}>
                    {otherCfgs.map((cfg: any) => (
                      <ConfigRow key={cfg.key} {...cfgRowProps(cfg)} />
                    ))}
                  </div>
                </div>
              )}
              <div className="mb-6">
                <h2 className="text-xs font-semibold text-status-error mb-3">Danger Zone</h2>
                <div className="card border-status-error/30 bg-status-error/5 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-medium text-content-primary">Clean Slate — Reset All Jobs</div>
                      <div className="text-xs text-content-tertiary mt-1">
                        Wipes all video history, job events, analytics, renders, and checkpoints. Preserves channels,
                        brand profiles, config, prompts, and ML models. Dashboard returns to{" "}
                        <span className="font-mono">0 delivered · 0 in-progress · 0 total</span>.
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCleanSlateOpen(true)}
                      disabled={systemStopped}
                      className="shrink-0 bg-status-error/10 text-status-error border-status-error/30 hover:bg-status-error/20 hover:text-status-error"
                    >
                      Clean Slate
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* ── Content Defaults tab ──────────────────────────────────── */}
            <TabsContent value="content">
              <p className="text-sm text-content-secondary mb-6">
                These values set system-wide defaults for all content pipelines. Workspace owners and individual
                channels can override any setting.{" "}
                <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
                  <Lock size={11} /> Locked settings cannot be overridden downstream.
                </span>
              </p>
              <div className="space-y-4">
                {Object.entries(CONTENT_SCHEMA).map(([key, schema]) => (
                  <EntitySettingRow
                    key={key}
                    esKey={key}
                    schema={schema}
                    value={esVal(key)}
                    locked={esLocked(key)}
                    saving={savingKey === key}
                    onChange={(v) => setEsVal(key, v)}
                    onLockedChange={(l) => setEsLocked(key, l)}
                    onSave={() => saveEntitySetting(key)}
                  />
                ))}
              </div>
            </TabsContent>

            {/* ── Budget tab ───────────────────────────────────────────── */}
            <TabsContent value="budget">
              <p className="text-sm text-content-secondary mb-6">
                Default cost controls applied system-wide. Each workspace and channel can independently override these
                limits.
              </p>
              <div className="space-y-4">
                {Object.entries(BUDGET_SCHEMA).map(([key, schema]) => (
                  <EntitySettingRow
                    key={key}
                    esKey={key}
                    schema={schema}
                    value={esVal(key)}
                    locked={esLocked(key)}
                    saving={savingKey === key}
                    onChange={(v) => setEsVal(key, v)}
                    onLockedChange={(l) => setEsLocked(key, l)}
                    onSave={() => saveEntitySetting(key)}
                  />
                ))}
              </div>
            </TabsContent>

            {/* ── Notifications tab ────────────────────────────────────── */}
            <TabsContent value="notifications">
              <div className="mb-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-semibold text-content-secondary">Notifications</h2>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-xs text-content-tertiary">Edit Mode</span>
                    <Switch
                      checked={editMode && !systemStopped}
                      onCheckedChange={(v) => !systemStopped && setEditMode(v)}
                      disabled={systemStopped}
                      aria-label="Toggle edit mode"
                    />
                  </label>
                </div>
                <div className="card divide-y divide-border">
                  {notifCfgs.length > 0 ? (
                    notifCfgs.map((cfg: any) => <ConfigRow key={cfg.key} {...cfgRowProps(cfg)} />)
                  ) : (
                    <div className="px-5 py-4 text-sm text-content-tertiary">
                      No notification keys in system_config.
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            {/* ── Display tab ──────────────────────────────────────────── */}
            <TabsContent value="display">
              <DisplayPreferences />
            </TabsContent>

            {/* ── Directories tab ──────────────────────────────────────── */}
            <TabsContent value="directories">
              <p className="text-sm text-content-secondary mb-6">
                Global reference data inherited by all workspaces. Superadmin-only.
              </p>
              <div className="space-y-3">
                <Link
                  href="/dashboard/lookup-values"
                  className="card flex items-center justify-between gap-4 p-5 hover:bg-surface-1 transition-colors group"
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-md bg-accent/10 text-accent shrink-0">
                      <Database size={16} />
                    </span>
                    <div>
                      <div className="text-sm font-medium text-content-primary">Lookup Values</div>
                      <div className="text-xs text-content-tertiary mt-0.5">
                        Manage global dropdown options — niches, languages, geographies, content type tags, LUT presets,
                        and more.
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={16} className="text-content-tertiary group-hover:text-content-primary shrink-0" />
                </Link>
                <Link
                  href="/dashboard/settings/flags"
                  className="card flex items-center justify-between gap-4 p-5 hover:bg-surface-1 transition-colors group"
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-md bg-accent/10 text-accent shrink-0">
                      <Flag size={16} />
                    </span>
                    <div>
                      <div className="text-sm font-medium text-content-primary">Feature Flags</div>
                      <div className="text-xs text-content-tertiary mt-0.5">
                        Toggle preview features and gradual rollouts across the platform.
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={16} className="text-content-tertiary group-hover:text-content-primary shrink-0" />
                </Link>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      {/* Clean Slate Confirmation Dialog */}
      <Dialog
        open={cleanSlateOpen}
        onOpenChange={(o) => {
          if (!o && !cleanSlateRunning) {
            setCleanSlateOpen(false);
            setCleanSlateInput("");
          }
        }}
      >
        <DialogContent className="border-status-error/30">
          <DialogHeader>
            <div>
              <DialogTitle>This will delete ALL job history</DialogTitle>
              <DialogDescription>This action cannot be undone.</DialogDescription>
            </div>
            <DialogCloseButton
              onClick={() => {
                if (!cleanSlateRunning) {
                  setCleanSlateOpen(false);
                  setCleanSlateInput("");
                }
              }}
              disabled={cleanSlateRunning}
            />
          </DialogHeader>
          <DialogBody>
            <div className="space-y-3 text-xs">
              <div>
                <div className="font-medium text-status-error mb-1">Will be wiped:</div>
                <ul className="list-disc pl-5 text-content-secondary space-y-0.5">
                  <li>All videos, job events, and analytics records</li>
                  <li>All running Temporal workflows (terminated)</li>
                  <li>All MinIO blobs (renders, checkpoints, assets)</li>
                </ul>
              </div>
              <div>
                <div className="font-medium text-status-success mb-1">Will be preserved:</div>
                <ul className="list-disc pl-5 text-content-secondary space-y-0.5">
                  <li>Channel configurations and brand profiles</li>
                  <li>System config, prompt registry, ML models</li>
                </ul>
              </div>
            </div>
            <div className="mt-3">
              <Label htmlFor="reset-confirm" className="text-xs text-content-secondary mb-1.5 block">
                Type <span className="font-mono font-semibold text-status-error">RESET</span> to confirm:
              </Label>
              <Input
                id="reset-confirm"
                type="text"
                value={cleanSlateInput}
                onChange={(e) => setCleanSlateInput(e.target.value)}
                disabled={cleanSlateRunning}
                placeholder="RESET"
                className="font-mono"
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCleanSlateOpen(false);
                  setCleanSlateInput("");
                }}
                disabled={cleanSlateRunning}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleCleanSlate}
                disabled={cleanSlateInput !== "RESET" || cleanSlateRunning}
              >
                {cleanSlateRunning ? "Wiping…" : "Clean Slate"}
              </Button>
            </DialogFooter>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function EntitySettingRow({
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
  schema: SettingSchema;
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
        <span className="text-xs text-content-tertiary">
          Lock — prevent workspace owners from overriding this setting
        </span>
      </div>
    </div>
  );
}

function ConfigRow({
  cfg,
  editMode,
  isEditing,
  editValue,
  chipInput,
  jsonError,
  onStartEdit,
  onEditValueChange,
  onChipInputChange,
  onAddChip,
  onRemoveChip,
  onSave,
  onCancel,
  onToggleBool,
}: {
  cfg: any;
  editMode: boolean;
  isEditing: boolean;
  editValue: string;
  chipInput: string;
  jsonError: string;
  onStartEdit: () => void;
  onEditValueChange: (v: string) => void;
  onChipInputChange: (v: string) => void;
  onAddChip: () => void;
  onRemoveChip: (i: number) => void;
  onSave: () => void;
  onCancel: () => void;
  onToggleBool: () => void;
}) {
  const sensitive = isSensitive(cfg.key);
  const isBool = isBooleanValue(cfg.value);
  const isJson = isJsonObject(cfg.value);
  const isArr = isJsonArray(cfg.value);

  let displayValue = cfg.value || "—";
  if (sensitive && !isEditing) displayValue = "••••••••";
  if (isJson && !isEditing) {
    try {
      displayValue = JSON.stringify(JSON.parse(cfg.value), null, 0).slice(0, 60) + (cfg.value.length > 60 ? "…" : "");
    } catch {}
  }

  return (
    <div className="px-5 py-4 hover:bg-surface-1/30 transition-colors">
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-content-primary">{friendlyName(cfg.key)}</div>
          <div className="text-xs text-content-tertiary mt-0.5">
            {cfg.description || <span className="font-mono text-content-tertiary/60">{cfg.key}</span>}
          </div>
        </div>

        {/* Boolean: always show toggle if editMode is on */}
        {isBool && !isEditing ? (
          <div className="flex items-center gap-3">
            <Switch
              checked={cfg.value === "true"}
              onCheckedChange={editMode ? onToggleBool : undefined}
              disabled={!editMode}
              aria-label={`Toggle ${cfg.key}`}
            />
          </div>
        ) : isEditing ? null : (
          <div className="flex items-center gap-3">
            {/* Array: show chips */}
            {isArr ? (
              <div className="flex flex-wrap gap-1 max-w-xs">
                {(() => {
                  try {
                    const arr = JSON.parse(cfg.value);
                    return arr.slice(0, 5).map((item: string, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-2 text-content-secondary"
                      >
                        {String(item)}
                      </span>
                    ));
                  } catch {
                    return <span className="text-xs text-content-tertiary">{displayValue}</span>;
                  }
                })()}
                {(() => {
                  try {
                    return JSON.parse(cfg.value).length > 5 ? (
                      <span className="text-[11px] text-content-tertiary">+{JSON.parse(cfg.value).length - 5}</span>
                    ) : null;
                  } catch {
                    return null;
                  }
                })()}
              </div>
            ) : (
              <code className="text-xs text-content-secondary bg-surface-2 px-2.5 py-1 rounded-md max-w-xs truncate block">
                {displayValue}
              </code>
            )}
            {editMode && (
              <Button variant="link" size="sm" onClick={onStartEdit} className="h-auto p-0 text-xs shrink-0">
                Edit
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Editing state */}
      {isEditing && (
        <div className="mt-3 p-4 bg-surface-1 rounded-lg border border-border">
          {isArr ? (
            /* Array editor: chips + input */
            <div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(() => {
                  try {
                    const arr = JSON.parse(editValue);
                    return arr.map((item: string, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-surface-2 text-content-primary"
                      >
                        {String(item)}
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => onRemoveChip(i)}
                          aria-label={`Remove ${String(item)}`}
                          className="h-4 w-4 ml-0.5 text-content-tertiary hover:text-status-error"
                        >
                          ×
                        </Button>
                      </span>
                    ));
                  } catch {
                    return null;
                  }
                })()}
              </div>
              <div className="flex gap-2">
                <Input
                  value={chipInput}
                  onChange={(e) => onChipInputChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      onAddChip();
                    }
                  }}
                  placeholder="Type and press Enter to add"
                  className="flex-1 h-8 text-xs"
                />
                <Button variant="secondary" size="sm" onClick={onAddChip}>
                  Add
                </Button>
              </div>
            </div>
          ) : isJson ? (
            /* JSON editor: textarea with live validation */
            <div>
              <div className="relative">
                <Textarea
                  value={editValue}
                  onChange={(e) => onEditValueChange(e.target.value)}
                  spellCheck={false}
                  error={!!jsonError}
                  aria-describedby={jsonError ? "json-error" : undefined}
                  className="text-xs font-mono min-h-[120px] resize-y"
                />
                <div className="absolute top-2 right-2 text-[10px] font-medium pointer-events-none">
                  {jsonError ? (
                    <span className="text-status-error">● Invalid</span>
                  ) : (
                    <span className="text-status-success">● Valid</span>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between mt-1">
                {jsonError ? (
                  <p id="json-error" className="text-xs text-status-error" role="alert">
                    {jsonError}
                  </p>
                ) : (
                  <p className="text-[10px] text-content-tertiary">JSON is valid.</p>
                )}
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  disabled={!!jsonError}
                  onClick={() => {
                    try {
                      onEditValueChange(JSON.stringify(JSON.parse(editValue), null, 2));
                    } catch {}
                  }}
                  className="h-auto p-0 text-[10px] text-content-tertiary hover:text-accent"
                >
                  Pretty-print
                </Button>
              </div>
            </div>
          ) : (
            /* Regular text input */
            <Input
              value={editValue}
              onChange={(e) => onEditValueChange(e.target.value)}
              type="text"
              className="h-8 text-xs"
              autoFocus
            />
          )}
          <div className="flex justify-end gap-2 mt-3">
            <Button variant="secondary" size="sm" onClick={onCancel}>
              Cancel
            </Button>
            <Button size="sm" onClick={onSave} disabled={!!jsonError}>
              Save
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function DisplayPreferences() {
  const { theme, setTheme } = useTheme();
  const { density, setDensity } = useAppState();

  const themeOpts: { value: "light" | "dark" | "system"; label: string }[] = [
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
    { value: "system", label: "System" },
  ];
  const densityOpts: { value: "comfortable" | "compact"; label: string }[] = [
    { value: "comfortable", label: "Comfortable" },
    { value: "compact", label: "Compact" },
  ];

  return (
    <div className="mb-8">
      <h2 className="text-xs font-semibold text-content-secondary mb-3 flex items-center gap-2">Display</h2>
      <div className="card p-5 space-y-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm font-medium text-content-primary">Theme</div>
            <div className="text-xs text-content-tertiary mt-0.5">Light, dark, or follow your operating system.</div>
          </div>
          <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-lg bg-surface-2 p-1">
            {themeOpts.map((opt) => (
              <Button
                key={opt.value}
                role="radio"
                aria-checked={theme === opt.value}
                variant="ghost"
                size="sm"
                onClick={() => setTheme(opt.value)}
                className={cn(
                  "h-7 px-3 text-xs",
                  theme === opt.value
                    ? "bg-surface-0 text-content-primary shadow-card hover:bg-surface-0"
                    : "text-content-tertiary hover:text-content-primary"
                )}
              >
                {opt.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm font-medium text-content-primary">Density</div>
            <div className="text-xs text-content-tertiary mt-0.5">Compact tightens spacing in cards and list rows.</div>
          </div>
          <div role="radiogroup" aria-label="Density" className="inline-flex rounded-lg bg-surface-2 p-1">
            {densityOpts.map((opt) => (
              <Button
                key={opt.value}
                role="radio"
                aria-checked={density === opt.value}
                variant="ghost"
                size="sm"
                onClick={() => setDensity(opt.value)}
                className={cn(
                  "h-7 px-3 text-xs",
                  density === opt.value
                    ? "bg-surface-0 text-content-primary shadow-card hover:bg-surface-0"
                    : "text-content-tertiary hover:text-content-primary"
                )}
              >
                {opt.label}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
