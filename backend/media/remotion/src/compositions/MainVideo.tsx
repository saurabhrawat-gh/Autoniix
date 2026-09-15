import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { TransitionSeries } from "@remotion/transitions";
import { z } from "zod";
import { DirectionV3 } from "../schemas/directionV3";
import { SegmentRenderer } from "../components/scenes/SegmentRenderer";
import { resolvePreset, resolveTransition } from "../registry";
import { AudioMixer } from "../components/audio/AudioMixer";
import { EffectErrorBoundary } from "../components/effects/EffectErrorBoundary";
import { msToFrames } from "../utils/timing";

export const mainVideoSchema = z.object({
  direction: DirectionV3,
});

export type MainVideoProps = z.infer<typeof mainVideoSchema>;

export const mainVideoDefaults: MainVideoProps = {
  direction: {
    version: "3.0",
    meta: {
      video_id: "preview",
      channel_id: "preview",
      title: "Preview",
      duration_target_seconds: 5,
      aspect: "16:9",
      fps: 30,
      resolution: { width: 1920, height: 1080 },
    },
    template: "hybrid-kinetic",
    theme: {
      primary_color: "#FF3B30",
      accent_color: "#FFD60A",
      background_color: "#0A0A0A",
      text_color: "#FFFFFF",
      fonts: { heading: "Inter", body: "Inter" },
    },
    grade_preset: "fx.grade.cinematic_teal_orange",
    segments: [
      {
        id: "s1",
        start_ms: 0,
        duration_ms: 5000,
        scene_preset: "scene.placeholder",
        scene_overrides: { label: "Preview", bg: "#0A0A0A", fg: "#FFFFFF" },
      },
    ],
  },
};

export const MainVideo: React.FC<MainVideoProps> = ({ direction }) => {
  const { fps } = useVideoConfig();

  const gradeResolved = resolvePreset(direction.grade_preset);
  const GradeComp = gradeResolved?.Component;
  const gradeProps = gradeResolved?.props ?? {};

  const globalEffectEls = (direction.global_effects ?? [])
    .filter((id) => id !== direction.grade_preset)
    .map((id, i) => {
      const r = resolvePreset(id);
      if (!r) return null;
      const { Component, props } = r;
      return (
        <EffectErrorBoundary key={`gfx-${i}`}>
          <Component {...props} />
        </EffectErrorBoundary>
      );
    });

  const globalOverlayEls = (direction.global_overlays ?? []).map((ov, i) => {
    const r = resolvePreset(ov.preset, ov.overrides ?? {});
    if (!r) return null;
    const { Component, props } = r;
    const merged: Record<string, unknown> = { ...props };
    if (ov.preset.startsWith("ov.caption.") && !merged.srtUrl && !merged.srt) {
      if (direction.audio?.voiceover_srt_url) {
        merged.srtUrl = direction.audio.voiceover_srt_url;
      }
    }
    return (
      <EffectErrorBoundary key={`gov-${i}`}>
        <Component {...merged} />
      </EffectErrorBoundary>
    );
  });

  const seriesChildren: React.ReactNode[] = [];
  direction.segments.forEach((seg, idx) => {
    seriesChildren.push(
      <TransitionSeries.Sequence
        key={`seq-${seg.id}`}
        durationInFrames={msToFrames(seg.duration_ms, fps)}
      >
        <SegmentRenderer segment={seg} />
      </TransitionSeries.Sequence>,
    );

    const isLast = idx === direction.segments.length - 1;
    if (!isLast && seg.transition_out) {
      const t = resolveTransition(seg.transition_out.preset);
      if (t) {
        const { presentation, timing } = t.build(seg.transition_out.overrides ?? {});
        seriesChildren.push(
          <TransitionSeries.Transition
            key={`trans-${seg.id}`}
            presentation={presentation}
            timing={timing}
          />,
        );
      }
    }
  });

  const body = <TransitionSeries>{seriesChildren}</TransitionSeries>;

  return (
    <AbsoluteFill style={{ backgroundColor: direction.theme.background_color }}>
      {GradeComp ? (
        <EffectErrorBoundary fallback={body}>
          <GradeComp {...gradeProps}>{body}</GradeComp>
        </EffectErrorBoundary>
      ) : (
        body
      )}

      {globalEffectEls}
      {globalOverlayEls}

      {direction.audio && (
        <AudioMixer
          voiceoverUrl={direction.audio.voiceover_url}
          voiceoverSrtUrl={direction.audio.voiceover_srt_url}
          musicUrl={direction.audio.music_url}
          musicVolumeDb={direction.audio.music_volume_db}
          ducking={
            direction.audio.ducking
              ? {
                  enabled: direction.audio.ducking.enabled,
                  duckingDb: -12,
                  fadeFrames: Math.round(
                    ((direction.audio.ducking.attack_ms + direction.audio.ducking.release_ms) /
                      2 /
                      1000) *
                      fps,
                  ),
                }
              : { enabled: true, duckingDb: -12, fadeFrames: 6 }
          }
        />
      )}
    </AbsoluteFill>
  );
};
