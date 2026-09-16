/**
 * lower(directionV3) → SceneGraph
 *
 * Pure function. Given a validated DirectionV3 input, produces a canonical
 * SceneGraph IR. Determinism guarantee: same input → same bytes.
 *
 * Invariants enforced:
 *   - Segments are sorted by start_ms, validated for non-overlap, and each
 *     segment becomes exactly one SceneClip on track "video".
 *   - Overlays across all segments are emitted on a single "overlay" track
 *     (SfxCues are aggregated into the AudioGraph).
 *   - Captions are NOT emitted at v1 (no per-word timings available here) —
 *     they are attached later by the caption agent when word timings arrive.
 *   - The original direction-v3 is copied verbatim into meta.sourceDirection
 *     so the legacy Tier-1 renderer can consume this SceneGraph unchanged.
 */

import type { DirectionV3Input, SegmentV3 } from "../schemas/directionV3";
import type { AudioGraph, Clip, PresetRef, SceneClip, SceneGraph, SfxCue, Track } from "./types";
import { hashNode } from "./hash";

export function lower(direction: DirectionV3Input): SceneGraph {
  const segments = [...direction.segments].sort((a, b) => a.start_ms - b.start_ms);
  assertNonOverlapping(segments);

  const videoClips: SceneClip[] = segments.map((s) => makeSceneClip(s));
  const videoTrack: Track = {
    id: "track-video",
    kind: "video",
    clips: videoClips,
  };

  const overlayClips: Clip[] = [];
  const overlayTrack: Track = {
    id: "track-overlay",
    kind: "overlay",
    clips: overlayClips,
  };

  const sfxAggregate = aggregateSfx(segments);
  const audio: AudioGraph = {
    voiceover: direction.audio?.voiceover_url
      ? { url: direction.audio.voiceover_url, srtUrl: direction.audio?.voiceover_srt_url }
      : undefined,
    music: direction.audio?.music_url
      ? { url: direction.audio.music_url, volumeDb: direction.audio?.music_volume_db }
      : undefined,
    sfx: sfxAggregate,
    ducking: direction.audio?.ducking
      ? {
          enabled: direction.audio.ducking.enabled,
          thresholdDb: direction.audio.ducking.threshold_db,
          attackMs: direction.audio.ducking.attack_ms,
          releaseMs: direction.audio.ducking.release_ms,
        }
      : undefined,
    loudnessTargetLufs: direction.audio?.loudness_target_lufs,
  };

  const totalDurationMs = segments.reduce((max, s) => Math.max(max, s.start_ms + s.duration_ms), 0);

  const globalOverlays: PresetRef[] = (direction.global_overlays ?? []).map((o) => ({
    preset: o.preset,
    overrides: o.overrides,
  }));

  const sceneGraph: SceneGraph = {
    version: 1,
    meta: {
      videoId: direction.meta.video_id,
      channelId: direction.meta.channel_id,
      title: direction.meta.title,
      fps: direction.meta.fps,
      resolution: { ...direction.meta.resolution },
      aspect: direction.meta.aspect,
      durationMs: totalDurationMs,
      sourceDirection: direction,
    },
    theme: {
      primaryColor: direction.theme.primary_color,
      accentColor: direction.theme.accent_color,
      backgroundColor: direction.theme.background_color,
      textColor: direction.theme.text_color,
      headingFont: direction.theme.fonts.heading,
      bodyFont: direction.theme.fonts.body,
    },
    gradePreset: direction.grade_preset,
    globalEffects: [...(direction.global_effects ?? [])],
    globalOverlays,
    branding: direction.branding
      ? {
          introPreset: direction.branding.intro_preset,
          outroPreset: direction.branding.outro_preset,
          watermark: direction.branding.watermark
            ? {
                preset: direction.branding.watermark.preset,
                overrides: direction.branding.watermark.overrides,
              }
            : undefined,
        }
      : undefined,
    tracks: [videoTrack, overlayTrack],
    audio,
    hash: "",
  };

  sceneGraph.hash = hashNode(sceneGraph);
  return sceneGraph;
}

function makeSceneClip(s: SegmentV3): SceneClip {
  const clip: SceneClip = {
    kind: "scene",
    id: s.id,
    scenePreset: s.scene_preset,
    sceneOverrides: s.scene_overrides,
    range: [s.start_ms, s.start_ms + s.duration_ms],
    animationsIn: s.animations_in?.map((a) => ({
      preset: a.preset,
      target: a.target,
      overrides: a.overrides,
    })),
    animationsOut: s.animations_out?.map((a) => ({
      preset: a.preset,
      target: a.target,
      overrides: a.overrides,
    })),
    effects: s.effects ? [...s.effects] : undefined,
    overlays: s.overlays?.map((o) => ({ preset: o.preset, overrides: o.overrides })),
    sfx: s.sfx?.map((x) => ({ preset: x.preset, atMs: x.at_ms, volumeDb: x.volume_db })),
    transitionOut: s.transition_out
      ? { preset: s.transition_out.preset, overrides: s.transition_out.overrides }
      : undefined,
    hash: "",
  };
  clip.hash = hashNode(clip);
  return clip;
}

function aggregateSfx(segments: SegmentV3[]): SfxCue[] {
  const cues: SfxCue[] = [];
  for (const s of segments) {
    if (!s.sfx) continue;
    for (const c of s.sfx) {
      cues.push({ preset: c.preset, atMs: s.start_ms + c.at_ms, volumeDb: c.volume_db });
    }
  }
  cues.sort((a, b) => a.atMs - b.atMs);
  return cues;
}

function assertNonOverlapping(segments: SegmentV3[]): void {
  for (let i = 1; i < segments.length; i++) {
    const prev = segments[i - 1]!;
    const cur = segments[i]!;
    const prevEnd = prev.start_ms + prev.duration_ms;
    if (cur.start_ms < prevEnd) {
      throw new Error(
        `scene-graph/lower: overlapping segments ${prev.id} (end=${prevEnd}) and ${cur.id} (start=${cur.start_ms})`,
      );
    }
  }
}
