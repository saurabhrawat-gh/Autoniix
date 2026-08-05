/**
 * SceneGraph IR — P0.1
 *
 * A typed, mutable, hashable representation of a video that all agents
 * read/write and all renderer tiers consume.
 *
 * Design notes:
 * - Every node carries a stable `hash` (sha256 of its canonicalized form).
 * - Agents produce PATCHES (shallow mutations). Hashes are recomputed on commit.
 * - The IR is independent of the upstream `DirectionV3` contract and can
 *   evolve on its own version axis (`SceneGraph.version`).
 * - `meta.sourceDirection` carries the original direction-v3 verbatim so the
 *   legacy Tier-1 render path remains a drop-in fallback during rollout.
 */

import type { DirectionV3Input } from "../schemas/directionV3";

export type Ms = number;
export type Hash = string;

export type SceneGraphVersion = 1;

export type Resolution = { width: number; height: number };

/**
 * Per-layer blend mode. Applied when compositing a clip onto the layers below.
 *
 * - The first 12 modes map directly to the CSS `mix-blend-mode` values
 *   supported by Chromium and are implemented as a CSS-only fast path.
 * - `add` and `subtract` have no native CSS equivalent and fall back to a WebGL
 *   shader composite at render time.
 *
 * Default (when omitted): "normal".
 */
export type BlendMode =
  | "normal"
  | "multiply"
  | "screen"
  | "overlay"
  | "soft_light"
  | "hard_light"
  | "color_dodge"
  | "color_burn"
  | "difference"
  | "exclusion"
  | "hue"
  | "saturation"
  | "color"
  | "luminosity"
  | "add"
  | "subtract";

export const BLEND_MODES: readonly BlendMode[] = [
  "normal",
  "multiply",
  "screen",
  "overlay",
  "soft_light",
  "hard_light",
  "color_dodge",
  "color_burn",
  "difference",
  "exclusion",
  "hue",
  "saturation",
  "color",
  "luminosity",
  "add",
  "subtract",
] as const;

/** Compositing parameters carried by every rangeable clip. Optional. */
export type Compositing = {
  /** CSS-style blend mode. Default "normal" when absent. */
  blendMode?: BlendMode;
  /** 0..1 layer opacity. Default 1.0 when absent. */
  opacity?: number;
};

/* -------------------------------------------------------------------- */
/* Phase 1C — Mask types (re-exported from registry/masks for IR use)   */
/* -------------------------------------------------------------------- */

/**
 * Phase 1C — Animated clip mask reference.
 *
 * Multiple masks per clip are supported via `blend`:
 *   • intersect — both masks must pass (default; AND)
 *   • add       — either mask passes (OR / union)
 *   • subtract  — the first passes, second cuts away (DIFFERENCE)
 *
 * The `track` shape is fully described in `registry/masks.ts`. We hold an
 * opaque structural type here to keep the IR file decoupled from the
 * registry implementation.
 */
export type MaskBlendMode = "intersect" | "add" | "subtract";

export interface ClipMaskRef {
  id: string;
  /** Raw `MaskTrack` from `registry/masks` — kept structural to avoid a circular import. */
  track: { keys: Array<{ tMs: number; shape: unknown; featherPx?: number; invert?: boolean }> };
  blend?: MaskBlendMode;
}

/* -------------------------------------------------------------------- */
/* Phase 2 — Source-side clip filter ref (IR-level structural type)     */
/* -------------------------------------------------------------------- */

/**
 * Source-side filter applied before rendering. The full discriminated-union
 * type lives in `registry/clipFilters.ts`; we hold a structural alias here
 * to avoid a circular import. Validation runs through
 * `registry/clipFilters.validateFilters` at commit time.
 */
export interface ClipFilterRef {
  kind: string;
  [k: string]: unknown;
}

/* -------------------------------------------------------------------- */
/* Phase 1D — Color grade track (IR-level structural type)              */
/* -------------------------------------------------------------------- */

/**
 * Color grade track held on a clip. The full type definition lives in
 * `registry/colorGrade.ts`; we hold a structural alias here to avoid a
 * circular import. Validation runs through `registry/colorGrade.validateColorGradeTrack`
 * at commit time.
 */
export interface ColorGradeTrackRef {
  keys: Array<{
    tMs: number;
    primary: Record<string, unknown>;
    secondaries?: Array<Record<string, unknown>>;
    lutId?: string;
    lutStrength?: number;
  }>;
}

export type Theme = {
  primaryColor: string;
  accentColor: string;
  backgroundColor: string;
  textColor: string;
  headingFont: string;
  bodyFont: string;
};

export type SceneGraphMeta = {
  videoId: string;
  channelId: string;
  title: string;
  fps: number;
  resolution: Resolution;
  aspect: "16:9" | "9:16" | "1:1";
  durationMs: Ms;
  /** Verbatim direction-v3, preserved for the legacy renderer path. */
  sourceDirection: DirectionV3Input;
};

export type PresetRef = {
  preset: string;
  overrides?: Record<string, unknown>;
};

export type AnimationRef = {
  preset: string;
  target?: string;
  overrides?: Record<string, unknown>;
};

export type SfxCue = {
  preset: string;
  atMs: number;
  volumeDb?: number;
};

export type TransitionRef = {
  preset: string;
  overrides?: Record<string, unknown>;
};

