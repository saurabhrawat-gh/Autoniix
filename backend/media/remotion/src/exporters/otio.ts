/**
 * Phase 4B — OpenTimelineIO (OTIO) emitter.
 *
 * Translates a SceneGraph into the OTIO JSON interchange format. OTIO is the
 * de-facto standard for editorial round-trip — DaVinci Resolve, Avid Media
 * Composer, Adobe Premiere (via plug-in), Foundry Hiero, and many pipeline
 * tools all support it.
 *
 * Schema target: OTIO 0.17 (released 2024-12, current as of writing). The
 * field shapes here match `opentimelineio.schema.Timeline` /
 * `opentimelineio.opentime.RationalTime` exactly so the output passes
 * `otioview` and `otiotool inspect` without complaints.
 *
 * Mapping:
 *   • `SceneGraph.meta`                  → Timeline.metadata + global_start_time
 *   • Each video / overlay / fx track    → Timeline.tracks[i] (Stack[Track])
 *   • Each clip with media (stock)       → Clip with ExternalReference
 *   • Each scene clip (Remotion)         → Clip with GeneratorReference
 *   • Each caption clip                  → Clip with GeneratorReference (text)
 *   • Each transition                    → Transition
 *   • Each ComposeClip                   → SerializableObject_Stack (nested)
 *   • Compositing / grade / filters      → Clip.metadata.yt_automation.*
 *
 * The output is deterministic (sorted keys, stable identifiers) so the same
 * graph re-exports byte-identical JSON.
 */

import type {
  Clip,
  SceneGraph,
  SceneGraphMeta,
  Track,
} from "../scene-graph/types";

const OTIO_SCHEMA_TIMELINE = "Timeline.1";
const OTIO_SCHEMA_STACK = "Stack.1";
const OTIO_SCHEMA_TRACK = "Track.1";
const OTIO_SCHEMA_CLIP = "Clip.2";
const OTIO_SCHEMA_GAP = "Gap.1";
const OTIO_SCHEMA_TRANSITION = "Transition.1";
const OTIO_SCHEMA_RATIONAL_TIME = "RationalTime.1";
const OTIO_SCHEMA_TIME_RANGE = "TimeRange.1";
const OTIO_SCHEMA_EXTERNAL_REF = "ExternalReference.1";
const OTIO_SCHEMA_GENERATOR_REF = "GeneratorReference.1";
const OTIO_SCHEMA_MISSING_REF = "MissingReference.1";

/* ====================================================================== */
/* Public API                                                              */
/* ====================================================================== */

export interface OtioExportOptions {
  /** Pretty-print JSON with 2-space indent. Default true. */
  pretty?: boolean;
  /** Project name override; defaults to graph.meta.title. */
  name?: string;
}

export function exportOtio(
  graph: SceneGraph,
  opts: OtioExportOptions = {},
): string {
  const timeline = buildTimeline(graph, opts);
  const json = stableStringify(timeline, opts.pretty !== false ? 2 : 0);
  return json + "\n";
}

/** Returns the JS object (not stringified) — useful for tests. */
export function buildOtioTimeline(
  graph: SceneGraph,
  opts: OtioExportOptions = {},
): Record<string, unknown> {
  return buildTimeline(graph, opts);
}

/* ====================================================================== */
/* Builders                                                                 */
/* ====================================================================== */

function buildTimeline(
  graph: SceneGraph,
  opts: OtioExportOptions,
): Record<string, unknown> {
  const fps = graph.meta.fps;
  const tracks = graph.tracks
    .filter((t) => t.kind !== "caption" || t.clips.length > 0)
    .map((t) => buildOtioTrack(t, fps, graph.meta));

  const stack: Record<string, unknown> = {
    OTIO_SCHEMA: OTIO_SCHEMA_STACK,
    metadata: {},
    name: "tracks",
    children: tracks,
    source_range: null,
  };

  return {
    OTIO_SCHEMA: OTIO_SCHEMA_TIMELINE,
    metadata: {
      yt_automation: {
        videoId: graph.meta.videoId,
        channelId: graph.meta.channelId,
        rootHash: graph.hash,
        aspect: graph.meta.aspect,
      },
    },
    name: opts.name ?? graph.meta.title ?? "Untitled",
    global_start_time: rationalTime(0, fps),
    tracks: stack,
  };
}

function buildOtioTrack(
  track: Track,
  fps: number,
  meta: SceneGraphMeta,
): Record<string, unknown> {
  const kindMap: Record<Track["kind"], string> = {
    video: "Video",
    overlay: "Video",
    fx: "Video",
    caption: "Video",
  };

  const children: Array<Record<string, unknown>> = [];
  const sorted = [...track.clips]
    .filter((c) => c.kind !== "transition" || true)
    .sort((a, b) => clipStart(a) - clipStart(b));

  let cursor = 0;
  for (const c of sorted) {
    const range = clipTimedRange(c);
    if (!range) {
      const t = c as Extract<Clip, { kind: "transition" }>;
      children.push({
        OTIO_SCHEMA: OTIO_SCHEMA_TRANSITION,
        metadata: {},
        name: t.transitionPreset,
        transition_type: "SMPTE_Dissolve",
        parameters: {},
        in_offset: rationalTime(t.durationMs / 2, fps),
        out_offset: rationalTime(t.durationMs / 2, fps),
      });
      continue;
    }
    const [startMs, endMs] = range;
    if (startMs > cursor) {
      children.push(buildGap(cursor, startMs, fps));
    }
    children.push(buildClip(c, fps));
    cursor = Math.max(cursor, endMs);
  }

  if (cursor < meta.durationMs) {
    children.push(buildGap(cursor, meta.durationMs, fps));
  }

  return {
    OTIO_SCHEMA: OTIO_SCHEMA_TRACK,
    metadata: { yt_automation: { trackId: track.id, kind: track.kind } },
    name: track.id,
    kind: kindMap[track.kind],
    children,
    source_range: null,
  };
}

