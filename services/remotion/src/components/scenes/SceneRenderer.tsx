import React from "react";
import { resolvePreset } from "../../registry";
import { PlaceholderScene } from "./PlaceholderScene";
import type { SegmentV3 } from "../../schemas/directionV3";

export interface SceneRendererProps {
  segment: SegmentV3;
}

/**
 * Resolves `segment.scene_preset` against the registry and renders the
 * corresponding component with merged props. Falls back to PlaceholderScene
 * when the preset ID is unknown (never blocks a render).
 */
export const SceneRenderer: React.FC<SceneRendererProps> = ({ segment }) => {
  const resolved = resolvePreset(segment.scene_preset, segment.scene_overrides ?? {});

  if (!resolved) {
    return <PlaceholderScene label={`unknown: ${segment.scene_preset}`} bg="#200" fg="#f55" />;
  }

  const { Component, props } = resolved;
  return <Component {...props} />;
};
