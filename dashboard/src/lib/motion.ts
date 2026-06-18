/**
 * Design-system motion tokens — single source of truth.
 * Maps directly to docs/design-system.md §6 (Motion Tokens).
 *
 * Usage:
 *   import { ease, dur } from '@/lib/motion';
 *   transition={{ duration: dur.base, ease: ease.enter }}
 */

export const ease: Record<'standard' | 'enter' | 'exit' | 'emphasis', [number, number, number, number]> = {
  standard:  [0.2,  0,   0,   1],
  enter:     [0.12, 0,   0.1, 1],
  exit:      [0.33, 0,   0.2, 1],
  emphasis:  [0.16, 1,   0.3, 1],
};

export const dur = {
  instant:    0,
  fast:       0.12,
  base:       0.2,
  slow:       0.26,
  deliberate: 0.32,
} as const;

/** Spring physics presets for AI-native animations. */
export const spring = {
  /** KPI number count-up — smooth, weighty */
  kpi:    { stiffness: 80,  damping: 20 },
  /** Icon hover / badge pop — snappy, tight */
  snappy: { stiffness: 400, damping: 30 },
  /** Card entrance / drawer open — soft landing */
  soft:   { stiffness: 120, damping: 18 },
} as const;

/** Shorthand transition objects for the most common patterns. */
export const transition = {
  /** Hover/focus/active micro-states: fast + standard easing */
  micro: { duration: dur.fast, ease: ease.standard },
  /** Panel/overlay enter: base + enter easing */
  enter: { duration: dur.base, ease: ease.enter },
  /** Panel/overlay exit: base + exit easing */
  exit:  { duration: dur.base, ease: ease.exit },
  /** Drawer/sidebar slide: slow + enter easing */
  slide: { duration: dur.slow, ease: ease.enter },
  /** Emphasis pop (badge, tick, success flash): fast + emphasis */
  pop:   { duration: dur.fast, ease: ease.emphasis },
} as const;
