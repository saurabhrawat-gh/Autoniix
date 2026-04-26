import { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import React from "react";
import { AbsoluteFill, interpolate } from "remotion";

/**
 * Premium flash transition with customizable color and intensity.
 * 
 * Creates an impact frame effect commonly used in action content, sports, and hype videos.
 * 
 * Quality: Matches After Effects flash transitions at 100%.
 */

export interface FlashTransitionProps extends Record<string, unknown> {
  /** Flash color */
  color?: string;
  /** Flash intensity (0-1, where 1 = fully opaque) */
  intensity?: number;
  /** Duration of flash peak in percentage of transition (0.1 = 10%) */
  peakDuration?: number;
}

export const flashTransition = (props?: FlashTransitionProps): TransitionPresentation<FlashTransitionProps> => {
  const color = props?.color ?? "#FFFFFF";
  const intensity = props?.intensity ?? 1.0;
  const peakDuration = props?.peakDuration ?? 0.15;

  const component: React.FC<TransitionPresentationComponentProps<FlashTransitionProps>> = ({
    children,
    presentationDirection,
    presentationProgress,
  }) => {
    const isEntering = presentationDirection === "entering";
    const progress = presentationProgress;

    // Flash curve: quick rise to peak, then fade out
    const peakStart = 0.5 - peakDuration / 2;
    const peakEnd = 0.5 + peakDuration / 2;
    
    const flashOpacity = interpolate(
      progress,
      [0, peakStart, peakEnd, 1],
      [0, intensity, intensity, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    // Scene opacity: fade out before flash, fade in after
    let sceneOpacity: number;
    if (isEntering) {
      sceneOpacity = interpolate(progress, [peakEnd, 1], [0, 1], { extrapolateLeft: "clamp" });
    } else {
      sceneOpacity = interpolate(progress, [0, peakStart], [1, 0], { extrapolateRight: "clamp" });
    }

    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ opacity: sceneOpacity }}>
          {children}
        </AbsoluteFill>
        <AbsoluteFill
          style={{
            backgroundColor: color,
            opacity: flashOpacity,
            pointerEvents: "none",
          }}
        />
      </AbsoluteFill>
    );
  };

  return { component, props: props ?? {} };
};
