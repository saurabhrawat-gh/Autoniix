/**
 * SceneGraph public surface.
 *
 * Downstream code should import ONLY from `./scene-graph` — never from the
 * internal modules — so the internal shape can change without ripple.
 */

export type {
  SceneGraph,
  SceneGraphMeta,
  SceneGraphVersion,
  Theme,
  Clip,
  SceneClip,
  StockClip,
  CaptionClip,
  FxClip,
  TransitionClip,
  ComposeClip,
  Track,
  TrackKind,
  AudioGraph,
  AudioClipRef,
  DuckingConfig,
  SfxCue,
  PresetRef,
  AnimationRef,
  TransitionRef,
  Branding,
  Resolution,
  Hash,
  Ms,
  Patch,
  PatchOp,
  BlendMode,
  Compositing,
  ClipMaskRef,
  MaskBlendMode,
  ColorGradeTrackRef,
  ClipFilterRef,
} from "./types";

export { BLEND_MODES } from "./types";
export { lower } from "./lower";
export { canonicalize, hashNode, sha256Hex } from "./hash";
export { tagCapabilities } from "./capability";
export type { ClipCapability, ClipCapabilityTagged } from "./capability";
export { planShards, msToFrames } from "./sharder";
export type { Shard, ShardPlan, ShardOptions } from "./sharder";
export { applyPatch } from "./commit";

export {
  isBlendMode,
  validateCompositing,
  cssBlendMode,
  requiresShader,
  effectiveBlendMode,
  effectiveOpacity,
  compositingToCss,
} from "./compositing";

export { blendModeHash, textAnimHash, maskHash, colorGradeHash, clipCacheKeys } from "./cacheKeys";
export type { ClipCacheKeys } from "./cacheKeys";
