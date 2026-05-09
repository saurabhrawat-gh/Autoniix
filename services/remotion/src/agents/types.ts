/**
 * Shared agent contract (sections 03.2, 03.15 of the vision docs).
 *
 * Every agent is a stateless async function over `(input, ctx) → output`,
 * declares a cost budget, and emits a Patch (never mutates the SceneGraph
 * directly). The orchestrator commits patches atomically.
 */

import type { Patch, SceneGraph } from "../scene-graph";

export interface Budget {
  /** Max tokens (input+output combined) per agent invocation. */
  tokensPerCall: number;
  /** Max number of agent invocations per render job. */
  callsPerJob: number;
  /** Max wall time per call in milliseconds. */
  wallMsPerCall: number;
}

export interface AgentCtx {
  channelId: string;
  niche: string;
  /** Free-form per-channel preferences propagated from `brand_dna`. */
  brandDna?: Record<string, unknown>;
  /** Recent channel performance summary (CTR, retention curves, top patterns). */
  history?: Record<string, unknown>;
  budget: Budget;
  /** Random seed; agents that use stochastic sampling MUST seed from this. */
  seed: number;
  /** Logical clock — same job retries reuse the same logical seed. */
  attempt: number;
}

export interface AgentRunMeta {
  agent: string;
  agentVersion: string;
  startedAt: string;     // ISO
  finishedAt: string;    // ISO
  latencyMs: number;
  tokenInput?: number;
  tokenOutput?: number;
  costUsd?: number;
  fallbackUsed?: boolean;
}

export interface AgentResult<T> {
  output: T;
  patch?: Patch;
  meta: AgentRunMeta;
}

export interface Agent<I, O> {
  readonly name: string;
  readonly version: string;
  run(input: I, ctx: AgentCtx): Promise<AgentResult<O>>;
}

/** Convenience to type a critic-style agent that does not produce a patch. */
export type Critic<I, O> = Agent<I, O>;

/** Helper to build a default budget. */
export function defaultBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    tokensPerCall: 4_000,
    callsPerJob: 8,
    wallMsPerCall: 30_000,
    ...overrides,
  };
}

export function nowIso(): string {
  return new Date().toISOString();
}

/** Type guard helper for orchestrator to detect graphs vs lower payloads. */
export function isSceneGraph(v: unknown): v is SceneGraph {
  return !!v && typeof v === "object" && "version" in (v as object) && "tracks" in (v as object);
}
