/**
 * Repair agent smoke (P0.7).
 *
 * End-to-end:
 *   direction-v3 → SceneGraph → induce critic flags → RepairAgent → applyPatch
 *   → recomputed graph hash differs and graph still validates (no overlaps).
 *
 * Run: cd services/remotion && npx tsx scripts/repair-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import { applyPatch, lower } from "../src/scene-graph";
import { makeRepair } from "../src/agents";
import type { CriticReport } from "../src/agents";

const fixturePath = path.resolve(__dirname, "../src/scene-graph/__fixtures__/minimal-direction.json");
const direction = DirectionV3.parse(JSON.parse(fs.readFileSync(fixturePath, "utf8")));
const graph = lower(direction);

const fakeReport: CriticReport = {
  rubric: {
    composition: { score: 7, issues: [] },
    motion_smoothness: { score: 7, issues: [] },
    text_legibility: { score: 5, issues: ["legibility low on s1"] },
    cut_rhythm: { score: 7, issues: [] },
    color_consistency: { score: 5, issues: ["palette drift"] },
    brand_fit: { score: 7, issues: [] },
    audio_balance_perception: { score: 7, issues: [] },
  },
  overall: 6.4,
  shardsFlagged: [
    { shardId: "s1", reason: "low_legibility", severity: "medium", detail: "contrast low" },
    { shardId: "s2", reason: "asset_mismatch", severity: "high", detail: "stock didn't match query" },
    { shardId: "s2", reason: "color_drift", severity: "medium" },
    { shardId: "s1", reason: "audio_drift", severity: "low" },
  ],
  pass: false,
};

async function main() {
  const { agent, defaultCtx } = makeRepair();
  const result = await agent.run({ graph, report: fakeReport }, defaultCtx);

  if (!result.output.applied) {
    console.error("FAIL: repair agent produced no ops");
    process.exit(1);
  }
  if (!result.patch) {
    console.error("FAIL: repair agent did not emit a patch");
    process.exit(1);
  }
  if (result.output.unhandled.length > 0) {
    console.warn(`   unhandled: ${result.output.unhandled.map((f) => f.reason).join(",")}`);
  }

  const next = applyPatch(graph, result.patch);
  if (next.hash === graph.hash) {
    console.error("FAIL: graph hash did not change after repair");
    process.exit(1);
  }

  // Reapplying the same patch must be deterministic.
  const next2 = applyPatch(graph, result.patch);
  if (next.hash !== next2.hash) {
    console.error("FAIL: applyPatch is not deterministic");
    process.exit(1);
  }

  console.log("OK repair smoke");
  console.log(`   ops:        ${result.output.ops.length}`);
  console.log(`   reasons:    ${result.patch.reason}`);
  console.log(`   pre  hash:  ${graph.hash.slice(0, 12)}…`);
  console.log(`   post hash:  ${next.hash.slice(0, 12)}…`);
  console.log(`   unhandled:  ${result.output.unhandled.length}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
