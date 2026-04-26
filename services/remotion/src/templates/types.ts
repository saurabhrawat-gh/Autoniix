/** Scene category = second segment of a `scene.*.*` preset ID. */
export type SceneCategory = string;

export interface Template {
  id: string;
  description: string;
  /** [min, max] fraction of total duration per scene category (e.g. "stock", "kinetic"). */
  ratio_budgets?: Record<SceneCategory, [number, number]>;
  cuts_per_minute?: [number, number];
  /** Transition preset ID *prefixes* that are allowed. */
  allowed_transition_prefixes?: string[];
  /** Transition preset IDs or prefixes that are forbidden. */
  forbidden_transition_prefixes?: string[];
  default_grade: string; // an `fx.grade.*` preset ID
  default_caption: string; // an `ov.caption.*` preset ID
  default_music_style?: string; // freeform label (upstream music selector uses this)
}
