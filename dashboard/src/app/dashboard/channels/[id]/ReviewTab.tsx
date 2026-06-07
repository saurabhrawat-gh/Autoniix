'use client';

import { useEffect, useState, useCallback } from 'react';
import { reviewConfigApi, ReviewProfile, ReviewConfig, ReviewGates } from '@/lib/api-v2';
import { useToast } from '@/lib/toast';
import { Button, Switch, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/lib/ui';
import { ClipboardCheck, ShieldCheck, SlidersHorizontal } from '@/lib/components/Icon';

interface Props {
  channelId: string;
}

const PROFILES: { value: ReviewProfile; label: string; description: string }[] = [
  { value: 'hands_off',    label: 'Hands-off',    description: 'No gates — pipeline runs straight through (default).' },
  { value: 'quick',        label: 'Quick',        description: 'Gates on script + final video only (2 checkpoints).' },
  { value: 'standard',     label: 'Standard',     description: 'Gates on title, script, metadata, thumbnail & final video.' },
  { value: 'full_control', label: 'Full Control', description: 'All 13 artifact gates ON — maximum oversight.' },
  { value: 'custom',       label: 'Custom',       description: 'Toggle each gate individually.' },
];

const GATE_META: { key: keyof ReviewGates; label: string; phase: string }[] = [
  { key: 'research_data',         label: 'Research data',         phase: 'Researching' },
  { key: 'brand_alignment_report',label: 'Brand alignment report', phase: 'Brand check' },
  { key: 'topic_title',           label: 'Topic / title',         phase: 'Scripting' },
  { key: 'story_script',          label: 'Story script',          phase: 'Scripting' },
  { key: 'script_voice_data',     label: 'Voice script',          phase: 'Scripting' },
  { key: 'script_assets_data',    label: 'Asset prompts',         phase: 'Scripting' },
  { key: 'script_direction_data', label: 'Direction JSON',        phase: 'Scripting' },
  { key: 'voice_track',           label: 'Voice track',           phase: 'Voice gen' },
  { key: 'scene_images',          label: 'Scene images / B-roll', phase: 'Asset gen' },
  { key: 'remotion_v3_json',      label: 'Edit JSON (Remotion)',  phase: 'Directing' },
  { key: 'metadata',              label: 'Metadata & SEO',        phase: 'Post-prod' },
  { key: 'thumbnail',             label: 'Thumbnail',             phase: 'Post-prod' },
  { key: 'final_video',           label: 'Final video',           phase: 'Rendering' },
];

const DEFAULT_GATES: ReviewGates = {
  research_data: false, brand_alignment_report: false, topic_title: false,
  story_script: false, script_voice_data: false, script_assets_data: false,
  script_direction_data: false, voice_track: false, scene_images: false,
  remotion_v3_json: false, metadata: false, thumbnail: false, final_video: false,
};

function gatesForProfile(profile: ReviewProfile): ReviewGates {
  if (profile === 'hands_off')    return { ...DEFAULT_GATES };
  if (profile === 'quick')        return { ...DEFAULT_GATES, story_script: true, final_video: true };
  if (profile === 'standard')     return { ...DEFAULT_GATES, topic_title: true, story_script: true, metadata: true, thumbnail: true, final_video: true };
  if (profile === 'full_control') return {
    research_data: true, brand_alignment_report: true, topic_title: true,
    story_script: true, script_voice_data: true, script_assets_data: true,
    script_direction_data: true, voice_track: true, scene_images: true,
    remotion_v3_json: true, metadata: true, thumbnail: true, final_video: true,
  };
  return { ...DEFAULT_GATES };
}

export default function ReviewTab({ channelId }: Props) {
  const { showToast } = useToast();
  const [config, setConfig] = useState<ReviewConfig | null>(null);
  const [profile, setProfile] = useState<ReviewProfile>('hands_off');
  const [gates, setGates] = useState<ReviewGates>({ ...DEFAULT_GATES });
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await reviewConfigApi.get(channelId);
      const data = (r as any).data ?? r;
      setConfig(data);
      setProfile(data.profile ?? 'hands_off');
      setGates(data.gates ?? { ...DEFAULT_GATES });
    } catch {
      showToast('Failed to load review config', 'error');
    } finally {
      setLoading(false);
    }
  }, [channelId, showToast]);

  useEffect(() => { load(); }, [load]);

  const handleProfileChange = (p: ReviewProfile) => {
    setProfile(p);
    if (p !== 'custom') setGates(gatesForProfile(p));
    setDirty(true);
  };

  const toggleGate = (key: keyof ReviewGates) => {
    setGates(prev => ({ ...prev, [key]: !prev[key] }));
    if (profile !== 'custom') setProfile('custom');
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await reviewConfigApi.update(channelId, {
        profile,
        gates: profile === 'custom' ? gates : undefined,
      });
      setDirty(false);
      showToast('Review config saved', 'success');
    } catch {
      showToast('Failed to save review config', 'error');
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    if (!config) return;
    setProfile(config.profile);
    setGates(config.gates ?? { ...DEFAULT_GATES });
    setDirty(false);
  };

  const activeGateCount = Object.values(gates).filter(Boolean).length;

  if (loading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">Loading review config…</div>
    );
  }

  return (
    <div className="space-y-8 p-1">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-accent" />
            Review Gates
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Choose which artifacts require your approval before the pipeline proceeds.
            {activeGateCount > 0 && (
              <span className="ml-1 text-status-warning font-medium">{activeGateCount} gate{activeGateCount !== 1 ? 's' : ''} active</span>
            )}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {dirty && (
            <Button variant="ghost" size="sm" onClick={reset}>Reset</Button>
          )}
          <Button size="sm" onClick={save} loading={saving} disabled={!dirty || saving}>
            Save
          </Button>
        </div>
      </div>

      <section className="space-y-3">
        <Label className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" />
          Review profile
        </Label>
        <Select value={profile} onValueChange={v => handleProfileChange(v as ReviewProfile)}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROFILES.map(p => (
              <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {PROFILES.find(p => p.value === profile)?.description}
        </p>
      </section>

      <section className="space-y-3">
        <Label className="flex items-center gap-1.5">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          Per-artifact gates
          {profile !== 'custom' && (
            <span className="text-xs text-muted-foreground font-normal ml-1">
              (switch any toggle to enter Custom mode)
            </span>
          )}
        </Label>
        <div className="divide-y divide-border rounded-lg border border-border">
          {GATE_META.map(({ key, label, phase }) => (
            <div key={key} className="flex items-center justify-between px-4 py-3 gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{label}</p>
                <p className="text-xs text-muted-foreground">{phase}</p>
              </div>
              <Switch
                checked={gates[key]}
                onCheckedChange={() => toggleGate(key)}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
