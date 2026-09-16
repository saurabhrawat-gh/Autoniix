import React from "react";
import { ShaderCanvas } from "./ShaderCanvas";

/**
 * Digital-glitch overlay: horizontal RGB-split bands, static-noise flashes,
 * and intermittent blocky displacements. Use `screen` blend to keep the
 * underlying scene visible, or `difference` for a harsher look.
 */
export interface GlitchProps {
  intensity?: number;
  bandCount?: number;
  /** Higher = glitches fire more often (Hz). */
  frequency?: number;
}

const FRAG = `
uniform float u_intensity;
uniform float u_bands;
uniform float u_freq;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash1(float n){ return fract(sin(n) * 43758.5453); }

void main() {
  vec2 uv = v_uv;
  float pulse = step(0.5, hash1(floor(u_time * u_freq)));

  float bandId = floor(uv.y * u_bands);
  float bandNoise = hash(vec2(bandId, floor(u_time * u_freq * 2.0)));
  float bandActive = step(0.75, bandNoise) * pulse;

  float shift = bandActive * (hash(vec2(bandId, u_time)) - 0.5) * 0.1;

  vec3 col = vec3(0.0);
  col.r = bandActive * (0.6 + 0.4 * hash(vec2(bandId, 1.0)));
  col.g = bandActive * (0.6 + 0.4 * hash(vec2(bandId, 2.0))) * 0.3;
  col.b = bandActive * (0.6 + 0.4 * hash(vec2(bandId, 3.0)));

  float pn = step(0.995, hash(uv * u_resolution + u_time));
  col += vec3(pn) * pulse * 0.8;

  out_color = vec4(col * u_intensity, (bandActive + pn * pulse) * u_intensity);
  float _ = shift;
}
`;

export const Glitch: React.FC<GlitchProps> = ({
  intensity = 0.7,
  bandCount = 40,
  frequency = 6,
}) => (
  <ShaderCanvas
    fragmentShader={FRAG}
    uniforms={{ u_intensity: intensity, u_bands: bandCount, u_freq: frequency }}
    blendMode="screen"
  />
);
