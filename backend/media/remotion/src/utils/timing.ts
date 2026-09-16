export const msToFrames = (ms: number, fps: number): number =>
  Math.max(1, Math.round((ms / 1000) * fps));

export const framesToMs = (frames: number, fps: number): number =>
  Math.round((frames / fps) * 1000);
