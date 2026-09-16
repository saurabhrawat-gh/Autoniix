/**
 * Director + Editor pipeline smoke (P0.8).
 *
 * Exercises:
 *   1. Director promotes the first scene to a hook archetype when needed.
 *   2. Editor adds animations to clips that lack them.
 *   3. Editor inserts pattern-interrupt transitions on long uninterrupted runs.
 *   4. Patches commit cleanly via applyPatch with monotonically changing root hash.
 *
 * Run: cd services/remotion && npx tsx scripts/director-editor-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import { applyPatch, lower } from "../src/scene-graph";
import { makeDirector, makeEditor } from "../src/agents";

async function main() {
  const fixturePath = path.resolve(
    __dirname,
    "../src/scene-graph/__fixtures__/minimal-direction.json",
  );
  const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

  const baseSeg = raw.segments[0];
  raw.segments = Array.from({ length: 8 }, (_, i) => ({
    ...baseSeg,
    id: `s${i + 1}`,
    start_ms: i * 3000,
    duration_ms: 3000,
    scene_preset: "StockFootageScene",
    animations_in: undefined,
    animations_out: undefined,
    transition_out: undefined,
  }));
  raw.meta.duration_target_seconds = 24;

  const direction = DirectionV3.parse(raw);
  const g0 = lower(direction);

  const { agent: director, defaultCtx: dctx } = makeDirector();
  const dRes = await director.run({ graph: g0 }, { ...dctx, niche: "documentary" });
  if (!dRes.output.changedHook) {
    console.error("FAIL: Director did not promote the first scene to a hook");
    process.exit(1);
  }
  if (!dRes.patch) {
    console.error("FAIL: Director did not emit a patch");
    process.exit(1);
  }
  const g1 = applyPatch(g0, dRes.patch);
  if (g1.hash === g0.hash) {
    console.error("FAIL: graph hash did not change after Director patch");
    process.exit(1);
  }

  const { agent: editor, defaultCtx: ectx } = makeEditor();
  const eRes = await editor.run({ graph: g1 }, ectx);
  if (eRes.output.animationFixes !== 8) {
    console.error(`FAIL: expected 8 animation fixes, got ${eRes.output.animationFixes}`);
    process.exit(1);
  }
  if (eRes.output.pacingFixes < 1) {
    console.error("FAIL: expected at least 1 pacing fix on a 24s graph with no interrupts");
    process.exit(1);
  }
  if (!eRes.patch) {
    console.error("FAIL: Editor did not emit a patch");
    process.exit(1);
  }
  const g2 = applyPatch(g1, eRes.patch);
  if (g2.hash === g1.hash) {
    console.error("FAIL: graph hash did not change after Editor patch");
    process.exit(1);
  }

  const eRes2 = await editor.run({ graph: g2 }, ectx);
  if (eRes2.output.animationFixes !== 0) {
    console.error(`FAIL: Editor not idempotent — animationFixes=${eRes2.output.animationFixes}`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
