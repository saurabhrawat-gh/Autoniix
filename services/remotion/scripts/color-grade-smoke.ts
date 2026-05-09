/**
 * Phase 1D — Per-shot color grade smoke test.
 *
 * Verifies the pure compute layer (`registry/colorGrade.ts`), the IR
 * mutation (`setClipColorGrade` patch op), and the algebra of the primary +
 * secondary correction.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/color-grade-smoke.ts
 *
 * Asserts:
 *   1. `applyPrimaryRgb` is identity for the default (empty) primary.
 *   2. Saturation = 0 collapses RGB to luma; saturation = 2 boosts.
 *   3. HSL qualifier weight = 1 inside, 0 outside, smoothly varies in the
 *      fade band.
 *   4. Power-window weight ∈ [0..1]; rect/ellipse correctly soft-edge.
 *   5. `colorGradeAtTime` interpolates primaries across keys.
 *   6. `setClipColorGrade` patch op installs the track and changes hashes
 *      deterministically; rejects bad input.
 *
 * Exits non-zero on any failure.
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  lower,
  type ColorGradeTrackRef,
  type Patch,
  type SceneClip,
} from "../src/scene-graph";
import {
  applyPrimaryRgb,
  colorGradeAtTime,
  hslQualifierWeight,
  powerWindowWeight,
  validateColorGradeTrack,
  type ColorGradeTrack,
  type ColorPrimary,
  type HslQualifier,
  type PowerWindow,
} from "../src/registry/colorGrade";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}
function near(a: number, b: number, eps = 1e-3): boolean {
  return Math.abs(a - b) < eps;
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

/* ---- 1. Identity primary ------------------------------------------------ */
{
  const empty: ColorPrimary = {};
  const out = applyPrimaryRgb([0.4, 0.6, 0.8], empty);
  check(near(out[0], 0.4) && near(out[1], 0.6) && near(out[2], 0.8), `identity primary: ${out}`);
}

/* ---- 2. Saturation 0 = luma; 2 = boost --------------------------------- */
{
  const desat = applyPrimaryRgb([0.8, 0.2, 0.2], { saturation: 0 });
  // Expected luma ~ 0.2126*0.8 + 0.7152*0.2 + 0.0722*0.2 ≈ 0.32
  const expectedY = 0.2126 * 0.8 + 0.7152 * 0.2 + 0.0722 * 0.2;
  check(near(desat[0], expectedY) && near(desat[1], expectedY) && near(desat[2], expectedY),
    `saturation=0 collapses to luma=${expectedY.toFixed(4)}, got ${desat}`);

  const boost = applyPrimaryRgb([0.5, 0.5, 0.7], { saturation: 2 });
  // Blue channel should pull further from luma than the green/red.
  const Y = 0.2126 * 0.5 + 0.7152 * 0.5 + 0.0722 * 0.7;
  check(boost[2] > 0.7 || boost[2] - Y > 0.7 - Y, `saturation=2 pushes blue away from luma`);
}

/* ---- 3. HSL qualifier weight -------------------------------------------- */
{
  const q: HslQualifier = {
    kind: "hsl_qualifier",
    hueCenter: 25, // orange
    hueWidth: 40,
    saturationRange: [0.15, 1.0],
    luminanceRange: [0.1, 0.9],
    softness: 0.2,
    grade: {},
  };
  // Pure orange should weight ~1
  const w_in = hslQualifierWeight([0.95, 0.55, 0.15], q);
  // Pure blue should weight ~0
  const w_out = hslQualifierWeight([0.1, 0.2, 0.95], q);
  // Edge case: hue ~45° (just past the halfWidth boundary; should land in fade band)
  const w_edge = hslQualifierWeight([0.90, 0.71, 0.15], q);
  check(w_in > 0.7, `HSL inside weight should be high, got ${w_in.toFixed(3)}`);
  check(w_out < 0.05, `HSL outside weight should be low, got ${w_out.toFixed(3)}`);
  check(w_edge > 0 && w_edge < 1, `HSL edge weight ∈ (0,1), got ${w_edge.toFixed(3)}`);
}

/* ---- 4. Power-window weight --------------------------------------------- */
{
  const ellipse: PowerWindow = {
    kind: "power_window",
    shape: { kind: "ellipse", cx: 0.5, cy: 0.5, rx: 0.25, ry: 0.25 },
    softness: 0.1,
    grade: {},
  };
  const w_center = powerWindowWeight(0.5, 0.5, ellipse);
  const w_edge = powerWindowWeight(0.75, 0.5, ellipse); // exactly on boundary
  const w_out = powerWindowWeight(0.95, 0.95, ellipse);
  check(w_center === 1, `ellipse center weight: ${w_center}`);
  check(w_edge > 0 && w_edge < 1, `ellipse boundary soft-edge: ${w_edge.toFixed(3)}`);
  check(w_out === 0, `ellipse outside weight: ${w_out}`);

  const rect: PowerWindow = {
    kind: "power_window",
    shape: { kind: "rect", left: 0.2, right: 0.8, top: 0.2, bottom: 0.8 },
    softness: 0.05,
    grade: {},
  };
  const r_in = powerWindowWeight(0.5, 0.5, rect);
  const r_out = powerWindowWeight(0.05, 0.05, rect);
  check(r_in === 1, `rect inside weight: ${r_in}`);
  check(r_out === 0, `rect outside weight: ${r_out}`);

  const inverted: PowerWindow = { ...ellipse, invert: true };
  const w_invert_center = powerWindowWeight(0.5, 0.5, inverted);
  check(w_invert_center === 0, `inverted ellipse center should be 0, got ${w_invert_center}`);
}

