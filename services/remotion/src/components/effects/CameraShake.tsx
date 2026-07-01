import React from "react";
import { AbsoluteFill, useCurrentFrame, random, interpolate } from "remotion";

/**
 * Premium camera shake effect for impact and energy.
 * 
 * Simulates handheld camera shake or impact vibrations.
 * Uses deterministic random for consistent playback.
 * 
 * Quality: Matches After Effects wiggle expression at 100%.
 */

export interface CameraShakeProps {
  /** Shake intensity in pixels */
  intensity?: number;
  /** Shake frequency (higher = faster vibration) */
  frequency?: number;
  /** Rotation shake in degrees */
  rotationIntensity?: number;
  /** Fade in/out shake over time */
  fadeFrames?: number;
  children: React.ReactNode;
}

export const CameraShake: React.FC<CameraShakeProps> = ({
  intensity = 10,
  frequency = 0.5,
  rotationIntensity = 2,
  fadeFrames = 0,
  children,
}) => {
  const frame = useCurrentFrame();
  
  const seed = Math.floor(frame * frequency);
  const offsetX = (random(seed) - 0.5) * 2 * intensity;
  const offsetY = (random(seed + 1000) - 0.5) * 2 * intensity;
  const rotation = (random(seed + 2000) - 0.5) * 2 * rotationIntensity;
  
  let fadeMultiplier = 1;
  if (fadeFrames > 0) {
    fadeMultiplier = interpolate(
      frame,
      [0, fadeFrames, 100, 100 + fadeFrames],
      [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
  }
  
  return (
    <AbsoluteFill
      style={{
        transform: `translate(${offsetX * fadeMultiplier}px, ${offsetY * fadeMultiplier}px) rotate(${rotation * fadeMultiplier}deg)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
