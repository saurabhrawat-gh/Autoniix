/* Shared pipeline vocabulary. Colours map onto the dashboard status palette so
 * marketing visuals read the same as the real product's phase stepper. */
export const C = {
  cream: "#fcffe1",
  violet: "#8a56ff",
  pink: "#ff6fb5",
  success: "#5a8c3a",
  warning: "#c48a2a",
  error: "#dc5a3a",
  info: "#5a7acc",
  text: "#edefd8",
  muted: "#8c9080",
} as const;

export type Stage = { id: string; label: string; model: string; color: string; verb: string };

export const STAGES: Stage[] = [
  { id: "research", label: "Research", model: "Gemini 2.5 Flash", color: C.info, verb: "Researching" },
  { id: "script", label: "Script", model: "Claude Sonnet", color: C.violet, verb: "Scripting" },
  { id: "voice", label: "Voice", model: "Fish Audio", color: C.pink, verb: "Synthesising voice" },
  { id: "render", label: "Render", model: "Remotion + FFmpeg", color: C.warning, verb: "Rendering" },
  { id: "publish", label: "Publish", model: "YouTube Data API", color: C.success, verb: "Publishing" },
];

export const JOBS = [
  {
    title: "How compound interest really works",
    channel: "Money Simplified",
    format: "Long-form",
    stage: 3,
    progress: 78,
  },
  { title: "Sleep cycles decoded — the science", channel: "Health Lab", format: "Short", stage: 2, progress: 52 },
  { title: "Gut microbiome — beginner guide", channel: "Health Lab", format: "Long-form", stage: 1, progress: 23 },
  { title: "Why index funds beat hedge funds", channel: "Money Simplified", format: "Short", stage: 0, progress: 8 },
  { title: "HIIT vs steady-state cardio", channel: "Fit in 5", format: "Short", stage: 4, progress: 97 },
  { title: "The psychology of money", channel: "Money Simplified", format: "Long-form", stage: 3, progress: 64 },
  { title: "Cold exposure — full protocol", channel: "Health Lab", format: "Long-form", stage: 1, progress: 31 },
];
