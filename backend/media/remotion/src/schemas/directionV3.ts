import { z } from "zod";

/**
 * Direction Format v3 — contract between the AI director (upstream)
 * and the Remotion renderer. See docs/D-direction-format-v3-schema.md.
 *
 * NOTE: preset IDs are validated as strings here. Strict enum validation
 * against the registry happens in compositionValidator.ts (runtime, post-registry-load)
 * to avoid a circular import between schemas and registry.
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

const Segment = z.object({
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

export const DirectionV3 = z.object({
  version: z.literal("3.0"),
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

export type DirectionV3Input = z.infer<typeof DirectionV3>;
export type SegmentV3 = z.infer<typeof Segment>;
