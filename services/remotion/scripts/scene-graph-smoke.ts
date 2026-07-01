/**
 * Smoke test for the SceneGraph IR (P0.1).
 *
 * Usage:  pnpm -F yt-automation-remotion tsx scripts/scene-graph-smoke.ts
 *         (or) cd services/remotion && npx tsx scripts/scene-graph-smoke.ts
 *
 * Checks:
 *   1. lower(directionV3) is deterministic (same bytes on repeated calls).
 *   2. Root hash is non-empty and changes when a segment prop changes.
 *   3. Capability tagger routes the stock-only clip to tier t2.
 *
 * Exits non-zero on any failure.
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import { lower, hashNode, tagCapabilities } from "../src/scene-graph";

const fixturePath = path.resolve(__dirname, "../src/scene-graph/__fixtures__/minimal-direction.json");
const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const direction = DirectionV3.parse(raw);

const g1 = lower(direction);
const g2 = lower(direction);

const h1 = hashNode(g1);
const h2 = hashNode(g2);

if (h1 !== h2) {
  console.error(`FAIL: determinism — h1=${h1} h2=${h2}`);
  process.exit(1);
}
if (h1 !== g1.hash) {
  console.error(`FAIL: root hash mismatch — hashNode=${h1} graph.hash=${g1.hash}`);
  process.exit(1);
}

const mutated = JSON.parse(JSON.stringify(raw));
mutated.segments[0].scene_overrides.headline = "A different headline";
const g3 = lower(DirectionV3.parse(mutated));
if (g3.hash === g1.hash) {
  console.error("FAIL: hash did not change after prop mutation");
  process.exit(1);
}

const caps = tagCapabilities(g1);
const s2 = caps.find((c) => c.clipId === "s2");
const s1 = caps.find((c) => c.clipId === "s1");
if (!s2 || s2.tier !== "t2") {
  console.error(`FAIL: expected s2 → t2, got ${s2?.tier}`);
  process.exit(1);
}
if (!s1 || s1.tier !== "t1") {
  console.error(`FAIL: expected s1 (HookOpener with effects) → t1, got ${s1?.tier}`);
  process.exit(1);
}

const video = g1.tracks.find((t) => t.kind === "video");
const overlay = g1.tracks.find((t) => t.kind === "overlay");
