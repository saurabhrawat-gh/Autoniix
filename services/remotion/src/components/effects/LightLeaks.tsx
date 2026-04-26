import React from "react";
import { ShaderCanvas } from "./ShaderCanvas";

/**
 * Film-style light leak: warm coloured radial gradients animating across the
 * frame to simulate analog film bleed. Composites with `screen` blend to warm
 * highlights without crushing underlying detail.
 */
export interface LightLeaksProps {
  intensity?: number;
  color?: [number, number, number];
  /** Leak travel speed (cycles/sec across the frame). */
  speed?: number;
}

const FRAG = `
uniform float u_intensity;
uniform vec3  u_color;
uniform float u_speed;

void main() {
  vec2 uv = v_uv;
  float t = u_time * u_speed;

  // Two moving blobs
  vec2 a = vec2(0.5 + 0.45 * sin(t * 0.7), 0.5 + 0.3 * cos(t * 0.9));
  vec2 b = vec2(0.5 + 0.5 * cos(t * 0.5 + 2.0), 0.5 + 0.4 * sin(t * 0.6 + 1.2));

  float leakA = smoothstep(0.55, 0.0, distance(uv, a));
  float leakB = smoothstep(0.6, 0.0, distance(uv, b));
  float leak = leakA * 0.6 + leakB * 0.5;

  // Subtle banding
  float band = 0.9 + 0.1 * sin(uv.y * 60.0 + t * 10.0);

  vec3 col = u_color * leak * band * u_intensity;
  out_color = vec4(col, leak * u_intensity);
}
`;

export const LightLeaks: React.FC<LightLeaksProps> = ({
  intensity = 0.55,
  color = [1.0, 0.55, 0.25],
  speed = 0.25,
}) => (
  <ShaderCanvas
    fragmentShader={FRAG}
    uniforms={{ u_intensity: intensity, u_color: color, u_speed: speed }}
    blendMode="screen"
  />
);
