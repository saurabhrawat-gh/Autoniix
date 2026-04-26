import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from "remotion";
import { PremiumFilmGrain } from "../components/effects/PremiumFilmGrain";
import { AdvancedParticleSystem } from "../components/effects/AdvancedParticleSystem";

/**
 * Demo composition showcasing 100% quality premium effects
 */
export const PremiumEffectsDemo: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background gradient */}
      <AbsoluteFill
        style={{
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          opacity,
        }}
      />

      {/* Advanced Particle System - Energy preset */}
      <Sequence from={0}>
        <AdvancedParticleSystem
          preset="energy"
          count={1000}
          glow={1}
          trails={0.7}
          depth3D={0.8}
        />
      </Sequence>

      {/* Premium Film Grain - 35mm */}
      <Sequence from={0}>
        <PremiumFilmGrain
          filmStock="35mm"
          intensity={0.15}
          grainSize={1}
          colorGrain={0.3}
          opacity={0.5}
        />
      </Sequence>

      {/* Title */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          opacity,
        }}
      >
        <h1
          style={{
            fontSize: 120,
            fontWeight: 900,
            color: "#fff",
            textShadow: "0 0 40px rgba(255,255,255,0.5)",
            fontFamily: "Arial, sans-serif",
          }}
        >
          100% QUALITY
        </h1>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
