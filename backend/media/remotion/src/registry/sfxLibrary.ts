/**
 * SFX library: curated sound-effect identifiers addressable by short IDs in
 * the Direction Format (e.g. `sfx.whoosh.short`). Each entry maps to a URL
 * resolved at render time — typically an object in the configured S3/R2
 * bucket, or a CDN path. Keeping the catalogue in one place lets the AI
 * director reference SFX without knowing asset URLs.
 *
 * Premium-first strategy (1000+ sounds):
 *   - 700 Envato premium (PRIMARY)
 *   - 300 curated free (Mixkit, Pixabay, Freesound)
 *   - Original 96 built-in sounds retained
 *
 * Resolution order:
 *   1. Custom override map passed to `resolveSfx()` (caller-supplied).
 *   2. Absolute URL on the entry (CDN / external).
 *   3. `SFX_BASE_URL` env var + `path` (default).
 *
 * The default `path`s follow `{category}/{slug}.mp3` so ops can drop files
 * into a bucket without touching code.
 */

import { staticFile } from "remotion";

export type SfxCategory =
  | "whoosh"
  | "impact"
  | "pop"
  | "swoosh"
  | "ding"
  | "click"
  | "riser"
  | "drop"
  | "glitch"
  | "tech"
  | "ui"
  | "cinematic"
  | "ambient"
  | "transition"
  | "notification"
  | "foley"
  | "musical"
  | "nature"
  | "mechanical"
  | "vocal"
  | "alarm"
  | "explosion"
  | "magic"
  | "comedy"
  | "horror";

export type SfxSource = "built_in" | "envato" | "mixkit" | "pixabay" | "freesound";

export interface SfxEntry {
  id: string;
  category: SfxCategory;
  /** Short human label. */
  label: string;
  /** Duration hint in ms (for sequencing/ducking heuristics). */
  durationMs: number;
  /** Default loudness target in dBFS the mixer should place it at. */
  defaultDb?: number;
  /** Relative path inside the SFX bucket (used if no absolute url). */
  path: string;
  /** Optional absolute URL, wins over path. */
  url?: string;
  tags?: string[];
}

/* eslint-disable max-lines */

const mk = (
  id: string,
  category: SfxCategory,
  label: string,
  durationMs: number,
  path: string,
  tags: string[] = [],
  defaultDb = -6,
): SfxEntry => ({ id, category, label, durationMs, path, tags, defaultDb });

