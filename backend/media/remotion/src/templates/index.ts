import type { Template } from "./types";

const stockDocumentary: Template = {
  id: "stock-documentary",
  description: "Nature / history / science docs. Stock footage heavy, soft transitions.",
  ratio_budgets: {
    stock: [0.55, 0.7],
    kinetic: [0.15, 0.25],
    quote: [0.05, 0.15],
  },
  cuts_per_minute: [6, 8],
  allowed_transition_prefixes: ["trans.cut", "trans.dissolve", "trans.slide"],
  forbidden_transition_prefixes: ["trans.flash", "trans.zoom"],
  default_grade: "fx.grade.natural_cinematic",
  default_caption: "ov.caption.subtitle_bottom_center",
  default_music_style: "ambient_underscore",
};

const hybridKinetic: Template = {
  id: "hybrid-kinetic",
  description: "Modern faceless YT — mix of stock + kinetic typography + data.",
  ratio_budgets: {
    stock: [0.35, 0.5],
    kinetic: [0.25, 0.35],
    list: [0.05, 0.15],
    hook: [0.02, 0.08],
  },
  cuts_per_minute: [8, 14],
  allowed_transition_prefixes: ["trans.cut", "trans.slide", "trans.zoom", "trans.dissolve"],
  forbidden_transition_prefixes: [],
  default_grade: "fx.grade.cinematic_teal_orange",
  default_caption: "ov.caption.word_highlight_yellow",
  default_music_style: "cinematic_with_beats",
};

const listicleTop10: Template = {
  id: "listicle-top10",
  description: "Countdown / ranking videos. Lots of list scenes, bold full-screen numbers.",
  ratio_budgets: {
    list: [0.3, 0.45],
    fullscreen: [0.15, 0.25],
    stock: [0.2, 0.35],
    hook: [0.03, 0.1],
  },
  cuts_per_minute: [10, 16],
  allowed_transition_prefixes: [
    "trans.cut",
    "trans.slide",
    "trans.zoom",
    "trans.flash",
    "trans.wipe",
  ],
  forbidden_transition_prefixes: [],
  default_grade: "fx.grade.bright_flat",
  default_caption: "ov.caption.word_highlight_yellow",
  default_music_style: "upbeat_corporate",
};

const twoDAnimated: Template = {
  id: "2d-animated",
  description: "Flat-design explainer w/ icon animations, kinetic type, bright palette.",
  ratio_budgets: {
    icon: [0.2, 0.35],
    kinetic: [0.25, 0.4],
    list: [0.05, 0.15],
    split: [0.05, 0.15],
  },
  cuts_per_minute: [12, 18],
  allowed_transition_prefixes: [
    "trans.cut",
    "trans.slide",
    "trans.push",
    "trans.whippan",
    "trans.wipe",
  ],
  forbidden_transition_prefixes: ["trans.flash", "trans.iris"],
  default_grade: "fx.grade.bright_flat",
  default_caption: "ov.caption.big_bold_shorts",
  default_music_style: "upbeat_playful",
};

const dataHeavy: Template = {
  id: "data-heavy",
  description: "Stats / finance / research videos — charts, countdowns, big numbers.",
  ratio_budgets: {
    data: [0.35, 0.55],
    kinetic: [0.1, 0.2],
    countdown: [0.05, 0.15],
    stock: [0.1, 0.25],
  },
  cuts_per_minute: [8, 12],
  allowed_transition_prefixes: [
    "trans.cut",
    "trans.dissolve",
    "trans.slide",
    "trans.wipe",
    "trans.blurswap",
  ],
  forbidden_transition_prefixes: ["trans.flash", "trans.whippan"],
  default_grade: "fx.grade.cinematic_teal_orange",
  default_caption: "ov.caption.subtitle_bottom_center",
  default_music_style: "corporate_tech",
};

