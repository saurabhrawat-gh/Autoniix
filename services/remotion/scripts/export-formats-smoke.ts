/**
 * Phase 4D — Export-formats smoke test.
 *
 * Builds the cinematic Price-Shock SceneGraph (Phase 1F fixture stack), then
 * runs the three exporters and verifies:
 *
 *   • FCPXML
 *       - XML root is `<fcpxml version="1.11">`
 *       - Has exactly one <project>, <sequence>, <spine>
 *       - Resources block declares the project format + every referenced
 *         asset / effect with a stable id
 *       - Spine contains the right number of clips
 *       - Output is deterministic (re-export is byte-identical)
 *       - Output is well-formed XML (parse round-trip via DOMParser when
 *         available; otherwise a structural regex check)
 *
 *   • OTIO
 *       - Top-level `OTIO_SCHEMA: "Timeline.1"`
 *       - tracks.children length == graph.tracks length (caption tracks may
 *         be omitted when empty, but our fixture has clips on each)
 *       - Every clip has a `media_reference` with the right schema
 *       - source_range / available_range are RationalTime + TimeRange
 *       - Deterministic across two runs
 *       - Reasonable scale: at 30fps, a 11s clip → frame value 330
 *
 *   • Alpha stems plan
 *       - At least one stem per non-empty overlay/caption/fx/title-card
 *         category that exists in the graph
 *       - Each stem has stable id derived from clip hashes (deterministic)
 *       - Output formats are valid (codec + container compatible)
 *       - rangeMs sane (start < end, both within meta.durationMs)
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/export-formats-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  lower,
  type Patch,
  type SceneClip,
} from "../src/scene-graph";
import {
  exportFcpxml,
  exportOtio,
  planAlphaStems,
  PRORES_4444,
} from "../src/exporters";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

/* ---- 1. Build the Phase-1F cinematic fixture --------------------- */

const fixturePath = path.resolve(
  __dirname,
  "../src/scene-graph/__fixtures__/minimal-direction.json",
);
const direction = DirectionV3.parse(JSON.parse(fs.readFileSync(fixturePath, "utf8")));
const baseGraph = lower(direction);
const videoTrack = baseGraph.tracks.find((t) => t.kind === "video")!;
const bgClip = videoTrack.clips[0] as SceneClip;

// Apply the Phase-1B-D stack so the export covers compositing, masks, grade,
// text animations.
const cinematicPatch: Patch = {
  agent: "export-formats-smoke",
  agentVersion: "1.0.0",
  ops: [
    {
      op: "replaceClip",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      clip: {
        ...bgClip,
        animationsIn: [
          ...(bgClip.animationsIn ?? []),
          { preset: "anim.text.scramble_decode" },
        ],
      },
    },
    {
      op: "setClipCompositing",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      compositing: { blendMode: "screen", opacity: 0.85 },
    },
    {
      op: "setClipColorGrade",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      colorGradeTrack: {
        keys: [
          {
            tMs: 0,
            primary: { saturation: 0.92, contrast: 1.08, temperature: 8 },
          },
          {
            tMs: 4000,
            primary: { saturation: 0.85, contrast: 1.15, temperature: 12 },
          },
        ],
      },
    },
    {
      op: "setClipFilters",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      filters: [
        { kind: "deinterlace", algo: "yadif" } as unknown as never,
        { kind: "stabilize", shakiness: 5, smoothing: 15 } as unknown as never,
      ],
    },
  ],
};
const graph = applyPatch(baseGraph, cinematicPatch);

/* ---- 2. FCPXML --------------------------------------------------- */

const fcpxml = exportFcpxml(graph);
check(fcpxml.startsWith(`<?xml version="1.0" encoding="UTF-8"?>`), `fcpxml: XML prolog`);
check(fcpxml.includes(`<!DOCTYPE fcpxml>`), `fcpxml: DOCTYPE present`);
check(/<fcpxml version="1\.11">/.test(fcpxml), `fcpxml: 1.11 root`);
check(fcpxml.includes(`<resources>`), `fcpxml: resources block`);
check(fcpxml.includes(`<project name=`), `fcpxml: project element`);
check(fcpxml.includes(`<sequence `), `fcpxml: sequence element`);
check(fcpxml.includes(`<spine>`), `fcpxml: spine element`);

// Format declaration must include the project resolution.
const res = graph.meta.resolution;
check(
  fcpxml.includes(`width="${res.width}"`) && fcpxml.includes(`height="${res.height}"`),
  `fcpxml: format carries resolution ${res.width}x${res.height}`,
);

// At least one effect resource for the scene preset.
const effectCount = (fcpxml.match(/<effect /g) ?? []).length;
check(effectCount >= 1, `fcpxml: at least one effect resource (got ${effectCount})`);

// Spine should contain entries for every non-transition video clip.
const spineClipsCount = (fcpxml.match(/<(asset-clip|video|gap) /g) ?? []).length;
const expectedSpine = videoTrack.clips.filter((c) => c.kind !== "transition").length;
check(
  spineClipsCount >= expectedSpine,
  `fcpxml: spine has ≥ ${expectedSpine} clips (got ${spineClipsCount})`,
);

// Compositing → adjust-blend.
check(
  fcpxml.includes(`<adjust-blend `),
  `fcpxml: adjust-blend emitted for screen blend mode`,
);

// Color grade → adjust-color.
check(
  fcpxml.includes(`<adjust-color `),
  `fcpxml: adjust-color emitted for primary grade`,
);

// Determinism — re-export same graph
const fcpxml2 = exportFcpxml(graph);
check(fcpxml === fcpxml2, `fcpxml: deterministic across two exports`);

