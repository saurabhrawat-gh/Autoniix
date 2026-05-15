'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { systemApi } from '@/lib/api-v2';
import { isLoggedIn } from '@/lib/api-v2';
import { cn } from '@/lib/utils';
import { useToast } from '@/lib/toast';
import { PageHeader } from '@/lib/components/PageHeader';
import { Skeleton } from '@/lib/components/Skeleton';
import { Power, PowerOff } from '@/lib/components/Icon';
import { useAppState } from '@/lib/components/AppStateProvider';
import { useTheme } from '@/lib/theme';
import {
  Button,
  Input,
  Textarea,
  Label,
  Switch,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/lib/ui';

const FRIENDLY_LABELS: Record<string, string> = {
  dashboard_admin_password: 'Admin Password',
  dashboard_session_ttl_hours: 'Session TTL (hours)',
  notify_daily_summary: 'Daily Summary Notification',
  notify_on_complete: 'Notify on Completion',
  notify_on_failure: 'Notify on Failure',
  notify_on_review: 'Notify on Review Needed',
  telegram_bot_token: 'Telegram Bot Token',
  telegram_chat_id: 'Telegram Chat ID',
  daily_budget_limit: 'Daily Budget Limit',
  daily_budget_used: 'Daily Budget Used',
  monthly_budget_usd: 'Monthly Budget (USD)',
  daily_cost_limit_usd: 'Daily Cost Limit (USD)',
  per_video_budget_usd: 'Per-Video Budget (USD)',
  emergency_stop: 'Emergency Stop',
  auto_approve_threshold: 'Auto-Approve Threshold',
  max_daily_videos: 'Max Daily Videos',
  default_content_mode: 'Default Content Mode',
  human_review_required: 'Human Review Required',
};

const GROUP_LABELS: Record<string, string> = {
  channel_defaults: 'Channel Defaults',
  dashboard: 'Dashboard',
  notifications: 'Notifications',
  budget: 'Budget & Costs',
  system: 'System',
};

const SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key'];
const CHANNEL_DEFAULT_KEYS = ['default_content_mode', 'per_video_budget_usd', 'max_daily_videos', 'auto_approve_threshold', 'human_review_required', 'quality_threshold'];

function friendlyName(key: string): string {
  if (FRIENDLY_LABELS[key]) return FRIENDLY_LABELS[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function isSensitive(key: string): boolean {
  return SENSITIVE_KEYS.some(s => key.toLowerCase().includes(s));
}

function isBooleanValue(val: string): boolean {
  return val === 'true' || val === 'false';
}

function isJsonObject(val: string): boolean {
  if (!val) return false;
  const t = val.trim();
  return t.startsWith('{') && t.endsWith('}');
}

function isJsonArray(val: string): boolean {
  if (!val) return false;
  const t = val.trim();
  return t.startsWith('[') && t.endsWith(']');
}

export default function SettingsPage() {
  const router = useRouter();
  const [configs, setConfigs] = useState<any[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [chipInput, setChipInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [emergency, setEmergency] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [jsonError, setJsonError] = useState('');
  const [cleanSlateOpen, setCleanSlateOpen] = useState(false);
  const [cleanSlateInput, setCleanSlateInput] = useState('');
  const [cleanSlateRunning, setCleanSlateRunning] = useState(false);
  const { showToast } = useToast();
  const systemStopped = emergency;

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadConfigs();
  }, [router]);

  async function loadConfigs() {
    try {
      const res = await systemApi.config();
      setConfigs(res.data ?? []);
      setConfigError(null);
      const isStopped = (res.data ?? []).some((c: any) => c.key === 'emergency_stop' && c.value === 'true');
      setEmergency(isStopped);
      if (isStopped) { setEditMode(false); setEditing(null); }
    } catch (e: any) {
      setConfigError(e?.message || 'Failed to load config from v2 API');
    }
    setLoading(false);
  }

  async function saveConfig(key: string, value?: string) {
    const val = value !== undefined ? value : editValue;
    // Validate JSON if applicable
    if (isJsonObject(val) || isJsonArray(val)) {
      try { JSON.parse(val); } catch {
        setJsonError('Invalid JSON'); return;
      }
    }
    try {
      await systemApi.updateConfig(key, val);
      setEditing(null);
      setJsonError('');
      loadConfigs();
    } catch {}
  }

  async function toggleBool(key: string, currentValue: string) {
    const newVal = currentValue === 'true' ? 'false' : 'true';
    await saveConfig(key, newVal);
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
    setJsonError('');
    setChipInput('');
  }

  // Live JSON validation as user types
  useEffect(() => {
    if (!editing) return;
    if (!isJsonObject(editValue) && !isJsonArray(editValue)) {
      setJsonError('');
      return;
    }
    try {
      JSON.parse(editValue);
      setJsonError('');
    } catch (e: any) {
      const msg = e?.message || 'Invalid JSON';
      // Trim noisy "JSON.parse:" prefixes for cleaner inline display
      setJsonError(msg.replace(/^JSON\.parse:\s*/, ''));
    }
  }, [editValue, editing]);

  function addChip() {
    if (!chipInput.trim()) return;
    try {
      const arr = JSON.parse(editValue);
      if (Array.isArray(arr)) {
        arr.push(chipInput.trim());
        setEditValue(JSON.stringify(arr));
        setChipInput('');
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
    if (cleanSlateInput !== 'RESET') return;
    setCleanSlateRunning(true);
    try {
      const res = await systemApi.cleanSlate();
      const d = res?.data || {};
      showToast(
        `Clean slate done: ${d.workflows_terminated || 0} workflow(s) terminated, ` +
        `${(d.tables_truncated || []).length} table(s) cleared, ` +
        `${d.storage_objects_deleted || 0} object(s) removed`,
        'success'
      );
      setCleanSlateOpen(false);
      setCleanSlateInput('');
      setTimeout(() => { router.push('/dashboard'); }, 500);
    } catch (err: any) {
      showToast(err?.message || 'Clean slate failed', 'error');
    } finally {
      setCleanSlateRunning(false);
    }
  }

  if (loading) return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Settings"
        subtitle="Loading configuration…"
        crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Settings' }]}
        containerClassName="max-w-4xl"
      />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-6 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </main>
    </div>
  );

  const groups: Record<string, any[]> = {
    channel_defaults: configs.filter(c => CHANNEL_DEFAULT_KEYS.includes(c.key)),
    dashboard: configs.filter(c => c.key.startsWith('dashboard_')),
    notifications: configs.filter(c => c.key.startsWith('notify_') || c.key.startsWith('telegram_')),
    budget: configs.filter(c => (c.key.includes('budget') || c.key.includes('cost')) && !CHANNEL_DEFAULT_KEYS.includes(c.key)),
    system: configs.filter(c =>
      !c.key.startsWith('dashboard_') && !c.key.startsWith('notify_') &&
      !c.key.startsWith('telegram_') && !c.key.includes('budget') && !c.key.includes('cost') &&
      !CHANNEL_DEFAULT_KEYS.includes(c.key)
    ),
  };

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Settings"
        subtitle="Manage configuration"
        crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Settings' }]}
        containerClassName="max-w-4xl"
        actions={(
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className={cn('text-xs font-medium', systemStopped ? 'text-content-tertiary' : 'text-content-secondary')}
                title={systemStopped ? 'Resume the system to edit settings' : 'Toggle to enable editing'}>
                Edit Mode{systemStopped ? ' (locked)' : ''}
              </span>
              <Switch
                checked={editMode && !systemStopped}
                onCheckedChange={(v) => !systemStopped && setEditMode(v)}
                disabled={systemStopped}
                aria-label="Toggle edit mode"
              />
            </label>
            <Button
              onClick={toggleEmergency}
              size="sm"
              leftIcon={emergency ? <Power size={14} /> : <PowerOff size={14} />}
              title={emergency ? 'Resume all paused workflows and re-enable the system' : 'Freeze the entire system and pause all running workflows'}
              className={cn(
                emergency
                  ? 'bg-status-success hover:bg-status-success/90 text-content-inverse'
                  : 'bg-status-error hover:bg-status-error/90 text-content-inverse hover:shadow-lg'
              )}
            >
              {emergency ? 'Resume System' : 'Emergency Stop'}
            </Button>
          </div>
        )}
      />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <DisplayPreferences />
          {configError && (
            <div className="mb-6 p-4 rounded-lg bg-status-error/10 border border-status-error/20 text-sm">
              <span className="font-semibold text-status-error">Config load failed: </span>
              <span className="text-content-secondary">{configError}</span>
              <Button variant="link" size="sm" onClick={loadConfigs} className="ml-3 h-auto p-0 text-xs">Retry</Button>
            </div>
          )}
          {Object.entries(groups).map(([group, items]) => (
            items.length > 0 && (
              <div key={group} className="mb-8">
                <h2 className="text-xs font-semibold text-content-secondary mb-3 flex items-center gap-2">
                  {GROUP_LABELS[group] || group}
                  <span className="text-content-tertiary font-normal">({items.length})</span>
                </h2>
                <div className={cn('card divide-y divide-border', systemStopped && 'lockdown-frost')}>
                  {items.map((cfg: any) => (
                    <ConfigRow
                      key={cfg.key}
                      cfg={cfg}
                      editMode={editMode}
                      isEditing={editing === cfg.key}
                      editValue={editValue}
                      chipInput={chipInput}
                      jsonError={jsonError}
                      onStartEdit={() => startEdit(cfg.key, cfg.value)}
                      onEditValueChange={setEditValue}
                      onChipInputChange={setChipInput}
                      onAddChip={addChip}
                      onRemoveChip={removeChip}
                      onSave={() => saveConfig(cfg.key)}
                      onCancel={() => { setEditing(null); setJsonError(''); }}
                      onToggleBool={() => toggleBool(cfg.key, cfg.value)}
                    />
                  ))}
                </div>
              </div>
            )
          ))}

          {/* Danger Zone */}
          <div className="mb-8">
            <h2 className="text-xs font-semibold text-status-error mb-3 flex items-center gap-2">
              Danger Zone
            </h2>
            <div className="card border-status-error/30 bg-status-error/5 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="text-sm font-medium text-content-primary">Clean Slate — Reset All Jobs</div>
                  <div className="text-xs text-content-tertiary mt-1">
                    Wipes all video history, job events, analytics, renders, and checkpoints.
                    Preserves channels, brand profiles, config, prompts, and ML models.
                    Dashboard returns to <span className="font-mono">0 delivered · 0 in-progress · 0 total</span>.
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
        </div>
      </main>

      {/* Clean Slate Confirmation Modal */}
      <Dialog
        open={cleanSlateOpen}
        onOpenChange={(o) => { if (!o && !cleanSlateRunning) { setCleanSlateOpen(false); setCleanSlateInput(''); } }}
      >
        <DialogContent className="max-w-md border-status-error/30">
          <DialogHeader>
            <div className="flex items-start gap-3">
              <div className="shrink-0 w-10 h-10 rounded-full bg-status-error/10 flex items-center justify-center text-status-error text-lg font-bold">!</div>
              <div>
                <DialogTitle>This will delete ALL job history</DialogTitle>
                <DialogDescription>This action cannot be undone.</DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <div className="space-y-3 text-xs">
            <div>
              <div className="font-medium text-status-error mb-1">Will be wiped:</div>
              <ul className="list-disc pl-5 text-content-secondary space-y-0.5">
                <li>All videos, job events, and analytics records</li>
                <li>All feedback and experiment data</li>
                <li>All MinIO blobs (renders, checkpoints, assets)</li>
                <li>All running Temporal workflows (terminated)</li>
                <li>All Redis channel locks</li>
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
          <div>
            <Label htmlFor="reset-confirm" className="text-xs text-content-secondary mb-1.5 block">
              Type <span className="font-mono font-semibold text-status-error">RESET</span> to confirm:
            </Label>
            <Input
              id="reset-confirm"
              type="text"
              value={cleanSlateInput}
              onChange={e => setCleanSlateInput(e.target.value)}
              disabled={cleanSlateRunning}
              placeholder="RESET"
              className="font-mono"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { setCleanSlateOpen(false); setCleanSlateInput(''); }}
              disabled={cleanSlateRunning}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCleanSlate}
              disabled={cleanSlateInput !== 'RESET' || cleanSlateRunning}
              loading={cleanSlateRunning}
            >
              {cleanSlateRunning ? 'Wiping…' : 'Clean Slate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ConfigRow({ cfg, editMode, isEditing, editValue, chipInput, jsonError,
  onStartEdit, onEditValueChange, onChipInputChange, onAddChip, onRemoveChip,
  onSave, onCancel, onToggleBool }: {
  cfg: any; editMode: boolean; isEditing: boolean; editValue: string;
  chipInput: string; jsonError: string;
  onStartEdit: () => void; onEditValueChange: (v: string) => void;
  onChipInputChange: (v: string) => void; onAddChip: () => void;
  onRemoveChip: (i: number) => void; onSave: () => void; onCancel: () => void;
  onToggleBool: () => void;
}) {
  const sensitive = isSensitive(cfg.key);
  const isBool = isBooleanValue(cfg.value);
  const isJson = isJsonObject(cfg.value);
  const isArr = isJsonArray(cfg.value);

  // Display value
  let displayValue = cfg.value || '—';
  if (sensitive && !isEditing) displayValue = '••••••••';
  if (isJson && !isEditing) {
    try { displayValue = JSON.stringify(JSON.parse(cfg.value), null, 0).slice(0, 60) + (cfg.value.length > 60 ? '…' : ''); } catch {}
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
              checked={cfg.value === 'true'}
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
                      <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-2 text-content-secondary">
                        {String(item)}
                      </span>
                    ));
                  } catch { return <span className="text-xs text-content-tertiary">{displayValue}</span>; }
                })()}
                {(() => { try { return JSON.parse(cfg.value).length > 5 ? <span className="text-[11px] text-content-tertiary">+{JSON.parse(cfg.value).length - 5}</span> : null; } catch { return null; } })()}
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
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-surface-2 text-content-primary">
                        {String(item)}
                        <button onClick={() => onRemoveChip(i)} className="text-content-tertiary hover:text-status-error ml-0.5">×</button>
                      </span>
                    ));
                  } catch { return null; }
                })()}
              </div>
              <div className="flex gap-2">
                <Input
                  value={chipInput}
                  onChange={(e) => onChipInputChange(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAddChip(); } }}
                  placeholder="Type and press Enter to add"
                  className="flex-1 h-8 text-xs"
                />
                <Button variant="secondary" size="sm" onClick={onAddChip}>Add</Button>
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
                  aria-describedby={jsonError ? 'json-error' : undefined}
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
                  <p id="json-error" className="text-xs text-status-error" role="alert">{jsonError}</p>
                ) : (
                  <p className="text-[10px] text-content-tertiary">JSON is valid.</p>
                )}
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  disabled={!!jsonError}
                  onClick={() => {
                    try { onEditValueChange(JSON.stringify(JSON.parse(editValue), null, 2)); } catch {}
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
            <Button variant="secondary" size="sm" onClick={onCancel}>Cancel</Button>
            <Button size="sm" onClick={onSave} disabled={!!jsonError}>Save</Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Display Preferences card — theme + density
// ──────────────────────────────────────────────────────────────
function DisplayPreferences() {
  const { theme, setTheme } = useTheme();
  const { density, setDensity } = useAppState();

  const themeOpts: { value: 'light' | 'dark' | 'system'; label: string }[] = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
    { value: 'system', label: 'System' },
  ];
  const densityOpts: { value: 'comfortable' | 'compact'; label: string }[] = [
    { value: 'comfortable', label: 'Comfortable' },
    { value: 'compact', label: 'Compact' },
  ];

  return (
    <div className="mb-8">
      <h2 className="text-xs font-semibold text-content-secondary mb-3 flex items-center gap-2">
        Display
      </h2>
      <div className="card p-5 space-y-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm font-medium text-content-primary">Theme</div>
            <div className="text-xs text-content-tertiary mt-0.5">
              Light, dark, or follow your operating system.
            </div>
          </div>
          <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-lg bg-surface-2 p-1">
            {themeOpts.map((opt) => (
              <button
                key={opt.value}
                role="radio"
                aria-checked={theme === opt.value}
                onClick={() => setTheme(opt.value)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  theme === opt.value
                    ? 'bg-surface-0 text-content-primary shadow-card'
                    : 'text-content-tertiary hover:text-content-primary',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm font-medium text-content-primary">Density</div>
            <div className="text-xs text-content-tertiary mt-0.5">
              Compact tightens spacing in cards and list rows.
            </div>
          </div>
          <div role="radiogroup" aria-label="Density" className="inline-flex rounded-lg bg-surface-2 p-1">
            {densityOpts.map((opt) => (
              <button
                key={opt.value}
                role="radio"
                aria-checked={density === opt.value}
                onClick={() => setDensity(opt.value)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  density === opt.value
                    ? 'bg-surface-0 text-content-primary shadow-card'
                    : 'text-content-tertiary hover:text-content-primary',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
