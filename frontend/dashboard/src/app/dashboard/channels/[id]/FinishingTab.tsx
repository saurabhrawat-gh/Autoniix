"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { finishingApi, type FinishingConfig, type FinishingPreset } from "@/lib/api-v2";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { Button, Switch, Input, Label } from "@/lib/ui";
import { Palette, Headphones, Save, RotateCcw, Film, SlidersHorizontal, Check } from "@/lib/components/Icon";

interface FinishingTabProps {
  channelId: string;
}

const LOUDNESS_MIN = -24;
const LOUDNESS_MAX = -9;
const TRUE_PEAK_MIN = -6;
const TRUE_PEAK_MAX = -0.1;

type EditableConfig = Omit<FinishingConfig, "channel_id" | "updated_at">;
type BoolKey = "audio_denoise" | "audio_eq" | "audio_compress" | "audio_music_duck";

const EDITABLE_KEYS: (keyof EditableConfig)[] = [
  "require_resolve_finish",
  "color_grade_preset",
  "audio_denoise",
  "audio_eq",
  "audio_compress",
  "audio_music_duck",
  "audio_loudness_lufs",
  "audio_true_peak_dbtps",
  "output_prores_archive",
];

const AUDIO_TOGGLES: { key: BoolKey; label: string; hint: string }[] = [
  { key: "audio_denoise", label: "Denoise", hint: "Remove background hiss and hum" },
  { key: "audio_eq", label: "EQ", hint: "Tonal balance for voice clarity" },
  { key: "audio_compress", label: "Compression", hint: "Even out loud and quiet passages" },
  { key: "audio_music_duck", label: "Music ducking", hint: "Lower music under narration" },
];

function pickEditable(cfg: FinishingConfig): EditableConfig {
  return {
    require_resolve_finish: cfg.require_resolve_finish,
    color_grade_preset: cfg.color_grade_preset,
    audio_denoise: cfg.audio_denoise,
    audio_eq: cfg.audio_eq,
    audio_compress: cfg.audio_compress,
    audio_music_duck: cfg.audio_music_duck,
    audio_loudness_lufs: cfg.audio_loudness_lufs,
    audio_true_peak_dbtps: cfg.audio_true_peak_dbtps,
    output_prores_archive: cfg.output_prores_archive,
  };
}