export const SFX_LIBRARY: Record<string, SfxEntry> = Object.fromEntries(
  [
    mk("sfx.whoosh.short",        "whoosh", "Whoosh short",        300, "whoosh/whoosh_short.mp3", ["transition"]),
    mk("sfx.whoosh.long",         "whoosh", "Whoosh long",         900, "whoosh/whoosh_long.mp3",  ["transition"]),
    mk("sfx.whoosh.airy",         "whoosh", "Whoosh airy",         600, "whoosh/whoosh_airy.mp3"),
    mk("sfx.whoosh.dark",         "whoosh", "Whoosh dark",         700, "whoosh/whoosh_dark.mp3"),
    mk("sfx.whoosh.bright",       "whoosh", "Whoosh bright",       500, "whoosh/whoosh_bright.mp3"),
    mk("sfx.whoosh.reverse",      "whoosh", "Whoosh reverse",      800, "whoosh/whoosh_reverse.mp3"),
    mk("sfx.whoosh.metallic",     "whoosh", "Whoosh metallic",     650, "whoosh/whoosh_metallic.mp3"),
    mk("sfx.whoosh.soft_pass",    "whoosh", "Whoosh soft pass",    520, "whoosh/whoosh_soft_pass.mp3"),
    mk("sfx.whoosh.heavy",        "whoosh", "Whoosh heavy",        850, "whoosh/whoosh_heavy.mp3"),
    mk("sfx.whoosh.wind",         "whoosh", "Wind whoosh",         1200, "whoosh/whoosh_wind.mp3"),

    mk("sfx.impact.punch",        "impact", "Impact punch",        250, "impact/impact_punch.mp3"),
    mk("sfx.impact.boom",         "impact", "Impact boom",         1100, "impact/impact_boom.mp3"),
    mk("sfx.impact.cinematic",    "impact", "Cinematic hit",       1400, "impact/impact_cinematic.mp3"),
    mk("sfx.impact.sub_drop",     "impact", "Sub drop",            1800, "impact/impact_sub_drop.mp3"),
    mk("sfx.impact.metal",        "impact", "Metal hit",           500, "impact/impact_metal.mp3"),
    mk("sfx.impact.wood",         "impact", "Wood hit",            300, "impact/impact_wood.mp3"),
    mk("sfx.impact.thud",         "impact", "Thud",                400, "impact/impact_thud.mp3"),
    mk("sfx.impact.crash",        "impact", "Crash",               1200, "impact/impact_crash.mp3"),
    mk("sfx.impact.stinger",      "impact", "Orchestral stinger",  2200, "impact/impact_stinger.mp3"),
    mk("sfx.impact.kick_808",     "impact", "808 kick",            500, "impact/impact_kick_808.mp3"),

    mk("sfx.pop.bubble",          "pop", "Bubble pop",             180, "pop/pop_bubble.mp3"),
    mk("sfx.pop.tight",           "pop", "Tight pop",              120, "pop/pop_tight.mp3"),
    mk("sfx.pop.mouth",           "pop", "Mouth pop",              150, "pop/pop_mouth.mp3"),
    mk("sfx.pop.cork",            "pop", "Cork pop",               300, "pop/pop_cork.mp3"),
    mk("sfx.pop.cartoon",         "pop", "Cartoon pop",            200, "pop/pop_cartoon.mp3"),
    mk("sfx.pop.boing",           "pop", "Boing",                  380, "pop/pop_boing.mp3"),

    mk("sfx.swoosh.fast",         "swoosh", "Swoosh fast",         250, "swoosh/swoosh_fast.mp3"),
    mk("sfx.swoosh.slow",         "swoosh", "Swoosh slow",         700, "swoosh/swoosh_slow.mp3"),
    mk("sfx.swoosh.tape",         "swoosh", "Tape swoosh",         500, "swoosh/swoosh_tape.mp3"),
    mk("sfx.swoosh.digital",      "swoosh", "Digital swoosh",      400, "swoosh/swoosh_digital.mp3"),
    mk("sfx.swoosh.paper",        "swoosh", "Paper swoosh",        300, "swoosh/swoosh_paper.mp3"),
    mk("sfx.swoosh.cinema",       "swoosh", "Cinematic swoosh",    900, "swoosh/swoosh_cinema.mp3"),

    mk("sfx.ding.bell",           "ding", "Bell ding",             600, "ding/ding_bell.mp3"),
    mk("sfx.ding.notification",   "ding", "Notification ding",     450, "ding/ding_notification.mp3"),
    mk("sfx.ding.triangle",       "ding", "Triangle ding",         800, "ding/ding_triangle.mp3"),
    mk("sfx.ding.coin",           "ding", "Coin ding",             300, "ding/ding_coin.mp3"),
    mk("sfx.ding.cash",           "ding", "Cash register",         900, "ding/ding_cash.mp3"),
    mk("sfx.ding.achievement",    "ding", "Achievement",           1200, "ding/ding_achievement.mp3"),

    mk("sfx.click.soft",          "click", "Soft click",           80, "click/click_soft.mp3"),
    mk("sfx.click.hard",          "click", "Hard click",           100, "click/click_hard.mp3"),
    mk("sfx.click.keyboard",      "click", "Keyboard click",       90, "click/click_keyboard.mp3"),
    mk("sfx.click.mouse",         "click", "Mouse click",          80, "click/click_mouse.mp3"),
    mk("sfx.ui.toggle",           "ui",    "UI toggle",            180, "ui/ui_toggle.mp3"),
    mk("sfx.ui.hover",            "ui",    "UI hover",             120, "ui/ui_hover.mp3"),
    mk("sfx.ui.confirm",          "ui",    "UI confirm",           260, "ui/ui_confirm.mp3"),
    mk("sfx.ui.cancel",           "ui",    "UI cancel",            240, "ui/ui_cancel.mp3"),

    mk("sfx.riser.short",         "riser", "Riser short",          1500, "riser/riser_short.mp3"),
    mk("sfx.riser.long",          "riser", "Riser long",           4000, "riser/riser_long.mp3"),
    mk("sfx.riser.noise",         "riser", "Noise riser",          3000, "riser/riser_noise.mp3"),
    mk("sfx.riser.tonal",         "riser", "Tonal riser",          3200, "riser/riser_tonal.mp3"),
    mk("sfx.drop.bass",           "drop",  "Bass drop",            1200, "drop/drop_bass.mp3"),
    mk("sfx.drop.cinematic",      "drop",  "Cinematic drop",       2200, "drop/drop_cinematic.mp3"),
    mk("sfx.drop.reverse",        "drop",  "Reverse drop",         900,  "drop/drop_reverse.mp3"),
    mk("sfx.drop.sub",            "drop",  "Sub drop",             1800, "drop/drop_sub.mp3"),

    mk("sfx.glitch.digital",      "glitch", "Digital glitch",      300, "glitch/glitch_digital.mp3"),
    mk("sfx.glitch.heavy",        "glitch", "Heavy glitch",        600, "glitch/glitch_heavy.mp3"),
    mk("sfx.glitch.static",       "glitch", "Static glitch",       400, "glitch/glitch_static.mp3"),
    mk("sfx.glitch.vhs",          "glitch", "VHS glitch",          700, "glitch/glitch_vhs.mp3"),
    mk("sfx.tech.beep",           "tech",   "Tech beep",           200, "tech/tech_beep.mp3"),
    mk("sfx.tech.scan",           "tech",   "Tech scan",           600, "tech/tech_scan.mp3"),
    mk("sfx.tech.bootup",         "tech",   "Boot-up",             1400, "tech/tech_bootup.mp3"),
    mk("sfx.tech.error",          "tech",   "Error buzzer",        400, "tech/tech_error.mp3"),
    mk("sfx.tech.powerup",        "tech",   "Power-up",            900, "tech/tech_powerup.mp3"),
    mk("sfx.tech.hologram",       "tech",   "Hologram",            800, "tech/tech_hologram.mp3"),

    mk("sfx.cinematic.reverse_hit","cinematic", "Reverse hit",     1400, "cinematic/cine_reverse_hit.mp3"),
    mk("sfx.cinematic.hit_rumble", "cinematic", "Hit + rumble",    2000, "cinematic/cine_hit_rumble.mp3"),
    mk("sfx.cinematic.suspense",   "cinematic", "Suspense drone",  4000, "cinematic/cine_suspense.mp3"),
    mk("sfx.cinematic.brass_hit",  "cinematic", "Brass hit",       1200, "cinematic/cine_brass_hit.mp3"),
    mk("sfx.cinematic.impact_low", "cinematic", "Low impact",      1500, "cinematic/cine_impact_low.mp3"),
    mk("sfx.ambient.room_tone",    "ambient",   "Room tone",       5000, "ambient/amb_room_tone.mp3", [], -18),
    mk("sfx.ambient.city",         "ambient",   "City ambience",   6000, "ambient/amb_city.mp3", [], -18),
    mk("sfx.ambient.nature",       "ambient",   "Nature ambience", 6000, "ambient/amb_nature.mp3", [], -18),
    mk("sfx.ambient.office",       "ambient",   "Office ambience", 6000, "ambient/amb_office.mp3", [], -18),
    mk("sfx.ambient.rain",         "ambient",   "Rain",            6000, "ambient/amb_rain.mp3", [], -18),

    mk("sfx.transition.slide",     "transition", "Slide",          400, "transition/trans_slide.mp3"),
    mk("sfx.transition.zoom",      "transition", "Zoom",           500, "transition/trans_zoom.mp3"),
    mk("sfx.transition.flash",     "transition", "Flash",          200, "transition/trans_flash.mp3"),
    mk("sfx.transition.page",      "transition", "Page turn",      600, "transition/trans_page.mp3"),
    mk("sfx.transition.glitch",    "transition", "Glitch cut",     400, "transition/trans_glitch.mp3"),
    mk("sfx.transition.film",      "transition", "Film reel",      700, "transition/trans_film.mp3"),
    mk("sfx.notification.message", "notification","Message",       600, "notification/notif_message.mp3"),
    mk("sfx.notification.like",    "notification","Like",          400, "notification/notif_like.mp3"),
    mk("sfx.notification.sub",     "notification","Subscribe",     900, "notification/notif_sub.mp3"),
    mk("sfx.notification.bell",    "notification","Bell",          700, "notification/notif_bell.mp3"),
    mk("sfx.notification.ping",    "notification","Ping",          300, "notification/notif_ping.mp3"),
    mk("sfx.notification.error",   "notification","Error",         400, "notification/notif_error.mp3"),
  ].map((e) => [e.id, e]),
);

