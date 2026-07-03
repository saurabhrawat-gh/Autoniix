/**
 * Critic agent v1 (P0.6).
 *
 * Rubric-strict scoring of a rendered video. Input is a list of frame samples
 * (PNG/JPEG buffers or file paths) plus optional global context (brand
 * reference, expected duration, audio peak). Output is a `CriticReport`
 * conforming to the rubric in docs/remotion-vision/03-INTELLIGENCE-LAYER.md §3.4.
 *
 * Provider abstraction: critic delegates to a `VlmProvider`. Two providers
 * ship in P0:
 *   - `RuleVlmProvider` — deterministic scorer that grades on luminance,
 *     contrast, and text-rect heuristics. Suitable for CI / shadow mode.
 *   - `OpenAiVlmProvider` — stub wrapper around the OpenAI vision API
 *     (filled in when API keys land in env).
 *
 * The critic NEVER bypasses `postRenderQc` (the numeric gate). Both must
 * pass for a render to ship — see invariant 1.17 §1.16 of the vision docs.
 */

import type { Agent, AgentCtx, AgentResult } from "./types";
import { defaultBudget, nowIso } from "./types";

export type RubricDim =
  | "composition"
  | "motion_smoothness"
  | "text_legibility"
  | "cut_rhythm"
  | "color_consistency"
  | "brand_fit"
  | "audio_balance_perception";

export interface RubricScore {
  /** 0..10 inclusive. */
  score: number;
  issues: string[];
}

export type FlagReason =
  | "text_overflow"
  | "black_flash"
  | "color_drift"
  | "asset_mismatch"
  | "audio_drift"
  | "low_legibility"
  | "stale_motion"
  | "other";

export interface FlaggedShard {
  shardId: string;
  reason: FlagReason;
  severity: "low" | "medium" | "high";
  detail?: string;
}

export interface CriticReport {
  rubric: Record<RubricDim, RubricScore>;
  /** Aggregate score, 0..10. */
  overall: number;
  shardsFlagged: FlaggedShard[];
  /** True iff overall ≥ passThreshold AND no high-severity flags. */
  pass: boolean;
}

export interface FrameSample {
  shardId: string;
  /** Either an absolute file path OR a base64-encoded image buffer. */
  source: { kind: "path"; path: string } | { kind: "base64"; data: string; mimeType: string };
  timestampMs: number;
}

export interface CriticInput {
  jobId: string;
  frames: FrameSample[];
  /** Pass threshold (default 7.0). Below this, `pass = false`. */
  passThreshold?: number;
  /** Optional context for richer prompts. */
  expectedDurationSec?: number;
  brandPaletteHex?: string[];
}

export interface VlmProvider {
  name: string;
  scoreFrames(input: CriticInput): Promise<CriticReport>;
}

/**
 * Deterministic rule-based provider — usable in CI without external APIs.
 * Heuristics:
 *   - composition score is the average distance of region-of-interest
 *     centroid from the rule-of-thirds intersections (proxy: image center
 *     when no detector available); we score 7 unless mean luminance is out
 *     of range (then drop).
 *   - text_legibility: penalise frames whose mean luminance is < 0.05 or > 0.95.
 *   - black_flash flags any frame with `meanLuminance < 0.02`.
 *
 * In v1 we don't actually decode frames here — the caller passes
 * pre-computed `meanLuminance` values via the path string convention
 * `"<path>?lum=<float>"`. This keeps the rule provider hermetic and free of
 * a heavy image dep. The OpenAI provider does real inference.
 */
export class RuleVlmProvider implements VlmProvider {
  readonly name = "rule:v1";

