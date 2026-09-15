/**
 * Director agent v1 (P0.8).
 *
 * Plans the high-level narrative structure of a SceneGraph. v1 is rule-based
 * and deterministic — the LLM-backed Director lands in P1 once the
 * preference + bandit infra is wired.
 *
 * Responsibilities at v1:
 *   1. Ensure the first clip on the video track is a hook archetype. If the
 *      first scene_preset is not in HOOK_SCENES, propose replacing it with
 *      `HookOpener` while preserving its range and overrides keys.
 *   2. Tag the graph with a chosen story `pattern` per niche (consumed by
 *      Editor for pacing decisions). This is purely metadata — agents stay
 *      pure functions and write through patches.
 *
 * Niche → pattern table (extend with bandit weights in P1):
 *
 *   documentary    → doc_arc
 *   motivational   → problem_agitate_solution
 *   finance        → data_reveal
 *   educational    → concept_reveal
 *   explainer      → problem_agitate_solution
 *   news           → news_block
 *   *              → list_3_2_1
 */

import type { Agent, AgentCtx, AgentResult } from "./types";
import type { Patch, PatchOp, SceneClip, SceneGraph } from "../scene-graph";
import { defaultBudget, nowIso } from "./types";

const VERSION = "0.1.0";

const HOOK_SCENES = new Set<string>([
  "HookOpener",
  "FullScreenText",
  "AdvancedKineticText",
  "TextStrokeReveal",
]);

export type StoryPattern =
  | "doc_arc"
  | "problem_agitate_solution"
  | "data_reveal"
  | "concept_reveal"
  | "news_block"
  | "list_3_2_1"
  | "before_after"
  | "myth_bust";

export interface DirectorInput {
  graph: SceneGraph;
  /** Optional explicit override; otherwise derived from ctx.niche. */
  pattern?: StoryPattern;
}

export interface DirectorOutput {
  pattern: StoryPattern;
  changedHook: boolean;
  ops: PatchOp[];
}

export class DirectorAgent implements Agent<DirectorInput, DirectorOutput> {
  readonly name = "director";
  readonly version = VERSION;

  async run(input: DirectorInput, ctx: AgentCtx): Promise<AgentResult<DirectorOutput>> {
    const startedAt = nowIso();
    const t0 = Date.now();
    const { graph } = input;

    const pattern = input.pattern ?? pickPattern(ctx.niche);
    const ops: PatchOp[] = [];

    const videoTrack = graph.tracks.find((t) => t.kind === "video");
    let changedHook = false;
    if (videoTrack && videoTrack.clips.length > 0) {
      const first = videoTrack.clips[0]!;
      if (first.kind === "scene" && !HOOK_SCENES.has(first.scenePreset)) {
        const promoted: SceneClip = {
          ...first,
          scenePreset: "HookOpener",
          sceneOverrides: {
            ...(first.sceneOverrides ?? {}),
            promotedFrom: first.scenePreset,
            pattern,
          },
        };
        ops.push({
          op: "replaceClip",
          trackId: videoTrack.id,
          clipId: first.id,
          clip: promoted,
        });
        changedHook = true;
      }
    }

    const patch: Patch | undefined =
      ops.length > 0
        ? {
            agent: this.name,
            agentVersion: VERSION,
            ops,
            reason: `director:${pattern}${changedHook ? "+promoteHook" : ""}`,
          }
        : undefined;

    return {
      output: { pattern, changedHook, ops },
      ...(patch ? { patch } : {}),
      meta: {
        agent: this.name,
        agentVersion: VERSION,
        startedAt,
        finishedAt: nowIso(),
        latencyMs: Date.now() - t0,
        fallbackUsed: false,
      },
    };
  }
}

export function pickPattern(niche: string): StoryPattern {
  switch (niche.toLowerCase()) {
    case "documentary":
    case "history":
      return "doc_arc";
    case "motivational":
    case "motivation":
      return "problem_agitate_solution";
    case "finance":
    case "business":
      return "data_reveal";
    case "educational":
    case "education":
    case "edu":
      return "concept_reveal";
    case "explainer":
      return "problem_agitate_solution";
    case "news":
      return "news_block";
    case "myth":
    case "myth_bust":
      return "myth_bust";
    case "before_after":
      return "before_after";
    default:
      return "list_3_2_1";
  }
}

export function makeDirector(): { agent: DirectorAgent; defaultCtx: AgentCtx } {
  return {
    agent: new DirectorAgent(),
    defaultCtx: {
      channelId: "default",
      niche: "general",
      seed: 0,
      attempt: 0,
      budget: defaultBudget(),
    },
  };
}
