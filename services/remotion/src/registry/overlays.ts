import { CaptionOverlay } from "../components/overlays/CaptionOverlay";
import { LowerThird } from "../components/overlays/LowerThird";
import { Watermark } from "../components/overlays/Watermark";
import { ProgressBar } from "../components/overlays/ProgressBar";
import { Particles } from "../components/overlays/Particles";
import { LogoBug } from "../components/overlays/LogoBug";
import { SubscribePing } from "../components/overlays/SubscribePing";
import { EndCard } from "../components/overlays/EndCard";
import { ChapterMarker } from "../components/overlays/ChapterMarker";
import { ChannelWatermark } from "../components/branding/ChannelWatermark";
import { WordAlignedCaption } from "../components/overlays/WordAlignedCaption";
import { AudioWaveform } from "../components/overlays/AudioWaveform";
import { PremiumLowerThird } from "../components/overlays/PremiumLowerThird";
import { ThreeDLogoReveal } from "../components/overlays/3DLogoReveal";
import type { PresetRegistry } from "./types";

export const OVERLAY_PRESETS: PresetRegistry = {
  // --- Captions ---
  "ov.caption.word_highlight_yellow": {
    id: "ov.caption.word_highlight_yellow",
    component: CaptionOverlay,
    defaultProps: { style: "word_highlight_yellow", accent: "#FFD60A", maxWords: 6 },
    category: "overlay",
    tags: ["caption", "word-highlight"],
  },
  "ov.caption.subtitle_bottom_center": {
    id: "ov.caption.subtitle_bottom_center",
    component: CaptionOverlay,
    defaultProps: { style: "subtitle_bottom_center" },
    category: "overlay",
    tags: ["caption", "subtitle"],
  },
  "ov.caption.karaoke_colored": {
    id: "ov.caption.karaoke_colored",
    component: CaptionOverlay,
    defaultProps: { style: "karaoke_colored", accent: "#00E0FF", maxWords: 8 },
    category: "overlay",
    tags: ["caption", "karaoke"],
  },
  "ov.caption.big_bold_shorts": {
    id: "ov.caption.big_bold_shorts",
    component: CaptionOverlay,
    defaultProps: { style: "big_bold_shorts", accent: "#FFD60A", maxWords: 4 },
    category: "overlay",
    tags: ["caption", "shorts"],
  },

  // --- LowerThird ---
  "ov.lowerthird.minimal_white": {
    id: "ov.lowerthird.minimal_white",
    component: LowerThird,
    defaultProps: { style: "minimal_white", position: "left" },
    category: "overlay",
    tags: ["lowerthird", "minimal"],
  },
  "ov.lowerthird.news_red": {
    id: "ov.lowerthird.news_red",
    component: LowerThird,
    defaultProps: { style: "news_red", position: "left", accent: "#E11D1D" },
    category: "overlay",
    tags: ["lowerthird", "news"],
  },
  "ov.lowerthird.gradient_modern": {
    id: "ov.lowerthird.gradient_modern",
    component: LowerThird,
    defaultProps: { style: "gradient_modern", position: "left", accent: "#FFD60A" },
    category: "overlay",
    tags: ["lowerthird", "modern"],
  },

  // --- Watermark ---
  "ov.watermark.tr_small": {
    id: "ov.watermark.tr_small",
    component: Watermark,
    defaultProps: { corner: "tr", size: 60, opacity: 0.7 },
    category: "overlay",
    tags: ["watermark", "logo"],
  },
  "ov.watermark.br_medium": {
    id: "ov.watermark.br_medium",
    component: Watermark,
    defaultProps: { corner: "br", size: 90, opacity: 0.8 },
    category: "overlay",
    tags: ["watermark", "logo"],
  },

  // --- Phase 2: ProgressBar ---
  "ov.progress.thin_top": {
    id: "ov.progress.thin_top", component: ProgressBar,
    defaultProps: { position: "top", style: "thin_line", heightPx: 6, color: "#FFD60A" },
    category: "overlay", tags: ["progress"],
  },
  "ov.progress.fat_bottom": {
    id: "ov.progress.fat_bottom", component: ProgressBar,
    defaultProps: { position: "bottom", style: "rounded_fat", heightPx: 10, color: "#FF3B30" },
    category: "overlay", tags: ["progress"],
  },
  "ov.progress.segmented_top": {
    id: "ov.progress.segmented_top", component: ProgressBar,
    defaultProps: { position: "top", style: "segmented", heightPx: 8, segments: 10, color: "#00E0FF" },
    category: "overlay", tags: ["progress", "chapters"],
  },

  // --- Phase 2: Particles (dust / snow / sparkles / confetti) ---
  "ov.particles.dust": {
    id: "ov.particles.dust", component: Particles,
    defaultProps: { style: "dust" }, category: "overlay", tags: ["particles", "ambient"],
  },
  "ov.particles.snow": {
    id: "ov.particles.snow", component: Particles,
    defaultProps: { style: "snow" }, category: "overlay", tags: ["particles", "weather"],
  },
  "ov.particles.sparkles": {
    id: "ov.particles.sparkles", component: Particles,
    defaultProps: { style: "sparkles" }, category: "overlay", tags: ["particles", "magic"],
  },
  "ov.particles.confetti": {
    id: "ov.particles.confetti", component: Particles,
    defaultProps: { style: "confetti" }, category: "overlay", tags: ["particles", "celebration"],
  },

  // --- Phase 2: LogoBug / ChannelWatermark ---
  "ov.logobug.tr": {
    id: "ov.logobug.tr", component: LogoBug,
    defaultProps: { corner: "tr", heightPx: 60, opacity: 0.8 },
    category: "overlay", tags: ["logo", "branding"],
  },
  "ov.logobug.br": {
    id: "ov.logobug.br", component: LogoBug,
    defaultProps: { corner: "br", heightPx: 60, opacity: 0.8 },
    category: "overlay", tags: ["logo", "branding"],
  },
  "ov.channel_watermark.default": {
    id: "ov.channel_watermark.default", component: ChannelWatermark,
    defaultProps: { corner: "tr", heightPx: 70, opacity: 0.85, padding: 56 },
    category: "overlay", tags: ["branding", "channel"],
  },

  // --- Phase 2: SubscribePing ---
  "ov.subscribe.red_button": {
    id: "ov.subscribe.red_button", component: SubscribePing,
    defaultProps: { style: "red_button", text: "SUBSCRIBE", position: "br" },
    category: "overlay", tags: ["subscribe", "cta"],
  },
  "ov.subscribe.minimal_pill": {
    id: "ov.subscribe.minimal_pill", component: SubscribePing,
    defaultProps: { style: "minimal_pill", text: "SUBSCRIBE", position: "br" },
    category: "overlay", tags: ["subscribe", "cta"],
  },
  "ov.subscribe.neon": {
    id: "ov.subscribe.neon", component: SubscribePing,
    defaultProps: { style: "neon", text: "SUBSCRIBE", position: "br" },
    category: "overlay", tags: ["subscribe", "cta", "neon"],
  },

  // --- Phase 2: EndCard (really a scene-like overlay, use at end of video) ---
  "ov.endcard.default": {
    id: "ov.endcard.default", component: EndCard,
    defaultProps: {}, category: "overlay", tags: ["endcard", "cta"],
  },

  // --- Phase 2: ChapterMarker ---
  "ov.chapter.top_left": {
    id: "ov.chapter.top_left", component: ChapterMarker,
    defaultProps: { position: "top" }, category: "overlay", tags: ["chapter"],
  },
  "ov.chapter.bottom_left": {
    id: "ov.chapter.bottom_left", component: ChapterMarker,
    defaultProps: { position: "bottom" }, category: "overlay", tags: ["chapter"],
  },

  // --- Phase 3: Word-level forced-alignment captions ---
  "ov.wordcap.karaoke_yellow": {
    id: "ov.wordcap.karaoke_yellow", component: WordAlignedCaption,
    defaultProps: { style: "karaoke_highlight", activeColor: "#FFD60A", chunkSize: 6, position: "bottom" },
    category: "overlay", tags: ["caption", "word-level", "premium"],
  },
  "ov.wordcap.karaoke_cyan": {
    id: "ov.wordcap.karaoke_cyan", component: WordAlignedCaption,
    defaultProps: { style: "karaoke_highlight", activeColor: "#00E0FF", chunkSize: 6, position: "bottom" },
    category: "overlay", tags: ["caption", "word-level", "premium"],
  },
  "ov.wordcap.pop_shorts": {
    id: "ov.wordcap.pop_shorts", component: WordAlignedCaption,
    defaultProps: { style: "pop_active", activeColor: "#FFD60A", chunkSize: 4, position: "center", fontSize: 88 },
    category: "overlay", tags: ["caption", "word-level", "shorts", "premium"],
  },
  "ov.wordcap.underline_minimal": {
    id: "ov.wordcap.underline_minimal", component: WordAlignedCaption,
    defaultProps: { style: "underline_active", activeColor: "#FF3B30", chunkSize: 8, position: "bottom" },
    category: "overlay", tags: ["caption", "word-level", "minimal", "premium"],
  },

  // --- Audio Waveforms ---
  "ov.waveform.bars_bottom": {
    id: "ov.waveform.bars_bottom", component: AudioWaveform,
    defaultProps: { audioSrc: "", style: "bars", bars: 64, color: "#00E0FF", position: "bottom", height: 0.2 },
    category: "overlay", tags: ["audio", "waveform", "premium", "bars"],
  },
  "ov.waveform.circular": {
    id: "ov.waveform.circular", component: AudioWaveform,
    defaultProps: { audioSrc: "", style: "circular", bars: 48, color: "#FF3B30", height: 0.3 },
    category: "overlay", tags: ["audio", "waveform", "premium", "circular"],
  },
  "ov.waveform.line_center": {
    id: "ov.waveform.line_center", component: AudioWaveform,
    defaultProps: { audioSrc: "", style: "line", bars: 128, color: "#FFD60A", position: "center", height: 0.15 },
    category: "overlay", tags: ["audio", "waveform", "premium", "line"],
  },
  "ov.waveform.radial": {
    id: "ov.waveform.radial", component: AudioWaveform,
    defaultProps: { audioSrc: "", style: "radial", bars: 64, color: "#4ECDC4", height: 0.4 },
    category: "overlay", tags: ["audio", "waveform", "premium", "radial"],
  },

  // --- PREMIUM LOWER THIRDS (100% Quality - Broadcast Grade) ---
  "ov.lowerthird.premium.minimal": {
    id: "ov.lowerthird.premium.minimal", component: PremiumLowerThird,
    defaultProps: { variation: "minimal", name: "John Doe", subtitle: "CEO & Founder", primaryColor: "#4ECDC4" },
    category: "overlay", tags: ["lowerthird", "premium", "100%", "minimal", "broadcast"],
  },
  "ov.lowerthird.premium.corporate": {
    id: "ov.lowerthird.premium.corporate", component: PremiumLowerThird,
    defaultProps: { variation: "corporate", name: "Jane Smith", subtitle: "Creative Director", primaryColor: "#667eea", secondaryColor: "#764ba2" },
    category: "overlay", tags: ["lowerthird", "premium", "100%", "corporate", "broadcast"],
  },
  "ov.lowerthird.premium.modern": {
    id: "ov.lowerthird.premium.modern", component: PremiumLowerThird,
    defaultProps: { variation: "modern", name: "Alex Johnson", subtitle: "Lead Designer", primaryColor: "#4facfe", secondaryColor: "#00f2fe" },
    category: "overlay", tags: ["lowerthird", "premium", "100%", "modern", "broadcast"],
  },
  "ov.lowerthird.premium.bold": {
    id: "ov.lowerthird.premium.bold", component: PremiumLowerThird,
    defaultProps: { variation: "bold", name: "Sarah Williams", subtitle: "Marketing Manager", primaryColor: "#fa709a", secondaryColor: "#fee140" },
    category: "overlay", tags: ["lowerthird", "premium", "100%", "bold", "broadcast"],
  },
  "ov.lowerthird.premium.elegant": {
    id: "ov.lowerthird.premium.elegant", component: PremiumLowerThird,
    defaultProps: { variation: "elegant", name: "Michael Brown", subtitle: "Senior Consultant", primaryColor: "#FFD700", secondaryColor: "#FF6B6B" },
    category: "overlay", tags: ["lowerthird", "premium", "100%", "elegant", "broadcast"],
  },

  // --- 3D LOGO REVEALS (95% Quality - CSS 3D Transforms) ---
  "ov.logo.3d.flip": {
    id: "ov.logo.3d.flip", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "flip", duration: 90, size: 0.4, color: "#4ECDC4" },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "flip", "reveal"],
  },
  "ov.logo.3d.cube": {
    id: "ov.logo.3d.cube", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "cube", duration: 90, size: 0.4, color: "#667eea" },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "cube", "reveal"],
  },
  "ov.logo.3d.fold": {
    id: "ov.logo.3d.fold", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "fold", duration: 120, size: 0.5, color: "#4facfe" },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "fold", "reveal"],
  },
  "ov.logo.3d.explode": {
    id: "ov.logo.3d.explode", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "explode", duration: 120, size: 0.4, color: "#fa709a" },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "explode", "reveal"],
  },
  "ov.logo.3d.spiral": {
    id: "ov.logo.3d.spiral", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "spiral", duration: 90, size: 0.4, color: "#FFD700" },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "spiral", "reveal"],
  },
  "ov.logo.3d.particles": {
    id: "ov.logo.3d.particles", component: ThreeDLogoReveal,
    defaultProps: { logoSrc: "", animation: "particles", duration: 120, size: 0.4, color: "#FF6B6B", particles: true },
    category: "overlay", tags: ["logo", "3d", "premium", "95%", "particles", "reveal"],
  },
};
