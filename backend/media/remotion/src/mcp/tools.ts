/**
 * MCP tool definitions (P0.9).
 *
 * Each tool is a typed (input → output) function. The HTTP server
 * (`src/mcp/server.ts`) dispatches POST /tool/<name> to these handlers; an
 * MCP stdio JSON-RPC adapter can be added on top later without touching this
 * file.
 *
 * Tool list (from docs/03-INTELLIGENCE-LAYER.md §3.12):
 *
 *   propose_scene        — draft a SceneGraph patch (not committed)
 *   render_preview       — enqueue a preview render of a graph patch
 *   query_registry       — list scenes/effects/transitions/luts
 *   get_qc_report        — fetch postRenderQc + critic report for a job
 *   list_channels        — list known channels (stub until brand store wired)
 *   get_retention_curve  — fetch per-channel retention summary (stub)
 *   run_bandit_sample    — pick an arm from the named cluster (stub)
 *
 * Stubs return well-typed placeholder data with `unimplemented: true` so
 * external agents can wire end-to-end against the schema today.
 */

import { DirectionV3 } from "../schemas/directionV3";
import { applyPatch, lower, type SceneGraph } from "../scene-graph";
import { DirectorAgent, EditorAgent } from "../agents";
import type { Patch } from "../scene-graph";

export interface ProposeSceneInput {
  /** A direction-v3 JSON OR an existing scene graph. */
  source: { kind: "directionV3"; direction: unknown } | { kind: "sceneGraph"; graph: SceneGraph };
  /** Which agent passes to run. */
  passes?: ("director" | "editor")[];
  /** Niche hint, used by Director. Default "general". */
  niche?: string;
}

export interface ProposeSceneOutput {
  graph: SceneGraph;
  patches: Patch[];
  appliedAgents: string[];
}

export async function proposeScene(input: ProposeSceneInput): Promise<ProposeSceneOutput> {
  let graph: SceneGraph;
  if (input.source.kind === "directionV3") {
    const parsed = DirectionV3.parse(input.source.direction);
    graph = lower(parsed);
  } else {
    graph = input.source.graph;
  }

  const passes = input.passes ?? ["director", "editor"];
  const ctx = {
    channelId: "mcp",
    niche: input.niche ?? "general",
    seed: 0,
    attempt: 0,
    budget: { tokensPerCall: 4000, callsPerJob: 8, wallMsPerCall: 30000 },
  };

  const patches: Patch[] = [];
  const appliedAgents: string[] = [];

  if (passes.includes("director")) {
    const r = await new DirectorAgent().run({ graph }, ctx);
    if (r.patch) {
      patches.push(r.patch);
      graph = applyPatch(graph, r.patch);
    }
    appliedAgents.push(r.meta.agentVersion);
  }
  if (passes.includes("editor")) {
    const r = await new EditorAgent().run({ graph }, ctx);
    if (r.patch) {
      patches.push(r.patch);
      graph = applyPatch(graph, r.patch);
    }
    appliedAgents.push(r.meta.agentVersion);
  }

  return { graph, patches, appliedAgents };
}

export interface RenderPreviewInput {
  graph: SceneGraph;
  /** Time window to preview. Default = first 5 sec of the graph. */
  rangeMs?: [number, number];
}

export interface RenderPreviewOutput {
  /** Stub: in P1 this returns a signed URL to a real MP4 preview. */
  status: "queued" | "unimplemented";
  previewUrl?: string;
  message: string;
}

export async function renderPreview(input: RenderPreviewInput): Promise<RenderPreviewOutput> {
  return {
    status: "unimplemented",
    message: `preview render of ${input.graph.meta.videoId} (${(input.rangeMs ?? [0, 5000]).join("..")}ms) not yet implemented`,
  };
}

export interface QueryRegistryInput {
  /** Filter by kind. Default returns all. */
  kind?: "scene" | "effect" | "transition" | "animation" | "overlay" | "lut" | "sfx";
  /** Filter by tag. */
  tag?: string;
  /** Limit (default 200). */
  limit?: number;
}

export interface RegistryEntry {
  id: string;
  kind: string;
  tags: string[];
  name?: string;
}

export interface QueryRegistryOutput {
  entries: RegistryEntry[];
}

