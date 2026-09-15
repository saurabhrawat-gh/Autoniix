import { Easing } from "remotion";

/**
 * Named easings used by animation/transition presets. Keep the enum string
 * values stable — they're referenced from the registry and from upstream JSON.
 */
export type EaseName = "linear" | "sine" | "power2" | "power3" | "bounce" | "elastic" | "back";

export const easings: Record<EaseName, (t: number) => number> = {
  linear: (t) => t,
  sine: Easing.inOut(Easing.sin),
  power2: Easing.bezier(0.4, 0, 0.2, 1),
  power3: Easing.bezier(0.25, 0.1, 0.25, 1),
  bounce: Easing.bounce,
  elastic: Easing.elastic(1.5),
  back: Easing.back(1.5),
};
