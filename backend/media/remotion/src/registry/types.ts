import type React from "react";

export type PresetCategory =
  | "scene"
  | "transition"
  | "animation"
  | "effect"
  | "overlay";

export interface PresetEntry<P extends Record<string, unknown> = Record<string, unknown>> {
  id: string;
  component: React.ComponentType<any>;
  defaultProps: P;
  category: PresetCategory;
  tags: string[];
  thumbnail?: string;
}

export type PresetRegistry = Record<string, PresetEntry>;
