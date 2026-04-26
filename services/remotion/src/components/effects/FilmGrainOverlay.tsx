import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useVideoConfig } from "remotion";

/**
 * Real film grain overlay — composites a looping grain footage video
 * over the underlying scene via CSS blend modes.
 *
 * Unlike the procedural SVG `Grain.tsx`, this uses real scanned film grain
 * footage (e.g., from Envato or RocketStock) for authentic cinematic texture
 * matching Red Giant Universe "Retrograde" / Magic Bullet Looks quality.
 *
 * The grain video should be:
 *   - MP4/WebM, ideally 4K (3840×2160)
 *   - Black-and-white noise on black background
 *   - Loopable (seamless loop)
 *
 * Blend modes:
 *   - "overlay" — balanced (default, most cinematic)
 *   - "soft-light" — subtler, documentary feel
 *   - "screen" — lighter, vintage look
 *   - "multiply" — darker, grittier
 */
export interface FilmGrainOverlayProps {
  /** URL or path to grain footage (MP4/WebM). */
  src: string;
  /** CSS blend mode for compositing. */
  blendMode?: React.CSSProperties["mixBlendMode"];
  /** Overall opacity 0..1. Controls grain intensity. */
  opacity?: number;
  /** Scale factor for grain texture. 1 = native, >1 = zoom in (larger grain). */
  scale?: number;
  /** Playback rate. 1 = normal, 0.5 = slower grain, 2 = faster. */
  playbackRate?: number;
  /** Start time offset in seconds within the grain footage. */
  startFrom?: number;
  /** Duration of the grain clip in seconds (for correct looping). Defaults to 5. */
  loopDurationSec?: number;
  /** Optional tint color applied via CSS filter. */
  tint?: string;
  /** Mute the grain video audio (always true, grain has no meaningful audio). */
  muted?: boolean;
}

export const FilmGrainOverlay: React.FC<FilmGrainOverlayProps> = ({
  src,
  blendMode = "overlay",
  opacity = 0.35,
  scale = 1,
  playbackRate = 1,
  startFrom = 0,
  loopDurationSec = 5,
  tint,
  muted = true,
}) => {
  const { fps } = useVideoConfig();
  const startFromFrame = Math.round(startFrom * fps);
  const loopFrames = Math.max(1, Math.ceil((loopDurationSec / playbackRate) * fps));

  const filterStyle = tint ? `opacity(1) drop-shadow(0 0 0 ${tint})` : undefined;

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: blendMode,
        opacity,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: scale !== 1 ? `scale(${scale})` : undefined,
          transformOrigin: "center center",
          filter: filterStyle,
        }}
      >
        <Loop durationInFrames={loopFrames}>
          <OffthreadVideo
            src={src}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            muted={muted}
            playbackRate={playbackRate}
            startFrom={startFromFrame}
          />
        </Loop>
      </div>
    </AbsoluteFill>
  );
};
