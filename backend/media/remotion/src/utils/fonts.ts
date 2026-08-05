/**
 * Font loading — ensures fonts are available during headless Remotion render.
 *
 * Uses @remotion/google-fonts so fonts are embedded in the bundle
 * and don't depend on system-installed fonts.
 *
 * Call `loadFonts()` once at the module level (e.g., Root.tsx).
 */

import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadNotoSerif } from "@remotion/google-fonts/NotoSerif";

let loaded = false;

export function loadFonts(): void {
  if (loaded) return;
  loaded = true;

  const inter = loadInter();
  inter.fontFamily;

  const notoSerif = loadNotoSerif();
  notoSerif.fontFamily;
}

/**
 * Font family constants to use in components.
 * These match the loaded Google Fonts above.
 */
export const FONTS = {
  heading: "Inter, system-ui, sans-serif",
  body: "Inter, system-ui, sans-serif",
  serif: "'Noto Serif', Georgia, serif",
} as const;
