import type { TransitionPresentation, TransitionTiming } from "@remotion/transitions";

/**
 * Factory output shape accepted by <TransitionSeries.Transition/>. We use
 * `TransitionPresentation<any>` here because presenter prop shapes vary per
 * preset — TransitionSeries consumes them uniformly at runtime.
 */
export interface TransitionPresetEntry {
  id: string;
  build: (overrides?: Record<string, unknown>) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    presentation: TransitionPresentation<any>;
    timing: TransitionTiming;
  };
  category: "transition";
  tags: string[];
}

export type TransitionRegistry = Record<string, TransitionPresetEntry>;
