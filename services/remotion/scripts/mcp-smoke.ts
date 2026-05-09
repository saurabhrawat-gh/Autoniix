/**
 * MCP tools smoke (P0.9). Invokes each tool directly (no HTTP) to validate
 * input/output shapes without depending on a live server. The HTTP layer in
 * `src/mcp/server.ts` is a thin dispatch shim over the same handlers.
 *
 * Run: cd services/remotion && npx tsx scripts/mcp-smoke.ts
 */

import fs from "node:fs";
import path from "node:path";
import { TOOLS } from "../src/mcp/tools";

async function main() {
  const fixturePath = path.resolve(__dirname, "../src/scene-graph/__fixtures__/minimal-direction.json");
  const direction = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

  // 1. propose_scene
  const proposeOut = await TOOLS.propose_scene({
    source: { kind: "directionV3", direction },
    niche: "documentary",
  });
  if (!proposeOut.graph || !proposeOut.graph.hash) {
    console.error("FAIL: propose_scene returned no graph");
    process.exit(1);
  }
  if (proposeOut.appliedAgents.length === 0) {
    console.error("FAIL: propose_scene applied no agents");
    process.exit(1);
  }

  // 2. query_registry — scenes
  const regOut = await TOOLS.query_registry({ kind: "scene", limit: 5 });
  if (regOut.entries.length === 0) {
    console.error("FAIL: query_registry returned no scenes");
    process.exit(1);
  }

  // 3. run_bandit_sample
  const banditOut = await TOOLS.run_bandit_sample({ cluster: "hook_style" });
  if (!banditOut.arm) {
    console.error("FAIL: bandit returned no arm");
    process.exit(1);
  }
  const unknownArmOut = await TOOLS.run_bandit_sample({ cluster: "nonexistent" });
  if (unknownArmOut.source !== "default" || unknownArmOut.arm !== "default") {
    console.error("FAIL: unknown cluster should return default fallback");
    process.exit(1);
  }

  // 4. render_preview — must report unimplemented (P1)
  const previewOut = await TOOLS.render_preview({ graph: proposeOut.graph });
  if (previewOut.status !== "unimplemented") {
    console.error("FAIL: render_preview should be unimplemented at P0");
    process.exit(1);
  }

  // 5. get_qc_report, list_channels, get_retention_curve — return well-typed stubs
  const qcOut = await TOOLS.get_qc_report({ jobId: "j-test" });
  const chOut = await TOOLS.list_channels();
  const retOut = await TOOLS.get_retention_curve({ channelId: "c1" });
  for (const stub of [qcOut, chOut, retOut]) {
    if (stub.status !== "unimplemented") {
      console.error(`FAIL: stub ${JSON.stringify(stub)} should be unimplemented at P0`);
      process.exit(1);
    }
  }

  console.log("OK mcp tools smoke");
  console.log(`   propose_scene:        agents=[${proposeOut.appliedAgents.join(", ")}], hash=${proposeOut.graph.hash.slice(0, 12)}…`);
  console.log(`   query_registry:       ${regOut.entries.length} scenes  e.g. ${regOut.entries[0]?.id}`);
  console.log(`   run_bandit_sample:    cluster=hook_style → ${banditOut.arm}`);
  console.log(`   render_preview:       ${previewOut.status}`);
  console.log(`   stubs:                qc=${qcOut.status} channels=${chOut.status} retention=${retOut.status}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