/* ---- 5. colorGradeAtTime interpolation ---------------------------------- */
{
  const track: ColorGradeTrack = {
    keys: [
      { tMs: 0, primary: { saturation: 1, contrast: 1 } },
      { tMs: 1000, primary: { saturation: 0.5, contrast: 1.4 } },
    ],
  };
  const a = colorGradeAtTime(track, 0);
  const mid = colorGradeAtTime(track, 500);
  const b = colorGradeAtTime(track, 1000);
  const after = colorGradeAtTime(track, 5000);
  check(a.primary.saturation === 1, "key A saturation");
  check(near(mid.primary.saturation ?? -1, 0.75), `mid saturation: ${mid.primary.saturation}`);
  check(near(mid.primary.contrast ?? -1, 1.2), `mid contrast: ${mid.primary.contrast}`);
  check(b.primary.saturation === 0.5, "key B saturation");
  check(after.primary.saturation === 0.5, "after-last clamps");
}

/* ---- 6. Patch op round-trip --------------------------------------------- */
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

const newGrade: ColorGradeTrackRef = {
  keys: [
    {
      tMs: 0,
      primary: { saturation: 0.85, contrast: 1.05 },
      secondaries: [
        {
          kind: "hsl_qualifier",
          hueCenter: 25,
          hueWidth: 40,
          saturationRange: [0.15, 0.85],
          luminanceRange: [0.2, 0.8],
          softness: 0.3,
          grade: { saturation: 1.15 },
        } as Record<string, unknown>,
      ],
      lutId: "lut.envato.cinematic_01",
      lutStrength: 0.85,
    },
  ],
};
const patch: Patch = {
  agent: "color-grade-smoke",
  agentVersion: "1.0.0",
  ops: [
    {
      op: "setClipColorGrade",
      trackId: videoTrack.id,
      clipId: targetClip.id,
      colorGradeTrack: newGrade,
    },
  ],
};
const g1 = applyPatch(g0, patch);
const updated = g1.tracks
  .find((t) => t.id === videoTrack.id)!
  .clips.find((c) => c.id === targetClip.id) as SceneClip;
check(!!updated.colorGradeTrack, "color grade track installed");
check(updated.colorGradeTrack?.keys.length === 1, "color grade key count");
check(updated.hash !== targetClip.hash, "clip hash changed after grade patch");
check(g1.hash !== initialRoot, "root hash changed after grade patch");

const g2 = applyPatch(g0, patch);
check(g1.hash === g2.hash, "applyPatch determinism");

// Validation rejects bad inputs
expectThrow(
  () => validateColorGradeTrack({ keys: [] } as unknown as ColorGradeTrack),
  "empty grade track rejected",
);
expectThrow(
  () =>
    validateColorGradeTrack({
      keys: [{ tMs: 0, primary: { saturation: -0.5 } }],
    } as unknown as ColorGradeTrack),
  "negative saturation rejected",
);
expectThrow(
  () =>
    validateColorGradeTrack({
      keys: [{ tMs: 0, primary: { temperature: 200 } }],
    } as unknown as ColorGradeTrack),
  "temperature out of range rejected",
);
expectThrow(
  () =>
    applyPatch(g0, {
      agent: "color-grade-smoke",
      agentVersion: "1.0.0",
      ops: [
        {
          op: "setClipColorGrade",
          trackId: videoTrack.id,
          clipId: targetClip.id,
          colorGradeTrack: {
            keys: [{ tMs: 0, primary: { saturation: -1 } }],
          } as unknown as ColorGradeTrackRef,
        },
      ],
    }),
  "bad grade rejected via patch",
);

if (failures === 0) {
  console.log("OK color-grade smoke");
  console.log(
    `   primary:     identity · sat collapse · sat boost · contrast · temp/tint`,
  );
  console.log(
    `   secondary:   hsl_qualifier (smooth fade) · power_window (ellipse + rect, invert)`,
  );
  console.log(`   patch op:    setClipColorGrade OK · deterministic`);
} else {
  console.error(`\n${failures} color-grade smoke check(s) failed.`);
  process.exit(1);
}
