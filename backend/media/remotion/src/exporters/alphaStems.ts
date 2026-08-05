/**
 * Phase 4C — Alpha-stem manifest planner.
 *
 * Walks a SceneGraph and returns a manifest of "stems" — isolated layers
 * that should be rendered with a transparent background as separate video
 * files (ProRes 4444 / VP9 / WebM-alpha) for downstream NLE compositing.
 *
 * Why stems matter:
 *   • Editors who import an FCPXML / OTIO often want to re-composite the
 *     captions, lower thirds, or overlay assets on top of their own footage
 *     instead of accepting the rendered MP4 verbatim.
 *   • Each stem is one connected layer (a single track or a single overlay
 *     clip group) plus the time range it occupies, plus a render directive
 *     that tells the Remotion render queue which composition to invoke and
 *     with what props.
 *
 * Output is data-only — no rendering happens here. The manifest feeds the
 * existing Remotion render service. Plan-only design lets the orchestrator
 * decide on caching, parallelism, and which stems to skip.
 */

import { createHash } from "node:crypto";
import type {
  Clip,
  SceneGraph,
  Track,
} from "../scene-graph/types";

/* ====================================================================== */
/* Public types                                                            */
/* ====================================================================== */

export type StemKind = "captions" | "overlays" | "fx" | "title-cards";

export interface StemRender {
  /** Stable id derived from (kind, trackId, clipIds, hash). */
  id: string;
  kind: StemKind;
  /** Source track id; absent for stems aggregated across tracks. */
  trackId?: string;
  /** Clip ids included in this stem. */
  clipIds: string[];
  /** Inclusive start, exclusive end, in ms (relative to project start). */
  rangeMs: [number, number];
  /** Suggested output format. */
  outputFormat: AlphaOutputFormat;
  /** Fully-qualified Remotion composition identifier. */
  composition: string;
  /** Props to pass to the composition (filter chain, scene IR, etc.). */
  inputProps: Record<string, unknown>;
  /**
   * Filename hint (no extension). Includes a content hash so re-renders are
   * idempotent and old stems aren't accidentally overwritten.
   */
  fileBasename: string;
}

export interface AlphaOutputFormat {
  /** Container. */
  container: "mov" | "webm";
  /** Codec — must support an alpha channel. */
  codec: "prores4444" | "vp9-alpha";
  /** Pixel format (e.g. yuva420p, yuva444p10le). */
  pixelFormat: string;
  /** ffmpeg `-c:v` argument for the chosen codec. */
  ffmpegCodec: string;
  /** Optional CRF / profile flags. */
  ffmpegFlags: string[];
}

export const PRORES_4444: AlphaOutputFormat = {
  container: "mov",
  codec: "prores4444",
  pixelFormat: "yuva444p10le",
  ffmpegCodec: "prores_ks",
  ffmpegFlags: ["-profile:v", "4444", "-pix_fmt", "yuva444p10le"],
};

export const VP9_ALPHA: AlphaOutputFormat = {
  container: "webm",
  codec: "vp9-alpha",
  pixelFormat: "yuva420p",
  ffmpegCodec: "libvpx-vp9",
  ffmpegFlags: ["-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-row-mt", "1"],
};

export interface AlphaStemsPlanOptions {
  /** Default output format for every stem. Default ProRes 4444. */
  defaultFormat?: AlphaOutputFormat;
  /** Render compositions registered in the Remotion service. Customize per
   *  project; defaults are sensible names for the standard pipeline. */
  compositions?: Partial<Record<StemKind, string>>;
  /**
   * If true, group adjacent overlays into a single stem when they share a
   * track. Off by default — most editors want one stem per logical asset.
   */
  groupAdjacentOverlays?: boolean;
}

export interface AlphaStemsPlan {
  stems: StemRender[];
  /** Stems that were skipped + the reason (e.g. "no clips"). */
  skipped: { kind: StemKind; trackId: string; reason: string }[];
}

