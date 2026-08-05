import React from "react";
import { ShaderCanvas } from "./ShaderCanvas";

/**
 * VHS-era overlay: horizontal scanlines, subtle color bleed, vertical jitter
 * bands, and a warm magenta tint consistent with magnetic-tape artifacts.
 * Procedural — composites over the underlying scene via `screen` blend.
 */
export interface VHSProps {
  intensity?: number;
  tint?: [number, number, number];
}

const FRAG = `
uniform float u_intensity;
uniform vec3 u_tint;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec2 uv = v_uv;
  float scan = 0.5 + 0.5 * sin(uv.y * u_resolution.y * 3.14159);
  float scanMask = mix(1.0, scan, 0.35);

  float band = smoothstep(0.0, 0.02, sin(uv.y * 40.0 - u_time * 8.0)) *
               smoothstep(0.02, 0.0, sin(uv.y * 40.0 - u_time * 8.0) - 0.02);
  float bandShift = band * 0.6;

  float jitter = (hash(vec2(floor(uv.y * 120.0), floor(u_time * 30.0))) - 0.5) * 0.02;

  float n = hash(uv * u_resolution + u_time * 60.0) * 0.12;

  vec3 col = vec3(0.0);
  col.r = n * 1.1 + bandShift * 0.6;
  col.g = n * 0.8;
  col.b = n * 0.5 + bandShift * 0.3;
  col *= scanMask;
  col += vec3(0.06, 0.0, 0.04);

  float vig = smoothstep(1.1, 0.35, distance(uv, vec2(0.5)));
  col *= vig;

  col *= u_tint;
  out_color = vec4(col * u_intensity, u_intensity * 0.85);

  float _ = jitter + 0.0;
}
uniform float u_intensity;
uniform vec3 u_tint;
`;

export const VHS: React.FC<VHSProps> = ({
  intensity = 0.7,
  tint = [1.05, 0.95, 1.0],
}) => (
  <ShaderCanvas
    fragmentShader={FRAG}
    uniforms={{ u_intensity: intensity, u_tint: tint }}
    blendMode="screen"
  />
);
