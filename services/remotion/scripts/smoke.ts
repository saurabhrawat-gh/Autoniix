/**
 * Phase 0 deliverable check: render a 5-second black video end-to-end.
 * Bypasses the queue for fast CI validation — calls the renderer directly.
 *
 * Usage: npm run smoke
 * Skips S3 upload if S3_ACCESS_KEY_ID is not set.
 */
import { runRender } from "../src/worker/renderer";
import { logger } from "../src/utils/logger";
import { env } from "../src/utils/env";

async function main() {
  if (!env.S3_ACCESS_KEY_ID) {
    logger.warn("S3 not configured — smoke test will fail at upload step. Set .env to complete.");
  }

  const result = await runRender(
    {
      renderId: "smoke_test",
      composition: "MainVideo",
      codec: "h264",
      outputFormat: "mp4",
      inputProps: {
        direction: {
          version: "3.0",
          meta: {
            video_id: "smoke",
            channel_id: "smoke",
            title: "Smoke",
            duration_target_seconds: 5,
            aspect: "16:9",
            fps: 30,
            resolution: { width: 1920, height: 1080 },
          },
          template: "hybrid-kinetic",
          theme: {
            primary_color: "#FF3B30",
            accent_color: "#FFD60A",
            background_color: "#000000",
            text_color: "#FFFFFF",
            fonts: { heading: "Inter", body: "Inter" },
          },
          grade_preset: "fx.grade.cinematic_teal_orange",
          segments: [
            {
              id: "s1",
              start_ms: 0,
              duration_ms: 5000,
              scene_preset: "scene.placeholder.black",
              scene_overrides: { label: "" },
            },
          ],
        },
      },
    },
    (p) => logger.info({ progress: p }, "render progress"),
  );

  logger.info({ result }, "smoke test complete");
}

main().catch((err) => {
  logger.error({ err }, "smoke test failed");
  process.exit(1);
});
