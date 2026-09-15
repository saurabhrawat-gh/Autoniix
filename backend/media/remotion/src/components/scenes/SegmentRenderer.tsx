import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { resolvePreset, resolveSfx } from "../../registry";
import { DiagnosticScene } from "./DiagnosticScene";
import { EffectErrorBoundary } from "../effects/EffectErrorBoundary";
import { SFXTrigger } from "../audio/SFXTrigger";
import { msToFrames } from "../../utils/timing";
import type { SegmentV3 } from "../../schemas/directionV3";

export interface SegmentRendererProps {
  segment: SegmentV3;
}

/**
 * Renders a single segment:
 *   1. Resolves scene_preset and mounts the scene component (with merged props).
 *   2. Wraps the scene in animations_in / animations_out (nested) if present.
 *   3. Stacks per-segment effects + overlays on top.
 */
export const SegmentRenderer: React.FC<SegmentRendererProps> = ({ segment }) => {
  const { fps } = useVideoConfig();
  const sceneResolved = resolvePreset(segment.scene_preset, segment.scene_overrides ?? {});

  let sceneEl: React.ReactNode;
  if (!sceneResolved) {
    sceneEl = (
      <DiagnosticScene
        reason="unresolved scene_preset"
        presetId={segment.scene_preset}
        segmentId={segment.id}
      />
    );
  } else {
    const { Component, props } = sceneResolved;
    sceneEl = <Component {...props} />;
  }

  if (segment.animations_in && segment.animations_in.length > 0) {
    for (const anim of segment.animations_in) {
      const aRes = resolvePreset(anim.preset, anim.overrides ?? {});
      if (!aRes) continue;
      const { Component: AnimComp, props: animProps } = aRes;
      sceneEl = <AnimComp {...animProps}>{sceneEl}</AnimComp>;
    }
  }

  if (segment.animations_out && segment.animations_out.length > 0) {
    for (const anim of segment.animations_out) {
      const aRes = resolvePreset(anim.preset, anim.overrides ?? {});
      if (!aRes) continue;
      const { Component: AnimComp, props: animProps } = aRes;
      sceneEl = <AnimComp {...animProps}>{sceneEl}</AnimComp>;
    }
  }

  const WRAPPING_PREFIXES = ["fx.lut."];
  const wrappingEffects: Array<{
    Component: React.ComponentType<any>;
    props: Record<string, any>;
  }> = [];
  const overlayEffects: React.ReactNode[] = [];

  for (const [i, id] of (segment.effects ?? []).entries()) {
    const r = resolvePreset(id);
    if (!r) continue;
    const { Component, props } = r;
    if (WRAPPING_PREFIXES.some((p) => id.startsWith(p))) {
      wrappingEffects.push({ Component, props });
    } else {
      overlayEffects.push(
        <EffectErrorBoundary key={`fx-${i}`}>
          <Component {...props} />
        </EffectErrorBoundary>,
      );
    }
  }

  for (const { Component: WrapComp, props: wrapProps } of wrappingEffects) {
    sceneEl = (
      <EffectErrorBoundary fallback={sceneEl}>
        <WrapComp {...wrapProps}>{sceneEl}</WrapComp>
      </EffectErrorBoundary>
    );
  }

  const overlayEls = (segment.overlays ?? []).map((ov, i) => {
    const r = resolvePreset(ov.preset, ov.overrides ?? {});
    if (!r) return null;
    const { Component, props } = r;
    return (
      <EffectErrorBoundary key={`ov-${i}`}>
        <Component {...props} />
      </EffectErrorBoundary>
    );
  });

  const sfxEls = (segment.sfx ?? []).map((cue, i) => {
    const isUrl = /^https?:\/\//.test(cue.preset);
    let src: string | null = null;
    let defaultDb = 0;
    if (isUrl) {
      src = cue.preset;
    } else {
      const res = resolveSfx(cue.preset);
      if (res) {
        src = res.resolvedUrl;
        defaultDb = res.defaultDb ?? 0;
      }
    }
    if (!src) return null;
    return (
      <SFXTrigger
        key={`sfx-${i}`}
        src={src}
        triggerAtFrame={msToFrames(cue.at_ms, fps)}
        volumeDb={cue.volume_db ?? defaultDb}
      />
    );
  });

  return (
    <AbsoluteFill>
      {sceneEl}
      {overlayEffects}
      {overlayEls}
      {sfxEls}
    </AbsoluteFill>
  );
};