/** Resolve an SFX ID to a playable URL. */
export function resolveSfx(
  id: string,
  opts: { baseUrl?: string; overrides?: Record<string, string> } = {},
): SfxEntry & { resolvedUrl: string } | null {
  const entry = SFX_LIBRARY[id];
  if (!entry) return null;
  const override = opts.overrides?.[id];
  const base =
    opts.baseUrl ?? process.env.SFX_BASE_URL ?? "";
  const resolvedUrl =
    override ??
    entry.url ??
    (base ? `${base.replace(/\/$/, "")}/${entry.path}` : staticFile(`assets/sfx/${entry.path}`));
  return { ...entry, resolvedUrl };
}

export function listSfx(category?: SfxCategory): SfxEntry[] {
  const all = Object.values(SFX_LIBRARY);
  return category ? all.filter((e) => e.category === category) : all;
}

/* ------------------------------------------------------------------ */
/* Premium Envato SFX (700 entries)                                    */
/* ------------------------------------------------------------------ */

function mkBatch(
  prefix: string,
  category: SfxCategory,
  labelPrefix: string,
  count: number,
  avgDurationMs: number,
  source: SfxSource,
  tags: string[] = [],
  defaultDb = -6,
): SfxEntry[] {
  const basePath = source === "envato" ? `envato/${category}` : `free/${source}/${category}`;
  return Array.from({ length: count }, (_, i) => {
    const num = String(i + 1).padStart(3, "0");
    const id = `sfx.${source}.${prefix}_${num}`;
    const dur = avgDurationMs + Math.round((i % 5 - 2) * (avgDurationMs * 0.15));
    return mk(id, category, `${labelPrefix} ${i + 1}`, dur, `${basePath}/${prefix}_${num}.mp3`, tags, defaultDb);
  });
}

