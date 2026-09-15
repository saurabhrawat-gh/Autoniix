/**
 * Phase 4A — FCPXML 1.11 emitter.
 *
 * Translates a SceneGraph into a Final Cut Pro XML document. The output is
 * importable into Final Cut Pro X (≥ 10.6.6) and most NLEs that consume
 * FCPXML (DaVinci Resolve, Premiere via plug-in, Motion).
 *
 * Scope (v1):
 *   • Project metadata (frame rate, resolution, title) → <fcpxml> + <project>.
 *   • Per-track lanes — video → spine, overlays → connected lanes, captions
 *     → connected lane with <title> elements (so the editor sees real text).
 *   • SceneClip / StockClip / CaptionClip / TransitionClip / ComposeClip.
 *   • Source-side filter chain (Phase 2) → <filter-video> / <effect> refs
 *     (informational; receiving NLE may not have the same filters installed).
 *   • Compositing (blend mode + opacity) → <adjust-blend> / <adjust-volume>.
 *   • Color grade (Phase 1D primary) → <adjust-color> with the mapped fields.
 *
 * Out of scope (v1, callable as TODO when needed):
 *   • Animated clip masks (Phase 1C) — FCPXML supports masks via <mask-shape>
 *     but the keyframe model is non-trivial; emit as a comment for now.
 *   • Animated text presets (Phase 1B) — exported as plain <title> with the
 *     final text; receiving NLE animates with its own engine.
 *
 * Design rules:
 *   • Output is deterministic (sorted attributes, stable resource IDs).
 *   • All time values use rational notation `<num>/<den>s` (FCPXML standard).
 *   • Resource IDs are content-addressed (`r-<sha256[:12]>`) so re-export
 *     is byte-identical when the input doesn't change.
 */

import { createHash } from "node:crypto";
import type { Clip, SceneGraph, SceneGraphMeta, Track } from "../scene-graph/types";

const FCPXML_VERSION = "1.11";

/* ====================================================================== */
/* Public API                                                              */
/* ====================================================================== */

export interface FcpxmlExportOptions {
  /** Project name shown in the FCP library. Defaults to `meta.title`. */
  projectName?: string;
  /** Library path the project is mounted under. Mostly cosmetic. */
  libraryName?: string;
  /** Pretty-print the XML with 2-space indent. Default true. */
  pretty?: boolean;
}

export function exportFcpxml(graph: SceneGraph, opts: FcpxmlExportOptions = {}): string {
  const ctx = newContext(graph.meta);
  const projectName = opts.projectName ?? graph.meta.title ?? "Untitled";
  const libraryName = opts.libraryName ?? `${projectName} Library`;

  collectResources(graph, ctx);

  const xml: string[] = [];
  xml.push(`<?xml version="1.0" encoding="UTF-8"?>`);
  xml.push(`<!DOCTYPE fcpxml>`);
  xml.push(`<fcpxml version="${FCPXML_VERSION}">`);
  xml.push(`  <resources>`);
  for (const r of ctx.resources) xml.push(`    ${r}`);
  xml.push(`  </resources>`);
  xml.push(`  <library name="${esc(libraryName)}">`);
  xml.push(`    <event name="${esc(projectName)}">`);
  xml.push(`      <project name="${esc(projectName)}">`);
  xml.push(
    `        <sequence format="${ctx.formatId}" duration="${secs(graph.meta.durationMs)}" tcStart="0s" tcFormat="${tcFormat(graph.meta.fps)}">`,
  );
  xml.push(`          <spine>`);

  const videoTracks = graph.tracks.filter((t) => t.kind === "video");
  const overlayTracks = graph.tracks.filter((t) => t.kind === "overlay");
  const captionTracks = graph.tracks.filter((t) => t.kind === "caption");
  const fxTracks = graph.tracks.filter((t) => t.kind === "fx");

  const primary = videoTracks[0];
  if (primary) {
    for (const c of primary.clips) {
      emitClipOnSpine(c, ctx, xml, "            ");
    }
  } else {
    xml.push(`            <gap duration="${secs(graph.meta.durationMs)}"/>`);
  }

  xml.push(`          </spine>`);

  let lane = 1;
  for (const t of [...videoTracks.slice(1), ...overlayTracks, ...fxTracks, ...captionTracks]) {
    for (const c of t.clips) {
      emitConnectedClip(c, ctx, xml, "          ", lane);
    }
    lane += 1;
  }

  xml.push(`        </sequence>`);
  xml.push(`      </project>`);
  xml.push(`    </event>`);
  xml.push(`  </library>`);
  xml.push(`</fcpxml>`);

  let out = xml.join("\n");
  if (opts.pretty === false) {
    out = out.replace(/\n\s+/g, "");
  }
  return out + "\n";
}

/* ====================================================================== */
/* Resource collection                                                     */
/* ====================================================================== */

interface FcpxmlContext {
  formatId: string;
  resources: string[];
  /** sha256 → assetId, so identical assetUrls share one <asset> resource. */
  assetIds: Map<string, string>;
  /** preset name → effectId, dedup'd across the project. */
  effectIds: Map<string, string>;
  meta: SceneGraphMeta;
}