/* ====================================================================== */
/* Public API                                                              */
/* ====================================================================== */

const DEFAULT_COMPOSITIONS: Record<StemKind, string> = {
  captions: "stem-captions",
  overlays: "stem-overlays",
  fx: "stem-fx",
  "title-cards": "stem-title-cards",
};

export function planAlphaStems(
  graph: SceneGraph,
  opts: AlphaStemsPlanOptions = {},
): AlphaStemsPlan {
  const fmt = opts.defaultFormat ?? PRORES_4444;
  const compositions = { ...DEFAULT_COMPOSITIONS, ...(opts.compositions ?? {}) };
  const stems: StemRender[] = [];
  const skipped: AlphaStemsPlan["skipped"] = [];

  for (const t of graph.tracks) {
    if (t.kind === "video") continue;
    if (t.kind === "caption") {
      collectCaptionStems(t, graph, fmt, compositions.captions, stems, skipped);
      continue;
    }
    if (t.kind === "overlay") {
      collectOverlayStems(
        t,
        graph,
        fmt,
        compositions.overlays,
        stems,
        skipped,
        opts.groupAdjacentOverlays === true,
      );
      continue;
    }
    if (t.kind === "fx") {
      collectFxStems(t, graph, fmt, compositions.fx, stems, skipped);
      continue;
    }
  }

  collectTitleCardStems(graph, fmt, compositions["title-cards"], stems);

  stems.sort((a, b) => a.rangeMs[0] - b.rangeMs[0] || a.id.localeCompare(b.id));

  return { stems, skipped };
}

/* ====================================================================== */
/* Per-kind collectors                                                    */
/* ====================================================================== */

function collectCaptionStems(
  t: Track,
  graph: SceneGraph,
  fmt: AlphaOutputFormat,
  composition: string,
  out: StemRender[],
  skipped: AlphaStemsPlan["skipped"],
): void {
  const clips = t.clips.filter((c): c is Extract<Clip, { kind: "caption" }> => c.kind === "caption");
  if (clips.length === 0) {
    skipped.push({ kind: "captions", trackId: t.id, reason: "no caption clips" });
    return;
  }
  const start = Math.min(...clips.map((c) => c.range[0]));
  const end = Math.max(...clips.map((c) => c.range[1]));
  const id = stemId("captions", [t.id], clips.map((c) => c.hash));
  out.push({
    id,
    kind: "captions",
    trackId: t.id,
    clipIds: clips.map((c) => c.id),
    rangeMs: [start, end],
    outputFormat: fmt,
    composition,
    inputProps: {
      trackId: t.id,
      clips: clips.map((c) => ({
        id: c.id,
        text: c.text,
        style: c.style,
        range: c.range,
        wordTimings: c.wordTimings ?? [],
      })),
      meta: graph.meta,
    },
    fileBasename: `stem-captions-${id}`,
  });
}

function collectOverlayStems(
  t: Track,
  graph: SceneGraph,
  fmt: AlphaOutputFormat,
  composition: string,
  out: StemRender[],
  skipped: AlphaStemsPlan["skipped"],
  groupAdjacent: boolean,
): void {
  const clips = t.clips.filter((c) => c.kind !== "transition");
  if (clips.length === 0) {
    skipped.push({ kind: "overlays", trackId: t.id, reason: "no overlay clips" });
    return;
  }

  if (groupAdjacent) {
    const start = Math.min(...clips.map((c) => clipStart(c)!));
    const end = Math.max(...clips.map((c) => clipEnd(c)!));
    const id = stemId("overlays", [t.id], clips.map((c) => clipHash(c)));
    out.push({
      id,
      kind: "overlays",
      trackId: t.id,
      clipIds: clips.map((c) => c.id),
      rangeMs: [start, end],
      outputFormat: fmt,
      composition,
      inputProps: { trackId: t.id, clipsHashes: clips.map((c) => clipHash(c)), meta: graph.meta },
      fileBasename: `stem-overlays-${id}`,
    });
    return;
  }

  for (const c of clips) {
    const start = clipStart(c)!;
    const end = clipEnd(c)!;
    const id = stemId("overlays", [t.id, c.id], [clipHash(c)]);
    out.push({
      id,
      kind: "overlays",
      trackId: t.id,
      clipIds: [c.id],
      rangeMs: [start, end],
      outputFormat: fmt,
      composition,
      inputProps: { trackId: t.id, clipId: c.id, clipHash: clipHash(c), meta: graph.meta },
      fileBasename: `stem-overlay-${c.id}-${id.slice(0, 8)}`,
    });
  }
}

