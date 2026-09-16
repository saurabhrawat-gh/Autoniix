import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { easings } from "../../utils/easing";

export interface BeforeAfterSliderProps {
  beforeUrl: string;
  afterUrl: string;
  beforeLabel?: string;
  afterLabel?: string;
  /** Sweep behaviour: "auto" animates the divider left→right, "static" stays at `position`. */
  mode?: "auto" | "static";
  position?: number;
  handleColor?: string;
}

export const BeforeAfterSlider: React.FC<BeforeAfterSliderProps> = ({
  beforeUrl,
  afterUrl,
  beforeLabel = "BEFORE",
  afterLabel = "AFTER",
  mode = "auto",
  position = 0.5,
  handleColor = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p =
    mode === "auto"
      ? easings.power2(
          interpolate(frame, [0, durationInFrames], [0.15, 0.85], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        )
      : position;

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Img
        src={afterUrl}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          width: `${p * 100}%`,
          overflow: "hidden",
        }}
      >
        <Img
          src={beforeUrl}
          style={{
            width: `${100 / p}vw`,
            height: "100%",
            objectFit: "cover",
          }}
        />
      </div>

      {/* Divider handle */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${p * 100}%`,
          width: 6,
          background: handleColor,
          boxShadow: "0 0 20px rgba(0,0,0,0.5)",
          transform: "translateX(-50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: `${p * 100}%`,
          transform: "translate(-50%, -50%)",
          width: 72,
          height: 72,
          borderRadius: "50%",
          background: handleColor,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#000",
          fontFamily: "Inter, sans-serif",
          fontWeight: 900,
          fontSize: 32,
        }}
      >
        ⇔
      </div>

      {/* Labels */}
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 60,
          padding: "12px 24px",
          background: "rgba(0,0,0,0.7)",
          color: "#fff",
          fontFamily: "Inter, sans-serif",
          fontWeight: 900,
          fontSize: 32,
          letterSpacing: 3,
        }}
      >
        {beforeLabel}
      </div>
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 60,
          padding: "12px 24px",
          background: "rgba(0,0,0,0.7)",
          color: "#fff",
          fontFamily: "Inter, sans-serif",
          fontWeight: 900,
          fontSize: 32,
          letterSpacing: 3,
        }}
      >
        {afterLabel}
      </div>
    </AbsoluteFill>
  );
};
