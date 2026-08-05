/**
 * Sharder smoke (P0.2). Verifies:
 *   - Shards cover [0, durationMs) contiguously with no gaps/overlaps.
 *   - Every shard boundary lies on a scene-clip boundary.
 *   - Re-running planShards() yields identical hashes (determinism).
 *
 * Run: cd services/remotion && npx tsx scripts/sharder-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { DirectionV3 } from "../src/schemas/directionV3";
import { lower, planShards } from "../src/scene-graph";

const fixturePath = path.resolve(__dirname, "../src/scene-graph/__fixtures__/minimal-direction.json");
const raw = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

const seg = raw.segments[0];
const segments: typeof raw.segments = [];
for (let i = 0; i < 8; i++) {
  segments.push({
    ...seg,
    id: `s${i + 1}`,
    start_ms: i * 3000,
    duration_ms: 3000,
    scene_preset: i % 3 === 2 ? "StockFootageScene" : "HookOpener",
  });
}
raw.segments = segments;
raw.meta.duration_target_seconds = 24;

const direction = DirectionV3.parse(raw);
const graph = lower(direction);

const planA = planShards(graph, { targetShards: 4 });
const planB = planShards(graph, { targetShards: 4 });

const hashesA = planA.shards.map((s) => s.hash).join("|");
const hashesB = planB.shards.map((s) => s.hash).join("|");
if (hashesA !== hashesB) {
  console.error("FAIL: shard hashes not deterministic");
  process.exit(1);
}

let cursor = 0;
for (const shard of planA.shards) {
  if (shard.startMs !== cursor) {
    console.error(`FAIL: shard ${shard.index} starts at ${shard.startMs}, expected ${cursor}`);
    process.exit(1);
  }
  cursor = shard.endMs;
}
if (cursor !== graph.meta.durationMs) {
  console.error(`FAIL: coverage ends at ${cursor}, expected ${graph.meta.durationMs}`);
  process.exit(1);
}

const segBounds = new Set<number>();
for (const c of segments) {
  segBounds.add(c.start_ms);
  segBounds.add(c.start_ms + c.duration_ms);
}
for (const cut of planA.cutPointsMs) {
  if (!segBounds.has(cut)) {
    console.error(`FAIL: cut at ${cut}ms is not on any segment boundary`);
    process.exit(1);
  }
}

for (const s of planA.shards) {
  if (!Number.isInteger(s.startFrame) || !Number.isInteger(s.endFrame)) {
    console.error(`FAIL: non-integer frame on shard ${s.index}`);
    process.exit(1);
  }
}

for (const s of planA.shards) {
}