export default function FinishingTab({ channelId }: FinishingTabProps) {
  const { showToast } = useToast();
  const [presets, setPresets] = useState<FinishingPreset[]>([]);
  const [server, setServer] = useState<EditableConfig | null>(null);
  const [form, setForm] = useState<EditableConfig | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [brokenThumbs, setBrokenThumbs] = useState<Set<string>>(new Set());

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      finishingApi.get(channelId),
      finishingApi
        .presets()
        .then((r) => r.presets)
        .catch(() => [] as FinishingPreset[]),
    ])
      .then(([cfg, ps]) => {
        const editable = pickEditable(cfg);
        setServer(editable);
        setForm(editable);
        setUpdatedAt(cfg.updated_at);
        setPresets(ps);
      })
      .catch((e: any) => showToast(e?.message || "Failed to load finishing settings", "error"))
      .finally(() => setLoading(false));
  }, [channelId, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  const set = <K extends keyof EditableConfig>(key: K, value: EditableConfig[K]) =>
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const loudnessValid = form
    ? Number.isFinite(form.audio_loudness_lufs) &&
      form.audio_loudness_lufs >= LOUDNESS_MIN &&
      form.audio_loudness_lufs <= LOUDNESS_MAX
    : true;
  const truePeakValid = form
    ? Number.isFinite(form.audio_true_peak_dbtps) &&
      form.audio_true_peak_dbtps >= TRUE_PEAK_MIN &&
      form.audio_true_peak_dbtps <= TRUE_PEAK_MAX
    : true;
  const valid = loudnessValid && truePeakValid;

  const dirty = useMemo(() => {
    if (!form || !server) return false;
    return EDITABLE_KEYS.some((k) => form[k] !== server[k]);
  }, [form, server]);

  const save = async () => {
    if (!form || !server || !dirty || !valid) return;
    const changed: Record<string, unknown> = {};
    for (const k of EDITABLE_KEYS) {
      if (form[k] !== server[k]) changed[k] = form[k];
    }
    setSaving(true);
    try {
      const updated = await finishingApi.update(channelId, changed);
      const editable = pickEditable(updated);
      setServer(editable);
      setForm(editable);
      setUpdatedAt(updated.updated_at);
      showToast("Finishing settings saved", "success");
    } catch (e: any) {
      showToast(e?.message || "Failed to save", "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    if (server) setForm(server);
  };

  if (loading || !form) {
    return <div className="p-6 text-sm text-content-tertiary text-center">Loading finishing settings…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="text-xs text-content-tertiary">
        Post-render finishing applied after assembly: a colour-grade LUT and audio mastering. Phase 1A runs in-process
        with ffmpeg; enabling “Force DaVinci Resolve” routes the render through the Resolve finishing service when it is
        available.
      </div>

      <section>
        <div className="flex items-center gap-1.5 mb-2">
          <Palette size={13} className="text-content-tertiary" />
          <span className="text-[10px] uppercase tracking-wide text-content-tertiary">Colour grade preset</span>
        </div>
        {presets.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-1/40 px-3 py-3 text-xs text-content-tertiary text-center">
            No presets available.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {presets.map((p) => {
              const selected = form.color_grade_preset === p.key;
              const showThumb = !brokenThumbs.has(p.key) && !!p.thumbnail_url;
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => set("color_grade_preset", p.key)}
                  aria-pressed={selected}
                  className={cn(
                    "text-left rounded-lg border overflow-hidden transition-colors",
                    selected ? "border-accent ring-2 ring-accent/40" : "border-border hover:border-content-tertiary"
                  )}
                >
                  <div className="aspect-video bg-surface-2 relative">
                    {showThumb ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={p.thumbnail_url}
                        alt={p.display_name}
                        className="w-full h-full object-cover"
                        onError={() => setBrokenThumbs((prev) => new Set(prev).add(p.key))}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Film size={18} className="text-content-tertiary" />
                      </div>
                    )}
                    {selected && (
                      <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-accent flex items-center justify-center">
                        <Check size={10} className="text-content-inverse" />
                      </div>
                    )}
                  </div>
                  <div className="p-2">
                    <div className="text-xs font-medium text-content-primary">{p.display_name}</div>
                    <div className="text-[10px] text-content-tertiary line-clamp-2 mt-0.5">{p.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <div className="flex items-center gap-1.5 mb-2">
          <Headphones size={13} className="text-content-tertiary" />
          <span className="text-[10px] uppercase tracking-wide text-content-tertiary">Audio mastering</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {AUDIO_TOGGLES.map((t) => (
            <label
              key={t.key}
              className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-0 px-3 py-2 cursor-pointer"
            >
              <div className="min-w-0">
                <div className="text-sm text-content-primary">{t.label}</div>
                <div className="text-[10px] text-content-tertiary">{t.hint}</div>
              </div>
              <Switch checked={form[t.key]} onCheckedChange={(v: boolean) => set(t.key, v)} />
            </label>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          <div>
            <Label htmlFor="finishing-loudness" className="text-[10px] uppercase tracking-wide text-content-tertiary">
              Loudness target (LUFS)
            </Label>
            <Input
              id="finishing-loudness"
              type="number"
              step={0.5}
              min={LOUDNESS_MIN}
              max={LOUDNESS_MAX}
              value={Number.isFinite(form.audio_loudness_lufs) ? form.audio_loudness_lufs : ""}
              onChange={(e) => set("audio_loudness_lufs", parseFloat(e.target.value))}
              error={!loudnessValid}
              hint={`${LOUDNESS_MIN} to ${LOUDNESS_MAX} LUFS · YouTube target ≈ −14`}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="finishing-truepeak" className="text-[10px] uppercase tracking-wide text-content-tertiary">
              True peak ceiling (dBTP)
            </Label>
            <Input
              id="finishing-truepeak"
              type="number"
              step={0.1}
              min={TRUE_PEAK_MIN}
              max={TRUE_PEAK_MAX}
              value={Number.isFinite(form.audio_true_peak_dbtps) ? form.audio_true_peak_dbtps : ""}
              onChange={(e) => set("audio_true_peak_dbtps", parseFloat(e.target.value))}
              error={!truePeakValid}
              hint={`${TRUE_PEAK_MIN} to ${TRUE_PEAK_MAX} dBTP · recommended −1.5`}
              className="mt-1"
            />
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center gap-1.5 mb-2">
          <SlidersHorizontal size={13} className="text-content-tertiary" />
          <span className="text-[10px] uppercase tracking-wide text-content-tertiary">Output</span>
        </div>
        <div className="space-y-2">
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-0 px-3 py-2 cursor-pointer">
            <div className="min-w-0">
              <div className="text-sm text-content-primary">Force DaVinci Resolve finish</div>
              <div className="text-[10px] text-content-tertiary">
                Require the Resolve finishing service (Phase 1B). When off, ffmpeg is used and the render is delivered
                even if Resolve is unavailable.
              </div>
            </div>
            <Switch
              checked={form.require_resolve_finish}
              onCheckedChange={(v: boolean) => set("require_resolve_finish", v)}
            />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-0 px-3 py-2 cursor-pointer">
            <div className="min-w-0">
              <div className="text-sm text-content-primary">Export ProRes archive master</div>
              <div className="text-[10px] text-content-tertiary">Keep a high-bitrate ProRes copy for archival.</div>
            </div>
            <Switch
              checked={form.output_prores_archive}
              onCheckedChange={(v: boolean) => set("output_prores_archive", v)}
            />
          </label>
        </div>
      </section>

      <div className="flex items-center justify-between gap-3 pt-3 border-t border-border">
        <div className="text-[10px] text-content-tertiary">
          {updatedAt ? `Last updated ${new Date(updatedAt).toLocaleString()}` : "Not yet customised"}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={reset}
            disabled={!dirty || saving}
            leftIcon={<RotateCcw size={12} />}
          >
            Reset
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={save}
            disabled={!dirty || !valid || saving}
            loading={saving}
            leftIcon={<Save size={12} />}
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}
