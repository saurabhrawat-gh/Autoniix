import { loadConfig } from "./config.js";
import { createApp } from "./app.js";

async function main() {
  const config = loadConfig();
  const app = await createApp(config);

  try {
    await app.listen({ port: config.port, host: "0.0.0.0" });
    app.log.info(`Gateway v2 listening on port ${config.port}`);
  } catch (error) {
    app.log.error(error);
    process.exit(1);
  }

  const shutdown = async (signal: string) => {
    app.log.info(`${signal} received, starting graceful shutdown`);
    await app.close();
    process.exit(0);
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

main();
