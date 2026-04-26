import React, { useEffect, useRef } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Lightweight fragment-shader overlay host. Mounts a WebGL2 canvas sized to the
 * composition and renders a full-screen quad with a user-supplied fragment
 * shader. Intended for *procedural* overlay effects (VHS, CRT, glitch bands,
 * grain, light leaks) that composite over the scene via CSS blend modes.
 *
 * Why not post-process the scene itself? Remotion renders the scene as DOM
 * (not a texture), so the shader can't sample underlying pixels. Reading the
 * composition into a texture (via html2canvas or dom-to-image) is too slow for
 * per-frame use. For true post-process FX we'd do a two-pass pipeline in
 * Phase 4 (render scene → OffthreadVideo → shader pass).
 *
 * Built-in uniforms (set automatically):
 *   uniform float u_time;         // seconds since composition start
 *   uniform float u_frame;        // integer frame index
 *   uniform vec2  u_resolution;   // canvas size in px
 *   uniform vec2  u_texel;        // 1.0 / u_resolution
 */

export interface ShaderCanvasProps {
  fragmentShader: string;
  /** Extra custom uniforms; numbers or tuples of numbers (length 2–4). */
  uniforms?: Record<string, number | number[]>;
  /** CSS blend mode applied to the canvas over the underlying scene. */
  blendMode?: React.CSSProperties["mixBlendMode"];
  /** Opacity of the canvas (0..1). */
  opacity?: number;
}

const VERT = `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FRAG_HEADER = `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 out_color;
uniform float u_time;
uniform float u_frame;
uniform vec2 u_resolution;
uniform vec2 u_texel;
`;

function compileShader(gl: WebGL2RenderingContext, type: number, src: string): WebGLShader {
  const sh = gl.createShader(type);
  if (!sh) throw new Error("createShader failed");
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh) ?? "unknown";
    gl.deleteShader(sh);
    throw new Error(`shader compile: ${log}`);
  }
  return sh;
}

function buildProgram(gl: WebGL2RenderingContext, frag: string): WebGLProgram {
  const prog = gl.createProgram();
  if (!prog) throw new Error("createProgram failed");
  gl.attachShader(prog, compileShader(gl, gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, compileShader(gl, gl.FRAGMENT_SHADER, FRAG_HEADER + frag));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(prog) ?? "unknown";
    gl.deleteProgram(prog);
    throw new Error(`program link: ${log}`);
  }
  return prog;
}

export const ShaderCanvas: React.FC<ShaderCanvasProps> = ({
  fragmentShader,
  uniforms,
  blendMode,
  opacity = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const glRef = useRef<WebGL2RenderingContext | null>(null);

  // Compile on shader change
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const gl = c.getContext("webgl2", { premultipliedAlpha: true, antialias: false });
    if (!gl) return;
    glRef.current = gl;
    try {
      const prog = buildProgram(gl, fragmentShader);
      programRef.current = prog;
      gl.useProgram(prog);

      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
        gl.STATIC_DRAW,
      );
      const loc = gl.getAttribLocation(prog, "a_pos");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    } catch (err) {
      // Compile errors surfaced for Phase 3 author debugging; do not crash comp.
      // eslint-disable-next-line no-console
      console.error("[ShaderCanvas]", err);
    }
  }, [fragmentShader]);

  // Render every frame Remotion ticks
  useEffect(() => {
    const gl = glRef.current;
    const prog = programRef.current;
    const c = canvasRef.current;
    if (!gl || !prog || !c) return;

    gl.viewport(0, 0, c.width, c.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(prog);

    const t = frame / fps;
    const setU = (name: string, fn: (loc: WebGLUniformLocation) => void) => {
      const loc = gl.getUniformLocation(prog, name);
      if (loc) fn(loc);
    };
    setU("u_time", (loc) => gl.uniform1f(loc, t));
    setU("u_frame", (loc) => gl.uniform1f(loc, frame));
    setU("u_resolution", (loc) => gl.uniform2f(loc, c.width, c.height));
    setU("u_texel", (loc) => gl.uniform2f(loc, 1 / c.width, 1 / c.height));

    if (uniforms) {
      for (const [k, v] of Object.entries(uniforms)) {
        setU(k, (loc) => {
          if (typeof v === "number") gl.uniform1f(loc, v);
          else if (v.length === 2) gl.uniform2f(loc, v[0] ?? 0, v[1] ?? 0);
          else if (v.length === 3) gl.uniform3f(loc, v[0] ?? 0, v[1] ?? 0, v[2] ?? 0);
          else if (v.length === 4) gl.uniform4f(loc, v[0] ?? 0, v[1] ?? 0, v[2] ?? 0, v[3] ?? 0);
        });
      }
    }
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }, [frame, fps, uniforms]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: blendMode, opacity }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
    </AbsoluteFill>
  );
};
