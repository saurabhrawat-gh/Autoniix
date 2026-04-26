import { PlaceholderScene } from "../components/scenes/PlaceholderScene";
import { StockFootageScene } from "../components/scenes/StockFootageScene";
import { KineticTypography } from "../components/scenes/KineticTypography";
import { FullScreenText } from "../components/scenes/FullScreenText";
import { QuoteCard } from "../components/scenes/QuoteCard";
import { ListAnimation } from "../components/scenes/ListAnimation";
import { HookOpener } from "../components/scenes/HookOpener";
import { DataVisualization } from "../components/scenes/DataVisualization";
import { SplitComparison } from "../components/scenes/SplitComparison";
import { IconAnimation } from "../components/scenes/IconAnimation";
import { CountdownScene } from "../components/scenes/CountdownScene";
import { BeforeAfterSlider } from "../components/scenes/BeforeAfterSlider";
import { PhoneMockup } from "../components/scenes/PhoneMockup";
import { BrowserMockup } from "../components/scenes/BrowserMockup";
import { SocialMockup } from "../components/scenes/SocialMockup";
import { IntroAnimation } from "../components/branding/IntroAnimation";
import { OutroEndscreen } from "../components/branding/OutroEndscreen";
import { TimelineAnimation } from "../components/scenes/TimelineAnimation";
import { MapAnimation } from "../components/scenes/MapAnimation";
import { CodeTyping } from "../components/scenes/CodeTyping";
import { FlowchartAnimation } from "../components/scenes/FlowchartAnimation";
import { AdvancedKineticText } from "../components/scenes/AdvancedKineticText";
import { TextStrokeReveal } from "../components/scenes/TextStrokeReveal";
import type { PresetRegistry } from "./types";

