import React from "react";
import { Audio, useVideoConfig } from "remotion";
import { dbToLinear } from "../../utils/audio";
import type { SrtCue } from "../../utils/srtParser";

export interface BackgroundMusicProps {
  src: string;
  volumeDb?: number;
  /** When set, music is ducked (attenuated) during these spoken cues. */
  duckCues?: SrtCue[];
  duckingDb?: number; // e.g. -12 → music drops 12 dB while VO plays
  fadeFrames?: number; // fade in/out around duck edges
  loop?: boolean;
}

export const BackgroundMusic: React.FC<BackgroundMusicProps> = ({
  src,
  volumeDb = -18,
  duckCues,
  duckingDb = -12,
  fadeFrames = 6,
  loop = true,
}) => {
  const { fps } = useVideoConfig();
  const base = dbToLinear(volumeDb);
  const ducked = dbToLinear(volumeDb + duckingDb);

  const volume = duckCues
    ? (frame: number): number => {
        const ms = (frame / fps) * 1000;
        const fadeMs = (fadeFrames / fps) * 1000;
        // find nearest cue and compute a smooth duck envelope
        let target = base;
        for (const c of duckCues) {
          if (ms >= c.startMs - fadeMs && ms <= c.endMs + fadeMs) {
            // inside attack/release window
            const t =
              ms < c.startMs
                ? (ms - (c.startMs - fadeMs)) / fadeMs // 0..1 fade-in
                : ms > c.endMs
                  ? 1 - (ms - c.endMs) / fadeMs // 1..0 fade-out
                  : 1;
            target = base + (ducked - base) * Math.max(0, Math.min(1, t));
            break;
          }
        }
        return target;
      }
    : base;

  return <Audio src={src} volume={volume} loop={loop} />;
};