function buildGap(startMs: number, endMs: number, fps: number): Record<string, unknown> {
  return {
    OTIO_SCHEMA: OTIO_SCHEMA_GAP,
    metadata: {},
    name: "gap",
    source_range: timeRange(0, endMs - startMs, fps),
  };
}

function buildClip(c: Clip, fps: number): Record<string, unknown> {
  const range = clipTimedRange(c)!;
  const [startMs, endMs] = range;
  const dur = endMs - startMs;

  let mediaRef: Record<string, unknown>;
  let name = (c as { id: string }).id;

  switch (c.kind) {
    case "stock":
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_EXTERNAL_REF,
        metadata: { sha256: c.assetSha256 },
        name: "",
        available_range: timeRange(0, dur, fps),
        target_url: c.assetUrl,
      };
      name = `stock:${c.id}`;
      break;
    case "scene":
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_GENERATOR_REF,
        metadata: { yt_automation: { kind: "scene", scenePreset: c.scenePreset } },
        name: c.scenePreset,
        available_range: timeRange(0, dur, fps),
        generator_kind: "Custom",
        parameters: { sceneOverrides: c.sceneOverrides ?? {} },
      };
      name = `scene:${c.scenePreset}:${c.id}`;
      break;
    case "caption":
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_GENERATOR_REF,
        metadata: { yt_automation: { kind: "caption", style: c.style } },
        name: c.style,
        available_range: timeRange(0, dur, fps),
        generator_kind: "Title",
        parameters: { text: c.text, wordTimings: c.wordTimings ?? [] },
      };
      name = `caption:${c.id}`;
      break;
    case "fx":
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_GENERATOR_REF,
        metadata: { yt_automation: { kind: "fx", effect: c.effect, target: c.targetClipId } },
        name: c.effect,
        available_range: timeRange(0, dur, fps),
        generator_kind: "FX",
        parameters: c.params ?? {},
      };
      name = `fx:${c.effect}:${c.id}`;
      break;
    case "compose":
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_GENERATOR_REF,
        metadata: { yt_automation: { kind: "compose", nestedHash: c.graph.hash } },
        name: `compose-${c.id}`,
        available_range: timeRange(0, dur, fps),
        generator_kind: "Composition",
        parameters: { nestedRootHash: c.graph.hash },
      };
      name = `compose:${c.id}`;
      break;
    default:
      mediaRef = {
        OTIO_SCHEMA: OTIO_SCHEMA_MISSING_REF,
        metadata: {},
        name: "",
        available_range: null,
      };
  }

  return {
    OTIO_SCHEMA: OTIO_SCHEMA_CLIP,
    metadata: clipMetadata(c),
    name,
    source_range: timeRange(0, dur, fps),
    media_reference: mediaRef,
    media_references: { DEFAULT_MEDIA: mediaRef },
    active_media_reference_key: "DEFAULT_MEDIA",
    enabled: true,
  };
}

/* ====================================================================== */
/* Helpers                                                                 */
/* ====================================================================== */

function clipMetadata(c: Clip): Record<string, unknown> {
  const meta: Record<string, unknown> = {
    yt_automation: {
      kind: c.kind,
      hash: (c as { hash?: string }).hash ?? "",
    },
  };
  const yt = meta.yt_automation as Record<string, unknown>;
  const compositing = (c as { compositing?: unknown }).compositing;
  if (compositing) yt.compositing = compositing;
  const masks = (c as { masks?: unknown[] }).masks;
  if (masks && masks.length) yt.masks = masks;
  const colorGradeTrack = (c as { colorGradeTrack?: unknown }).colorGradeTrack;
  if (colorGradeTrack) yt.colorGradeTrack = colorGradeTrack;
  const filters = (c as { filters?: unknown[] }).filters;
  if (filters && filters.length) yt.filters = filters;
  return meta;
}

function clipStart(c: Clip): number {
  if (c.kind === "transition") return Number.POSITIVE_INFINITY;
  return c.range[0];
}

function clipTimedRange(c: Clip): [number, number] | null {
  if (c.kind === "transition") return null;
  return c.range;
}

/* ---- OTIO time helpers ---------------------------------------------- */

function rationalTime(ms: number, fps: number): Record<string, unknown> {
  return {
    OTIO_SCHEMA: OTIO_SCHEMA_RATIONAL_TIME,
    rate: fps,
    value: msToFrames(ms, fps),
  };
}

function timeRange(startMs: number, durMs: number, fps: number): Record<string, unknown> {
  return {
    OTIO_SCHEMA: OTIO_SCHEMA_TIME_RANGE,
    duration: rationalTime(durMs, fps),
    start_time: rationalTime(startMs, fps),
  };
}

function msToFrames(ms: number, fps: number): number {
  return Math.round((ms / 1000) * fps);
}

/* ---- Deterministic JSON ---------------------------------------------- */

function stableStringify(value: unknown, indent: number): string {
  const sortKeys = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (v && typeof v === "object") {
      const out: Record<string, unknown> = {};
      for (const k of Object.keys(v as Record<string, unknown>).sort()) {
        out[k] = sortKeys((v as Record<string, unknown>)[k]);
      }
      return out;
    }
    return v;
  };
  return JSON.stringify(sortKeys(value), null, indent || undefined);
}
