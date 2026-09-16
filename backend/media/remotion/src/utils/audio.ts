/** dB → linear gain (10^(dB/20)). 0 dB = 1.0, -6 dB ≈ 0.5. */
export const dbToLinear = (db: number): number => Math.pow(10, db / 20);

/** Simple envelope interpolation helper (0..1 at t). */
export const envelope = (
  value: number,
  target: number,
  attackMs: number,
  releaseMs: number,
  active: boolean,
  dtMs: number,
): number => {
  const tau = active ? attackMs : releaseMs;
  const alpha = 1 - Math.exp(-dtMs / Math.max(1, tau));
  return value + (target - value) * alpha;
};