const productReview: Template = {
  id: "product-review",
  description: "Unboxing / review videos with mockups, pros-cons lists, ratings.",
  ratio_budgets: {
    mockup: [0.25, 0.4],
    list: [0.15, 0.3],
    stock: [0.1, 0.25],
    quote: [0.05, 0.15],
  },
  cuts_per_minute: [8, 14],
  allowed_transition_prefixes: [
    "trans.cut",
    "trans.slide",
    "trans.push",
    "trans.dissolve",
    "trans.cover",
  ],
  forbidden_transition_prefixes: [],
  default_grade: "fx.grade.high_key_commercial",
  default_caption: "ov.caption.word_highlight_yellow",
  default_music_style: "clean_modern",
};

const tutorialScreencast: Template = {
  id: "tutorial-screencast",
  description: "How-to videos with browser/phone screen mockups, step lists, chapters.",
  ratio_budgets: {
    mockup: [0.4, 0.6],
    list: [0.1, 0.25],
    fullscreen: [0.05, 0.15],
  },
  cuts_per_minute: [6, 10],
  allowed_transition_prefixes: ["trans.cut", "trans.dissolve", "trans.blurswap"],
  forbidden_transition_prefixes: ["trans.flash", "trans.whippan", "trans.iris"],
  default_grade: "fx.grade.natural_cinematic",
  default_caption: "ov.caption.subtitle_bottom_center",
  default_music_style: "lofi_focus",
};

const motivationalReel: Template = {
  id: "motivational-reel",
  description: "Short-form vertical motivation — quotes, fullscreen text, cinematic stock.",
  ratio_budgets: {
    quote: [0.2, 0.35],
    fullscreen: [0.15, 0.3],
    stock: [0.3, 0.5],
    kinetic: [0.1, 0.2],
  },
  cuts_per_minute: [14, 22],
  allowed_transition_prefixes: [
    "trans.cut",
    "trans.blurswap",
    "trans.whippan",
    "trans.flash",
    "trans.dissolve",
  ],
  forbidden_transition_prefixes: [],
  default_grade: "fx.grade.cinematic_teal_orange",
  default_caption: "ov.caption.big_bold_shorts",
  default_music_style: "epic_cinematic",
};

const cinematicVlog: Template = {
  id: "cinematic-vlog",
  description: "Travel/lifestyle vlog — letterbox, long dissolves, film grain.",
  ratio_budgets: {
    stock: [0.6, 0.8],
    kinetic: [0.05, 0.15],
    quote: [0.05, 0.15],
  },
  cuts_per_minute: [6, 10],
  allowed_transition_prefixes: ["trans.dissolve", "trans.cut", "trans.blurswap"],
  forbidden_transition_prefixes: ["trans.flash", "trans.whippan", "trans.zoom", "trans.iris"],
  default_grade: "fx.grade.warm_sunset",
  default_caption: "ov.caption.subtitle_bottom_center",
  default_music_style: "cinematic_ambient",
};

const corporateExplainer: Template = {
  id: "corporate-explainer",
  description: "B2B explainer — mockups, data, clean typography, low-energy cuts.",
  ratio_budgets: {
    mockup: [0.15, 0.3],
    data: [0.15, 0.3],
    kinetic: [0.1, 0.2],
    list: [0.1, 0.2],
    stock: [0.1, 0.2],
  },
  cuts_per_minute: [6, 10],
  allowed_transition_prefixes: ["trans.cut", "trans.dissolve", "trans.slide", "trans.cover"],
  forbidden_transition_prefixes: ["trans.flash", "trans.whippan", "trans.iris"],
  default_grade: "fx.grade.bright_flat",
  default_caption: "ov.caption.subtitle_bottom_center",
  default_music_style: "corporate_tech",
};

export const TEMPLATES: Record<string, Template> = {
  [stockDocumentary.id]: stockDocumentary,
  [hybridKinetic.id]: hybridKinetic,
  [listicleTop10.id]: listicleTop10,
  [twoDAnimated.id]: twoDAnimated,
  [dataHeavy.id]: dataHeavy,
  [productReview.id]: productReview,
  [tutorialScreencast.id]: tutorialScreencast,
  [motivationalReel.id]: motivationalReel,
  [cinematicVlog.id]: cinematicVlog,
  [corporateExplainer.id]: corporateExplainer,
};

export type { Template } from "./types";
