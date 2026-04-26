import React from "react";
import { AbsoluteFill } from "remotion";
import { ShaderCanvas } from "./ShaderCanvas";

/**
 * CRT-era overlay: RGB phosphor mask, scanlines, and barrel-distortion vignette.
 * Composite with `multiply` blend to darken/tint the underlying scene, or pair
 * with a separate ColorGrade preset for richer CRT colour bias.
 */
export interface CRTProps {
  curvature?: number; // 0..1, barrel strength
  scanlineStrength?: number;
  phosphorStrength?: number;
}

const FRAG = `
uniform float u_curvature;
uniform float u_scan;
uniform float u_phosphor;

void main() {
  vec2 uv = v_uv;
  // Barrel distort
  vec2 cc = uv - 0.5;
  float r2 = dot(cc, cc);
  uv += cc * r2 * u_curvature;

  // Off-screen darken for wrapped UV
  float mask = step(0.0, uv.x) * step(uv.x, 1.0) *
               step(0.0, uv.y) * step(uv.y, 1.0);

  // Scanlines
  float scan = 0.5 + 0.5 * sin(uv.y * u_resolution.y * 3.14159);
  float scanMask = mix(1.0, scan, u_scan);

  // Phosphor triad: tint every 3 horizontal pixels R/G/B
  float pixX = floor(uv.x * u_resolution.x);
  float phase = mod(pixX, 3.0);
  vec3 phosphor = vec3(
    phase < 1.0 ? 1.0 : 0.3,
    (phase >= 1.0 && phase < 2.0) ? 1.0 : 0.3,
    phase >= 2.0 ? 1.0 : 0.3
  );
  phosphor = mix(vec3(1.0), phosphor, u_phosphor);

  // Combine: darken via scanlines × phosphor, plus vignette
  float vig = smoothstep(1.4, 0.4, distance(uv, vec2(0.5)));
  vec3 col = phosphor * scanMask * vig * mask;

  out_color = vec4(col, 1.0);
}
`;

export const CRT: React.FC<CRTProps> = ({
  curvature = 0.15,
  scanlineStrength = 0.5,
  phosphorStrength = 0.6,
}) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <ShaderCanvas
      fragmentShader={FRAG}
      uniforms={{
        u_curvature: curvature,
        u_scan: scanlineStrength,
        u_phosphor: phosphorStrength,
      }}
      blendMode="multiply"
    />
  </AbsoluteFill>
);