export const SCENE_PRESETS: PresetRegistry = {
  // --- Debug ---
  "scene.placeholder": {
    id: "scene.placeholder",
    component: PlaceholderScene,
    defaultProps: { label: "placeholder", bg: "#0A0A0A", fg: "#FFFFFF" },
    category: "scene",
    tags: ["debug"],
  },
  "scene.placeholder.black": {
    id: "scene.placeholder.black",
    component: PlaceholderScene,
    defaultProps: { label: "", bg: "#000000", fg: "#000000" },
    category: "scene",
    tags: ["debug", "black"],
  },

  // --- Stock footage ---
  "scene.stock.static_centered": {
    id: "scene.stock.static_centered",
    component: StockFootageScene,
    defaultProps: { fit: "cover", kenBurns: false, volume: 0 },
    category: "scene",
    tags: ["stock", "footage"],
  },
  "scene.stock.kenburns_slow": {
    id: "scene.stock.kenburns_slow",
    component: StockFootageScene,
    defaultProps: { fit: "cover", kenBurns: true, kenBurnsTo: 1.05, volume: 0 },
    category: "scene",
    tags: ["stock", "footage", "kenburns"],
  },
  "scene.stock.kenburns_punch": {
    id: "scene.stock.kenburns_punch",
    component: StockFootageScene,
    defaultProps: { fit: "cover", kenBurns: true, kenBurnsTo: 1.18, volume: 0 },
    category: "scene",
    tags: ["stock", "footage", "kenburns", "punch"],
  },

  // --- Kinetic typography ---
  "scene.kinetic.scale_punch": {
    id: "scene.kinetic.scale_punch",
    component: KineticTypography,
    defaultProps: { animation: "scale_punch" },
    category: "scene",
    tags: ["kinetic", "text", "punch"],
  },
  "scene.kinetic.word_cascade": {
    id: "scene.kinetic.word_cascade",
    component: KineticTypography,
    defaultProps: { animation: "word_cascade" },
    category: "scene",
    tags: ["kinetic", "text"],
  },
  "scene.kinetic.typewriter": {
    id: "scene.kinetic.typewriter",
    component: KineticTypography,
    defaultProps: { animation: "typewriter" },
    category: "scene",
    tags: ["kinetic", "text", "typewriter"],
  },
  "scene.kinetic.fade_up": {
    id: "scene.kinetic.fade_up",
    component: KineticTypography,
    defaultProps: { animation: "fade_up" },
    category: "scene",
    tags: ["kinetic", "text", "fade"],
  },

  // --- Full-screen statements ---
  "scene.fullscreen.bold": {
    id: "scene.fullscreen.bold",
    component: FullScreenText,
    defaultProps: { uppercase: true },
    category: "scene",
    tags: ["fullscreen", "statement"],
  },
  "scene.fullscreen.bold_red": {
    id: "scene.fullscreen.bold_red",
    component: FullScreenText,
    defaultProps: { uppercase: true, bg: "#FF3B30", color: "#FFFFFF" },
    category: "scene",
    tags: ["fullscreen", "statement", "red"],
  },

  // --- Quotes ---
  "scene.quote.minimal_serif": {
    id: "scene.quote.minimal_serif",
    component: QuoteCard,
    defaultProps: { style: "serif_minimal" },
    category: "scene",
    tags: ["quote", "minimal"],
  },
  "scene.quote.bold_modern": {
    id: "scene.quote.bold_modern",
    component: QuoteCard,
    defaultProps: { style: "bold_modern" },
    category: "scene",
    tags: ["quote", "modern"],
  },
  "scene.quote.neon": {
    id: "scene.quote.neon",
    component: QuoteCard,
    defaultProps: { style: "neon" },
    category: "scene",
    tags: ["quote", "neon"],
  },

  // --- Lists ---
  "scene.list.checkmark": {
    id: "scene.list.checkmark",
    component: ListAnimation,
    defaultProps: { bullet: "check" },
    category: "scene",
    tags: ["list", "check"],
  },
  "scene.list.numbered": {
    id: "scene.list.numbered",
    component: ListAnimation,
    defaultProps: { bullet: "number" },
    category: "scene",
    tags: ["list", "numbered"],
  },
  "scene.list.arrow": {
    id: "scene.list.arrow",
    component: ListAnimation,
    defaultProps: { bullet: "arrow" },
    category: "scene",
    tags: ["list"],
  },

  // --- Hook openers ---
  "scene.hook.question": {
    id: "scene.hook.question",
    component: HookOpener,
    defaultProps: { style: "question", flash: false },
    category: "scene",
    tags: ["hook", "question"],
  },
  "scene.hook.question_flash": {
    id: "scene.hook.question_flash",
    component: HookOpener,
    defaultProps: { style: "question", flash: true },
    category: "scene",
    tags: ["hook", "question", "flash"],
  },
  "scene.hook.stat": {
    id: "scene.hook.stat",
    component: HookOpener,
    defaultProps: { style: "stat", flash: false },
    category: "scene",
    tags: ["hook", "stat"],
  },
  "scene.hook.statement": {
    id: "scene.hook.statement",
    component: HookOpener,
    defaultProps: { style: "statement", flash: false },
    category: "scene",
    tags: ["hook", "statement"],
  },

  // --- Phase 2: DataVisualization ---
  "scene.data.bar": {
    id: "scene.data.bar", component: DataVisualization,
    defaultProps: { type: "bar" }, category: "scene", tags: ["data", "chart", "bar"],
  },
  "scene.data.line": {
    id: "scene.data.line", component: DataVisualization,
    defaultProps: { type: "line" }, category: "scene", tags: ["data", "chart", "line"],
  },
  "scene.data.pie": {
    id: "scene.data.pie", component: DataVisualization,
    defaultProps: { type: "pie" }, category: "scene", tags: ["data", "chart", "pie"],
  },
  "scene.data.donut": {
    id: "scene.data.donut", component: DataVisualization,
    defaultProps: { type: "donut" }, category: "scene", tags: ["data", "chart", "donut"],
  },
  "scene.data.stacked_bar": {
    id: "scene.data.stacked_bar", component: DataVisualization,
    defaultProps: { type: "stacked_bar" }, category: "scene", tags: ["data", "chart"],
  },

  // --- Phase 2: SplitComparison ---
  "scene.split.vs_badge": {
    id: "scene.split.vs_badge", component: SplitComparison,
    defaultProps: { vsBadge: true }, category: "scene", tags: ["split", "compare", "vs"],
  },
  "scene.split.no_badge": {
    id: "scene.split.no_badge", component: SplitComparison,
    defaultProps: { vsBadge: false }, category: "scene", tags: ["split", "compare"],
  },

  // --- Phase 2: IconAnimation ---
  "scene.icon.pop": {
    id: "scene.icon.pop", component: IconAnimation,
    defaultProps: { style: "pop" }, category: "scene", tags: ["icon"],
  },
  "scene.icon.pulse": {
    id: "scene.icon.pulse", component: IconAnimation,
    defaultProps: { style: "pulse" }, category: "scene", tags: ["icon", "pulse"],
  },

  // --- Phase 2: CountdownScene ---
  "scene.countdown.numeric": {
    id: "scene.countdown.numeric", component: CountdownScene,
    defaultProps: { style: "numeric" }, category: "scene", tags: ["countdown"],
  },
  "scene.countdown.dial": {
    id: "scene.countdown.dial", component: CountdownScene,
    defaultProps: { style: "dial" }, category: "scene", tags: ["countdown", "dial"],
  },

  // --- Phase 2: BeforeAfterSlider ---
  "scene.beforeafter.auto_sweep": {
    id: "scene.beforeafter.auto_sweep", component: BeforeAfterSlider,
    defaultProps: { mode: "auto" }, category: "scene", tags: ["beforeafter", "slider"],
  },
  "scene.beforeafter.static_center": {
    id: "scene.beforeafter.static_center", component: BeforeAfterSlider,
    defaultProps: { mode: "static", position: 0.5 }, category: "scene", tags: ["beforeafter"],
  },

  // --- Phase 2: Mockups ---
  "scene.mockup.phone_iphone": {
    id: "scene.mockup.phone_iphone", component: PhoneMockup,
    defaultProps: { style: "iphone" }, category: "scene", tags: ["mockup", "phone"],
  },
  "scene.mockup.phone_tilted": {
    id: "scene.mockup.phone_tilted", component: PhoneMockup,
    defaultProps: { style: "iphone", tilt: -8 }, category: "scene", tags: ["mockup", "phone"],
  },
  "scene.mockup.browser": {
    id: "scene.mockup.browser", component: BrowserMockup,
    defaultProps: {}, category: "scene", tags: ["mockup", "browser"],
  },
  "scene.mockup.social_twitter": {
    id: "scene.mockup.social_twitter", component: SocialMockup,
    defaultProps: { platform: "twitter" }, category: "scene", tags: ["mockup", "social"],
  },
  "scene.mockup.social_instagram": {
    id: "scene.mockup.social_instagram", component: SocialMockup,
    defaultProps: { platform: "instagram" }, category: "scene", tags: ["mockup", "social"],
  },
  "scene.mockup.social_youtube_comment": {
    id: "scene.mockup.social_youtube_comment", component: SocialMockup,
    defaultProps: { platform: "youtube_comment" }, category: "scene", tags: ["mockup", "social"],
  },

  // --- Phase 2: Branding (full-screen) ---
  "scene.branding.intro_sweep": {
    id: "scene.branding.intro_sweep", component: IntroAnimation,
    defaultProps: {}, category: "scene", tags: ["branding", "intro"],
  },
  "scene.branding.outro_subscribe": {
    id: "scene.branding.outro_subscribe", component: OutroEndscreen,
    defaultProps: {}, category: "scene", tags: ["branding", "outro"],
  },

  // --- Phase 3: Premium scenes ---
  "scene.timeline.horizontal": {
    id: "scene.timeline.horizontal", component: TimelineAnimation,
    defaultProps: { orientation: "horizontal", events: [] },
    category: "scene", tags: ["timeline", "premium"],
  },
  "scene.timeline.vertical": {
    id: "scene.timeline.vertical", component: TimelineAnimation,
    defaultProps: { orientation: "vertical", events: [] },
    category: "scene", tags: ["timeline", "premium"],
  },
  "scene.map.route": {
    id: "scene.map.route", component: MapAnimation,
    defaultProps: { drawRoute: true, pins: [] },
    category: "scene", tags: ["map", "premium"],
  },
  "scene.map.pins_only": {
    id: "scene.map.pins_only", component: MapAnimation,
    defaultProps: { drawRoute: false, pins: [] },
    category: "scene", tags: ["map", "premium"],
  },
  "scene.code.typing_dark_ts": {
    id: "scene.code.typing_dark_ts", component: CodeTyping,
    defaultProps: { code: "", language: "ts", theme: "dark", cps: 30 },
    category: "scene", tags: ["code", "premium"],
  },
  "scene.code.typing_light_py": {
    id: "scene.code.typing_light_py", component: CodeTyping,
    defaultProps: { code: "", language: "py", theme: "light", cps: 30 },
    category: "scene", tags: ["code", "premium"],
  },
  "scene.code.typing_fast_dark": {
    id: "scene.code.typing_fast_dark", component: CodeTyping,
    defaultProps: { code: "", language: "ts", theme: "dark", cps: 60 },
    category: "scene", tags: ["code", "premium", "fast"],
  },
  "scene.flowchart.default": {
    id: "scene.flowchart.default", component: FlowchartAnimation,
    defaultProps: { nodes: [], edges: [] },
    category: "scene", tags: ["flowchart", "premium"],
  },

  // --- Premium Kinetic Typography ---
  "scene.kinetic.cascade": {
    id: "scene.kinetic.cascade", component: AdvancedKineticText,
    defaultProps: { text: "", style: "cascade", staggerFrames: 3, fontSize: 80, motionBlur: true },
    category: "scene", tags: ["text", "kinetic", "premium", "cascade"],
  },
  "scene.kinetic.elastic": {
    id: "scene.kinetic.elastic", component: AdvancedKineticText,
    defaultProps: { text: "", style: "elastic", staggerFrames: 2, fontSize: 80, motionBlur: true },
    category: "scene", tags: ["text", "kinetic", "premium", "elastic"],
  },
  "scene.kinetic.glitch": {
    id: "scene.kinetic.glitch", component: AdvancedKineticText,
    defaultProps: { text: "", style: "glitch", staggerFrames: 4, fontSize: 80, motionBlur: false },
    category: "scene", tags: ["text", "kinetic", "premium", "glitch"],
  },
  "scene.kinetic.wave": {
    id: "scene.kinetic.wave", component: AdvancedKineticText,
    defaultProps: { text: "", style: "wave", staggerFrames: 2, fontSize: 80, motionBlur: true },
    category: "scene", tags: ["text", "kinetic", "premium", "wave"],
  },
  "scene.kinetic.explode": {
    id: "scene.kinetic.explode", component: AdvancedKineticText,
    defaultProps: { text: "", style: "explode", staggerFrames: 3, fontSize: 80, motionBlur: true },
    category: "scene", tags: ["text", "kinetic", "premium", "explode"],
  },

  // --- Text Stroke Reveal ---
  "scene.text.stroke_reveal": {
    id: "scene.text.stroke_reveal", component: TextStrokeReveal,
    defaultProps: { text: "", fontSize: 100, strokeColor: "#FFFFFF", fillColor: "#FFFFFF", strokeWidth: 3, revealDuration: 60, fillDelay: 30 },
    category: "scene", tags: ["text", "stroke", "premium", "reveal"],
  },
  "scene.text.stroke_reveal_neon": {
    id: "scene.text.stroke_reveal_neon", component: TextStrokeReveal,
    defaultProps: { text: "", fontSize: 100, strokeColor: "#00E0FF", fillColor: "#00E0FF", strokeWidth: 4, revealDuration: 50, fillDelay: 25 },
    category: "scene", tags: ["text", "stroke", "premium", "neon"],
  },
};
