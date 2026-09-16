/**
 * AE-291 — Channel creation wizard per-step validation.
 *
 * Pure functions: given the current `state` they return `{valid, errors}`
 * for a single step. The keys in `errors` correspond to `FormState` field
 * names (or synthetic keys like `pillars[0].name`) so the UI can render
 * inline error helpers next to the right input.
 */

export type WizardErrors = Record<string, string>;

export type StepValidation = {
  valid: boolean;
  errors: WizardErrors;
};

const HEX_RE = /^#([0-9a-fA-F]{3}){1,2}$/;

export function validateBasics(state: any): StepValidation {
  const errors: WizardErrors = {};
  const name: string = (state.channel_name ?? "").trim();
  if (!name) errors.channel_name = "Channel name is required.";
  else if (name.length < 3) errors.channel_name = "Must be at least 3 characters.";
  else if (name.length > 50) errors.channel_name = "Must be 50 characters or fewer.";

  if (!(state.niche ?? "").trim()) errors.niche = "Pick a niche.";
  if (!(state.primary_language ?? "").trim()) errors.primary_language = "Select a primary language.";
  const handle: string = (state.handle ?? "").trim();
  if (!handle) errors.handle = "YouTube handle is required (e.g. @YourChannel).";
  else if (!handle.startsWith("@")) errors.handle = "Handle must start with @.";
  if (!["short", "long", "mixed"].includes(state.content_mode)) {
    errors.content_mode = "Pick a content mode.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateStrategy(state: any): StepValidation {
  const errors: WizardErrors = {};
  const tags: string[] = state.content_type_tags ?? [];
  if (tags.length === 0) {
    errors.content_type_tags = "Pick at least one channel-type tag.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateMissionPillars(state: any): StepValidation {
  const errors: WizardErrors = {};
  const mission: string = (state.mission ?? "").trim();
  if (!mission) errors.mission = "Mission statement is required.";
  else if (mission.length < 20) errors.mission = "At least 20 characters — describe why this channel exists.";

  const pillars: Array<{ name?: string; description?: string }> = state.pillars ?? [];
  if (pillars.length < 2) {
    errors.pillars = "Add at least 2 content pillars.";
  } else {
    pillars.forEach((p, i) => {
      const n = (p.name ?? "").trim();
      const d = (p.description ?? "").trim();
      if (n.length < 3) errors[`pillars[${i}].name`] = "Pillar name must be at least 3 characters.";
      if (d.length < 10) errors[`pillars[${i}].description`] = "Pillar description must be at least 10 characters.";
    });
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateVoice(state: any): StepValidation {
  const errors: WizardErrors = {};
  if (!(state.narration_style ?? "").trim()) errors.narration_style = "Describe your narration style.";
  if (!(state.music_style ?? "").trim()) errors.music_style = "Pick a music direction.";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateVisual(state: any): StepValidation {
  const errors: WizardErrors = {};
  if (!(state.thumbnail_style ?? "").trim()) {
    errors.thumbnail_style = "Describe your thumbnail style.";
  }
  if (!HEX_RE.test(state.primary_color ?? "")) {
    errors.primary_color = "Enter a valid hex color (e.g. #7c3aed).";
  }
  if (!HEX_RE.test(state.secondary_color ?? "")) {
    errors.secondary_color = "Enter a valid hex color.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

const URL_RE = /^https?:\/\/[\w.-]+(\.[a-z]{2,})+([/?#].*)?$/i;
const YT_RE = /^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i;

export function validateReferences(state: any): StepValidation {
  const errors: WizardErrors = {};
  const refs: Array<{ kind: string; uri?: string }> = state.references ?? [];
  refs.forEach((r, i) => {
    const uri = (r.uri ?? "").trim();
    if (!uri) {
      errors[`references[${i}].uri`] = "URL or storage key is required.";
      return;
    }
    if (r.kind === "url" || r.kind === "video" || r.kind === "gdrive" || r.kind === "notion") {
      if (!URL_RE.test(uri)) {
        errors[`references[${i}].uri`] = "Must be a valid http(s):// URL.";
      } else if (r.kind === "video" && !YT_RE.test(uri)) {
        errors[`references[${i}].uri`] = "Video references must be a YouTube URL.";
      }
    }
  });
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateAutomation(state: any): StepValidation {
  const errors: WizardErrors = {};
  if (!["never", "first_10", "always"].includes(state.human_review_required)) {
    errors.human_review_required = "Pick a human-review policy.";
  }
  const sw = Number(state.videos_per_week_short);
  const lw = Number(state.videos_per_week_long);
  if (Number.isNaN(sw) || sw < 0 || sw > 50) {
    errors.videos_per_week_short = "Must be between 0 and 50.";
  }
  if (Number.isNaN(lw) || lw < 0 || lw > 50) {
    errors.videos_per_week_long = "Must be between 0 and 50.";
  }
  if (sw + lw === 0) {
    errors.videos_per_week_short =
      errors.videos_per_week_short || "You must publish at least 1 video per week (short or long).";
  }
  const cap = Number(state.max_daily_api_spend);
  if (Number.isNaN(cap) || cap < 1) {
    errors.max_daily_api_spend = "Daily spend cap must be at least $1.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

const STEP_KEYS = ["basics", "strategy", "pillars", "voice", "visual", "references", "automation", "review"] as const;

export type StepKey = (typeof STEP_KEYS)[number];

const VALIDATORS: Record<Exclude<StepKey, "review">, (s: any) => StepValidation> = {
  basics: validateBasics,
  strategy: validateStrategy,
  pillars: validateMissionPillars,
  voice: validateVoice,
  visual: validateVisual,
  references: validateReferences,
  automation: validateAutomation,
};

export function validateStep(stepKey: StepKey, state: any): StepValidation {
  if (stepKey === "review") {
    const errs: WizardErrors = {};
    let valid = true;
    (Object.keys(VALIDATORS) as Array<keyof typeof VALIDATORS>).forEach((k) => {
      const r = VALIDATORS[k](state);
      if (!r.valid) {
        valid = false;
        errs[k] = `Step "${k}" has issues.`;
      }
    });
    return { valid, errors: errs };
  }
  return VALIDATORS[stepKey](state);
}

/** Compute validity for every step. Memoize by passing a stable state ref. */
export function computeAllValidity(state: any): Record<StepKey, boolean> {
  const out = {} as Record<StepKey, boolean>;
  STEP_KEYS.forEach((k) => {
    out[k] = validateStep(k, state).valid;
  });
  return out;
}