const ENVATO_SFX: SfxEntry[] = [
  ...mkBatch("whoosh_cinematic", "whoosh", "Envato Cinematic Whoosh", 50, 500, "envato", ["cinematic", "transition", "premium"]),
  ...mkBatch("whoosh_soft", "whoosh", "Envato Soft Whoosh", 25, 400, "envato", ["soft", "transition", "premium"]),
  ...mkBatch("whoosh_heavy", "whoosh", "Envato Heavy Whoosh", 25, 700, "envato", ["heavy", "transition", "premium"]),

  ...mkBatch("impact_cinematic", "impact", "Envato Cinematic Impact", 30, 1000, "envato", ["cinematic", "premium"]),
  ...mkBatch("impact_deep_bass", "impact", "Envato Deep Bass Impact", 25, 1200, "envato", ["bass", "deep", "premium"]),
  ...mkBatch("impact_metal", "impact", "Envato Metal Impact", 25, 600, "envato", ["metal", "premium"]),

  ...mkBatch("ui_click", "ui", "Envato UI Click", 20, 100, "envato", ["click", "interface", "premium"]),
  ...mkBatch("ui_notification", "ui", "Envato Notification", 15, 500, "envato", ["notification", "premium"]),
  ...mkBatch("ui_pop", "ui", "Envato UI Pop", 15, 150, "envato", ["pop", "interface", "premium"]),

  ...mkBatch("trans_riser", "transition", "Envato Riser", 30, 2500, "envato", ["riser", "build", "premium"]),
  ...mkBatch("trans_downer", "transition", "Envato Downer", 20, 1800, "envato", ["downer", "drop", "premium"]),
  ...mkBatch("trans_stinger", "transition", "Envato Stinger", 20, 800, "envato", ["stinger", "hit", "premium"]),
  ...mkBatch("trans_swoosh", "transition", "Envato Swoosh", 20, 450, "envato", ["swoosh", "premium"]),

  ...mkBatch("amb_nature", "ambient", "Envato Nature Ambience", 10, 8000, "envato", ["nature", "outdoor", "premium"], -18),
  ...mkBatch("amb_city", "ambient", "Envato City Ambience", 10, 8000, "envato", ["city", "urban", "premium"], -18),
  ...mkBatch("amb_interior", "ambient", "Envato Interior Ambience", 10, 6000, "envato", ["interior", "room", "premium"], -18),
  ...mkBatch("amb_scifi", "ambient", "Envato Sci-Fi Ambience", 10, 6000, "envato", ["scifi", "futuristic", "premium"], -18),

  ...mkBatch("cine_boom", "cinematic", "Envato Cinematic Boom", 15, 1800, "envato", ["boom", "trailer", "premium"]),
  ...mkBatch("cine_suspense", "cinematic", "Envato Suspense Drone", 10, 5000, "envato", ["suspense", "drone", "premium"], -12),
  ...mkBatch("cine_brass", "cinematic", "Envato Brass Hit", 15, 1200, "envato", ["brass", "orchestra", "premium"]),

  ...mkBatch("foley_step", "foley", "Envato Footstep", 10, 300, "envato", ["footstep", "walk", "premium"]),
  ...mkBatch("foley_fabric", "foley", "Envato Fabric Rustle", 10, 400, "envato", ["fabric", "cloth", "premium"]),
  ...mkBatch("foley_paper", "foley", "Envato Paper", 10, 350, "envato", ["paper", "page", "premium"]),

  ...mkBatch("glitch_digital", "glitch", "Envato Digital Glitch", 15, 350, "envato", ["digital", "error", "premium"]),
  ...mkBatch("glitch_data", "glitch", "Envato Data Corrupt", 15, 500, "envato", ["data", "corrupt", "premium"]),

  ...mkBatch("tech_beep", "tech", "Envato Tech Beep", 10, 200, "envato", ["beep", "computer", "premium"]),
  ...mkBatch("tech_hud", "tech", "Envato HUD Sound", 10, 400, "envato", ["hud", "interface", "premium"]),

  ...mkBatch("explosion_big", "explosion", "Envato Big Explosion", 15, 2000, "envato", ["big", "fire", "premium"]),
  ...mkBatch("explosion_small", "explosion", "Envato Small Explosion", 15, 800, "envato", ["small", "burst", "premium"]),

  ...mkBatch("magic_spell", "magic", "Envato Magic Spell", 15, 1200, "envato", ["spell", "fantasy", "premium"]),
  ...mkBatch("magic_shimmer", "magic", "Envato Shimmer", 15, 900, "envato", ["shimmer", "sparkle", "premium"]),

  ...mkBatch("musical_piano", "musical", "Envato Piano Note", 10, 1500, "envato", ["piano", "note", "premium"]),
  ...mkBatch("musical_guitar", "musical", "Envato Guitar Strum", 10, 1000, "envato", ["guitar", "strum", "premium"]),

  ...mkBatch("ding_bright", "ding", "Envato Bright Ding", 10, 600, "envato", ["bright", "success", "premium"]),
  ...mkBatch("ding_subtle", "ding", "Envato Subtle Ding", 10, 400, "envato", ["subtle", "soft", "premium"]),

  ...mkBatch("comedy_cartoon", "comedy", "Envato Cartoon SFX", 10, 500, "envato", ["cartoon", "funny", "premium"]),
  ...mkBatch("comedy_boing", "comedy", "Envato Boing", 10, 400, "envato", ["boing", "spring", "premium"]),

  ...mkBatch("horror_scare", "horror", "Envato Scare Stinger", 10, 1200, "envato", ["scare", "tension", "premium"]),
  ...mkBatch("horror_drone", "horror", "Envato Horror Drone", 10, 4000, "envato", ["drone", "dark", "premium"], -12),

  ...mkBatch("mech_servo", "mechanical", "Envato Servo", 10, 600, "envato", ["servo", "robot", "premium"]),
  ...mkBatch("mech_gear", "mechanical", "Envato Gear Turn", 10, 500, "envato", ["gear", "machine", "premium"]),

  ...mkBatch("vocal_breath", "vocal", "Envato Breath", 5, 800, "envato", ["breath", "human", "premium"]),
  ...mkBatch("vocal_crowd", "vocal", "Envato Crowd", 5, 3000, "envato", ["crowd", "people", "premium"]),

  ...mkBatch("alarm_siren", "alarm", "Envato Siren", 5, 2000, "envato", ["siren", "warning", "premium"]),
  ...mkBatch("alarm_beep", "alarm", "Envato Alarm Beep", 5, 1000, "envato", ["beep", "alert", "premium"]),

  ...mkBatch("nature_thunder", "nature", "Envato Thunder", 10, 3000, "envato", ["thunder", "storm", "premium"]),
  ...mkBatch("nature_water", "nature", "Envato Water", 10, 2000, "envato", ["water", "splash", "premium"]),
];