export async function queryRegistry(input: QueryRegistryInput): Promise<QueryRegistryOutput> {
  const { listPresets } = await import("../registry");
  const limit = input.limit ?? 200;

  const baseFilter:
    { category?: "scene" | "effect" | "transition" | "animation" | "overlay" } | undefined =
    input.kind && input.kind !== "lut" && input.kind !== "sfx"
      ? { category: input.kind as "scene" | "effect" | "transition" | "animation" | "overlay" }
      : undefined;

  const presets = listPresets({
    ...(baseFilter ?? {}),
    ...(input.tag ? { tag: input.tag } : {}),
  });

  const entries: RegistryEntry[] = presets.slice(0, limit).map((p) => ({
    id: p.id,
    kind: p.category,
    tags: p.tags,
  }));

  if (!input.kind || input.kind === "lut") {
    const { lutLibrary } = await import("../registry/lutLibrary");
    for (const l of lutLibrary) {
      if (input.tag && !l.tags.includes(input.tag)) continue;
      if (entries.length >= limit) break;
      entries.push({ id: l.id, kind: "lut", tags: l.tags, name: l.name });
    }
  }
  if (!input.kind || input.kind === "sfx") {
    const { SFX_LIBRARY } = await import("../registry/sfxLibrary");
    for (const s of Object.values(SFX_LIBRARY)) {
      const tags = s.tags ?? [];
      if (input.tag && !tags.includes(input.tag)) continue;
      if (entries.length >= limit) break;
      entries.push({ id: s.id, kind: "sfx", tags, name: s.label });
    }
  }

  return { entries };
}

export interface GetQcReportInput {
  jobId: string;
}

export interface GetQcReportOutput {
  status: "found" | "not_found" | "unimplemented";
  jobId: string;
  qc?: unknown;
  critic?: unknown;
  message: string;
}

export async function getQcReport(input: GetQcReportInput): Promise<GetQcReportOutput> {
  return {
    status: "unimplemented",
    jobId: input.jobId,
    message: "QC report retrieval not yet wired; see P0.12 (DB migrations).",
  };
}

export interface ListChannelsOutput {
  status: "found" | "unimplemented";
  channels: { id: string; niche?: string; brand?: Record<string, unknown> }[];
  message: string;
}

export async function listChannels(): Promise<ListChannelsOutput> {
  return {
    status: "unimplemented",
    channels: [],
    message: "Wired through brand_dna service in P1; returning empty list as a stub.",
  };
}

export interface GetRetentionCurveInput {
  channelId: string;
  lastN?: number;
}

export interface GetRetentionCurveOutput {
  status: "found" | "unimplemented";
  channelId: string;
  curves: { videoId: string; retention: number[] }[];
  message: string;
}

export async function getRetentionCurve(
  input: GetRetentionCurveInput,
): Promise<GetRetentionCurveOutput> {
  return {
    status: "unimplemented",
    channelId: input.channelId,
    curves: [],
    message: "Wired to analytics/pattern_miner in P1.",
  };
}

export interface RunBanditSampleInput {
  /** Cluster name, e.g. "hook_style", "pacing", "transition_family". */
  cluster: string;
  /** Optional context: channelId, niche. */
  channelId?: string;
}

export interface RunBanditSampleOutput {
  cluster: string;
  arm: string;
  source: "default" | "bandit";
  message?: string;
}

const BANDIT_DEFAULTS: Record<string, string[]> = {
  hook_style: ["question", "shock", "stat", "story", "paradox"],
  pacing: ["fast", "medium", "slow", "dynamic"],
  transition_family: ["cuts_only", "zoom_punch", "whip", "flash", "mixed"],
  caption_style: ["word_karaoke", "line_fade", "full_screen", "side_bar"],
};

export async function runBanditSample(input: RunBanditSampleInput): Promise<RunBanditSampleOutput> {
  const arms = BANDIT_DEFAULTS[input.cluster];
  if (!arms || arms.length === 0) {
    return {
      cluster: input.cluster,
      arm: "default",
      source: "default",
      message: `unknown cluster ${input.cluster}; bandit table not yet seeded for this dimension`,
    };
  }
  return {
    cluster: input.cluster,
    arm: arms[0]!,
    source: "default",
    message: "bandit defaults — Thompson sampling lands in P1 with channel_style_priors",
  };
}

export const TOOLS = {
  propose_scene: proposeScene,
  render_preview: renderPreview,
  query_registry: queryRegistry,
  get_qc_report: getQcReport,
  list_channels: listChannels,
  get_retention_curve: getRetentionCurve,
  run_bandit_sample: runBanditSample,
} as const;

export type ToolName = keyof typeof TOOLS;
