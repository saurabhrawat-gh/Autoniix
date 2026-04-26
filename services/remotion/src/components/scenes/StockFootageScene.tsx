import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type Fit = "cover" | "contain" | "fill";

export interface StockFootageSceneProps {
  src: string;
  startFrom?: number; // seconds into the source
  endAt?: number; // seconds into the source
  fit?: Fit;
  volume?: number;
  /** Simple Ken Burns — zooms from 1.0 to `kenBurnsTo` over the clip. */
  kenBurns?: boolean;
  kenBurnsTo?: number;
  bg?: string;
}

export const StockFootageScene: React.FC<StockFootageSceneProps> = ({
  src,
  startFrom,
  endAt,
  fit = "cover",
  volume = 0,
  kenBurns = false,
  kenBurnsTo = 1.08,
  bg = "#000",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = kenBurns
    ? interpolate(frame, [0, durationInFrames], [1, kenBurnsTo], {
        extrapolateRight: "clamp",
      })
    : 1;

  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <div style={{ width: "100%", height: "100%", transform: `scale(${scale})` }}>
        <OffthreadVideo
          src={src}
          startFrom={startFrom}
          endAt={endAt}
          volume={volume}
          style={{
            width: "100%",
            height: "100%",
            objectFit: fit,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
