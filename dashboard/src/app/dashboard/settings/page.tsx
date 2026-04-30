'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, isLoggedIn } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ThemeToggle, HomeLogo } from '@/lib/theme';

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
  const [emergency, setEmergency] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [jsonError, setJsonError] = useState('');
  const systemStopped = emergency;

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    loadConfigs();
  }, [router]);

  async function loadConfigs() {
    try {
      const res = await api.config();
      setConfigs(res.data);
      const isStopped = res.data.some((c: any) => c.key === 'emergency_stop' && c.value === 'true');
      setEmergency(isStopped);
      if (isStopped) { setEditMode(false); setEditing(null); }
    } catch {}
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
      await api.updateConfig(key, val);
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
      if (emergency) await api.emergencyResume();
      else await api.emergencyStop();
      loadConfigs();
    } catch {}
  }

  function startEdit(key: string, value: string) {
    setEditing(key);
    setEditValue(value);
    setJsonError('');
    setChipInput('');
  }

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

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
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
    <div className="h-screen flex flex-col">
      {/* Fixed Header */}
      <header className="sticky top-0 z-10 bg-surface-0 border-b border-border px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HomeLogo />
            <div>
              <h1 className="text-lg font-semibold text-content-primary">Settings</h1>
              <p className="text-xs text-content-tertiary mt-0.5">Manage configuration</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Edit Mode Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <span className={cn('text-xs font-medium', systemStopped ? 'text-content-tertiary' : 'text-content-secondary')}
                title={systemStopped ? 'Resume the system to edit settings' : 'Toggle to enable editing'}>
                Edit Mode{systemStopped ? ' (locked)' : ''}
              </span>
              <button
                onClick={systemStopped ? undefined : () => setEditMode(!editMode)}
                disabled={systemStopped}
                className={cn(
                  'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                  editMode && !systemStopped ? 'bg-accent' : 'bg-surface-3',
                  systemStopped && 'opacity-50 cursor-not-allowed'
                )}>
                <span className={cn(
                  'inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform',
                  editMode && !systemStopped ? 'translate-x-[18px]' : 'translate-x-[2px]'
                )} />
              </button>
            </label>
            <ThemeToggle />
            <button onClick={toggleEmergency}
              title={emergency ? 'Resume all paused workflows and re-enable the system' : 'Freeze the entire system and pause all running workflows'}
              className={cn(
                'px-4 py-2 rounded-lg text-xs font-medium transition-all',
                emergency
                  ? 'bg-status-success text-white hover:opacity-90'
                  : 'bg-status-error text-white hover:opacity-90 hover:shadow-lg'
              )}>
              {emergency ? '▶ Resume System' : '■ Emergency Stop'}
            </button>
          </div>
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-6">
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
        </div>
      </main>
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
            <button
              onClick={editMode ? onToggleBool : undefined}
              disabled={!editMode}
              className={cn(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                cfg.value === 'true' ? 'bg-accent' : 'bg-surface-3',
                !editMode && 'opacity-60 cursor-not-allowed'
              )}>
              <span className={cn(
                'inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
                cfg.value === 'true' ? 'translate-x-[22px]' : 'translate-x-[3px]'
              )} />
            </button>
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
              <button onClick={onStartEdit}
                className="text-xs text-accent hover:text-accent-hover font-medium transition-colors shrink-0">
                Edit
              </button>
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
                <input
                  value={chipInput}
                  onChange={(e) => onChipInputChange(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAddChip(); } }}
                  placeholder="Type and press Enter to add"
                  className="!flex-1 !py-1.5 !px-3 !text-xs"
                />
                <button onClick={onAddChip} className="btn-secondary !py-1.5 !px-3 !text-xs">Add</button>
              </div>
            </div>
          ) : isJson ? (
            /* JSON editor: textarea */
            <div>
              <textarea
                value={(() => { try { return JSON.stringify(JSON.parse(editValue), null, 2); } catch { return editValue; } })()}
                onChange={(e) => onEditValueChange(e.target.value)}
                className="!w-full !py-2 !px-3 !text-xs font-mono !min-h-[120px] !resize-y"
              />
              {jsonError && <p className="text-xs text-status-error mt-1">{jsonError}</p>}
            </div>
          ) : (
            /* Regular text input */
            <input
              value={editValue}
              onChange={(e) => onEditValueChange(e.target.value)}
              type={sensitive ? 'text' : 'text'}
              className="!w-full !py-1.5 !px-3 !text-xs"
              autoFocus
            />
          )}
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={onCancel} className="btn-secondary !py-1.5 !px-3 !text-xs">Cancel</button>
            <button onClick={onSave} className="btn-primary !py-1.5 !px-3 !text-xs">Save</button>
          </div>
        </div>
      )}
    </div>
  );
}
