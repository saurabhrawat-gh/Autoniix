import { z } from "zod";

/**
 * Direction Format v3.1 — granular editorial contract.
 *
 * v3.1 extends v3.0 with the granularity needed for professional-tier editing:
 *   - `timeline[]` per segment — anchor keyframes at ≤500ms spacing (½-sec floor).
 *     Each keyframe carries full editorial state (camera, effects, lighting,
 *     text visibility, overlay opacity, audio ducking). Between keyframes,
 *     Remotion interpolates via the `ease` field on each keyframe.
 *   - `captions[]` per segment — word-level timing (from Inworld TTS
 *     word_alignment or whisperx fallback). Enables word-perfect subtitle
 *     rendering and per-word emphasis animations.
 *   - `micro_beats[]` per segment — sub-100ms hit markers merged from voice
 *     emphasis_hits + music beat_map_ms + asset cut_suggestions_ms.
 *     Fires punch-zooms, flashes, cuts on exact frames.
 *   - `audio_track` per segment — measured voice URL/gain, music URL/gain,
 *     and a per-frame ducking_envelope so music dips exactly during speech.
 *   - `layers[]` per segment — parallax / PIP / secondary video stacks.
 *
 * Backward compatibility: all new fields are optional. A v3.0 payload
 * parses under v3.1 unchanged. The `direction` service upgrades v3.0 →
 * v3.1 in-place via the densifier described in the plan.
 *
 * Rule (enforced by validator, not by Zod alone):
 *   for every segment, `timeline` covers [0, duration_ms] with each pair
 *   of consecutive `t_ms` values ≤ 500 ms apart (the ½-second floor).
 *   `assembly` service will auto-interpolate + raise a sync_issues warning
 *   when the input is sparser than that.
 */

const presetId = z.string().min(1);

const PresetRef = z.object({
  preset: presetId,
  overrides: z.record(z.unknown()).optional(),
});

const Animation = z.object({
  preset: presetId,
  target: z.string().optional(),
  overrides: z.record(z.unknown()).optional(),
});

const SfxCue = z.object({
  preset: z.string(),
  at_ms: z.number().int().nonnegative(),
  volume_db: z.number().optional(),
});

// ── NEW in v3.1 ────────────────────────────────────────────────────────────

const EaseCurve = z.enum([
  "linear",
  "step",
  "cubic-in",
  "cubic-out",
  "cubic-in-out",
  "spring",
  "elastic-out",
  "back-out",
  "expo-out",
]);

const CameraState = z.object({
  x: z.number().default(0), // px, relative to composition center
  y: z.number().default(0),
  scale: z.number().positive().default(1), // 1.0 = fit; 1.15 = 15% zoom in
  rotation: z.number().default(0), // degrees
  anchor: z.tuple([z.number(), z.number()]).default([0.5, 0.5]), // normalized [0..1] pivot
});

const EffectsIntensity = z.object({
  grade_strength: z.number().min(0).max(1).default(1), // color-grade LUT mix amount
  vignette: z.number().min(0).max(1).default(0),
  blur_px: z.number().min(0).default(0),
  chroma: z.number().min(0).max(1).default(0), // chromatic aberration
  grain: z.number().min(0).max(1).default(0),
  bloom: z.number().min(0).max(1).default(0),
});

const LightingState = z.object({
  exposure: z.number().default(0), // stops, ±3
  contrast: z.number().positive().default(1),
  saturation: z.number().nonnegative().default(1),
  temperature: z.number().default(0), // -100..+100 (cool→warm)
  tint: z.number().default(0), // green↔magenta
});

const TextState = z.object({
  visible_word_index: z.number().int().nonnegative().default(0), // reveal index for typewriter/karaoke
  emphasis_word_index: z.number().int().nonnegative().nullable().default(null),
  opacity: z.number().min(0).max(1).default(1),
  scale: z.number().positive().default(1),
});

const OverlayOpacity = z.object({
  lower_third: z.number().min(0).max(1).default(0),
  watermark: z.number().min(0).max(1).default(1),
  caption: z.number().min(0).max(1).default(1),
  progress_bar: z.number().min(0).max(1).default(0),
});