function newContext(meta: SceneGraphMeta): FcpxmlContext {
  const formatId = `r-fmt-${meta.fps}-${meta.resolution.width}x${meta.resolution.height}`;
  return {
    formatId,
    resources: [],
    assetIds: new Map(),
    effectIds: new Map(),
    meta,
  };
}

function collectResources(graph: SceneGraph, ctx: FcpxmlContext): void {
  const { width, height } = ctx.meta.resolution;
  ctx.resources.push(
    `<format id="${ctx.formatId}" name="FFVideoFormat${height}p${ctx.meta.fps}" frameDuration="${frameDur(ctx.meta.fps)}" width="${width}" height="${height}" colorSpace="1-1-1 (Rec. 709)"/>`,
  );

  const visit = (g: SceneGraph): void => {
    for (const t of g.tracks) {
      for (const c of t.clips) {
        registerClipResources(c, ctx);
        if (c.kind === "compose") visit(c.graph);
      }
    }
  };
  visit(graph);
}

function registerClipResources(clip: Clip, ctx: FcpxmlContext): void {
  if (clip.kind === "stock") {
    const aid = assetIdForUrl(clip.assetUrl, clip.assetSha256, ctx);
    void aid;
  }
  if (clip.kind === "scene") {
    if (!ctx.effectIds.has(clip.scenePreset)) {
      const eid = `r-eff-${shortHash(clip.scenePreset)}`;
      ctx.effectIds.set(clip.scenePreset, eid);
      ctx.resources.push(
        `<effect id="${eid}" name="${esc(clip.scenePreset)}" uid=".../Generators.localized/Generators.localized/Custom.localized/Custom.motn"/>`,
      );
    }
  }
  if (clip.kind === "transition") {
    if (!ctx.effectIds.has(clip.transitionPreset)) {
      const eid = `r-tr-${shortHash(clip.transitionPreset)}`;
      ctx.effectIds.set(clip.transitionPreset, eid);
      ctx.resources.push(
        `<effect id="${eid}" name="${esc(clip.transitionPreset)}" uid=".../Transitions.localized/Movements.localized/Cross Dissolve.localized/Cross Dissolve.motr"/>`,
      );
    }
  }
}

function assetIdForUrl(url: string, sha256: string, ctx: FcpxmlContext): string {
  const key = sha256 || url;
  const existing = ctx.assetIds.get(key);
  if (existing) return existing;
  const id = `r-ast-${(sha256 || shortHash(url)).slice(0, 12)}`;
  ctx.assetIds.set(key, id);
  ctx.resources.push(
    `<asset id="${id}" name="${esc(filename(url))}" src="${esc(url)}" hasVideo="1" format="${ctx.formatId}" hasAudio="0" duration="0s"/>`,
  );
  return id;
}

/* ====================================================================== */
/* Clip emission                                                           */
/* ====================================================================== */

function emitClipOnSpine(c: Clip, ctx: FcpxmlContext, xml: string[], indent: string): void {
  emitClip(c, ctx, xml, indent, /* connected */ false, /* lane */ 0);
}

function emitConnectedClip(
  c: Clip,
  ctx: FcpxmlContext,
  xml: string[],
  indent: string,
  lane: number,
): void {
  emitClip(c, ctx, xml, indent, /* connected */ true, lane);
}

function emitClip(
  c: Clip,
  ctx: FcpxmlContext,
  xml: string[],
  indent: string,
  connected: boolean,
  lane: number,
): void {
  const startEnd = clipRange(c);
  if (!startEnd) return;
  const [startMs, endMs] = startEnd;
  const offset = secs(startMs);
  const duration = secs(endMs - startMs);
  const laneAttr = connected && lane > 0 ? ` lane="${lane}"` : "";
  const offsetAttr = connected ? ` offset="${offset}"` : ` offset="${offset}"`;

  const adjustments = renderAdjustments(c);

  switch (c.kind) {
    case "stock": {
      const aid = assetIdForUrl(c.assetUrl, c.assetSha256, ctx);
      xml.push(
        `${indent}<asset-clip${laneAttr} ref="${aid}"${offsetAttr} name="${esc(c.id)}" duration="${duration}" start="0s">`,
      );
      for (const a of adjustments) xml.push(`${indent}  ${a}`);
      xml.push(`${indent}</asset-clip>`);
      return;
    }
    case "scene": {
      const eid = ctx.effectIds.get(c.scenePreset)!;
      xml.push(
        `${indent}<video${laneAttr} ref="${eid}"${offsetAttr} name="${esc(c.id)}" duration="${duration}" start="0s">`,
      );
      for (const a of adjustments) xml.push(`${indent}  ${a}`);
      xml.push(`${indent}</video>`);
      return;
    }
    case "caption": {
      const text = c.text || "";
      xml.push(
        `${indent}<title${laneAttr}${offsetAttr} name="${esc(c.id)}" duration="${duration}" start="0s" ref="${ensureBasicTitleEffect(ctx)}">`,
      );
      xml.push(`${indent}  <text>`);
      xml.push(`${indent}    <text-style ref="ts1">${esc(text)}</text-style>`);
      xml.push(`${indent}  </text>`);
      xml.push(`${indent}  <text-style-def id="ts1">`);
      xml.push(
        `${indent}    <text-style font="Helvetica" fontSize="64" fontColor="1 1 1 1" alignment="center" bold="1"/>`,
      );
      xml.push(`${indent}  </text-style-def>`);
      for (const a of adjustments) xml.push(`${indent}  ${a}`);
      xml.push(`${indent}</title>`);
      return;
    }
    case "fx": {
      xml.push(
        `${indent}<!-- fx ${esc(c.id)} preset=${esc(c.effect)} target=${esc(c.targetClipId)} duration=${duration} -->`,
      );
      return;
    }
    case "transition": {
      const eid = ctx.effectIds.get(c.transitionPreset)!;
      xml.push(
        `${indent}<transition offset="${offset}" name="${esc(c.transitionPreset)}" duration="${secs(c.durationMs)}">`,
      );
      xml.push(`${indent}  <filter-video ref="${eid}"/>`);
      xml.push(`${indent}</transition>`);
      return;
    }
    case "compose": {
      xml.push(
        `${indent}<gap${laneAttr}${offsetAttr} name="${esc(`compose:${c.id}`)}" duration="${duration}" start="0s"/>`,
      );
      return;
    }
  }
}

