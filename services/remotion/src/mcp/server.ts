/**
 * MCP HTTP server (P0.9).
 *
 * Minimal tool-dispatch surface. Each tool from `./tools.ts` is mounted at
 * `POST /tool/<name>` and at `GET /tool/<name>?json=<urlencoded>`. A list of
 * available tools is at `GET /tools`.
 *
 * Why HTTP and not stdio JSON-RPC: easy to test (curl, dashboard fetch,
 * external clients) without bringing in the official MCP SDK as a dep.
 * A stdio JSON-RPC adapter can wrap this in a follow-up.
 *
 * Run:
 *   MCP_PORT=4100 npm run mcp
 */

import express from "express";
import pinoHttp from "pino-http";
import { logger } from "../utils/logger";
import { TOOLS, type ToolName } from "./tools";

const PORT = Number(process.env.MCP_PORT ?? 4100);

const app = express();
app.use(express.json({ limit: "20mb" }));
app.use(pinoHttp({ logger }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", tools: Object.keys(TOOLS) });
});

app.get("/tools", (_req, res) => {
  res.json({
    tools: Object.keys(TOOLS).map((name) => ({
      name,
      endpoint: `/tool/${name}`,
      method: "POST",
    })),
  });
});

app.post("/tool/:name", async (req, res) => {
  const name = req.params.name as ToolName;
  const tool = TOOLS[name];
  if (!tool) {
    return res.status(404).json({ error: `unknown tool: ${name}`, knownTools: Object.keys(TOOLS) });
  }
  try {
    // Casting through unknown is the safest pattern across the heterogeneous
    // tool signatures; per-tool input shapes are validated inside the handler.
    const out = await (tool as (input: unknown) => Promise<unknown>)(req.body ?? {});
    return res.json(out);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logger.warn({ tool: name, err: message }, "tool invocation failed");
    return res.status(400).json({ error: message });
  }
});

if (require.main === module) {
  app.listen(PORT, () => {
    logger.info({ port: PORT, tools: Object.keys(TOOLS) }, "mcp tool server listening");
  });
}

export { app };