/**
 * Anchor keyframe. At least one keyframe per ½-second is required (assembly
 * enforces). Values here are what the state SHOULD BE at `t_ms`; between
 * consecutive keyframes Remotion interpolates using the `ease` on the
 * later keyframe.
 */
const TimelineKeyframe = z.object({
  t_ms: z.number().int().nonnegative(), // absolute ms within the segment
  ease: EaseCurve.default("cubic-in-out"),
  camera: CameraState.partial().optional(),
  effects: EffectsIntensity.partial().optional(),
  lighting: LightingState.partial().optional(),
  text_state: TextState.partial().optional(),
  overlay_opacity: OverlayOpacity.partial().optional(),
  audio_ducking_db: z.number().optional(), // 0 = no duck, -12 = duck music by 12 dB
});

const CaptionWord = z.object({
  word: z.string(),
  start_ms: z.number().int().nonnegative(),
  end_ms: z.number().int().positive(),
  is_emphasis: z.boolean().default(false),
  sentence_id: z.string().optional(),
  style_id: z.string().optional(), // preset ID for this word's caption style
});

const MicroBeatKind = z.enum([
  "hit", // impact — flash, shake, thud
  "cut", // scene change
  "reveal", // text/overlay appears
  "zoom_punch", // rapid zoom-in
  "flash", // 1–2 frame full-screen flash
  "sfx", // trigger an SFX
]);

const MicroBeat = z.object({
  at_ms: z.number().int().nonnegative(),
  kind: MicroBeatKind,
  source: z.enum(["voice_emphasis", "music_beat", "asset_cut", "narrative", "manual"]),
  intensity: z.number().min(0).max(1).default(0.5),
  payload: z.record(z.unknown()).optional(), // kind-specific extras
});

const DuckingEnvelopePoint = z.object({
  t_ms: z.number().int().nonnegative(),
  gain_db: z.number(), // e.g. 0 during silence, -12 during speech
});

const AudioTrack = z.object({
  voiceover_url: z.string().url().optional(),
  voiceover_start_ms: z.number().int().nonnegative().default(0),
  voiceover_gain_db: z.number().default(0),
  music_bed_url: z.string().url().optional(),
  music_gain_db: z.number().default(-8), // typical music bed sits ~8 dB below voice
  ducking_envelope: z.array(DuckingEnvelopePoint).optional(),
  loudness_target_lufs: z.number().default(-14), // YouTube target
});

const Layer = z.object({
  z: z.number().int().default(0), // stack order — higher = on top
  asset_url: z.string().url(),
  fit: z.enum(["cover", "contain", "fill"]).default("cover"),
  transform_keyframes: z
    .array(TimelineKeyframe.partial().extend({ t_ms: z.number().int().nonnegative() }))
    .optional(),
  opacity_keyframes: z
    .array(z.object({ t_ms: z.number().int().nonnegative(), opacity: z.number().min(0).max(1) }))
    .optional(),
});

// ── Segment (v3.0 fields kept + v3.1 fields added) ─────────────────────────

const Segment = z.object({
  // v3.0 (unchanged)
  id: z.string(),
  start_ms: z.number().int().nonnegative(),
  duration_ms: z.number().int().positive(),
  scene_preset: presetId,
  scene_overrides: z.record(z.unknown()).optional(),
  animations_in: z.array(Animation).optional(),
  animations_out: z.array(Animation).optional(),
  effects: z.array(presetId).optional(),
  overlays: z.array(PresetRef).optional(),
  sfx: z.array(SfxCue).optional(),
  transition_out: PresetRef.optional(),

  // v3.1 additions (all optional for backward-compat)
  timeline: z.array(TimelineKeyframe).optional(),
  captions: z.array(CaptionWord).optional(),
  micro_beats: z.array(MicroBeat).optional(),
  audio_track: AudioTrack.optional(),
  layers: z.array(Layer).optional(),
  is_hero_moment: z.boolean().optional(), // hook / punchline / reveal → gets multi-take voice
});

const Theme = z.object({
  primary_color: z.string(),
  accent_color: z.string(),
  background_color: z.string(),
  text_color: z.string(),
  fonts: z.object({ heading: z.string(), body: z.string() }),
});

