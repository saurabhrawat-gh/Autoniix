/**
 * Editor agent v1 (P0.8).
 *
 * Refines a SceneGraph after Director's pass. v1 responsibilities (rule-based):
 *
 *   1. PACING — for any contiguous gap > MAX_NO_INTERRUPT_MS on the video
 *      track without a "pattern interrupt", flag the longest scene in that
 *      gap to gain a `transitionOut` (zoom-punch) so the viewer gets a beat.
 *
 *   2. ANIMATION — every scene clip must have at least one `animations_in`.
 *      If empty, set a `fadeIn` on it. The final renderer interprets this.
 *
 *   3. CAPTION DENSITY — if the channel niche is "shorts" (passed via ctx),
 *      ensure each scene has `captionStyleHint` set on overrides; the
 *      Reframer (P1) reads this when projecting to 9:16.
 *
 * All edits emit PatchOps; the orchestrator commits via `applyPatch`. No LLM
 * calls in v1. Future versions (P1+) call the asset-rerank service via MCP.
 */

import type { Agent, AgentCtx, AgentResult } from "./types";
import type { Patch, PatchOp, SceneClip, SceneGraph } from "../scene-graph";
import { defaultBudget, nowIso } from "./types";

const VERSION = "0.1.0";
const MAX_NO_INTERRUPT_MS = 20_000;
const PATTERN_INTERRUPT_TRANSITIONS = new Set<string>([
  "zoomPunchIn",
  "whip",
  "flashCut",
  "glitch",
]);

export interface EditorInput {
  graph: SceneGraph;
}

export interface EditorOutput {
  /** Number of scene clips touched by pacing fixes. */
  pacingFixes: number;
  /** Number of scene clips that received an animation. */
  animationFixes: number;
  /** Number of clips that gained a caption-style hint (Shorts only). */
  captionFixes: number;
  ops: PatchOp[];
}

export class EditorAgent implements Agent<EditorInput, EditorOutput> {
  readonly name = "editor";
  readonly version = VERSION;

  async run(input: EditorInput, ctx: AgentCtx): Promise<AgentResult<EditorOutput>> {
    const startedAt = nowIso();
    const t0 = Date.now();

    const ops: PatchOp[] = [];
    const videoTrack = input.graph.tracks.find((t) => t.kind === "video");
    let pacingFixes = 0;
    let animationFixes = 0;
    let captionFixes = 0;

    if (videoTrack) {
      const working: SceneClip[] = (videoTrack.clips.filter((c) => c.kind === "scene") as SceneClip[]).map((c) => ({ ...c }));

      for (let i = 0; i < working.length; i++) {
        const clip = working[i]!;
        if ((clip.animationsIn?.length ?? 0) === 0) {
          const updated: SceneClip = { ...clip, animationsIn: [{ preset: "fadeIn" }] };
          working[i] = updated;
          ops.push({
            op: "replaceClip",
            trackId: videoTrack.id,
            clipId: clip.id,
            clip: updated,
          });
          animationFixes++;
        }
      }

      let runStartMs = working[0]?.range[0] ?? 0;
      let runIdx: number[] = [];
      const flushRun = () => {
        if (runIdx.length === 0) return;
        const lastIdx = runIdx[runIdx.length - 1]!;
        const runDuration = working[lastIdx]!.range[1] - runStartMs;
        if (runDuration > MAX_NO_INTERRUPT_MS) {
          const limit = runStartMs + MAX_NO_INTERRUPT_MS;
          const candidates = runIdx
            .map((i) => ({ i, c: working[i]! }))
            .filter(({ c }) => !c.transitionOut || !PATTERN_INTERRUPT_TRANSITIONS.has(c.transitionOut.preset));
          const fitting = candidates.filter(({ c }) => c.range[1] <= limit);
          const pick = (fitting.length > 0 ? fitting : candidates).reduce((a, b) =>
            Math.abs(a.c.range[1] - limit) <= Math.abs(b.c.range[1] - limit) ? a : b,
          );
          if (pick) {
            const updated: SceneClip = { ...pick.c, transitionOut: { preset: "zoomPunchIn" } };
            working[pick.i] = updated;
            ops.push({
              op: "replaceClip",
              trackId: videoTrack.id,
              clipId: pick.c.id,
              clip: updated,
            });
            pacingFixes++;
          }
        }
      };
      for (let i = 0; i < working.length; i++) {
        const clip = working[i]!;
        const hasInterrupt = clip.transitionOut && PATTERN_INTERRUPT_TRANSITIONS.has(clip.transitionOut.preset);
        runIdx.push(i);
        if (hasInterrupt) {
          flushRun();
          runStartMs = clip.range[1];
          runIdx = [];
        }
      }
      flushRun();

      if (ctx.niche.toLowerCase() === "shorts") {
        for (const clip of working) {
          const overrides = clip.sceneOverrides ?? {};
          if (overrides.captionStyleHint == null) {
            ops.push({
              op: "setClipProps",
              trackId: videoTrack.id,
              clipId: clip.id,
              props: { ...overrides, captionStyleHint: "word_karaoke" },
            });
            captionFixes++;
          }
        }
      }
    }

    const patch: Patch | undefined = ops.length > 0
      ? {
          agent: this.name,
          agentVersion: VERSION,
          ops,
          reason: `editor:p${pacingFixes}+a${animationFixes}+c${captionFixes}`,
        }
      : undefined;

    return {
      output: { pacingFixes, animationFixes, captionFixes, ops },
      ...(patch ? { patch } : {}),
      meta: {
        agent: this.name,
        agentVersion: VERSION,
        startedAt,
        finishedAt: nowIso(),
        latencyMs: Date.now() - t0,
      },
    };
  }
}

export function makeEditor(): { agent: EditorAgent; defaultCtx: AgentCtx } {
  return {
    agent: new EditorAgent(),
    defaultCtx: {
      channelId: "default",
      niche: "general",
      seed: 0,
      attempt: 0,
      budget: defaultBudget(),
    },
  };
}
