/**
 * Phase 1F — End-to-end golden test.
 *
 * Reconstructs the "Price Shock Reveal" scene from the design chat using the
 * Phase 1A–1D patch ops we just shipped, then asserts:
 *   • Blend mode + opacity round-trip onto the bg clip.
 *   • Advanced text animation preset (scramble_decode) registered on the hook.
 *   • Animated bezier mask reveals the chart over a 1.4s window.
 *   • Per-shot color grade with HSL qualifier + LUT installed on the bg.
 *   • Per-clip cache keys derived from `clipCacheKeys()` reflect every patch.
 *   • Hashes are deterministic across two identical builds.
 *
 * This is the "everything works together" gate before Phase 2.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/cinematic-grade-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import {
  applyPatch,
  clipCacheKeys,
  hashNode,
  lower,
  type ClipMaskRef,
  type ColorGradeTrackRef,
  type Patch,
  type SceneClip,
  type SceneGraph,
} from "../src/scene-graph";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

/* ---- 1. Bootstrap a graph from the existing fixture -------------------- */
const fixturePath = path.resolve(
  __dirname,
  "../src/scene-graph/__fixtures__/minimal-direction.json",
);
const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const direction = DirectionV3.parse(raw);
const baseGraph = lower(direction);

const videoTrack = baseGraph.tracks.find((t) => t.kind === "video")!;
const bgClip = videoTrack.clips[0] as SceneClip; // s1 — the hook scene

/* ---- 2. Build the cinematic patch chain (1A → 1C → 1D → 1B) ----------- */

// 2A — Phase 1A: blend mode + opacity on the bg
const patch1A: Patch = {
  agent: "cinematic-grade-smoke",
  agentVersion: "1.0.0",
  reason: "Phase 1A: dim bg slightly when chart enters",
  ops: [
    {
      op: "setClipCompositing",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      compositing: { blendMode: "normal", opacity: 0.65 },
    },
  ],
};

// 2B — Phase 1C: animated wipe mask reveals the bg from 9.8s to 11.2s.
//      In a real scene this would land on the chart-overlay clip; we install
//      it on the bg as a stand-in to exercise the IR contract.
const wipeTrack: ClipMaskRef["track"] = {
  keys: [
    { tMs: 9800, shape: { kind: "rect", left: 0, right: 0, top: 0, bottom: 1 } as unknown },
    { tMs: 11200, shape: { kind: "rect", left: 0, right: 1, top: 0, bottom: 1 } as unknown },
  ],
};
const patch1C: Patch = {
  agent: "cinematic-grade-smoke",
  agentVersion: "1.0.0",
  reason: "Phase 1C: chart wipe-in mask",
  ops: [
    {
      op: "setClipMasks",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      masks: [{ id: "chart_wipe", blend: "intersect", track: wipeTrack }],
    },
  ],
};

// 2C — Phase 1D: per-shot color grade with skin-tone HSL secondary + LUT
const grade: ColorGradeTrackRef = {
  keys: [
    {
      tMs: 0,
      primary: { saturation: 0.88, contrast: 1.06, temperature: 12 },
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
      lutId: "lut_archive_warm",
      lutStrength: 0.85,
    },
    {
      tMs: 8500,
      primary: { saturation: 0.85, contrast: 1.12, temperature: 15 },
      lutId: "lut_high_contrast_warm",
      lutStrength: 0.7,
    },
  ],
};
const patch1D: Patch = {
  agent: "cinematic-grade-smoke",
  agentVersion: "1.0.0",
  reason: "Phase 1D: warm vintage grade with skin-tone secondary",
  ops: [
    {
      op: "setClipColorGrade",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      colorGradeTrack: grade,
    },
  ],
};

// 2D — Phase 1B: replace bg's animationsIn with a scramble_decode preset.
//      The lowerer doesn't emit text animations on the bg today, but the
//      cache-key helper hashes any registered text-class preset. We use
//      `setClipProps` to attach the preset reference indirectly through
//      sceneOverrides (clean path); for the purposes of this E2E we
//      stamp `animationsIn` via `replaceClip` which also exercises hashing.
const updatedBg: SceneClip = {
  ...bgClip,
  animationsIn: [
    ...(bgClip.animationsIn ?? []),
    { preset: "anim.text.scramble_decode" },
  ],
};
const patch1B: Patch = {
  agent: "cinematic-grade-smoke",
  agentVersion: "1.0.0",
  reason: "Phase 1B: scramble-decode hook text",
  ops: [
    {
      op: "replaceClip",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      clip: updatedBg,
    },
  ],
};

/* ---- 3. Apply patches in order; assert each effect --------------------- */
/* Order matters: 1B uses `replaceClip` which clobbers any prior fields, so
 * it runs FIRST. The other patches (1A/1C/1D) use targeted ops that augment
 * the existing clip and stack on top of 1B's new baseline. */

let g: SceneGraph = baseGraph;
const initialRootHash = g.hash;

g = applyPatch(g, patch1B);
const after1B = pickClip(g, videoTrack.id, bgClip.id);
check(
  Array.isArray(after1B.animationsIn) &&
    after1B.animationsIn!.some((a) => a.preset === "anim.text.scramble_decode"),
  `1B: scramble_decode preset added`,
);

