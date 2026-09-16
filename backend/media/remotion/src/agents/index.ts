/**
 * Agents public surface (P0.6–P0.8).
 *
 * Per the vision docs, agents are pure functions over (input, ctx) → output
 * that may emit a `Patch` against the SceneGraph. The orchestrator commits
 * patches atomically and never lets an agent mutate the graph in-place.
 */

export type { Agent, AgentCtx, AgentResult, AgentRunMeta, Budget, Critic } from "./types";
export { defaultBudget, isSceneGraph, nowIso } from "./types";

export { CriticAgent, RuleVlmProvider, OpenAiVlmProvider, makeDefaultCritic } from "./critic";
export type {
  CriticInput,
  CriticReport,
  FlaggedShard,
  FlagReason,
  FrameSample,
  RubricDim,
  RubricScore,
  VlmProvider,
} from "./critic";

export { RepairAgent, makeRepair } from "./repair";
export type { RepairInput, RepairOutput } from "./repair";

export { DirectorAgent, makeDirector, pickPattern } from "./director";
export type { DirectorInput, DirectorOutput, StoryPattern } from "./director";

export { EditorAgent, makeEditor } from "./editor";
export type { EditorInput, EditorOutput } from "./editor";
