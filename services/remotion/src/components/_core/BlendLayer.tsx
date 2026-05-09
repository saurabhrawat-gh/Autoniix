/**
 * Phase 1A — `<BlendLayer>` renderer wrapper.
 *
 * Wraps any child layer with CSS `mix-blend-mode` + `opacity` derived from the
 * scene-graph `Compositing` value carried on the clip.
 *
 * Scope:
 *   - 14 CSS-supported blend modes use the fast path (no extra GPU work).
 *   - `add` and `subtract` fall back to documented approximations (`screen` and
 *     `difference` respectively) and log a one-time dev-only warning. A true
 *     additive composite is on the Tier-0 (WebGPU) roadmap; this wrapper is the
 *     contract surface, not the final pixel-perfect implementation.
 *
 * The wrapper is intentionally a no-op when `compositing` is undefined — every
 * existing render path stays bit-identical until clips opt in.
 */

import React from "react";
import {
  effectiveBlendMode,
  effectiveOpacity,
  cssBlendMode,
  requiresShader,
} from "../../scene-graph/compositing";
import type { Compositing } from "../../scene-graph/types";

export interface BlendLayerProps {
  /** May be `undefined` — the wrapper becomes a transparent passthrough. */
  compositing?: Compositing;
  /** For diagnostics + the one-time-warn map. */
  clipId?: string;
  /** Forwarded to the wrapping element. */
  className?: string;
  /** Inline style merged with the computed mix-blend-mode + opacity. */
  style?: React.CSSProperties;
  children: React.ReactNode;
}

/* ---- Dev-only warn-once for shader-path modes ------------------------- */
const _warned = new Set<string>();
function warnOnce(key: string, message: string): void {
  if (process.env.NODE_ENV === "production") return;
  if (_warned.has(key)) return;
  _warned.add(key);
  // eslint-disable-next-line no-console
  console.warn(`[BlendLayer] ${message}`);
}

/**
 * For `add`/`subtract` we emit a CSS approximation today. The mapping is
 * deliberate and documented:
 *   add      → screen     (lighten composite, close to additive on dark bg)
 *   subtract → difference (darken composite, close to subtractive on dark bg)
 */
function fallbackCssBlendMode(mode: "add" | "subtract"): string {
  return mode === "add" ? "screen" : "difference";
}

export const BlendLayer: React.FC<BlendLayerProps> = ({
  compositing,
  clipId,
  className,
  style,
  children,
}) => {
  // No compositing value → bit-identical to a plain wrapper.
  if (!compositing) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    );
  }

  const mode = effectiveBlendMode(compositing);
  const opacity = effectiveOpacity(compositing);

  let mixBlendMode = cssBlendMode(mode);
  if (mixBlendMode === null) {
    if (requiresShader(mode)) {
      warnOnce(
        `shader-fallback:${mode}`,
        `blendMode "${mode}" requires the WebGPU compositor (clip=${clipId ?? "?"}). ` +
          `Falling back to CSS approximation. Track the proper path in services/remotion/src/components/_core/BlendLayer.tsx.`,
      );
      mixBlendMode = fallbackCssBlendMode(mode as "add" | "subtract");
    } else {
      mixBlendMode = "normal";
    }
  }

  return (
    <div
      className={className}
      data-blend-mode={mode}
      data-clip-id={clipId}
      style={{
        ...style,
        mixBlendMode: mixBlendMode as React.CSSProperties["mixBlendMode"],
        opacity,
      }}
    >
      {children}
    </div>
  );
};
