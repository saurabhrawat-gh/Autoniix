/**
 * Phase 1A — Blend mode smoke test.
 *
 * Verifies the SceneGraph IR + commit layer + compositing helpers for
 * per-layer blend modes.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/blend-mode-smoke.ts
 *
 * Checks:
 *   1. All 16 declared blend modes round-trip through the IR (validate +
 *      hash + canonical-stringify).
 *   2. CSS-supported modes resolve to the expected `mix-blend-mode` strings.
 *   3. Shader-only modes (add, subtract) are flagged via `requiresShader`.
 *   4. The `setClipCompositing` patch op mutates a clip in place and changes
 *      both the clip-level and root-level hash.
 *   5. Invalid input (bad mode, out-of-range opacity) is rejected.
 *
 * Exits non-zero on any failure.
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  BLEND_MODES,
  cssBlendMode,
  hashNode,
  lower,
  requiresShader,
  validateCompositing,
  type BlendMode,
  type Compositing,
  type Patch,
  type SceneClip,
} from "../src/scene-graph";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

/* ---- 1. All 16 modes round-trip --------------------------------------- */
check(BLEND_MODES.length === 16, `expected 16 blend modes, got ${BLEND_MODES.length}`);
for (const mode of BLEND_MODES) {
  const c: Compositing = { blendMode: mode, opacity: 0.75 };
  validateCompositing(c, `test-${mode}`);
  // canonical-stringify must succeed
  const h = hashNode(c);
  check(h.length === 64, `hash for ${mode} not 64 hex chars`);
}

/* ---- 2. CSS mapping --------------------------------------------------- */
const cssExpected: Partial<Record<BlendMode, string>> = {
  normal: "normal",
  multiply: "multiply",
  screen: "screen",
  overlay: "overlay",
  soft_light: "soft-light",
  hard_light: "hard-light",
  color_dodge: "color-dodge",
  color_burn: "color-burn",
  difference: "difference",
  exclusion: "exclusion",
  hue: "hue",
  saturation: "saturation",
  color: "color",
  luminosity: "luminosity",
};
for (const [mode, expected] of Object.entries(cssExpected) as [BlendMode, string][]) {
  const got = cssBlendMode(mode);
  check(got === expected, `cssBlendMode(${mode}) → expected "${expected}" got "${got}"`);
}

/* ---- 3. Shader fallback flag ------------------------------------------ */
check(cssBlendMode("add") === null, `cssBlendMode(add) should be null`);
check(cssBlendMode("subtract") === null, `cssBlendMode(subtract) should be null`);
check(requiresShader("add"), `requiresShader(add) should be true`);
check(requiresShader("subtract"), `requiresShader(subtract) should be true`);
check(!requiresShader("multiply"), `requiresShader(multiply) should be false`);
check(!requiresShader(undefined), `requiresShader(undefined) should be false`);

/* ---- 4. Patch op round-trip ------------------------------------------- */
const fixturePath = path.resolve(
  __dirname,
  "../src/scene-graph/__fixtures__/minimal-direction.json",
);
const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const direction = DirectionV3.parse(raw);

const g0 = lower(direction);
const initialRootHash = g0.hash;
const videoTrack = g0.tracks.find((t) => t.kind === "video");
check(!!videoTrack, "expected at least one video track");
const targetClip = videoTrack?.clips[0] as SceneClip | undefined;
check(!!targetClip && targetClip.kind === "scene", "expected first clip to be a scene clip");

if (videoTrack && targetClip) {
  const patch: Patch = {
    agent: "blend-mode-smoke",
    agentVersion: "1.0.0",
    ops: [
      {
        op: "setClipCompositing",
        trackId: videoTrack.id,
        clipId: targetClip.id,
        compositing: { blendMode: "overlay", opacity: 0.85 },
      },
    ],
    reason: "test: tag the hook with overlay@0.85",
  };
  const g1 = applyPatch(g0, patch);

  const updated = g1.tracks
    .find((t) => t.id === videoTrack.id)
    ?.clips.find((c) => c.id === targetClip.id) as SceneClip | undefined;
  check(!!updated, "patched clip should still exist");
  check(
    updated?.compositing?.blendMode === "overlay",
    `expected blendMode=overlay, got ${updated?.compositing?.blendMode}`,
  );
  check(
    updated?.compositing?.opacity === 0.85,
    `expected opacity=0.85, got ${updated?.compositing?.opacity}`,
  );
  check(
    updated?.hash !== targetClip.hash,
    "clip hash should change after compositing patch",
  );
  check(g1.hash !== initialRootHash, "root hash should change after compositing patch");

  // Re-applying the same patch must be deterministic (same hash).
  const g2 = applyPatch(g0, patch);
  check(g2.hash === g1.hash, "applyPatch must be deterministic");

  // Partial update — change only opacity.
  const partial: Patch = {
    agent: "blend-mode-smoke",
    agentVersion: "1.0.0",
    ops: [
      {
        op: "setClipCompositing",
        trackId: videoTrack.id,
        clipId: targetClip.id,
        compositing: { opacity: 0.5 },
      },
    ],
  };
  const g3 = applyPatch(g1, partial);
  const partialUpdated = g3.tracks
    .find((t) => t.id === videoTrack.id)
    ?.clips.find((c) => c.id === targetClip.id) as SceneClip | undefined;
  check(
    partialUpdated?.compositing?.blendMode === "overlay",
    "partial update must preserve existing blendMode",
  );
  check(
    partialUpdated?.compositing?.opacity === 0.5,
    "partial update must apply new opacity",
  );
}

/* ---- 5. Invalid inputs are rejected ----------------------------------- */
function expectThrow(fn: () => void, msg: string): void {
  try {
    fn();
    console.error(`FAIL: ${msg} (expected throw)`);
    failures += 1;
  } catch {
    // ok
  }
}
expectThrow(
  () => validateCompositing({ blendMode: "weird" as BlendMode }, "x"),
  "unknown blend mode should throw",
);
expectThrow(
  () => validateCompositing({ opacity: -0.1 }, "x"),
  "opacity < 0 should throw",
);
expectThrow(
  () => validateCompositing({ opacity: 1.1 }, "x"),
  "opacity > 1 should throw",
);
expectThrow(
  () => validateCompositing({ opacity: Number.NaN }, "x"),
  "opacity NaN should throw",
);

if (failures === 0) {
  console.log("OK blend-mode smoke");
  console.log(`   modes:       ${BLEND_MODES.length} (14 CSS · 2 shader-fallback)`);
  console.log(`   patch op:    setClipCompositing OK · deterministic`);
} else {
  console.error(`\n${failures} blend-mode smoke check(s) failed.`);
  process.exit(1);
}
