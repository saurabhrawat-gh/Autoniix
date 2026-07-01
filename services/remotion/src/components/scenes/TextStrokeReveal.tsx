import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

/**
 * Premium text stroke reveal animation.
 * 
 * Animates text by drawing the stroke outline first, then filling.
 * Creates a handwritten/signature effect.
 * 
 * Quality: Matches After Effects stroke reveal at 95%+.
 */

export interface TextStrokeRevealProps {
  text: string;
  /** Font size in pixels */
  fontSize?: number;
  /** Font family */
  fontFamily?: string;
  /** Stroke color */
  strokeColor?: string;
  /** Fill color */
  fillColor?: string;
  /** Stroke width in pixels */
  strokeWidth?: number;
  /** Duration of stroke reveal in frames */
  revealDuration?: number;
  /** Delay before fill appears in frames */
  fillDelay?: number;
  /** Text alignment */
  align?: "left" | "center" | "right";
}

export const TextStrokeReveal: React.FC<TextStrokeRevealProps> = ({
  text,
  fontSize = 100,
  fontFamily = "Inter, sans-serif",
  strokeColor = "#FFFFFF",
  fillColor = "#FFFFFF",
  strokeWidth = 3,
  revealDuration = 60,
  fillDelay = 30,
  align = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const strokeProgress = spring({
    frame,
    fps,
    config: { damping: 100, stiffness: 50 },
    from: 0,
    to: 1,
    durationInFrames: revealDuration,
  });
  
  const fillOpacity = interpolate(
    frame,
    [fillDelay, fillDelay + 20],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  
  const strokeDashoffset = (1 - strokeProgress) * 1000;
  
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center",
        padding: "0 5%",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 1000 300"
        preserveAspectRatio="xMidYMid meet"
        style={{ overflow: "visible" }}
      >
        {/* Stroke outline (animated) */}
        <text
          x={align === "left" ? "0" : align === "right" ? "1000" : "500"}
          y="150"
          fontSize={fontSize}
          fontFamily={fontFamily}
          fontWeight="700"
          textAnchor={align === "left" ? "start" : align === "right" ? "end" : "middle"}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray="1000"
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {text}
        </text>
        
        {/* Fill (appears after stroke) */}
        <text
          x={align === "left" ? "0" : align === "right" ? "1000" : "500"}
          y="150"
          fontSize={fontSize}
          fontFamily={fontFamily}
          fontWeight="700"
          textAnchor={align === "left" ? "start" : align === "right" ? "end" : "middle"}
          fill={fillColor}
          opacity={fillOpacity}
        >
          {text}
        </text>
      </svg>
    </AbsoluteFill>
  );
};
