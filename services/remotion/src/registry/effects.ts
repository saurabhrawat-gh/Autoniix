import { ColorGrade } from "../components/effects/ColorGrade";
import { Vignette } from "../components/effects/Vignette";
import { Grain } from "../components/effects/Grain";
import { Letterbox } from "../components/effects/Letterbox";
import { ChromaticAberration } from "../components/effects/ChromaticAberration";
import { Bloom } from "../components/effects/Bloom";
import { TiltShift } from "../components/effects/TiltShift";
import { MotionBlur } from "../components/effects/MotionBlur";
import { Duotone } from "../components/effects/Duotone";
import { FrameBorder } from "../components/effects/FrameBorder";
import { Glow } from "../components/effects/Glow";
import { VHS } from "../components/effects/VHS";
import { CRT } from "../components/effects/CRT";
import { Glitch } from "../components/effects/Glitch";
import { LightLeaks } from "../components/effects/LightLeaks";
import { Scanlines } from "../components/effects/Scanlines";
import { FilmGrainOverlay } from "../components/effects/FilmGrainOverlay";
import { LUTGrade } from "../components/effects/LUTGrade";
import { LUTGradeWebGL } from "../components/effects/LUTGradeWebGL";
import { ParticleSystem } from "../components/effects/ParticleSystem";
import { CameraShake } from "../components/effects/CameraShake";
import { GlitchEffect } from "../components/effects/GlitchEffect";
import { DepthOfField } from "../components/effects/DepthOfField";
import { PremiumFilmGrain } from "../components/effects/PremiumFilmGrain";
import { AdvancedParticleSystem } from "../components/effects/AdvancedParticleSystem";
import { LiquidMorph } from "../components/effects/LiquidMorph";
import { AdvancedShapes } from "../components/effects/AdvancedShapes";
import { PremiumMasks } from "../components/effects/PremiumMasks";
import { staticFile } from "remotion";
import type { PresetRegistry } from "./types";