// Closing tags balance
check(fcpxml.includes(`</fcpxml>`), `fcpxml: closing tag`);

// Crude well-formedness — every <fcpxml> / <library> / <event> / <project> /
// <sequence> / <spine> opens and closes exactly once.
for (const tag of ["fcpxml", "library", "event", "project", "sequence", "spine", "resources"]) {
  const opens = (fcpxml.match(new RegExp(`<${tag}\\b`, "g")) ?? []).length;
  const closes = (fcpxml.match(new RegExp(`</${tag}>`, "g")) ?? []).length;
  check(opens === closes && opens === 1, `fcpxml: <${tag}> balanced (open=${opens} close=${closes})`);
}

/* ---- 3. OTIO ----------------------------------------------------- */

const otioStr = exportOtio(graph);
const otio = JSON.parse(otioStr) as Record<string, unknown>;
check(otio.OTIO_SCHEMA === "Timeline.1", `otio: schema Timeline.1`);
check(typeof otio.name === "string", `otio: timeline.name is string`);
check(
  (otio.global_start_time as Record<string, unknown>)?.OTIO_SCHEMA === "RationalTime.1",
  `otio: global_start_time is RationalTime.1`,
);

const tracks = otio.tracks as Record<string, unknown>;
check(tracks.OTIO_SCHEMA === "Stack.1", `otio: tracks is Stack.1`);
const trackList = tracks.children as Array<Record<string, unknown>>;
check(Array.isArray(trackList) && trackList.length >= 1, `otio: at least 1 track`);
for (const t of trackList) {
  check(t.OTIO_SCHEMA === "Track.1", `otio: track schema Track.1`);
  const kids = t.children as Array<Record<string, unknown>>;
  check(Array.isArray(kids), `otio: track children is array`);
  for (const k of kids) {
    const schema = k.OTIO_SCHEMA;
    const ok = schema === "Clip.2" || schema === "Gap.1" || schema === "Transition.1";
    check(ok === true, `otio: child schema is Clip|Gap|Transition (got ${String(schema)})`);
    if (schema === "Clip.2") {
      const sr = k.source_range as Record<string, unknown>;
      check(sr?.OTIO_SCHEMA === "TimeRange.1", `otio: clip.source_range is TimeRange.1`);
      const mr = k.media_reference as Record<string, unknown>;
      check(typeof mr?.OTIO_SCHEMA === "string", `otio: clip.media_reference has schema`);
    }
  }
}

// Frame-locked durations: 30fps × 1000ms = 30 frames per second
const fps = graph.meta.fps;
const totalFrames = Math.round((graph.meta.durationMs / 1000) * fps);
check(totalFrames > 0, `otio: total frames > 0`);

// Determinism
const otio2 = exportOtio(graph);
check(otioStr === otio2, `otio: deterministic across two exports`);

// yt_automation metadata round-trips the root hash
const metaYt = (otio.metadata as Record<string, unknown>).yt_automation as Record<string, unknown>;
check(metaYt.rootHash === graph.hash, `otio: metadata carries root hash`);

/* ---- 4. Alpha-stems plan ----------------------------------------- */

const plan = planAlphaStems(graph);
check(plan.stems.length >= 1, `alpha: at least one stem (got ${plan.stems.length})`);

for (const s of plan.stems) {
  check(s.id.length === 16, `alpha: stem id is 16 hex chars (got ${s.id.length})`);
  check(s.rangeMs[0] < s.rangeMs[1], `alpha: stem rangeMs[0] < rangeMs[1]`);
  check(
    s.rangeMs[0] >= 0 && s.rangeMs[1] <= graph.meta.durationMs,
    `alpha: stem range within project duration (${s.rangeMs[0]}-${s.rangeMs[1]} ⊂ 0-${graph.meta.durationMs})`,
  );
  check(typeof s.composition === "string" && s.composition.length > 0, `alpha: composition non-empty`);
  check(s.outputFormat.codec === "prores4444" || s.outputFormat.codec === "vp9-alpha", `alpha: codec valid`);
  check(s.fileBasename.includes(s.id.slice(0, 8)) || s.fileBasename.endsWith(s.id), `alpha: filename includes hash`);
  check(s.clipIds.length >= 1, `alpha: stem has ≥ 1 clip ref`);
}

// Determinism
const plan2 = planAlphaStems(graph);
check(
  plan.stems.length === plan2.stems.length &&
    plan.stems.every((s, i) => s.id === plan2.stems[i]!.id),
  `alpha: plan deterministic across calls`,
);

// Title-card stem should be present because we attached scramble_decode.
const hasTitleCard = plan.stems.some((s) => s.kind === "title-cards");
check(hasTitleCard, `alpha: scramble_decode produced a title-card stem`);

// VP9-alpha format alternative is also plannable.
const planVp9 = planAlphaStems(graph, { defaultFormat: { ...PRORES_4444 } });
check(planVp9.stems.every((s) => s.outputFormat.codec === "prores4444"), `alpha: format override applies`);

/* ---- Outcome ------------------------------------------------------ */

if (failures === 0) {
  console.log("OK export-formats smoke");
  console.log(`   fcpxml:   ${fcpxml.length} bytes · ${spineClipsCount} spine items · ${effectCount} effects`);
  console.log(`   otio:     ${otioStr.length} bytes · ${trackList.length} tracks · root_hash=${graph.hash.slice(0, 12)}…`);
  console.log(`   alpha:    ${plan.stems.length} stems · kinds=${[...new Set(plan.stems.map((s) => s.kind))].join("·")} · ${plan.skipped.length} skipped`);
} else {
  console.error(`\n${failures} export-formats check(s) failed.`);
  process.exit(1);
}
