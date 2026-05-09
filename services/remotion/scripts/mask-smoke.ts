/**
 * Phase 1C — Animated bezier mask smoke test.
 *
 * Verifies the pure compute layer (`registry/masks.ts`), the IR mutation
 * (`setClipMasks` patch op), and validation rules.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/mask-smoke.ts
 *
 * Asserts:
 *   1. maskAtTime() interpolates rect / ellipse / bezier_path between keys
 *      and clamps before-first / after-last.
 *   2. Mismatched-kind keys snap (no cross-morph).
 *   3. shapeToSvgPath() emits valid `d` strings for SVG kinds; null for
 *      luma/chroma.
 *   4. validateMaskTrack rejects unsorted / empty / out-of-range inputs.
 *   5. setClipMasks patch op installs masks, updates clip + root hashes,
 *      and is deterministic.
 *
 * Exits non-zero on any failure.
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  hashNode,
  lower,
  type ClipMaskRef,
  type Patch,
  type SceneClip,
} from "../src/scene-graph";
import {
  maskAtTime,
  shapeToSvgPath,
  validateMaskTrack,
  type MaskTrack,
} from "../src/registry/masks";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}
function expectThrow(fn: () => void, msg: string): void {
  try {
    fn();
    console.error(`FAIL: ${msg} (expected throw)`);
    failures += 1;
  } catch {
    /* ok */
  }
}

/* ---- 1. Interpolation: rect, ellipse, bezier_path --------------------- */
const rectTrack: MaskTrack = {
  keys: [
    { tMs: 0, shape: { kind: "rect", left: 0, right: 0, top: 0, bottom: 1 } },
    { tMs: 1000, shape: { kind: "rect", left: 0, right: 1, top: 0, bottom: 1 } },
  ],
};
{
  const a = maskAtTime(rectTrack, 0);
  const mid = maskAtTime(rectTrack, 500);
  const b = maskAtTime(rectTrack, 1000);
  const after = maskAtTime(rectTrack, 5000);
  check(a.shape.kind === "rect" && (a.shape as { right: number }).right === 0, "rect @ t=0");
  check(
    mid.shape.kind === "rect" && (mid.shape as { right: number }).right === 0.5,
    `rect mid right=${(mid.shape as { right: number }).right}`,
  );
  check(b.shape.kind === "rect" && (b.shape as { right: number }).right === 1, "rect @ t=1000");
  check(
    after.shape.kind === "rect" && (after.shape as { right: number }).right === 1,
    "rect clamps after-last",
  );
}

const ellipseTrack: MaskTrack = {
  keys: [
    { tMs: 0, shape: { kind: "ellipse", cx: 0.5, cy: 0.5, rx: 0.1, ry: 0.1 } },
    { tMs: 1000, shape: { kind: "ellipse", cx: 0.5, cy: 0.5, rx: 0.4, ry: 0.4 } },
  ],
};
{
  const mid = maskAtTime(ellipseTrack, 500);
  check(
    mid.shape.kind === "ellipse" && Math.abs((mid.shape as { rx: number }).rx - 0.25) < 1e-9,
    `ellipse mid rx=${(mid.shape as { rx: number }).rx}`,
  );
}

const bezierTrack: MaskTrack = {
  keys: [
    {
      tMs: 0,
      shape: {
        kind: "bezier_path",
        segments: [
          { cmd: "M", points: [0, 0.5] },
          { cmd: "C", points: [0.25, 0, 0.75, 0, 1, 0.5] },
          { cmd: "Z", points: [] },
        ],
      },
    },
    {
      tMs: 1000,
      shape: {
        kind: "bezier_path",
        segments: [
          { cmd: "M", points: [0, 0.5] },
          { cmd: "C", points: [0.25, 1, 0.75, 1, 1, 0.5] },
          { cmd: "Z", points: [] },
        ],
      },
    },
  ],
};
{
  const mid = maskAtTime(bezierTrack, 500);
  check(mid.shape.kind === "bezier_path", "bezier mid kind");
  if (mid.shape.kind === "bezier_path") {
    const cseg = mid.shape.segments[1]!;
    check(
      Math.abs(cseg.points[1]! - 0.5) < 1e-9,
      `bezier mid c1.y=${cseg.points[1]} (expected 0.5)`,
    );
  }
}

/* ---- 2. Cross-kind snap (no morph between rect and ellipse) ----------- */
const mixedTrack: MaskTrack = {
  keys: [
    { tMs: 0, shape: { kind: "rect", left: 0, right: 1, top: 0, bottom: 1 } },
    { tMs: 1000, shape: { kind: "ellipse", cx: 0.5, cy: 0.5, rx: 0.5, ry: 0.5 } },
  ],
};
{
  const early = maskAtTime(mixedTrack, 250);
  const late = maskAtTime(mixedTrack, 750);
  check(early.shape.kind === "rect", `mixed early snaps to rect`);
  check(late.shape.kind === "ellipse", `mixed late snaps to ellipse`);
}