/** Phase 1: 4 components → 10 presets (5 grade LUTs + 2 vignette + 2 grain + 1 letterbox). */
export const EFFECT_PRESETS: PresetRegistry = {
  "fx.grade.natural_cinematic": {
    id: "fx.grade.natural_cinematic",
    component: ColorGrade,
    defaultProps: { lut: "natural_cinematic" },
    category: "effect",
    tags: ["grade", "cinematic"],
  },
  "fx.grade.cinematic_teal_orange": {
    id: "fx.grade.cinematic_teal_orange",
    component: ColorGrade,
    defaultProps: { lut: "cinematic_teal_orange" },
    category: "effect",
    tags: ["grade", "cinematic", "teal-orange"],
  },
  "fx.grade.bright_flat": {
    id: "fx.grade.bright_flat",
    component: ColorGrade,
    defaultProps: { lut: "bright_flat" },
    category: "effect",
    tags: ["grade", "flat", "2d"],
  },
  "fx.grade.moody_cool": {
    id: "fx.grade.moody_cool",
    component: ColorGrade,
    defaultProps: { lut: "moody_cool" },
    category: "effect",
    tags: ["grade", "moody"],
  },
  "fx.grade.noir_bw": {
    id: "fx.grade.noir_bw",
    component: ColorGrade,
    defaultProps: { lut: "noir_bw" },
    category: "effect",
    tags: ["grade", "bw"],
  },

  "fx.vignette.soft": {
    id: "fx.vignette.soft",
    component: Vignette,
    defaultProps: { intensity: 0.45, radius: 0.6 },
    category: "effect",
    tags: ["vignette", "overlay"],
  },
  "fx.vignette.hard": {
    id: "fx.vignette.hard",
    component: Vignette,
    defaultProps: { intensity: 0.75, radius: 0.45 },
    category: "effect",
    tags: ["vignette", "overlay"],
  },

  "fx.grain.film_35mm": {
    id: "fx.grain.film_35mm",
    component: Grain,
    defaultProps: { intensity: 0.08, scale: 0.9 },
    category: "effect",
    tags: ["grain", "overlay", "film"],
  },
  "fx.grain.super8": {
    id: "fx.grain.super8",
    component: Grain,
    defaultProps: { intensity: 0.15, scale: 1.3 },
    category: "effect",
    tags: ["grain", "overlay", "super8"],
  },

  "fx.letterbox.cinematic_235": {
    id: "fx.letterbox.cinematic_235",
    component: Letterbox,
    defaultProps: { aspect: 2.35, color: "#000" },
    category: "effect",
    tags: ["letterbox", "cinematic"],
  },

  // Phase 2: extra LUTs
  "fx.grade.warm_sunset": {
    id: "fx.grade.warm_sunset", component: ColorGrade,
    defaultProps: { lut: "warm_sunset" }, category: "effect", tags: ["grade", "warm"],
  },
  "fx.grade.cold_winter": {
    id: "fx.grade.cold_winter", component: ColorGrade,
    defaultProps: { lut: "cold_winter" }, category: "effect", tags: ["grade", "cold"],
  },
  "fx.grade.vintage_faded": {
    id: "fx.grade.vintage_faded", component: ColorGrade,
    defaultProps: { lut: "vintage_faded" }, category: "effect", tags: ["grade", "vintage"],
  },
  "fx.grade.neon_night": {
    id: "fx.grade.neon_night", component: ColorGrade,
    defaultProps: { lut: "neon_night" }, category: "effect", tags: ["grade", "neon"],
  },
  "fx.grade.high_key_commercial": {
    id: "fx.grade.high_key_commercial", component: ColorGrade,
    defaultProps: { lut: "high_key_commercial" }, category: "effect", tags: ["grade", "commercial"],
  },
  "fx.grade.matrix_green": {
    id: "fx.grade.matrix_green", component: ColorGrade,
    defaultProps: { lut: "matrix_green" }, category: "effect", tags: ["grade", "tech"],
  },
  "fx.grade.pastel_soft": {
    id: "fx.grade.pastel_soft", component: ColorGrade,
    defaultProps: { lut: "pastel_soft" }, category: "effect", tags: ["grade", "soft"],
  },
  "fx.grade.hdr_pop": {
    id: "fx.grade.hdr_pop", component: ColorGrade,
    defaultProps: { lut: "hdr_pop" }, category: "effect", tags: ["grade", "pop"],
  },
  "fx.grade.sepia_doc": {
    id: "fx.grade.sepia_doc", component: ColorGrade,
    defaultProps: { lut: "sepia_doc" }, category: "effect", tags: ["grade", "sepia", "doc"],
  },
  "fx.grade.cyberpunk_magenta": {
    id: "fx.grade.cyberpunk_magenta", component: ColorGrade,
    defaultProps: { lut: "cyberpunk_magenta" }, category: "effect", tags: ["grade", "cyberpunk"],
  },

  // Phase 2: ChromaticAberration
  "fx.chromab.subtle": {
    id: "fx.chromab.subtle", component: ChromaticAberration,
    defaultProps: { strengthPx: 2 }, category: "effect", tags: ["chromab", "stylized"],
  },
  "fx.chromab.strong": {
    id: "fx.chromab.strong", component: ChromaticAberration,
    defaultProps: { strengthPx: 6 }, category: "effect", tags: ["chromab", "glitch"],
  },

  // Phase 2: Bloom
  "fx.bloom.soft": {
    id: "fx.bloom.soft", component: Bloom,
    defaultProps: { intensity: 0.35, blurPx: 24 }, category: "effect", tags: ["bloom"],
  },
  "fx.bloom.dreamy": {
    id: "fx.bloom.dreamy", component: Bloom,
    defaultProps: { intensity: 0.7, blurPx: 40 }, category: "effect", tags: ["bloom", "dreamy"],
  },

  // Phase 2: TiltShift
  "fx.tiltshift.miniature": {
    id: "fx.tiltshift.miniature", component: TiltShift,
    defaultProps: { blurPx: 18, focusHeightPct: 28 }, category: "effect", tags: ["tiltshift"],
  },

  // Phase 2: MotionBlur
  "fx.motionblur.horizontal": {
    id: "fx.motionblur.horizontal", component: MotionBlur,
    defaultProps: { axis: "x", amount: 10 }, category: "effect", tags: ["motionblur"],
  },
  "fx.motionblur.vertical": {
    id: "fx.motionblur.vertical", component: MotionBlur,
    defaultProps: { axis: "y", amount: 10 }, category: "effect", tags: ["motionblur"],
  },

  // Phase 2: Duotone
  "fx.duotone.red_navy": {
    id: "fx.duotone.red_navy", component: Duotone,
    defaultProps: { shadow: "#1b1e3f", highlight: "#ff3b30" }, category: "effect", tags: ["duotone"],
  },
  "fx.duotone.purple_yellow": {
    id: "fx.duotone.purple_yellow", component: Duotone,
    defaultProps: { shadow: "#2a0a4a", highlight: "#ffd60a" }, category: "effect", tags: ["duotone"],
  },
  "fx.duotone.teal_orange": {
    id: "fx.duotone.teal_orange", component: Duotone,
    defaultProps: { shadow: "#0e2a38", highlight: "#ff9a3c" }, category: "effect", tags: ["duotone"],
  },

  // Phase 2: FrameBorder
  "fx.frame.thin_white": {
    id: "fx.frame.thin_white", component: FrameBorder,
    defaultProps: { color: "#FFFFFF", widthPx: 4, inset: 36 }, category: "effect", tags: ["frame"],
  },
  "fx.frame.polaroid": {
    id: "fx.frame.polaroid", component: FrameBorder,
    defaultProps: { color: "#FFFFFF", widthPx: 24, inset: 80, shadow: true }, category: "effect",
    tags: ["frame", "polaroid"],
  },

  // Phase 2: Glow
  "fx.glow.yellow_soft": {
    id: "fx.glow.yellow_soft", component: Glow,
    defaultProps: { color: "#FFD60A", intensity: 0.4, spreadPct: 30 }, category: "effect", tags: ["glow"],
  },
  "fx.glow.cyan_hard": {
    id: "fx.glow.cyan_hard", component: Glow,
    defaultProps: { color: "#00E0FF", intensity: 0.7, spreadPct: 50 }, category: "effect", tags: ["glow", "neon"],
  },

  // Phase 3: Premium shader-based effects
  "fx.vhs.subtle": {
    id: "fx.vhs.subtle", component: VHS,
    defaultProps: { intensity: 0.3, scanlineStrength: 0.3 }, category: "effect", tags: ["vhs", "premium", "retro"],
  },
  "fx.vhs.heavy": {
    id: "fx.vhs.heavy", component: VHS,
    defaultProps: { intensity: 0.8, scanlineStrength: 0.6 }, category: "effect", tags: ["vhs", "premium", "retro"],
  },
  "fx.crt.classic": {
    id: "fx.crt.classic", component: CRT,
    defaultProps: { curvature: 0.15, scanlineStrength: 0.5, phosphorStrength: 0.5 },
    category: "effect", tags: ["crt", "premium", "retro"],
  },
  "fx.crt.arcade": {
    id: "fx.crt.arcade", component: CRT,
    defaultProps: { curvature: 0.25, scanlineStrength: 0.75, phosphorStrength: 0.8 },
    category: "effect", tags: ["crt", "premium", "arcade"],
  },
  "fx.glitch.mild": {
    id: "fx.glitch.mild", component: Glitch,
    defaultProps: { intensity: 0.4, bandCount: 30, frequency: 4 },
    category: "effect", tags: ["glitch", "premium"],
  },
  "fx.glitch.heavy": {
    id: "fx.glitch.heavy", component: Glitch,
    defaultProps: { intensity: 0.9, bandCount: 60, frequency: 10 },
    category: "effect", tags: ["glitch", "premium", "heavy"],
  },
  "fx.lightleaks.warm": {
    id: "fx.lightleaks.warm", component: LightLeaks,
    defaultProps: { intensity: 0.55, color: [1.0, 0.55, 0.25], speed: 0.25 },
    category: "effect", tags: ["lightleaks", "premium", "warm"],
  },
  "fx.lightleaks.magenta": {
    id: "fx.lightleaks.magenta", component: LightLeaks,
    defaultProps: { intensity: 0.5, color: [1.0, 0.3, 0.8], speed: 0.3 },
    category: "effect", tags: ["lightleaks", "premium"],
  },
  "fx.scanlines.soft": {
    id: "fx.scanlines.soft", component: Scanlines,
    defaultProps: { lineHeight: 3, opacity: 0.25 },
    category: "effect", tags: ["scanlines", "premium"],
  },
  "fx.scanlines.hard": {
    id: "fx.scanlines.hard", component: Scanlines,
    defaultProps: { lineHeight: 2, opacity: 0.55 },
    category: "effect", tags: ["scanlines", "premium"],
  },

  // Phase 4: Premium real-footage grain overlays
  "fx.grain.real.35mm_fine": {
    id: "fx.grain.real.35mm_fine", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/35mm_cinematic_fine_01.mp4"), blendMode: "overlay", opacity: 0.25 },
    category: "effect", tags: ["grain", "premium", "35mm", "real"],
  },
  "fx.grain.real.35mm_heavy": {
    id: "fx.grain.real.35mm_heavy", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/35mm_cinematic_heavy_01.mp4"), blendMode: "overlay", opacity: 0.35 },
    category: "effect", tags: ["grain", "premium", "35mm", "heavy", "real"],
  },
  "fx.grain.real.16mm_doc": {
    id: "fx.grain.real.16mm_doc", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/16mm_doc_01.mp4"), blendMode: "overlay", opacity: 0.30 },
    category: "effect", tags: ["grain", "premium", "16mm", "documentary", "real"],
  },
  "fx.grain.real.8mm_vintage": {
    id: "fx.grain.real.8mm_vintage", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/8mm_vintage_01.mp4"), blendMode: "soft-light", opacity: 0.40 },
    category: "effect", tags: ["grain", "premium", "8mm", "vintage", "real"],
  },
  "fx.grain.real.super8_warm": {
    id: "fx.grain.real.super8_warm", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/super8_warm_01.mp4"), blendMode: "soft-light", opacity: 0.38 },
    category: "effect", tags: ["grain", "premium", "super8", "warm", "real"],
  },
  "fx.grain.real.damaged": {
    id: "fx.grain.real.damaged", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/damaged_01.mp4"), blendMode: "screen", opacity: 0.45 },
    category: "effect", tags: ["grain", "premium", "damaged", "archival", "real"],
  },
  "fx.grain.real.clean_subtle": {
    id: "fx.grain.real.clean_subtle", component: FilmGrainOverlay,
    defaultProps: { src: staticFile("assets/grain/envato/clean_subtle_01.mp4"), blendMode: "overlay", opacity: 0.15 },
    category: "effect", tags: ["grain", "premium", "clean", "subtle", "real"],
  },

  // Phase 4: 3D LUT color grading presets
  "fx.lut.cinematic_teal_orange": {
    id: "fx.lut.cinematic_teal_orange", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/cinematic_teal_orange_01.cube"), intensity: 0.85 },
    category: "effect", tags: ["lut", "grade", "premium", "cinematic"],
  },
  "fx.lut.kodak_2383": {
    id: "fx.lut.kodak_2383", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/kodak_2383_01.cube"), intensity: 0.90 },
    category: "effect", tags: ["lut", "grade", "premium", "film", "kodak"],
  },
  "fx.lut.fuji_3510": {
    id: "fx.lut.fuji_3510", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/fuji_3510_01.cube"), intensity: 0.90 },
    category: "effect", tags: ["lut", "grade", "premium", "film", "fuji"],
  },
  "fx.lut.moody_dark": {
    id: "fx.lut.moody_dark", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/moody_dark_01.cube"), intensity: 0.75 },
    category: "effect", tags: ["lut", "grade", "premium", "moody"],
  },
  "fx.lut.documentary_natural": {
    id: "fx.lut.documentary_natural", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/doc_natural_01.cube"), intensity: 0.70 },
    category: "effect", tags: ["lut", "grade", "premium", "documentary"],
  },
  "fx.lut.vintage_faded": {
    id: "fx.lut.vintage_faded", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/vintage_faded_01.cube"), intensity: 0.75 },
    category: "effect", tags: ["lut", "grade", "premium", "vintage"],
  },
  "fx.lut.warm_golden": {
    id: "fx.lut.warm_golden", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/warm_golden_hour_01.cube"), intensity: 0.75 },
    category: "effect", tags: ["lut", "grade", "premium", "warm"],
  },
  "fx.lut.bw_classic": {
    id: "fx.lut.bw_classic", component: LUTGrade,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/bw_classic_01.cube"), intensity: 0.90 },
    category: "effect", tags: ["lut", "grade", "premium", "bw"],
  },

  // Premium WebGL LUT Grading (95%+ accuracy)
  "fx.lut.webgl.cinematic_teal_orange": {
    id: "fx.lut.webgl.cinematic_teal_orange", component: LUTGradeWebGL,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/cinematic_teal_orange_01.cube"), intensity: 1.0 },
    category: "effect", tags: ["lut", "grade", "premium", "webgl", "cinematic"],
  },
  "fx.lut.webgl.moody_dark": {
    id: "fx.lut.webgl.moody_dark", component: LUTGradeWebGL,
    defaultProps: { lutSrc: staticFile("assets/luts/envato/moody_dark_01.cube"), intensity: 0.85 },
    category: "effect", tags: ["lut", "grade", "premium", "webgl", "moody"],
  },

  // Particle Systems
  "fx.particles.dust": {
    id: "fx.particles.dust", component: ParticleSystem,
    defaultProps: { type: "dust", count: 100, color: "#FFFFFF", sizeRange: [1, 4], gravity: 0.2 },
    category: "effect", tags: ["particles", "dust", "premium"],
  },
  "fx.particles.sparks": {
    id: "fx.particles.sparks", component: ParticleSystem,
    defaultProps: { type: "sparks", count: 50, color: "#FFD700", sizeRange: [2, 6], gravity: -0.5 },
    category: "effect", tags: ["particles", "sparks", "premium", "energy"],
  },
  "fx.particles.confetti": {
    id: "fx.particles.confetti", component: ParticleSystem,
    defaultProps: { type: "confetti", count: 80, color: ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77"], sizeRange: [4, 8], gravity: 0.8 },
    category: "effect", tags: ["particles", "confetti", "premium", "celebration"],
  },
  "fx.particles.snow": {
    id: "fx.particles.snow", component: ParticleSystem,
    defaultProps: { type: "snow", count: 120, color: "#FFFFFF", sizeRange: [2, 6], gravity: 0.3 },
    category: "effect", tags: ["particles", "snow", "premium", "winter"],
  },

  // Camera Shake
  "fx.shake.subtle": {
    id: "fx.shake.subtle", component: CameraShake,
    defaultProps: { intensity: 5, frequency: 0.5, rotationIntensity: 1 },
    category: "effect", tags: ["shake", "camera", "premium", "subtle"],
  },
  "fx.shake.impact": {
    id: "fx.shake.impact", component: CameraShake,
    defaultProps: { intensity: 15, frequency: 1.0, rotationIntensity: 3, fadeFrames: 20 },
    category: "effect", tags: ["shake", "camera", "premium", "impact"],
  },

  // Glitch Effects
  "fx.glitch.subtle": {
    id: "fx.glitch.subtle", component: GlitchEffect,
    defaultProps: { intensity: 0.3, frequency: 0.05, rgbSplit: true, scanLines: false, displacement: true },
    category: "effect", tags: ["glitch", "premium", "subtle"],
  },
  "fx.glitch.intense": {
    id: "fx.glitch.intense", component: GlitchEffect,
    defaultProps: { intensity: 0.8, frequency: 0.2, rgbSplit: true, scanLines: true, displacement: true },
    category: "effect", tags: ["glitch", "premium", "intense", "digital"],
  },

  // Depth of Field
  "fx.dof.center": {
    id: "fx.dof.center", component: DepthOfField,
    defaultProps: { blurAmount: 15, focusRegion: "center", softness: 0.5 },
    category: "effect", tags: ["dof", "blur", "premium", "cinematic"],
  },
  "fx.dof.vignette": {
    id: "fx.dof.vignette", component: DepthOfField,
    defaultProps: { blurAmount: 20, focusRegion: "center", softness: 0.7 },
    category: "effect", tags: ["dof", "blur", "premium", "vignette"],
  },

  // PREMIUM Film Grain (100% Quality - WebGL Generated)
  "fx.grain.premium.35mm": {
    id: "fx.grain.premium.35mm", component: PremiumFilmGrain,
    defaultProps: { filmStock: "35mm", intensity: 0.15, grainSize: 1, colorGrain: 0.3, opacity: 0.5 },
    category: "effect", tags: ["grain", "premium", "100%", "35mm", "webgl"],
  },
  "fx.grain.premium.16mm": {
    id: "fx.grain.premium.16mm", component: PremiumFilmGrain,
    defaultProps: { filmStock: "16mm", intensity: 0.25, grainSize: 1.2, colorGrain: 0.4, opacity: 0.6 },
    category: "effect", tags: ["grain", "premium", "100%", "16mm", "webgl"],
  },
  "fx.grain.premium.65mm": {
    id: "fx.grain.premium.65mm", component: PremiumFilmGrain,
    defaultProps: { filmStock: "65mm", intensity: 0.08, grainSize: 0.8, colorGrain: 0.2, opacity: 0.4 },
    category: "effect", tags: ["grain", "premium", "100%", "65mm", "webgl", "imax"],
  },
  "fx.grain.premium.super8": {
    id: "fx.grain.premium.super8", component: PremiumFilmGrain,
    defaultProps: { filmStock: "super8", intensity: 0.35, grainSize: 1.5, colorGrain: 0.5, opacity: 0.7 },
    category: "effect", tags: ["grain", "premium", "100%", "super8", "webgl", "vintage"],
  },
  "fx.grain.premium.digital": {
    id: "fx.grain.premium.digital", component: PremiumFilmGrain,
    defaultProps: { filmStock: "digital", intensity: 0.10, grainSize: 1, colorGrain: 0.15, opacity: 0.3 },
    category: "effect", tags: ["grain", "premium", "100%", "digital", "webgl", "subtle"],
  },

  // ADVANCED Particle Systems (100% Quality - 1000+ particles)
  "fx.particles.advanced.energy": {
    id: "fx.particles.advanced.energy", component: AdvancedParticleSystem,
    defaultProps: { preset: "energy", count: 1000, glow: 1, trails: 0.7, depth3D: 0.8 },
    category: "effect", tags: ["particles", "premium", "100%", "energy", "advanced"],
  },
  "fx.particles.advanced.magic": {
    id: "fx.particles.advanced.magic", component: AdvancedParticleSystem,
    defaultProps: { preset: "magic", count: 800, glow: 1, trails: 0.9, depth3D: 0.9, turbulence: 0.8 },
    category: "effect", tags: ["particles", "premium", "100%", "magic", "advanced"],
  },
  "fx.particles.advanced.fire": {
    id: "fx.particles.advanced.fire", component: AdvancedParticleSystem,
    defaultProps: { preset: "fire", count: 1200, colors: ["#FF4500", "#FF6347", "#FFD700"], glow: 1, trails: 0.6 },
    category: "effect", tags: ["particles", "premium", "100%", "fire", "advanced"],
  },
  "fx.particles.advanced.smoke": {
    id: "fx.particles.advanced.smoke", component: AdvancedParticleSystem,
    defaultProps: { preset: "smoke", count: 600, colors: ["#808080", "#A9A9A9", "#C0C0C0"], glow: 0.2, trails: 0.4, turbulence: 0.9 },
    category: "effect", tags: ["particles", "premium", "100%", "smoke", "advanced"],
  },
  "fx.particles.advanced.sparks": {
    id: "fx.particles.advanced.sparks", component: AdvancedParticleSystem,
    defaultProps: { preset: "sparks", count: 500, colors: ["#FFD700", "#FFA500", "#FFFFFF"], glow: 1, trails: 0.8 },
    category: "effect", tags: ["particles", "premium", "100%", "sparks", "advanced"],
  },
  "fx.particles.advanced.rain": {
    id: "fx.particles.advanced.rain", component: AdvancedParticleSystem,
    defaultProps: { preset: "rain", count: 2000, colors: ["#87CEEB"], glow: 0.1, trails: 0.3, depth3D: 0.6 },
    category: "effect", tags: ["particles", "premium", "100%", "rain", "advanced", "weather"],
  },

  // LIQUID MORPH (100% Quality - SVG Path Morphing)
  "fx.morph.liquid.blob": {
    id: "fx.morph.liquid.blob", component: LiquidMorph,
    defaultProps: { preset: "blob", color: "#4ECDC4", colorSecondary: "#FF6B6B", liquidIntensity: 15 },
    category: "effect", tags: ["morph", "premium", "100%", "liquid", "blob"],
  },
  "fx.morph.liquid.wave": {
    id: "fx.morph.liquid.wave", component: LiquidMorph,
    defaultProps: { preset: "wave", color: "#667eea", colorSecondary: "#764ba2", liquidIntensity: 12 },
    category: "effect", tags: ["morph", "premium", "100%", "liquid", "wave"],
  },
  "fx.morph.liquid.pulse": {
    id: "fx.morph.liquid.pulse", component: LiquidMorph,
    defaultProps: { preset: "pulse", color: "#f093fb", colorSecondary: "#f5576c", liquidIntensity: 18 },
    category: "effect", tags: ["morph", "premium", "100%", "liquid", "pulse"],
  },
  "fx.morph.liquid.twist": {
    id: "fx.morph.liquid.twist", component: LiquidMorph,
    defaultProps: { preset: "twist", color: "#4facfe", colorSecondary: "#00f2fe", liquidIntensity: 15 },
    category: "effect", tags: ["morph", "premium", "100%", "liquid", "twist"],
  },
  "fx.morph.liquid.melt": {
    id: "fx.morph.liquid.melt", component: LiquidMorph,
    defaultProps: { preset: "melt", color: "#fa709a", colorSecondary: "#fee140", liquidIntensity: 20 },
    category: "effect", tags: ["morph", "premium", "100%", "liquid", "melt"],
  },

  // ADVANCED SHAPES (100% Quality - Geometric Patterns)
  "fx.shapes.kaleidoscope": {
    id: "fx.shapes.kaleidoscope", component: AdvancedShapes,
    defaultProps: { preset: "kaleidoscope", count: 12, colors: ["#4ECDC4", "#FF6B6B", "#FFE66D"], complexity: 3 },
    category: "effect", tags: ["shapes", "premium", "100%", "kaleidoscope", "geometric"],
  },
  "fx.shapes.mandala": {
    id: "fx.shapes.mandala", component: AdvancedShapes,
    defaultProps: { preset: "mandala", count: 8, colors: ["#667eea", "#764ba2", "#f093fb"], complexity: 4 },
    category: "effect", tags: ["shapes", "premium", "100%", "mandala", "sacred"],
  },
  "fx.shapes.hexagrid": {
    id: "fx.shapes.hexagrid", component: AdvancedShapes,
    defaultProps: { preset: "hexagrid", count: 6, colors: ["#4facfe", "#00f2fe"], complexity: 3, renderMode: "stroke" },
    category: "effect", tags: ["shapes", "premium", "100%", "hexagon", "grid"],
  },
  "fx.shapes.spirograph": {
    id: "fx.shapes.spirograph", component: AdvancedShapes,
    defaultProps: { preset: "spirograph", count: 12, color: "#fa709a", complexity: 5, strokeWidth: 3 },
    category: "effect", tags: ["shapes", "premium", "100%", "spirograph", "mathematical"],
  },
  "fx.shapes.fractal": {
    id: "fx.shapes.fractal", component: AdvancedShapes,
    defaultProps: { preset: "fractal", count: 6, colors: ["#FFD700", "#FF6B6B", "#4ECDC4"], complexity: 4 },
    category: "effect", tags: ["shapes", "premium", "100%", "fractal", "recursive"],
  },
  "fx.shapes.geometric": {
    id: "fx.shapes.geometric", component: AdvancedShapes,
    defaultProps: { preset: "geometric", count: 12, colors: ["#667eea", "#f5576c", "#4facfe"], renderMode: "both" },
    category: "effect", tags: ["shapes", "premium", "100%", "geometric", "mixed"],
  },
};