function collectFxStems(
  t: Track,
  graph: SceneGraph,
  fmt: AlphaOutputFormat,
  composition: string,
  out: StemRender[],
  skipped: AlphaStemsPlan["skipped"],
): void {
  const clips = t.clips.filter((c): c is Extract<Clip, { kind: "fx" }> => c.kind === "fx");
  if (clips.length === 0) {
    skipped.push({ kind: "fx", trackId: t.id, reason: "no fx clips" });
    return;
  }
  for (const c of clips) {
    const id = stemId("fx", [t.id, c.id], [c.hash]);
    out.push({
      id,
      kind: "fx",
      trackId: t.id,
      clipIds: [c.id],
      rangeMs: c.range,
      outputFormat: fmt,
      composition,
      inputProps: {
        trackId: t.id,
        clipId: c.id,
        effect: c.effect,
        params: c.params ?? {},
        targetClipId: c.targetClipId,
        meta: graph.meta,
      },
      fileBasename: `stem-fx-${c.effect}-${c.id}-${id.slice(0, 8)}`,
    });
  }
}

function collectTitleCardStems(
  graph: SceneGraph,
  fmt: AlphaOutputFormat,
  composition: string,
  out: StemRender[],
): void {
  for (const t of graph.tracks) {
    if (t.kind !== "video" && t.kind !== "overlay") continue;
    for (const c of t.clips) {
      if (c.kind !== "scene") continue;
      const sc = c as Extract<Clip, { kind: "scene" }>;
      const anims = [...(sc.animationsIn ?? []), ...(sc.animationsOut ?? [])];
      const hasTextAnim = anims.some((a) =>
        a.preset.startsWith("anim.text.") ||
        a.preset.startsWith("anim.in.typewriter") ||
        a.preset.startsWith("anim.in.scramble"),
      );
      if (!hasTextAnim) continue;
      const id = stemId("title-cards", [t.id, sc.id], [sc.hash]);
      out.push({
        id,
        kind: "title-cards",
        trackId: t.id,
        clipIds: [sc.id],
        rangeMs: sc.range,
        outputFormat: fmt,
        composition,
        inputProps: {
          trackId: t.id,
          clipId: sc.id,
          scenePreset: sc.scenePreset,
          sceneOverrides: sc.sceneOverrides ?? {},
          animationsIn: sc.animationsIn ?? [],
          animationsOut: sc.animationsOut ?? [],
          meta: graph.meta,
        },
        fileBasename: `stem-titlecard-${sc.id}-${id.slice(0, 8)}`,
      });
    }
  }
}

/* ====================================================================== */
/* Helpers                                                                 */
/* ====================================================================== */

function clipStart(c: Clip): number | null {
  if (c.kind === "transition") return null;
  return c.range[0];
}

function clipEnd(c: Clip): number | null {
  if (c.kind === "transition") return null;
  return c.range[1];
}

function clipHash(c: Clip): string {
  return (c as { hash?: string }).hash ?? "";
}

function stemId(kind: StemKind, scope: string[], hashes: string[]): string {
  const blob = JSON.stringify({ kind, scope, hashes });
  return createHash("sha256").update(blob).digest("hex").slice(0, 16);
}
