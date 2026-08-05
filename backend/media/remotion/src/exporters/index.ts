/**
 * Phase 4 — Export system.
 *
 * Three translators that take a SceneGraph and produce industry-standard
 * editorial interchange artefacts:
 *
 *   • exportFcpxml      → Final Cut Pro XML 1.11 (string)
 *   • exportOtio        → OpenTimelineIO 0.17 JSON (string)
 *   • planAlphaStems    → Manifest of transparent stem render jobs
 *
 * All three are pure data transforms — no I/O, no rendering. Caller writes
 * the strings to disk / S3 and feeds the alpha-stem manifest into the
 * Remotion render queue.
 */

export { exportFcpxml } from "./fcpxml";
export type { FcpxmlExportOptions } from "./fcpxml";

export { exportOtio, buildOtioTimeline } from "./otio";
export type { OtioExportOptions } from "./otio";

export {
  planAlphaStems,
  PRORES_4444,
  VP9_ALPHA,
} from "./alphaStems";
export type {
  AlphaOutputFormat,
  AlphaStemsPlan,
  AlphaStemsPlanOptions,
  StemKind,
  StemRender,
} from "./alphaStems";