g = applyPatch(g, patch1A);
const after1A = pickClip(g, videoTrack.id, bgClip.id);
check(
  after1A.compositing?.blendMode === "normal" && after1A.compositing?.opacity === 0.65,
  `1A: compositing applied (got ${JSON.stringify(after1A.compositing)})`,
);

g = applyPatch(g, patch1C);
const after1C = pickClip(g, videoTrack.id, bgClip.id);
check(
  Array.isArray(after1C.masks) && after1C.masks!.length === 1,
  `1C: mask installed`,
);
check(after1C.masks?.[0]!.id === "chart_wipe", `1C: mask id`);

g = applyPatch(g, patch1D);
const afterAll = pickClip(g, videoTrack.id, bgClip.id);
check(!!afterAll.colorGradeTrack, `1D: color grade installed`);
check(
  afterAll.colorGradeTrack?.keys.length === 2,
  `1D: 2 grade keys`,
);
// Final state must carry every patch's effect.
check(afterAll.compositing?.opacity === 0.65, `final state preserves 1A`);
check(afterAll.masks?.length === 1, `final state preserves 1C`);
check(
  afterAll.animationsIn!.some((a) => a.preset === "anim.text.scramble_decode"),
  `final state preserves 1B`,
);

/* ---- 4. Hash invariants ----------------------------------------------- */

check(g.hash !== initialRootHash, `root hash changed after cinematic chain`);

// Re-apply the same chain to a fresh base — must end at the same root hash.
let g2: SceneGraph = baseGraph;
g2 = applyPatch(g2, patch1B);
g2 = applyPatch(g2, patch1A);
g2 = applyPatch(g2, patch1C);
g2 = applyPatch(g2, patch1D);
check(g.hash === g2.hash, `cinematic chain is deterministic`);

// Re-hash the resolved graph from scratch — must equal the stored root hash.
const recomputed = hashNode({ ...g, hash: "" });
// Note: hashNode strips `hash` fields by canonicalize rules, but the type
// requires the field to exist — clear it to confirm the canonical match.
check(recomputed === g.hash, `recomputed root hash matches stored`);

/* ---- 5. Cache keys reflect every advanced field ------------------------ */

const keys = clipCacheKeys(afterAll);
check(keys.blendMode === "normal", `cacheKeys.blendMode`);
check(typeof keys.blendModeHash === "string" && keys.blendModeHash.length === 64, `cacheKeys.blendModeHash`);
check(keys.maskCount === 1, `cacheKeys.maskCount`);
check(typeof keys.maskHash === "string" && keys.maskHash.length === 64, `cacheKeys.maskHash`);
check(typeof keys.colorGradeHash === "string" && keys.colorGradeHash.length === 64, `cacheKeys.colorGradeHash`);
check(typeof keys.textAnimHash === "string" && keys.textAnimHash.length === 64, `cacheKeys.textAnimHash`);

// Same clip → same cache keys (determinism).
const keys2 = clipCacheKeys(pickClip(g2, videoTrack.id, bgClip.id));
check(JSON.stringify(keys) === JSON.stringify(keys2), `cache keys deterministic`);

/* ---- 6. Cache keys are sensitive to changes --------------------------- */

const tweakedOpacity: Patch = {
  agent: "cinematic-grade-smoke",
  agentVersion: "1.0.0",
  ops: [
    {
      op: "setClipCompositing",
      trackId: videoTrack.id,
      clipId: bgClip.id,
      compositing: { opacity: 0.6 }, // changed
    },
  ],
};
const g3 = applyPatch(g, tweakedOpacity);
const keys3 = clipCacheKeys(pickClip(g3, videoTrack.id, bgClip.id));
check(keys.blendModeHash !== keys3.blendModeHash, `cache key responds to opacity change`);
check(keys.maskHash === keys3.maskHash, `mask hash unchanged when only blend changes`);
check(keys.colorGradeHash === keys3.colorGradeHash, `grade hash unchanged when only blend changes`);

/* ---- Outcome ---------------------------------------------------------- */

if (failures === 0) {
  console.log("OK cinematic-grade smoke");
  console.log(`   patches:     1A blend · 1C mask · 1D color grade · 1B text anim`);
  console.log(`   root hash:   ${g.hash.slice(0, 16)}…  (deterministic across 2 runs)`);
  console.log(
    `   cache keys:  blend=${keys.blendModeHash?.slice(0, 8)}… · mask=${keys.maskHash?.slice(0, 8)}… · grade=${keys.colorGradeHash?.slice(0, 8)}… · anim=${keys.textAnimHash?.slice(0, 8)}…`,
  );
} else {
  console.error(`\n${failures} cinematic-grade smoke check(s) failed.`);
  process.exit(1);
}

/* ---- helpers ---------------------------------------------------------- */
function pickClip(graph: SceneGraph, trackId: string, clipId: string): SceneClip {
  const t = graph.tracks.find((x) => x.id === trackId)!;
  const c = t.clips.find((x) => x.id === clipId)!;
  return c as SceneClip;
}
