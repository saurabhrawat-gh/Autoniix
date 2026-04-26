import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { resolvePreset, resolveSfx } from "../../registry";
import { PlaceholderScene } from "./PlaceholderScene";
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
  const sceneResolved = resolvePreset(
    segment.scene_preset,
    segment.scene_overrides ?? {},
  );

  let sceneEl: React.ReactNode;
  if (!sceneResolved) {
    sceneEl = (
      <PlaceholderScene label={`unknown: ${segment.scene_preset}`} bg="#200" fg="#f55" />
    );
  } else {
    const { Component, props } = sceneResolved;
    sceneEl = <Component {...props} />;
  }

  // Wrap scene in animations_in (nested). Wrappers expect `children`.
  if (segment.animations_in && segment.animations_in.length > 0) {
    for (const anim of segment.animations_in) {
      const aRes = resolvePreset(anim.preset, anim.overrides ?? {});
      if (!aRes) continue;
      const { Component: AnimComp, props: animProps } = aRes;
      sceneEl = <AnimComp {...animProps}>{sceneEl}</AnimComp>;
    }
  }

  // Wrap scene in animations_out (exit animations, nested).
  if (segment.animations_out && segment.animations_out.length > 0) {
    for (const anim of segment.animations_out) {
      const aRes = resolvePreset(anim.preset, anim.overrides ?? {});
      if (!aRes) continue;
      const { Component: AnimComp, props: animProps } = aRes;
      sceneEl = <AnimComp {...animProps}>{sceneEl}</AnimComp>;
    }
  }

  // Per-segment effects: split into wrapping effects (e.g. LUTGrade, which
  // take children and apply CSS/SVG filters) vs. overlay effects (stacked on top).
  const WRAPPING_PREFIXES = ["fx.lut."];
  const wrappingEffects: Array<{ Component: React.ComponentType<any>; props: Record<string, any> }> = [];
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

  // Wrap scene in LUT/filter effects (innermost first)
  for (const { Component: WrapComp, props: wrapProps } of wrappingEffects) {
    sceneEl = (
      <EffectErrorBoundary fallback={sceneEl}>
        <WrapComp {...wrapProps}>{sceneEl}</WrapComp>
      </EffectErrorBoundary>
    );
  }

  // Per-segment overlays.
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

  // Per-segment SFX cues: `preset` is either an absolute URL or a library ID
  // (e.g. `sfx.whoosh.short`) resolved via the SFX catalog.
  const sfxEls = (segment.sfx ?? []).map((cue, i) => {
    const isUrl = /^https?:\/\//i.test(cue.preset);
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