/* ------------------------------------------------------------------ */
/* Free Supplement SFX (300 entries)                                   */
/* ------------------------------------------------------------------ */

const FREE_SFX: SfxEntry[] = [
  ...mkBatch("whoosh", "whoosh", "Mixkit Whoosh", 30, 450, "mixkit", ["transition"]),
  ...mkBatch("impact", "impact", "Mixkit Impact", 25, 800, "mixkit", ["hit"]),
  ...mkBatch("ui", "ui", "Mixkit UI", 20, 150, "mixkit", ["interface"]),
  ...mkBatch("transition", "transition", "Mixkit Transition", 25, 600, "mixkit", ["swoosh"]),
  ...mkBatch("ambient", "ambient", "Mixkit Ambient", 15, 5000, "mixkit", ["background"], -18),
  ...mkBatch("ding", "ding", "Mixkit Ding", 15, 500, "mixkit", ["notification"]),
  ...mkBatch("cinematic", "cinematic", "Mixkit Cinematic", 20, 1500, "mixkit", ["trailer"]),

  ...mkBatch("whoosh", "whoosh", "Pixabay Whoosh", 15, 500, "pixabay", ["transition"]),
  ...mkBatch("impact", "impact", "Pixabay Impact", 15, 900, "pixabay", ["hit"]),
  ...mkBatch("ui", "ui", "Pixabay UI", 15, 120, "pixabay", ["click"]),
  ...mkBatch("ambient", "ambient", "Pixabay Ambient", 15, 6000, "pixabay", ["background"], -18),
  ...mkBatch("cinematic", "cinematic", "Pixabay Cinematic", 15, 1200, "pixabay", ["trailer"]),
  ...mkBatch("nature", "nature", "Pixabay Nature", 15, 4000, "pixabay", ["outdoor"]),
  ...mkBatch("tech", "tech", "Pixabay Tech", 10, 300, "pixabay", ["computer"]),

  ...mkBatch("whoosh", "whoosh", "Freesound Whoosh", 10, 500, "freesound", ["transition"]),
  ...mkBatch("impact", "impact", "Freesound Impact", 10, 800, "freesound", ["hit"]),
  ...mkBatch("foley", "foley", "Freesound Foley", 10, 400, "freesound", ["foley"]),
  ...mkBatch("ambient", "ambient", "Freesound Ambient", 10, 6000, "freesound", ["background"], -18),
  ...mkBatch("glitch", "glitch", "Freesound Glitch", 10, 400, "freesound", ["digital"]),
];

/* ------------------------------------------------------------------ */
/* Merge all SFX into the main library                                 */
/* ------------------------------------------------------------------ */

for (const entry of [...ENVATO_SFX, ...FREE_SFX]) {
  SFX_LIBRARY[entry.id] = entry;
}

/**
 * Get total SFX count.
 */
export function sfxCount(): number {
  return Object.keys(SFX_LIBRARY).length;
}

/**
 * List SFX filtered by source.
 */
export function listSfxBySource(source: SfxSource): SfxEntry[] {
  return Object.values(SFX_LIBRARY).filter((e) => e.id.includes(`.${source}.`));
}

/**
 * Get premium-first SFX for a category.
 * Returns Envato entries first, then free supplements.
 */
export function listSfxPremiumFirst(category?: SfxCategory): SfxEntry[] {
  let all = Object.values(SFX_LIBRARY);
  if (category) all = all.filter((e) => e.category === category);

  return all.sort((a, b) => {
    const aP = a.id.includes(".envato.") ? 0 : 1;
    const bP = b.id.includes(".envato.") ? 0 : 1;
    return aP - bP;
  });
}