/** A single timed clip on a track. */
export type SceneClip = {
  kind: "scene";
  id: string;
  scenePreset: string;
  sceneOverrides?: Record<string, unknown>;
  range: [Ms, Ms];
  animationsIn?: AnimationRef[];
  animationsOut?: AnimationRef[];
  effects?: string[];
  overlays?: PresetRef[];
  sfx?: SfxCue[];
  transitionOut?: TransitionRef;
  /** Phase 1A: per-layer compositing (blend mode + opacity). Optional. */
  compositing?: Compositing;
  /** Phase 1C: animated clip masks. Optional. */
  masks?: ClipMaskRef[];
  /** Phase 1D: per-shot color grade track. Optional. */
  colorGradeTrack?: ColorGradeTrackRef;
  /** Phase 2: source-side filter chain (deinterlace, stabilize, warp, ...). */
  filters?: ClipFilterRef[];
  hash: Hash;
};

/** Declared here for forward compatibility. Not emitted by the v1 lowerer. */
export type StockClip = {
  kind: "stock";
  id: string;
  assetSha256: string;
  assetUrl: string;
  transform: { fit: "cover" | "contain"; zoom?: number; panFrom?: [number, number]; panTo?: [number, number] };
  range: [Ms, Ms];
  /** Phase 1A: per-layer compositing (blend mode + opacity). Optional. */
  compositing?: Compositing;
  /** Phase 1C: animated clip masks. Optional. */
  masks?: ClipMaskRef[];
  /** Phase 1D: per-shot color grade track. Optional. */
  colorGradeTrack?: ColorGradeTrackRef;
  /** Phase 2: source-side filter chain (deinterlace, stabilize, warp, ...). */
  filters?: ClipFilterRef[];
  hash: Hash;
};

export type CaptionClip = {
  kind: "caption";
  id: string;
  text: string;
  wordTimings?: { word: string; startMs: Ms; endMs: Ms }[];
  style: string;
  range: [Ms, Ms];
  /** Phase 1A: per-layer compositing (blend mode + opacity). Optional. */
  compositing?: Compositing;
  /** Phase 1C: animated clip masks. Optional. */
  masks?: ClipMaskRef[];
  hash: Hash;
};

export type FxClip = {
  kind: "fx";
  id: string;
  effect: string;
  params?: Record<string, unknown>;
  targetClipId: string;
  range: [Ms, Ms];
  /** Phase 1A: per-layer compositing (blend mode + opacity). Optional. */
  compositing?: Compositing;
  /** Phase 1C: animated clip masks. Optional. */
  masks?: ClipMaskRef[];
  hash: Hash;
};

export type TransitionClip = {
  kind: "transition";
  id: string;
  transitionPreset: string;
  fromClipId: string;
  toClipId: string;
  durationMs: Ms;
  hash: Hash;
};

/** Nested composition — a SceneGraph embedded as a clip. P1+ usage. */
export type ComposeClip = {
  kind: "compose";
  id: string;
  graph: SceneGraph;
  range: [Ms, Ms];
  /** Phase 1A: per-layer compositing (blend mode + opacity). Optional. */
  compositing?: Compositing;
  /** Phase 1C: animated clip masks. Optional. */
  masks?: ClipMaskRef[];
  hash: Hash;
};

export type Clip =
  | SceneClip
  | StockClip
  | CaptionClip
  | FxClip
  | TransitionClip
  | ComposeClip;

export type TrackKind = "video" | "overlay" | "caption" | "fx";

export type Track = {
  id: string;
  kind: TrackKind;
  clips: Clip[];
};

export type AudioClipRef = {
  url?: string;
  srtUrl?: string;
  volumeDb?: number;
};

export type DuckingConfig = {
  enabled: boolean;
  thresholdDb: number;
  attackMs: number;
  releaseMs: number;
};

export type AudioGraph = {
  voiceover?: AudioClipRef;
  music?: AudioClipRef;
  sfx: SfxCue[];
  ducking?: DuckingConfig;
  loudnessTargetLufs?: number;
};

export type Branding = {
  introPreset?: string;
  outroPreset?: string;
  watermark?: PresetRef;
};

export type SceneGraph = {
  version: SceneGraphVersion;
  meta: SceneGraphMeta;
  theme: Theme;
  gradePreset: string;
  globalEffects: string[];
  globalOverlays: PresetRef[];
  branding?: Branding;
  tracks: Track[];
  audio: AudioGraph;
  /** Root hash — changes iff any descendant hash changes. */
  hash: Hash;
};

/**
 * Patch = JSON-Merge-ish shallow replacement ops an agent can emit.
 * All agents mutate the graph through Patch ops only; the commit layer
 * recomputes hashes and validates structural invariants.
 */
export type PatchOp =
  | { op: "replaceClip"; trackId: string; clipId: string; clip: Clip }
  | { op: "insertClip"; trackId: string; atIndex: number; clip: Clip }
  | { op: "removeClip"; trackId: string; clipId: string }
  | { op: "setTheme"; theme: Partial<Theme> }
  | { op: "setGradePreset"; preset: string }
  | { op: "setAudio"; audio: Partial<AudioGraph> }
  | { op: "setClipProps"; trackId: string; clipId: string; props: Record<string, unknown> }
  | { op: "setClipCompositing"; trackId: string; clipId: string; compositing: Compositing }
  | { op: "setClipMasks"; trackId: string; clipId: string; masks: ClipMaskRef[] }
  | { op: "setClipColorGrade"; trackId: string; clipId: string; colorGradeTrack: ColorGradeTrackRef }
  | { op: "setClipFilters"; trackId: string; clipId: string; filters: ClipFilterRef[] };

export type Patch = {
  agent: string;
  agentVersion: string;
  ops: PatchOp[];
  /** Optional reason/log line for observability. */
  reason?: string;
};
