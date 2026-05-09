/**
 * Repair agent v1 (P0.7).
 *
 * Given a critic report and the current SceneGraph, propose a `Patch` that
 * targets ONLY the flagged shards. Bounded retry is enforced upstream — this
 * agent does not loop.
 *
 * Rule table (extends `repair_rules` table per docs/03-INTELLIGENCE-LAYER.md §3.3.4):
 *
 *   text_overflow   → setClipProps { fontSize: shrink by 0.85 } on caption clip
 *   black_flash     → insert 3-frame crossfade transition before flagged clip
 *   color_drift     → setGradePreset (re-apply Colorist baseline)
 *   asset_mismatch  → setClipProps { regenerate: true } — Editor will re-query asset service
 *   audio_drift     → setAudio { ducking.enabled: true } when not already on
 *   low_legibility  → setClipProps { textColorOverride: brand.text } + bump font weight
 *   stale_motion    → setClipProps { animationsIn: ["fadeIn"] } if currently empty
 *
 * Anything else falls through with `op: "noop"` (logged) — orchestrator
 * should escalate to human review or to the LLM-backed repair agent (P2).
 */

import type { Agent, AgentCtx, AgentResult } from "./types";
import type { CriticReport, FlagReason, FlaggedShard } from "./critic";
import type { Patch, PatchOp, SceneClip, SceneGraph } from "../scene-graph";
import { defaultBudget, nowIso } from "./types";

export interface RepairInput {
  graph: SceneGraph;
  report: CriticReport;
}

export interface RepairOutput {
  /** True iff at least one rule fired. False = nothing this agent can do. */
  applied: boolean;
  ops: PatchOp[];
  unhandled: FlaggedShard[];
}

const VERSION = "0.1.0";

export class RepairAgent implements Agent<RepairInput, RepairOutput> {
  readonly name = "repair";
  readonly version = VERSION;

  async run(input: RepairInput, _ctx: AgentCtx): Promise<AgentResult<RepairOutput>> {
    const startedAt = nowIso();
    const t0 = Date.now();
    const { graph, report } = input;

    // Index clips by id for fast lookup.
    const clipIndex = indexSceneClips(graph);

    const ops: PatchOp[] = [];
    const unhandled: FlaggedShard[] = [];

    for (const flag of report.shardsFlagged) {
      const op = ruleForFlag(flag, graph, clipIndex);
      if (op) {
        ops.push(op);
      } else {
        unhandled.push(flag);
      }
    }

    const applied = ops.length > 0;
    const patch: Patch | undefined = applied
      ? {
          agent: this.name,
          agentVersion: VERSION,
          ops,
          reason: `repair:${report.shardsFlagged.map((f) => f.reason).join("+")}`,
        }
      : undefined;

    return {
      output: { applied, ops, unhandled },
      ...(patch ? { patch } : {}),
      meta: {
        agent: this.name,
        agentVersion: VERSION,
        startedAt,
        finishedAt: nowIso(),
        latencyMs: Date.now() - t0,
        fallbackUsed: !applied,
      },
    };
  }
}

interface ClipIndexEntry {
  trackId: string;
  clip: SceneClip;
}

function indexSceneClips(graph: SceneGraph): Map<string, ClipIndexEntry> {
  const map = new Map<string, ClipIndexEntry>();
  for (const track of graph.tracks) {
    for (const clip of track.clips) {
      if (clip.kind === "scene") {
        map.set(clip.id, { trackId: track.id, clip });
      }
    }
  }
  return map;
}

function ruleForFlag(
  flag: FlaggedShard,
  graph: SceneGraph,
  clipIndex: Map<string, ClipIndexEntry>,
): PatchOp | null {
  const target = clipIndex.get(flag.shardId);

  switch (flag.reason satisfies FlagReason) {
    case "text_overflow":
      if (!target) return null;
      return {
        op: "setClipProps",
        trackId: target.trackId,
        clipId: target.clip.id,
        props: { ...(target.clip.sceneOverrides ?? {}), fontScale: 0.85 },
      };

    case "low_legibility":
      if (!target) return null;
      return {
        op: "setClipProps",
        trackId: target.trackId,
        clipId: target.clip.id,
        props: {
          ...(target.clip.sceneOverrides ?? {}),
          textColorOverride: graph.theme.textColor,
          fontWeight: 700,
        },
      };

    case "black_flash":
      if (!target) return null;
      return {
        op: "setClipProps",
        trackId: target.trackId,
        clipId: target.clip.id,
        props: {
          ...(target.clip.sceneOverrides ?? {}),
          // Renderer interprets this as "render a 3-frame crossfade in".
          repairCrossfadeInFrames: 3,
        },
      };

    case "color_drift":
      // Re-apply baseline grade preset.
      return { op: "setGradePreset", preset: graph.gradePreset };

    case "asset_mismatch":
      if (!target) return null;
      return {
        op: "setClipProps",
        trackId: target.trackId,
        clipId: target.clip.id,
        props: {
          ...(target.clip.sceneOverrides ?? {}),
          regenerate: true,
          regenReason: "asset_mismatch",
        },
      };

    case "audio_drift":
      if (graph.audio.ducking?.enabled) return null;
      return {
        op: "setAudio",
        audio: {
          ducking: {
            enabled: true,
            thresholdDb: graph.audio.ducking?.thresholdDb ?? -24,
            attackMs: graph.audio.ducking?.attackMs ?? 40,
            releaseMs: graph.audio.ducking?.releaseMs ?? 220,
          },
        },
      };

    case "stale_motion":
      if (!target) return null;
      if ((target.clip.animationsIn?.length ?? 0) > 0) return null;
      return {
        op: "setClipProps",
        trackId: target.trackId,
        clipId: target.clip.id,
        props: {
          ...(target.clip.sceneOverrides ?? {}),
          repairAnimationIn: "fadeIn",
        },
      };

    case "other":
      return null;
  }
}

export function makeRepair(): { agent: RepairAgent; defaultCtx: AgentCtx } {
  return {
    agent: new RepairAgent(),
    defaultCtx: {
      channelId: "default",
      niche: "general",
      seed: 0,
      attempt: 0,
      budget: defaultBudget(),
    },
  };
}