/* ---- 3. SVG path serialization ---------------------------------------- */
{
  const rect = shapeToSvgPath(
    { kind: "rect", left: 0, right: 0.5, top: 0, bottom: 0.5 },
    100,
    100,
  );
  check(typeof rect === "string" && rect!.startsWith("M"), `rect → SVG path: ${rect}`);

  const ell = shapeToSvgPath(
    { kind: "ellipse", cx: 0.5, cy: 0.5, rx: 0.4, ry: 0.4 },
    100,
    100,
  );
  check(typeof ell === "string" && ell!.includes("A"), `ellipse → SVG arc path`);

  const luma = shapeToSvgPath(
    { kind: "luma", threshold: 0.5, softness: 0.1 },
    100,
    100,
  );
  check(luma === null, `luma path is null (shader path)`);

  const chroma = shapeToSvgPath(
    { kind: "chroma", keyColor: [0, 1, 0], tolerance: 0.1, spill: 0.05 },
    100,
    100,
  );
  check(chroma === null, `chroma path is null (shader path)`);
}

/* ---- 4. Validation ---------------------------------------------------- */
expectThrow(() => validateMaskTrack({ keys: [] }), "empty track rejected");
expectThrow(
  () =>
    validateMaskTrack({
      keys: [
        { tMs: 100, shape: { kind: "rect", left: 0, right: 1, top: 0, bottom: 1 } },
        { tMs: 50, shape: { kind: "rect", left: 0, right: 1, top: 0, bottom: 1 } },
      ],
    }),
  "unsorted keys rejected",
);
expectThrow(
  () =>
    validateMaskTrack({
      keys: [{ tMs: 0, shape: { kind: "rect", left: 1, right: 0, top: 0, bottom: 1 } }],
    }),
  "rect with left>right rejected",
);
expectThrow(
  () =>
    validateMaskTrack({
      keys: [{ tMs: 0, shape: { kind: "luma", threshold: 1.5, softness: 0 } }],
    }),
  "luma threshold OOB rejected",
);

/* ---- 5. setClipMasks patch op ----------------------------------------- */
const fixturePath = path.resolve(
  __dirname,
  "../src/scene-graph/__fixtures__/minimal-direction.json",
);
const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const direction = DirectionV3.parse(raw);
const g0 = lower(direction);
const initialRoot = g0.hash;
const videoTrack = g0.tracks.find((t) => t.kind === "video")!;
const targetClip = videoTrack.clips[0] as SceneClip;

const newMasks: ClipMaskRef[] = [
  {
    id: "wipe",
    blend: "intersect",
    track: rectTrack as unknown as { keys: ClipMaskRef["track"]["keys"] },
  },
];
const patch: Patch = {
  agent: "mask-smoke",
  agentVersion: "1.0.0",
  ops: [
    {
      op: "setClipMasks",
      trackId: videoTrack.id,
      clipId: targetClip.id,
      masks: newMasks,
    },
  ],
};
const g1 = applyPatch(g0, patch);
const updated = g1.tracks
  .find((t) => t.id === videoTrack.id)!
  .clips.find((c) => c.id === targetClip.id) as SceneClip;
check(Array.isArray(updated.masks) && updated.masks?.length === 1, "mask installed");
check(updated.masks?.[0]!.id === "wipe", "mask id preserved");
check(updated.hash !== targetClip.hash, "clip hash changed after mask patch");
check(g1.hash !== initialRoot, "root hash changed after mask patch");

const g2 = applyPatch(g0, patch);
check(g1.hash === g2.hash, "applyPatch determinism");
void hashNode; // referenced for completeness

// Validation rejects bad masks via patch
expectThrow(
  () =>
    applyPatch(g0, {
      agent: "mask-smoke",
      agentVersion: "1.0.0",
      ops: [
        {
          op: "setClipMasks",
          trackId: videoTrack.id,
          clipId: targetClip.id,
          masks: [{ id: "bad", track: { keys: [] } }],
        },
      ],
    }),
  "empty mask track rejected via patch",
);
expectThrow(
  () =>
    applyPatch(g0, {
      agent: "mask-smoke",
      agentVersion: "1.0.0",
      ops: [
        {
          op: "setClipMasks",
          trackId: videoTrack.id,
          clipId: targetClip.id,
          masks: [
            { id: "a", track: rectTrack as unknown as { keys: ClipMaskRef["track"]["keys"] } },
            { id: "a", track: rectTrack as unknown as { keys: ClipMaskRef["track"]["keys"] } },
          ],
        },
      ],
    }),
  "duplicate mask ids rejected via patch",
);

if (failures === 0) {
  console.log("OK mask smoke");
  console.log(
    `   kinds:       rect · ellipse · bezier_path (svg path) · luma · chroma (shader path)`,
  );
  console.log(`   patch op:    setClipMasks OK · deterministic`);
} else {
  console.error(`\n${failures} mask smoke check(s) failed.`);
  process.exit(1);
}
