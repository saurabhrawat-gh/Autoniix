/**
 * Critic agent smoke (P0.6).
 *
 * Verifies:
 *   - A bright/normal-luminance frame strip → pass = true
 *   - A frame strip with a single near-black frame → pass = false (high-sev flag)
 *   - Determinism: same input → same overall score across runs
 *
 * Run: cd services/remotion && npx tsx scripts/critic-smoke.ts
 */

import { CriticAgent, makeDefaultCritic, type FrameSample } from "../src/agents";

function mkFrame(shardId: string, lum: number, atMs: number): FrameSample {
  return {
    shardId,
    source: { kind: "path", path: `/tmp/${shardId}.png?lum=${lum}` },
    timestampMs: atMs,
  };
}

async function main() {
  const { agent, defaultCtx } = makeDefaultCritic();

  const goodFrames: FrameSample[] = [
    mkFrame("s0", 0.45, 0),
    mkFrame("s0", 0.5, 1000),
    mkFrame("s1", 0.55, 2000),
    mkFrame("s1", 0.48, 3000),
  ];
  const r1 = await agent.run({ jobId: "j1", frames: goodFrames }, defaultCtx);
  if (!r1.output.pass) {
    console.error("FAIL: expected good frames to pass");
    console.error(JSON.stringify(r1.output, null, 2));
    process.exit(1);
  }

  const badFrames: FrameSample[] = [
    mkFrame("s0", 0.45, 0),
    mkFrame("s1", 0.005, 1000),
    mkFrame("s1", 0.5, 2000),
  ];
  const r2 = await agent.run({ jobId: "j2", frames: badFrames }, defaultCtx);
  if (r2.output.pass) {
    console.error("FAIL: expected black-flash frames to FAIL");
    process.exit(1);
  }
  if (!r2.output.shardsFlagged.some((f) => f.reason === "black_flash" && f.severity === "high")) {
    console.error("FAIL: expected high-severity black_flash flag");
    console.error(JSON.stringify(r2.output, null, 2));
    process.exit(1);
  }

  const r3 = await new CriticAgent().run({ jobId: "j1", frames: goodFrames }, defaultCtx);
  if (r3.output.overall !== r1.output.overall) {
    console.error(`FAIL: non-deterministic overall (${r1.output.overall} vs ${r3.output.overall})`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