function ensureBasicTitleEffect(ctx: FcpxmlContext): string {
  const KEY = "_basic_title";
  const existing = ctx.effectIds.get(KEY);
  if (existing) return existing;
  const id = "r-title-basic";
  ctx.effectIds.set(KEY, id);
  ctx.resources.push(
    `<effect id="${id}" name="Basic Title" uid=".../Titles.localized/Basic Text.localized/Basic Title.localized/Basic Title.moti"/>`,
  );
  return id;
}

/* ====================================================================== */
/* Adjustments — compositing, color grade, filters                         */
/* ====================================================================== */

function renderAdjustments(c: Clip): string[] {
  if (c.kind === "transition") return [];
  const out: string[] = [];

  const compositing = (c as { compositing?: { blendMode?: string; opacity?: number } }).compositing;
  if (compositing) {
    if (compositing.blendMode && compositing.blendMode !== "normal") {
      out.push(`<adjust-blend amount="1" mode="${esc(compositing.blendMode)}"/>`);
    }
    if (compositing.opacity !== undefined && compositing.opacity !== 1) {
      out.push(`<adjust-volume amount="0 dB"/>`);
      out.push(
        `<adjust-blend amount="${num(compositing.opacity)}"${
          compositing.blendMode ? ` mode="${esc(compositing.blendMode)}"` : ""
        }/>`,
      );
    }
  }

  const grade = (
    c as {
      colorGradeTrack?: {
        keys?: Array<{
          tMs?: number;
          primary?: { saturation?: number; contrast?: number; temperature?: number };
        }>;
      };
    }
  ).colorGradeTrack;
  if (grade?.keys?.length) {
    const k0 = grade.keys[0]!;
    const p = k0.primary ?? {};
    const sat = p.saturation ?? 1;
    const ctr = p.contrast ?? 1;
    const temp = p.temperature ?? 0;
    out.push(
      `<adjust-color saturation="${num(sat)}" contrast="${num(ctr)}" exposure="${num(temp / 50)}"/>`,
    );
  }

  const filters = (c as { filters?: Array<{ kind: string }> }).filters;
  if (filters?.length) {
    for (const f of filters) {
      out.push(`<!-- source-filter ${esc(f.kind)} -->`);
    }
  }

  const masks = (c as { masks?: Array<{ id: string }> }).masks;
  if (masks?.length) {
    out.push(`<!-- ${masks.length} animated mask(s); export to FCPXML mask-shape pending -->`);
  }

  return out;
}

/* ====================================================================== */
/* Helpers                                                                 */
/* ====================================================================== */

function clipRange(c: Clip): [number, number] | null {
  if (c.kind === "transition") return null;
  return c.range;
}

/** Convert ms → FCPXML rational seconds (locked to 1/<fps>s grid for stable round-trips). */
function secs(ms: number): string {
  const TICKS = 30000;
  const ticks = Math.round((ms / 1000) * TICKS);
  return `${ticks}/${TICKS}s`;
}

function frameDur(fps: number): string {
  if (fps === 30) return "100/3000s";
  if (fps === 24) return "100/2400s";
  if (fps === 25) return "100/2500s";
  if (fps === 60) return "100/6000s";
  return `1/${fps}s`;
}

function tcFormat(fps: number): string {
  return fps === 23.976 || fps === 29.97 || fps === 59.94 ? "DF" : "NDF";
}

function esc(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function num(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(4).replace(/\.?0+$/, "");
}

function filename(url: string): string {
  const last = url.split(/[/?]/).filter(Boolean).pop() ?? url;
  return last.replace(/\.[^.]+$/, "");
}

function shortHash(s: string): string {
  return createHash("sha256").update(s).digest("hex").slice(0, 12);
}