const Audio = z.object({
  voiceover_url: z.string().url().optional(),
  voiceover_srt_url: z.string().url().optional(),
  music_url: z.string().url().optional(),
  music_volume_db: z.number().optional(),
  ducking: z
    .object({
      enabled: z.boolean(),
      threshold_db: z.number(),
      attack_ms: z.number(),
      release_ms: z.number(),
    })
    .optional(),
  loudness_target_lufs: z.number().optional(),
});

const Branding = z
  .object({
    intro_preset: z.string().optional(),
    outro_preset: z.string().optional(),
    watermark: PresetRef.optional(),
  })
  .optional();

const Meta = z.object({
  video_id: z.string(),
  channel_id: z.string(),
  title: z.string(),
  duration_target_seconds: z.number().positive(),
  aspect: z.enum(["16:9", "9:16", "1:1"]),
  fps: z.number().int().positive(),
  resolution: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
  }),
});

const Thumbnail = z
  .object({
    composition: z.literal("ThumbnailComp"),
    layout_preset: z.string(),
    background_url: z.string().url(),
    title: z.object({
      text: z.string(),
      font: z.string(),
      weight: z.number(),
      size: z.number(),
      color: z.string(),
      stroke: z.object({ color: z.string(), width: z.number() }).optional(),
    }),
    format: z.enum(["png", "jpg"]),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
  })
  .optional();

export const DirectionV3_1 = z.object({
  version: z.union([z.literal("3.0"), z.literal("3.1")]), // accept both
  meta: Meta,
  template: z.string(),
  theme: Theme,
  grade_preset: presetId,
  global_effects: z.array(presetId).optional(),
  global_overlays: z.array(PresetRef).optional(),
  audio: Audio.optional(),
  branding: Branding,
  segments: z.array(Segment).min(1),
  thumbnail: Thumbnail,
});

export type DirectionV3_1Input = z.infer<typeof DirectionV3_1>;
export type SegmentV3_1 = z.infer<typeof Segment>;
export type TimelineKeyframeInput = z.infer<typeof TimelineKeyframe>;
export type CaptionWordInput = z.infer<typeof CaptionWord>;
export type MicroBeatInput = z.infer<typeof MicroBeat>;
export type AudioTrackInput = z.infer<typeof AudioTrack>;
export type LayerInput = z.infer<typeof Layer>;

/**
 * Runtime check: every segment's `timeline` must cover [0, duration_ms]
 * with consecutive keyframes ≤ 500 ms apart. Returns a list of issues.
 * Empty list = passes. Call this in `assembly` after densification.
 */
export const MAX_KEYFRAME_GAP_MS = 500;

export function validateTimelineDensity(direction: DirectionV3_1Input): string[] {
  const issues: string[] = [];
  for (const seg of direction.segments) {
    if (!seg.timeline || seg.timeline.length === 0) {
      // v3.1 permits omission — density is only checked when timeline is present.
      continue;
    }
    const kfs = [...seg.timeline].sort((a, b) => a.t_ms - b.t_ms);
    const first = kfs[0];
    const last = kfs[kfs.length - 1];
    if (!first || !last) continue;
    if (first.t_ms > 0) {
      issues.push(`segment ${seg.id}: first keyframe at ${first.t_ms}ms, expected 0`);
    }
    if (last.t_ms < seg.duration_ms - MAX_KEYFRAME_GAP_MS) {
      issues.push(
        `segment ${seg.id}: last keyframe at ${last.t_ms}ms leaves > ${MAX_KEYFRAME_GAP_MS}ms tail before segment end (${seg.duration_ms}ms)`,
      );
    }
    for (let i = 1; i < kfs.length; i++) {
      const prev = kfs[i - 1];
      const curr = kfs[i];
      if (!prev || !curr) continue;
      const gap = curr.t_ms - prev.t_ms;
      if (gap > MAX_KEYFRAME_GAP_MS) {
        issues.push(
          `segment ${seg.id}: keyframe gap ${gap}ms between t=${prev.t_ms} and t=${curr.t_ms} exceeds ${MAX_KEYFRAME_GAP_MS}ms floor`,
        );
      }
    }
  }
  return issues;
}