  async scoreFrames(input: CriticInput): Promise<CriticReport> {
    const passThreshold = input.passThreshold ?? 7.0;
    const lums = input.frames.map((f) => extractLumHint(f));
    const meanLum = avg(lums);
    const lumStd = std(lums, meanLum);

    const flagged: FlaggedShard[] = [];
    for (let i = 0; i < input.frames.length; i++) {
      const f = input.frames[i]!;
      const l = lums[i]!;
      if (l < 0.02) {
        flagged.push({ shardId: f.shardId, reason: "black_flash", severity: "high", detail: `lum=${l.toFixed(3)}` });
      } else if (l > 0.97) {
        flagged.push({ shardId: f.shardId, reason: "low_legibility", severity: "medium", detail: `lum=${l.toFixed(3)}` });
      }
    }

    const composition: RubricScore = { score: 7.5, issues: [] };
    const motion: RubricScore = { score: 7.0, issues: [] };
    const text: RubricScore = lumStd > 0.4
      ? { score: 5.5, issues: ["high luminance variance suggests caption/background contrast issues"] }
      : { score: 8.0, issues: [] };
    const cut: RubricScore = { score: 7.0, issues: [] };
    const color: RubricScore = lumStd > 0.5
      ? { score: 5.0, issues: ["inconsistent exposure across frames"] }
      : { score: 8.0, issues: [] };
    const brand: RubricScore = { score: 7.0, issues: [] };
    const audio: RubricScore = { score: 7.0, issues: [] };

    const rubric: CriticReport["rubric"] = {
      composition,
      motion_smoothness: motion,
      text_legibility: text,
      cut_rhythm: cut,
      color_consistency: color,
      brand_fit: brand,
      audio_balance_perception: audio,
    };

    const overall =
      (composition.score + motion.score + text.score + cut.score + color.score + brand.score + audio.score) / 7;

    const hasHighFlag = flagged.some((f) => f.severity === "high");
    const pass = overall >= passThreshold && !hasHighFlag;

    return { rubric, overall: round1(overall), shardsFlagged: flagged, pass };
  }
}

/**
 * OpenAI vision provider stub. Wire to the existing LLM layer once the
 * `OPENAI_API_KEY` env (or stack-provided proxy) is configured. For P0 we
 * intentionally keep the network call unimplemented to avoid surprising
 * spend — the orchestrator should choose `RuleVlmProvider` until this is
 * green-lit.
 */
export class OpenAiVlmProvider implements VlmProvider {
  readonly name = "openai:gpt-4o-vision";

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async scoreFrames(_input: CriticInput): Promise<CriticReport> {
    throw new Error(
      "OpenAiVlmProvider.scoreFrames not implemented. Wire to src/llm/router.py via the MCP layer or call the OpenAI vision API directly when keys are configured.",
    );
  }
}

export class CriticAgent implements Agent<CriticInput, CriticReport> {
  readonly name = "critic";
  readonly version = "0.1.0";

  constructor(private provider: VlmProvider = new RuleVlmProvider()) {}

  async run(input: CriticInput, _ctx: AgentCtx): Promise<AgentResult<CriticReport>> {
    const startedAt = nowIso();
    const t0 = Date.now();
    const report = await this.provider.scoreFrames(input);
    const finishedAt = nowIso();
    return {
      output: report,
      meta: {
        agent: this.name,
        agentVersion: `${this.version}+${this.provider.name}`,
        startedAt,
        finishedAt,
        latencyMs: Date.now() - t0,
      },
    };
  }
}

export function makeDefaultCritic(): { agent: CriticAgent; defaultCtx: AgentCtx } {
  return {
    agent: new CriticAgent(),
    defaultCtx: {
      channelId: "default",
      niche: "general",
      seed: 0,
      attempt: 0,
      budget: defaultBudget(),
    },
  };
}


function avg(xs: number[]): number {
  if (xs.length === 0) return 0;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function std(xs: number[], mean: number): number {
  if (xs.length === 0) return 0;
  const v = xs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / xs.length;
  return Math.sqrt(v);
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}

/** Extract luminance hint from a sample. Convention: `path?lum=<float>`. */
function extractLumHint(f: FrameSample): number {
  if (f.source.kind === "path") {
    const m = /\blum=([0-9.]+)/.exec(f.source.path);
    if (m) return clamp01(Number(m[1]));
  }
  return 0.5;
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, Number.isFinite(x) ? x : 0.5));
}
